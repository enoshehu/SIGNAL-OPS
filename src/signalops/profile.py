"""Reproducible descriptive profile for paired weather and railway hours."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from signalops.analysis import hourly_summary


@dataclass(frozen=True, slots=True)
class ConditionSummary:
    condition: str
    city_hours: int
    planned_events: int
    matched_events: int
    delayed_events: int
    cancelled_events: int

    @property
    def delay_share(self) -> float | None:
        return self.delayed_events / self.matched_events if self.matched_events else None

    @property
    def cancellation_share(self) -> float | None:
        return self.cancelled_events / self.matched_events if self.matched_events else None


def _condition_rows(rows: list[dict[str, object]], name: str) -> list[dict[str, object]]:
    if name == "all paired hours":
        return rows
    if name == "hot (≥30 °C)":
        return [row for row in rows if float(row.get("air_temperature_c") or -999) >= 30]
    if name == "rain (≥1 mm/h)":
        return [row for row in rows if float(row.get("precipitation_mm") or 0) >= 1]
    if name == "strong wind (≥10 m/s)":
        return [row for row in rows if float(row.get("wind_speed_m_s") or 0) >= 10]
    if name == "strong gust (≥15 m/s)":
        return [row for row in rows if float(row.get("wind_gust_m_s") or 0) >= 15]
    raise ValueError(f"Unknown condition: {name}")


def condition_summaries(database: Path) -> tuple[ConditionSummary, ...]:
    paired = [row for row in hourly_summary(database) if int(row.get("paired") or 0)]
    summaries: list[ConditionSummary] = []
    for name in (
        "all paired hours",
        "hot (≥30 °C)",
        "rain (≥1 mm/h)",
        "strong wind (≥10 m/s)",
        "strong gust (≥15 m/s)",
    ):
        rows = _condition_rows(paired, name)
        summaries.append(
            ConditionSummary(
                condition=name,
                city_hours=len(rows),
                planned_events=sum(int(row.get("planned_events") or 0) for row in rows),
                matched_events=sum(int(row.get("matched_change_events") or 0) for row in rows),
                delayed_events=sum(int(row.get("delayed_events") or 0) for row in rows),
                cancelled_events=sum(int(row.get("cancelled_events") or 0) for row in rows),
            )
        )
    return tuple(summaries)


def _percentage(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def render_profile(database: Path) -> str:
    rows = hourly_summary(database)
    paired = [row for row in rows if int(row.get("paired") or 0)]
    cities = ("duesseldorf", "duisburg", "essen", "koeln")
    lines = [
        "# Paired weather × railway window profile",
        "",
        (
            "This report is generated from canonical SQLite rows. Comparisons are descriptive and "
            "do not establish that weather caused railway disruption."
        ),
        "",
        "## Coverage",
        "",
        f"- Paired city-hours: **{len(paired)}**",
    ]
    for city in cities:
        count = sum(1 for row in paired if row["city"] == city)
        lines.append(f"- {city}: **{count}** paired city-hours")
    if not paired:
        lines.extend(
            [
                "",
                (
                    "> Status: waiting for a genuine overlapping source window. No weather-effect "
                    "comparison is reported."
                ),
                "",
            ]
        )
        return "\n".join(lines)

    fields = (
        ("air_temperature_c", "temperature"),
        ("relative_humidity_pct", "humidity"),
        ("precipitation_mm", "precipitation"),
        ("wind_speed_m_s", "wind speed"),
        ("wind_gust_m_s", "wind gust"),
    )
    lines.extend(["", "## Missingness within paired hours", ""])
    for field, label in fields:
        missing = sum(row.get(field) is None for row in paired)
        lines.append(f"- {label}: {missing}/{len(paired)} missing")

    lines.extend(
        [
            "",
            "## Descriptive condition comparison",
            "",
            "| Condition | City-hours | Plans | Matched | Delay share | Cancellation share |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for item in condition_summaries(database):
        lines.append(
            f"| {item.condition} | {item.city_hours} | {item.planned_events} | "
            f"{item.matched_events} | {_percentage(item.delay_share)} | "
            f"{_percentage(item.cancellation_share)} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            "- Stations are city-area proxies, not measurements at railway platforms.",
            (
                "- Duisburg live POI wind uses Duisburg-Baerl; historical CDC wind and gust "
                "use Xanten, approximately 26.5 km away."
            ),
            "- DB change feeds are snapshots; unmatched changes are not counted as delays.",
            "- Exact UTC-hour matching reduces sample size and does not control for other causes.",
            "- Condition thresholds are transparent descriptive bands, not causal models.",
            "",
        ]
    )
    return "\n".join(lines)


def write_profile(database: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_profile(database), encoding="utf-8")
