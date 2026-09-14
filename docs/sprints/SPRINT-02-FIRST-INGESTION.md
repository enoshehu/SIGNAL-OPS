# Sprint 2 — First real ingestion

**Status:** ⚠️ Implementation complete; live DB verification blocked by credentials  
**Date:** 2026-09-14  
**Theme:** Preserve a small real source response before adding a database.

## Sprint goal

Download one narrow response from each official source, preserve the original bytes with
provenance, and parse enough of each format to prove that the adapters understand it.

## Cross-check performed

Three independent review tracks checked DWD, Deutsche Bahn, and implementation simplicity. The
selected sources and access rules were then checked again against their official publisher pages.
The source record is in [`docs/SOURCES.md`](../SOURCES.md).

## Scope checklist

- [x] Verify current official DWD and DB source contracts.
- [x] Select Berlin-Tempelhof DWD station `00433` and Berlin Hbf EVA `8011160`.
- [x] Add a small standard-library HTTP client with timeout, two attempts, a size limit, and clear
  errors.
- [x] Download and parse the DWD hourly temperature/humidity ZIP.
- [x] Build and fixture-test the DB planned-timetable XML download and parser.
- [x] Preserve source bytes and metadata with atomic per-file writes, unique timestamps, overwrite
  protection, and a SHA-256 checksum.
- [x] Add offline tests for URLs, credentials, parsers, storage, retries, and dry runs.
- [x] Add `signalops ingest --source dwd|db` with `--dry-run`.
- [x] Complete and record a live DWD ingestion.
- [ ] Complete a live DB ingestion after credentials are provided externally.

## Deliberately simple design

- Python standard library only; no HTTP framework, database, async code, or plugin system.
- One configured station per source instead of a discovery engine.
- Raw files and one metadata sidecar instead of a manifest service.
- Parsers produce the existing source-independent record envelope; persistence of parsed records
  remains Sprint 3 work.

## Verification evidence

Offline suite:

```text
15 tests ran and passed.
```

Live DWD observation:

```text
retrieved_at: 2026-09-14T16:37:48.650512+00:00
source: DWD CDC hourly air temperature, station 00433
downloaded bytes: 81,967
SHA-256: 74d9a38949449f27032e10c3b170bd5df58a102398c370001dca9084a3462ca9
parsed rows: 13,200
```

These are results from that single reproducible run, not production performance or quality
metrics. Raw data is ignored by Git but kept in the local project under `data/raw/dwd/`.

DB verification:

- URL construction, secret headers, missing-credential behavior, and XML parsing pass offline.
- DB credentials were later configured locally and detected successfully.
- A live request on 2026-09-14 reached the DB API but returned HTTP 403 with the published message
  `Not registered to plan`.
- This access gate was resolved during Sprint 6: the application was subscribed and two plan
  requests returned valid, empty XML responses. No timetable event is claimed from those files.

## Changes from plan

- The first slice uses only DB `plan`; live-change retrieval is deferred until the basic credentialed
  request succeeds.
- Parsed rows are counted but not stored. Durable parsed storage belongs to Sprint 3.
- Sprint 2's DB access gate was later closed in Sprint 6. The historical 403 remains documented.
- Raw content and metadata are individually atomic files, not one atomic two-file transaction. A
  parsing failure clearly reports that the preserved raw path already exists.

## Handoff

The application is now subscribed to the free Timetables product. Credentials remain configured
locally as environment variables:

```bash
export DB_API_CLIENT_ID="..."
export DB_API_KEY="..."
```

Do not paste credentials into documentation, Git, or chat. A non-empty timetable response is still
required before real railway events can be analysed.
