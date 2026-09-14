# Project vision implementation map

This file maps `PROJECT_VISION.md` to evidence. `Complete` means implemented and tested; `Blocked`
means an external account or application is required; `Planned` means no completion claim is made.

| Vision capability | Status | Evidence or dependency |
|---|---|---|
| DWD raw ingestion | Complete | Historical Berlin proof plus four preserved Rhine–Ruhr station archives |
| DB planned timetable ingestion | Complete | 241 live stop records preserved across four city stations |
| Config-driven dataset onboarding | Complete for DWD/DB | `config/datasets/*.toml`, catalog tests |
| Source, dataset and entity catalog | Complete | Universal SQLite tables |
| Weather observations | Complete | 105,600 regional canonical observations plus historical Berlin evidence |
| Rhine–Ruhr city profiles | Complete | Selectable DWD/DB profiles for Duisburg, Essen, Düsseldorf, and Köln |
| Railway service events | Complete for planned events | 353 live planned arrival/departure events normalized across four cities |
| City-scoped quality | Complete | Latest import and checks resolve by station scope instead of global source order |
| Weather × Railway city-hour export | Partial | Export works and preserves unmatched hours; current sources have zero overlapping hours |
| Raw/Bronze and parsed-raw layers | Complete | Raw archive plus SQLite replay tables |
| Validation and quality results | Complete per city | DWD and DB checks select station-scoped imports and persist evidence |
| Data Source Health | Partial | Transparent rule states exist; API health and UI remain later work |
| Numeric Data Trust Score | Deliberately deferred | No justified weighting formula; evidence stays visible per rule |
| Schema drift | Complete at parsed-payload layer | Baseline field/type fingerprints; raw contract drift remains later work |
| Signals and thresholds | Planned | Sprint 6 |
| Incidents, actions and decisions | Planned | Sprint 7 |
| Excel review queue | Planned | Sprint 8 |
| Power BI data exports | Planned | Sprint 8; `.pbix` requires Power BI access |
| Jira/Confluence/Miro outputs | Planned | Sprint 8; live publishing requires external accounts |
| Mission-control UI and query API | Planned | Sprint 9 |
| CI, scheduling and release | Planned | Sprint 10; remote publication requires GitHub access |
| SMARD, UBA and Destatis missions | Source research in progress | Separate adapters require verified contracts |

Only measured counts from real or explicitly labelled fixture runs may be added to this table.
