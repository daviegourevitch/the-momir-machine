from __future__ import annotations

import re
import sqlite3
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, TypedDict


CARD_LIST_SETTING_ID = "card_list"
CARD_LIST_FIELD_ID = "list_id"
NO_CARD_LIST_VALUE = "na"


class CardListInfo(TypedDict):
    id: str
    label: str
    file_name: str
    card_count: int


def ensure_card_lists_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS card_lists (
            list_id TEXT NOT NULL,
            list_label TEXT NOT NULL,
            source_file TEXT NOT NULL,
            card_name_lower TEXT NOT NULL,
            PRIMARY KEY (list_id, card_name_lower)
        );
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_card_lists_list_id ON card_lists(list_id);")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_card_lists_list_id_name "
        "ON card_lists(list_id, card_name_lower);"
    )


def _slugify(value: str) -> str:
    lowered = value.strip().lower()
    if not lowered:
        return "list"
    normalized = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    return normalized or "list"


def _label_from_stem(stem: str) -> str:
    words = [part for part in re.split(r"[_\-\s]+", stem.strip()) if part]
    if not words:
        return "Unnamed list"
    return " ".join(word.capitalize() for word in words)


def discover_card_lists(lists_dir: Path) -> List[CardListInfo]:
    if not lists_dir.is_dir():
        return []

    discovered: List[CardListInfo] = []
    used_ids: set[str] = set()
    for path in sorted(lists_dir.glob("*.txt"), key=lambda item: item.name.lower()):
        stem = path.stem.strip()
        base_id = _slugify(stem)
        list_id = base_id
        suffix = 2
        while list_id in used_ids:
            list_id = f"{base_id}_{suffix}"
            suffix += 1
        used_ids.add(list_id)

        card_names = read_list_card_names(path)
        discovered.append(
            {
                "id": list_id,
                "label": _label_from_stem(stem),
                "file_name": path.name,
                "card_count": len(card_names),
            }
        )
    return discovered


def read_list_card_names(path: Path) -> List[str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return []
    names = {
        line.strip().lower()
        for line in raw.splitlines()
        if line.strip()
    }
    return sorted(names)


def sync_card_lists(db_path: Path, lists_dir: Path) -> List[CardListInfo]:
    discovered = discover_card_lists(lists_dir)
    if not db_path.is_file():
        return discovered

    try:
        with sqlite3.connect(db_path) as conn:
            ensure_card_lists_schema(conn)
            list_ids = [entry["id"] for entry in discovered]
            if list_ids:
                placeholders = ", ".join("?" for _ in list_ids)
                conn.execute(
                    f"DELETE FROM card_lists WHERE list_id NOT IN ({placeholders});",
                    list_ids,
                )
            else:
                conn.execute("DELETE FROM card_lists;")

            for entry in discovered:
                list_id = entry["id"]
                source_path = lists_dir / entry["file_name"]
                names = read_list_card_names(source_path)
                conn.execute("DELETE FROM card_lists WHERE list_id = ?;", [list_id])
                if not names:
                    continue
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO card_lists
                    (list_id, list_label, source_file, card_name_lower)
                    VALUES (?, ?, ?, ?);
                    """,
                    [
                        (list_id, entry["label"], entry["file_name"], card_name)
                        for card_name in names
                    ],
                )
            conn.commit()
    except sqlite3.Error as exc:
        print(f"Card lists: failed to sync list files: {exc}")

    return discovered


def selected_card_list_id(
    settings: Dict[str, Dict[str, bool | int | float | str]],
) -> str | None:
    list_settings = settings.get(CARD_LIST_SETTING_ID, {})
    selected = list_settings.get(CARD_LIST_FIELD_ID, NO_CARD_LIST_VALUE)
    if not isinstance(selected, str):
        return None
    if selected == NO_CARD_LIST_VALUE:
        return None
    return selected


def apply_card_list_setting(
    settings_schema: List[Dict[str, Any]], discovered_lists: List[CardListInfo]
) -> List[Dict[str, Any]]:
    schema_copy = deepcopy(settings_schema)
    current = next(
        (setting for setting in schema_copy if setting.get("id") == CARD_LIST_SETTING_ID),
        None,
    )

    options = [NO_CARD_LIST_VALUE, *[entry["id"] for entry in discovered_lists]]
    quick_options: List[Dict[str, Any]] = [
        {
            "id": NO_CARD_LIST_VALUE,
            "label": "N/A",
            "values": {CARD_LIST_FIELD_ID: NO_CARD_LIST_VALUE},
        }
    ]
    quick_options.extend(
        {
            "id": entry["id"],
            "label": entry["label"],
            "values": {CARD_LIST_FIELD_ID: entry["id"]},
        }
        for entry in discovered_lists
    )

    field_rules = {
        entry["id"]: {"op": "name_in_list", "column": "name", "list_id": entry["id"]}
        for entry in discovered_lists
    }
    if not field_rules:
        # Placeholder rule keeps schema validation shape stable with no selected match.
        field_rules = {"__unused__": {"op": "eq", "column": "id", "value": "__unused__"}}

    setting = {
        "id": CARD_LIST_SETTING_ID,
        "label": "Card List",
        "show_advanced": False,
        "filter": {
            "mode": "selected_field_rule",
            "selected_field": CARD_LIST_FIELD_ID,
            "field_rules": field_rules,
        },
        "advanced_fields": [
            {
                "id": CARD_LIST_FIELD_ID,
                "label": "Card List",
                "type": "string",
                "default": NO_CARD_LIST_VALUE,
                "options": options,
            }
        ],
        "quick_options": quick_options,
    }
    if isinstance(current, dict):
        setting["label"] = str(current.get("label", setting["label"]))

    remaining = [
        item for item in schema_copy if str(item.get("id", "")) != CARD_LIST_SETTING_ID
    ]
    return [setting, *remaining]
