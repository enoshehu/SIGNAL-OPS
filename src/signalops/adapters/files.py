"""Simple atomic storage for original source responses."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from signalops.domain import RawArtifact


class RawFileStore:
    def __init__(self, data_dir: Path) -> None:
        self.root = data_dir / "raw"

    def save(self, artifact: RawArtifact) -> Path:
        day = artifact.retrieved_at.strftime("%Y-%m-%d")
        timestamp = artifact.retrieved_at.strftime("%Y%m%dT%H%M%S%fZ")
        directory = self.root / artifact.source / day
        directory.mkdir(parents=True, exist_ok=True)
        filename = Path(artifact.filename).name
        target = directory / f"{timestamp}_{filename}"
        if target.exists() or target.with_suffix(target.suffix + ".metadata.json").exists():
            raise FileExistsError(f"Raw artifact already exists: {target}")
        self._atomic_write(target, artifact.content)

        metadata = {
            "source": artifact.source,
            "external_id": artifact.external_id,
            "filename": filename,
            "retrieved_at": artifact.retrieved_at.isoformat(),
            "content_type": artifact.content_type,
            "source_url": artifact.provenance["source_url"],
            "provenance": artifact.provenance,
            "byte_count": len(artifact.content),
            "sha256": hashlib.sha256(artifact.content).hexdigest(),
        }
        metadata_target = target.with_suffix(target.suffix + ".metadata.json")
        body = json.dumps(metadata, indent=2, sort_keys=True).encode("utf-8") + b"\n"
        self._atomic_write(metadata_target, body)
        return target

    @staticmethod
    def load(path: Path) -> RawArtifact:
        metadata_path = path.with_suffix(path.suffix + ".metadata.json")
        content = path.read_bytes()
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        checksum = hashlib.sha256(content).hexdigest()
        if checksum != metadata["sha256"] or len(content) != metadata["byte_count"]:
            raise ValueError(f"Raw artifact verification failed: {path}")
        provenance = dict(metadata.get("provenance", {"source_url": metadata["source_url"]}))
        provenance["sha256"] = checksum
        return RawArtifact(
            source=metadata["source"],
            external_id=metadata["external_id"],
            filename=metadata["filename"],
            retrieved_at=datetime.fromisoformat(metadata["retrieved_at"]),
            content=content,
            content_type=metadata["content_type"],
            provenance=provenance,
        )

    @staticmethod
    def _atomic_write(target: Path, content: bytes) -> None:
        with NamedTemporaryFile(dir=target.parent, delete=False) as temporary:
            temporary.write(content)
            temporary_path = Path(temporary.name)
        try:
            os.replace(temporary_path, target)
        except BaseException:
            temporary_path.unlink(missing_ok=True)
            raise
