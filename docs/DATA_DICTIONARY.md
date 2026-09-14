# Data dictionary

## Canonical tables

| Table | Grain | Purpose |
|---|---|---|
| `sources` | one source | Publisher, licence, and source URL |
| `datasets` | one dataset and source stream | Adapter, stream, entity type, and refresh plan |
| `entities` | one station | Rail or weather station with city metadata |
| `observations` | station × timestamp × metric × import | Temperature, humidity, rain, wind, and gust values |
| `service_events` | station × stop × arrival/departure × import | Planned or changed railway event snapshots |
| `quality_results` | quality run × rule | Inspectable pass, warning, or failure evidence |
| `operational_signals` | stable rule × city/hour or source scope | Evidence for the four approved version 1.0 signal types |
| `incidents` | incident occurrence | Open/resolved lifecycle; at most one open incident per stable signal |

Current signal types are `DELAY_OVER_20_MINUTES`, `CANCELLATION_DETECTED`,
`SOURCE_DATA_STALE`, and `SCHEMA_CHANGED`. A resolved condition may open a later incident if it is
detected again. No machine-learning score or opaque composite severity is used.

## Rhine–Ruhr city-hour export

File: `data/rhine_ruhr/processed/rhine_ruhr_hourly.csv`  
Grain: one city and UTC hour per row.

| Field | Meaning |
|---|---|
| `city` | Stable configuration key such as `essen` or `koeln` |
| `hour_utc` | Exact UTC hour bucket |
| `rail_station` | DB station name when railway data exists |
| `weather_station` | DWD station name when weather data exists |
| `planned_arrivals` | Count of planned arrival events; null when rail data is unavailable |
| `planned_departures` | Count of planned departure events; null when rail data is unavailable |
| `planned_events` | Planned arrivals plus departures; null when rail data is unavailable |
| `matched_change_events` | Planned events with a matching full-change event by station, stop ID, and event type |
| `cancelled_events` | Matched events whose DB change status is `cs="c"` |
| `delayed_events` | Matched, non-cancelled events with changed time later than planned time |
| `average_delay_minutes` | Mean positive delay among delayed events; null when none are observed |
| `maximum_delay_minutes` | Largest positive delay among delayed events; null when none are observed |
| `air_temperature_c` | DWD hourly air temperature in degrees Celsius |
| `relative_humidity_pct` | DWD hourly relative humidity in percent |
| `precipitation_mm` | DWD hourly precipitation total in millimetres |
| `wind_speed_m_s` | DWD hourly mean wind speed in metres per second |
| `wind_gust_m_s` | DWD maximum wind gust during the last hour in metres per second |
| `wind_direction_deg` | DWD hourly mean wind direction in degrees |
| `weather_available` | `1` if a weather row exists, otherwise `0` |
| `rail_available` | `1` if a railway row exists, otherwise `0` |
| `paired` | `1` only when both sources exist for the city and hour |

The export keeps the preferred latest value for each city, hour, and weather metric, using final
CDC values over overlapping provisional POI values and direct city stations over proxy stations.
It keeps the latest row for each DB stop ID and arrival/departure type. Plan and
change rows are joined only on that stable key. Change events without a saved plan counterpart are
excluded from delay and cancellation metrics because their denominator is unknown. The export
does not calculate disruption rates or causal weather effects.
