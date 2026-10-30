"""Run folder layout: every run keeps its inputs and outputs together."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

DATASET_FILE = "dataset.csv"
CONFIG_FILE = "config.yml"
TRAIN_FILE = "train.py"
EVALUATION_FILE = "evaluation.json"
MODEL_FILE = "mmm_model.nc"
RUN_FILES = (DATASET_FILE, CONFIG_FILE, TRAIN_FILE, EVALUATION_FILE, MODEL_FILE)


def write_inputs(
    run_dir: Path,
    columns: list[str],
    rows: list[dict[str, Any]],
    config_yaml: str,
    script: str,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / DATASET_FILE).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    (run_dir / CONFIG_FILE).write_text(config_yaml, encoding="utf-8")
    (run_dir / TRAIN_FILE).write_text(script, encoding="utf-8")


def missing_outputs(run_dir: Path) -> list[str]:
    return [name for name in RUN_FILES if not (run_dir / name).is_file() or (run_dir / name).stat().st_size == 0]
