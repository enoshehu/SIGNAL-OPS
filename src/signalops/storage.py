"""Small SQLite store for replayable parsed raw records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import Iterable

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
            if "scope_key" not in columns:
                self._migrate_scope_key()
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS artifact_imports (
                id INTEGER PRIMARY KEY,
                source TEXT NOT NULL,
                scope_key TEXT NOT NULL,
                artifact_sha256 TEXT NOT NULL,
                artifact_path TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                loaded_at TEXT NOT NULL,
                record_count INTEGER NOT NULL,
                UNIQUE (source, scope_key, artifact_sha256)
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
        existing = self.connection.execute(
            "SELECT record_count FROM artifact_imports "
            "WHERE source = ? AND scope_key = ? AND artifact_sha256 = ?",
            (artifact.source, scope_key, checksum),
        ).fetchone()
        if existing:
            return StorageResult(existing[0], 0)

        rows = list(records)
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO artifact_imports
                (source, scope_key, artifact_sha256, artifact_path, retrieved_at, loaded_at,
                 record_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.source,
                    scope_key,
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
        for key in ("station_id", "station_eva"):
            value = artifact.provenance.get(key)
            if value:
                return str(value)
        raise ValueError("Raw artifact is missing station identity in its provenance")

    def _migrate_scope_key(self) -> None:
        self.connection.commit()
        self.connection.execute("PRAGMA foreign_keys = OFF")
        with self.connection:
            self.connection.execute(
                "ALTER TABLE parsed_raw_records RENAME TO parsed_raw_records_legacy"
            )
            self.connection.execute("ALTER TABLE artifact_imports RENAME TO artifact_imports_legacy")
            self.connection.executescript(
                """
                CREATE TABLE artifact_imports (
                    id INTEGER PRIMARY KEY,
                    source TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    artifact_sha256 TEXT NOT NULL,
                    artifact_path TEXT NOT NULL,
                    retrieved_at TEXT NOT NULL,
                    loaded_at TEXT NOT NULL,
                    record_count INTEGER NOT NULL,
                    UNIQUE (source, scope_key, artifact_sha256)
                );
                CREATE TABLE parsed_raw_records (
                    import_id INTEGER NOT NULL REFERENCES artifact_imports(id),
                    external_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    PRIMARY KEY (import_id, external_id)
                );
                INSERT INTO artifact_imports
                (id, source, scope_key, artifact_sha256, artifact_path, retrieved_at, loaded_at,
                 record_count)
                SELECT a.id, a.source,
                       COALESCE(
                         (SELECT COALESCE(
                             json_extract(r.payload_json, '$.station_id'),
                             json_extract(r.payload_json, '$.station_eva')
                          )
                          FROM parsed_raw_records_legacy r
                          WHERE r.import_id = a.id LIMIT 1),
                         'legacy'
                       ),
                       a.artifact_sha256, a.artifact_path, a.retrieved_at,
                       a.loaded_at, a.record_count
                FROM artifact_imports_legacy a;
                INSERT INTO parsed_raw_records SELECT * FROM parsed_raw_records_legacy;
                DROP TABLE parsed_raw_records_legacy;
                DROP TABLE artifact_imports_legacy;
                """
            )
        self.connection.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "SQLiteRecordStore":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
