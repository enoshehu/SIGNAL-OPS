"""Load small, declarative dataset definitions."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DatasetDefinition:
    key: str
    name: str
    adapter: str
    stream: str
    entity_type: str
    refresh_minutes: int
    source: dict[str, object]
    entities: tuple[dict[str, object], ...]
    quality: tuple[dict[str, object], ...]
    signals: tuple[dict[str, object], ...]


def load_catalog(directory: Path) -> dict[str, DatasetDefinition]:
    catalog: dict[str, DatasetDefinition] = {}
    for path in sorted(directory.glob("*.toml")):
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
        dataset = raw["dataset"]
        entity_rows = raw.get("entities")
        if entity_rows is None:
            entity_rows = [raw["entity"]]
        definition = DatasetDefinition(
            key=str(dataset["key"]),
            name=str(dataset["name"]),
            adapter=str(dataset["adapter"]),
            stream=str(dataset.get("stream", "default")),
            entity_type=str(dataset["entity_type"]),
            refresh_minutes=int(dataset["refresh_minutes"]),
            source=dict(raw["source"]),
            entities=tuple(dict(entity) for entity in entity_rows),
            quality=tuple(raw.get("quality", [])),
            signals=tuple(raw.get("signals", [])),
        )
        if definition.key in catalog:
            raise ValueError(f"Duplicate dataset key: {definition.key}")
        if not definition.adapter or not definition.stream or definition.refresh_minutes <= 0:
            raise ValueError(f"Invalid dataset definition: {path}")
        catalog[definition.key] = definition
    return catalog
