"""Generate the descriptive paired-window profile from a SIGNAL//OPS database."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from signalops.profile import write_profile


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path("docs/analysis/PAIRED_WINDOW_PROFILE.md")
    )
    args = parser.parse_args()
    write_profile(args.database, args.output)
    print(f"profile: {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, sqlite3.Error) as error:
        print(f"Profile generation failed: {error}")
        raise SystemExit(2) from error
