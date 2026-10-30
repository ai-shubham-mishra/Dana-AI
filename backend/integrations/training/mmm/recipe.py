"""Builds the MMM run config and the on-the-fly training script from a validated plan."""

from __future__ import annotations

import ast
import copy
import re
from pathlib import Path
from typing import Any

import yaml

from config.settings import BACKEND_ROOT
from integrations.training.mmm.plan import MMMPlan

SKILL_DIR = BACKEND_ROOT / "agent" / "skills" / "ml-ops" / "ml" / "mmm"
DEFAULTS_PATH = SKILL_DIR / "config-reference" / "defaults.yaml"
TEMPLATE_PATH = SKILL_DIR / "run-script" / "train_template.py.tmpl"
DATE_COLUMN = "date"
PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")


def load_defaults() -> dict[str, Any]:
    return yaml.safe_load(DEFAULTS_PATH.read_text(encoding="utf-8"))


def build_config(plan: MMMPlan, defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    base = copy.deepcopy(defaults if defaults is not None else load_defaults())
    model = base["model"]
    sampling = base["sampling"]
    overrides = plan.overrides
    if "adstock_l_max" in overrides:
        model["adstock"]["l_max"] = overrides["adstock_l_max"]
    if "yearly_seasonality" in overrides:
        model["yearly_seasonality"] = overrides["yearly_seasonality"]
    if "time_varying_intercept" in overrides:
        model["time_varying_intercept"] = overrides["time_varying_intercept"]
    for key in ("chains", "tune", "draws"):
        if key in overrides:
            sampling[key] = overrides[key]
    validation = base["validation"]
    if "holdout_periods" in overrides:
        validation["holdout_periods"] = overrides["holdout_periods"]
    return {
        "date_column": DATE_COLUMN,
        "target_column": plan.kpi,
        "channels": sorted(plan.channels),
        "controls": sorted(plan.controls),
        "model": model,
        "sampling": sampling,
        "validation": validation,
    }


def dump_config(config: dict[str, Any]) -> str:
    return yaml.safe_dump(config, sort_keys=False)


def render_script(config: dict[str, Any], plan_summary: dict[str, Any], generated_at: str) -> str:
    values = {
        "CONFIG_LITERAL": repr(config),
        "PLAN_SUMMARY_LITERAL": repr(plan_summary),
        "GENERATED_AT_LITERAL": repr(generated_at),
    }
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    unknown = sorted(set(PLACEHOLDER.findall(template)) - set(values))
    if unknown:
        raise ValueError(f"template has unknown placeholders: {', '.join(unknown)}")
    script = PLACEHOLDER.sub(lambda match: values[match.group(1)], template)
    ast.parse(script)
    return script
