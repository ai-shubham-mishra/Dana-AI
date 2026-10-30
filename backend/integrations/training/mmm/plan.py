"""Validated MMM run plan. The agent proposes it; the service executes it."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from pydantic import BaseModel, Field, model_validator

NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
RESERVED_OUTPUT_NAMES = frozenset({"date"})
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

    @model_validator(mode="after")
    def _check_identifiers(self) -> SourceSpec:
        for name in (self.table, self.date_column, *self.metrics.values()):
            if not IDENTIFIER_PATTERN.match(name):
                raise PlanError(f"'{name}' is not a valid connector table or column name")
        return self


class MMMPlan(BaseModel):
    kpi: str
    channels: list[str] = Field(min_length=1)
    controls: list[str] = Field(default_factory=list)
    controls_reason: str = ""
    sources: list[SourceSpec] = Field(min_length=1)
    date_start: date
    date_end: date
    overrides: dict[str, Any] = Field(default_factory=dict)
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
        if self.kpi not in known:
            raise PlanError(f"kpi '{self.kpi}' is not a mapped output")
        for group, names in (("channels", self.channels), ("controls", self.controls)):
            if len(set(names)) != len(names):
                raise PlanError(f"{group} must not repeat")
            for name in names:
                if name not in known:
                    raise PlanError(f"{group[:-1]} '{name}' is not a mapped output")
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
