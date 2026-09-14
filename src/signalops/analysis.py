"""Small city-hour export for the Rhine–Ruhr case study."""

from __future__ import annotations

import csv
from contextlib import closing
from pathlib import Path
import sqlite3


COLUMNS = (
    "city", "hour_utc", "rail_station", "weather_station",
    "planned_arrivals", "planned_departures", "planned_events",
    "air_temperature_c", "relative_humidity_pct",
    "weather_available", "rail_available", "paired",
)


def hourly_summary(database: Path) -> list[dict[str, object]]:
    query = """
    WITH weather_imports AS (
      SELECT entity_key, MAX(import_id) AS import_id
      FROM observations
      GROUP BY entity_key
    ),
    latest_weather AS (
      SELECT o.* FROM observations o
      JOIN weather_imports i
        ON i.entity_key = o.entity_key AND i.import_id = o.import_id
    ),
    weather AS (
      SELECT json_extract(e.attributes_json, '$.city') AS city,
             substr(o.observed_at, 1, 13) || ':00:00+00:00' AS hour_utc,
             e.name AS weather_station,
             MAX(CASE WHEN o.metric = 'air_temperature' THEN o.value END)
               AS air_temperature_c,
             MAX(CASE WHEN o.metric = 'relative_humidity' THEN o.value END)
               AS relative_humidity_pct
      FROM latest_weather o
      JOIN entities e ON e.entity_key = o.entity_key
      GROUP BY city, hour_utc, e.name
    ),
    rail_imports AS (
      SELECT entity_key, MAX(import_id) AS import_id
      FROM service_events
      GROUP BY entity_key
    ),
    latest_rail AS (
      SELECT s.* FROM service_events s
      JOIN rail_imports i
        ON i.entity_key = s.entity_key AND i.import_id = s.import_id
    ),
    rail AS (
      SELECT json_extract(e.attributes_json, '$.city') AS city,
             substr(s.planned_at, 1, 13) || ':00:00+00:00' AS hour_utc,
             e.name AS rail_station,
             SUM(CASE WHEN s.event_type = 'arrival' THEN 1 ELSE 0 END)
               AS planned_arrivals,
             SUM(CASE WHEN s.event_type = 'departure' THEN 1 ELSE 0 END)
               AS planned_departures,
             COUNT(*) AS planned_events
      FROM latest_rail s
      JOIN entities e ON e.entity_key = s.entity_key
      WHERE s.planned_at IS NOT NULL
      GROUP BY city, hour_utc, e.name
    ),
    hours AS (
      SELECT city, hour_utc FROM weather
      UNION
      SELECT city, hour_utc FROM rail
    )
    SELECT h.city, h.hour_utc, r.rail_station, w.weather_station,
           r.planned_arrivals, r.planned_departures, r.planned_events,
           w.air_temperature_c, w.relative_humidity_pct,
           CASE WHEN w.city IS NULL THEN 0 ELSE 1 END AS weather_available,
           CASE WHEN r.city IS NULL THEN 0 ELSE 1 END AS rail_available,
           CASE WHEN w.city IS NOT NULL AND r.city IS NOT NULL THEN 1 ELSE 0 END AS paired
    FROM hours h
    LEFT JOIN weather w ON w.city = h.city AND w.hour_utc = h.hour_utc
    LEFT JOIN rail r ON r.city = h.city AND r.hour_utc = h.hour_utc
    ORDER BY h.hour_utc, h.city
    """
    with closing(sqlite3.connect(database)) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(query)]


def export_hourly_csv(database: Path, output: Path) -> int:
    rows = hourly_summary(database)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)
