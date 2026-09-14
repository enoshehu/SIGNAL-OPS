"""In-memory raw-artifact store used by deterministic tests."""

from __future__ import annotations

from pathlib import Path

from signalops.domain import RawArtifact


class InMemoryRawArtifactStore:
    def __init__(self) -> None:
        self.artifacts: list[RawArtifact] = []

    def save(self, artifact: RawArtifact) -> Path:
        self.artifacts.append(artifact)
        return Path(artifact.filename)
