"""Run repository-level security, licence and claim consistency checks."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

from signalops.analysis import hourly_summary
from signalops.catalog import load_catalog
from signalops.publish import dashboard_payload, database_publish_context


def tracked_files(root: Path) -> tuple[Path, ...]:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True)
    return tuple(root / item.decode() for item in result.stdout.split(b"\0") if item)


def dashboard_differences(
    rows: list[dict[str, object]],
    actual: dict[str, object],
    context: dict[str, object] | None = None,
) -> list[str]:
    """Rebuild the payload at its recorded generation time and compare every field."""
    context = context or {}
    generated_at = datetime.fromisoformat(str(actual["generatedAt"]))
    actual_provenance = actual.get("provenance", {})
    if not isinstance(actual_provenance, dict):
        actual_provenance = {}
    expected = dashboard_payload(
        rows,
        generated_at=generated_at,
        provenance={
            # Deployment identifiers describe the publication being checked. Preserve the
            # committed values instead of inheriting the verifier's GITHUB_* environment.
            "gitSha": actual_provenance.get("gitSha", "unknown"),
            "workflowRunId": actual_provenance.get("workflowRunId", "local"),
            "dataDatabaseUpdatedAt": context.get("dataDatabaseUpdatedAt"),
        },
        quality_results=context.get("qualityResults", {}),
    )
    comparable = dict(actual)
    if comparable == expected:
        return []
    return ["dashboard summary does not match the rebuilt evidence database"]


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
    dashboard: dict[str, object] | None = None
    if dashboard_path.exists():
        dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
        if int(dashboard["pairedHours"]) == 0 and "do not" not in str(dashboard["notice"]).lower():
            errors.append("zero-overlap dashboard does not disclose the claim limitation")

    if database and not database.exists():
        errors.append(f"database does not exist: {database}")
    elif database:
        with sqlite3.connect(database) as connection:
            violations = connection.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                errors.append(f"database has {len(violations)} foreign-key violations")
        if dashboard is not None:
            context = database_publish_context(database)
            errors.extend(dashboard_differences(hourly_summary(database), dashboard, context))
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
