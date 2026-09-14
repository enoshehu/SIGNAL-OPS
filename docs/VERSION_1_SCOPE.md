# SIGNAL//OPS version 1.0 scope

This document translates the long-term goals in `PROJECT_VISION.md` into a finite first release.
The original vision remains the long-term product contract. This file decides what version 1.0
must prove and what later releases may add.

## Release statement

Version 1.0 is a reproducible Weather × Railway data product for Duisburg, Essen, Düsseldorf,
and Köln. It preserves source evidence, checks data quality, calculates supported railway metrics,
and publishes an honest static dashboard through GitHub Actions and GitHub Pages.

The platform is reusable, not no-code. DWD and DB prove that two structurally different sources
can share storage, lineage, quality, signal, and publishing conventions. A new source still needs
an adapter, normalizer, rules, and tests.

## Required for version 1.0

| Area | Smallest credible deliverable | Completion evidence |
|---|---|---|
| DWD + DB | Four-city ingestion, replay, normalization, and an overlapping analysis window | Reproducible run and source coverage table |
| Quality | Explicit rule results and parsed-schema drift | Tests plus persisted evidence |
| Signals | Stale source, schema change, delay over 20 minutes, and cancellation | Deterministic examples and tests |
| Incident workflow | One controlled failure from detection through resolution | Repository record plus one Jira issue |
| GitHub Actions | Tests, lint, package check, and Pages deployment | Passing workflows on `main` |
| GitHub Pages | Static overview, city comparison, quality state, caveats, and downloads | Public URL |
| Excel | One formatted Data Steward Review Queue | Versioned `.xlsx` artifact |
| Power BI | Three-page report using the published export | `.pbix` plus PDF/screenshots and refresh notes |
| Jira | Delivery backlog and one data-quality incident | Linked project/issue and exported evidence |
| Confluence | Concise architecture and incident decision page | Linked page and exported PDF |
| Miro | Architecture, lineage, incident lifecycle, and onboarding frame | Linked board and exported PDF/image |

External tools support the data product; they are not runtime dependencies. The repository and
published data remain understandable if an external link is unavailable.

## Explicitly deferred

- SMARD electricity data.
- UBA air-quality data.
- Destatis and other public-statistics sources.
- Additional cities and networks.
- Forecasting and machine-learning anomaly detection.
- Numeric trust scores without a defensible weighting model.
- A hosted Python query API.
- User accounts and multi-user incident management.
- Importing reviewer edits from Excel.
- Automatic Miro or Confluence publishing.
- Generic configuration-only onboarding for arbitrary sources.
- PostgreSQL, a warehouse, or production real-time guarantees.

## Future releases

### Version 1.1 — reliability

Improve retention, scheduled collection, duplicate-incident suppression, contract tests,
accessibility, and optional reviewed-correction import.

### Version 2.0 — energy

Add SMARD as the third adapter and use DWD weather in a second analytical mission. Measure how
much code can actually be reused before strengthening the universal-platform claim.

### Version 2.1 — air quality

Add UBA station measurements, weather association, missing-measurement signals, and a city-level
air-quality view.

### Version 3.0 — multi-domain operations

Add Destatis, combined mission control, actions, decisions, operational KPIs, improved
source/API-health history, reusable adapter tooling, and an optional server-hosted query API.
Evaluate a numeric trust score only after its weights can be justified and validated. This closes
the remaining long-term concepts in `PROJECT_VISION.md` without pretending they belong in the
first release.

## Definition of done

Version 1.0 is complete only when a clean clone can reproduce a fixture run, real paired hours
support the published analysis, all automated checks pass, Pages is live, and every public claim
links to evidence. External deliverables must have repository exports so they remain reviewable.
