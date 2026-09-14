# Operational runbooks

These procedures apply to the rolling GitHub Actions pipeline and to local `signalops sync` runs.
Never paste credentials, request headers, or `.env` contents into logs or issues.

## Source download failure

1. Identify the failing dataset, city, endpoint status and UTC run time from the compact sync output.
2. Check the official provider status and source contract. Do not repeatedly force a rate-limited API.
3. Preserve any successfully downloaded raw responses; the synchronizer isolates other targets.
4. Retry with the normal schedule. Use `--force` only after confirming the provider is healthy.
5. Verify `collection_runs`, the raw checksum sidecar and `PRAGMA foreign_key_check` before closing.

## Missing or rejected DB credentials

1. Confirm the GitHub repository has `DB_API_CLIENT_ID` and `DB_API_KEY` Actions secrets.
2. Confirm the workflow passes them only through its step environment.
3. Rotate a credential if it appeared in any output; redaction is not a substitute for rotation.
4. Manually dispatch the workflow with live collection enabled and confirm all eight DB targets pass.

## Schema or parser failure

1. Retain the exact raw artifact and checksum that failed.
2. Compare the provider's current documented schema with the parsed-payload schema snapshot.
3. Add a failing fixture test that contains the new contract before changing the adapter.
4. Update the adapter and mapping, replay the retained artifact, and run the complete offline suite.
5. Record added, removed and changed fields plus the recovery commit in the incident resolution.

## Replay and database recovery

1. Download the current `live-data` release asset and keep a recovery copy.
2. Verify the archive and SQLite database before changing anything.
3. Replay only raw files with matching metadata sidecars and SHA-256 checksums.
4. Normalize, run quality, regenerate the profile/dashboard and check foreign keys.
5. Replace the release asset only after the full run succeeds; never publish a partial database.

## No weather–rail overlap

1. Compare the maximum DWD observation time with the minimum DB planned time in UTC.
2. Remember that DWD recent climate files normally end at yesterday and update daily.
3. Continue collecting DB plans and changes; do not fabricate, interpolate or relabel future weather.
4. When overlap arrives, rebuild the paired profile and preserve an immutable evidence snapshot.

## Controlled recovery exercise

Run `PYTHONPATH=src python scripts/failure_drill.py`. It injects an invalid ZIP offline, verifies that
parsing fails before database import, then replays a valid checksummed replacement. The generated
report is stored in `docs/analysis/CONTROLLED_FAILURE_DRILL.md`.
