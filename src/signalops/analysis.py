"""Small city-hour export for the Rhine–Ruhr case study."""

from __future__ import annotations

import csv
import sqlite3
from contextlib import closing
from pathlib import Path

COLUMNS = (
    "city",
    "hour_utc",
    "rail_station",
    "weather_station",
    "planned_arrivals",
    "planned_departures",
    "planned_events",
    "matched_change_events",
    "classified_change_events",
    "cancelled_events",
    "delayed_events",
    "positive_delay_minutes_total",
    "average_delay_minutes",
    "maximum_delay_minutes",
    "air_temperature_c",
    "relative_humidity_pct",
    "precipitation_mm",
    "wind_speed_m_s",
    "wind_gust_m_s",
    "wind_direction_deg",
    "temperature_station",
    "temperature_station_role",
    "temperature_source",
    "humidity_station",
    "humidity_station_role",
    "humidity_source",
    "precipitation_station",
    "precipitation_station_role",
    "precipitation_source",
    "wind_station",
    "wind_station_role",
    "wind_source",
    "gust_station",
    "gust_station_role",
    "gust_source",
    "weather_available",
    "rail_available",
    "paired",
)


def hourly_summary(database: Path) -> list[dict[str, object]]:
    query = """
    WITH weather_candidates AS (
      SELECT o.*, a.retrieved_at,
             json_extract(e.attributes_json, '$.city') AS city,
             json_extract(e.attributes_json, '$.role') AS station_role
      FROM observations o
      JOIN artifact_imports a ON a.id = o.import_id
      JOIN entities e ON e.entity_key = o.entity_key
    ),
    weather_ranked AS (
      SELECT *, ROW_NUMBER() OVER (
        PARTITION BY city, observed_at, metric
        ORDER BY CASE WHEN value IS NULL THEN 1 ELSE 0 END,
                 CASE WHEN station_role IS NULL THEN 0 ELSE 1 END,
                 CASE WHEN dataset_key = 'dwd_live_observations' THEN 1 ELSE 0 END,
                 julianday(retrieved_at) DESC, import_id DESC
      ) AS row_number
      FROM weather_candidates
    ),
    latest_weather AS (
      SELECT * FROM weather_ranked WHERE row_number = 1
    ),
    weather AS (
      SELECT json_extract(e.attributes_json, '$.city') AS city,
             substr(o.observed_at, 1, 13) || ':00:00+00:00' AS hour_utc,
             GROUP_CONCAT(DISTINCT e.name) AS weather_station,
             MAX(CASE WHEN o.metric = 'air_temperature' THEN o.value END)
               AS air_temperature_c,
             MAX(CASE WHEN o.metric = 'relative_humidity' THEN o.value END)
               AS relative_humidity_pct,
             MAX(CASE WHEN o.metric = 'precipitation' THEN o.value END)
               AS precipitation_mm,
             MAX(CASE WHEN o.metric = 'wind_speed' THEN o.value END)
               AS wind_speed_m_s,
             MAX(CASE WHEN o.metric = 'wind_gust' THEN o.value END)
               AS wind_gust_m_s,
             MAX(CASE WHEN o.metric = 'wind_direction' THEN o.value END)
               AS wind_direction_deg,
             MAX(CASE WHEN o.metric = 'air_temperature' THEN e.name END)
               AS temperature_station,
             MAX(CASE WHEN o.metric = 'air_temperature' THEN o.station_role END)
               AS temperature_station_role,
             MAX(CASE WHEN o.metric = 'air_temperature' THEN o.dataset_key END)
               AS temperature_source,
             MAX(CASE WHEN o.metric = 'relative_humidity' THEN e.name END)
               AS humidity_station,
             MAX(CASE WHEN o.metric = 'relative_humidity' THEN o.station_role END)
               AS humidity_station_role,
             MAX(CASE WHEN o.metric = 'relative_humidity' THEN o.dataset_key END)
               AS humidity_source,
             MAX(CASE WHEN o.metric = 'precipitation' THEN e.name END)
               AS precipitation_station,
             MAX(CASE WHEN o.metric = 'precipitation' THEN o.station_role END)
               AS precipitation_station_role,
             MAX(CASE WHEN o.metric = 'precipitation' THEN o.dataset_key END)
               AS precipitation_source,
             MAX(CASE WHEN o.metric = 'wind_speed' THEN e.name END)
               AS wind_station,
             MAX(CASE WHEN o.metric = 'wind_speed' THEN o.station_role END)
               AS wind_station_role,
             MAX(CASE WHEN o.metric = 'wind_speed' THEN o.dataset_key END)
               AS wind_source,
             MAX(CASE WHEN o.metric = 'wind_gust' THEN e.name END)
               AS gust_station,
             MAX(CASE WHEN o.metric = 'wind_gust' THEN o.station_role END)
               AS gust_station_role,
             MAX(CASE WHEN o.metric = 'wind_gust' THEN o.dataset_key END)
               AS gust_source
      FROM latest_weather o
      JOIN entities e ON e.entity_key = o.entity_key
      GROUP BY city, hour_utc
    ),
    plan_ranked AS (
      SELECT s.*,
             ROW_NUMBER() OVER (
               PARTITION BY s.entity_key, s.stop_id, s.event_type
               ORDER BY julianday(a.retrieved_at) DESC, s.import_id DESC
             ) AS row_number
      FROM service_events s
      JOIN artifact_imports a ON a.id = s.import_id
      WHERE status = 'planned'
    ),
    plans AS (
      SELECT * FROM plan_ranked WHERE row_number = 1
    ),
    change_ranked AS (
      SELECT s.*,
             ROW_NUMBER() OVER (
               PARTITION BY s.entity_key, s.stop_id, s.event_type
               ORDER BY julianday(a.retrieved_at) DESC, s.import_id DESC
             ) AS row_number
      FROM service_events s
      JOIN artifact_imports a ON a.id = s.import_id
      WHERE status IN ('changed', 'cancelled')
    ),
    latest_changes AS (
      SELECT * FROM change_ranked WHERE row_number = 1
    ),
    change_time_ranked AS (
      SELECT s.*,
             ROW_NUMBER() OVER (
               PARTITION BY s.entity_key, s.stop_id, s.event_type
               ORDER BY julianday(a.retrieved_at) DESC, s.import_id DESC
             ) AS row_number
      FROM service_events s
      JOIN artifact_imports a ON a.id = s.import_id
      WHERE status = 'changed' AND changed_at IS NOT NULL
    ),
    latest_change_times AS (
      SELECT * FROM change_time_ranked WHERE row_number = 1
    ),
    changes AS (
      SELECT c.*,
             CASE WHEN c.status = 'cancelled' THEN NULL
                  ELSE COALESCE(c.changed_at, t.changed_at) END AS effective_changed_at
      FROM latest_changes c
      LEFT JOIN latest_change_times t
        ON t.entity_key = c.entity_key
       AND t.stop_id = c.stop_id
       AND t.event_type = c.event_type
    ),
    merged_rail AS (
      SELECT p.*, c.event_id AS change_event_id,
             c.effective_changed_at AS current_at, c.status AS change_status
      FROM plans p
      LEFT JOIN changes c
        ON c.entity_key = p.entity_key
       AND c.stop_id = p.stop_id
       AND c.event_type = p.event_type
    ),
    rail AS (
      SELECT json_extract(e.attributes_json, '$.city') AS city,
             substr(s.planned_at, 1, 13) || ':00:00+00:00' AS hour_utc,
             e.name AS rail_station,
             SUM(CASE WHEN s.event_type = 'arrival' THEN 1 ELSE 0 END)
               AS planned_arrivals,
             SUM(CASE WHEN s.event_type = 'departure' THEN 1 ELSE 0 END)
               AS planned_departures,
             COUNT(*) AS planned_events,
             SUM(CASE WHEN s.change_event_id IS NOT NULL THEN 1 ELSE 0 END)
               AS matched_change_events,
             SUM(CASE WHEN s.change_status = 'cancelled' OR s.current_at IS NOT NULL
                      THEN 1 ELSE 0 END) AS classified_change_events,
             SUM(CASE WHEN s.change_status = 'cancelled' THEN 1 ELSE 0 END)
               AS cancelled_events,
             SUM(CASE WHEN s.change_status != 'cancelled'
                            AND s.current_at IS NOT NULL
                            AND julianday(s.current_at) > julianday(s.planned_at)
                      THEN 1 ELSE 0 END) AS delayed_events,
             SUM(CASE WHEN s.change_status != 'cancelled'
                            AND julianday(s.current_at) > julianday(s.planned_at)
                      THEN (julianday(s.current_at) - julianday(s.planned_at)) * 1440
                      ELSE 0 END) AS positive_delay_minutes_total,
             ROUND(AVG(CASE WHEN s.change_status != 'cancelled'
                                  AND julianday(s.current_at) > julianday(s.planned_at)
                            THEN (julianday(s.current_at) - julianday(s.planned_at)) * 1440
                       END), 1) AS average_delay_minutes,
             ROUND(MAX(CASE WHEN s.change_status != 'cancelled'
                                  AND julianday(s.current_at) > julianday(s.planned_at)
                            THEN (julianday(s.current_at) - julianday(s.planned_at)) * 1440
                       END), 1) AS maximum_delay_minutes
      FROM merged_rail s
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
           r.matched_change_events, r.classified_change_events,
           r.cancelled_events, r.delayed_events, r.positive_delay_minutes_total,
           r.average_delay_minutes, r.maximum_delay_minutes,
           w.air_temperature_c, w.relative_humidity_pct, w.precipitation_mm,
           w.wind_speed_m_s, w.wind_gust_m_s, w.wind_direction_deg,
           w.temperature_station, w.temperature_station_role, w.temperature_source,
           w.humidity_station, w.humidity_station_role, w.humidity_source,
           w.precipitation_station, w.precipitation_station_role, w.precipitation_source,
           w.wind_station, w.wind_station_role, w.wind_source,
           w.gust_station, w.gust_station_role, w.gust_source,
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
