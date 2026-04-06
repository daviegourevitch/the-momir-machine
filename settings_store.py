from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


JSONValue = bool | int | float | str


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _coerce_for_field(value: Any, field: Dict[str, Any]) -> JSONValue | None:
    field_type = field["type"]
    if field_type == "boolean":
        return value if isinstance(value, bool) else None

    if field_type == "number":
        return value if _is_number(value) else None

    if field_type == "string":
        if not isinstance(value, str):
            return None
        options = field.get("options")
        if isinstance(options, list) and options and value not in options:
            return None
        return value

    return None


def _validate_field(field: Any) -> Dict[str, Any] | None:
    if not isinstance(field, dict):
        return None

    field_id = field.get("id")
    if not isinstance(field_id, str) or not field_id.strip():
        return None

    field_type = field.get("type")
    if field_type not in ("boolean", "number", "string"):
        return None

    clean: Dict[str, Any] = {
        "id": field_id,
        "label": field.get("label") if isinstance(field.get("label"), str) else field_id,
        "type": field_type,
    }

    default = _coerce_for_field(field.get("default"), clean)
    if default is None:
        if field_type == "boolean":
            default = False
        elif field_type == "number":
            default = 0
        else:
            default = ""
    clean["default"] = default

    if field_type == "number":
        step = field.get("step", 1)
        clean["step"] = step if _is_number(step) and step != 0 else 1
    elif field_type == "string":
        options = field.get("options")
        if isinstance(options, list):
            clean_options = [opt for opt in options if isinstance(opt, str)]
            if clean_options:
                clean["options"] = clean_options
                if clean["default"] not in clean_options:
                    clean["default"] = clean_options[0]

    return clean


def _validate_quick_option(
    option: Any, field_map: Dict[str, Dict[str, Any]], field_order: List[str]
) -> Dict[str, Any] | None:
    if not isinstance(option, dict):
        return None
    opt_id = option.get("id")
    if not isinstance(opt_id, str) or not opt_id.strip():
        return None

    values = option.get("values")
    if not isinstance(values, dict):
        return None

    normalized_values: Dict[str, JSONValue] = {}
    for field_id in field_order:
        field = field_map[field_id]
        if field_id not in values:
            return None
        coerced = _coerce_for_field(values[field_id], field)
        if coerced is None:
            return None
        normalized_values[field_id] = coerced

    return {
        "id": opt_id,
        "label": option.get("label") if isinstance(option.get("label"), str) else opt_id,
        "values": normalized_values,
    }


def _validate_setting(setting: Any) -> Dict[str, Any] | None:
    if not isinstance(setting, dict):
        return None

    setting_id = setting.get("id")
    if not isinstance(setting_id, str) or not setting_id.strip():
        return None

    raw_fields = setting.get("advanced_fields")
    if not isinstance(raw_fields, list) or not raw_fields:
        return None

    fields: List[Dict[str, Any]] = []
    field_ids: set[str] = set()
    for raw_field in raw_fields:
        clean_field = _validate_field(raw_field)
        if clean_field is None:
            continue
        if clean_field["id"] in field_ids:
            continue
        fields.append(clean_field)
        field_ids.add(clean_field["id"])

    if not fields:
        return None

    field_map = {field["id"]: field for field in fields}
    field_order = [field["id"] for field in fields]

    quick_options: List[Dict[str, Any]] = []
    raw_quick_options = setting.get("quick_options")
    if isinstance(raw_quick_options, list):
        for raw_option in raw_quick_options:
            clean_option = _validate_quick_option(raw_option, field_map, field_order)
            if clean_option is not None:
                quick_options.append(clean_option)

    clean_setting: Dict[str, Any] = {
        "id": setting_id,
        "label": setting.get("label") if isinstance(setting.get("label"), str) else setting_id,
        "advanced_fields": fields,
        "quick_options": quick_options,
    }
    return clean_setting


