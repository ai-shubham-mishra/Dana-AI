"""Spend profile per candidate channel and per proposed combined group, over the modelling window."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class ChannelStat:
    name: str
    total: float
    active_days: int
    mean_active: float
    share: float
    low: bool


@dataclass(frozen=True)
class ChannelProfile:
    total_spend: float
    channels: list[ChannelStat] = field(default_factory=list)
    groups: list[ChannelStat] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_spend": self.total_spend,
            "channels": [stat.__dict__ for stat in self.channels],
            "groups": [stat.__dict__ for stat in self.groups],
        }


def _window_series(
    by_day: dict[date, dict[str, float | None]], names: list[str], date_start: date, date_end: date
) -> dict[str, dict[date, float]]:
    series: dict[str, dict[date, float]] = {name: {} for name in names}
    for day, values in by_day.items():
        if not date_start <= day <= date_end:
            continue
        for name in names:
            value = values.get(name)
            if value is not None:
                series[name][day] = float(value)
    return series


def _stat(name: str, series: dict[date, float], denominator: float, threshold: float) -> ChannelStat:
    total = sum(series.values())
    active = [value for value in series.values() if value > 0]
    share = total / denominator if denominator > 0 else 0.0
    mean_active = sum(active) / len(active) if active else 0.0
    return ChannelStat(
        name=name,
        total=round(total, 2),
        active_days=len(active),
        mean_active=round(mean_active, 2),
        share=round(share, 4),
        low=share < threshold,
    )


def profile_spend(
    by_day: dict[date, dict[str, float | None]],
    candidates: list[str],
    groups: dict[str, list[str]],
    date_start: date,
    date_end: date,
    threshold_share: float,
) -> ChannelProfile:
    """Shares are of total candidate spend. A group's active days are the days any member was active."""
    series = _window_series(by_day, candidates, date_start, date_end)
    total_spend = sum(sum(values.values()) for values in series.values())
    channels = [_stat(name, series[name], total_spend, threshold_share) for name in candidates]
    channels.sort(key=lambda stat: stat.share)

    group_stats: list[ChannelStat] = []
    for group, members in groups.items():
        combined: dict[date, float] = {}
        for member in members:
            for day, value in series.get(member, {}).items():
                combined[day] = combined.get(day, 0.0) + value
        group_stats.append(_stat(group, combined, total_spend, threshold_share))
    return ChannelProfile(total_spend=round(total_spend, 2), channels=channels, groups=group_stats)
