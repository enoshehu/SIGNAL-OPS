"""Universal Source, Dataset, Entity, Observation and Event layer."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from signalops.catalog import DatasetDefinition
from signalops.storage import SQLiteRecordStore

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
  source_key TEXT PRIMARY KEY, name TEXT NOT NULL, provider TEXT NOT NULL,
  license TEXT NOT NULL, source_url TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS datasets (
  dataset_key TEXT PRIMARY KEY, source_key TEXT NOT NULL REFERENCES sources(source_key),
  name TEXT NOT NULL, adapter TEXT NOT NULL, stream_key TEXT NOT NULL, entity_type TEXT NOT NULL,
  refresh_minutes INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS entities (
  entity_key TEXT PRIMARY KEY, entity_type TEXT NOT NULL, name TEXT NOT NULL,
  latitude REAL, longitude REAL, attributes_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS observations (
  observation_id TEXT PRIMARY KEY, dataset_key TEXT NOT NULL, entity_key TEXT NOT NULL,
  import_id INTEGER NOT NULL, observed_at TEXT NOT NULL, metric TEXT NOT NULL,
  value REAL, unit TEXT NOT NULL, source_payload_json TEXT NOT NULL,
  FOREIGN KEY(dataset_key) REFERENCES datasets(dataset_key),
  FOREIGN KEY(entity_key) REFERENCES entities(entity_key),
  FOREIGN KEY(import_id) REFERENCES artifact_imports(id)
);
CREATE TABLE IF NOT EXISTS service_events (
  event_id TEXT PRIMARY KEY, dataset_key TEXT NOT NULL, entity_key TEXT NOT NULL,
  import_id INTEGER NOT NULL, stop_id TEXT NOT NULL, event_type TEXT NOT NULL,
  planned_at TEXT, changed_at TEXT, status TEXT, source_payload_json TEXT NOT NULL,
  FOREIGN KEY(dataset_key) REFERENCES datasets(dataset_key),
  FOREIGN KEY(entity_key) REFERENCES entities(entity_key),
  FOREIGN KEY(import_id) REFERENCES artifact_imports(id)
);
"""


def normalize(database: Path, definition: DatasetDefinition) -> int:
    # Normalization may be the first command run after an upgrade.
    with SQLiteRecordStore(database):
        pass
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA)
        _upgrade_catalog_schema(connection)
        _upgrade_canonical_constraints(connection)
        _register(connection, definition)
        _repair_legacy_rail_streams(connection)
        rows = connection.execute(
            """SELECT r.import_id, r.external_id, r.payload_json
               FROM parsed_raw_records r
               JOIN artifact_imports a ON a.id = r.import_id
               WHERE a.source = ? AND a.stream_key = ?""",
            (definition.adapter, definition.stream),
        ).fetchall()
        try:
            normalizer = NORMALIZERS[definition.adapter]
        except KeyError as exc:
            raise ValueError(f"No normalizer registered for adapter: {definition.adapter}") from exc
        return normalizer(connection, definition, rows)


