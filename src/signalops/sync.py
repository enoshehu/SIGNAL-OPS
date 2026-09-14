"""Incremental, failure-isolated synchronization of configured source datasets."""

from __future__ import annotations

import fcntl
import os
import re
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from signalops.adapters import (
    DeutscheBahnTimetablesAdapter,
    DWDOpenDataAdapter,
    DWDPOIAdapter,
    RawFileStore,
)
from signalops.analysis import export_hourly_csv, hourly_summary
from signalops.catalog import DatasetDefinition, load_catalog
from signalops.config import Settings, load_settings
from signalops.operations import run_operational_cycle
from signalops.profile import write_profile
from signalops.publish import database_publish_context, write_dashboard_json
from signalops.quality import assess
from signalops.retention import RetentionResult, apply_retention
from signalops.storage import SQLiteRecordStore
from signalops.universal import normalize

_ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class SyncTarget:
    dataset: DatasetDefinition
    city_key: str
    city_name: str
    scope_key: str

    @property
    def label(self) -> str:
        return f"{self.city_key}/{self.dataset.key}"


@dataclass(frozen=True, slots=True)
class SyncItemResult:
    label: str
    status: str
    detail: str


@dataclass(frozen=True, slots=True)
class SyncSummary:
    items: tuple[SyncItemResult, ...]
    normalized_rows: int = 0
    analysis_rows: int = 0
    paired_hours: int = 0
    signals_detected: int = 0
    incidents_opened: int = 0
    quality_failures: tuple[str, ...] = ()
    retention: RetentionResult | None = None

    @property
    def operational_failures(self) -> tuple[SyncItemResult, ...]:
        return tuple(item for item in self.items if item.status == "failed")


def load_env_file(path: Path, *, override: bool = False) -> tuple[str, ...]:
    """Load literal KEY=VALUE entries without evaluating shell syntax."""
    if not path.exists():
        return ()
    loaded: list[str] = []
    for line_number, original in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = original.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError(f"Invalid environment entry at {path}:{line_number}")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not _ENV_KEY.fullmatch(key):
            raise ValueError(f"Invalid environment key at {path}:{line_number}")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if override or key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return tuple(loaded)


def _ensure_collection_log(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS collection_runs (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            scope_key TEXT NOT NULL,
            stream_key TEXT NOT NULL,
            checked_at TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('success', 'failure')),
            artifact_sha256 TEXT,
            records_seen INTEGER,
            records_inserted INTEGER,
            detail TEXT
        );
        CREATE INDEX IF NOT EXISTS collection_runs_lookup
          ON collection_runs (source, scope_key, stream_key, status, checked_at);
        """
    )


def _latest_success(connection: sqlite3.Connection, target: SyncTarget) -> datetime | None:
    _ensure_collection_log(connection)
    row = connection.execute(
        """
        SELECT checked_at FROM collection_runs
        WHERE source = ? AND scope_key = ? AND stream_key = ? AND status = 'success'
        ORDER BY checked_at DESC LIMIT 1
        """,
        (target.dataset.adapter, target.scope_key, target.dataset.stream),
    ).fetchone()
    if row is None:
        row = connection.execute(
            """
            SELECT loaded_at FROM artifact_imports
            WHERE source = ? AND scope_key = ? AND stream_key = ?
            ORDER BY loaded_at DESC LIMIT 1
            """,
            (target.dataset.adapter, target.scope_key, target.dataset.stream),
        ).fetchone()
    return datetime.fromisoformat(row[0]).astimezone(UTC) if row else None


def target_is_due(
    connection: sqlite3.Connection, target: SyncTarget, now: datetime
) -> tuple[bool, datetime | None]:
    if now.tzinfo is None:
        raise ValueError("Synchronization time must be timezone-aware")
    last_success = _latest_success(connection, target)
    due = last_success is None or now.astimezone(UTC) >= last_success + timedelta(
        minutes=target.dataset.refresh_minutes
    )
    return due, last_success


def _record_run(
    connection: sqlite3.Connection,
    target: SyncTarget,
    now: datetime,
    status: str,
    *,
    checksum: str | None = None,
    records_seen: int | None = None,
    records_inserted: int | None = None,
    detail: str | None = None,
) -> None:
    _ensure_collection_log(connection)
    with connection:
        connection.execute(
            """
            INSERT INTO collection_runs
              (source, scope_key, stream_key, checked_at, status, artifact_sha256,
               records_seen, records_inserted, detail)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                target.dataset.adapter,
                target.scope_key,
                target.dataset.stream,
                now.astimezone(UTC).isoformat(),
                status,
                checksum,
                records_seen,
                records_inserted,
                detail,
            ),
        )


