# Sprint 1 — Foundation

**Status:** ✅ Complete  
**Date:** 2026-09-14  
**Theme:** Establish trustworthy boundaries before retrieving live data.

## Sprint goal

Create a runnable, documented Python foundation that can accept real DWD and Deutsche Bahn
integrations without coupling the core pipeline to vendor APIs, network libraries, or storage.

## Delivered

- [x] Python 3.11+ `src` package scaffold.
- [x] Project metadata and optional development tooling.
- [x] Typed `RawRecord` and `IngestionResult` domain models.
- [x] `SourceAdapter` and `RecordSink` protocols.
- [x] DWD Open Data adapter boundary.
- [x] Deutsche Bahn Timetables adapter boundary.
- [x] In-memory sink for tests and experiments.
- [x] Source-independent ingestion pipeline.
- [x] TOML configuration with environment overrides.
- [x] External-only DB credential configuration.
- [x] Safe CLI status command.
- [x] Six deterministic offline tests.
- [x] README, build log, roadmap, and sprint documentation.
- [x] Git repository initialized on `main`.

## Verification evidence

Executed from the Desktop repository with Python 3.13:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3.13 -m unittest discover -s tests -v
```

Observed result: six tests ran and passed.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3.13 -m signalops status \
  --config config/base.toml
```

Observed result: DWD configuration ready; DB credentials required; no network requests made.

## Decisions

Architectural decision details are recorded as ADR-001 through ADR-007 in
[the build and architecture log](../BUILD_LOG.md).

## Changes from plan

- The test suite uses Python's standard library instead of requiring Pytest, allowing immediate
  offline verification without installing packages.
- Live endpoint validation was kept out of Sprint 1 and remains the first Sprint 2 activity.

## Known limitations

- No adapter performs live retrieval yet.
- No raw or curated persistence layer exists.
- No quality rules, analytical results, dashboards, or production metrics exist.
- DB ingestion cannot begin until valid credentials are supplied externally.

## Handoff

Sprint 1 meets its stated foundation goal. The project is deliberately paused before Sprint 2 so
the owner can approve the first station, product, time window, and credential approach.