def _register(connection: sqlite3.Connection, definition: DatasetDefinition) -> None:
    source = definition.source
    connection.execute(
        "INSERT OR REPLACE INTO sources VALUES (?, ?, ?, ?, ?)",
        (source["key"], source["name"], source["provider"], source["license"], source["url"]),
    )
    connection.execute(
        """INSERT OR REPLACE INTO datasets
           (dataset_key, source_key, name, adapter, stream_key, entity_type, refresh_minutes)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            definition.key,
            source["key"],
            definition.name,
            definition.adapter,
            definition.stream,
            definition.entity_type,
            definition.refresh_minutes,
        ),
    )
    for entity in definition.entities:
        attributes = {
            key: value
            for key, value in entity.items()
            if key not in {"key", "name", "latitude", "longitude"}
        }
        connection.execute(
            "INSERT OR REPLACE INTO entities VALUES (?, ?, ?, ?, ?, ?)",
            (
                entity["key"],
                definition.entity_type,
                entity["name"],
                entity.get("latitude"),
                entity.get("longitude"),
                json.dumps(attributes, sort_keys=True),
            ),
        )


def _weather(
    connection: sqlite3.Connection, definition: DatasetDefinition, rows: list[tuple]
) -> int:
    inserted = 0
    entity_keys = {str(entity["key"]) for entity in definition.entities}
    for import_id, external_id, payload_json in rows:
        payload = json.loads(payload_json)
        entity_key = f"dwd:{payload['station_id']}"
        if entity_key not in entity_keys:
            continue
        observed = datetime.strptime(payload["observed_at_utc"], "%Y%m%d%H").replace(tzinfo=UTC)
        for metric, unit, field in (
            ("air_temperature", "°C", "temperature_c"),
            ("relative_humidity", "%", "relative_humidity_pct"),
        ):
            observation_id = f"{definition.key}:{import_id}:{external_id}:{metric}"
            cursor = connection.execute(
                "INSERT OR IGNORE INTO observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    observation_id,
                    definition.key,
                    entity_key,
                    import_id,
                    observed.isoformat(),
                    metric,
                    payload[field],
                    unit,
                    payload_json,
                ),
            )
            inserted += cursor.rowcount
    return inserted


def _rail(connection: sqlite3.Connection, definition: DatasetDefinition, rows: list[tuple]) -> int:
    inserted = 0
    entity_keys = {str(entity["key"]) for entity in definition.entities}
    for import_id, stop_id, payload_json in rows:
        payload = json.loads(payload_json)
        entity_key = f"db:{payload['station_eva']}"
        if entity_key not in entity_keys:
            continue
        stop = ElementTree.fromstring(payload["raw_xml"])
        for tag, event_type in (("ar", "arrival"), ("dp", "departure")):
            event = stop.find(tag)
            if event is None:
                continue
            planned = _db_time(event.attrib.get("pt"))
            changed = _db_time(event.attrib.get("ct"))
            feed = payload.get("feed", "plan")
            if feed == "changes":
                status = "cancelled" if event.attrib.get("cs") == "c" else "changed"
            else:
                status = "planned"
                changed = None
            event_id = f"{definition.key}:{import_id}:{stop_id}:{event_type}"
            cursor = connection.execute(
                "INSERT OR IGNORE INTO service_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    definition.key,
                    entity_key,
                    import_id,
                    stop_id,
                    event_type,
                    planned,
                    changed,
                    status,
                    payload_json,
                ),
            )
            inserted += cursor.rowcount
    return inserted


def _db_time(value: str | None) -> str | None:
    if not value:
        return None
    local_time = datetime.strptime(value, "%y%m%d%H%M").replace(tzinfo=ZoneInfo("Europe/Berlin"))
    return local_time.astimezone(UTC).isoformat()


Normalizer = Callable[[sqlite3.Connection, DatasetDefinition, list[tuple]], int]
NORMALIZERS: dict[str, Normalizer] = {"dwd": _weather, "db": _rail}


def register_normalizer(adapter: str, normalizer: Normalizer) -> None:
    """Register a domain normalizer without changing catalog-loading logic."""
    if not adapter:
        raise ValueError("Adapter name is required")
    NORMALIZERS[adapter] = normalizer


def _upgrade_catalog_schema(connection: sqlite3.Connection) -> None:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(datasets)")}
    if "stream_key" not in columns:
        connection.execute(
            "ALTER TABLE datasets ADD COLUMN stream_key TEXT NOT NULL DEFAULT 'default'"
        )


def _upgrade_canonical_constraints(connection: sqlite3.Connection) -> None:
    tables = ("observations", "service_events")
    if all(
        len(connection.execute(f"PRAGMA foreign_key_list({table})").fetchall()) >= 3
        for table in tables
    ):
        return
    connection.commit()
    connection.execute("PRAGMA foreign_keys = OFF")
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            CREATE TABLE observations_new (
              observation_id TEXT PRIMARY KEY, dataset_key TEXT NOT NULL, entity_key TEXT NOT NULL,
              import_id INTEGER NOT NULL, observed_at TEXT NOT NULL, metric TEXT NOT NULL,
              value REAL, unit TEXT NOT NULL, source_payload_json TEXT NOT NULL,
              FOREIGN KEY(dataset_key) REFERENCES datasets(dataset_key),
              FOREIGN KEY(entity_key) REFERENCES entities(entity_key),
              FOREIGN KEY(import_id) REFERENCES artifact_imports(id)
            )
            """
        )
        connection.execute("INSERT INTO observations_new SELECT * FROM observations")
        connection.execute("DROP TABLE observations")
        connection.execute("ALTER TABLE observations_new RENAME TO observations")
        connection.execute(
            """
            CREATE TABLE service_events_new (
              event_id TEXT PRIMARY KEY, dataset_key TEXT NOT NULL, entity_key TEXT NOT NULL,
              import_id INTEGER NOT NULL, stop_id TEXT NOT NULL, event_type TEXT NOT NULL,
              planned_at TEXT, changed_at TEXT, status TEXT, source_payload_json TEXT NOT NULL,
              FOREIGN KEY(dataset_key) REFERENCES datasets(dataset_key),
              FOREIGN KEY(entity_key) REFERENCES entities(entity_key),
              FOREIGN KEY(import_id) REFERENCES artifact_imports(id)
            )
            """
        )
        connection.execute("INSERT INTO service_events_new SELECT * FROM service_events")
        connection.execute("DROP TABLE service_events")
        connection.execute("ALTER TABLE service_events_new RENAME TO service_events")
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise sqlite3.IntegrityError("Canonical migration failed foreign-key validation")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA foreign_keys = ON")


def _repair_legacy_rail_streams(connection: sqlite3.Connection) -> None:
    has_changes = connection.execute(
        "SELECT 1 FROM datasets WHERE dataset_key = 'db_changes'"
    ).fetchone()
    if not has_changes:
        return
    connection.execute(
        """UPDATE service_events
           SET event_id = 'db_changes' || substr(event_id, instr(event_id, ':')),
               dataset_key = 'db_changes'
           WHERE dataset_key = 'db_timetables' AND status IN ('changed', 'cancelled')"""
    )
