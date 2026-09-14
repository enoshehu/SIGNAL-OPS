"""Command-line entry point for safe local operations."""

from __future__ import annotations

import argparse
import os
import sqlite3
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from signalops.adapters import DeutscheBahnTimetablesAdapter, DWDOpenDataAdapter, RawFileStore
from signalops.analysis import export_hourly_csv
from signalops.catalog import load_catalog
from signalops.config import ConfigurationError, load_settings
from signalops.operations import run_operational_cycle
from signalops.pipeline import IngestionPipeline
from signalops.quality import assess
from signalops.storage import SQLiteRecordStore
from signalops.sync import synchronize
from signalops.universal import normalize


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
    ingest.add_argument(
        "--dry-run", action="store_true", help="show the request without sending it"
    )
    ingest.add_argument(
        "--at", help="DB plan hour in ISO format, for example 2026-09-14T10:00:00+00:00"
    )
    ingest.add_argument(
        "--db-feed",
        choices=("plan", "changes"),
        default="plan",
        help="DB timetable feed; changes uses the current full-change endpoint",
    )
    replay = subparsers.add_parser("replay", help="verify and load one saved raw artifact")
    replay.add_argument("path", type=Path)
    replay.add_argument("--config", type=Path, default=default_config)
    normal = subparsers.add_parser("normalize", help="build canonical observations or events")
    normal.add_argument("--dataset", required=True)
    normal.add_argument("--config", type=Path, default=default_config)
    quality = subparsers.add_parser("quality", help="run configured data-quality checks")
    quality.add_argument("--dataset", required=True)
    quality.add_argument("--city", help="run checks for one city profile")
    quality.add_argument("--config", type=Path, default=default_config)
    analysis = subparsers.add_parser("analyze", help="export the city-hour analysis table")
    analysis.add_argument("--config", type=Path, default=default_config)
    analysis.add_argument("--output", type=Path)
    operate = subparsers.add_parser(
        "operate", help="detect rail signals and open duplicate-safe local incidents"
    )
    operate.add_argument("--config", type=Path, default=default_config)
    sync = subparsers.add_parser(
        "sync", help="download due datasets, refresh quality checks, and rebuild outputs"
    )
    sync.add_argument("--config", type=Path, default=default_config)
    sync.add_argument("--env-file", type=Path, default=Path(".env"))
    sync.add_argument("--force", action="store_true", help="download even when a feed is not due")
    sync.add_argument(
        "--dry-run", action="store_true", help="show due requests without downloading"
    )
    sync.add_argument("--dataset", action="append", default=[], help="limit to one dataset key")
    sync.add_argument("--city", action="append", default=[], help="limit to one city key")
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
            else DeutscheBahnTimetablesAdapter(
                db_settings, requested_at=requested_at, feed=args.db_feed
            )
        )
        print(f"city: {city.name}")
        print(f"source: {adapter.name}")
        print(f"request: {adapter.url}")
        if args.dry_run:
            print("Dry run: no request sent and no file written.")
            return 0
        try:
            result = IngestionPipeline(RawFileStore(settings.data_dir)).run(adapter)
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"Ingestion failed: {exc}")
            return 2
        print(f"saved: {result.artifact_path}")
        print(f"parsed records: {result.records_parsed}")
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
                settings.data_dir / "signalops.sqlite",
                definition,
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
    if args.command == "operate":
        try:
            settings = load_settings(args.config)
            database_path = settings.data_dir / "signalops.sqlite"
            detected, opened = run_operational_cycle(database_path)
        except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
            print(f"Operational cycle failed: {exc}")
            return 2
        print(f"signals detected: {detected}")
        print(f"new incidents opened: {opened}")
        return 0
    if args.command == "sync":
        try:
            summary = synchronize(
                args.config,
                env_file=args.env_file,
                force=args.force,
                dry_run=args.dry_run,
                datasets=args.dataset,
                cities=args.city,
            )
        except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
            print(f"Synchronization failed: {exc}")
            return 2
        for item in summary.items:
            print(f"{item.status}: {item.label} — {item.detail}")
        if not args.dry_run:
            print(f"new canonical rows: {summary.normalized_rows}")
            print(f"analysis rows: {summary.analysis_rows}")
            print(f"paired city-hours: {summary.paired_hours}")
            print(f"signals detected: {summary.signals_detected}")
            print(f"new incidents opened: {summary.incidents_opened}")
            if summary.retention:
                print(f"retention cutoff: {summary.retention.cutoff.isoformat()}")
                print(
                    "retention removed: "
                    f"{summary.retention.database_rows_deleted} database rows, "
                    f"{summary.retention.raw_artifacts_deleted} raw artifacts"
                )
            if summary.quality_failures:
                print("quality warnings: " + ", ".join(summary.quality_failures))
        return 2 if summary.operational_failures else 0
    return 1
