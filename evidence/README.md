# Reproducible Rhine–Ruhr evidence

This directory contains the credential-free public-source snapshots used for the Sprint 6
measurements. Each raw response has a JSON sidecar containing its source URL, retrieval time,
byte count, and SHA-256 checksum. No API credential or request header is stored.

The files are retained as source evidence under the publishers' documented CC BY 4.0 terms. See
[`docs/SOURCES.md`](../docs/SOURCES.md) for source links and attribution.

Rebuild the SQLite database and city-hour export without making a network request:

```bash
PYTHONPATH=src python3.13 scripts/rebuild_evidence.py
```

The command refuses to overwrite an existing rebuild. Its default output is
`build/evidence-rebuild/`, which is ignored by Git. The expected snapshot contains 105,600
canonical weather observations, 3,917 canonical railway events, and 52,807 city-hour rows.

The snapshot is evidence of one retrieval, not a promise that rolling upstream APIs will return
identical bytes later. New live claims require a new preserved snapshot and updated documentation.
