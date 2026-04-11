from card_query_engine import build_filter_where


def test_returns_true_clause_when_no_rules() -> None:
    where_sql, params = build_filter_where([], {})
    assert where_sql == "1=1"
    assert params == []


def test_any_enabled_builds_or_clause(sample_settings_schema, sample_settings) -> None:
    where_sql, params = build_filter_where(sample_settings_schema, sample_settings)

    assert "json_each" in where_sql
    assert " OR " not in where_sql  # only one enabled card_type field
    assert params == ["Creature", "modern", "legal"]


def test_selected_field_rule_handles_boolean_keys() -> None:
    schema = [
        {
            "id": "double_sided",
            "advanced_fields": [
                {"id": "double_sided", "type": "boolean", "default": False}
            ],
            "filter": {
                "mode": "selected_field_rule",
                "selected_field": "double_sided",
                "field_rules": {
                    "true": {"op": "not_null", "column": "card_faces"},
                    "false": {"op": "is_null", "column": "card_faces"},
                },
            },
        }
    ]

    where_sql, _ = build_filter_where(schema, {"double_sided": {"double_sided": True}})
    assert "IS NOT NULL" in where_sql


def test_active_card_list_disables_other_filters() -> None:
    schema = [
        {
            "id": "card_list",
            "advanced_fields": [{"id": "list_id", "type": "string", "default": "na"}],
            "filter": {
                "mode": "selected_field_rule",
                "selected_field": "list_id",
                "field_rules": {
                    "tribal": {"op": "name_in_list", "column": "name", "list_id": "tribal"}
                },
            },
        },
        {
            "id": "format",
            "advanced_fields": [{"id": "format", "type": "string", "default": "modern"}],
            "filter": {
                "mode": "selected_field_rule",
                "selected_field": "format",
                "field_rules": {
                    "modern": {
                        "op": "json_object_key_eq",
                        "column": "legalities",
                        "key": "modern",
                        "value": "legal",
                    }
                },
            },
        },
    ]
    settings = {"card_list": {"list_id": "tribal"}, "format": {"format": "modern"}}

    where_sql, params = build_filter_where(schema, settings)

    assert "card_lists" in where_sql
    assert "json_extract" not in where_sql
    assert params == ["tribal"]


def test_invalid_filter_rule_is_ignored() -> None:
    schema = [
        {
            "id": "bad_setting",
            "advanced_fields": [{"id": "x", "type": "boolean", "default": True}],
            "filter": {
                "mode": "any_enabled",
                "field_rules": {
                    "x": {"op": "eq", "column": "totally_invalid_column", "value": "x"}
                },
            },
        }
    ]

    where_sql, params = build_filter_where(schema, {"bad_setting": {"x": True}})
    assert where_sql == "1=1"
    assert params == []
