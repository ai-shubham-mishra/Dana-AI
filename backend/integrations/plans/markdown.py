"""Bulleted markdown format for a saved plan. Parsing returns a raw spec; the store validates it with MMMPlan."""

import re
from datetime import date
from typing import Any

NONE_VALUES = frozenset({"", "none", "-"})
SECTION_KEYS = {
    "kpi": "kpi",
    "channels": "channels",
    "controls": "controls",
    "controlsreason": "controls_reason",
    "window": "window",
    "sources": "sources",
    "preparation": "preparation",
    "overrides": "overrides",
}
PREPARATION_KEYS = {
    "texttonumeric": "text_to_numeric",
    "datefeatures": "date_features",
    "holidaycountry": "holiday_country",
    "lags": "lags",
    "rollingmeans": "rolling_means",
    "combinechannels": "combine_channels",
}
SOURCE_KEYS = {"datecolumn": "date_column", "metrics": "metrics", "filters": "filters"}
BULLET_RE = re.compile(r"^(\s*)[-*]\s+(.*)$")


class InvalidPlan(ValueError):
    pass


def _key(raw: str) -> str:
    return re.sub(r"[\s_\-]", "", raw).lower()


def _split_line(line_no: int, text: str) -> tuple[str, str]:
    if ":" not in text:
        raise InvalidPlan(f"line {line_no}: expected 'Name: value', got '{text}'")
    key, value = text.split(":", 1)
    return key.strip(), value.strip()


def _items(value: str) -> list[str]:
    return [] if _key(value) in NONE_VALUES else [part.strip() for part in value.split(",") if part.strip()]


