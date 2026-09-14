import json
import sqlite3
import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from signalops.history import weather_coverage


class HistoryTests(unittest.TestCase):
    def test_weather_coverage_reports_city_metric_grain(self) -> None:
        with TemporaryDirectory() as directory:
            database = Path(directory) / "signalops.sqlite"
            with sqlite3.connect(database) as connection:
                connection.executescript(
                    """
                    CREATE TABLE entities (
                      entity_key TEXT PRIMARY KEY, attributes_json TEXT NOT NULL
                    );
                    CREATE TABLE observations (
                      dataset_key TEXT, entity_key TEXT, observed_at TEXT, metric TEXT
                    );
                    """
                )
                connection.execute(
                    "INSERT INTO entities VALUES (?, ?)",
                    ("dwd:01303", json.dumps({"city": "essen"})),
                )
                connection.executemany(
                    "INSERT INTO observations VALUES (?, ?, ?, ?)",
                    [
                        (
                            "dwd_weather",
                            "dwd:01303",
                            "2026-03-18T00:00:00+00:00",
                            "air_temperature",
                        ),
                        (
                            "dwd_weather",
                            "dwd:01303",
                            "2026-09-13T23:00:00+00:00",
                            "air_temperature",
                        ),
                    ],
                )

            rows = weather_coverage(database, datetime(2026, 3, 18, tzinfo=UTC))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["city"], "essen")
        self.assertEqual(rows[0]["metric"], "air_temperature")
        self.assertEqual(rows[0]["hours"], 2)


if __name__ == "__main__":
    unittest.main()
