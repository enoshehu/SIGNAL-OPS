# Architecture audit: keep the proof, remove the platform theatre

## The project in easy terms

SIGNAL//OPS collects weather and railway files, keeps the originals, translates them into one
small database, checks whether they are trustworthy, and publishes an honest dashboard. When a
simple rule finds a problem, it records a signal and opens a local incident. Excel, Power BI,
Jira, Confluence, and Miro are presentation and collaboration tools around that core; none should
be required for the pipeline to work.

The simplest accurate architecture is:

```text
DWD + Deutsche Bahn
        ↓
preserved raw files
        ↓
one Python package + SQLite
        ↓
quality rules + four operational signals
        ↓
CSV/JSON → GitHub Pages, Excel, Power BI
        ↓
optional Jira, Confluence, and Miro evidence
```

That is enough architecture for a strong student project.

## Main criticism

The long-term vision is attractive, but it combines a case study, a generic data platform, an
incident-management product, and a portfolio of enterprise tools. Building all four at once would
hide the useful engineering under integration work. Calling the first release a universal
platform would also be too strong: two implemented adapters demonstrate a reusable pattern, not
universal compatibility.

The project should be judged by whether a reviewer can run it, inspect the evidence, understand a
failure, and reproduce a published number. It should not be judged by the number of products in
the diagram.

## Keep in version 1.0

- DWD weather and Deutsche Bahn plan/change ingestion for four Rhine–Ruhr cities.
- Immutable raw evidence, checksums, replay, and one SQLite database.
- A small canonical model for observations and service events.
- Explicit quality results; no unexplained score.
- Exactly four signals: stale source, schema change, delay over 20 minutes, and cancellation.
- A duplicate-safe local incident lifecycle.
- A static GitHub Pages dashboard built from versioned JSON.
- One Excel review queue and one Power BI report contract.
- Small Jira, Confluence, and Miro artifacts that document delivery and one controlled incident.
- GitHub Actions for tests, packaging, evidence rebuilding, scheduled collection, and Pages.

## Remove from version 1.0

- Energy, air quality, statistics, and additional cities.
- A hosted Python API; GitHub Pages cannot run it.
- PostgreSQL, a warehouse, event streaming, microservices, Airflow, or Kubernetes.
- Machine learning, forecasting, and automatic anomaly detection.
- A numeric trust score without validated weights.
- A no-code or configuration-only promise for arbitrary new sources.
- Two-way synchronization with Excel, Jira, Confluence, Miro, or Power BI.
- Production real-time, high-availability, and indefinite-retention claims.

## External tools have bounded jobs

| Tool | Version 1.0 job | Runtime dependency? |
|---|---|---|
| GitHub | Source, review, CI, scheduled demo, release evidence | Yes |
| GitHub Pages | Public static dashboard | Yes |
| Excel | Human review queue | No |
| Power BI | Portfolio report over published CSV | No |
| Jira | Delivery backlog and one incident example | No |
| Confluence | Architecture and incident decision record | No |
| Miro | Four-frame visual explanation | No |

This boundary prevents five external services from becoming five failure points in the data
pipeline.

## Feasibility and honest limitations

| Requirement | Feasible? | Constraint |
|---|---|---|
| Tests and static dashboard on GitHub | Yes | Already represented by workflows in the repository |
| Scheduled collection | Yes, as a demo | Requires DB secrets; Actions cache is convenient state, not a durable database |
| Weather × Railway analysis | Yes | A real overlapping window must accumulate before publishing a relationship |
| Excel queue | Yes | Version 1.0 is export-only |
| Power BI report | Yes | `.pbix` creation needs Power BI Desktop or Service access |
| Jira/Confluence/Miro evidence | Yes | Creation needs the owner's authenticated workspace and chosen destination |
| Universal arbitrary-source onboarding | Not honestly in 1.0 | Every genuinely different source still needs code and tests |

The scheduled workflow retains each run's raw evidence as a 30-day artifact and restores SQLite
from an Actions cache. This is suitable for a student demonstration. A later reliability release
should move retained state to durable object storage or a managed database if the project needs
production-like guarantees.

## Version plan

- **1.0 — Weather × Railway proof:** finish a real overlap window, publish Pages, and create the
  bounded external artifacts.
- **1.1 — Reliability:** durable retention, recovery testing, accessibility, and correction import.
- **2.0 — Energy:** add SMARD as the third adapter and measure actual reuse.
- **2.1 — Air quality:** add UBA data and a second city-level mission.
- **3.0 — Multi-domain operations:** add Destatis, actions, decisions, operational KPIs, mature
  source health, and only then consider combined mission control or a hosted API.

## Definition of a good student submission

A clean checkout passes its tests, rebuilds the committed evidence, produces the same dashboard
inputs, and explains why zero paired hours currently means “wait for evidence,” not “invent a
result.” The presenter can trace one dashboard value to SQLite and raw source data, then walk one
controlled failure from a quality rule to a resolved incident. That is smaller than the original
platform story, but much more credible.
