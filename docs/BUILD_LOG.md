# SIGNAL//OPS build and architecture log

This is the chronological project record. Sprint statuses describe the state at that time; use
`ROADMAP.md` for current status. Dates use the Europe/Berlin date.

## Product intent

SIGNAL//OPS is a DataOps application that ingests German weather and
railway data, preserve source provenance, normalize it into a shared model, assess data quality,
and exposes operational outputs. Values are reported only after a reproducible run.

## Architecture

```text
DWD / DB source
      |
adapter.download() -> RawArtifact (original ZIP/XML bytes + provenance)
      |
RawFileStore (each raw and metadata file is written atomically)
      |
adapter.parse() -> RawRecord (counted in Sprint 2; durable storage begins in Sprint 3)
      |
SQLite staged records -> canonical observations / service events
      |
configured quality rules -> persisted results, affected IDs and schema snapshots
      |
signals, operations and analytics (later sprints)
```

The Sprint 1 `IngestionPipeline` remains a tested example of source/sink orchestration. It is not
used by the Sprint 2 raw-download path and will be revisited when parsed storage is designed.

### ADR-001 — Python 3.11 and `src` package layout

- Status: accepted, Sprint 1.
- Decision: use Python 3.11+ with a `src/signalops` package and `pyproject.toml`.
- Why: modern standard-library TOML support, clean import boundaries, and packaging behavior that
  prevents tests from accidentally importing an uninstalled working-directory package.
- Consequence: contributors need Python 3.11 or newer.

### ADR-002 — Ports and adapters

- Status: accepted, Sprint 1.
- Decision: define `SourceAdapter` and `RecordSink` protocols. The orchestration layer knows only
  these contracts, not HTTP libraries, database drivers, or vendor response shapes.
- Why: DWD and DB have different access patterns. Stable boundaries let us test offline and change
  a source or storage technology without rewriting orchestration.

### ADR-003 — Frozen raw record envelope

- Status: accepted, Sprint 1.
- Decision: every parsed item enters the system as a frozen `RawRecord` envelope containing source,
  external ID, UTC retrieval time, payload, and provenance.
- Why: raw provenance is essential for replay, audit, debugging, and later quality checks.
- Consequence: normalization is a later stage and must not overwrite raw source data. Mapping
  payloads inside the envelope are treated as read-only by convention.

### ADR-004 — Configuration and secrets

- Status: accepted, Sprint 1.
- Decision: non-secret defaults live in `config/base.toml`; runtime environment variables override
  environment name, data directory, and DB credentials. Credentials are never stored in TOML.
- Why: this keeps local, CI, and future deployed environments portable and avoids secret leakage.

### ADR-005 — Standard library at the foundation

- Status: accepted, Sprint 1.
- Decision: production code currently has no third-party runtime dependency. HTTP transport will
  be selected in Sprint 2 after validating source behavior. Ruff is development-only; tests use
  the standard library.
- Why: keep the scaffold runnable and reduce premature decisions. Ruff is an optional development
  tool; the test suite itself uses the standard library.

### ADR-006 — No live calls in unit tests

- Status: accepted, Sprint 1.
- Decision: tests use deterministic fake adapters and sinks. Later live-source checks will be
  separately marked integration tests.
- Why: unit tests should be fast, repeatable, credential-free, and safe for CI.

### ADR-007 — Separate plans from evidence

- Status: accepted, Sprint 1 documentation update.
- Decision: `ROADMAP.md` owns future intent and sprint checklists; sprint records own scoped
  delivery evidence; this log owns chronological decisions and verified results.
- Why: a polished repository must make it impossible to mistake planned features for completed
  capabilities.
- Consequence: every sprint updates all three layers before handoff.

### ADR-008 — Preserve bytes before parsing

- Status: accepted, Sprint 2.
- Decision: save each original ZIP or XML response plus a small metadata sidecar before using its
  parser.
- Why: the raw response is the replay and audit boundary; parsed rows alone cannot reproduce a
  changing upstream source.

### ADR-009 — Fixed first slice

