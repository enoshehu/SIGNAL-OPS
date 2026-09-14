import sqlite3
import unittest
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from signalops.domain import RawArtifact, RawRecord
from signalops.storage import SQLiteRecordStore


def sample_artifact(checksum: str = "abc123") -> RawArtifact:
    return RawArtifact(
        "dwd",
        "weather",
        "weather.zip",
        datetime(2026, 9, 14, tzinfo=UTC),
        b"content",
        "application/zip",
        {
            "source_url": "https://example.invalid/weather",
            "sha256": checksum,
            "station_id": "01303",
        },
    )


def sample_record(artifact: RawArtifact) -> RawRecord:
    return RawRecord(
        "dwd",
        "00433-2026091410",
        artifact.retrieved_at,
        {"temperature_c": 18.2, "relative_humidity_pct": None},
        {"source_url": artifact.provenance["source_url"]},
    )


class SQLiteRecordStoreTests(unittest.TestCase):
    def test_same_bytes_are_separate_for_plan_and_change_streams(self) -> None:
        plan = RawArtifact(
            "db",
            "plan",
            "plan.xml",
            datetime(2026, 9, 14, tzinfo=UTC),
            b"same",
            "application/xml",
            {
                "source_url": "https://example.invalid",
                "sha256": "same",
                "station_eva": "8000098",
                "feed": "plan",
            },
        )
        changes = RawArtifact(
            "db",
            "changes",
            "changes.xml",
            plan.retrieved_at,
            b"same",
            "application/xml",
            {**plan.provenance, "feed": "changes"},
        )
        record = RawRecord(
            "db",
            "stop",
            plan.retrieved_at,
            {"station_eva": "8000098"},
            {"source_url": "https://example.invalid"},
        )
        with TemporaryDirectory() as directory:
            database = Path(directory) / "signalops.sqlite"
            with SQLiteRecordStore(database) as store:
                store.store(plan, Path("plan.xml"), [record])
                store.store(changes, Path("changes.xml"), [record])
            with closing(sqlite3.connect(database)) as connection:
                streams = connection.execute(
                    "SELECT stream_key FROM artifact_imports ORDER BY stream_key"
                ).fetchall()
        self.assertEqual(streams, [("changes",), ("plan",)])

    def test_replay_is_idempotent_and_records_artifact(self) -> None:
        artifact = sample_artifact()
        records = [sample_record(artifact)]
        with TemporaryDirectory() as directory:
            database = Path(directory) / "signalops.sqlite"
            with SQLiteRecordStore(database) as store:
                first = store.store(artifact, Path("weather.zip"), records)
                second = store.store(artifact, Path("weather.zip"), records)

            self.assertEqual(first.records_inserted, 1)
            self.assertEqual(second.records_inserted, 0)
            with closing(sqlite3.connect(database)) as connection, connection:
                import_count = connection.execute(
                    "SELECT COUNT(*) FROM artifact_imports"
                ).fetchone()[0]
                record_count = connection.execute(
                    "SELECT COUNT(*) FROM parsed_raw_records"
                ).fetchone()[0]
            self.assertEqual(import_count, 1)
            self.assertEqual(record_count, 1)

    def test_changed_artifact_keeps_a_second_record_version(self) -> None:
        first = sample_artifact("first")
        second = sample_artifact("second")
        with TemporaryDirectory() as directory:
            database = Path(directory) / "signalops.sqlite"
            with SQLiteRecordStore(database) as store:
                store.store(first, Path("first.zip"), [sample_record(first)])
                store.store(second, Path("second.zip"), [sample_record(second)])
            with closing(sqlite3.connect(database)) as connection, connection:
                count = connection.execute("SELECT COUNT(*) FROM parsed_raw_records").fetchone()[0]
            self.assertEqual(count, 2)

    def test_same_bytes_are_separate_for_different_stations(self) -> None:
        first = sample_artifact("same")
        second = RawArtifact(
            first.source,
            first.external_id,
            first.filename,
            first.retrieved_at,
            first.content,
            first.content_type,
            {**first.provenance, "station_id": "13670"},
        )
        with TemporaryDirectory() as directory:
            database = Path(directory) / "signalops.sqlite"
            with SQLiteRecordStore(database) as store:
                store.store(first, Path("essen.zip"), [sample_record(first)])
                store.store(second, Path("duisburg.zip"), [sample_record(second)])
            with closing(sqlite3.connect(database)) as connection, connection:
                scopes = connection.execute(
                    "SELECT scope_key FROM artifact_imports ORDER BY scope_key"
                ).fetchall()
            self.assertEqual(scopes, [("01303",), ("13670",)])

    def test_duplicate_id_rolls_back_the_import(self) -> None:
        artifact = sample_artifact()
        record = sample_record(artifact)
        with TemporaryDirectory() as directory:
            database = Path(directory) / "signalops.sqlite"
            with SQLiteRecordStore(database) as store, self.assertRaises(sqlite3.IntegrityError):
                store.store(artifact, Path("weather.zip"), [record, record])
            with closing(sqlite3.connect(database)) as connection, connection:
                count = connection.execute("SELECT COUNT(*) FROM artifact_imports").fetchone()[0]
            self.assertEqual(count, 0)

    def test_old_schema_recovers_station_scope_from_payload(self) -> None:
        with TemporaryDirectory() as directory:
            database = Path(directory) / "signalops.sqlite"
            with closing(sqlite3.connect(database)) as connection, connection:
                connection.executescript(
                    """
                    CREATE TABLE artifact_imports (
                      id INTEGER PRIMARY KEY, source TEXT, artifact_sha256 TEXT,
                      artifact_path TEXT, retrieved_at TEXT, loaded_at TEXT,
                      record_count INTEGER, UNIQUE(source, artifact_sha256)
                    );
                    CREATE TABLE parsed_raw_records (
                      import_id INTEGER REFERENCES artifact_imports(id),
                      external_id TEXT, payload_json TEXT,
                      provenance_json TEXT, PRIMARY KEY(import_id, external_id)
                    );
                    INSERT INTO artifact_imports VALUES
                      (1, 'dwd', 'old', 'weather.zip', '2026-09-14', '2026-09-14', 1);
                    INSERT INTO parsed_raw_records VALUES
                      (1, 'row', '{"station_id":"01303"}', '{}');
                    """
                )
            with SQLiteRecordStore(database):
                pass
            with closing(sqlite3.connect(database)) as connection, connection:
                scope = connection.execute(
                    "SELECT scope_key FROM artifact_imports WHERE id = 1"
                ).fetchone()[0]
                stream = connection.execute(
                    "SELECT stream_key FROM artifact_imports WHERE id = 1"
                ).fetchone()[0]
                parent = connection.execute(
                    "PRAGMA foreign_key_list(parsed_raw_records)"
                ).fetchone()[2]
                violations = connection.execute("PRAGMA foreign_key_check").fetchall()
            self.assertEqual(scope, "01303")
            self.assertEqual(stream, "observations")
            self.assertEqual(parent, "artifact_imports")
            self.assertEqual(violations, [])
