# Sprint 5 — Data quality and schema drift

**Status:** Complete for the available DWD data; DB live evidence remains blocked  
**Date:** 2026-09-14

## Goal

Add small, explainable checks that say what was tested, how many rows failed, and which records
were affected. Do not hide the evidence behind a made-up percentage.

## Delivered

- [x] Configuration-driven quality rules for DWD weather observations.
- [x] Checks for timestamp validity, humidity range, missing measurements, canonical-key
  uniqueness, entity integrity, hourly continuity, and observation freshness.
- [x] Pass, warning, and failure states with checked and failed counts.
- [x] Immutable quality-run and rule-result records in SQLite.
- [x] Affected item identifiers for record-level investigation.
- [x] Parsed-payload schema fingerprints and baseline comparison.
- [x] Schema additions reported as warnings; removals or type changes reported as failures.
- [x] A `signalops quality --dataset ...` command.
- [x] Tests for missing and invalid values, time gaps, stable schemas, added fields, and unknown
  configured rules.
- [x] Berlin-local DB timetable conversion to UTC, including winter and summer tests.
- [x] Explicit decision not to publish a numeric trust score without a justified formula.

## Rule semantics

| Rule | Meaning | Null handling |
|---|---|---|
| `valid_timestamp` | Timestamp must parse and include a timezone | Invalid or absent fails |
| `humidity_range` | Non-null relative humidity must be from 0 through 100 percent | Checked separately |
| `value_present` | Canonical measurement value must be present | Null produces a warning |
| `unique_observation` | Entity, timestamp, and metric must be unique inside one import | Not applicable |
| `entity_integrity` | Canonical row must refer to a registered entity | Not applicable |
| `hourly_continuity` | Unique weather timestamps must have no internal hourly gap | Not applicable |
| `freshness` | Latest observation must be no older than the configured 1,440 minutes | No valid time fails |
| `schema_drift` | Parsed field structure is compared with the first stored baseline | Values are never stored |

Each assessment uses only the latest artifact import. This avoids confusing retained historical
versions with duplicates.

## Observed DWD result

The saved Berlin-Tempelhof import contains 26,400 canonical observations at 13,200 hourly
timestamps: one temperature and one humidity row per timestamp.

| Rule | Result | Evidence |
|---|---|---:|
| Timestamp validity | Pass | 0 of 26,400 failed |
| Humidity range | Pass | 0 of 13,200 failed |
| Value presence | Warning | 73 of 26,400 were null |
| Canonical-key uniqueness | Pass | 0 of 26,400 failed |
| Entity integrity | Pass | 0 of 26,400 failed |
| Hourly continuity | Pass | 0 missing hours inside 13,200 timestamps |
| Observation freshness | Pass at execution time | 1,440-minute configured boundary |
| Parsed schema | Pass | First five-field baseline stored |

The 73 null values comprise 36 temperature values and 37 humidity values. This is an observed
property of one local source artifact, not a production KPI. DWD source quality codes are
preserved but not interpreted here because their meaning has not yet been documented from the
publisher's code table.

## Verification

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3.13 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3.13 -m signalops quality \
  --dataset dwd_weather --config config/base.toml
```

The complete offline suite passed 27 tests. The live-artifact quality run stored eight rule
results and 73 affected record identifiers.

## Boundaries

- Schema drift currently describes the parsed JSON payload. A DWD header change rejected by the
  parser, or a structural change inside DB XML, needs a source-contract check in a later sprint.
- No live DB quality result is claimed because DB Marketplace credentials and a real XML artifact
  are not available.
- Freshness is evaluated when the command runs and may change naturally over time.
- A numeric trust score is deliberately absent. Individual facts are easier to explain and audit.

## Sprint 6 backlog

- [ ] Obtain or import a permitted real DB timetable artifact.
- [ ] Confirm DB timestamp semantics against the live contract.
- [ ] Define the location and time matching rule before joining sources.
- [ ] Choose an analysis window covered by both real datasets.
- [ ] Produce only descriptive Weather × Railway outputs supported by retrieved data.
- [ ] Carry Sprint 5 warnings and source limitations into every analytical output.
