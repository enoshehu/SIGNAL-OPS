import json
import sqlite3
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from signalops.retention import apply_retention


class RetentionTests(unittest.TestCase):
    def test_prunes_old_rows_and_raw_pairs_but_keeps_future_events(self) -> None:
        now = datetime(2026, 9, 14, 12, tzinfo=UTC)
        cutoff = now - timedelta(days=7)
        with TemporaryDirectory() as directory:
            data_dir = Path(directory)
            database = data_dir / "signalops.sqlite"
            raw = data_dir / "raw" / "dwd" / "2026-09-01"
            raw.mkdir(parents=True)
            artifact = raw / "old.zip"
            artifact.write_bytes(b"old")
            artifact.with_suffix(".zip.metadata.json").write_text(
                json.dumps({"retrieved_at": "2026-09-01T00:00:00+00:00"}),
                encoding="utf-8",
            )
            with sqlite3.connect(database) as connection:
                connection.executescript(
                    """
                    CREATE TABLE artifact_imports (
                      id INTEGER PRIMARY KEY, source TEXT, scope_key TEXT, stream_key TEXT,
                      artifact_sha256 TEXT, artifact_path TEXT, retrieved_at TEXT, loaded_at TEXT,
                      record_count INTEGER
                    );
                    CREATE TABLE parsed_raw_records (
                      import_id INTEGER REFERENCES artifact_imports(id), external_id TEXT,
                      payload_json TEXT, provenance_json TEXT,
                      PRIMARY KEY(import_id, external_id)
                    );
                    CREATE TABLE observations (
                      observation_id TEXT PRIMARY KEY, import_id INTEGER REFERENCES artifact_imports(id),
                      observed_at TEXT
                    );
                    CREATE TABLE service_events (
                      event_id TEXT PRIMARY KEY, import_id INTEGER REFERENCES artifact_imports(id),
                      planned_at TEXT, changed_at TEXT
                    );
                    """
                )
                connection.execute(
                    "INSERT INTO artifact_imports VALUES (1,'dwd','x','observations','a','x',?,?,2)",
                    (now.isoformat(), now.isoformat()),
                )
                connection.executemany(
                    "INSERT INTO parsed_raw_records VALUES (1,?,?, '{}')",
                    [
                        ("old", '{"observed_at_utc":"2026090100"}'),
                        ("new", '{"observed_at_utc":"2026091400"}'),
                    ],
                )
                connection.executemany(
                    "INSERT INTO observations VALUES (?,1,?)",
                    [("old", "2026-09-01T00:00:00+00:00"), ("new", now.isoformat())],
                )
                connection.execute(
                    "INSERT INTO service_events VALUES ('future',1,?,NULL)",
                    ((now + timedelta(days=1)).isoformat(),),
                )

            result = apply_retention(database, data_dir, cutoff)

            with sqlite3.connect(database) as connection:
                observations = connection.execute(
                    "SELECT observation_id FROM observations"
                ).fetchall()
                raw_records = connection.execute(
                    "SELECT external_id FROM parsed_raw_records"
                ).fetchall()
                future = connection.execute("SELECT event_id FROM service_events").fetchall()
                record_count = connection.execute(
                    "SELECT record_count FROM artifact_imports"
                ).fetchone()[0]
            self.assertEqual(observations, [("new",)])
            self.assertEqual(raw_records, [("new",)])
            self.assertEqual(future, [("future",)])
            self.assertEqual(record_count, 1)
            self.assertEqual(result.raw_artifacts_deleted, 1)
            self.assertEqual(result.raw_cutoff, cutoff)
            self.assertFalse(artifact.exists())

    def test_raw_files_can_expire_before_analytical_rows(self) -> None:
        now = datetime(2026, 9, 14, 12, tzinfo=UTC)
        data_cutoff = now - timedelta(days=180)
        raw_cutoff = now - timedelta(days=30)
        with TemporaryDirectory() as directory:
            data_dir = Path(directory)
            database = data_dir / "signalops.sqlite"
            raw = data_dir / "raw" / "dwd" / "2026-07-01"
            raw.mkdir(parents=True)
            artifact = raw / "weather.zip"
            artifact.write_bytes(b"weather")
            artifact.with_suffix(".zip.metadata.json").write_text(
                json.dumps({"retrieved_at": "2026-07-01T00:00:00+00:00"}),
                encoding="utf-8",
            )
            with sqlite3.connect(database) as connection:
                connection.execute(
                    "CREATE TABLE observations (observation_id TEXT, observed_at TEXT)"
                )
                connection.execute(
                    "INSERT INTO observations VALUES ('kept', '2026-07-01T00:00:00+00:00')"
                )

            result = apply_retention(database, data_dir, data_cutoff, raw_cutoff=raw_cutoff)

            with sqlite3.connect(database) as connection:
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0], 1
                )
            self.assertEqual(result.raw_artifacts_deleted, 1)
            self.assertFalse(artifact.exists())


if __name__ == "__main__":
    unittest.main()