def configured_targets(
    settings: Settings,
    catalog: dict[str, DatasetDefinition],
    *,
    datasets: Sequence[str] = (),
    cities: Sequence[str] = (),
) -> tuple[SyncTarget, ...]:
    selected_datasets = tuple(datasets) or tuple(catalog)
    unknown_datasets = sorted(set(selected_datasets) - set(catalog))
    if unknown_datasets:
        raise ValueError("Unknown datasets: " + ", ".join(unknown_datasets))
    selected_cities = tuple(cities) or tuple(city.key for city in settings.cities)
    city_by_key = {city.key: city for city in settings.cities}
    unknown_cities = sorted(set(selected_cities) - set(city_by_key))
    if unknown_cities:
        raise ValueError("Unknown cities: " + ", ".join(unknown_cities))

    targets: list[SyncTarget] = []
    for dataset_key in selected_datasets:
        definition = catalog[dataset_key]
        for city_key in selected_cities:
            city = city_by_key[city_key]
            entity = next(
                (item for item in definition.entities if item.get("city") == city_key), None
            )
            if entity is None:
                raise ValueError(f"Dataset {dataset_key} has no entity for city {city_key}")
            scope = str(entity["key"]).split(":", 1)[1]
            targets.append(SyncTarget(definition, city.key, city.name, scope))
    return tuple(targets)


def _adapter(settings: Settings, target: SyncTarget, now: datetime):
    city = settings.city(target.city_key)
    if target.dataset.adapter == "dwd":
        delivery = str(target.dataset.source.get("delivery", "cdc"))
        if delivery == "poi":
            entity = next(
                item for item in target.dataset.entities if item.get("city") == target.city_key
            )
            return DWDPOIAdapter(
                replace(
                    settings.dwd,
                    station_id=target.scope_key,
                    poi_id=str(entity.get("poi_id", city.dwd_poi_id)),
                )
            )
        archive_path = str(target.dataset.source.get("archive_path", settings.dwd.archive_path))
        product = str(target.dataset.source.get("product", "air_temperature"))
        return DWDOpenDataAdapter(
            replace(settings.dwd, station_id=target.scope_key, archive_path=archive_path),
            product=product,
        )
    if target.dataset.adapter == "db":
        return DeutscheBahnTimetablesAdapter(
            replace(settings.db, eva_number=city.db_eva_number),
            requested_at=now.astimezone(ZoneInfo("Europe/Berlin")),
            feed=target.dataset.stream,
        )
    raise ValueError(f"No adapter registered for {target.dataset.adapter}")


