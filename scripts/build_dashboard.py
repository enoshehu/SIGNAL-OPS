"""Rebuild the static dashboard payload from an existing SIGNAL//OPS database."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from signalops.analysis import hourly_summary
from signalops.publish import database_publish_context, write_dashboard_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("site/data/summary.json"))
    args = parser.parse_args()
    rows = hourly_summary(args.database)
    context = database_publish_context(args.database)
    write_dashboard_json(
        rows,
        args.output,
        provenance={"dataDatabaseUpdatedAt": context["dataDatabaseUpdatedAt"]},
        quality_results=context["qualityResults"],
    )
    print(f"dashboard rows: {len(rows)}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, sqlite3.Error) as error:
        print(f"Dashboard build failed: {error}")
        raise SystemExit(2) from error
