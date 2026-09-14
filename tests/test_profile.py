import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from signalops.profile import condition_summaries, render_profile
from signalops.universal import SCHEMA


class ProfileTests(unittest.TestCase):
    def test_profile_reports_condition_sample_sizes_without_causal_claim(self) -> None:
        with TemporaryDirectory() as directory:
            database = Path(directory) / "profile.sqlite"
            with sqlite3.connect(database) as connection:
                connection.executescript(SCHEMA)
                connection.execute(
                    "INSERT INTO entities VALUES "
                    "('dwd:one','weather_station','Weather',NULL,NULL,'{\"city\":\"essen\"}')"
                )
                connection.execute(
                    "INSERT INTO entities VALUES "
                    "('db:one','rail_station','Rail',NULL,NULL,'{\"city\":\"essen\"}')"
                )
                observations = [
                    ("temp", "air_temperature", 31.0, "°C"),
                    ("rain", "precipitation", 2.0, "mm"),
                    ("wind", "wind_speed", 11.0, "m/s"),
                ]
                connection.executemany(
                    "INSERT INTO observations VALUES (?, 'weather', 'dwd:one', 1, "
                    "'2026-09-14T10:00:00+00:00', ?, ?, ?, '{}')",
                    observations,
                )
                connection.execute(
                    "INSERT INTO service_events VALUES "
                    "('plan','db_timetables','db:one',2,'stop','departure',"
                    "'2026-09-14T10:15:00+00:00',NULL,'planned','{}')"
                )
                connection.execute(
                    "INSERT INTO service_events VALUES "
                    "('change','db_changes','db:one',3,'stop','departure',NULL,"
                    "'2026-09-14T10:30:00+00:00','changed','{}')"
                )
            summaries = {item.condition: item for item in condition_summaries(database)}
            report = render_profile(database)

        self.assertEqual(summaries["rain (≥1 mm/h)"].city_hours, 1)
        self.assertEqual(summaries["strong wind (≥10 m/s)"].delayed_events, 1)
        self.assertIn("do not establish", report)

    def test_empty_profile_explicitly_waits_for_real_overlap(self) -> None:
        with TemporaryDirectory() as directory:
            database = Path(directory) / "empty.sqlite"
            with sqlite3.connect(database) as connection:
                connection.executescript(SCHEMA)
            report = render_profile(database)
        self.assertIn("waiting for a genuine overlapping source window", report)


if __name__ == "__main__":
    unittest.main()
