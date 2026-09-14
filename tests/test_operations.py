from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from signalops.operations import (
    analysis_signals,
    persist_incidents,
    quality_signals,
    resolve_incident,
)
from signalops.quality import QualityResult


class OperationsTests(unittest.TestCase):
    def test_detects_only_supported_rail_signals(self) -> None:
        now = datetime(2026, 9, 14, 20, tzinfo=UTC)
        rows = [
            {
                "city": "essen", "hour_utc": "2026-09-14T19:00:00+00:00",
                "maximum_delay_minutes": 27, "cancelled_events": 2,
            },
            {
                "city": "duisburg", "hour_utc": "2026-09-14T19:00:00+00:00",
                "maximum_delay_minutes": 10, "cancelled_events": 0,
            },
        ]

        signals = analysis_signals(rows, detected_at=now)

        self.assertEqual(
            {signal.signal_type for signal in signals},
            {"DELAY_OVER_20_MINUTES", "CANCELLATION_DETECTED"},
        )

    def test_quality_rules_create_stale_and_schema_signals(self) -> None:
        now = datetime(2026, 9, 14, 20, tzinfo=UTC)
        results = [
            QualityResult("freshness", "warning", 10, 1, {"reason": "Source is stale"}),
            QualityResult("schema_drift", "failure", 5, 1, {"reason": "Field removed"}),
            QualityResult("value_present", "warning", 10, 2, {"reason": "Missing values"}),
        ]

        signals = quality_signals(
            results, dataset="dwd_weather", entity_key="dwd:01303", detected_at=now
        )

        self.assertEqual(
            {signal.signal_type for signal in signals}, {"SOURCE_DATA_STALE", "SCHEMA_CHANGED"}
        )

    def test_incident_open_is_idempotent_and_can_be_resolved(self) -> None:
        now = datetime(2026, 9, 14, 20, tzinfo=UTC)
        signal = analysis_signals(
            [{
                "city": "koeln", "hour_utc": "2026-09-14T19:00:00+00:00",
                "maximum_delay_minutes": 90, "cancelled_events": 0,
            }],
            detected_at=now,
        )[0]
        with TemporaryDirectory() as directory:
            database = Path(directory) / "operations.sqlite"
            self.assertEqual(persist_incidents(database, [signal]), 1)
            self.assertEqual(persist_incidents(database, [signal]), 0)
            resolve_incident(database, 1, "Adapter verified against the source contract")
            self.assertEqual(persist_incidents(database, [signal]), 1)
            with closing(sqlite3.connect(database)) as connection:
                rows = connection.execute(
                    "SELECT status, resolution FROM incidents ORDER BY incident_id"
                ).fetchall()
        self.assertEqual(rows[0], ("resolved", "Adapter verified against the source contract"))
        self.assertEqual(rows[1], ("open", None))


if __name__ == "__main__":
    unittest.main()
