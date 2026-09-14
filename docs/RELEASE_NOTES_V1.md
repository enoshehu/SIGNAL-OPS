# SIGNAL//OPS 1.0 release notes — draft

Version 1 delivers a reproducible Rhine–Ruhr weather and railway DataOps case study across
Duisburg, Essen, Düsseldorf and Köln.

## Included

- DWD temperature, humidity, precipitation and wind adapters.
- DB planned timetable and live full-change adapters.
- Raw source retention, metadata, checksums, replay and canonical SQLite lineage.
- Seven-day rolling live storage and immutable release evidence.
- Product-specific quality checks, parsed-payload schema drift and source-health signals.
- Plan/change matching, delay/cancellation signals and duplicate-safe incidents.
- Generated city-hour CSV, paired-window profile and accessible static dashboard.
- GitHub Actions verification, scheduled collection, release-asset state and Pages deployment.
- Failure/recovery drill, runbooks, security/licence review and demo script.

## Release gate still open

Do not tag `v1.0.0` until genuine weather and railway overlap is preserved for every city, the
generated paired analysis is reviewed, and the published dashboard screenshot reflects that
evidence.
