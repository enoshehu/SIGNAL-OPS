"""Run repository-level security, licence and claim consistency checks."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
from pathlib import Path

from signalops.catalog import load_catalog


def tracked_files(root: Path) -> tuple[Path, ...]:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True)
    return tuple(root / item.decode() for item in result.stdout.split(b"\0") if item)


def check_repository(root: Path, database: Path | None = None) -> list[str]:
    errors: list[str] = []
    if not (root / "LICENSE").is_file():
        errors.append("LICENSE is missing")
    catalog = load_catalog(root / "config" / "datasets")
    for key, definition in catalog.items():
        if not definition.source.get("license"):
            errors.append(f"{key} has no source licence")
        if not str(definition.source.get("url", "")).startswith("https://"):
            errors.append(f"{key} has no HTTPS source URL")

    credential_assignment = re.compile(r"DB_API_(?:CLIENT_ID|KEY)\s*=\s*[\"']?([A-Za-z0-9_-]{12,})")
    for path in tracked_files(root):
        if not path.is_file() or path.suffix.lower() in {".zip", ".xlsx", ".png", ".sqlite"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if path.name != ".env.example" and credential_assignment.search(text):
            errors.append(f"credential assignment found in tracked file: {path.relative_to(root)}")

    dashboard_path = root / "site" / "data" / "summary.json"
    if dashboard_path.exists():
        payload = json.loads(dashboard_path.read_text(encoding="utf-8"))
        if int(payload["pairedHours"]) == 0 and "do not" not in str(payload["notice"]).lower():
            errors.append("zero-overlap dashboard does not disclose the claim limitation")

    if database and database.exists():
        with sqlite3.connect(database) as connection:
            violations = connection.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                errors.append(f"database has {len(violations)} foreign-key violations")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--database", type=Path)
    args = parser.parse_args()
    errors = check_repository(args.root.resolve(), args.database)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("Release checks passed: security, licences, claims, and database integrity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
