# Architecture and data lineage

```mermaid
flowchart LR
  DWD[DWD climate products\ntemperature · humidity · rain · wind]
  DB[DB Timetables\nplans · full changes]
  DWD --> RAW[Raw bytes + metadata + SHA-256]
  DB --> RAW
  RAW --> PARSED[Source-shaped parsed records]
  PARSED --> RETAIN[Seven-day retention boundary]
  RETAIN --> CANON[Canonical observations + service events]
  CANON --> DQ[Quality results + schema snapshots]
  CANON --> JOIN[City + exact UTC-hour analysis]
  DQ --> SIGNAL[Signals + duplicate-safe incidents]
  JOIN --> PROFILE[Paired-window profile]
  JOIN --> PAGE[Static dashboard JSON]
  PROFILE --> RELEASE[GitHub live-data release asset]
  PAGE --> PAGES[GitHub Pages]
```

Every canonical row carries an import identifier. Every import records the source, dataset stream,
station scope, retrieval time, raw path, checksum and record count. Missing weather or railway data
remains missing; it is never converted to zero. The immutable `evidence/` bundle is separate from
the rolling operational database and is not removed by retention.
