# SIGNAL//OPS

SIGNAL//OPS is a reusable real-world DataOps platform: it ingests independent public feeds,
preserves their evidence, tests whether they can be trusted, and turns time-aligned observations
into operational signals. Its first live mission combines DWD weather with Deutsche Bahn timetable
updates for Duisburg, Essen, Düsseldorf, and Köln.

[**Live dashboard**](https://enoshehu.github.io/SIGNAL-OPS/) ·
[Data profile](docs/analysis/RHINE_RUHR_DATA_PROFILE.md) ·
[Architecture](docs/ARCHITECTURE_AUDIT.md) ·
[Roadmap](docs/ROADMAP.md)

[![Verify](https://github.com/enoshehu/SIGNAL-OPS/actions/workflows/ci.yml/badge.svg)](https://github.com/enoshehu/SIGNAL-OPS/actions/workflows/ci.yml)
[![Publish dashboard](https://github.com/enoshehu/SIGNAL-OPS/actions/workflows/pages.yml/badge.svg)](https://github.com/enoshehu/SIGNAL-OPS/actions/workflows/pages.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)

## What it does

- Downloads DWD ZIP archives and DB timetable XML without storing credentials in Git.
- Keeps source files, retrieval metadata, and SHA-256 checksums for replay.
- Normalizes weather observations and railway events into a small SQLite model.
- Checks timestamps, missing values, duplicates, freshness, continuity, and schema changes.
- Matches DB plans with change events to calculate observed delays and cancellations.
- Builds CSV and JSON dashboard outputs, with an Excel review workbook for handoff.

## Live mission: when the sky strains the railway

The current mission asks whether rain, wind, heat, or other weather conditions coincide with more
delays and cancellations at the four monitored stations. A weather observation and railway events
become comparable only when their configured city and exact UTC hour match.

The live evidence goal is at least 168 paired city-hours, with at least 24 hours in every city,
72 hours of temporal span, 50% expected city-hour coverage, healthy sources, and at least 80% DB
event matching in every city. Until every gate passes, overlap is shown as evidence in progress—not
as a weather-effect conclusion. Even after readiness, the result describes association and does not
claim that weather caused a specific disruption.

## Current snapshot

| Data | Result |
|---|---:|
| Weather observations | 105,600 |
| Planned railway events | 353 |
| Plans matched with updates | 331 |
| Cities | 4 |
| Automated tests | 86 |

The saved weather window ends on 13 September 2026 and the railway window begins on 14 September
2026. There are no paired city-hours yet, so the project does not calculate a weather–railway
relationship. The railway results describe one collected slice and are not performance ratings.
The rolling GitHub Pages database grows independently and can contain newer paired observations.

## Architecture

```text
DWD + Deutsche Bahn
        ↓
raw files + checksums
        ↓
adapters → SQLite → quality rules
        ↓
city-hour analysis → CSV / JSON
        ↓
GitHub Pages + review exports
```

The implementation uses Python's standard library and SQLite. DWD and DB remain source-specific
at the adapter boundary; the storage, quality, analysis, and publishing layers share common
interfaces.

## Run locally

Requires Python 3.11 or newer.

```bash
git clone https://github.com/enoshehu/SIGNAL-OPS.git
cd SIGNAL-OPS
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m unittest discover -s tests -v
```

Rebuild the committed evidence and open the dashboard:

```bash
python scripts/rebuild_evidence.py
python scripts/build_dashboard.py --database build/evidence-rebuild/signalops.sqlite
python -m http.server 8000 --directory site
```

Then open `http://localhost:8000`.

Live DB collection requires `DB_API_CLIENT_ID` and `DB_API_KEY`. Copy `.env.example` to `.env`,
add the credentials locally, and never commit that file. Environment variables override TOML
configuration.

Download every due feed for all four cities and rebuild the analytical outputs with one command:

```bash
signalops sync
```

The synchronizer reads secrets from `.env` without executing it, prevents concurrent runs, keeps
each raw response and checksum, and isolates failures by city and feed. It enforces the configured
180-day analytical window and 30-day raw-artifact window; future timetable rows remain available
for live operation. Refresh intervals live in `config/datasets/`: DB changes every
15 minutes, DB plans hourly, live DWD observations hourly, temperature and humidity every six
hours, and CDC rain/wind/gust archives daily. Use
`signalops sync --dry-run` to inspect what is due or `signalops sync --force` for a complete manual
refresh.

Load the official DWD history immediately with `signalops backfill-weather --days 180`. DWD's
rolling archives cover the complete period. DB does not publish an equivalent archive of historical
actual arrivals and departures through the Timetables API, so rail history starts when this collector
begins running and grows forward to 180 days.

GitHub Actions checks due feeds every 15 minutes and publishes the latest bounded database and raw
files as the replaceable `live-data` release asset. Public DWD collection runs without secrets;
the configured hourly and daily dataset intervals prevent redundant downloads. Configure
`DB_API_CLIENT_ID` and `DB_API_KEY` as repository Actions secrets to add timetable collection. If
they are absent, the workflow still refreshes DWD data. This avoids committing a frequently
changing SQLite binary or retaining old database versions in Git history. The dashboard deployment
and rolling data update share one serialized workflow. The current archive is available from the
[`live-data` release](https://github.com/enoshehu/SIGNAL-OPS/releases/tag/live-data) after the first
successful scheduled run.

## Useful commands

```bash
signalops status
signalops sync
signalops backfill-weather --days 180
signalops ingest --source dwd --city essen
signalops ingest --source db --city essen --db-feed plan
signalops normalize --dataset dwd_weather
signalops quality --dataset dwd_weather --city essen
signalops analyze
signalops operate
```

## Repository guide

| Path | Contents |
|---|---|
| `src/signalops/` | ingestion, storage, quality, analysis, and operations code |
| `tests/` | offline unit and integration-style tests |
| `config/` | non-secret source and dataset configuration |
| `evidence/` | public source snapshots used for reproducible results |
| `site/` | static GitHub Pages dashboard |
| `docs/` | methods, source contracts, decisions, and roadmap |
| `integrations/` | optional Jira, Confluence, Miro, and Power BI handoff files |

## Project status

Version `0.5.0` is a working pre-release. The immediate release gate is an overlapping DWD/DB
window, followed by the final accessibility, security, and claim-to-evidence review. The complete
long-term requirements remain in [PROJECT_VISION.md](docs/PROJECT_VISION.md), which is preserved as
the original project brief.

Data sources and licences: [SOURCES.md](docs/SOURCES.md).
Canonical fields: [DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md).
Reproduction notes: [evidence/README.md](evidence/README.md).
Operational recovery: [RUNBOOKS.md](docs/RUNBOOKS.md).
Architecture and lineage: [LINEAGE.md](docs/LINEAGE.md).
Five-minute walkthrough: [DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md).
