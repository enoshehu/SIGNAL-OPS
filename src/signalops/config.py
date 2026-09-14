"""Typed, secret-safe application configuration."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


class ConfigurationError(ValueError):
    """Raised when configuration cannot be loaded or validated."""


@dataclass(frozen=True, slots=True)
class SourceSettings:
    enabled: bool
    base_url: str
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class DWDSettings(SourceSettings):
    station_id: str
    archive_path: str


@dataclass(frozen=True, slots=True)
class DBSettings(SourceSettings):
    eva_number: str
    client_id: str | None
    api_key: str | None

    @property
    def credentials_configured(self) -> bool:
        return bool(self.client_id and self.api_key)


@dataclass(frozen=True, slots=True)
class CitySettings:
    key: str
    name: str
    db_station_name: str
    db_eva_number: str
    dwd_station_name: str
    dwd_station_id: str


@dataclass(frozen=True, slots=True)
class Settings:
    name: str
    environment: str
    data_dir: Path
    default_city: str
    cities: tuple[CitySettings, ...]
    dwd: DWDSettings
    db: DBSettings

    def city(self, key: str | None = None) -> CitySettings:
        wanted = key or self.default_city
        for city in self.cities:
            if city.key == wanted:
                return city
        choices = ", ".join(city.key for city in self.cities)
        raise ConfigurationError(f"Unknown city '{wanted}'. Choose from: {choices}")


def _source(table: dict[str, object], label: str) -> SourceSettings:
    try:
        base_url = str(table["base_url"]).rstrip("/")
        timeout = int(table["timeout_seconds"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigurationError(f"Invalid {label} source configuration") from exc
    if not base_url.startswith("https://") or timeout <= 0:
        raise ConfigurationError(f"{label} requires an HTTPS URL and positive timeout")
    return SourceSettings(bool(table.get("enabled", True)), base_url, timeout)


def load_settings(path: str | Path = "config/base.toml") -> Settings:
    config_path = Path(path)
    try:
        with config_path.open("rb") as handle:
            raw = tomllib.load(handle)
        app = raw["app"]
        sources = raw["sources"]
        dwd_base = _source(sources["dwd"], "DWD")
        db_base = _source(sources["db"], "DB")
        dwd_archive_path = str(sources["dwd"]["archive_path"])
        cities = tuple(
            CitySettings(
                key=str(key),
                name=str(value["name"]),
                db_station_name=str(value["db_station_name"]),
                db_eva_number=str(value["db_eva_number"]),
                dwd_station_name=str(value["dwd_station_name"]),
                dwd_station_id=str(value["dwd_station_id"]),
            )
            for key, value in raw["cities"].items()
        )
        default_city = str(app.get("default_city", "essen"))
    except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigurationError(f"Could not load configuration from {config_path}") from exc

    city_by_key = {city.key: city for city in cities}
    if default_city not in city_by_key:
        raise ConfigurationError(f"Unknown default city: {default_city}")
    selected = city_by_key[default_city]

    data_dir = Path(os.getenv("SIGNALOPS_DATA_DIR", str(app.get("data_dir", "data"))))
    if not data_dir.is_absolute():
        data_dir = config_path.resolve().parent.parent / data_dir

    return Settings(
        name=str(app.get("name", "SIGNAL//OPS")),
        environment=os.getenv("SIGNALOPS_ENV", str(app.get("environment", "development"))),
        data_dir=data_dir,
        default_city=default_city,
        cities=cities,
        dwd=DWDSettings(
            enabled=dwd_base.enabled,
            base_url=dwd_base.base_url,
            timeout_seconds=dwd_base.timeout_seconds,
            station_id=selected.dwd_station_id,
            archive_path=dwd_archive_path,
        ),
        db=DBSettings(
            enabled=db_base.enabled,
            base_url=db_base.base_url,
            timeout_seconds=db_base.timeout_seconds,
            eva_number=selected.db_eva_number,
            client_id=os.getenv("DB_API_CLIENT_ID") or None,
            api_key=os.getenv("DB_API_KEY") or None,
        ),
    )