- Status: accepted, Sprint 2.
- Decision: start with DWD Berlin-Tempelhof `00433` hourly temperature/humidity and DB Berlin Hbf
  `8011160` planned timetable for one requested hour.
- Why: fixed stations keep the code understandable and allow the source mechanics to be verified
  before adding discovery, normalization, or scale.

### ADR-010 — Standard-library HTTP

- Status: accepted, Sprint 2.
- Decision: use a small `urllib` wrapper with a timeout, two attempts for temporary network errors,
  a five-megabyte response limit, and explicit HTTP error messages.
- Why: this meets the first-ingestion need without adding a runtime dependency or framework.

### ADR-011 — SQLite for local staged storage

- Status: accepted, Sprint 3.
- Decision: use one local SQLite file with `artifact_imports` and `parsed_raw_records` tables.
- Why: SQLite is included with Python, easy to inspect, transactional, and enough for
  the current single-user data volume.
- Consequence: PostgreSQL, ORMs, concurrency tuning, and migrations are deferred until evidence
  shows they are useful.

### ADR-012 — Artifact checksum is replay identity

- Status: accepted, Sprint 3.
- Decision: `(source, SHA-256)` uniquely identifies an imported raw snapshot. The same bytes replay
  as a no-op; changed bytes create a new version even when the upstream filename is unchanged.
- Why: DWD's `_akt.zip` archive changes daily, so its URL and filename are not stable identities.

### ADR-013 — Small universal model with source-shaped payload retention

- Status: accepted, Sprint 4.
- Decision: use shared source, dataset, entity, observation, and service-event tables while
  retaining the parsed source payload on each canonical row.
- Why: weather measurements and railway events need common lineage without forcing their
  domain fields are identical.

### ADR-014 — Quality evidence instead of a numeric trust score

- Status: accepted, Sprint 5.
- Decision: persist pass, warning, or failure per configured rule, together with counts, reasons,
  and affected identifiers. Do not calculate a weighted score.
- Why: there is no evidence-based weighting formula yet. Visible rule results are easier to audit
  and defend than an arbitrary 0–100 number.
- Consequence: a future summary may be added only when its calculation and decision use are
  documented.

### ADR-015 — Import-scoped checks and parsed-schema baseline

- Status: accepted, Sprint 5.
- Decision: assess the latest artifact import and compare its parsed field profile with the first
  stored baseline. Store field names, types, nullability, and presence counts—never values.
- Why: import scope avoids treating retained versions as duplicates. The initial baseline remains
  stable, so an unaccepted change does not silently become normal on the next run.
- Consequence: this detects parser-output drift, not every possible raw ZIP header or XML change.

### ADR-016 — DB station time is converted through Europe/Berlin

- Status: accepted, Sprint 5 pending live-contract confirmation.
- Decision: interpret compact DB planned times in `Europe/Berlin`, then store UTC.
- Why: direct UTC assignment was wrong across standard and daylight-saving time. Winter and summer
  tests now cover the conversion.
- Consequence: live DB evidence remains blocked until credentials allow the current contract and a
  real response to be verified.

## Sprint 1 — Foundation

Date: 2026-09-14

### Goal

Create a runnable, documented architecture that can accept DWD and DB integrations without
coupling the core pipeline to either service.

### Completed

- Created installable Python package and developer tooling configuration.
- Added typed domain models for raw records and ingestion run results.
- Added source and sink contracts.
- Added DWD and DB adapter shells with configuration validation and explicit Sprint 2 boundaries.
- Added a source-independent ingestion pipeline and an in-memory sink for tests.
- Added TOML configuration loading plus external environment overrides.
- Added a `signalops status` CLI that performs no network calls.
- Added offline standard-library unit tests for configuration, adapter readiness, and orchestration
  behavior.
- Added `.env.example`, secret-safe `.gitignore`, repository map, and run instructions.
- Added a GitHub-renderable roadmap, documentation hub, Sprint 1 record, and reusable sprint
  update template.
- Initialized Git locally after verification.

### Setup performed

1. Created the repository structure on the user's Desktop.
2. Added source, tests, configuration, documentation, and project metadata.
3. Used the already-installed Python 3.13 interpreter; no environment or package download was
   required for verification.
