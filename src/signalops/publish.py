"""Build the static dashboard payload from canonical city-hour rows."""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterable, Mapping
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

CITY_KEYS = ("duesseldorf", "duisburg", "essen", "koeln")
DISPLAY_NAMES = {
    "duesseldorf": "Düsseldorf",
    "duisburg": "Duisburg",
    "essen": "Essen",
    "koeln": "Köln",
}
READINESS_MIN_PAIRED_HOURS = 168
READINESS_MIN_PAIRED_HOURS_PER_CITY = 24
READINESS_MIN_SPAN_HOURS = 72
READINESS_MIN_OVERLAP_COVERAGE = 0.5
READINESS_MIN_MATCH_COVERAGE = 0.8


def database_publish_context(database: Path) -> dict[str, object]:
    """Read deployment metadata and the most recent persisted quality results."""
    context: dict[str, object] = {"dataDatabaseUpdatedAt": None, "qualityResults": {}}
    with closing(sqlite3.connect(database)) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        if "artifact_imports" in tables:
            latest = connection.execute("SELECT MAX(retrieved_at) FROM artifact_imports").fetchone()
            context["dataDatabaseUpdatedAt"] = latest[0] if latest else None
        if {"quality_runs", "quality_results"}.issubset(tables):
            rows = connection.execute(
                """
                WITH ranked_runs AS (
                  SELECT q.dataset_key, q.run_id, a.scope_key,
                         ROW_NUMBER() OVER (
                           PARTITION BY q.dataset_key, a.scope_key ORDER BY q.run_id DESC
                         ) AS row_number
                  FROM quality_runs q JOIN artifact_imports a ON a.id = q.import_id
                ), latest_runs AS (
                  SELECT dataset_key, run_id, scope_key FROM ranked_runs WHERE row_number = 1
                )
                SELECT q.dataset_key, q.scope_key, r.rule_key, r.status,
                       r.records_checked, r.records_failed, r.details_json
                FROM latest_runs q JOIN quality_results r ON r.run_id = q.run_id
                ORDER BY q.dataset_key, q.scope_key, r.rule_key
                """
            ).fetchall()
            quality: dict[str, list[dict[str, object]]] = {}
            for dataset, scope, rule, status, checked, failed, details in rows:
                quality.setdefault(dataset, []).append({
                    "scope": scope, "rule": rule, "status": status,
                    "checked": checked, "failed": failed,
                    "details": json.loads(details),
                })
            context["qualityResults"] = quality
    return context


def _window(hours: list[str]) -> dict[str, object]:
    return {
        "start": min(hours) if hours else None,
        "end": max(hours) if hours else None,
        "cityHours": len(hours),
    }


