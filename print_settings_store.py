from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Literal, TypedDict


NumberType = Literal["int", "float"]


class PrintSettingField(TypedDict):
    id: str
    label: str
    type: Literal["boolean", "number"]
    number_type: NumberType
    step: float
    min: float
    max: float


PrintSettings = Dict[str, bool | int | float]


DEFAULT_PRINT_SETTINGS: PrintSettings = {
    "dither_enabled": True,
    "threshold": 140,
    "contrast": 2.0,
    "unsharp_radius": 1.0,
    "unsharp_percent": 150,
    "unsharp_threshold": 3,
    "gamma": 1.8,
}


PRINT_SETTING_FIELDS: List[PrintSettingField] = [
    {
        "id": "dither_enabled",
        "label": "Dithering",
        "type": "boolean",
        "number_type": "int",
        "step": 1.0,
        "min": 0.0,
        "max": 1.0,
    },
    {
        "id": "threshold",
        "label": "Threshold",
        "type": "number",
        "number_type": "int",
        "step": 1.0,
        "min": 0.0,
        "max": 255.0,
    },
    {
        "id": "contrast",
        "label": "Contrast",
        "type": "number",
        "number_type": "float",
        "step": 0.1,
        "min": 0.5,
        "max": 4.0,
    },
    {
        "id": "unsharp_radius",
        "label": "Unsharp Radius",
        "type": "number",
        "number_type": "float",
        "step": 0.1,
        "min": 0.0,
        "max": 5.0,
    },
    {
        "id": "unsharp_percent",
        "label": "Unsharp Percent",
        "type": "number",
        "number_type": "int",
        "step": 5.0,
        "min": 0.0,
        "max": 500.0,
    },
    {
        "id": "unsharp_threshold",
        "label": "Unsharp Threshold",
        "type": "number",
        "number_type": "int",
        "step": 1.0,
        "min": 0.0,
        "max": 255.0,
    },
    {
        "id": "gamma",
        "label": "Gamma",
        "type": "number",
        "number_type": "float",
        "step": 0.1,
        "min": 0.2,
        "max": 5.0,
    },
]


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return min(max_value, max(min_value, value))


def _coerce_value(field: PrintSettingField, value: Any) -> bool | int | float | None:
    field_type = field["type"]
    if field_type == "boolean":
        if isinstance(value, bool):
            return value
        return None

    if field_type == "number":
        if not _is_number(value):
            return None
        numeric = _clamp(float(value), field["min"], field["max"])
        if field["number_type"] == "int":
            return int(round(numeric))
        return float(numeric)

    return None


def normalize_print_settings(raw: Any) -> PrintSettings:
    normalized: PrintSettings = dict(DEFAULT_PRINT_SETTINGS)
    if not isinstance(raw, dict):
        return normalized

    for field in PRINT_SETTING_FIELDS:
        field_id = field["id"]
        coerced = _coerce_value(field, raw.get(field_id))
        if coerced is not None:
            normalized[field_id] = coerced

    return normalized


def load_print_settings(path: Path) -> PrintSettings:
    settings = dict(DEFAULT_PRINT_SETTINGS)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        settings = normalize_print_settings(raw)
    except FileNotFoundError:
        pass
    except Exception as exc:
        print(f"Failed to load print settings, using defaults: {exc}")

    save_print_settings(path, settings)
    return settings


def save_print_settings(path: Path, settings: PrintSettings) -> None:
    normalized = normalize_print_settings(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
