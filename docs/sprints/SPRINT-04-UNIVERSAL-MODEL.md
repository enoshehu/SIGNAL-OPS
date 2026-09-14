# Sprint 4 — Universal model

**Status:** Complete; DB live verification was added during Sprint 6
**Date:** 2026-09-14

## Delivered

- [x] Declarative TOML definitions for DWD and DB datasets.
- [x] Validated dataset catalog loader.
- [x] Universal source, dataset, entity, observation and service-event tables.
- [x] DWD timestamp conversion to timezone-aware UTC.
- [x] Separate temperature and humidity observations with explicit units.
- [x] DB arrival/departure normalization from fixture-tested XML.
- [x] Idempotent canonical row identifiers.
- [x] `signalops normalize --dataset ...` command.
- [x] Catalog and normalization tests.

## Observed verification

The full suite passed 21 tests. Normalizing the verified DWD artifact created 26,400 observations:
13,200 air-temperature records and 13,200 relative-humidity records. Both cover
`2025-03-13T00:00:00+00:00` through `2026-09-13T23:00:00+00:00`.

These are local row counts and source coverage, not quality or performance scores.

## Boundary

Quality and operational workflows were added in later sprints. Sprint 6 verified the railway model
with preserved DB plan and change responses.
