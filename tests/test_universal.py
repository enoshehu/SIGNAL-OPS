from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import closing
import json
import sqlite3
import unittest

from signalops.catalog import load_catalog
from signalops.universal import _db_time, normalize


class UniversalModelTests(unittest.TestCase):
    def test_db_local_times_are_converted_to_utc(self) -> None:
        self.assertEqual(_db_time("2601151200"), "2026-01-15T11:00:00+00:00")
        self.assertEqual(_db_time("2607151200"), "2026-07-15T10:00:00+00:00")

    def test_catalog_loads_both_datasets(self) -> None:
        catalog = load_catalog(Path("config/datasets"))
        self.assertEqual(set(catalog), {"dwd_weather", "db_timetables"})
        self.assertEqual(catalog["db_timetables"].signals[0]["threshold"], 20)

    def test_normalizes_dwd_values_with_units_and_utc_time(self) -> None:
        with TemporaryDirectory() as directory:
            database = Path(directory) / "signalops.sqlite"
            with closing(sqlite3.connect(database)) as connection:
                connection.executescript(
                    """
                    CREATE TABLE artifact_imports (id INTEGER PRIMARY KEY, source TEXT);
                    CREATE TABLE parsed_raw_records
                    (import_id INTEGER, external_id TEXT, payload_json TEXT, provenance_json TEXT);
                    INSERT INTO artifact_imports VALUES (1, 'dwd');
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
            self.assertEqual(inserted, 2)
            self.assertEqual(rows[0], ("air_temperature", 18.2, "°C", "2026-09-14T10:00:00+00:00"))
            self.assertEqual(rows[1][0:3], ("relative_humidity", 71.0, "%"))

    def test_rail_rows_are_mapped_to_their_city_station(self) -> None:
        with TemporaryDirectory() as directory:
            database = Path(directory) / "signalops.sqlite"
            with closing(sqlite3.connect(database)) as connection:
                connection.executescript(
                    """
                    CREATE TABLE artifact_imports (id INTEGER PRIMARY KEY, source TEXT);
                    CREATE TABLE parsed_raw_records
                    (import_id INTEGER, external_id TEXT, payload_json TEXT, provenance_json TEXT);
                    INSERT INTO artifact_imports VALUES (1, 'db');
                    """
                )
                connection.executemany(
                    "INSERT INTO parsed_raw_records VALUES (?, ?, ?, '{}')",
                    [
                        (1, "stop-essen", json.dumps({
                            "station_eva": "8000098",
                            "raw_xml": '<s id="stop-essen"><dp pt="2609141000" /></s>',
                        })),
                        (1, "stop-duisburg", json.dumps({
                            "station_eva": "8000086",
                            "raw_xml": '<s id="stop-duisburg"><ar pt="2609141030" /></s>',
                        })),
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
            payload = json.dumps({
                "station_eva": "8000098", "feed": "changes",
                "raw_xml": '<s id="stop-essen"><dp ct="2609141025" cs="c" /></s>',
            })
            with closing(sqlite3.connect(database)) as connection:
                connection.executescript(
                    """
                    CREATE TABLE artifact_imports (id INTEGER PRIMARY KEY, source TEXT);
                    CREATE TABLE parsed_raw_records
                    (import_id INTEGER, external_id TEXT, payload_json TEXT, provenance_json TEXT);
                    INSERT INTO artifact_imports VALUES (1, 'db');
                    """
                )
                connection.execute(
                    "INSERT INTO parsed_raw_records VALUES (1, 'stop-essen', ?, '{}')", (payload,)
                )
                connection.commit()
            definition = load_catalog(Path("config/datasets"))["db_timetables"]
            self.assertEqual(normalize(database, definition), 1)
            with closing(sqlite3.connect(database)) as connection:
                row = connection.execute(
                    "SELECT planned_at, changed_at, status FROM service_events"
                ).fetchone()
            self.assertEqual(row, (None, "2026-09-14T08:25:00+00:00", "cancelled"))
