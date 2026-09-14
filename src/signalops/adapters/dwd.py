"""DWD hourly CDC archives and current POI observation parsers."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from datetime import UTC, datetime
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
    "extreme_wind": {
        "prefix": "produkt_fx_stunde_",
        "quality": "QN_8",
        "fields": {"wind_gust_m_s": "FX_911"},
    },
}

POI_FIELDS = {
    "temperature_c": "dry_bulb_temperature_at_2_meter_above_ground",
    "relative_humidity_pct": "relative_humidity",
    "precipitation_mm": "precipitation_amount_last_hour",
    "wind_speed_m_s": "mean_wind_speed_during last_10_min_at_10_meters_above_ground",
    "wind_direction_deg": "mean_wind_direction_during_last_10 min_at_10_meters_above_ground",
    "wind_gust_m_s": "maximum_wind_speed_last_hour",
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
                "delivery": "cdc",
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


class DWDPOIAdapter:
    """Parse DWD's rolling current-day station observations without credentials."""

    name = "dwd"

    def __init__(self, settings: DWDSettings, http: HttpClient | None = None) -> None:
        self.settings = settings
        self.http = http or HttpClient()

    @property
    def poi_token(self) -> str:
        return self.settings.poi_id.ljust(5, "_")

    @property
    def url(self) -> str:
        path = self.settings.poi_path.format(poi_token=self.poi_token)
        return f"{self.settings.poi_base_url}/{path.lstrip('/')}"

    @property
    def ready(self) -> bool:
        return (
            self.settings.enabled
            and bool(self.settings.poi_id)
            and self.settings.poi_base_url.startswith("https://")
        )

    def download(self) -> RawArtifact:
        result = self.http.get(self.url, headers={}, timeout=self.settings.timeout_seconds)
        return RawArtifact(
            source=self.name,
            external_id=f"poi-hourly-{self.settings.station_id}",
            filename=PurePosixPath(self.url).name,
            retrieved_at=result.retrieved_at,
            content=result.content,
            content_type=result.content_type,
            provenance={
                "source_url": result.url,
                "station_id": self.settings.station_id,
                "poi_id": self.settings.poi_id,
                "stream_key": "live_observations",
                "product": "poi_observations",
                "delivery": "poi",
            },
        )

    def parse(self, artifact: RawArtifact) -> Iterable[RawRecord]:
        text = TextIOWrapper(BytesIO(artifact.content), encoding="utf-8-sig", newline="")
        reader = csv.DictReader(text, delimiter=";")
        headers = {str(header).strip() for header in (reader.fieldnames or [])}
        required = {"surface observations", "Parameter description", *POI_FIELDS.values()}
        missing = required - headers
        if missing:
            raise ValueError(f"DWD POI table is missing columns: {', '.join(sorted(missing))}")

        station_row = next(reader, None)
        header_row = next(reader, None)
        if station_row is None or header_row is None:
            raise ValueError("DWD POI table is missing its station or description row")
        reported_poi_id = str(station_row["surface observations"]).strip().rstrip("_")
        if reported_poi_id != self.settings.poi_id:
            raise ValueError(
                f"DWD POI station {reported_poi_id} does not match {self.settings.poi_id}"
            )

        for raw_row in reader:
            row = {str(key).strip(): str(value).strip() for key, value in raw_row.items()}
            date = row["surface observations"]
            time = row["Parameter description"]
            try:
                observed = datetime.strptime(f"{date} {time}", "%d.%m.%y %H:%M").replace(tzinfo=UTC)
            except ValueError as exc:
                raise ValueError(f"Invalid DWD POI timestamp: {date} {time}") from exc
            observed_utc = observed.strftime("%Y%m%d%H")
            payload: dict[str, object] = {
                "station_id": self.settings.station_id,
                "poi_id": reported_poi_id,
                "observed_at_utc": observed_utc,
                "observation_status": "provisional",
                "product": "poi_observations",
            }
            for field, column in POI_FIELDS.items():
                value = _poi_number(row[column])
                if field in {"wind_speed_m_s", "wind_gust_m_s"} and value is not None:
                    value /= 3.6
                payload[field] = value
            yield RawRecord(
                source=self.name,
                external_id=f"{self.settings.station_id}-{observed_utc}",
                retrieved_at=artifact.retrieved_at,
                payload=payload,
                provenance={"source_url": artifact.provenance["source_url"]},
            )


def _poi_number(value: str) -> float | None:
    return None if value in {"", "---"} else float(value.replace(",", "."))
