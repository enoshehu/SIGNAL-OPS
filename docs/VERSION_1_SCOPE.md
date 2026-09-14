# Version 1 scope

Version 1 is a reproducible Weather × Railway case study for Duisburg, Essen, Düsseldorf, and
Köln. It is one implementation stage of the unchanged `PROJECT_VISION.md`, not a replacement for
the longer-term plan.

## Required

| Area | Release evidence |
|---|---|
| Sources | Preserved DWD and DB files for an overlapping window |
| Pipeline | Replayable ingestion and canonical SQLite data |
| Quality | Persisted rule results and schema checks |
| Analysis | City-hour comparison with sample size and limits |
| Operations | Four signals plus one documented incident lifecycle |
| Web | Public Pages dashboard built from reproducible evidence |
| Automation | Passing CI and a secrets-safe scheduled collection |
| Handoffs | Small Excel, Power BI, Jira, Confluence, and Miro examples |

External tools are outputs, not runtime dependencies. Repository exports must remain useful when
an external workspace is unavailable.

## Not required for version 1

- SMARD, UBA, or Destatis
- additional cities
- PostgreSQL or hosted warehouse storage
- a Python web API
- forecasting or machine learning
- a numeric trust score
- multi-user accounts
- two-way synchronization with review tools
- production availability or real-time guarantees

These capabilities remain scheduled in [ROADMAP.md](ROADMAP.md).

## Definition of done

- [ ] The committed evidence contains overlapping weather and railway hours.
- [x] A clean clone rebuilds the published data and passes all tests.
- [x] Every dashboard number traces to SQLite and a preserved source file.
- [x] Pages passes automated accessibility checks and desktop/mobile visual review.
- [x] Security, licence, and claim-to-evidence reviews are complete.
- [ ] Release `v1.0.0` includes a short demo and release notes.
