"""Command-line entry point for safe local operations."""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime
import os
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

from signalops.adapters import DeutscheBahnTimetablesAdapter, DWDOpenDataAdapter, RawFileStore
from signalops.config import ConfigurationError, load_settings
from signalops.catalog import load_catalog
from signalops.storage import SQLiteRecordStore
from signalops.universal import normalize
from signalops.quality import assess
from signalops.analysis import export_hourly_csv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="signalops", description="SIGNAL//OPS DataOps CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    status = subparsers.add_parser("status", help="show configuration readiness; make no API calls")
    default_config = Path(os.getenv("SIGNALOPS_CONFIG", "config/base.toml"))
    status.add_argument("--config", type=Path, default=default_config)
    ingest = subparsers.add_parser("ingest", help="download and preserve one raw source response")
    ingest.add_argument("--source", choices=("dwd", "db"), required=True)
    ingest.add_argument("--city", help="city profile; default is configured in base.toml")
    ingest.add_argument("--config", type=Path, default=default_config)
    ingest.add_argument("--dry-run", action="store_true", help="show the request without sending it")
    ingest.add_argument("--at", help="DB plan hour in ISO format, for example 2026-09-14T10:00:00+00:00")
    replay = subparsers.add_parser("replay", help="verify and load one saved raw artifact")
    replay.add_argument("path", type=Path)
    replay.add_argument("--config", type=Path, default=default_config)
    normal = subparsers.add_parser("normalize", help="build canonical observations or events")
    normal.add_argument("--dataset", choices=("dwd_weather", "db_timetables"), required=True)
    normal.add_argument("--config", type=Path, default=default_config)
    quality = subparsers.add_parser("quality", help="run configured data-quality checks")
    quality.add_argument("--dataset", choices=("dwd_weather", "db_timetables"), required=True)
    quality.add_argument("--city", help="run checks for one city profile")
    quality.add_argument("--config", type=Path, default=default_config)
    analysis = subparsers.add_parser("analyze", help="export the city-hour analysis table")
    analysis.add_argument("--config", type=Path, default=default_config)
    analysis.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "status":
        try:
            settings = load_settings(args.config)
        except ConfigurationError as exc:
            print(f"Configuration error: {exc}")
            return 2
        dwd = DWDOpenDataAdapter(settings.dwd)
        db = DeutscheBahnTimetablesAdapter(settings.db)
        print(f"{settings.name} [{settings.environment}]")
        print(f"data directory: {settings.data_dir}")
        print("cities: " + ", ".join(city.name for city in settings.cities))
        print(f"default city: {settings.city().name}")
        print(f"DWD adapter: {'configured' if dwd.ready else 'disabled'}")
        if not settings.db.enabled:
            db_status = "disabled"
        else:
            db_status = "configured" if db.ready else "credentials required"
        print(f"DB adapter: {db_status}")
        print("No network requests were made.")
        return 0
    if args.command == "ingest":
        try:
            settings = load_settings(args.config)
        except ConfigurationError as exc:
            print(f"Configuration error: {exc}")
            return 2
        try:
            requested_at = (
                datetime.fromisoformat(args.at)
                if args.at
                else datetime.now(ZoneInfo("Europe/Berlin"))
            )
        except ValueError:
            print("Invalid --at value. Use ISO format with a UTC offset.")
            return 2
        if requested_at.utcoffset() is None:
            print("Invalid --at value. Include a UTC offset, for example +00:00.")
            return 2
        try:
            city = settings.city(args.city)
        except ConfigurationError as exc:
            print(f"Configuration error: {exc}")
            return 2
        dwd_settings = replace(settings.dwd, station_id=city.dwd_station_id)
        db_settings = replace(settings.db, eva_number=city.db_eva_number)
        source_settings = dwd_settings if args.source == "dwd" else db_settings
        if not source_settings.enabled:
            print(f"Source is disabled in configuration: {args.source}")
            return 2
        adapter = (
            DWDOpenDataAdapter(dwd_settings)
            if args.source == "dwd"
            else DeutscheBahnTimetablesAdapter(db_settings, requested_at=requested_at)
        )
        print(f"city: {city.name}")
        print(f"source: {adapter.name}")
        print(f"request: {adapter.url}")
        if args.dry_run:
            print("Dry run: no request sent and no file written.")
            return 0
        try:
            artifact = adapter.download()
            target = RawFileStore(settings.data_dir).save(artifact)
        except (RuntimeError, ValueError) as exc:
            print(f"Ingestion failed: {exc}")
            return 2
        try:
            record_count = sum(1 for _ in adapter.parse(artifact))
        except ValueError as exc:
            print(f"Raw file saved: {target}")
            print(f"Parsing failed: {exc}")
            return 2
        print(f"saved: {target}")
        print(f"parsed records: {record_count}")
        return 0
    if args.command == "replay":
        try:
            settings = load_settings(args.config)
            artifact = RawFileStore(settings.data_dir).load(args.path)
            if artifact.source == "dwd":
                station_id = str(artifact.provenance.get("station_id", settings.dwd.station_id))
                adapter = DWDOpenDataAdapter(replace(settings.dwd, station_id=station_id))
            elif artifact.source == "db":
                station_eva = str(artifact.provenance.get("station_eva", settings.db.eva_number))
                adapter = DeutscheBahnTimetablesAdapter(
                    replace(settings.db, eva_number=station_eva)
                )
            else:
                raise ValueError(f"Unsupported source in metadata: {artifact.source}")
            database_path = settings.data_dir / "signalops.sqlite"
            with SQLiteRecordStore(database_path) as store:
                result = store.store(artifact, args.path, adapter.parse(artifact))
        except (OSError, KeyError, RuntimeError, ValueError, sqlite3.Error) as exc:
            print(f"Replay failed: {exc}")
            return 2
        print(f"verified raw file: {args.path}")
        print(f"database: {database_path}")
        print(f"records seen: {result.records_seen}")
        print(f"new records inserted: {result.records_inserted}")
        return 0
    if args.command == "normalize":
        try:
            settings = load_settings(args.config)
            catalog_dir = args.config.resolve().parent / "datasets"
            definition = load_catalog(catalog_dir)[args.dataset]
            database_path = settings.data_dir / "signalops.sqlite"
            inserted = normalize(database_path, definition)
        except (OSError, KeyError, RuntimeError, ValueError, sqlite3.Error) as exc:
            print(f"Normalization failed: {exc}")
            return 2
        print(f"dataset: {args.dataset}")
        print(f"new canonical rows: {inserted}")
        return 0
    if args.command == "quality":
        try:
            settings = load_settings(args.config)
            definition = load_catalog(args.config.resolve().parent / "datasets")[args.dataset]
            city = settings.city(args.city)
            scope = city.dwd_station_id if definition.adapter == "dwd" else city.db_eva_number
            results = assess(
                settings.data_dir / "signalops.sqlite", definition,
                entity_key=f"{definition.adapter}:{scope}",
            )
        except (OSError, KeyError, RuntimeError, ValueError, sqlite3.Error) as exc:
            print(f"Quality check failed: {exc}")
            return 2
        print(f"city: {city.name}")
        for result in results:
            print(f"{result.rule}: {result.status} ({result.failed}/{result.checked} failed)")
        return int(any(result.status == "failure" for result in results))
    if args.command == "analyze":
        try:
            settings = load_settings(args.config)
            database_path = settings.data_dir / "signalops.sqlite"
            output = args.output or settings.data_dir / "processed" / "rhine_ruhr_hourly.csv"
            row_count = export_hourly_csv(database_path, output)
        except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
            print(f"Analysis export failed: {exc}")
            return 2
        print(f"database: {database_path}")
        print(f"output: {output}")
        print(f"city-hour rows: {row_count}")
        return 0
    return 1
