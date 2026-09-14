"""Collect one live four-city slice and refresh the static dashboard payload."""

from __future__ import annotations

import os
import shutil
import sqlite3
from dataclasses import replace
from pathlib import Path

from signalops.adapters import DeutscheBahnTimetablesAdapter, DWDOpenDataAdapter, RawFileStore
from signalops.analysis import hourly_summary
from signalops.catalog import load_catalog
from signalops.config import load_settings
from signalops.operations import run_operational_cycle
from signalops.publish import write_dashboard_json
from signalops.quality import assess
from signalops.storage import SQLiteRecordStore
from signalops.universal import normalize


def collect(adapter, raw_store: RawFileStore, database: Path) -> None:
    artifact = adapter.download()
    artifact_path = raw_store.save(artifact)
    verified = raw_store.load(artifact_path)
    evidence_dir = os.getenv("SIGNALOPS_RUN_EVIDENCE")
    if evidence_dir:
        destination = Path(evidence_dir) / artifact_path.relative_to(raw_store.root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(artifact_path, destination)
        metadata = artifact_path.with_suffix(artifact_path.suffix + ".metadata.json")
        shutil.copy2(metadata, destination.with_suffix(destination.suffix + ".metadata.json"))
    with SQLiteRecordStore(database) as store:
        store.store(verified, artifact_path, adapter.parse(verified))


def main() -> int:
    settings = load_settings(os.getenv("SIGNALOPS_CONFIG", "config/base.toml"))
    if not settings.db.credentials_configured:
        raise RuntimeError("DB_API_CLIENT_ID and DB_API_KEY are required for live collection")
    raw_store = RawFileStore(settings.data_dir)
    database = settings.data_dir / "signalops.sqlite"

    for city in settings.cities:
        collect(
            DWDOpenDataAdapter(replace(settings.dwd, station_id=city.dwd_station_id)),
            raw_store,
            database,
        )
        db_settings = replace(settings.db, eva_number=city.db_eva_number)
        collect(DeutscheBahnTimetablesAdapter(db_settings, feed="plan"), raw_store, database)
        collect(DeutscheBahnTimetablesAdapter(db_settings, feed="changes"), raw_store, database)

    config = Path(os.getenv("SIGNALOPS_CONFIG", "config/base.toml"))
    catalog = load_catalog(config.resolve().parent / "datasets")
    for dataset_key in ("dwd_weather", "db_timetables", "db_changes"):
        normalize(database, catalog[dataset_key])

    for city in settings.cities:
        for dataset_key in ("dwd_weather", "db_timetables", "db_changes"):
            definition = catalog[dataset_key]
            scope = city.dwd_station_id if definition.adapter == "dwd" else city.db_eva_number
            assess(database, definition, entity_key=f"{definition.adapter}:{scope}")

    rows = hourly_summary(database)
    output = Path(os.getenv("SIGNALOPS_SITE_DATA", "site/data/summary.json"))
    write_dashboard_json(rows, output)
    detected, opened = run_operational_cycle(database)
    print(f"dashboard rows: {len(rows)}")
    print(f"signals detected: {detected}")
    print(f"new incidents opened: {opened}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, sqlite3.Error) as error:
        print(f"Live collection failed: {error}")
        raise SystemExit(2) from error
