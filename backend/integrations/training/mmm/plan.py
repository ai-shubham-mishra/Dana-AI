"""Validated MMM run plan. The agent proposes it; the service executes it."""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Literal

import holidays
from pydantic import BaseModel, Field, model_validator

NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,62}$")
RESERVED_OUTPUT_NAMES = frozenset({"date"})
MAX_FILTER_VALUE_LENGTH = 100
DATE_FEATURES = ("day_of_week", "month", "week_of_year", "is_weekend")
HOLIDAY_FEATURE = "is_holiday"
MAX_LAG_DAYS = 52
MAX_ROLLING_WINDOW = 52
OVERRIDE_RANGES: dict[str, tuple[int, int]] = {
    "adstock_l_max": (1, 52),
    "yearly_seasonality": (0, 6),
    "chains": (1, 8),
    "tune": (100, 4000),
    "draws": (100, 4000),
    "holdout_periods": (0, 52),
}
BOOL_OVERRIDES = frozenset({"time_varying_intercept"})
OVERRIDE_KEYS = frozenset(OVERRIDE_RANGES) | BOOL_OVERRIDES


class PlanError(ValueError):
    """Raised when an MMM plan fails validation."""


class SourceSpec(BaseModel):
    table: str
    date_column: str
    metrics: dict[str, str] = Field(min_length=1)
    filters: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_identifiers(self) -> SourceSpec:
        for name in (self.table, self.date_column, *self.metrics.values(), *self.filters):
            if not IDENTIFIER_PATTERN.match(name):
                raise PlanError(f"'{name}' is not a valid connector table or column name")
        for column, value in self.filters.items():
            if not value.strip() or len(value) > MAX_FILTER_VALUE_LENGTH:
                raise PlanError(f"filter value for '{column}' must be 1 to {MAX_FILTER_VALUE_LENGTH} characters")
        return self


class PreparationSpec(BaseModel):
    text_to_numeric: list[str] = Field(
        default_factory=list,
        description="Metric outputs whose source column is text holding numbers. Values are read as numbers; blanks and unreadable values become 0.",
    )
    date_features: list[Literal["day_of_week", "month", "week_of_year", "is_weekend"]] = Field(
        default_factory=list,
        description="Calendar features derived from each date: day_of_week (0=Monday), month, week_of_year, is_weekend (0/1).",
    )
    holiday_country: str | None = Field(
        default=None,
        description="ISO 3166-1 alpha-2 country code. Adds is_holiday (0/1) for public holidays in that country.",
    )
    lags: dict[str, list[int]] = Field(
        default_factory=dict,
        description=f"Metric output to lag days (1 to {MAX_LAG_DAYS}), for example {{'search': [7, 14]}}. Creates <output>_lag_<days> features.",
    )
    rolling_means: dict[str, int] = Field(
        default_factory=dict,
        description=f"Metric output to trailing rolling-mean window in days (2 to {MAX_ROLLING_WINDOW}), for example {{'search': 7}}. Creates <output>_roll_mean_<days> features.",
    )
    combine_channels: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Combined channel name to the raw outputs it sums, for example {'social_prospecting': ['meta_reach', 'meta_traffic']}. Each group is a daily sum column and is listed in channels in place of its members.",
    )

    @model_validator(mode="after")
    def _check_preparation(self) -> PreparationSpec:
        if len(set(self.text_to_numeric)) != len(self.text_to_numeric):
            raise PlanError("preparation.text_to_numeric must not repeat")
        for name in (*self.text_to_numeric, *self.lags, *self.rolling_means, *self.combine_channels):
            if not NAME_PATTERN.match(name):
                raise PlanError(f"preparation output name '{name}' must be lowercase snake_case")
        seen: set[str] = set()
        for group, members in self.combine_channels.items():
            if group in RESERVED_OUTPUT_NAMES:
                raise PlanError(f"combined channel name '{group}' is reserved")
            if len(set(members)) != len(members) or len(members) < 2:
                raise PlanError(f"combined channel '{group}' needs at least 2 distinct members")
            repeated = seen & set(members)
            if repeated:
                raise PlanError(f"output '{sorted(repeated)[0]}' is in more than one combined channel")
            seen.update(members)
        if len(set(self.date_features)) != len(self.date_features):
            raise PlanError("preparation.date_features must not repeat")
        if self.holiday_country is not None:
            try:
                holidays.country_holidays(self.holiday_country)
            except NotImplementedError as exc:
                raise PlanError(f"holiday_country '{self.holiday_country}' is not supported; use an ISO alpha-2 code") from exc
        for name, lags in self.lags.items():
            if not lags or len(set(lags)) != len(lags):
                raise PlanError(f"lags for '{name}' must be a non-empty list of distinct day counts")
            for lag in lags:
                if isinstance(lag, bool) or not 1 <= lag <= MAX_LAG_DAYS:
                    raise PlanError(f"lag for '{name}' must be between 1 and {MAX_LAG_DAYS} days")
        for name, window in self.rolling_means.items():
            if isinstance(window, bool) or not 2 <= window <= MAX_ROLLING_WINDOW:
                raise PlanError(f"rolling mean window for '{name}' must be between 2 and {MAX_ROLLING_WINDOW} days")
        return self

    def feature_names(self) -> list[str]:
        names = list(self.date_features)
        if self.holiday_country is not None:
            names.append(HOLIDAY_FEATURE)
        for metric, lags in self.lags.items():
            names.extend(f"{metric}_lag_{lag}" for lag in lags)
        for metric, window in self.rolling_means.items():
            names.append(f"{metric}_roll_mean_{window}")
        return names

    def history_days(self) -> int:
        """Days before the window needed so lags and rolling means are full at the first row."""
        spans = [lag for lags in self.lags.values() for lag in lags]
        spans.extend(window - 1 for window in self.rolling_means.values())
        return max(spans, default=0)

    def is_empty(self) -> bool:
        return not (
            self.text_to_numeric
            or self.date_features
            or self.holiday_country
            or self.lags
            or self.rolling_means
            or self.combine_channels
        )


