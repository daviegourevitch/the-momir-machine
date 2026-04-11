from pathlib import Path

from settings_store import (
    build_default_settings,
    load_settings,
    quick_option_index,
    quick_option_label,
    validate_menu_items,
)


def test_validate_menu_items_filters_invalid_and_duplicate_settings() -> None:
    validated = validate_menu_items(
        [
            {"id": "bad_missing_fields"},
            {
                "id": "mode",
                "advanced_fields": [{"id": "flag", "type": "boolean", "default": True}],
                "quick_options": [
                    {"id": "on", "values": {"flag": True}},
                    {"id": "off", "values": {"flag": False}},
                ],
            },
            {
                "id": "mode",
                "advanced_fields": [{"id": "other", "type": "boolean", "default": True}],
            },
        ]
    )

    assert len(validated) == 1
    assert validated[0]["id"] == "mode"
    assert validated[0]["advanced_fields"][0]["id"] == "flag"


def test_load_settings_coerces_values_and_persists_normalized_data(tmp_path: Path) -> None:
    schema = validate_menu_items(
        [
            {
                "id": "format",
                "advanced_fields": [
                    {
                        "id": "format",
                        "type": "string",
                        "default": "no_format",
                        "options": ["no_format", "modern"],
                    }
                ],
                "quick_options": [
                    {"id": "none", "values": {"format": "no_format"}},
                    {"id": "modern", "values": {"format": "modern"}},
                ],
            }
        ]
    )
    defaults = build_default_settings(schema)
    path = tmp_path / "settings.json"
    path.write_text('{"format":{"format":"illegal_value"}}', encoding="utf-8")

    loaded = load_settings(path, defaults, schema)

    assert loaded == {"format": {"format": "no_format"}}
    serialized = path.read_text(encoding="utf-8")
    assert '"format": "no_format"' in serialized


def test_quick_option_index_and_label() -> None:
    setting = {
        "advanced_fields": [
            {"id": "a"},
            {"id": "b"},
        ],
        "quick_options": [
            {"label": "AB", "values": {"a": True, "b": False}},
            {"label": "BA", "values": {"a": False, "b": True}},
        ],
    }

    assert quick_option_index(setting, {"a": True, "b": False}) == 0
    assert quick_option_label(setting, {"a": False, "b": True}) == "BA"
    assert quick_option_label(setting, {"a": True, "b": True}) == "Custom"
