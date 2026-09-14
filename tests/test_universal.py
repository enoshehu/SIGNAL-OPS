import json
import sqlite3
import unittest
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from signalops.catalog import DatasetDefinition, load_catalog
from signalops.domain import RawArtifact, RawRecord
from signalops.storage import SQLiteRecordStore
from signalops.universal import _db_time, normalize, register_normalizer


class UniversalModelTests(unittest.TestCase):
    def test_custom_adapter_uses_registered_normalizer(self) -> None:
        observed: list[int] = []

        def custom_normalizer(connection, definition, rows):
            observed.append(len(rows))
            return len(rows)

        register_normalizer("custom", custom_normalizer)
        definition = DatasetDefinition(
            key="custom_metrics",
            name="Custom metrics",
            adapter="custom",
            stream="observations",
            entity_type="custom_entity",
            refresh_minutes=60,
            source={
                "key": "custom",
                "name": "Custom source",
                "provider": "Fixture",
                "license": "CC0",
                "url": "https://example.invalid/custom",
            },
            entities=({"key": "custom:one", "name": "One"},),
            quality=(),
            signals=(),
        )
        retrieved = datetime(2026, 9, 14, tzinfo=UTC)
        artifact = RawArtifact(
            "custom",
            "one",
            "custom.json",
            retrieved,
            b"{}",
            "application/json",
            {
                "source_url": "https://example.invalid/custom",
                "sha256": "custom",
                "scope_key": "one",
                "stream_key": "observations",
            },
        )
        record = RawRecord(
            "custom",
            "one",
            retrieved,
            {"entity_key": "custom:one"},
            {"source_url": "https://example.invalid/custom"},
        )
        with TemporaryDirectory() as directory:
            database = Path(directory) / "signalops.sqlite"
            with SQLiteRecordStore(database) as store:
                store.store(artifact, Path("custom.json"), [record])
            inserted = normalize(database, definition)

        self.assertEqual(inserted, 1)
        self.assertEqual(observed, [1])

    def test_db_local_times_are_converted_to_utc(self) -> None:
        self.assertEqual(_db_time("2601151200"), "2026-01-15T11:00:00+00:00")
        self.assertEqual(_db_time("2607151200"), "2026-07-15T10:00:00+00:00")

    def test_catalog_loads_configured_datasets(self) -> None:
        catalog = load_catalog(Path("config/datasets"))
        self.assertEqual(
            set(catalog),
            {
                "db_changes",
                "db_timetables",
                "dwd_weather",
                "dwd_precipitation",
                "dwd_wind",
            },
        )
        self.assertEqual(catalog["db_timetables"].signals[0]["threshold"], 20)
        self.assertEqual(catalog["db_changes"].stream, "changes")

    def test_normalizes_dwd_values_with_units_and_utc_time(self) -> None:
        with TemporaryDirectory() as directory:
            database = Path(directory) / "signalops.sqlite"
            with closing(sqlite3.connect(database)) as connection:
                connection.executescript(
                    """
                    CREATE TABLE artifact_imports (
                      id INTEGER PRIMARY KEY, source TEXT, scope_key TEXT, stream_key TEXT,
                      artifact_sha256 TEXT, artifact_path TEXT, retrieved_at TEXT, loaded_at TEXT,
                      record_count INTEGER, UNIQUE(source, scope_key, stream_key, artifact_sha256)
                    );
                    CREATE TABLE parsed_raw_records
                    (import_id INTEGER, external_id TEXT, payload_json TEXT, provenance_json TEXT,
                     PRIMARY KEY(import_id, external_id));
                    INSERT INTO artifact_imports VALUES
                    (1, 'dwd', '01303', 'observations', 'one', '', '', '', 1);
                    INSERT INTO parsed_raw_records VALUES
                    (1, '01303-2026091410',
                     '{"station_id":"01303","observed_at_utc":"2026091410","temperature_c":18.2,"relative_humidity_pct":71.0}',
                     '{}');
                    """
                )
            definition = load_catalog(Path("config/datasets"))["dwd_weather"]
            inserted = normalize(database, definition)
            with closing(sqlite3.connect(database)) as connection:
                rows = connection.execute(
                    "SELECT metric, value, unit, observed_at FROM observations ORDER BY metric"
                ).fetchall()
                connection.execute("PRAGMA foreign_keys = ON")
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            "orphan",
                            "dwd_weather",
                            "missing",
                            1,
                            "2026-09-14T10:00:00+00:00",
                            "air_temperature",
                            1.0,
                            "°C",
                            "{}",
                        ),
                    )
            self.assertEqual(inserted, 2)
            self.assertEqual(rows[0], ("air_temperature", 18.2, "°C", "2026-09-14T10:00:00+00:00"))
            self.assertEqual(rows[1][0:3], ("relative_humidity", 71.0, "%"))

    def test_rail_rows_are_mapped_to_their_city_station(self) -> None:
        with TemporaryDirectory() as directory:
            database = Path(directory) / "signalops.sqlite"
            with closing(sqlite3.connect(database)) as connection:
                connection.executescript(
                    """
                    CREATE TABLE artifact_imports (
                      id INTEGER PRIMARY KEY, source TEXT, scope_key TEXT, stream_key TEXT,
                      artifact_sha256 TEXT, artifact_path TEXT, retrieved_at TEXT, loaded_at TEXT,
                      record_count INTEGER, UNIQUE(source, scope_key, stream_key, artifact_sha256)
                    );
                    CREATE TABLE parsed_raw_records
                    (import_id INTEGER, external_id TEXT, payload_json TEXT, provenance_json TEXT,
                     PRIMARY KEY(import_id, external_id));
                    INSERT INTO artifact_imports VALUES
                    (1, 'db', 'test', 'plan', 'one', '', '', '', 2);
                    """
                )
                connection.executemany(
                    "INSERT INTO parsed_raw_records VALUES (?, ?, ?, '{}')",
                    [
                        (
                            1,
                            "stop-essen",
                            json.dumps(
                                {
                                    "station_eva": "8000098",
                                    "raw_xml": '<s id="stop-essen"><dp pt="2609141000" /></s>',
                                }
                            ),
                        ),
                        (
                            1,
                            "stop-duisburg",
                            json.dumps(
                                {
                                    "station_eva": "8000086",
                                    "raw_xml": '<s id="stop-duisburg"><ar pt="2609141030" /></s>',
                                }
                            ),
                        ),
                    ],
                )
                connection.commit()
            definition = load_catalog(Path("config/datasets"))["db_timetables"]
            self.assertEqual(normalize(database, definition), 2)
            with closing(sqlite3.connect(database)) as connection:
                rows = connection.execute(
                    "SELECT stop_id, entity_key FROM service_events ORDER BY stop_id"
                ).fetchall()
            self.assertEqual(
                rows,
                [("stop-duisburg", "db:8000086"), ("stop-essen", "db:8000098")],
            )

    def test_rail_change_keeps_changed_time_and_cancellation(self) -> None:
        with TemporaryDirectory() as directory:
            database = Path(directory) / "signalops.sqlite"
            payload = json.dumps(
                {
                    "station_eva": "8000098",
                    "feed": "changes",
                    "raw_xml": '<s id="stop-essen"><dp ct="2609141025" cs="c" /></s>',
                }
            )
            with closing(sqlite3.connect(database)) as connection:
                connection.executescript(
                    """
                    CREATE TABLE artifact_imports (
                      id INTEGER PRIMARY KEY, source TEXT, scope_key TEXT, stream_key TEXT,
                      artifact_sha256 TEXT, artifact_path TEXT, retrieved_at TEXT, loaded_at TEXT,
                      record_count INTEGER, UNIQUE(source, scope_key, stream_key, artifact_sha256)
                    );
                    CREATE TABLE parsed_raw_records
                    (import_id INTEGER, external_id TEXT, payload_json TEXT, provenance_json TEXT,
                     PRIMARY KEY(import_id, external_id));
                    INSERT INTO artifact_imports VALUES
                    (1, 'db', '8000098', 'changes', 'one', '', '', '', 1);
                    """
                )
                connection.execute(
                    "INSERT INTO parsed_raw_records VALUES (1, 'stop-essen', ?, '{}')", (payload,)
                )
                connection.commit()
            definition = load_catalog(Path("config/datasets"))["db_changes"]
            self.assertEqual(normalize(database, definition), 1)
            with closing(sqlite3.connect(database)) as connection:
                row = connection.execute(
                    "SELECT planned_at, changed_at, status FROM service_events"
                ).fetchone()
            self.assertEqual(row, (None, "2026-09-14T08:25:00+00:00", "cancelled"))
