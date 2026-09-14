"""Bound live operational storage to a rolling time window."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RetentionResult:
    cutoff: datetime
    raw_cutoff: datetime
    database_rows_deleted: int
    raw_artifacts_deleted: int


def _tables(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }


def _delete(connection: sqlite3.Connection, statement: str, parameters: tuple = ()) -> int:
    cursor = connection.execute(statement, parameters)
    return max(cursor.rowcount, 0)


def prune_database(database: Path, cutoff: datetime) -> int:
    """Delete source and operational rows older than cutoff, then reclaim disk space."""
    if cutoff.tzinfo is None:
        raise ValueError("Retention cutoff must be timezone-aware")
    cutoff_utc = cutoff.astimezone(UTC)
    cutoff_iso = cutoff_utc.isoformat()
    cutoff_dwd = cutoff_utc.strftime("%Y%m%d%H")
    deleted = 0
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        tables = _tables(connection)
        with connection:
            if {"quality_failures", "quality_results", "quality_runs"} <= tables:
                deleted += _delete(
                    connection,
                    "DELETE FROM quality_failures WHERE result_id IN "
                    "(SELECT result_id FROM quality_results WHERE run_id IN "
                    "(SELECT run_id FROM quality_runs WHERE executed_at < ?))",
                    (cutoff_iso,),
                )
                deleted += _delete(
                    connection,
                    "DELETE FROM quality_results WHERE run_id IN "
                    "(SELECT run_id FROM quality_runs WHERE executed_at < ?)",
                    (cutoff_iso,),
                )
                deleted += _delete(
                    connection, "DELETE FROM quality_runs WHERE executed_at < ?", (cutoff_iso,)
                )
            if {"incidents", "operational_signals"} <= tables:
                deleted += _delete(
                    connection,
                    "DELETE FROM incidents WHERE signal_id IN "
                    "(SELECT signal_id FROM operational_signals WHERE detected_at < ?)",
                    (cutoff_iso,),
                )
                deleted += _delete(
                    connection,
                    "DELETE FROM operational_signals WHERE detected_at < ?",
                    (cutoff_iso,),
                )
            if "observations" in tables:
                deleted += _delete(
                    connection, "DELETE FROM observations WHERE observed_at < ?", (cutoff_iso,)
                )
            if "service_events" in tables:
                deleted += _delete(
                    connection,
                    "DELETE FROM service_events WHERE COALESCE(changed_at, planned_at) < ?",
                    (cutoff_iso,),
                )
            if "parsed_raw_records" in tables and "artifact_imports" in tables:
                deleted += _delete(
                    connection,
                    """
                    DELETE FROM parsed_raw_records
                    WHERE import_id IN (SELECT id FROM artifact_imports WHERE source = 'dwd')
                      AND json_extract(payload_json, '$.observed_at_utc') < ?
                    """,
                    (cutoff_dwd,),
                )

                old_imports = "SELECT id FROM artifact_imports WHERE retrieved_at < ?"
                if {"quality_failures", "quality_results", "quality_runs"} <= tables:
                    deleted += _delete(
                        connection,
                        "DELETE FROM quality_failures WHERE result_id IN "
                        "(SELECT result_id FROM quality_results WHERE run_id IN "
                        f"(SELECT run_id FROM quality_runs WHERE import_id IN ({old_imports})))",
                        (cutoff_iso,),
                    )
                    deleted += _delete(
                        connection,
                        "DELETE FROM quality_results WHERE run_id IN "
                        f"(SELECT run_id FROM quality_runs WHERE import_id IN ({old_imports}))",
                        (cutoff_iso,),
                    )
                    deleted += _delete(
                        connection,
                        f"DELETE FROM quality_runs WHERE import_id IN ({old_imports})",
                        (cutoff_iso,),
                    )
                if "schema_snapshots" in tables:
                    deleted += _delete(
                        connection,
                        f"DELETE FROM schema_snapshots WHERE import_id IN ({old_imports})",
                        (cutoff_iso,),
                    )
                for table in ("observations", "service_events", "parsed_raw_records"):
                    if table in tables:
                        deleted += _delete(
                            connection,
                            f"DELETE FROM {table} WHERE import_id IN ({old_imports})",
                            (cutoff_iso,),
                        )
                deleted += _delete(
                    connection, "DELETE FROM artifact_imports WHERE retrieved_at < ?", (cutoff_iso,)
                )
                connection.execute(
                    """
                    UPDATE artifact_imports
                    SET record_count = (
                      SELECT COUNT(*) FROM parsed_raw_records r WHERE r.import_id = artifact_imports.id
                    )
                    """
                )
            if "collection_runs" in tables:
                deleted += _delete(
                    connection, "DELETE FROM collection_runs WHERE checked_at < ?", (cutoff_iso,)
                )
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise sqlite3.IntegrityError("Retention created foreign-key violations")
        connection.execute("VACUUM")
    return deleted


def prune_raw_files(data_dir: Path, cutoff: datetime) -> int:
    """Remove complete raw artifact/metadata pairs retrieved before cutoff."""
    raw_root = data_dir / "raw"
    if not raw_root.exists():
        return 0
    deleted = 0
    for metadata_path in raw_root.rglob("*.metadata.json"):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            retrieved_at = datetime.fromisoformat(str(metadata["retrieved_at"]))
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
        if retrieved_at.astimezone(UTC) >= cutoff.astimezone(UTC):
            continue
        artifact_path = Path(str(metadata_path)[: -len(".metadata.json")])
        artifact_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)
        deleted += 1
    for directory in sorted(raw_root.rglob("*"), reverse=True):
        if directory.is_dir():
            try:
                directory.rmdir()
            except OSError:
                pass
    return deleted


def apply_retention(
    database: Path, data_dir: Path, cutoff: datetime, *, raw_cutoff: datetime | None = None
) -> RetentionResult:
    raw_boundary = raw_cutoff or cutoff
    if raw_boundary.tzinfo is None:
        raise ValueError("Raw retention cutoff must be timezone-aware")
    return RetentionResult(
        cutoff=cutoff.astimezone(UTC),
        raw_cutoff=raw_boundary.astimezone(UTC),
        database_rows_deleted=prune_database(database, cutoff),
        raw_artifacts_deleted=prune_raw_files(data_dir, raw_boundary),
    )
