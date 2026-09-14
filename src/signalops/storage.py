"""Small SQLite store for replayable parsed raw records."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Self

from signalops.domain import RawArtifact, RawRecord


@dataclass(frozen=True, slots=True)
class StorageResult:
    records_seen: int
    records_inserted: int


class SQLiteRecordStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute("PRAGMA foreign_keys = ON")
        existing = self.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'artifact_imports'"
        ).fetchone()
        if existing:
            columns = {
                row[1] for row in self.connection.execute("PRAGMA table_info(artifact_imports)")
            }
            if "scope_key" not in columns or "stream_key" not in columns:
                self._migrate_import_identity(columns)
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS artifact_imports (
                id INTEGER PRIMARY KEY,
                source TEXT NOT NULL,
                scope_key TEXT NOT NULL,
                stream_key TEXT NOT NULL,
                artifact_sha256 TEXT NOT NULL,
                artifact_path TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                loaded_at TEXT NOT NULL,
                record_count INTEGER NOT NULL,
                UNIQUE (source, scope_key, stream_key, artifact_sha256)
            );

            CREATE TABLE IF NOT EXISTS parsed_raw_records (
                import_id INTEGER NOT NULL REFERENCES artifact_imports(id),
                external_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                provenance_json TEXT NOT NULL,
                PRIMARY KEY (import_id, external_id)
            );
            """
        )

    def store(
        self, artifact: RawArtifact, artifact_path: Path, records: Iterable[RawRecord]
    ) -> StorageResult:
        checksum = artifact.provenance["sha256"]
        scope_key = self._scope_key(artifact)
        stream_key = self._stream_key(artifact)
        existing = self.connection.execute(
            "SELECT id, record_count FROM artifact_imports "
            "WHERE source = ? AND scope_key = ? AND stream_key = ? AND artifact_sha256 = ?",
            (artifact.source, scope_key, stream_key, checksum),
        ).fetchone()
        if existing:
            import_id, stored_count = existing
            rows = list(records)
            if stored_count == len(rows):
                return StorageResult(stored_count, 0)
            with self.connection:
                before = self.connection.total_changes
                self.connection.executemany(
                    """
                    INSERT OR IGNORE INTO parsed_raw_records
                    (import_id, external_id, payload_json, provenance_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    [
                        (
                            import_id,
                            record.external_id,
                            json.dumps(record.payload, sort_keys=True),
                            json.dumps(record.provenance, sort_keys=True),
                        )
                        for record in rows
                    ],
                )
                inserted = self.connection.total_changes - before
                self.connection.execute(
                    "UPDATE artifact_imports SET record_count = ? WHERE id = ?",
                    (len(rows), import_id),
                )
            return StorageResult(len(rows), inserted)

        rows = list(records)
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO artifact_imports
                (source, scope_key, stream_key, artifact_sha256, artifact_path, retrieved_at,
                 loaded_at, record_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.source,
                    scope_key,
                    stream_key,
                    checksum,
                    str(artifact_path.resolve()),
                    artifact.retrieved_at.isoformat(),
                    datetime.now(UTC).isoformat(),
                    len(rows),
                ),
            )
            import_id = cursor.lastrowid
            self.connection.executemany(
                """
                INSERT INTO parsed_raw_records
                (import_id, external_id, payload_json, provenance_json)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        import_id,
                        record.external_id,
                        json.dumps(record.payload, sort_keys=True),
                        json.dumps(record.provenance, sort_keys=True),
                    )
                    for record in rows
                ],
            )
        return StorageResult(len(rows), len(rows))

    @staticmethod
    def _scope_key(artifact: RawArtifact) -> str:
        for key in ("scope_key", "entity_key", "station_id", "station_eva"):
            value = artifact.provenance.get(key)
            if value:
                return str(value)
        raise ValueError("Raw artifact is missing station identity in its provenance")

    @staticmethod
    def _stream_key(artifact: RawArtifact) -> str:
        stream = artifact.provenance.get("stream_key") or artifact.provenance.get("feed")
        if stream:
            return str(stream)
        if artifact.source == "dwd":
            return "observations"
        if artifact.source == "db":
            return "plan"
        return "default"

    def _migrate_import_identity(self, columns: set[str]) -> None:
        scope_expression = (
            "a.scope_key"
            if "scope_key" in columns
            else """
            COALESCE(
              (SELECT COALESCE(
                  json_extract(r.payload_json, '$.scope_key'),
                  json_extract(r.payload_json, '$.entity_key'),
                  json_extract(r.payload_json, '$.station_id'),
                  json_extract(r.payload_json, '$.station_eva')
               )
               FROM parsed_raw_records r
               WHERE r.import_id = a.id LIMIT 1),
              'legacy'
            )
        """
        )
        stream_expression = (
            "a.stream_key"
            if "stream_key" in columns
            else """
            COALESCE(
              (SELECT COALESCE(
                  json_extract(r.payload_json, '$.stream_key'),
                  json_extract(r.payload_json, '$.feed')
               )
               FROM parsed_raw_records r
               WHERE r.import_id = a.id LIMIT 1),
              CASE WHEN a.source = 'dwd' THEN 'observations' ELSE 'plan' END
            )
        """
        )
        self.connection.commit()
        self.connection.execute("PRAGMA foreign_keys = OFF")
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            self.connection.execute(
                """
                CREATE TABLE artifact_imports_new (
                    id INTEGER PRIMARY KEY,
                    source TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    stream_key TEXT NOT NULL,
                    artifact_sha256 TEXT NOT NULL,
                    artifact_path TEXT NOT NULL,
                    retrieved_at TEXT NOT NULL,
                    loaded_at TEXT NOT NULL,
                    record_count INTEGER NOT NULL,
                    UNIQUE (source, scope_key, stream_key, artifact_sha256)
                )
                """
            )
            self.connection.execute(
                f"""
                INSERT INTO artifact_imports_new
                (id, source, scope_key, stream_key, artifact_sha256, artifact_path, retrieved_at,
                 loaded_at, record_count)
                SELECT a.id, a.source, {scope_expression}, {stream_expression},
                       a.artifact_sha256, a.artifact_path, a.retrieved_at,
                       a.loaded_at, a.record_count
                FROM artifact_imports a
                """
            )
            self.connection.execute("DROP TABLE artifact_imports")
            self.connection.execute("ALTER TABLE artifact_imports_new RENAME TO artifact_imports")
            violations = self.connection.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise sqlite3.IntegrityError("Storage migration failed foreign-key validation")
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        finally:
            self.connection.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
