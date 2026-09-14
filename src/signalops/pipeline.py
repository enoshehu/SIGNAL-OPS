"""Source-independent raw ingestion orchestration."""

from signalops.domain import IngestionResult
from signalops.ports import RawArtifactStore, SourceAdapter


class IngestionPipeline:
    def __init__(self, raw_store: RawArtifactStore) -> None:
        self.raw_store = raw_store

    def run(self, source: SourceAdapter) -> IngestionResult:
        artifact = source.download()
        artifact_path = self.raw_store.save(artifact)
        records_parsed = sum(1 for _ in source.parse(artifact))
        return IngestionResult(source.name, artifact_path, records_parsed)
