"""Boundary contracts used by the core pipeline."""

from __future__ import annotations

from typing import Iterable, Protocol

from signalops.domain import RawRecord


class SourceAdapter(Protocol):
    name: str

    def fetch(self) -> Iterable[RawRecord]: ...


class RecordSink(Protocol):
    def write(self, records: Iterable[RawRecord]) -> int: ...