def check_combine_groups(
    groups: dict[str, list[str]],
    outputs: list[str],
    kpi: str,
    controls: list[str],
    features: list[str] | None = None,
) -> None:
    """Members must be mapped outputs that are neither the kpi nor a control. Group names must be new names."""
    known = set(outputs)
    taken = known | set(features or []) | {kpi}
    for group, members in groups.items():
        if group in taken:
            raise PlanError(f"combined channel '{group}' clashes with an output, prepared feature or the kpi")
        for member in members:
            if member not in known:
                raise PlanError(f"combined channel '{group}' member '{member}' is not a mapped output")
            if member == kpi:
                raise PlanError(f"combined channel '{group}' cannot include the kpi '{kpi}'")
            if member in controls:
                raise PlanError(f"combined channel '{group}' cannot include control '{member}'")


class MMMPlan(BaseModel):
    kpi: str
    channels: list[str] = Field(min_length=1)
    controls: list[str] = Field(default_factory=list)
    controls_reason: str = ""
    sources: list[SourceSpec] = Field(min_length=1)
    date_start: date
    date_end: date
    overrides: dict[str, Any] = Field(default_factory=dict)
    preparation: PreparationSpec = Field(default_factory=PreparationSpec)
    rationale: str = ""

    @model_validator(mode="after")
    def _check_plan(self) -> MMMPlan:
        if not self.controls and not self.controls_reason.strip():
            raise PlanError(
                "no controls were given. Confirm controls with the user (holiday or Black Friday flags, "
                "promotions, price, weather) and pass them in controls, or pass controls_reason explaining why none apply"
            )
        outputs: list[str] = []
        for source in self.sources:
            outputs.extend(source.metrics)
        for name in outputs:
            if not NAME_PATTERN.match(name):
                raise PlanError(f"output name '{name}' must be lowercase snake_case")
            if name in RESERVED_OUTPUT_NAMES:
                raise PlanError(f"output name '{name}' is reserved")
        if len(set(outputs)) != len(outputs):
            raise PlanError("output names must be unique across all sources")
        known = set(outputs)
        features = self.preparation.feature_names()
        if len(set(features)) != len(features):
            raise PlanError("prepared feature names must be unique")
        clashes = sorted(known & set(features))
        if clashes:
            raise PlanError(f"prepared feature '{clashes[0]}' clashes with a mapped output; rename the output")
        for name in self.preparation.text_to_numeric:
            if name not in known:
                raise PlanError(f"preparation text_to_numeric '{name}' is not a mapped output")
        for name in (*self.preparation.lags, *self.preparation.rolling_means):
            if name not in known:
                raise PlanError(f"preparation lag or rolling mean '{name}' is not a mapped output")
            if name == self.kpi:
                raise PlanError("lags and rolling means of the kpi are not allowed because they leak the target")
        if self.kpi not in known:
            raise PlanError(f"kpi '{self.kpi}' is not a mapped output")
        groups = self.preparation.combine_channels
        check_combine_groups(groups, outputs, self.kpi, self.controls, features)
        members = {member for group_members in groups.values() for member in group_members}
        for name in self.channels:
            if name in members:
                raise PlanError(f"channel '{name}' is combined into a group; list the group name in channels instead")
        for group in groups:
            if group not in self.channels:
                raise PlanError(f"combined channel '{group}' must be listed in channels")
        for group, names, allowed in (
            ("channels", self.channels, known | set(groups)),
            ("controls", self.controls, known | set(features)),
        ):
            if len(set(names)) != len(names):
                raise PlanError(f"{group} must not repeat")
            for name in names:
                if name not in allowed:
                    raise PlanError(f"{group[:-1]} '{name}' is not a mapped output or prepared feature")
        overlap = set(self.channels) & set(self.controls)
        if overlap or self.kpi in self.channels or self.kpi in self.controls:
            raise PlanError("kpi, channels and controls must not overlap")
        if self.date_start > self.date_end:
            raise PlanError("date_start must not be after date_end")
        for key, value in self.overrides.items():
            _check_override(key, value)
        return self

    def output_names(self) -> list[str]:
        return [name for source in self.sources for name in source.metrics]

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def _check_override(key: str, value: Any) -> None:
    if key not in OVERRIDE_KEYS:
        raise PlanError(f"override '{key}' is not allowed; see config-reference/SKILL.md")
    if key in BOOL_OVERRIDES:
        if not isinstance(value, bool):
            raise PlanError(f"override '{key}' must be true or false")
        return
    low, high = OVERRIDE_RANGES[key]
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise PlanError(f"override '{key}' must be an integer between {low} and {high}")
