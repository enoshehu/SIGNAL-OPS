"""Universal Source, Dataset, Entity, Observation and Event layer."""

from __future__ import annotations

from contextlib import closing
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from signalops.catalog import DatasetDefinition


SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
  source_key TEXT PRIMARY KEY, name TEXT NOT NULL, provider TEXT NOT NULL,
  license TEXT NOT NULL, source_url TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS datasets (
  dataset_key TEXT PRIMARY KEY, source_key TEXT NOT NULL REFERENCES sources(source_key),
  name TEXT NOT NULL, adapter TEXT NOT NULL, entity_type TEXT NOT NULL,
  refresh_minutes INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS entities (
  entity_key TEXT PRIMARY KEY, entity_type TEXT NOT NULL, name TEXT NOT NULL,
  latitude REAL, longitude REAL, attributes_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS observations (
  observation_id TEXT PRIMARY KEY, dataset_key TEXT NOT NULL, entity_key TEXT NOT NULL,
  import_id INTEGER NOT NULL, observed_at TEXT NOT NULL, metric TEXT NOT NULL,
  value REAL, unit TEXT NOT NULL, source_payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS service_events (
  event_id TEXT PRIMARY KEY, dataset_key TEXT NOT NULL, entity_key TEXT NOT NULL,
  import_id INTEGER NOT NULL, stop_id TEXT NOT NULL, event_type TEXT NOT NULL,
  planned_at TEXT, changed_at TEXT, status TEXT, source_payload_json TEXT NOT NULL
);
"""


def normalize(database: Path, definition: DatasetDefinition) -> int:
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA)
        _register(connection, definition)
        rows = connection.execute(
            """SELECT r.import_id, r.external_id, r.payload_json
               FROM parsed_raw_records r
               JOIN artifact_imports a ON a.id = r.import_id
               WHERE a.source = ?""",
            (definition.adapter,),
        ).fetchall()
        if definition.adapter == "dwd":
            return _weather(connection, definition, rows)
        return _rail(connection, definition, rows)


def _register(connection: sqlite3.Connection, definition: DatasetDefinition) -> None:
    source = definition.source
    connection.execute(
        "INSERT OR REPLACE INTO sources VALUES (?, ?, ?, ?, ?)",
        (source["key"], source["name"], source["provider"], source["license"], source["url"]),
    )
    connection.execute(
        "INSERT OR REPLACE INTO datasets VALUES (?, ?, ?, ?, ?, ?)",
        (
            definition.key, source["key"], definition.name, definition.adapter,
            definition.entity_type, definition.refresh_minutes,
        ),
    )
    for entity in definition.entities:
        attributes = {key: value for key, value in entity.items() if key not in {
            "key", "name", "latitude", "longitude"
        }}
        connection.execute(
            "INSERT OR REPLACE INTO entities VALUES (?, ?, ?, ?, ?, ?)",
            (
                entity["key"], definition.entity_type, entity["name"], entity.get("latitude"),
                entity.get("longitude"), json.dumps(attributes, sort_keys=True),
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
                    observation_id, definition.key, entity_key, import_id, observed.isoformat(),
                    metric, payload[field], unit, payload_json,
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
                    event_id, definition.key, entity_key, import_id, stop_id, event_type,
                    planned, changed, status, payload_json,
                ),
            )
            inserted += cursor.rowcount
    return inserted


def _db_time(value: str | None) -> str | None:
    if not value:
        return None
    local_time = datetime.strptime(value, "%y%m%d%H%M").replace(
        tzinfo=ZoneInfo("Europe/Berlin")
    )
    return local_time.astimezone(UTC).isoformat()
