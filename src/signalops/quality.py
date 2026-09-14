"""Small, inspectable data-quality checks with persisted evidence."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3

from signalops.catalog import DatasetDefinition
from signalops.storage import SQLiteRecordStore


QUALITY_SCHEMA = """
CREATE TABLE IF NOT EXISTS quality_runs (
  run_id INTEGER PRIMARY KEY, dataset_key TEXT NOT NULL, import_id INTEGER NOT NULL,
  executed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quality_results (
  result_id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES quality_runs(run_id),
  rule_key TEXT NOT NULL, status TEXT NOT NULL, records_checked INTEGER NOT NULL,
  records_failed INTEGER NOT NULL, details_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quality_failures (
  result_id INTEGER NOT NULL REFERENCES quality_results(result_id),
  item_id TEXT NOT NULL, reason TEXT NOT NULL,
  PRIMARY KEY (result_id, item_id)
);
CREATE TABLE IF NOT EXISTS schema_snapshots (
  snapshot_id INTEGER PRIMARY KEY, dataset_key TEXT NOT NULL, import_id INTEGER NOT NULL,
  fingerprint TEXT NOT NULL, fields_json TEXT NOT NULL, observed_at TEXT NOT NULL,
  UNIQUE(dataset_key, fingerprint)
);
"""


@dataclass(frozen=True, slots=True)
class QualityResult:
    rule: str
    status: str
    checked: int
    failed: int
    details: dict[str, object]
    affected_ids: tuple[str, ...] = ()


def assess(
    database: Path, definition: DatasetDefinition, entity_key: str | None = None
) -> list[QualityResult]:
    # Quality can be the first command run after an upgrade, so prepare older databases here too.
    with SQLiteRecordStore(database):
        pass
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(QUALITY_SCHEMA)
        rules = {str(rule["key"]): rule for rule in definition.quality}
        known_rules = {
            "valid_timestamp", "humidity_range", "value_present", "unique_observation",
            "entity_integrity", "hourly_continuity", "freshness", "schema_drift",
        }
        unknown = sorted(set(rules) - known_rules)
        if unknown:
            raise ValueError(f"Unknown quality rule: {', '.join(unknown)}")

        if entity_key:
            scope_key = entity_key.split(":", 1)[1]
            latest = connection.execute(
                "SELECT MAX(id) FROM artifact_imports WHERE source = ? AND scope_key = ?",
                (definition.adapter, scope_key),
            ).fetchone()[0]
        else:
            latest = connection.execute(
                "SELECT MAX(id) FROM artifact_imports WHERE source = ?", (definition.adapter,)
            ).fetchone()[0]
        if latest is None:
            target = entity_key or definition.adapter
            raise ValueError(f"No imported data found for scope: {target}")

        if definition.adapter == "dwd":
            sql = (
                "SELECT observation_id, entity_key, observed_at, metric, value FROM observations "
                "WHERE dataset_key = ? AND import_id = ?"
            )
        else:
            sql = (
                "SELECT event_id, entity_key, COALESCE(planned_at, changed_at), "
                "event_type, NULL FROM service_events "
                "WHERE dataset_key = ? AND import_id = ?"
            )
        parameters: tuple[object, ...] = (definition.key, latest)
        if entity_key:
            sql += " AND entity_key = ?"
            parameters += (entity_key,)
        rows = connection.execute(sql, parameters).fetchall()
        if not rows:
            raise ValueError(f"No canonical rows found for latest import: {latest}")

        results: list[QualityResult] = []
        for key in rules:
            if key == "valid_timestamp":
                affected = tuple(row[0] for row in rows if not _valid_time(row[2]))
                results.append(_result(key, len(rows), affected, rules[key]))
            elif key == "humidity_range":
                humidity = [row for row in rows if row[3] == "relative_humidity"]
                affected = tuple(
                    row[0] for row in humidity
                    if row[4] is not None and not 0 <= row[4] <= 100
                )
                results.append(_result(key, len(humidity), affected, rules[key]))
            elif key == "value_present":
                affected = tuple(row[0] for row in rows if row[4] is None)
                results.append(_result(key, len(rows), affected, rules[key]))
            elif key == "unique_observation":
                seen: set[tuple[str, str, str]] = set()
                affected_list: list[str] = []
                for row in rows:
                    grain = (row[1], row[2], row[3])
                    if grain in seen:
                        affected_list.append(row[0])
                    seen.add(grain)
                results.append(_result(key, len(rows), tuple(affected_list), rules[key]))
            elif key == "entity_integrity":
                known = {row[0] for row in connection.execute("SELECT entity_key FROM entities")}
                affected = tuple(row[0] for row in rows if row[1] not in known)
                results.append(_result(key, len(rows), affected, rules[key]))
            elif key == "hourly_continuity":
                results.append(_hourly_continuity(rows, rules[key]))
            elif key == "freshness":
                results.append(_freshness(rows, rules[key]))
            elif key == "schema_drift":
                results.append(_schema_drift(connection, definition, latest, rules[key]))

        executed_at = datetime.now(UTC).isoformat()
        with connection:
            cursor = connection.execute(
                "INSERT INTO quality_runs(dataset_key, import_id, executed_at) VALUES (?, ?, ?)",
                (definition.key, latest, executed_at),
            )
            run_id = cursor.lastrowid
            for item in results:
                result_cursor = connection.execute(
                    """INSERT INTO quality_results
                       (run_id, rule_key, status, records_checked, records_failed, details_json)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (run_id, item.rule, item.status, item.checked, item.failed,
                     json.dumps(item.details, sort_keys=True)),
                )
                connection.executemany(
                    "INSERT INTO quality_failures(result_id, item_id, reason) VALUES (?, ?, ?)",
                    [(result_cursor.lastrowid, item_id, str(item.details["reason"]))
                     for item_id in item.affected_ids],
                )
        return results


def _result(
    key: str, checked: int, affected: tuple[str, ...], rule: dict[str, object]
) -> QualityResult:
    severity = str(rule.get("severity", "medium"))
    status = "pass" if not affected else ("failure" if severity == "high" else "warning")
    reason = "No problems found" if not affected else f"{len(affected)} checked items failed"
    return QualityResult(
        key, status, checked, len(affected), {"severity": severity, "reason": reason}, affected
    )


def _valid_time(value: str) -> bool:
    try:
        return datetime.fromisoformat(value).utcoffset() is not None
    except (TypeError, ValueError):
        return False


def _freshness(rows: list[tuple], rule: dict[str, object]) -> QualityResult:
    max_age = int(rule["max_age_minutes"])
    timestamps = [datetime.fromisoformat(row[2]) for row in rows if _valid_time(row[2])]
    if not timestamps:
        return QualityResult(
            "freshness", "failure", len(rows), len(rows),
            {"max_age_minutes": max_age, "reason": "No valid timestamp is available"},
        )
    age = max(0, int((datetime.now(UTC) - max(timestamps)).total_seconds() // 60))
    failed = int(age > max_age)
    return QualityResult(
        "freshness", "warning" if failed else "pass", len(rows), failed,
        {"age_minutes": age, "max_age_minutes": max_age,
         "reason": "Latest observation exceeds the configured age" if failed else
                   "Latest observation is within the configured age"},
    )


def _hourly_continuity(rows: list[tuple], rule: dict[str, object]) -> QualityResult:
    timestamps = sorted({datetime.fromisoformat(row[2]) for row in rows if _valid_time(row[2])})
    missing: list[str] = []
    for earlier, later in zip(timestamps, timestamps[1:]):
        expected = earlier + timedelta(hours=1)
        while expected < later:
            missing.append(expected.isoformat())
            expected += timedelta(hours=1)
    return _result("hourly_continuity", len(timestamps), tuple(missing), rule)


def _schema_drift(
    connection: sqlite3.Connection,
    definition: DatasetDefinition,
    import_id: int,
    rule: dict[str, object],
) -> QualityResult:
    payloads = connection.execute(
        "SELECT payload_json FROM parsed_raw_records WHERE import_id = ?", (import_id,)
    ).fetchall()
    total = len(payloads)
    fields: dict[str, dict[str, object]] = {}
    for (payload_json,) in payloads:
        for key, value in json.loads(payload_json).items():
            field = fields.setdefault(key, {"types": set(), "nullable": False, "present": 0})
            field["present"] = int(field["present"]) + 1
            if value is None:
                field["nullable"] = True
            else:
                field["types"].add(_json_type(value))
    schema = {
        key: {
            "types": sorted(field["types"]),
            "nullable": field["nullable"],
            "present": field["present"],
            "total": total,
        }
        for key, field in sorted(fields.items())
    }
    encoded = json.dumps(schema, sort_keys=True)
    signature_json = json.dumps(_signature(schema), sort_keys=True)
    fingerprint = hashlib.sha256(signature_json.encode()).hexdigest()
    previous = connection.execute(
        "SELECT fields_json FROM schema_snapshots "
        "WHERE dataset_key = ? ORDER BY snapshot_id LIMIT 1",
        (definition.key,),
    ).fetchone()
    added: list[str] = []
    removed: list[str] = []
    changed: list[str] = []
    if previous:
        old = json.loads(previous[0])
        added = sorted(set(schema) - set(old))
        removed = sorted(set(old) - set(schema))
        changed = sorted(
            key for key in set(old) & set(schema) if _field_changed(old[key], schema[key])
        )
    with connection:
        connection.execute(
            """INSERT OR IGNORE INTO schema_snapshots
               (dataset_key, import_id, fingerprint, fields_json, observed_at)
               VALUES (?, ?, ?, ?, ?)""",
            (definition.key, import_id, fingerprint, encoded, datetime.now(UTC).isoformat()),
        )
    failed = len(removed) + len(changed)
    status = "failure" if failed else ("warning" if added else "pass")
    affected = tuple(removed + changed + added)
    return QualityResult(
        "schema_drift", status, len(schema), failed,
        {"added": added, "removed": removed, "type_changed": changed,
         "severity": rule.get("severity", "high"),
         "reason": "Parsed payload schema changed" if affected else "Schema matches the baseline"},
        affected,
    )


def _json_type(value: object) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _signature(schema: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    return {
        key: {
            "types": field["types"],
            "required": field["present"] == field["total"],
        }
        for key, field in schema.items()
    }


def _field_changed(old: dict[str, object], new: dict[str, object]) -> bool:
    old_types = set(old.get("types", []))
    new_types = set(new.get("types", []))
    type_changed = bool(old_types and new_types and old_types != new_types)
    old_required = old.get("present") == old.get("total")
    new_required = new.get("present") == new.get("total")
    return type_changed or old_required != new_required
