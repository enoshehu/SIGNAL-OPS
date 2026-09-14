"""Rebuild the committed Rhine–Ruhr evidence snapshot without network access."""

from __future__ import annotations

import argparse
import sqlite3
from dataclasses import replace
from pathlib import Path

from signalops.adapters import DeutscheBahnTimetablesAdapter, DWDOpenDataAdapter, RawFileStore
from signalops.analysis import export_hourly_csv
from signalops.catalog import load_catalog
from signalops.config import load_settings
from signalops.storage import SQLiteRecordStore
from signalops.universal import normalize


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=Path("evidence/raw"))
    parser.add_argument("--output", type=Path, default=Path("build/evidence-rebuild"))
    parser.add_argument("--config", type=Path, default=Path("config/base.toml"))
    return parser


def adapter_for(artifact, settings):
    if artifact.source == "dwd":
        station = str(artifact.provenance["station_id"])
        return DWDOpenDataAdapter(replace(settings.dwd, station_id=station))
    if artifact.source == "db":
        station = str(artifact.provenance["station_eva"])
        feed = str(artifact.provenance.get("feed", "plan"))
        return DeutscheBahnTimetablesAdapter(replace(settings.db, eva_number=station), feed=feed)
    raise ValueError(f"Unsupported evidence source: {artifact.source}")


def rebuild(evidence: Path, output: Path, config: Path) -> tuple[int, int, int]:
    database = output / "signalops.sqlite"
    export = output / "rhine_ruhr_hourly.csv"
    if database.exists():
        raise FileExistsError(f"Refusing to overwrite existing rebuild: {database}")
    output.mkdir(parents=True, exist_ok=True)
    settings = load_settings(config)

    artifacts = sorted(
        path
        for path in evidence.rglob("*")
        if (
            path.is_file()
            and not path.name.endswith(".metadata.json")
            and path.with_suffix(path.suffix + ".metadata.json").is_file()
        )
    )
    if not artifacts:
        raise ValueError(f"No evidence artifacts found under {evidence}")

    with SQLiteRecordStore(database) as store:
        for path in artifacts:
            artifact = RawFileStore.load(path)
            adapter = adapter_for(artifact, settings)
            store.store(artifact, path, adapter.parse(artifact))

    catalog = load_catalog(config.resolve().parent / "datasets")
    for dataset_key in ("dwd_weather", "db_timetables", "db_changes"):
        normalize(database, catalog[dataset_key])
    exported = export_hourly_csv(database, export)

    with sqlite3.connect(database) as connection:
        observations = connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
        events = connection.execute("SELECT COUNT(*) FROM service_events").fetchone()[0]
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise sqlite3.IntegrityError(f"Evidence rebuild has foreign-key violations: {violations}")
    return observations, events, exported


def main() -> int:
    args = build_parser().parse_args()
    observations, events, exported = rebuild(args.evidence, args.output, args.config)
    print(f"canonical weather observations: {observations}")
    print(f"canonical railway events: {events}")
    print(f"city-hour rows: {exported}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
