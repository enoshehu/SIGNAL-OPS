"""Build the small static dashboard payload from canonical city-hour rows."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path


def dashboard_payload(
    rows: Iterable[dict[str, object]], *, generated_at: datetime | None = None
) -> dict[str, object]:
    city_rows: dict[str, list[dict[str, object]]] = {}
    paired_hours = 0
    weather_hours = 0
    rail_hours = 0
    observed_hours: list[str] = []
    for row in rows:
        city_rows.setdefault(str(row["city"]), []).append(row)
        paired_hours += int(row.get("paired") or 0)
        weather_hours += int(row.get("weather_available") or 0)
        rail_hours += int(row.get("rail_available") or 0)
        if row.get("hour_utc"):
            observed_hours.append(str(row["hour_utc"]))

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
        weather_rows = [row for row in scoped if int(row.get("weather_available") or 0)]
        latest_weather = max(
            weather_rows, key=lambda row: str(row.get("hour_utc") or ""), default=None
        )
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
                "weatherHours": len(weather_rows),
                "latestWeatherAt": latest_weather.get("hour_utc") if latest_weather else None,
                "temperature": latest_weather.get("air_temperature_c") if latest_weather else None,
                "humidity": latest_weather.get("relative_humidity_pct") if latest_weather else None,
                "precipitation": latest_weather.get("precipitation_mm") if latest_weather else None,
                "windSpeed": latest_weather.get("wind_speed_m_s") if latest_weather else None,
            }
        )

    if paired_hours:
        status = "ANALYSIS READY"
        notice = (
            f"{paired_hours} city-hour observations contain both sources. "
            "Results remain descriptive and do not establish causation."
        )
    else:
        status = "WAITING FOR TIME OVERLAP"
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
        "weatherHours": weather_hours,
        "railHours": rail_hours,
        "windowStart": min(observed_hours) if observed_hours else None,
        "windowEnd": max(observed_hours) if observed_hours else None,
        "notice": notice,
        "cities": cities,
        "sources": [
            {"name": "DWD Weather", "state": "READY", "detail": f"{weather_hours} city-hours"},
            {"name": "DB Plans", "state": "READY", "detail": f"{total_plans} timetable events"},
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
