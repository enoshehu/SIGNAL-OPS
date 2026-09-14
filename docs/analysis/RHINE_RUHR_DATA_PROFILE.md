# Rhine–Ruhr regional data profile

Date checked: 2026-09-14  
Database: local isolated Sprint 6 database under `data/rhine_ruhr/`

## Intended use and grain

The analytical table has one row per city and UTC hour. Weather and railway records match only
when their configured city key and UTC hour are identical. A missing source remains null and is
never converted to zero.

## Weather profile

| City | Source rows | Canonical observations | Missing values | UTC coverage |
|---|---:|---:|---:|---|
| Düsseldorf | 13,200 | 26,400 | 552 (2.09%) | 2025-03-13 00:00 to 2026-09-13 23:00 |
| Duisburg | 13,200 | 26,400 | 0 (0.00%) | 2025-03-13 00:00 to 2026-09-13 23:00 |
| Essen | 13,200 | 26,400 | 0 (0.00%) | 2025-03-13 00:00 to 2026-09-13 23:00 |
| Köln | 13,200 | 26,400 | 68 (0.26%) | 2025-03-13 00:00 to 2026-09-13 23:00 |

All four city-scoped checks passed timestamp validity, humidity range, uniqueness, entity
integrity, hourly continuity, freshness, and parsed-schema stability. Missing-value checks produced
warnings for Düsseldorf and Köln.

## Railway profile

| City | Raw stops | Planned events | UTC event coverage |
|---|---:|---:|---|
| Düsseldorf | 58 | 95 | 2026-09-14 17:00 to 18:00 |
| Duisburg | 59 | 83 | 2026-09-14 16:56 to 18:01 |
| Essen | 39 | 51 | 2026-09-14 17:01 to 17:59 |
| Köln | 65 | 124 | 2026-09-14 17:00 to 17:59 |

All 353 planned events passed timestamp validity. Four later full-change snapshots contained 2,599
raw stops and 3,564 arrival/departure updates. Timestamp checks on those updates found 78 records
without their own usable planned or changed time: Düsseldorf 18, Duisburg 38, Essen 0, and Köln 22.

Plans and changes are matched on station, DB stop ID, and arrival/departure type. The saved plan
slice has 331 matched events. Its rail-only descriptive results are:

| City | Plans | Matched changes | Cancelled | Positively delayed | Mean positive delay | Maximum positive delay |
|---|---:|---:|---:|---:|---:|---:|
| Düsseldorf | 95 | 95 | 0 | 66 | 12.8 min | 84 min |
| Duisburg | 83 | 61 | 0 | 47 | 19.8 min | 83 min |
| Essen | 51 | 51 | 0 | 35 | 5.2 min | 27 min |
| Köln | 124 | 124 | 2 | 73 | 13.3 min | 90 min |

These are one-slice observations, not production KPIs or representative performance claims.
Missing change rows are not counted as on-time, and changes without a saved plan are excluded.

## Join coverage finding

| City | Exported hours | Weather hours | Rail hours | Paired hours |
|---|---:|---:|---:|---:|
| Düsseldorf | 13,202 | 13,200 | 2 | 0 |
| Duisburg | 13,203 | 13,200 | 3 | 0 |
| Essen | 13,201 | 13,200 | 1 | 0 |
| Köln | 13,201 | 13,200 | 1 | 0 |

**Finding:** the current snapshot cannot answer a Weather × Railway question because the DWD
archive ends one day before the DB plan slice. Severity is high for joined analysis and confidence
is high because the maximum and minimum source timestamps were checked directly.

**Smallest remediation:** preserve the current DB slice, refresh the four DWD archives after they
include 2026-09-14, replay and normalize those snapshots, then regenerate the same export.

The official DWD archives were checked again on 2026-09-14 and still ended at 23:00 UTC on
2026-09-13 for all four stations.

## Sources

- [DWD current hourly station catalogue](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/air_temperature/recent/TU_Stundenwerte_Beschreibung_Stationen.txt)
- [DWD hourly temperature archives](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/air_temperature/recent/)
- [DB Timetables product and contract](https://developers.deutschebahn.com/db-api-marketplace/apis/product/timetables)
- Preserved raw files and metadata under `evidence/raw/`, with the working copy under the local
  `data/rhine_ruhr/raw/` directory.
