"""Small operational signal and incident lifecycle for version 1.0."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from signalops.analysis import hourly_summary
from signalops.quality import QualityResult

OPERATIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS operational_signals (
  signal_id TEXT PRIMARY KEY,
  signal_type TEXT NOT NULL,
  entity_key TEXT NOT NULL,
  severity TEXT NOT NULL,
  detected_at TEXT NOT NULL,
  value REAL,
  threshold REAL,
  message TEXT NOT NULL,
  evidence_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS incidents (
  incident_id INTEGER PRIMARY KEY,
  signal_id TEXT NOT NULL REFERENCES operational_signals(signal_id),
  status TEXT NOT NULL CHECK(status IN ('open', 'resolved')),
  opened_at TEXT NOT NULL,
  closed_at TEXT,
  resolution TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS one_open_incident_per_signal
  ON incidents(signal_id) WHERE status = 'open';
"""


@dataclass(frozen=True, slots=True)
class Signal:
    signal_id: str
    signal_type: str
    entity_key: str
    severity: str
    detected_at: datetime
    value: float | None
    threshold: float | None
    message: str
    evidence: dict[str, object]


def analysis_signals(
    rows: Iterable[dict[str, object]], *, detected_at: datetime, delay_threshold: float = 20
) -> list[Signal]:
    """Create transparent rule-based signals from city-hour railway rows."""
    signals: list[Signal] = []
    for row in rows:
        city = str(row["city"])
        hour = str(row["hour_utc"])
        maximum = row.get("maximum_delay_minutes")
        cancellations = int(row.get("cancelled_events") or 0)
        if maximum is not None and float(maximum) > delay_threshold:
            signals.append(
                Signal(
                    f"delay_over_threshold:{city}:{hour}",
                    "DELAY_OVER_20_MINUTES",
                    city,
                    "high",
                    detected_at,
                    float(maximum),
                    delay_threshold,
                    f"Maximum positive delay in {city} exceeded {delay_threshold:g} minutes",
                    {"hour_utc": hour, "matched_events_only": True},
                )
            )
        if cancellations:
            signals.append(
                Signal(
                    f"cancellation:{city}:{hour}",
                    "CANCELLATION_DETECTED",
                    city,
                    "high",
                    detected_at,
                    float(cancellations),
                    0,
                    f"{cancellations} matched cancellation event(s) detected in {city}",
                    {"hour_utc": hour, "matched_events_only": True},
                )
            )
    return signals


def quality_signals(
    results: Iterable[QualityResult], *, dataset: str, entity_key: str, detected_at: datetime
) -> list[Signal]:
    """Convert only the two approved source-health rules into operational signals."""
    signals: list[Signal] = []
    mapping = {"freshness": "SOURCE_DATA_STALE", "schema_drift": "SCHEMA_CHANGED"}
    for result in results:
        signal_type = mapping.get(result.rule)
        if signal_type is None or result.status == "pass":
            continue
        signals.append(
            Signal(
                f"{signal_type.lower()}:{dataset}:{entity_key}",
                signal_type,
                entity_key,
                "high" if result.status == "failure" else "medium",
                detected_at,
                float(result.failed),
                0,
                str(result.details.get("reason", result.rule)),
                {"dataset": dataset, "rule": result.rule, "details": result.details},
            )
        )
    return signals


def persist_incidents(database: Path, signals: Iterable[Signal]) -> int:
    """Persist signals and open one incident per stable signal identity."""
    opened = 0
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(OPERATIONS_SCHEMA)
        for signal in signals:
            connection.execute(
                """INSERT OR IGNORE INTO operational_signals
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    signal.signal_id,
                    signal.signal_type,
                    signal.entity_key,
                    signal.severity,
                    signal.detected_at.astimezone(UTC).isoformat(),
                    signal.value,
                    signal.threshold,
                    signal.message,
                    json.dumps(signal.evidence, sort_keys=True),
                ),
            )
            cursor = connection.execute(
                """INSERT OR IGNORE INTO incidents
                   (signal_id, status, opened_at) VALUES (?, 'open', ?)""",
                (signal.signal_id, signal.detected_at.astimezone(UTC).isoformat()),
            )
            opened += cursor.rowcount
    return opened


def resolve_incident(database: Path, incident_id: int, resolution: str) -> None:
    if not resolution.strip():
        raise ValueError("Incident resolution is required")
    with closing(sqlite3.connect(database)) as connection, connection:
        cursor = connection.execute(
            """UPDATE incidents SET status = 'resolved', closed_at = ?, resolution = ?
               WHERE incident_id = ? AND status = 'open'""",
            (datetime.now(UTC).isoformat(), resolution.strip(), incident_id),
        )
        if cursor.rowcount != 1:
            raise ValueError(f"Open incident not found: {incident_id}")


def stored_quality_signals(database: Path, *, detected_at: datetime) -> list[Signal]:
    """Read only the latest stored quality run for each dataset."""
    query = """
    WITH latest AS (
      SELECT dataset_key, MAX(run_id) AS run_id FROM quality_runs GROUP BY dataset_key
    )
    SELECT q.dataset_key, a.source || ':' || a.scope_key AS entity_key,
           r.rule_key, r.status, r.records_checked, r.records_failed, r.details_json
    FROM latest l
    JOIN quality_runs q ON q.run_id = l.run_id
    JOIN quality_results r ON r.run_id = q.run_id
    JOIN artifact_imports a ON a.id = q.import_id
    WHERE r.rule_key IN ('freshness', 'schema_drift') AND r.status != 'pass'
    """
    try:
        with closing(sqlite3.connect(database)) as connection:
            rows = connection.execute(query).fetchall()
    except sqlite3.OperationalError:
        return []
    signals: list[Signal] = []
    for dataset, entity_key, rule, status, checked, failed, details in rows:
        result = QualityResult(rule, status, checked, failed, json.loads(details))
        signals.extend(
            quality_signals(
                [result], dataset=dataset, entity_key=entity_key, detected_at=detected_at
            )
        )
    return signals


def run_operational_cycle(
    database: Path, *, detected_at: datetime | None = None
) -> tuple[int, int]:
    observed_at = detected_at or datetime.now(UTC)
    signals = analysis_signals(hourly_summary(database), detected_at=observed_at)
    signals.extend(stored_quality_signals(database, detected_at=observed_at))
    return len(signals), persist_incidents(database, signals)
