from datetime import UTC, datetime
from typing import Iterable
import unittest

from signalops.adapters import InMemoryRecordSink
from signalops.domain import RawRecord
from signalops.pipeline import IngestionPipeline


class FakeSource:
    name = "fake-weather"

    def fetch(self) -> Iterable[RawRecord]:
        return [
            RawRecord(
                source=self.name,
                external_id="sample-1",
                retrieved_at=datetime(2026, 9, 14, tzinfo=UTC),
                payload={"temperature_c": 18.0},
                provenance={"fixture": "unit-test"},
            )
        ]


class PipelineTests(unittest.TestCase):
    def test_pipeline_writes_records_and_returns_observed_count(self) -> None:
        sink = InMemoryRecordSink()
        result = IngestionPipeline(sink).run(FakeSource())

        self.assertEqual(result.source, "fake-weather")
        self.assertEqual(result.records_written, 1)
        self.assertEqual(sink.records[0].external_id, "sample-1")

    def test_raw_records_require_timezone_aware_retrieval_time(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            RawRecord("dwd", "x", datetime(2026, 9, 14), {}, {})
