"""Run an offline corrupt-source failure and verified-replay recovery drill."""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from signalops.adapters import DWDOpenDataAdapter, RawFileStore
from signalops.config import DWDSettings
from signalops.domain import RawArtifact
from signalops.storage import SQLiteRecordStore


def _artifact(content: bytes, external_id: str) -> RawArtifact:
    return RawArtifact(
        source="dwd",
        external_id=external_id,
        filename=f"{external_id}.zip",
        retrieved_at=datetime.now(UTC),
        content=content,
        content_type="application/zip",
        provenance={
            "source_url": "https://example.invalid/controlled-drill",
            "station_id": "01303",
        },
    )


def _valid_zip() -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "produkt_tu_stunde_drill.txt",
            "STATIONS_ID;MESS_DATUM;QN_9;TT_TU;RF_TU\r\n01303;2026091410;3;18.2;71.0\r\n",
        )
    return output.getvalue()


def run_drill(report: Path) -> None:
    settings = DWDSettings(True, "https://example.invalid", 30, "01303", "unused")
    adapter = DWDOpenDataAdapter(settings)
    with TemporaryDirectory() as directory:
        data_dir = Path(directory)
        raw_store = RawFileStore(data_dir)
        corrupt_path = raw_store.save(_artifact(b"not-a-zip", "corrupt"))
        corrupt = raw_store.load(corrupt_path)
        try:
            list(adapter.parse(corrupt))
        except ValueError as error:
            detected = str(error)
        else:
            raise RuntimeError("Controlled corrupt archive was not rejected")

        recovered_path = raw_store.save(_artifact(_valid_zip(), "recovered"))
        recovered = raw_store.load(recovered_path)
        records = list(adapter.parse(recovered))
        with SQLiteRecordStore(data_dir / "signalops.sqlite") as store:
            stored = store.store(recovered, recovered_path, records)

    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "# Controlled source-failure drill\n\n"
        f"- Detection: **PASS** — {detected}\n"
        "- Containment: **PASS** — the corrupt response remained preserved but was not imported.\n"
        f"- Recovery: **PASS** — verified replacement parsed and inserted {stored.records_inserted} record.\n"
        "- Credential exposure: **NONE** — the drill is offline and uses no secrets.\n\n"
        "Recovery procedure: retain the failed response, verify the source contract, replay a valid "
        "replacement, run quality checks, then close the incident with evidence.\n",
        encoding="utf-8",
    )


def main() -> int:
    report = Path("docs/analysis/CONTROLLED_FAILURE_DRILL.md")
    run_drill(report)
    print(f"drill report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
