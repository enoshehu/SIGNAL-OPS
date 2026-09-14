"""Boundary contracts used by the core pipeline."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from signalops.domain import RawArtifact, RawRecord


class SourceAdapter(Protocol):
    name: str

    def download(self) -> RawArtifact: ...

    def parse(self, artifact: RawArtifact) -> Iterable[RawRecord]: ...


class RawArtifactStore(Protocol):
    def save(self, artifact: RawArtifact) -> Path: ...