@contextmanager
def _exclusive_sync(data_dir: Path) -> Iterator[None]:
    data_dir.mkdir(parents=True, exist_ok=True)
    lock_path = data_dir / ".sync.lock"
    with lock_path.open("a", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another SIGNAL//OPS synchronization is already running") from exc
        yield


def synchronize(
    config: Path,
    *,
    env_file: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
    datasets: Sequence[str] = (),
    cities: Sequence[str] = (),
    now: datetime | None = None,
) -> SyncSummary:
    if env_file is not None:
        load_env_file(env_file)
    settings = load_settings(config)
    catalog = load_catalog(config.resolve().parent / "datasets")
    targets = configured_targets(settings, catalog, datasets=datasets, cities=cities)
    current_time = now or datetime.now(UTC)
    if current_time.tzinfo is None:
        raise ValueError("Synchronization time must be timezone-aware")
    database = settings.data_dir / "signalops.sqlite"
    raw_store = RawFileStore(settings.data_dir)
    items: list[SyncItemResult] = []
    touched: set[str] = set()

    with _exclusive_sync(settings.data_dir), SQLiteRecordStore(database) as store:
        for target in targets:
            due, last_success = target_is_due(store.connection, target, current_time)
            if not force and not due:
                next_due = last_success + timedelta(minutes=target.dataset.refresh_minutes)
                items.append(
                    SyncItemResult(target.label, "skipped", f"next due {next_due.isoformat()}")
                )
                continue
            adapter = _adapter(settings, target, current_time)
            if dry_run:
                items.append(SyncItemResult(target.label, "due", adapter.url))
                continue
            try:
                artifact = adapter.download()
                artifact_path = raw_store.save(artifact)
                verified = raw_store.load(artifact_path)
                stored = store.store(verified, artifact_path, adapter.parse(verified))
                checksum = str(verified.provenance["sha256"])
                _record_run(
                    store.connection,
                    target,
                    current_time,
                    "success",
                    checksum=checksum,
                    records_seen=stored.records_seen,
                    records_inserted=stored.records_inserted,
                )
                touched.add(target.dataset.key)
                items.append(
                    SyncItemResult(
                        target.label,
                        "downloaded",
                        f"{stored.records_seen} records; {stored.records_inserted} new",
                    )
                )
            except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
                detail = f"{type(exc).__name__}: {exc}"
                _record_run(store.connection, target, current_time, "failure", detail=detail)
                items.append(SyncItemResult(target.label, "failed", detail))

    if dry_run:
        return SyncSummary(tuple(items))

    cutoff = current_time.astimezone(UTC) - timedelta(days=settings.retention_days)
    raw_cutoff = current_time.astimezone(UTC) - timedelta(days=settings.raw_retention_days)
    retention = apply_retention(database, settings.data_dir, cutoff, raw_cutoff=raw_cutoff)
    normalized_rows = sum(normalize(database, catalog[key]) for key in sorted(touched))
    quality_failures: list[str] = []
    for target in targets:
        results = assess(
            database,
            target.dataset,
            entity_key=f"{target.dataset.adapter}:{target.scope_key}",
        )
        quality_failures.extend(
            f"{target.label}/{result.rule}" for result in results if result.status == "failure"
        )

    if quality_failures:
        return SyncSummary(
            items=tuple(items),
            normalized_rows=normalized_rows,
            quality_failures=tuple(quality_failures),
            retention=retention,
        )

    project_root = config.resolve().parent.parent
    analysis_rows = export_hourly_csv(
        database, settings.data_dir / "processed" / "rhine_ruhr_hourly.csv"
    )
    rows = hourly_summary(database)
    paired_hours = sum(int(row.get("paired") or 0) for row in rows)
    publish_context = database_publish_context(database)
    write_dashboard_json(
        rows,
        project_root / "site" / "data" / "summary.json",
        provenance={"dataDatabaseUpdatedAt": publish_context["dataDatabaseUpdatedAt"]},
        quality_results=publish_context["qualityResults"],
    )
    write_profile(database, settings.data_dir / "processed" / "paired_window_profile.md")
    signals_detected, incidents_opened = run_operational_cycle(database)
    return SyncSummary(
        items=tuple(items),
        normalized_rows=normalized_rows,
        analysis_rows=analysis_rows,
        paired_hours=paired_hours,
        signals_detected=signals_detected,
        incidents_opened=incidents_opened,
        quality_failures=tuple(quality_failures),
        retention=retention,
    )
