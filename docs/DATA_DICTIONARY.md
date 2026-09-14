# Data dictionary

## Canonical tables

| Table | Grain | Purpose |
|---|---|---|
| `sources` | one source | Publisher, licence, and source URL |
| `datasets` | one dataset and source stream | Adapter, stream, entity type, and refresh plan |
| `entities` | one station | Rail or weather station with city metadata |
| `observations` | station × timestamp × metric × import | Temperature and humidity values |
| `service_events` | station × stop × arrival/departure × import | Planned or changed railway event snapshots |
| `quality_results` | quality run × rule | Inspectable pass, warning, or failure evidence |

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
| `weather_available` | `1` if a weather row exists, otherwise `0` |
| `rail_available` | `1` if a railway row exists, otherwise `0` |
| `paired` | `1` only when both sources exist for the city and hour |

The export keeps the latest row for each station, DB stop ID, and arrival/departure type. Plan and
change rows are joined only on that stable key. Change events without a saved plan counterpart are
excluded from delay and cancellation metrics because their denominator is unknown. The export
does not calculate disruption rates or causal weather effects.
