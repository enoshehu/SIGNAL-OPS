import unittest
from datetime import UTC, datetime

from signalops.publish import dashboard_payload


class PublishTests(unittest.TestCase):
    def test_payload_aggregates_cities_without_inventing_paired_data(self) -> None:
        payload = dashboard_payload(
            [
                {
                    "city": "essen",
                    "hour_utc": "2026-09-13T10:00:00+00:00",
                    "paired": 0,
                    "weather_available": 1,
                    "rail_available": 0,
                    "air_temperature_c": 21.5,
                    "relative_humidity_pct": 71.0,
                    "precipitation_mm": 0.2,
                    "wind_speed_m_s": 3.4,
                    "wind_gust_m_s": 8.2,
                    "planned_events": 10,
                    "matched_change_events": 8,
                    "cancelled_events": 1,
                    "delayed_events": 4,
                    "average_delay_minutes": 5.0,
                    "maximum_delay_minutes": 12.0,
                },
                {
                    "city": "essen",
                    "hour_utc": "2026-09-14T10:00:00+00:00",
                    "paired": 0,
                    "weather_available": 0,
                    "rail_available": 1,
                    "planned_events": 5,
                    "matched_change_events": 5,
                    "cancelled_events": 0,
                    "delayed_events": 1,
                    "average_delay_minutes": 15.0,
                    "maximum_delay_minutes": 15.0,
                },
            ],
            generated_at=datetime(2026, 9, 14, tzinfo=UTC),
        )

        essen = next(city for city in payload["cities"] if city["key"] == "essen")
        self.assertEqual(essen["plans"], 15)
        self.assertEqual(essen["meanDelay"], 7.0)
        self.assertEqual(essen["temperature"], 21.5)
        self.assertEqual(essen["weatherHours"], 1)
        self.assertEqual(essen["windGust"], 8.2)
        self.assertEqual(payload["windowStart"], "2026-09-13T10:00:00+00:00")
        self.assertEqual(payload["windowEnd"], "2026-09-14T10:00:00+00:00")
        self.assertEqual(payload["pairedHours"], 0)
        self.assertEqual(payload["status"], "WAITING FOR TIME OVERLAP")

    def test_payload_marks_real_overlap_available(self) -> None:
        payload = dashboard_payload(
            [{"city": "koeln", "paired": 1, "weather_available": 1, "rail_available": 1}],
            generated_at=datetime(2026, 9, 14, tzinfo=UTC),
        )
        self.assertEqual(payload["pairedHours"], 1)
        self.assertEqual(payload["status"], "ANALYSIS READY")


if __name__ == "__main__":
    unittest.main()
