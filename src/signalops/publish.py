"""Build the small static dashboard payload from canonical city-hour rows."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Iterable


def dashboard_payload(
    rows: Iterable[dict[str, object]], *, generated_at: datetime | None = None
) -> dict[str, object]:
    city_rows: dict[str, list[dict[str, object]]] = {}
    paired_hours = 0
    for row in rows:
        city_rows.setdefault(str(row["city"]), []).append(row)
        paired_hours += int(row.get("paired") or 0)

    display_names = {
        "duesseldorf": "Düsseldorf",
        "duisburg": "Duisburg",
        "essen": "Essen",
        "koeln": "Köln",
    }
    cities: list[dict[str, object]] = []
    for key in ("duesseldorf", "duisburg", "essen", "koeln"):
        scoped = city_rows.get(key, [])
        plans = sum(int(row.get("planned_events") or 0) for row in scoped)
        matched = sum(int(row.get("matched_change_events") or 0) for row in scoped)
        cancelled = sum(int(row.get("cancelled_events") or 0) for row in scoped)
        delayed = sum(int(row.get("delayed_events") or 0) for row in scoped)
        delay_numerator = sum(
            float(row["average_delay_minutes"]) * int(row.get("delayed_events") or 0)
            for row in scoped
            if row.get("average_delay_minutes") is not None
        )
        maximums = [
            float(row["maximum_delay_minutes"])
            for row in scoped
            if row.get("maximum_delay_minutes") is not None
        ]
        cities.append(
            {
                "key": key,
                "name": display_names[key],
                "plans": plans,
                "matched": matched,
                "cancelled": cancelled,
                "delayed": delayed,
                "meanDelay": round(delay_numerator / delayed, 1) if delayed else None,
                "maxDelay": round(max(maximums), 1) if maximums else None,
            }
        )

    if paired_hours:
        status = "PAIRED EVIDENCE AVAILABLE"
        notice = (
            f"{paired_hours} city-hour observations contain both sources. "
            "Results remain descriptive and do not establish causation."
        )
    else:
        status = "COLLECTING EVIDENCE"
        notice = (
            "The retained weather and railway windows do not overlap yet. "
            "Weather effects are not calculated."
        )
    total_plans = sum(int(city["plans"]) for city in cities)
    total_matched = sum(int(city["matched"]) for city in cities)
    return {
        "generatedAt": (generated_at or datetime.now(UTC)).astimezone(UTC).isoformat(),
        "status": status,
        "pairedHours": paired_hours,
        "notice": notice,
        "cities": cities,
        "sources": [
            {"name": "DWD Weather", "state": "READY", "detail": "Latest archive retained"},
            {"name": "DB Plans", "state": "READY", "detail": f"{total_plans} planned events"},
            {
                "name": "DB Changes",
                "state": "READY",
                "detail": f"{total_matched} matched events",
            },
            {
                "name": "Paired analysis",
                "state": "READY" if paired_hours else "WAITING",
                "detail": f"{paired_hours} overlapping city-hours",
            },
        ],
    }


def write_dashboard_json(
    rows: Iterable[dict[str, object]], output: Path, *, generated_at: datetime | None = None
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(dashboard_payload(rows, generated_at=generated_at), indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
