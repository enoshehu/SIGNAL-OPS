from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from signalops.adapters import RawFileStore
from signalops.domain import RawArtifact


class RawFileStoreTests(unittest.TestCase):
    def test_saves_original_bytes_and_metadata(self) -> None:
        artifact = RawArtifact(
            source="dwd",
            external_id="temperature-00433",
            filename="weather.zip",
            retrieved_at=datetime(2026, 9, 14, 10, tzinfo=UTC),
            content=b"sample bytes",
            content_type="application/zip",
            provenance={
                "source_url": "https://example.invalid/weather.zip",
                "station_id": "01303",
            },
        )
        with TemporaryDirectory() as directory:
            store = RawFileStore(Path(directory))
            target = store.save(artifact)
            metadata = json.loads(target.with_suffix(".zip.metadata.json").read_text())

            self.assertEqual(target.read_bytes(), b"sample bytes")
            self.assertEqual(metadata["byte_count"], 12)
            self.assertEqual(metadata["sha256"], hashlib.sha256(b"sample bytes").hexdigest())
            self.assertEqual(list(target.parent.glob("tmp*")), [])

            loaded = store.load(target)
            self.assertEqual(loaded.content, artifact.content)
            self.assertEqual(loaded.provenance["sha256"], metadata["sha256"])
            self.assertEqual(loaded.provenance["station_id"], "01303")

    def test_refuses_to_overwrite_an_existing_raw_artifact(self) -> None:
        artifact = RawArtifact(
            source="db",
            external_id="plan-1",
            filename="plan.xml",
            retrieved_at=datetime(2026, 9, 14, 10, tzinfo=UTC),
            content=b"<timetable />",
            content_type="application/xml",
            provenance={"source_url": "https://example.invalid/plan"},
        )
        with TemporaryDirectory() as directory:
            store = RawFileStore(Path(directory))
            store.save(artifact)
            with self.assertRaisesRegex(FileExistsError, "already exists"):
                store.save(artifact)

    def test_detects_changed_raw_bytes(self) -> None:
        artifact = RawArtifact(
            source="dwd",
            external_id="sample",
            filename="weather.zip",
            retrieved_at=datetime(2026, 9, 14, 10, tzinfo=UTC),
            content=b"original",
            content_type="application/zip",
            provenance={"source_url": "https://example.invalid/weather"},
        )
        with TemporaryDirectory() as directory:
            store = RawFileStore(Path(directory))
            target = store.save(artifact)
            target.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "verification failed"):
                store.load(target)