def _pairs(line_no: int, value: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in value.split(";"):
        if not part.strip():
            continue
        if "=" not in part:
            raise InvalidPlan(f"line {line_no}: expected 'output=value' pairs separated by ';', got '{part.strip()}'")
        name, target = part.split("=", 1)
        result[name.strip()] = target.strip()
    return result


def _ints(line_no: int, text: str) -> list[int]:
    try:
        return [int(part) for part in _items(text)]
    except ValueError as exc:
        raise InvalidPlan(f"line {line_no}: '{text}' must be whole numbers separated by commas") from exc


def _int(line_no: int, text: str) -> int:
    try:
        return int(text)
    except ValueError as exc:
        raise InvalidPlan(f"line {line_no}: '{text}' must be a whole number") from exc


def _scalar(text: str) -> Any:
    lowered = text.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    try:
        return int(text)
    except ValueError:
        return text


def _window(line_no: int, value: str) -> tuple[str, str]:
    parts = re.split(r"\s+to\s+", value.strip())
    if len(parts) != 2:
        raise InvalidPlan(f"line {line_no}: window must be 'YYYY-MM-DD to YYYY-MM-DD'")
    try:
        return date.fromisoformat(parts[0]).isoformat(), date.fromisoformat(parts[1]).isoformat()
    except ValueError as exc:
        raise InvalidPlan(f"line {line_no}: window dates must be YYYY-MM-DD") from exc


def parse_plan_markdown(text: str) -> dict[str, Any]:
    raw: dict[str, Any] = {"preparation": {}, "overrides": {}, "sources": []}
    section: str | None = None
    source: dict[str, Any] | None = None
    for line_no, line in enumerate((text or "").splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = BULLET_RE.match(line)
        if match is None:
            raise InvalidPlan(f"line {line_no}: every line must be a bullet starting with '- '")
        indent = len(match.group(1).expandtabs(4))
        key, value = _split_line(line_no, match.group(2))
        name = _key(key)
        if indent == 0:
            section = SECTION_KEYS.get(name)
            source = None
            if section is None:
                raise InvalidPlan(f"line {line_no}: unknown field '{key}'")
            if section == "kpi":
                raw["kpi"] = value
            elif section == "channels":
                raw["channels"] = _items(value)
            elif section == "controls":
                raw["controls"] = _items(value)
            elif section == "controls_reason":
                raw["controls_reason"] = value
            elif section == "window":
                raw["date_start"], raw["date_end"] = _window(line_no, value)
        elif section == "sources" and indent == 2:
            if name != "table":
                raise InvalidPlan(f"line {line_no}: a source must start with 'Table:'")
            source = {"table": value, "filters": {}}
            raw["sources"].append(source)
        elif section == "sources" and indent >= 4:
            if source is None:
                raise InvalidPlan(f"line {line_no}: '{key}' must follow a 'Table:' line")
            field = SOURCE_KEYS.get(name)
            if field is None:
                raise InvalidPlan(f"line {line_no}: unknown source field '{key}'")
            source[field] = value if field == "date_column" else _pairs(line_no, value)
        elif section == "preparation" and indent == 2:
            field = PREPARATION_KEYS.get(name)
            if field is None:
                raise InvalidPlan(f"line {line_no}: unknown preparation field '{key}'")
            if field in ("lags", "rolling_means", "combine_channels"):
                pairs = _pairs(line_no, value)
                if field == "lags":
                    raw["preparation"][field] = {k: _ints(line_no, v) for k, v in pairs.items()}
                elif field == "rolling_means":
                    raw["preparation"][field] = {k: _int(line_no, v) for k, v in pairs.items()}
                else:
                    raw["preparation"][field] = {k: _items(v) for k, v in pairs.items()}
            elif field == "holiday_country":
                raw["preparation"][field] = None if _key(value) in NONE_VALUES else value
            else:
                raw["preparation"][field] = _items(value)
        elif section == "overrides" and indent == 2:
            raw["overrides"][key] = _scalar(value)
        else:
            raise InvalidPlan(f"line {line_no}: '{key}' is not in a section that accepts it")

    missing = [field for field in ("kpi", "channels", "date_start", "date_end") if field not in raw]
    if missing:
        raise InvalidPlan(f"the plan is missing: {', '.join(missing)}")
    if not raw["sources"]:
        raise InvalidPlan("the plan needs at least one source under 'Sources:'")
    for index, src in enumerate(raw["sources"], start=1):
        absent = [field for field in ("date_column", "metrics") if field not in src]
        if absent:
            raise InvalidPlan(f"source {index} is missing: {', '.join(absent)}")
    return raw


def _join_pairs(pairs: dict[str, Any]) -> str:
    return "; ".join(f"{name}={','.join(map(str, v)) if isinstance(v, list) else v}" for name, v in pairs.items())


def render_plan_markdown(spec: dict[str, Any]) -> str:
    lines = [
        f"- KPI: {spec['kpi']}",
        f"- Channels: {', '.join(spec['channels'])}",
        f"- Controls: {', '.join(spec.get('controls') or []) or 'none'}",
    ]
    if spec.get("controls_reason"):
        lines.append(f"- Controls reason: {spec['controls_reason']}")
    lines.append(f"- Window: {spec['date_start']} to {spec['date_end']}")
    lines.append("- Sources:")
    for src in spec["sources"]:
        lines.append(f"  - Table: {src['table']}")
        lines.append(f"    - Date column: {src['date_column']}")
        lines.append(f"    - Metrics: {_join_pairs(src['metrics'])}")
        if src.get("filters"):
            lines.append(f"    - Filters: {_join_pairs(src['filters'])}")
    prep = spec.get("preparation") or {}
    lines.append("- Preparation:")
    if prep.get("text_to_numeric"):
        lines.append(f"  - Text to numeric: {', '.join(prep['text_to_numeric'])}")
    if prep.get("date_features"):
        lines.append(f"  - Date features: {', '.join(prep['date_features'])}")
    if prep.get("holiday_country"):
        lines.append(f"  - Holiday country: {prep['holiday_country']}")
    if prep.get("lags"):
        lines.append(f"  - Lags: {_join_pairs(prep['lags'])}")
    if prep.get("rolling_means"):
        lines.append(f"  - Rolling means: {_join_pairs(prep['rolling_means'])}")
    if prep.get("combine_channels"):
        lines.append(f"  - Combine channels: {_join_pairs(prep['combine_channels'])}")
    lines.append("- Overrides:")
    for name, value in (spec.get("overrides") or {}).items():
        rendered = str(value).lower() if isinstance(value, bool) else value
        lines.append(f"  - {name}: {rendered}")
    return "\n".join(lines) + "\n"