4. Ran the standard-library unit suite and CLI status command from the Desktop copy.
5. Initialized a Git repository with `main` as the initial branch. Files remain intentionally
   uncommitted so the user can review the first snapshot before committing it.

### Current limitations

- Adapters validate readiness but intentionally do not issue HTTP requests yet.
- No live data has been collected, so there are no production freshness, completeness, or
  reliability metrics to report.
- No database, schema registry, quality rules, scheduler, dashboard, or CI workflow exists yet.
- Deutsche Bahn credentials must be obtained by the user and injected at runtime.

## Sprint 2 original proposed backlog — First real ingestion

Status: accepted after owner direction; retained here as the pre-implementation plan. Actual scope
and results are recorded in the Sprint 2 section below.

1. Verify current official DWD and DB API documentation, access terms, and endpoint contracts.
2. Select a narrow first slice: one DWD station/product and one DB station/time window.
3. Implement HTTP transport with timeouts, retries, response-size limits, and clear error classes.
4. Implement DWD discovery/download/parsing and DB timetable retrieval/parsing.
5. Store immutable raw responses plus metadata using atomic local writes.
6. Add fixtures captured from permitted responses and contract/parser tests.
7. Add a `signalops ingest` command with dry-run and source selection.
8. Record the first reproducible live-run evidence; report only metrics actually observed.
9. Decide the Sprint 3 persistence target (SQLite locally, with a PostgreSQL-compatible model).

## Documentation update — Repository roadmap

Date: 2026-09-14

- Added `docs/ROADMAP.md` with a ten-sprint delivery map and checklists.
- Added `docs/README.md` as the documentation landing page.
- Added a factual Sprint 1 record and a reusable future-sprint template.
- Updated the root README with GitHub-friendly navigation, status badges, and a clear
  current-project boundary.
- Added `.DS_Store` to ignored local artifacts.
- No application behavior, live-data status, or production metric changed in this update.

## Sprint 2 — First real ingestion

Date: 2026-09-14

### Completed

- Independently cross-checked DWD, DB, and implementation simplicity, then verified source claims
  against official publisher pages.
- Added byte-based raw artifacts, a small HTTP client, and atomic per-file raw/metadata storage.
- Implemented DWD download and ZIP parsing for Berlin-Tempelhof station `00433`.
- Implemented credentialed DB plan download and XML parsing for Berlin Hbf EVA `8011160`.
- Added a safe `ingest` command with source selection and dry-run behavior.
- Resolved relative data paths against the repository instead of the caller's current directory.
- Added source attribution and access documentation.
- Expanded the offline suite to 15 passing tests, including disabled-source, collision, timestamp,
  and schema-drift checks.

### Observed live evidence

- DWD retrieval time: `2026-09-14T16:37:48.650512+00:00`.
- Downloaded: 81,967 bytes from the configured DWD archive.
- SHA-256: `74d9a38949449f27032e10c3b170bd5df58a102398c370001dca9084a3462ca9`.
- Parser produced 13,200 rows from that response.
- These values describe one run. They are not production KPIs or data-quality scores.

### Open exit gate

- DB credentials were initially unavailable. They were later configured and detected without being
  printed or stored in tracked files.
- The first authenticated live request reached DB on 2026-09-14 but returned HTTP 403 with
  `Not registered to plan`.
- The DB adapter is verified offline for its official URL structure, secret headers, XML parser,
  and missing-credential failure.
- This historical access gate was resolved in Sprint 6 when the application subscription became
  active and successful XML responses were preserved.

## Sprint 3 — Durable storage and replay

Date: 2026-09-14

### Completed

- Added raw artifact loading with byte-count and SHA-256 verification.
- Added a no-network `replay` command.
- Added a two-table SQLite schema for artifact imports and parsed raw records.
- Added transactional rollback, checksum-based idempotency, and changed-snapshot version retention.
- Added DWD station-consistency validation.
- Expanded the full offline suite to 19 passing tests.

### Observed verification

