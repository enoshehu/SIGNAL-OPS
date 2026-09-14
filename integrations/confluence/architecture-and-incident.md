# SIGNAL//OPS version 1.0

## Purpose

SIGNAL//OPS investigates observable relationships between weather and railway operations for four
Rhine–Ruhr cities. It preserves source evidence, reports quality limitations, and does not claim
that weather caused a railway outcome.

## Architecture

```text
DWD ZIP + DB XML
       ↓
preserved raw evidence
       ↓
parsed records in SQLite
       ↓
weather observations + railway events
       ↓
quality rules + operational signals
       ↓
city-hour export
       ↓
GitHub Pages + Power BI + Excel review queue
```

The repository owns technical definitions and reproducible evidence. This page is the concise
stakeholder view and links to the relevant repository version rather than duplicating it.

## Controlled incident record

**Title:** DWD schema change detected  
**Signal:** `SCHEMA_CHANGED`  
**Severity:** High  
**Expected exercise:** a fixture removes or renames a required parsed field. The quality run fails,
an incident is opened, the changed fields and failed run are attached, and the adapter or accepted
schema is updated. A successful replay provides closure evidence.

### Decision

Do not silently accept a removed field or type change as the new baseline. Preserve the failed
artifact, investigate the publisher contract, update code and tests when justified, and close the
incident only after a successful replay.

### External fields to complete

- Repository release URL:
- GitHub Actions run URL:
- Jira incident URL:
- Owner:
- Resolution date:
- Confluence PDF export:
