import json
import sqlite3
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from signalops.publish import dashboard_payload, database_publish_context


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
        self.assertEqual(payload["schemaVersion"], 2)
        self.assertEqual(payload["windows"]["weather"]["start"], "2026-09-13T10:00:00+00:00")
        self.assertEqual(payload["windows"]["rail"]["end"], "2026-09-14T10:00:00+00:00")
        self.assertIsNone(payload["windows"]["overlap"]["start"])
        self.assertEqual(payload["pairedHours"], 0)
        self.assertEqual(payload["status"], "WAITING FOR TIME OVERLAP")

    def test_payload_marks_real_overlap_available(self) -> None:
        payload = dashboard_payload(
            [{
                "city": "koeln", "hour_utc": "2026-09-14T00:00:00+00:00",
                "paired": 1, "weather_available": 1, "rail_available": 1,
            }],
            generated_at=datetime(2026, 9, 14, tzinfo=UTC),
        )
        self.assertEqual(payload["pairedHours"], 1)
        self.assertEqual(payload["status"], "OVERLAP DETECTED")
        self.assertFalse(payload["readiness"]["ready"])
        self.assertEqual(payload["liveGoal"]["currentPairedHours"], 1)
        self.assertEqual(len(payload["pairedTimeline"]), 1)
        self.assertTrue(payload["collection"]["atomicPublication"])

    def test_delay_rate_uses_matched_events_and_total_minutes_round_once(self) -> None:
        payload = dashboard_payload(
            [{
                "city": "duisburg", "hour_utc": "2026-09-14T10:00:00+00:00",
                "rail_available": 1, "planned_events": 83, "matched_change_events": 61,
                "classified_change_events": 61, "delayed_events": 47,
                "positive_delay_minutes_total": 930.6, "maximum_delay_minutes": 40.0,
            }],
            generated_at=datetime(2026, 9, 14, 10, tzinfo=UTC),
        )
        city = next(city for city in payload["cities"] if city["key"] == "duisburg")
        self.assertEqual(city["matchCoverage"], 0.7349)
        self.assertEqual(city["coverageState"], "DEGRADED")
        self.assertEqual(city["positiveDelayRate"], 0.7705)
        self.assertEqual(city["positiveDelayMinutesTotal"], 930.6)
        self.assertEqual(city["meanDelay"], 19.8)
        self.assertEqual(city["unmatched"], 22)

    def test_readiness_requires_coverage_in_every_city_and_healthy_sources(self) -> None:
        start = datetime(2026, 9, 11, tzinfo=UTC)
        rows = []
        for offset in range(72):
            for city in ("duesseldorf", "duisburg", "essen", "koeln"):
                rows.append({
                    "city": city, "hour_utc": (start + timedelta(hours=offset)).isoformat(),
                    "paired": 1, "weather_available": 1, "rail_available": 1,
                    "planned_events": 1, "matched_change_events": 1,
                    "classified_change_events": 1,
                })
        payload = dashboard_payload(
            rows, generated_at=start + timedelta(hours=71),
            quality_results={"dwd_live_observations": [{"rule": "freshness", "status": "pass"}]},
        )
        self.assertEqual(payload["status"], "ANALYSIS READY")
        self.assertTrue(payload["readiness"]["ready"])

        failed = dashboard_payload(
            rows, generated_at=start + timedelta(hours=71),
            quality_results={"db_changes": [{"rule": "schema_drift", "status": "failure"}]},
        )
        self.assertEqual(failed["status"], "OVERLAP DETECTED")
        self.assertEqual(failed["sources"][2]["state"], "FAILED")

    def test_database_context_keeps_latest_quality_run_for_each_scope(self) -> None:
        with TemporaryDirectory() as directory:
            database = Path(directory) / "quality.sqlite"
            with sqlite3.connect(database) as connection:
                connection.executescript(
                    """
                    CREATE TABLE artifact_imports (
                      id INTEGER PRIMARY KEY, scope_key TEXT, retrieved_at TEXT
                    );
                    CREATE TABLE quality_runs (
                      run_id INTEGER PRIMARY KEY, dataset_key TEXT, import_id INTEGER
                    );
                    CREATE TABLE quality_results (
                      result_id INTEGER PRIMARY KEY, run_id INTEGER, rule_key TEXT,
                      status TEXT, records_checked INTEGER, records_failed INTEGER,
                      details_json TEXT
                    );
                    """
                )
                connection.executemany(
                    "INSERT INTO artifact_imports VALUES (?, ?, ?)",
                    [
                        (1, "01078", "2026-09-14T10:00:00+00:00"),
                        (2, "02667", "2026-09-14T11:00:00+00:00"),
                    ],
                )
                connection.executemany(
                    "INSERT INTO quality_runs VALUES (?, 'dwd_weather', ?)",
                    [(1, 1), (2, 2)],
                )
                connection.executemany(
                    "INSERT INTO quality_results VALUES (?, ?, 'freshness', ?, 1, ?, ?)",
                    [
                        (1, 1, "pass", 0, json.dumps({"severity": "medium"})),
                        (2, 2, "warning", 1, json.dumps({"severity": "medium"})),
                    ],
                )

            context = database_publish_context(database)

        checks = context["qualityResults"]["dwd_weather"]
        self.assertEqual({check["scope"] for check in checks}, {"01078", "02667"})
        self.assertEqual(context["dataDatabaseUpdatedAt"], "2026-09-14T11:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
