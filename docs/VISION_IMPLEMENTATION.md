# Project vision implementation map

This file maps the unchanged `PROJECT_VISION.md` to implementation evidence.

| Vision capability | Status | Evidence or dependency |
|---|---|---|
| DWD raw ingestion | Complete for v1 | Temperature/humidity, precipitation, and wind products across four city scopes |
| DB planned timetable ingestion | Complete | Incremental hourly collection across four city stations |
| DB timetable change ingestion | Complete | Incremental 15-minute full-change collection, separated from plans |
| Config-driven dataset onboarding | Partial | Catalog and entity scopes are configurable; each new provider still needs code and tests |
| Source, dataset and entity catalog | Complete | Universal SQLite tables |
| Weather observations | Complete for v1 | Temperature, humidity, rainfall, wind speed/direction, and gusts with 180-day analytical retention |
| Rhine–Ruhr city profiles | Complete | Selectable DWD/DB profiles for Duisburg, Essen, Düsseldorf, and Köln |
| Railway service events | Complete for plan/change snapshots | Rolling plans and changes normalized across four cities |
| City-scoped quality | Complete | Latest import and checks resolve by station scope instead of global source order |
| Weather × Railway city-hour export | Partial | Export and condition profile work; genuine overlapping evidence awaits the next DWD day |
| Raw/Bronze and parsed-raw layers | Complete | Raw archive plus SQLite replay tables; credential-free evidence is committed |
| Validation and quality results | Complete for v1 | Product-specific value checks, timestamps, integrity, continuity, freshness, and schema drift |
| Data Source Health | Partial | Scheduled runs evaluate quality; the dashboard currently shows availability only |
| Numeric Data Trust Score | Planned after validation | Current outputs show individual rule evidence |
| Schema drift | Complete at parsed-payload layer | Baseline field/type fingerprints; raw contract drift remains later work |
| Delay and cancellation derivation | Complete for matched events | Stable plan/change join; unmatched changes excluded |
| Signals and thresholds | Complete for v1 | Four transparent rules: delay, cancellation, stale source, and schema change |
| Incidents, actions and decisions | Partial | Duplicate-safe local incident lifecycle is implemented; external Jira sync is blocked on a workspace |
| Excel review queue | Partial | Initial formatted workbook exists; automated regeneration remains planned |
| Power BI data exports | Planned | Sprint 8; `.pbix` requires Power BI access |
| Jira/Confluence/Miro outputs | Planned | Sprint 8; live publishing requires external accounts |
| Static mission-control UI | Live | `site/` renders measured rail evidence and exposes the missing joined evidence |
| Query API | Planned for a later release | Version 1 uses static JSON on Pages |
| CI | Complete | Python 3.11–3.13, lint, format, tests, and offline evidence rebuild |
| Pages deployment | Live | [Public dashboard](https://enoshehu.github.io/SIGNAL-OPS/) |
| Scheduled collection | Complete for v1 | GitHub live DWD/DB run, 180-day analytical retention, 30-day raw retention, failure issue, and Pages deployment verified |
| SMARD, UBA and Destatis missions | Planned | Separate adapters require verified contracts |

Only measured counts from real or explicitly labelled fixture runs may be added to this table.
