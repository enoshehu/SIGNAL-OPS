"""Source-independent ingestion orchestration."""

from signalops.domain import IngestionResult
from signalops.ports import RecordSink, SourceAdapter


class IngestionPipeline:
    def __init__(self, sink: RecordSink) -> None:
        self.sink = sink

    def run(self, source: SourceAdapter) -> IngestionResult:
        written = self.sink.write(source.fetch())
        return IngestionResult(source=source.name, records_written=written)
