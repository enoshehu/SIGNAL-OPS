"""One-time historical loading and coverage reporting."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from signalops.catalog import load_catalog
from signalops.config import load_settings
from signalops.sync import SyncSummary, synchronize

ARCHIVE_DATASETS = (
    "dwd_weather",
    "dwd_precipitation",
    "dwd_wind",
    "dwd_wind_gust",
)


def weather_coverage(database: Path, cutoff: datetime) -> list[dict[str, object]]:
    """Summarize retained canonical weather coverage at city-metric grain."""
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT json_extract(e.attributes_json, '$.city') AS city,
                   o.metric,
                   MIN(o.observed_at) AS first_hour,
                   MAX(o.observed_at) AS last_hour,
                   COUNT(DISTINCT o.observed_at) AS hours
            FROM observations o
            JOIN entities e ON e.entity_key = o.entity_key
            WHERE o.observed_at >= ? AND o.dataset_key IN (?, ?, ?, ?)
            GROUP BY city, o.metric
            ORDER BY city, o.metric
            """,
            (cutoff.astimezone(UTC).isoformat(), *ARCHIVE_DATASETS),
        ).fetchall()
    return [dict(row) for row in rows]


def backfill_weather(
    config: Path, *, days: int = 180, cities: tuple[str, ...] = (), now: datetime | None = None
) -> tuple[SyncSummary, Path, list[dict[str, object]]]:
    """Download DWD rolling archives and retain the requested historical window."""
    if days <= 0:
        raise ValueError("Backfill days must be positive")
    settings = load_settings(config)
    if days > settings.retention_days:
        raise ValueError(
            f"Backfill requests {days} days but retention is {settings.retention_days} days"
        )
    catalog = load_catalog(config.resolve().parent / "datasets")
    datasets = tuple(key for key in ARCHIVE_DATASETS if key in catalog)
    current = (now or datetime.now(UTC)).astimezone(UTC)
    summary = synchronize(
        config,
        force=True,
        datasets=datasets,
        cities=cities,
        now=current,
    )
    database = settings.data_dir / "signalops.sqlite"
    cutoff = current - timedelta(days=days)
    coverage = weather_coverage(database, cutoff)
    report = settings.data_dir / "processed" / "historical_coverage.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps(
            {
                "generated_at": current.isoformat(),
                "requested_days": days,
                "cutoff": cutoff.isoformat(),
                "database": str(database),
                "coverage": coverage,
                "rail_history_note": (
                    "The DB Timetables API has no equivalent historical actuals archive. "
                    "Rail history begins with SIGNAL//OPS collection and accumulates forward."
                ),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return summary, report, coverage
