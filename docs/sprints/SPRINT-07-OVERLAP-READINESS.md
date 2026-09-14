# Sprint 7 — Overlap readiness

**Status:** Active

**Started:** 2026-09-14

**Goal:** Retain DB activity until DWD publishes the same UTC hours, then verify one genuine
paired hour for every city.

## Delivered

- [x] Rolling seven-day live database and raw-file retention.
- [x] Feed-specific collection clocks: DB changes every 15 minutes, DB plans hourly,
  temperature/humidity every six hours, and rain/wind daily.
- [x] UTC city-hour joining that keeps unmatched hours visible.
- [x] Generated paired-window profile with missingness and sample sizes.
- [x] Retrieval-time snapshot selection, independent of replay order.
- [x] Preserve the last known changed time when a later DB update changes only another field.
- [x] Stop publication when a high-severity quality rule fails.
- [x] Offline regression tests for these rules.

## Current evidence

- Retained DB plans cover 14 September 2026 for all four cities.
- The four DWD temperature archives currently end at `2026-09-13T23:00:00+00:00`.
- The dashboard therefore reports zero paired city-hours and makes no weather-effect claim.

## Completion gate

- [ ] DWD advances to cover the retained DB window for all four cities.
- [ ] The generated profile reports at least one paired city-hour per city.
- [ ] The overlapping raw files are preserved as release evidence.
- [ ] Dashboard numbers and descriptive comparisons are reviewed before the v1 tag.

The pipeline polls for the source update. No retrospective DB availability is assumed.
