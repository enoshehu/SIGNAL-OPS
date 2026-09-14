import sqlite3
import unittest
from contextlib import closing
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from signalops.catalog import load_catalog
from signalops.domain import RawArtifact, RawRecord
from signalops.quality import assess
from signalops.storage import SQLiteRecordStore
from signalops.universal import normalize


class QualityTests(unittest.TestCase):
    def test_db_changes_allow_events_without_a_time(self) -> None:
        definition = load_catalog(Path("config/datasets"))["db_changes"]
        retrieved = datetime(2026, 9, 14, tzinfo=UTC)
        artifact = RawArtifact(
            "db",
            "changes",
            "changes.xml",
            retrieved,
            b"changes",
            "application/xml",
            {
                "source_url": "https://example.invalid/changes",
                "sha256": "changes-with-platform-only",
                "station_eva": "8000098",
                "feed": "changes",
            },
        )
        records = [
            RawRecord(
                "db",
                "stop-platform",
                retrieved,
                {
                    "station_eva": "8000098",
                    "feed": "changes",
                    "stop_id": "stop-platform",
                    "raw_xml": '<s id="stop-platform"><dp cp="10" /></s>',
                },
                {"source_url": "https://example.invalid/changes"},
            ),
            RawRecord(
                "db",
                "stop-time",
                retrieved,
                {
                    "station_eva": "8000098",
                    "feed": "changes",
                    "stop_id": "stop-time",
                    "raw_xml": '<s id="stop-time"><dp ct="2609141010" /></s>',
                },
                {"source_url": "https://example.invalid/changes"},
            ),
        ]
        with TemporaryDirectory() as directory:
            database = Path(directory) / "signalops.sqlite"
            with SQLiteRecordStore(database) as store:
                store.store(artifact, Path("changes.xml"), records)
            normalize(database, definition)
            result = {item.rule: item for item in assess(database, definition)}["valid_timestamp"]

        self.assertEqual(result.status, "pass")
        self.assertEqual(result.checked, 1)

    def test_db_plan_quality_does_not_select_newer_changes_import(self) -> None:
        catalog = load_catalog(Path("config/datasets"))
        plan_definition = catalog["db_timetables"]
        changes_definition = catalog["db_changes"]
        retrieved = datetime(2026, 9, 14, tzinfo=UTC)
        plan_artifact = RawArtifact(
            "db",
            "plan",
            "plan.xml",
            retrieved,
            b"plan",
            "application/xml",
            {
                "source_url": "https://example.invalid/plan",
                "sha256": "plan",
                "station_eva": "8000098",
                "feed": "plan",
            },
        )
        change_artifact = RawArtifact(
            "db",
            "changes",
            "changes.xml",
            retrieved,
            b"changes",
            "application/xml",
            {
                "source_url": "https://example.invalid/changes",
                "sha256": "changes",
                "station_eva": "8000098",
                "feed": "changes",
            },
        )
        plan_record = RawRecord(
            "db",
            "stop-1",
            retrieved,
            {
                "station_eva": "8000098",
                "feed": "plan",
                "stop_id": "stop-1",
                "raw_xml": '<s id="stop-1"><dp pt="2609141000" /></s>',
            },
            {"source_url": "https://example.invalid/plan"},
        )
        change_record = RawRecord(
            "db",
            "stop-1",
            retrieved,
            {
                "station_eva": "8000098",
                "feed": "changes",
                "stop_id": "stop-1",
                "raw_xml": '<s id="stop-1"><dp ct="2609141010" /></s>',
            },
            {"source_url": "https://example.invalid/changes"},
        )
        with TemporaryDirectory() as directory:
            database = Path(directory) / "signalops.sqlite"
            with SQLiteRecordStore(database) as store:
                store.store(plan_artifact, Path("plan.xml"), [plan_record])
                store.store(change_artifact, Path("changes.xml"), [change_record])
            normalize(database, plan_definition)
            normalize(database, changes_definition)
            assess(database, plan_definition, entity_key="db:8000098")
            with closing(sqlite3.connect(database)) as connection:
                assessed_import = connection.execute(
                    "SELECT import_id FROM quality_runs WHERE dataset_key = 'db_timetables'"
                ).fetchone()[0]
                plan_import = connection.execute(
                    "SELECT id FROM artifact_imports WHERE stream_key = 'plan'"
                ).fetchone()[0]
        self.assertEqual(assessed_import, plan_import)

    def test_quality_migrates_an_old_database_before_using_station_scope(self) -> None:
        definition = load_catalog(Path("config/datasets"))["dwd_weather"]
        definition = replace(definition, quality=({"key": "valid_timestamp"},))
        with TemporaryDirectory() as directory:
            database = Path(directory) / "signalops.sqlite"
            with closing(sqlite3.connect(database)) as connection, connection:
                connection.executescript(
                    """
                    CREATE TABLE artifact_imports (
                      id INTEGER PRIMARY KEY, source TEXT NOT NULL,
                      artifact_sha256 TEXT NOT NULL, artifact_path TEXT NOT NULL,
                      retrieved_at TEXT NOT NULL, loaded_at TEXT NOT NULL,
                      record_count INTEGER NOT NULL, UNIQUE(source, artifact_sha256)
                    );
                    CREATE TABLE parsed_raw_records (
                      import_id INTEGER NOT NULL, external_id TEXT NOT NULL,
                      payload_json TEXT NOT NULL, provenance_json TEXT NOT NULL,
                      PRIMARY KEY(import_id, external_id)
                    );
                    CREATE TABLE observations (
                      observation_id TEXT, dataset_key TEXT, entity_key TEXT, import_id INTEGER,
                      observed_at TEXT, metric TEXT, value REAL
                    );
                    INSERT INTO artifact_imports VALUES
                      (1, 'dwd', 'old', 'weather.zip', '2026-09-14T10:00:00+00:00',
                       '2026-09-14T10:01:00+00:00', 1);
                    INSERT INTO parsed_raw_records VALUES
                      (1, '01303-hour', '{"station_id":"01303"}', '{}');
                    INSERT INTO observations VALUES
                      ('weather-row', 'dwd_weather', 'dwd:01303', 1,
                       '2026-09-14T10:00:00+00:00', 'air_temperature', 18.0);
                    """
                )

            result = assess(database, definition, entity_key="dwd:01303")[0]
            with closing(sqlite3.connect(database)) as connection:
                scope = connection.execute(
                    "SELECT scope_key FROM artifact_imports WHERE id = 1"
                ).fetchone()[0]

        self.assertEqual(result.status, "pass")
        self.assertEqual(scope, "01303")

    def test_hourly_gap_is_reported(self) -> None:
        definition = load_catalog(Path("config/datasets"))["dwd_weather"]
        now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        artifact = RawArtifact(
            "dwd",
            "weather",
            "weather.zip",
            now,
            b"x",
            "application/zip",
            {"source_url": "https://example.invalid", "sha256": "gap", "station_id": "01303"},
        )
        records = [
            RawRecord(
                "dwd",
                f"01303-{hour}",
                now,
                {
                    "station_id": "01303",
                    "observed_at_utc": (now.replace(hour=10 + hour)).strftime("%Y%m%d%H"),
                    "temperature_c": 18.0,
                    "relative_humidity_pct": 70.0,
                },
                {"source_url": "https://example.invalid"},
            )
            for hour in (0, 2)
        ]
        with TemporaryDirectory() as directory:
            database = Path(directory) / "signalops.sqlite"
            with SQLiteRecordStore(database) as store:
                store.store(artifact, Path("weather.zip"), records)
            normalize(database, definition)
            result = {item.rule: item for item in assess(database, definition)}["hourly_continuity"]

        self.assertEqual(result.status, "warning")
        self.assertEqual(result.failed, 1)

    def test_unknown_configured_rule_is_rejected(self) -> None:
        definition = load_catalog(Path("config/datasets"))["dwd_weather"]
        definition = replace(definition, quality=({"key": "mystery_rule"},))
        with (
            TemporaryDirectory() as directory,
            self.assertRaisesRegex(ValueError, "Unknown quality rule"),
        ):
            assess(Path(directory) / "signalops.sqlite", definition)

    def test_city_scope_does_not_use_another_citys_latest_import(self) -> None:
        definition = load_catalog(Path("config/datasets"))["dwd_weather"]
        definition = replace(definition, quality=({"key": "valid_timestamp"},))
        with TemporaryDirectory() as directory:
            database = Path(directory) / "signalops.sqlite"
            with closing(sqlite3.connect(database)) as connection, connection:
                connection.executescript(
                    """
                    CREATE TABLE artifact_imports
                      (id INTEGER PRIMARY KEY, source TEXT, scope_key TEXT, stream_key TEXT);
                    CREATE TABLE parsed_raw_records
                      (import_id INTEGER, payload_json TEXT);
                    CREATE TABLE observations
                      (observation_id TEXT, dataset_key TEXT, entity_key TEXT, import_id INTEGER,
                       observed_at TEXT, metric TEXT, value REAL);
                    INSERT INTO artifact_imports VALUES (1, 'dwd', '01303', 'observations');
                    INSERT INTO artifact_imports VALUES (2, 'dwd', '13670', 'observations');
                    INSERT INTO observations VALUES
                      ('essen-row', 'dwd_weather', 'dwd:01303', 1,
                       '2026-09-14T10:00:00+00:00', 'air_temperature', 18.0);
                    """
                )
            result = assess(database, definition, entity_key="dwd:01303")[0]
        self.assertEqual(result.checked, 1)
        self.assertEqual(result.status, "pass")

    def test_reports_observed_missing_and_invalid_values(self) -> None:
        definition = load_catalog(Path("config/datasets"))["dwd_weather"]
        now = datetime.now(UTC)
        artifact = RawArtifact(
            "dwd",
            "weather",
            "weather.zip",
            now,
            b"x",
            "application/zip",
            {
                "source_url": "https://example.invalid",
                "sha256": "quality-one",
                "station_id": "01303",
            },
        )
        record = RawRecord(
            "dwd",
            "01303-now",
            now,
            {
                "station_id": "01303",
                "observed_at_utc": now.strftime("%Y%m%d%H"),
                "temperature_c": None,
                "relative_humidity_pct": 120.0,
                "source_quality_level": "1",
            },
            {"source_url": "https://example.invalid"},
        )
        with TemporaryDirectory() as directory:
            database = Path(directory) / "signalops.sqlite"
            with SQLiteRecordStore(database) as store:
                store.store(artifact, Path("weather.zip"), [record])
            normalize(database, definition)
            results = {result.rule: result for result in assess(database, definition)}
            with closing(sqlite3.connect(database)) as connection:
                saved_failures = connection.execute(
                    "SELECT COUNT(*) FROM quality_failures"
                ).fetchone()[0]

        self.assertEqual(results["value_present"].failed, 1)
        self.assertEqual(results["value_present"].status, "warning")
        self.assertEqual(results["humidity_range"].failed, 1)
        self.assertEqual(results["schema_drift"].status, "pass")
        self.assertEqual(saved_failures, 2)

    def test_same_schema_remains_stable(self) -> None:
        definition = load_catalog(Path("config/datasets"))["dwd_weather"]
        now = datetime.now(UTC)
        artifact = RawArtifact(
            "dwd",
            "weather",
            "weather.zip",
            now,
            b"x",
            "application/zip",
            {"source_url": "https://example.invalid", "sha256": "stable", "station_id": "01303"},
        )
        record = RawRecord(
            "dwd",
            "01303-now",
            now,
            {
                "station_id": "01303",
                "observed_at_utc": now.strftime("%Y%m%d%H"),
                "temperature_c": 18.0,
                "relative_humidity_pct": 70.0,
            },
            {"source_url": "https://example.invalid"},
        )
        with TemporaryDirectory() as directory:
            database = Path(directory) / "signalops.sqlite"
            with SQLiteRecordStore(database) as store:
                store.store(artifact, Path("weather.zip"), [record])
            normalize(database, definition)
            first = {item.rule: item for item in assess(database, definition)}
            second = {item.rule: item for item in assess(database, definition)}

        self.assertEqual(first["schema_drift"].status, "pass")
        self.assertEqual(second["schema_drift"].status, "pass")

    def test_added_source_field_is_reported_as_warning(self) -> None:
        definition = load_catalog(Path("config/datasets"))["dwd_weather"]
        now = datetime.now(UTC)
        base_payload = {
            "station_id": "01303",
            "observed_at_utc": now.strftime("%Y%m%d%H"),
            "temperature_c": 18.0,
            "relative_humidity_pct": 70.0,
        }
        with TemporaryDirectory() as directory:
            database = Path(directory) / "signalops.sqlite"
            with SQLiteRecordStore(database) as store:
                first_artifact = RawArtifact(
                    "dwd",
                    "weather",
                    "first.zip",
                    now,
                    b"one",
                    "application/zip",
                    {
                        "source_url": "https://example.invalid",
                        "sha256": "first",
                        "station_id": "01303",
                    },
                )
                first_record = RawRecord(
                    "dwd",
                    "01303-first",
                    now,
                    base_payload,
                    {"source_url": "https://example.invalid"},
                )
                store.store(first_artifact, Path("first.zip"), [first_record])
            normalize(database, definition)
            assess(database, definition)

            with SQLiteRecordStore(database) as store:
                second_artifact = RawArtifact(
                    "dwd",
                    "weather",
                    "second.zip",
                    now,
                    b"two",
                    "application/zip",
                    {
                        "source_url": "https://example.invalid",
                        "sha256": "second",
                        "station_id": "01303",
                    },
                )
                second_record = RawRecord(
                    "dwd",
                    "01303-second",
                    now,
                    {**base_payload, "new_field": "example"},
                    {"source_url": "https://example.invalid"},
                )
                store.store(second_artifact, Path("second.zip"), [second_record])
            normalize(database, definition)
            result = {item.rule: item for item in assess(database, definition)}["schema_drift"]

        self.assertEqual(result.status, "warning")
        self.assertEqual(result.details["added"], ["new_field"])
