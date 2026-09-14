"""Compatibility wrapper for the incremental SIGNAL//OPS synchronizer."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from signalops.sync import synchronize


def main() -> int:
    summary = synchronize(Path("config/base.toml"), env_file=Path(".env"))
    for item in summary.items:
        print(f"{item.status}: {item.label} — {item.detail}")
    print(f"analysis rows: {summary.analysis_rows}")
    print(f"paired city-hours: {summary.paired_hours}")
    return 2 if summary.operational_failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, sqlite3.Error) as error:
        print(f"Live collection failed: {error}")
        raise SystemExit(2) from error
