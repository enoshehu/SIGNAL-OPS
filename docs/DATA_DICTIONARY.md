# Data dictionary

## Canonical tables

| Table | Grain | Purpose |
|---|---|---|
| `sources` | one source | Publisher, licence, and source URL |
| `datasets` | one dataset | Adapter, entity type, and planned refresh |
| `entities` | one station | Rail or weather station with city metadata |
| `observations` | station × timestamp × metric × import | Temperature and humidity values |
| `service_events` | station × stop × arrival/departure × import | Planned railway events |
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
| `air_temperature_c` | DWD hourly air temperature in degrees Celsius |
| `relative_humidity_pct` | DWD hourly relative humidity in percent |
| `weather_available` | `1` if a weather row exists, otherwise `0` |
| `rail_available` | `1` if a railway row exists, otherwise `0` |
| `paired` | `1` only when both sources exist for the city and hour |

The export uses the latest imported snapshot per station. It does not calculate delays,
cancellations, disruption rates, or causal weather effects.
