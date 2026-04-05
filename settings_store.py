from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def load_menu_schema(menu_schema_path: Path) -> List[Dict[str, Any]]:
    fallback_menu: List[Dict[str, Any]] = [
        {"id": "option_a", "label": "Option A", "default": True},
        {"id": "option_b", "label": "Option B", "default": False},
    ]
    try:
        raw = json.loads(menu_schema_path.read_text(encoding="utf-8"))
        items = raw.get("menu", [])
        if not isinstance(items, list) or not items:
            raise ValueError("menu must be a non-empty list")
        validated = validate_menu_items(items)
        return validated if validated else fallback_menu
    except Exception as exc:
        print(f"Failed to load menu schema, using fallback menu: {exc}")
        return fallback_menu


def validate_menu_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    validated: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            continue
        label = item.get("label") if isinstance(item.get("label"), str) else item_id
        default = bool(item.get("default", False))
        clean: Dict[str, Any] = {"id": item_id, "label": label, "default": default}
        submenu = item.get("submenu")
        if isinstance(submenu, list):
            child_items = validate_menu_items(submenu)
            if child_items:
                clean["submenu"] = child_items
        validated.append(clean)
    return validated


def build_default_settings(
    items: List[Dict[str, Any]], prefix: str = ""
) -> Dict[str, bool]:
    defaults: Dict[str, bool] = {}
    for item in items:
        key = f"{prefix}.{item['id']}" if prefix else item["id"]
        defaults[key] = bool(item.get("default", False))
        submenu = item.get("submenu")
        if isinstance(submenu, list) and submenu:
            defaults.update(build_default_settings(submenu, key))
    return defaults


def load_settings(settings_path: Path, defaults: Dict[str, bool]) -> Dict[str, bool]:
    settings = dict(defaults)
    try:
        raw = json.loads(settings_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            for key, value in raw.items():
                if key in settings and isinstance(value, bool):
                    settings[key] = value
    except FileNotFoundError:
        pass
    except Exception as exc:
        print(f"Failed to load saved settings, using defaults: {exc}")
    save_settings(settings_path, settings)
    return settings


def save_settings(settings_path: Path, settings: Dict[str, bool]) -> None:
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
