"""Small sink used for deterministic tests and local experiments."""

from __future__ import annotations

from typing import Iterable

from signalops.domain import RawRecord


class InMemoryRecordSink:
    def __init__(self) -> None:
        self.records: list[RawRecord] = []

    def write(self, records: Iterable[RawRecord]) -> int:
        batch = list(records)
        self.records.extend(batch)
        return len(batch)
