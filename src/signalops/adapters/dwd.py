"""DWD hourly climate-product downloads and parsers."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from io import BytesIO, TextIOWrapper
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from signalops.config import DWDSettings
from signalops.domain import RawArtifact, RawRecord
from signalops.http import HttpClient

PRODUCTS = {
    "air_temperature": {
        "prefix": "produkt_tu_stunde_",
        "quality": "QN_9",
        "fields": {
            "temperature_c": "TT_TU",
            "relative_humidity_pct": "RF_TU",
        },
    },
    "precipitation": {
        "prefix": "produkt_rr_stunde_",
        "quality": "QN_8",
        "fields": {"precipitation_mm": "R1"},
    },
    "wind": {
        "prefix": "produkt_ff_stunde_",
        "quality": "QN_3",
        "fields": {"wind_speed_m_s": "F", "wind_direction_deg": "D"},
    },
}


class DWDOpenDataAdapter:
    name = "dwd"

    def __init__(
        self,
        settings: DWDSettings,
        http: HttpClient | None = None,
        product: str = "air_temperature",
    ) -> None:
        if product not in PRODUCTS:
            raise ValueError(f"Unsupported DWD product: {product}")
        self.settings = settings
        self.http = http or HttpClient()
        self.product = product

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
            external_id=f"hourly-{self.product}-{self.settings.station_id}",
            filename=PurePosixPath(self.url).name,
            retrieved_at=result.retrieved_at,
            content=result.content,
            content_type=result.content_type,
            provenance={
                "source_url": result.url,
                "station_id": self.settings.station_id,
                "stream_key": "observations" if self.product == "air_temperature" else self.product,
                "product": self.product,
            },
        )

    def parse(self, artifact: RawArtifact) -> Iterable[RawRecord]:
        try:
            archive = ZipFile(BytesIO(artifact.content))
        except BadZipFile as exc:
            raise ValueError("DWD response is not a valid ZIP archive") from exc
        product = PRODUCTS[self.product]
        names = [
            name
            for name in archive.namelist()
            if PurePosixPath(name).name.lower().startswith(str(product["prefix"]))
            and name.endswith(".txt")
        ]
        if len(names) != 1:
            raise ValueError(f"DWD archive must contain exactly one hourly {self.product} table")
        with archive, archive.open(names[0]) as raw_file:
            reader = csv.DictReader(TextIOWrapper(raw_file, encoding="utf-8-sig"), delimiter=";")
            fields = dict(product["fields"])
            quality_field = str(product["quality"])
            required = {"STATIONS_ID", "MESS_DATUM", quality_field, *fields.values()}
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
                payload: dict[str, object] = {
                    "station_id": station_id,
                    "observed_at_utc": observed,
                    "source_quality_level": row[quality_field],
                    "product": self.product,
                }
                payload.update({key: _number(row[column]) for key, column in fields.items()})
                yield RawRecord(
                    source=self.name,
                    external_id=f"{station_id}-{observed}",
                    retrieved_at=artifact.retrieved_at,
                    payload=payload,
                    provenance={"source_url": artifact.provenance["source_url"]},
                )


def _number(value: str) -> float | None:
    return None if value in {"", "-999"} else float(value)
