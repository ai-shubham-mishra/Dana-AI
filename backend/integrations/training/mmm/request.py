import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

MODEL_FAMILY = "mmm"
DATE_RANGE_RE = re.compile(r"^\s*(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})\s*$")


class RequestError(ValueError):
    pass


@dataclass(frozen=True)
class DatasetSpec:
    target_column: str
    channels: tuple[str, ...]


@dataclass(frozen=True)
class MMMRequest:
    kpi: str
    channels: tuple[str, ...]
    date_start: str
    date_end: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kpi": self.kpi,
            "channels": list(self.channels),
            "date_start": self.date_start,
            "date_end": self.date_end,
        }


def load_dataset_spec(config_path: Path) -> DatasetSpec:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return DatasetSpec(target_column=config["target_column"], channels=tuple(config["channels"]))


def validate_request(
    *,
    model: str,
    kpi: str,
    channels: list[str],
    date_range: str,
    spec: DatasetSpec,
) -> MMMRequest:
    if model.strip().lower() != MODEL_FAMILY:
        raise RequestError(f"model '{model}' is not supported yet; only '{MODEL_FAMILY}' can be trained")
    if kpi.strip().lower() != spec.target_column.lower():
        raise RequestError(f"kpi '{kpi}' is not available; the sample dataset models '{spec.target_column}'")

    by_key = {name.lower(): name for name in spec.channels}
    resolved: list[str] = []
    unknown: list[str] = []
    for channel in channels:
        canonical = by_key.get(channel.strip().lower())
        if canonical is None:
            unknown.append(channel)
        elif canonical not in resolved:
            resolved.append(canonical)
    if unknown:
        raise RequestError(
            f"unknown channel(s) {', '.join(unknown)}; choose from: {', '.join(spec.channels)}"
        )
    if not resolved:
        raise RequestError("at least one channel is required")

    match = DATE_RANGE_RE.match(date_range or "")
    if match is None:
        raise RequestError("date_range must look like 'YYYY-MM-DD to YYYY-MM-DD'")
    try:
        start, end = (date.fromisoformat(value) for value in match.groups())
    except ValueError as exc:
        raise RequestError(f"date_range has an invalid date: {exc}") from exc
    if start > end:
        raise RequestError("date_range start must be on or before its end")

    return MMMRequest(
        kpi=spec.target_column,
        channels=tuple(resolved),
        date_start=start.isoformat(),
        date_end=end.isoformat(),
    )
