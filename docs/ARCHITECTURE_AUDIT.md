# Architecture and scope

## System overview

```text
DWD ZIP files                  DB timetable XML
      │                               │
      └──────── source adapters ──────┘
                       │
              raw files + metadata
                       │
              parsed source records
                       │
                     SQLite
           ┌───────────┼───────────┐
      quality rules   analysis   signals/incidents
           └───────────┼───────────┘
                  CSV and JSON
                       │
              GitHub Pages / exports
```

The application is one Python package backed by SQLite. It does not require a web framework,
message broker, warehouse, or separate API for the current workload.

## Main components

| Component | Responsibility |
|---|---|
| `adapters/` | Download and parse DWD and DB source formats |
| `storage.py` | Preserve imports and parsed records with replay identity |
| `universal.py` | Create canonical weather observations and railway events |
| `quality.py` | Run configured checks and store their evidence |
| `analysis.py` | Match plan/change events and build city-hour rows |
| `operations.py` | Create four rule-based signals and local incidents |
| `publish.py` | Convert analysis rows into static dashboard data |

## Data boundaries

- Raw source files are never overwritten.
- Every import stores source, stream, station scope, retrieval time, path, checksum, and row count.
- Canonical rows retain their import ID and source payload.
- DWD and DB use separate normalizers because their records have different meanings.
- Weather and railway data join only by configured city and exact UTC hour.
- Missing source data remains null; it is not treated as zero.

## Quality and operations

Quality checks report `pass`, `warning`, or `failure` with row counts and affected identifiers.
There is no composite trust score. The current signal types are:

- `DELAY_OVER_20_MINUTES`
- `CANCELLATION_DETECTED`
- `SOURCE_DATA_STALE`
- `SCHEMA_CHANGED`

Signals have stable IDs. The database permits only one open incident per signal, while resolved
incidents remain in history.

## Web delivery

GitHub Pages serves static HTML, CSS, JavaScript, and generated JSON. A single workflow handles
both deployment modes:

- Push or manual run: rebuild the checked-in evidence and publish it.
- Schedule: collect a new source slice using GitHub Secrets, run quality checks, and publish only
  when no rule returns `failure`.

The scheduled SQLite file uses Actions cache storage and raw responses are retained as workflow
artifacts for 30 days. This is suitable for the project demonstration, not durable production
storage.

## Scope decisions

The first release uses four Rhine–Ruhr cities and two providers. It demonstrates a reusable
pattern, but each additional provider still needs its own adapter, mapping, rules, and tests.

Deferred until later releases:

- SMARD, UBA, and Destatis adapters
- durable hosted storage
- a server-side query API
- machine-learning anomaly detection
- multi-user incident management
- automatic two-way synchronization with external tools

These items remain part of the unchanged long-term [project vision](PROJECT_VISION.md) and are
scheduled in the [roadmap](ROADMAP.md).
