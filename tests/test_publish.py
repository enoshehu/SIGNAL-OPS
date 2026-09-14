from datetime import UTC, datetime
import unittest

from signalops.publish import dashboard_payload


class PublishTests(unittest.TestCase):
    def test_payload_aggregates_cities_without_inventing_paired_data(self) -> None:
        payload = dashboard_payload(
            [
                {
                    "city": "essen", "paired": 0, "planned_events": 10,
                    "matched_change_events": 8, "cancelled_events": 1, "delayed_events": 4,
                    "average_delay_minutes": 5.0, "maximum_delay_minutes": 12.0,
                },
                {
                    "city": "essen", "paired": 0, "planned_events": 5,
                    "matched_change_events": 5, "cancelled_events": 0, "delayed_events": 1,
                    "average_delay_minutes": 15.0, "maximum_delay_minutes": 15.0,
                },
            ],
            generated_at=datetime(2026, 9, 14, tzinfo=UTC),
        )

        essen = next(city for city in payload["cities"] if city["key"] == "essen")
        self.assertEqual(essen["plans"], 15)
        self.assertEqual(essen["meanDelay"], 7.0)
        self.assertEqual(payload["pairedHours"], 0)
        self.assertEqual(payload["status"], "COLLECTING EVIDENCE")

    def test_payload_marks_real_overlap_available(self) -> None:
        payload = dashboard_payload(
            [{"city": "koeln", "paired": 1}],
            generated_at=datetime(2026, 9, 14, tzinfo=UTC),
        )
        self.assertEqual(payload["pairedHours"], 1)
        self.assertEqual(payload["status"], "PAIRED EVIDENCE AVAILABLE")


if __name__ == "__main__":
    unittest.main()
