"""Builds MMM rows from per-day metric values and the prepared features (lags, rolling means, calendar, holidays)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import holidays

from integrations.training.mmm.plan import HOLIDAY_FEATURE, PreparationSpec
from integrations.training.mmm.recipe import DATE_COLUMN


def _value(by_day: dict[date, dict[str, float | None]], day: date, name: str) -> float:
    """A missing or NULL value is a blank, and blanks count as 0."""
    value = by_day.get(day, {}).get(name)
    return float(value) if value is not None else 0.0


def _holiday_calendar(country: str, start: date, end: date) -> holidays.HolidayBase:
    return holidays.country_holidays(country, years=range(start.year, end.year + 1))


def _calendar_features(day: date, spec: PreparationSpec) -> dict[str, int]:
    features: dict[str, int] = {}
    for name in spec.date_features:
        if name == "day_of_week":
            features[name] = day.weekday()
        elif name == "month":
            features[name] = day.month
        elif name == "week_of_year":
            features[name] = day.isocalendar().week
        elif name == "is_weekend":
            features[name] = int(day.weekday() >= 5)
    return features


def build_rows(
    by_day: dict[date, dict[str, float | None]],
    outputs: list[str],
    kpi: str,
    date_start: date,
    date_end: date,
    spec: PreparationSpec,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Keeps in-window days that have a KPI value. Lags and rolling means read the full history in by_day."""
    holiday_calendar = _holiday_calendar(spec.holiday_country, date_start, date_end) if spec.holiday_country else None
    blanks = dict.fromkeys(outputs, 0)
    rows: list[dict[str, Any]] = []
    dropped = 0
    for day in sorted(d for d in by_day if date_start <= d <= date_end):
        values = by_day[day]
        if kpi not in values:
            dropped += 1
            continue
        record: dict[str, Any] = {DATE_COLUMN: day.isoformat()}
        for name in outputs:
            if values.get(name) is None:
                blanks[name] += 1
            record[name] = _value(by_day, day, name)
        record.update(_calendar_features(day, spec))
        if holiday_calendar is not None:
            record[HOLIDAY_FEATURE] = int(day in holiday_calendar)
        for metric, lags in spec.lags.items():
            for lag in lags:
                record[f"{metric}_lag_{lag}"] = _value(by_day, day - timedelta(days=lag), metric)
        for metric, window in spec.rolling_means.items():
            history = [_value(by_day, day - timedelta(days=offset), metric) for offset in range(window)]
            record[f"{metric}_roll_mean_{window}"] = sum(history) / window
        rows.append(record)
    log = {
        "rows_kept": len(rows),
        "days_dropped_without_kpi": dropped,
        "blanks_filled": blanks,
        "history_days": spec.history_days(),
        "features": spec.feature_names(),
    }
    return rows, log