- First replay of the Sprint 2 DWD artifact: 13,200 records seen and inserted.
- Second replay of the same bytes: 13,200 records seen and zero inserted.
- Final database state: one artifact import and 13,200 parsed raw records.
- These counts describe a local verification run, not production performance or quality.

### Next gate

Sprint 4 should use a real DB XML response before finalizing canonical railway entities. DB API
Marketplace credentials remain external and were not available during this sprint.

## Sprint 4 — Universal model

Date: 2026-09-14

### Completed

- Added declarative DWD and DB dataset definitions and a catalog loader.
- Added shared source, dataset, entity, observation, and service-event tables.
- Normalized DWD timestamps, temperature, humidity, and units while retaining lineage.
- Added fixture-tested DB arrival and departure normalization.
- Added the `normalize` command and idempotent canonical identifiers.
- Expanded the offline suite to 21 passing tests.

### Observed verification

- The one verified DWD import produced 26,400 canonical observations: 13,200 temperatures and
  13,200 relative-humidity values.
- Coverage is `2025-03-13T00:00:00+00:00` through `2026-09-13T23:00:00+00:00`.
- A second normalization inserted zero rows.

These are local counts and coverage, not production performance or quality metrics.

## Sprint 5 — Data quality and schema drift

Date: 2026-09-14

### Completed

- Added eight configuration-driven DWD checks covering validity, completeness, uniqueness,
  integrity, continuity, freshness, and parsed-schema drift.
- Added SQLite tables for immutable quality runs, individual results, affected identifiers, and
  schema snapshots.
- Added the `quality` command with pass, warning, and failure output.
- Rejected unknown configured rules instead of silently skipping them.
- Profiled schema names and types without retaining source values.
- Corrected DB planned-time conversion and tested winter and summer offsets.
- Expanded the offline suite to 27 passing tests.

### Observed verification

- Latest-import grain: 26,400 DWD observations across 13,200 hourly timestamps.
- Missing values: 73 of 26,400; 36 temperature and 37 humidity.
- Invalid non-null humidity values: 0 of 13,200.
- Duplicate canonical keys, broken entity links, and missing internal hours: zero observed.
- Freshness passed the configured 1,440-minute boundary at execution time.
- The first five-field parsed-payload schema was stored as the baseline.
- The latest quality run persisted eight results and 73 affected identifiers.

These findings describe the saved Berlin-Tempelhof artifact only. They are not a service-level
claim or a trust score.

### Next gate

Sprint 6 needs a real, permitted DB timetable artifact before Weather × Railway joining and
analysis can be presented as real-world evidence. The join window, spatial rule, and temporal
tolerance must be written down before any metric is calculated.

## Sprint 6 — Rhine–Ruhr scope

Date: 2026-09-14

### Completed

- Reframed the case study around Duisburg, Essen, Düsseldorf, and Köln.
- Verified the four Hauptbahnhof EVA numbers with the subscribed DB station-search endpoint.
- Verified four current DWD hourly-temperature stations and archive availability.
- Added `--city` selection while keeping one simple DWD adapter and one DB adapter.
- Stored station identity in raw provenance and restored it during replay.
- Expanded the catalog and normalization layer to map records to four weather and rail entities.
- Changed the DB default request clock from UTC to `Europe/Berlin`.

### Live evidence and limitations

- The DB application subscription is active: authenticated plan requests now succeed.
- Two Berlin verification calls saved valid XML responses, both containing `<timetable/>` and zero
  records. This verifies access, not operational rail coverage.
- Historical Berlin artifacts and quality findings remain unchanged and clearly labelled.
- No Rhine–Ruhr metric or Weather × Railway result is claimed yet.

### Next gate

Collect at least one non-empty plan artifact for each selected city, define the observation window
and join tolerances, then ingest the four DWD profiles before calculating descriptive results.

### Sprint 6 continuation: regional evidence

- Stored one non-empty 19:00 German-local DB plan slice for each city: 58 raw stops for
  Düsseldorf, 59 for Duisburg, 39 for Essen, and 65 for Köln.