def _age_minutes(latest_at: str | None, generated_at: datetime) -> int | None:
    if not latest_at:
        return None
    try:
        latest = datetime.fromisoformat(latest_at).astimezone(UTC)
    except (TypeError, ValueError):
        return None
    return max(0, int((generated_at - latest).total_seconds() // 60))


def _source_health(
    *, name: str, detail: str, count: int, latest_at: str | None,
    generated_at: datetime, datasets: tuple[str, ...],
    quality_results: Mapping[str, object], stale_after_minutes: int,
) -> dict[str, object]:
    checks = [
        check for dataset in datasets for check in quality_results.get(dataset, [])
        if isinstance(check, dict)
    ]
    failures = [check for check in checks if check.get("status") == "failure"]
    warnings = [check for check in checks if check.get("status") == "warning"]
    freshness_warnings = [check for check in warnings if check.get("rule") == "freshness"]
    age = _age_minutes(latest_at, generated_at)
    if not count:
        state, reason = "WAITING", "No retained observations are available."
    elif failures:
        state, reason = "FAILED", f"{len(failures)} latest quality check(s) failed."
    elif freshness_warnings or (age is not None and age > stale_after_minutes):
        state, reason = "STALE", "The latest retained observation exceeds its freshness limit."
    elif warnings:
        state, reason = "DEGRADED", f"{len(warnings)} latest quality check(s) reported warnings."
    else:
        state, reason = "READY", "Retained data are present and no latest quality check is failing."
    return {
        "name": name, "state": state, "detail": detail, "reason": reason,
        "latestAt": latest_at, "ageMinutes": age,
        "quality": {"checks": len(checks), "warnings": len(warnings), "failures": len(failures)},
    }


def _metric_provenance(row: Mapping[str, object], prefix: str) -> dict[str, object] | None:
    station = row.get(f"{prefix}_station")
    dataset = row.get(f"{prefix}_source")
    if not station and not dataset:
        return None
    return {
        "station": station,
        "role": row.get(f"{prefix}_station_role") or "Configured city weather proxy",
        "dataset": dataset,
        "provisional": dataset == "dwd_live_observations",
    }


def dashboard_payload(
    rows: Iterable[dict[str, object]], *, generated_at: datetime | None = None,
    provenance: Mapping[str, object] | None = None,
    quality_results: Mapping[str, object] | None = None,
) -> dict[str, object]:
    generated = (generated_at or datetime.now(UTC)).astimezone(UTC)
    provenance = provenance or {}
    quality_results = quality_results or {}
    city_rows: dict[str, list[dict[str, object]]] = {}
    weather_hours: list[str] = []
    rail_hours: list[str] = []
    paired_hours: list[str] = []
    paired_samples: list[dict[str, object]] = []
    for row in rows:
        city_rows.setdefault(str(row["city"]), []).append(row)
        hour = str(row.get("hour_utc") or "")
        if hour and int(row.get("weather_available") or 0):
            weather_hours.append(hour)
        if hour and int(row.get("rail_available") or 0):
            rail_hours.append(hour)
        if hour and int(row.get("paired") or 0):
            paired_hours.append(hour)
            delayed = int(row.get("delayed_events") or 0)
            matched = int(row.get("matched_change_events") or 0)
            delay_total = float(row.get("positive_delay_minutes_total") or 0)
            if not delay_total and row.get("average_delay_minutes") is not None:
                delay_total = float(row["average_delay_minutes"]) * delayed
            paired_samples.append(
                {
                    "city": str(row["city"]),
                    "hourUtc": hour,
                    "weatherStation": row.get("weather_station"),
                    "weather": {
                        "temperature": row.get("air_temperature_c"),
                        "humidity": row.get("relative_humidity_pct"),
                        "precipitation": row.get("precipitation_mm"),
                        "windSpeed": row.get("wind_speed_m_s"),
                        "windGust": row.get("wind_gust_m_s"),
                    },
                    "rail": {
                        "planned": int(row.get("planned_events") or 0),
                        "matched": matched,
                        "delayed": delayed,
                        "cancelled": int(row.get("cancelled_events") or 0),
                        "positiveDelayRate": round(delayed / matched, 4) if matched else None,
                        "meanPositiveDelay": (
                            round(delay_total / delayed, 1) if delayed else None
                        ),
                    },
                }
            )

    cities: list[dict[str, object]] = []
    for key in CITY_KEYS:
        scoped = city_rows.get(key, [])
        plans = sum(int(row.get("planned_events") or 0) for row in scoped)
        matched = sum(int(row.get("matched_change_events") or 0) for row in scoped)
        classified = sum(int(row.get("classified_change_events") or 0) for row in scoped)
        cancelled = sum(int(row.get("cancelled_events") or 0) for row in scoped)
        delayed = sum(int(row.get("delayed_events") or 0) for row in scoped)
        delay_minutes = sum(float(row.get("positive_delay_minutes_total") or 0) for row in scoped)
        if not delay_minutes:  # Compatibility for callers supplying pre-v2 analysis rows.
            delay_minutes = sum(
                float(row["average_delay_minutes"]) * int(row.get("delayed_events") or 0)
                for row in scoped if row.get("average_delay_minutes") is not None
            )
        if not classified:
            classified = sum(min(
                int(row.get("matched_change_events") or 0),
                int(row.get("cancelled_events") or 0) + int(row.get("delayed_events") or 0),
            ) for row in scoped)
        maximums = [
            float(row["maximum_delay_minutes"])
            for row in scoped
            if row.get("maximum_delay_minutes") is not None
        ]
        weather_rows = [row for row in scoped if int(row.get("weather_available") or 0)]
        city_paired = [
            str(row["hour_utc"])
            for row in scoped
            if row.get("hour_utc") and int(row.get("paired") or 0)
        ]
        latest_weather = max(
            weather_rows, key=lambda row: str(row.get("hour_utc") or ""), default=None
        )
        metric_sources = {
            metric: source
            for metric, prefix in {
                "temperature": "temperature", "humidity": "humidity",
                "precipitation": "precipitation", "windSpeed": "wind", "windGust": "gust",
            }.items()
            if latest_weather and (source := _metric_provenance(latest_weather, prefix))
        }
        cities.append({
            "key": key, "name": DISPLAY_NAMES[key], "plans": plans, "matched": matched,
            "classified": classified, "unmatched": max(0, plans - matched),
            "unclassified": max(0, matched - classified),
            "cancelled": cancelled,
            "delayed": delayed,
            "matchCoverage": round(matched / plans, 4) if plans else None,
            "coverageState": (
                "DEGRADED"
                if plans and matched / plans < READINESS_MIN_MATCH_COVERAGE
                else ("READY" if plans else "WAITING")
            ),
            "positiveDelayRate": round(delayed / matched, 4) if matched else None,
            "positiveDelayMinutesTotal": delay_minutes,
            "meanDelay": round(delay_minutes / delayed, 1) if delayed else None,
            "maxDelay": round(max(maximums), 1) if maximums else None,
            "pairedHours": len(city_paired), "pairedWindow": _window(city_paired),
            "weatherHours": len(weather_rows),
            "latestWeatherAt": latest_weather.get("hour_utc") if latest_weather else None,
            "weatherStation": latest_weather.get("weather_station") if latest_weather else None,
            "weatherProvenance": metric_sources,
            "temperature": latest_weather.get("air_temperature_c") if latest_weather else None,
            "humidity": latest_weather.get("relative_humidity_pct") if latest_weather else None,
            "precipitation": latest_weather.get("precipitation_mm") if latest_weather else None,
            "windSpeed": latest_weather.get("wind_speed_m_s") if latest_weather else None,
            "windGust": latest_weather.get("wind_gust_m_s") if latest_weather else None,
        })

    windows = {
        "weather": _window(weather_hours),
        "rail": _window(rail_hours),
        "overlap": _window(paired_hours),
    }
    overlap_span_hours = 0
    if windows["overlap"]["start"] and windows["overlap"]["end"]:
        start = datetime.fromisoformat(str(windows["overlap"]["start"]))
        end = datetime.fromisoformat(str(windows["overlap"]["end"]))
        overlap_span_hours = int((end - start).total_seconds() // 3600) + 1
    expected_overlap_city_hours = overlap_span_hours * len(CITY_KEYS)
    overlap_coverage = (
        len(paired_hours) / expected_overlap_city_hours if expected_overlap_city_hours else 0.0
    )
    total_plans = sum(int(city["plans"]) for city in cities)
    total_matched = sum(int(city["matched"]) for city in cities)
    total_classified = sum(int(city["classified"]) for city in cities)
    latest_weather_at = windows["weather"]["end"]
    latest_rail_at = windows["rail"]["end"]
    sources = [
        _source_health(
            name="DWD Weather", detail=f"{len(weather_hours)} retained city-hours",
            count=len(weather_hours),
            latest_at=str(latest_weather_at) if latest_weather_at else None,
            generated_at=generated,
            datasets=(
                "dwd_live_observations",
                "dwd_weather",
                "dwd_precipitation",
                "dwd_wind",
                "dwd_wind_gust",
            ),
            quality_results=quality_results, stale_after_minutes=180,
        ),
        _source_health(
            name="DB Plans", detail=f"{total_plans} retained timetable events", count=total_plans,
            latest_at=str(latest_rail_at) if latest_rail_at else None, generated_at=generated,
            datasets=("db_timetables",), quality_results=quality_results, stale_after_minutes=180,
        ),
        _source_health(
            name="DB Changes",
            detail=f"{total_matched} of {total_plans} plans matched",
            count=total_matched,
            latest_at=str(latest_rail_at) if latest_rail_at else None, generated_at=generated,
            datasets=("db_changes",), quality_results=quality_results, stale_after_minutes=180,
        ),
    ]
    low_coverage_cities = [
        str(city["name"])
        for city in cities
        if city["matchCoverage"] is not None
        and float(city["matchCoverage"]) < READINESS_MIN_MATCH_COVERAGE
    ]
    if low_coverage_cities and sources[2]["state"] == "READY":
        sources[2]["state"] = "DEGRADED"
        sources[2]["reason"] = (
            "Matching coverage is below 80% in " + ", ".join(low_coverage_cities) + "."
        )
    source_gate = all(source["state"] not in {"FAILED", "STALE"} for source in sources)
    match_coverage = total_matched / total_plans if total_plans else 0.0
    city_match_coverages = [
        float(city["matchCoverage"])
        for city in cities
        if city["matchCoverage"] is not None
    ]
    minimum_city_match_coverage = min(city_match_coverages, default=0.0)
    criteria = [
        {
            "key": "pairedHours",
            "label": "Paired city-hours",
            "actual": len(paired_hours),
            "required": READINESS_MIN_PAIRED_HOURS,
            "passed": len(paired_hours) >= READINESS_MIN_PAIRED_HOURS,
        },
        {
            "key": "pairedHoursPerCity",
            "label": "Paired hours in every city",
            "actual": min(int(city["pairedHours"]) for city in cities),
            "required": READINESS_MIN_PAIRED_HOURS_PER_CITY,
            "passed": all(
                int(city["pairedHours"]) >= READINESS_MIN_PAIRED_HOURS_PER_CITY
                for city in cities
            ),
        },
        {
            "key": "overlapSpanHours",
            "label": "Overlap time span",
            "actual": overlap_span_hours,
            "required": READINESS_MIN_SPAN_HOURS,
            "passed": overlap_span_hours >= READINESS_MIN_SPAN_HOURS,
        },
        {
            "key": "overlapCoverage",
            "label": "Expected city-hour coverage",
            "actual": round(overlap_coverage, 4),
            "required": READINESS_MIN_OVERLAP_COVERAGE,
            "passed": overlap_coverage >= READINESS_MIN_OVERLAP_COVERAGE,
        },
        {
            "key": "matchCoverage",
            "label": "DB matching coverage in every city",
            "actual": round(minimum_city_match_coverage, 4),
            "required": READINESS_MIN_MATCH_COVERAGE,
            "passed": minimum_city_match_coverage >= READINESS_MIN_MATCH_COVERAGE,
        },
        {
            "key": "sourceHealth",
            "label": "No failed or stale source",
            "actual": source_gate,
            "required": True,
            "passed": source_gate,
        },
    ]
    analysis_ready = all(bool(criterion["passed"]) for criterion in criteria)
    if analysis_ready:
        status = "ANALYSIS READY"
        notice = (
            f"{len(paired_hours)} city-hours meet the published coverage and source-health "
            "thresholds. Results remain descriptive and do not establish causation."
        )
    elif paired_hours:
        status = "OVERLAP DETECTED"
        notice = (
            f"{len(paired_hours)} city-hours overlap, but one or more readiness thresholds "
            "are not met. Weather effects are not reported yet."
        )
    else:
        status = "WAITING FOR TIME OVERLAP"
        notice = (
            "The retained weather and railway windows do not overlap yet. "
            "Weather effects are not calculated."
        )
    sources.append({
        "name": "Paired analysis",
        "state": "READY" if analysis_ready else ("PARTIAL" if paired_hours else "WAITING"),
        "detail": f"{len(paired_hours)} overlapping city-hours",
        "reason": "All readiness gates pass." if analysis_ready else "Readiness gates remain open.",
        "latestAt": windows["overlap"]["end"], "ageMinutes": None,
        "quality": {"checks": len(criteria), "warnings": 0, "failures": 0},
    })
    recent_paired_samples = sorted(
        paired_samples,
        key=lambda sample: (str(sample["hourUtc"]), str(sample["city"])),
        reverse=True,
    )[:24]

    return {
        "schemaVersion": 2, "generatedAt": generated.isoformat(), "status": status,
        "notice": notice, "pairedHours": len(paired_hours), "weatherHours": len(weather_hours),
        "railHours": len(rail_hours), "windows": windows,
        "latestDwdAt": latest_weather_at, "latestDbAt": latest_rail_at,
        "completeness": {
            "planned": total_plans, "matched": total_matched, "classified": total_classified,
            "unmatched": max(0, total_plans - total_matched),
            "unclassified": max(0, total_matched - total_classified),
            "delayed": sum(int(city["delayed"]) for city in cities),
            "cancelled": sum(int(city["cancelled"]) for city in cities),
            "positiveDelayMinutesTotal": sum(
                float(city["positiveDelayMinutesTotal"]) for city in cities
            ),
            "matchCoverage": round(match_coverage, 4) if total_plans else None,
        },
        "readiness": {"ready": analysis_ready, "criteria": criteria},
        "liveGoal": {
            "title": (
                "Build trustworthy evidence of when weather stress and rail disruption coincide"
            ),
            "question": (
                "Do rain, wind, heat, or other weather conditions coincide with more delays "
                "or cancellations at the four Rhine–Ruhr stations?"
            ),
            "method": (
                "Join configured DWD weather proxies to DB operational events only when city "
                "and UTC hour match; report association without claiming causation."
            ),
            "currentPairedHours": len(paired_hours),
            "targetPairedHours": READINESS_MIN_PAIRED_HOURS,
            "progress": round(min(1.0, len(paired_hours) / READINESS_MIN_PAIRED_HOURS), 4),
            "state": status,
        },
        "pairedTimeline": recent_paired_samples,
        "collection": {
            "pipelineCadenceMinutes": 15, "browserPollSeconds": 60,
            "analysisRetentionDays": 180, "rawEvidenceRetentionDays": 30,
            "explanation": (
                "The browser checks the latest published JSON every 60 seconds. Collection "
                "runs separately on a nominal 15-minute GitHub Actions schedule."
            ),
            "refreshScope": [
                "DWD weather",
                "DB plans",
                "DB changes",
                "quality checks",
                "paired analysis",
            ],
            "atomicPublication": True,
        },
        "provenance": {
            "gitSha": provenance.get("gitSha") or os.getenv("GITHUB_SHA") or "unknown",
            "workflowRunId": provenance.get("workflowRunId")
            or os.getenv("GITHUB_RUN_ID")
            or "local",
            "dataDatabaseUpdatedAt": provenance.get("dataDatabaseUpdatedAt"),
        },
        "cities": cities, "sources": sources,
    }


def write_dashboard_json(
    rows: Iterable[dict[str, object]], output: Path, *, generated_at: datetime | None = None,
    provenance: Mapping[str, object] | None = None,
    quality_results: Mapping[str, object] | None = None,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            dashboard_payload(
                rows,
                generated_at=generated_at,
                provenance=provenance,
                quality_results=quality_results,
            ),
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
