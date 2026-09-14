import unittest
from datetime import UTC, datetime
from pathlib import Path

from signalops.adapters import InMemoryRawArtifactStore
from signalops.domain import RawArtifact, RawRecord
from signalops.pipeline import IngestionPipeline


class FakeSource:
    name = "fake-weather"

    def download(self) -> RawArtifact:
        return RawArtifact(
            self.name,
            "sample-download",
            "sample.json",
            datetime(2026, 9, 14, tzinfo=UTC),
            b"{}",
            "application/json",
            {"source_url": "https://example.invalid/sample"},
        )

    def parse(self, artifact: RawArtifact):
        return [
            RawRecord(
                source=self.name,
                external_id="sample-1",
                retrieved_at=artifact.retrieved_at,
                payload={"temperature_c": 18.0},
                provenance={"fixture": "unit-test"},
            )
        ]


class PipelineTests(unittest.TestCase):
    def test_pipeline_preserves_raw_artifact_and_reports_parsed_count(self) -> None:
        store = InMemoryRawArtifactStore()
        result = IngestionPipeline(store).run(FakeSource())

        self.assertEqual(result.source, "fake-weather")
        self.assertEqual(result.records_parsed, 1)
        self.assertEqual(result.artifact_path, Path("sample.json"))
        self.assertEqual(store.artifacts[0].external_id, "sample-download")

    def test_raw_records_require_timezone_aware_retrieval_time(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            RawRecord("dwd", "x", datetime.fromisoformat("2026-09-14"), {}, {})
