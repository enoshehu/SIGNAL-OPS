# Sprint 9 — 180-day historical window

Date: 2026-09-15

## Outcome

SIGNAL//OPS now keeps a rolling 180-day analytical database while limiting replayable raw files to
30 days. A fresh installation can seed the weather side from DWD's official recent archives, and
the scheduled GitHub workflow continues both weather and railway collection.

## Verified local backfill

The command below completed without operational or quality failures:

```text
signalops backfill-weather --days 180
```

- Scope: Düsseldorf, Duisburg, Essen, and Köln.
- Metrics: air temperature, relative humidity, precipitation, wind speed, wind direction, and wind
  gust.
- Expected groups: 24; observed groups: 24.
- First covered hour: `2026-03-18T23:00:00+00:00`.
- Latest archive hour: `2026-09-13T23:00:00+00:00`.
- Complete series: 4,297 distinct hours. Essen wind and gust and the Köln and Düsseldorf gust
  series contain documented source gaps; no interpolation was applied.
- Local database: 105,706 weather observations, 10,198 railway service-event states, and no
  foreign-key violations. Database size at verification was 89,997,312 bytes.

The generated local coverage report is
`data/rhine_ruhr/processed/historical_coverage.json`. The runtime data directory is intentionally
excluded from Git because the workflow stores its rolling database in a GitHub release asset.

## Automation behavior

Every scheduled run restores the previous `live-data` release, downloads due public DWD products,
collects DB plans and changes when credentials are configured, applies retention, rebuilds the
dashboard, and replaces the release asset only after validation succeeds.

The workflow can bootstrap weather history without a prior release because each DWD recent archive
contains more than the required window. Rail data has a different boundary: the official DB
Timetables interface is a live operational feed and does not provide an equivalent historical
actuals archive. SIGNAL//OPS therefore starts railway history at first collection and accumulates
it forward for up to 180 days.

## Trust boundary

Missing source hours remain missing. Historical railway delays are not inferred from plans and are
not sourced from unofficial scraped datasets. Weather/rail conclusions stay disabled until the
database contains real observations from the same city and hour.
