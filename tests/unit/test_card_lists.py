from pathlib import Path
import sqlite3

from card_lists import (
    CARD_LIST_FIELD_ID,
    CARD_LIST_SETTING_ID,
    NO_CARD_LIST_VALUE,
    apply_card_list_setting,
    discover_card_lists,
    selected_card_list_id,
    sync_card_lists,
)


def test_discover_card_lists_generates_unique_ids_and_labels(tmp_path: Path) -> None:
    (tmp_path / "alpha list.txt").write_text("Card A\nCard B\n", encoding="utf-8")
    (tmp_path / "alpha-list.txt").write_text("Card C\n", encoding="utf-8")

    discovered = discover_card_lists(tmp_path)

    assert [entry["id"] for entry in discovered] == ["alpha_list", "alpha_list_2"]
    assert [entry["label"] for entry in discovered] == ["Alpha List", "Alpha List"]
    assert discovered[0]["card_count"] == 2


def test_selected_card_list_id_returns_none_for_na() -> None:
    assert selected_card_list_id({CARD_LIST_SETTING_ID: {CARD_LIST_FIELD_ID: NO_CARD_LIST_VALUE}}) is None
    assert selected_card_list_id({CARD_LIST_SETTING_ID: {CARD_LIST_FIELD_ID: "my_list"}}) == "my_list"


def test_apply_card_list_setting_inserts_first_entry() -> None:
    schema = [{"id": "format", "label": "Format", "advanced_fields": [{"id": "x"}]}]
    discovered = [{"id": "my_list", "label": "My List", "file_name": "my-list.txt", "card_count": 1}]

    updated = apply_card_list_setting(schema, discovered)

    assert updated[0]["id"] == CARD_LIST_SETTING_ID
    assert updated[1]["id"] == "format"
    options = updated[0]["advanced_fields"][0]["options"]
    assert options == [NO_CARD_LIST_VALUE, "my_list"]


def test_sync_card_lists_writes_names_to_database(tmp_path: Path) -> None:
    lists_dir = tmp_path / "lists"
    lists_dir.mkdir()
    (lists_dir / "tribal.txt").write_text("Goblin Guide\nGoblin Guide\nLlanowar Elves\n", encoding="utf-8")
    db_path = tmp_path / "cards.db"
    with sqlite3.connect(db_path):
        pass

    synced = sync_card_lists(db_path, lists_dir)

    assert len(synced) == 1
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT list_id, card_name_lower FROM card_lists ORDER BY card_name_lower;"
        ).fetchall()
    assert rows == [("tribal", "goblin guide"), ("tribal", "llanowar elves")]
