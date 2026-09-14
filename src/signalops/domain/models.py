"""Source-independent domain types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class RawArtifact:
    """An HTTP response preserved before parsing or transformation."""

    source: str
    external_id: str
    filename: str
    retrieved_at: datetime
    content: bytes
    content_type: str
    provenance: Mapping[str, str]

    def __post_init__(self) -> None:
        if self.retrieved_at.tzinfo is None:
            raise ValueError("retrieved_at must be timezone-aware")
        if not self.source or not self.external_id or not self.filename:
            raise ValueError("source, external_id, and filename are required")


@dataclass(frozen=True, slots=True)
class RawRecord:
    source: str
    external_id: str
    retrieved_at: datetime
    payload: Mapping[str, Any]
    provenance: Mapping[str, str]

    def __post_init__(self) -> None:
        if self.retrieved_at.tzinfo is None:
            raise ValueError("retrieved_at must be timezone-aware")
        if not self.source or not self.external_id:
            raise ValueError("source and external_id are required")


@dataclass(frozen=True, slots=True)
class IngestionResult:
    source: str
    records_written: int
