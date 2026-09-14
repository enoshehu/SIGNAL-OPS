# Project vision implementation map

This file maps `PROJECT_VISION.md` to evidence. `Complete` means implemented and tested; `Blocked`
means an external account or application is required; `Planned` means no completion claim is made.

| Vision capability | Status | Evidence or dependency |
|---|---|---|
| DWD raw ingestion | Complete | Historical Berlin proof plus four preserved Rhine–Ruhr station archives |
| DB planned timetable ingestion | Complete | 221 live stop records preserved across four city stations |
| DB timetable change ingestion | Complete | 2,599 live change-feed stops preserved separately from plans |
| Config-driven dataset onboarding | Extensible core complete | Arbitrary catalog adapters are accepted; normalizer registration and generic entity scopes are tested |
| Source, dataset and entity catalog | Complete | Universal SQLite tables |
| Weather observations | Complete | 105,600 regional canonical observations plus historical Berlin evidence |
| Rhine–Ruhr city profiles | Complete | Selectable DWD/DB profiles for Duisburg, Essen, Düsseldorf, and Köln |
| Railway service events | Complete for plan/change snapshots | 353 plans plus 3,564 live event updates normalized across four cities |
| City-scoped quality | Complete | Latest import and checks resolve by station scope instead of global source order |
| Weather × Railway city-hour export | Partial | Export works and preserves unmatched hours; current sources have zero overlapping hours |
| Raw/Bronze and parsed-raw layers | Complete | Raw archive plus SQLite replay tables; credential-free evidence is committed |
| Validation and quality results | Partial by source | Full configured DWD suite; DB currently checks event timestamp usability |
| Data Source Health | Partial | Transparent rule states exist; API health and UI remain later work |
| Numeric Data Trust Score | Deliberately deferred | No justified weighting formula; evidence stays visible per rule |
| Schema drift | Complete at parsed-payload layer | Baseline field/type fingerprints; raw contract drift remains later work |
| Delay and cancellation derivation | Complete for matched events | Stable plan/change join; unmatched changes excluded |
| Signals and thresholds | Planned | Sprint 7 after the descriptive analysis is valid |
| Incidents, actions and decisions | Planned | Sprint 7 |
| Excel review queue | Partial | Initial formatted workbook exists; automated regeneration remains planned |
| Power BI data exports | Planned | Sprint 8; `.pbix` requires Power BI access |
| Jira/Confluence/Miro outputs | Planned | Sprint 8; live publishing requires external accounts |
| Static mission-control UI | Implemented locally | `site/` renders measured rail evidence and exposes the missing joined evidence |
| Query API | Deferred | GitHub Pages cannot host Python; static JSON is the version 1.0 interface |
| CI | Configured | Python 3.11–3.13, lint, format, tests, and offline evidence rebuild |
| Pages deployment | Configured | Static deployment workflow exists; remote verification requires Pages to be enabled |
| Scheduled collection | Planned | Requires GitHub secrets and a reviewed persistence design |
| SMARD, UBA and Destatis missions | Source research in progress | Separate adapters require verified contracts |

Only measured counts from real or explicitly labelled fixture runs may be added to this table.
