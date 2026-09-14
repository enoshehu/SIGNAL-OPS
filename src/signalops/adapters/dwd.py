"""DWD hourly temperature download and parser."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from io import BytesIO, TextIOWrapper
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from signalops.config import DWDSettings
from signalops.domain import RawArtifact, RawRecord
from signalops.http import HttpClient


class DWDOpenDataAdapter:
    name = "dwd"

    def __init__(self, settings: DWDSettings, http: HttpClient | None = None) -> None:
        self.settings = settings
        self.http = http or HttpClient()

    @property
    def url(self) -> str:
        path = self.settings.archive_path.format(station_id=self.settings.station_id)
        return f"{self.settings.base_url}/{path.lstrip('/')}"

    @property
    def ready(self) -> bool:
        return self.settings.enabled and self.settings.base_url.startswith("https://")

    def download(self) -> RawArtifact:
        result = self.http.get(self.url, headers={}, timeout=self.settings.timeout_seconds)
        return RawArtifact(
            source=self.name,
            external_id=f"hourly-air-temperature-{self.settings.station_id}",
            filename=PurePosixPath(self.url).name,
            retrieved_at=result.retrieved_at,
            content=result.content,
            content_type=result.content_type,
            provenance={"source_url": result.url, "station_id": self.settings.station_id},
        )

    def parse(self, artifact: RawArtifact) -> Iterable[RawRecord]:
        try:
            archive = ZipFile(BytesIO(artifact.content))
        except BadZipFile as exc:
            raise ValueError("DWD response is not a valid ZIP archive") from exc
        names = [
            name
            for name in archive.namelist()
            if PurePosixPath(name).name.startswith("produkt_tu_stunde_") and name.endswith(".txt")
        ]
        if len(names) != 1:
            raise ValueError("DWD archive must contain exactly one hourly temperature table")
        with archive, archive.open(names[0]) as raw_file:
            reader = csv.DictReader(TextIOWrapper(raw_file, encoding="utf-8-sig"), delimiter=";")
            required = {"STATIONS_ID", "MESS_DATUM", "QN_9", "TT_TU", "RF_TU"}
            headers = {header.strip() for header in (reader.fieldnames or [])}
            missing = required - headers
            if missing:
                raise ValueError(f"DWD table is missing columns: {', '.join(sorted(missing))}")
            for raw_row in reader:
                row = {str(key).strip(): str(value).strip() for key, value in raw_row.items()}
                station_id = row["STATIONS_ID"].zfill(5)
                if station_id != self.settings.station_id:
                    raise ValueError(
                        f"DWD row station {station_id} does not match {self.settings.station_id}"
                    )
                observed = row["MESS_DATUM"]
                yield RawRecord(
                    source=self.name,
                    external_id=f"{station_id}-{observed}",
                    retrieved_at=artifact.retrieved_at,
                    payload={
                        "station_id": station_id,
                        "observed_at_utc": observed,
                        "temperature_c": _number(row["TT_TU"]),
                        "relative_humidity_pct": _number(row["RF_TU"]),
                        "source_quality_level": row["QN_9"],
                    },
                    provenance={"source_url": artifact.provenance["source_url"]},
                )


def _number(value: str) -> float | None:
    return None if value in {"", "-999"} else float(value)
