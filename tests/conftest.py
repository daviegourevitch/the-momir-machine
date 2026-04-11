from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable

import pytest


@pytest.fixture
def sample_settings_schema() -> list[dict[str, Any]]:
    return [
        {
            "id": "card_type",
            "advanced_fields": [
                {"id": "creature", "type": "boolean", "default": True},
                {"id": "instant", "type": "boolean", "default": False},
            ],
            "filter": {
                "mode": "any_enabled",
                "field_rules": {
                    "creature": {
                        "op": "json_array_contains",
                        "column": "card_types",
                        "value": "Creature",
                    },
                    "instant": {
                        "op": "json_array_contains",
                        "column": "card_types",
                        "value": "Instant",
                    },
                },
            },
        },
        {
            "id": "format",
            "advanced_fields": [
                {
                    "id": "format",
                    "type": "string",
                    "default": "no_format",
                    "options": ["no_format", "modern", "pauper"],
                }
            ],
            "filter": {
                "mode": "selected_field_rule",
                "selected_field": "format",
                "field_rules": {
                    "modern": {
                        "op": "json_object_key_eq",
                        "column": "legalities",
                        "key": "modern",
                        "value": "legal",
                    },
                    "pauper": {
                        "op": "json_object_key_eq",
                        "column": "legalities",
                        "key": "pauper",
                        "value": "legal",
                    },
                },
            },
        },
    ]


@pytest.fixture
def sample_settings() -> dict[str, dict[str, bool | int | float | str]]:
    return {
        "card_type": {"creature": True, "instant": False},
        "format": {"format": "modern"},
        "card_list": {"list_id": "na"},
    }


def _init_cards_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE cards (
            id TEXT,
            name TEXT,
            cmc REAL,
            card_types TEXT,
            legalities TEXT,
            image_uris TEXT,
            card_faces TEXT,
            released_at TEXT,
            set_type TEXT,
            border_color TEXT
        );
        """
    )
    conn.execute("CREATE INDEX idx_cards_name ON cards(name);")
    conn.execute("CREATE INDEX idx_cards_cmc ON cards(cmc);")
    conn.execute(
        """
        CREATE TABLE card_lists (
            list_id TEXT NOT NULL,
            list_label TEXT NOT NULL,
            source_file TEXT NOT NULL,
            card_name_lower TEXT NOT NULL,
            PRIMARY KEY (list_id, card_name_lower)
        );
        """
    )


@pytest.fixture
def make_cards_db(tmp_path: Path):
    def _make(rows: Iterable[Dict[str, Any]]) -> Path:
        db_path = tmp_path / "cards.db"
        with sqlite3.connect(db_path) as conn:
            _init_cards_schema(conn)
            for row in rows:
                image_uris = row.get("image_uris")
                card_faces = row.get("card_faces")
                conn.execute(
                    """
                    INSERT INTO cards
                    (id, name, cmc, card_types, legalities, image_uris, card_faces, released_at, set_type, border_color)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        row.get("id", row["name"].lower().replace(" ", "_")),
                        row["name"],
                        row["cmc"],
                        json.dumps(row.get("card_types", [])),
                        json.dumps(row.get("legalities", {})),
                        json.dumps(image_uris) if image_uris is not None else None,
                        json.dumps(card_faces) if card_faces is not None else None,
                        row.get("released_at", "2020-01-01"),
                        row.get("set_type", "expansion"),
                        row.get("border_color", "black"),
                    ],
                )
            conn.commit()
        return db_path

    return _make