- Stored four DWD archives with 13,200 hourly source rows each.
- Used `data/rhine_ruhr/` to prevent historical Berlin rows from entering the regional database.
- Added station scope to artifact imports so identical response bytes from different stations do
  not collide and quality checks select the intended city.
- Normalized 105,600 weather observations and 353 planned railway events.
- Added a deterministic city-hour CSV export that retains unmatched hours and null values.
- The export has 52,807 city-hour rows and zero paired hours. DWD ends at
  `2026-09-13T23:00:00+00:00`; the DB plan slice begins on 2026-09-14.
- No relationship or operational-performance claim is made from this non-overlapping snapshot.

### Sprint 6 compatibility fix: direct quality runs

- A reported quality run against the earlier SQLite file failed because station scoping had been
  added after that file was created.
- Quality assessment now prepares and migrates storage before querying `scope_key`; users do not
  need to replay or delete existing data.
- The base configuration now points to the active Rhine–Ruhr database so its default Essen city
  and default data are consistent. The historical Berlin database remains opt-in.
- The migration uses one atomic parent-table replacement, checks foreign-key integrity, and always
  restores foreign-key enforcement.
- A regression test covers the exact quality-on-old-database path. The full offline suite passes
  36 tests.

### Sprint 6 DB full-change slice

- Added a small `--db-feed changes` option for DB `GET /fchg/{eva}` requests; plan behavior remains
  the default.
- Preserved four live full-change XML snapshots: 2,599 raw stop updates and 3,564 normalized
  arrival/departure event updates.
- Reconciled plan and change snapshots by station, DB stop ID, and event type. The plan slice has
  331 matched events; extra changes without a saved plan are excluded from delay metrics.
- Fixed the city-hour query so each stable plan event survives later hourly imports and full-change
  imports. It no longer assumes that the newest station import replaces every earlier plan hour.
- Added matched-change, cancellation, positive-delay, mean-delay, and maximum-delay fields to the
  export. These remain descriptive fields, not production KPIs.
- The four DB change timestamp checks found 78 updates without a usable time. The results are kept
  as failures rather than hidden.
- Rechecked the four official DWD archives; all still end at `2026-09-13T23:00:00+00:00`, so paired
  analysis remains blocked.
- Added four focused regression tests. The full offline suite now passes 40 tests.

### Professional audit remediation

- Reconnected live DWD and DB adapters to the source-independent ingestion pipeline; the CLI no
  longer bypasses the architectural contract.
- Separated DB plan and full-change streams in artifact identity, dataset configuration,
  normalization, and quality selection. Existing local imports migrated without row loss.
- Added generic scope and normalizer registration hooks so a new source is not rejected by the
  catalog or silently treated as railway data.
- Added enforced dataset, entity, and import foreign keys to canonical observations and events;
  the Rhine–Ruhr database passes integrity and foreign-key checks after migration.
- Made failed raw response publication remove both content and metadata instead of leaving a
  partial pair.
- Added a credential-free 2.1 MB evidence bundle and offline rebuild command. The clean rebuild
  reproduces 105,600 weather observations, 3,917 railway events, and 52,807 city-hour rows.
- Added an MIT license and CI checks for Python 3.11–3.13, Ruff, the unit suite, and the evidence
  rebuild. The expanded offline suite passes 46 tests.

### GitHub live-collection verification

- Added the two DB credential names to GitHub Secrets and a manual live-collection workflow input.
- The first live run exposed a rule error: DB full changes can contain platform, route, or message
  updates without a changed time. These are valid source records, not malformed timestamps.
- Added `allow_missing` only to the DB change-feed timestamp rule. Supplied timestamps must still
  parse with a timezone; DB plan and DWD timestamps remain required.
- Added a regression test and expanded the offline suite to 55 passing tests.
- Verified a complete GitHub run: live DWD/DB collection, quality assessment, cached state, raw
  evidence upload, dashboard build, and Pages deployment all passed.
- That run produced 52,810 dashboard rows, eight rule-based signals, and eight newly opened local
  incidents. The live dashboard still reports zero paired city-hours because the source windows
  do not overlap. These are run results, not production KPIs.