def fallback_schema() -> List[Dict[str, Any]]:
    return [
        {
            "id": "card_type",
            "label": "Card Type",
            "quick_options": [
                {
                    "id": "all_cards",
                    "label": "All cards",
                    "values": {
                        "creature": True,
                        "instant": True,
                        "sorcery": True,
                        "artifact": True,
                        "enchantment": True,
                        "planeswalker": True,
                    },
                }
            ],
            "advanced_fields": [
                {"id": "creature", "label": "Creature", "type": "boolean", "default": True},
                {"id": "instant", "label": "Instant", "type": "boolean", "default": True},
                {"id": "sorcery", "label": "Sorcery", "type": "boolean", "default": True},
                {"id": "artifact", "label": "Artifact", "type": "boolean", "default": True},
                {"id": "enchantment", "label": "Enchantment", "type": "boolean", "default": True},
                {"id": "planeswalker", "label": "Planeswalker", "type": "boolean", "default": True},
            ],
        }
    ]


def load_menu_schema(menu_schema_path: Path) -> List[Dict[str, Any]]:
    try:
        raw = json.loads(menu_schema_path.read_text(encoding="utf-8"))
        settings = raw.get("settings", [])
        if not isinstance(settings, list) or not settings:
            raise ValueError("settings must be a non-empty list")
        validated = validate_menu_items(settings)
        return validated if validated else fallback_schema()
    except Exception as exc:
        print(f"Failed to load menu schema, using fallback schema: {exc}")
        return fallback_schema()


def validate_menu_items(items: List[Any]) -> List[Dict[str, Any]]:
    validated: List[Dict[str, Any]] = []
    used_ids: set[str] = set()
    for item in items:
        clean_item = _validate_setting(item)
        if clean_item is None:
            continue
        if clean_item["id"] in used_ids:
            continue
        validated.append(clean_item)
        used_ids.add(clean_item["id"])
    return validated


def build_default_settings(items: List[Dict[str, Any]]) -> Dict[str, Dict[str, JSONValue]]:
    defaults: Dict[str, Dict[str, JSONValue]] = {}
    for item in items:
        setting_id = str(item["id"])
        setting_defaults: Dict[str, JSONValue] = {}
        for field in item.get("advanced_fields", []):
            setting_defaults[field["id"]] = field["default"]
        defaults[setting_id] = setting_defaults
    return defaults


def load_settings(
    settings_path: Path,
    defaults: Dict[str, Dict[str, JSONValue]],
    schema: List[Dict[str, Any]],
) -> Dict[str, Dict[str, JSONValue]]:
    settings: Dict[str, Dict[str, JSONValue]] = {
        setting_id: dict(values) for setting_id, values in defaults.items()
    }
    schema_map = {item["id"]: item for item in schema}

    try:
        raw = json.loads(settings_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            for setting_id, raw_setting_values in raw.items():
                if setting_id not in settings or not isinstance(raw_setting_values, dict):
                    continue
                setting_schema = schema_map.get(setting_id)
                if setting_schema is None:
                    continue
                field_map = {
                    field["id"]: field
                    for field in setting_schema.get("advanced_fields", [])
                }
                for field_id, raw_value in raw_setting_values.items():
                    field = field_map.get(field_id)
                    if field is None:
                        continue
                    coerced = _coerce_for_field(raw_value, field)
                    if coerced is not None:
                        settings[setting_id][field_id] = coerced
    except FileNotFoundError:
        pass
    except Exception as exc:
        print(f"Failed to load saved settings, using defaults: {exc}")

    save_settings(settings_path, settings)
    return settings


def save_settings(
    settings_path: Path, settings: Dict[str, Dict[str, JSONValue]]
) -> None:
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def quick_option_index(
    setting_def: Dict[str, Any], values: Dict[str, JSONValue]
) -> int:
    field_ids = [field["id"] for field in setting_def.get("advanced_fields", [])]
    for idx, option in enumerate(setting_def.get("quick_options", [])):
        option_values = option.get("values", {})
        if all(values.get(field_id) == option_values.get(field_id) for field_id in field_ids):
            return idx
    return -1


def quick_option_label(
    setting_def: Dict[str, Any], values: Dict[str, JSONValue]
) -> str:
    idx = quick_option_index(setting_def, values)
    if idx < 0:
        return "Custom"
    quick_options = setting_def.get("quick_options", [])
    return str(quick_options[idx].get("label", "Custom"))
