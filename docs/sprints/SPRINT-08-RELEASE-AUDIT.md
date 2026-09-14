# Sprint 8 — release audit

**Status:** Active

**Started:** 2026-09-14

**Goal:** Make every dashboard value traceable to the database used to publish it, then prepare the
version 1 release after genuine Weather × Railway overlap exists.

## Delivered

- [x] Rebuild the checked-in dashboard from committed raw evidence.
- [x] Compare every dashboard field except `generatedAt` with values derived from its database.
- [x] Fail clearly when the requested audit database is missing.
- [x] Run the committed-evidence comparison in CI.
- [x] Run the rolling-data comparison before a live dashboard is published.
- [x] Keep the versioned evidence and rolling live data as two clearly separated modes.

## Current evidence

- The committed evidence rebuild contains 105,600 weather observations and 3,917 railway events.
- It produces 52,807 city-hour rows, 353 planned events, and 331 matched updates.
- A credentialed GitHub run collected all configured DWD and DB feeds, saved the rolling database
  in the `live-data` release, and deployed GitHub Pages successfully.
- The live dashboard still reports zero paired hours because DWD ends at 13 September 23:00 UTC.

These are observed run counts, not production targets or service metrics.

## Completion gate

- [ ] Sprint 7 captures at least one genuine paired hour for every city.
- [ ] Review the generated comparison, sample sizes, and limitations.
- [ ] Replace the README screenshot with the final evidence state.
- [ ] Run the full release checklist from a clean checkout.
- [ ] Tag `v1.0.0` and publish the reviewed release notes.
