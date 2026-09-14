# Security, licence and release review

## Security

- Credentials live only in local `.env` or encrypted GitHub Actions secrets.
- `.env` is ignored by Git and locally restricted to the owner.
- The loader treats `.env` values literally and never evaluates shell syntax.
- Source URLs use HTTPS; DB credentials are sent only in required request headers.
- Workflow permissions are explicit and failure issues are duplicate-safe.
- Raw publication is atomic and checksum-verified before parsing.
- SQLite foreign keys are enabled and checked after retention and evidence rebuild.
- The rolling database is replaced only after a successful workflow.

## Licences

- Project code: MIT.
- DWD products: CC BY 4.0 with provider and product URLs recorded in the catalog.
- Deutsche Bahn Timetables: CC BY 4.0 with provider and endpoint recorded in the catalog.
- Source attribution and limitations are documented in `docs/SOURCES.md`.

## Claims

- Dashboard counts come from generated canonical rows.
- Missing sources remain null and visible.
- Delay metrics use matched plan/change events only.
- Weather comparisons expose paired-hour and matched-event denominators.
- No causal wording is generated.
- Zero overlap remains an explicit pending result, not a hidden failure.

Run `PYTHONPATH=src python scripts/release_check.py --database data/rhine_ruhr/signalops.sqlite`
before a release. CI runs the repository portion on Python 3.11–3.13.
