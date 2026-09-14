# Controlled source-failure drill

- Detection: **PASS** — DWD response is not a valid ZIP archive
- Containment: **PASS** — the corrupt response remained preserved but was not imported.
- Recovery: **PASS** — verified replacement parsed and inserted 1 record.
- Credential exposure: **NONE** — the drill is offline and uses no secrets.

Recovery procedure: retain the failed response, verify the source contract, replay a valid replacement, run quality checks, then close the incident with evidence.
