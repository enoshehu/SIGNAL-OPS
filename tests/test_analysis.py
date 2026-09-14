import csv
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from signalops.analysis import COLUMNS, export_hourly_csv, hourly_summary
from signalops.universal import SCHEMA


class AnalysisTests(unittest.TestCase):
    def test_pairs_same_city_hour_and_keeps_unmatched_hours(self) -> None:
        with TemporaryDirectory() as directory:
            database = Path(directory) / "signalops.sqlite"
            with closing(sqlite3.connect(database)) as connection, connection:
                connection.executescript(SCHEMA)
                connection.executemany(
                    "INSERT INTO entities VALUES (?, ?, ?, NULL, NULL, ?)",
                    [
                        ("dwd:01303", "weather_station", "Essen-Bredeney",
                         json.dumps({"city": "essen"})),
                        ("db:8000098", "rail_station", "Essen Hbf",
                         json.dumps({"city": "essen"})),
                        ("dwd:13670", "weather_station", "Duisburg-Baerl",
                         json.dumps({"city": "duisburg"})),
                    ],
                )
                connection.executemany(
                    "INSERT INTO observations VALUES (?, 'dwd_weather', ?, ?, ?, ?, ?, ?, '{}')",
                    [
                        ("w1", "dwd:01303", 1, "2026-09-14T17:00:00+00:00",
                         "air_temperature", 18.0, "°C"),
                        ("w2", "dwd:01303", 1, "2026-09-14T17:00:00+00:00",
                         "relative_humidity", 70.0, "%"),
                        ("w3", "dwd:13670", 1, "2026-09-14T17:00:00+00:00",
                         "air_temperature", 17.0, "°C"),
                        ("w4", "dwd:01303", 3, "2026-09-14T17:00:00+00:00",
                         "air_temperature", 19.0, "°C"),
                        ("w5", "dwd:01303", 3, "2026-09-14T17:00:00+00:00",
                         "relative_humidity", 69.0, "%"),
                    ],
                )
                connection.execute(
                    "INSERT INTO service_events VALUES "
                    "('r1', 'db_timetables', 'db:8000098', 2, 'stop-1', 'departure', "
                    "'2026-09-14T17:20:00+00:00', NULL, 'planned', '{}')"
                )
            rows = hourly_summary(database)

        self.assertEqual(len(rows), 2)
        essen = next(row for row in rows if row["city"] == "essen")
        duisburg = next(row for row in rows if row["city"] == "duisburg")
        self.assertEqual(essen["paired"], 1)
        self.assertEqual(essen["planned_departures"], 1)
        self.assertEqual(essen["air_temperature_c"], 19.0)
        self.assertEqual(duisburg["rail_available"], 0)
        self.assertIsNone(duisburg["planned_events"])

    def test_export_has_stable_columns(self) -> None:
        with TemporaryDirectory() as directory:
            database = Path(directory) / "signalops.sqlite"
            output = Path(directory) / "out" / "summary.csv"
            with closing(sqlite3.connect(database)) as connection, connection:
                connection.executescript(SCHEMA)
            self.assertEqual(export_hourly_csv(database, output), 0)
            with output.open(encoding="utf-8", newline="") as handle:
                self.assertEqual(tuple(next(csv.reader(handle))), COLUMNS)

    def test_keeps_separate_plan_hours_and_merges_only_matching_changes(self) -> None:
        with TemporaryDirectory() as directory:
            database = Path(directory) / "signalops.sqlite"
            with closing(sqlite3.connect(database)) as connection, connection:
                connection.executescript(SCHEMA)
                connection.execute(
                    "INSERT INTO entities VALUES (?, ?, ?, NULL, NULL, ?)",
                    ("db:8000098", "rail_station", "Essen Hbf", json.dumps({"city": "essen"})),
                )
                connection.executemany(
                    "INSERT INTO service_events VALUES (?, 'db_timetables', 'db:8000098', ?, ?, "
                    "'departure', ?, ?, ?, '{}')",
                    [
                        ("plan-1", 1, "stop-1", "2026-09-14T17:20:00+00:00", None, "planned"),
                        ("plan-2", 2, "stop-2", "2026-09-14T18:20:00+00:00", None, "planned"),
                        ("change-1", 3, "stop-1", None, "2026-09-14T17:30:00+00:00", "changed"),
                        ("change-2", 3, "stop-2", None, "2026-09-14T18:20:00+00:00", "cancelled"),
                        ("unmatched", 3, "stop-3", None, "2026-09-14T19:00:00+00:00", "changed"),
                    ],
                )

            rows = hourly_summary(database)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["planned_events"], 1)
        self.assertEqual(rows[0]["matched_change_events"], 1)
        self.assertEqual(rows[0]["delayed_events"], 1)
        self.assertEqual(rows[0]["average_delay_minutes"], 10.0)
        self.assertEqual(rows[1]["cancelled_events"], 1)
