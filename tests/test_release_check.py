import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.release_check import check_repository, dashboard_differences
from signalops.publish import dashboard_payload


class ReleaseCheckTests(unittest.TestCase):
    def test_repository_passes_static_release_checks(self) -> None:
        self.assertEqual(check_repository(Path.cwd()), [])

    def test_dashboard_numbers_must_match_rebuilt_rows(self) -> None:
        rows = [
            {
                "city": "duisburg",
                "hour_utc": "2026-09-14T10:00:00+00:00",
                "weather_available": 1,
                "rail_available": 1,
                "paired": 1,
                "planned_events": 2,
                "matched_change_events": 1,
                "cancelled_events": 0,
                "delayed_events": 1,
                "average_delay_minutes": 4.0,
                "maximum_delay_minutes": 4.0,
                "air_temperature_c": 18.2,
                "relative_humidity_pct": 70.0,
                "precipitation_mm": 0.0,
                "wind_speed_m_s": 2.1,
            }
        ]
        payload = dashboard_payload(rows)
        self.assertEqual(dashboard_differences(rows, payload), [])

        payload["pairedHours"] = 2
        self.assertEqual(
            dashboard_differences(rows, payload),
            ["dashboard summary does not match the rebuilt evidence database"],
        )

    def test_requested_database_must_exist(self) -> None:
        with TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.sqlite"
            self.assertIn(
                f"database does not exist: {missing}", check_repository(Path.cwd(), missing)
            )


if __name__ == "__main__":
    unittest.main()
