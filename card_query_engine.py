from __future__ import annotations

from typing import Any, Dict, List, Tuple

from card_lists import CARD_LIST_SETTING_ID, selected_card_list_id


SQLParams = List[Any]
SQLParts = Tuple[str, SQLParams]

# Keep a strict allow-list so schema-defined filters cannot target arbitrary SQL identifiers.
ALLOWED_CARD_COLUMNS = {
    "arena_id",
    "artist",
    "artist_ids",
    "attraction_lights",
    "booster",
    "border_color",
    "card_back_id",
    "card_faces",
    "card_types",
    "cardmarket_id",
    "cmc",
    "collector_number",
    "color_identity",
    "color_indicator",
    "colors",
    "content_warning",
    "defense",
    "digital",
    "edhrec_rank",
    "finishes",
    "flavor_name",
    "flavor_text",
    "frame",
    "frame_effects",
    "full_art",
    "game_changer",
    "games",
    "hand_modifier",
    "highres_image",
    "id",
    "illustration_id",
    "image_status",
    "image_uris",
    "keywords",
    "lang",
    "layout",
    "legalities",
    "life_modifier",
    "loyalty",
    "mana_cost",
    "mtgo_foil_id",
    "mtgo_id",
    "multiverse_ids",
    "name",
    "object",
    "oracle_id",
    "oracle_text",
    "oversized",
    "penny_rank",
    "power",
    "printed_name",
    "printed_text",
    "printed_type_line",
    "prints_search_uri",
    "produced_mana",
    "promo",
    "promo_types",
    "rarity",
    "released_at",
    "reprint",
    "reserved",
    "rulings_uri",
    "scryfall_set_uri",
    "scryfall_uri",
    "security_stamp",
    "set",
    "set_id",
    "set_name",
    "set_search_uri",
    "set_type",
    "set_uri",
    "story_spotlight",
    "tcgplayer_etched_id",
    "tcgplayer_id",
    "textless",
    "toughness",
    "type_line",
    "uri",
    "variation",
    "variation_of",
    "watermark",
}


def _quote_column(column: str) -> str:
    if column not in ALLOWED_CARD_COLUMNS:
        raise ValueError(f"Unsupported filter column: {column}")
    return f'"{column}"'


def _rule_to_sql(rule: Dict[str, Any]) -> SQLParts:
    op = str(rule.get("op", ""))

    if op in ("and", "or"):
        rules = rule.get("rules", [])
        if not isinstance(rules, list) or not rules:
            raise ValueError(f"Invalid '{op}' rule")
        clauses: List[str] = []
        params: SQLParams = []
        for child in rules:
            child_sql, child_params = _rule_to_sql(child)
            clauses.append(f"({child_sql})")
            params.extend(child_params)
        joiner = " AND " if op == "and" else " OR "
        return joiner.join(clauses), params

    if op == "not":
        child = rule.get("rule")
        if not isinstance(child, dict):
            raise ValueError("Invalid 'not' rule")
        child_sql, child_params = _rule_to_sql(child)
        return f"NOT ({child_sql})", child_params

    column = _quote_column(str(rule.get("column", "")))

    if op == "is_null":
        return f"{column} IS NULL", []
    if op == "not_null":
        return f"{column} IS NOT NULL", []
    if op == "eq":
        return f"{column} = ?", [rule.get("value")]
    if op == "neq":
        return f"{column} != ?", [rule.get("value")]

    if op in ("in", "not_in"):
        values = rule.get("values", [])
        if not isinstance(values, list) or not values:
            raise ValueError(f"Invalid '{op}' values")
        placeholders = ", ".join("?" for _ in values)
        keyword = "IN" if op == "in" else "NOT IN"
        return f"{column} {keyword} ({placeholders})", list(values)

    if op == "json_array_contains":
        return (
            f"EXISTS (SELECT 1 FROM json_each({column}) AS item WHERE item.value = ?)",
            [rule.get("value")],
        )

    if op == "json_array_overlaps":
        values = rule.get("values", [])
        if not isinstance(values, list) or not values:
            raise ValueError("Invalid 'json_array_overlaps' values")
        placeholders = ", ".join("?" for _ in values)
        return (
            f"EXISTS (SELECT 1 FROM json_each({column}) AS item WHERE item.value IN ({placeholders}))",
            list(values),
        )

    if op == "json_object_key_eq":
        key = rule.get("key")
        value = rule.get("value")
        return f"json_extract({column}, '$.' || ?) = ?", [key, value]

    if op == "name_in_list":
        list_id = rule.get("list_id")
        if not isinstance(list_id, str) or not list_id:
            raise ValueError("Invalid 'name_in_list' list_id")
        return (
            "EXISTS ("
            "SELECT 1 FROM card_lists AS cl "
            f"WHERE cl.list_id = ? AND cl.card_name_lower = LOWER({column})"
            ")",
            [list_id],
        )

    raise ValueError(f"Unsupported filter operation: {op}")


def _field_map_for_setting(setting_schema: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    fields = setting_schema.get("advanced_fields", [])
    if not isinstance(fields, list):
        return {}
    mapping: Dict[str, Dict[str, Any]] = {}
    for field in fields:
        if isinstance(field, dict):
            field_id = field.get("id")
            if isinstance(field_id, str) and field_id:
                mapping[field_id] = field
    return mapping


def _rule_key_for_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def build_filter_where(
    settings_schema: List[Dict[str, Any]],
    settings: Dict[str, Dict[str, bool | int | float | str]],
) -> SQLParts:
    all_clauses: List[str] = []
    all_params: SQLParams = []
    active_card_list_id = selected_card_list_id(settings)

    for setting_schema in settings_schema:
        if not isinstance(setting_schema, dict):
            continue
        setting_id = str(setting_schema.get("id", ""))
        if active_card_list_id and setting_id != CARD_LIST_SETTING_ID:
            # Card-list mode intentionally ignores conflicting settings.
            continue
        filter_def = setting_schema.get("filter")
        if not isinstance(filter_def, dict):
            continue

        mode = filter_def.get("mode")
        field_rules = filter_def.get("field_rules")
        if not isinstance(mode, str) or not isinstance(field_rules, dict):
            continue

        setting_values = settings.get(setting_id, {})
        field_map = _field_map_for_setting(setting_schema)

        if mode == "any_enabled":
            setting_clauses: List[str] = []
            setting_params: SQLParams = []
            for field_id, field in field_map.items():
                if field.get("type") != "boolean":
                    continue
                if not bool(setting_values.get(field_id, field.get("default", False))):
                    continue
                rule = field_rules.get(field_id)
                if not isinstance(rule, dict):
                    continue
                try:
                    clause, params = _rule_to_sql(rule)
                except ValueError:
                    continue
                setting_clauses.append(f"({clause})")
                setting_params.extend(params)

            if setting_clauses:
                all_clauses.append("(" + " OR ".join(setting_clauses) + ")")
                all_params.extend(setting_params)
            continue

        if mode == "selected_field_rule":
            selected_field = filter_def.get("selected_field")
            if not isinstance(selected_field, str) or not selected_field:
                continue

            selected_value = setting_values.get(selected_field)
            if selected_value is None and selected_field in field_map:
                selected_value = field_map[selected_field].get("default")

            key = _rule_key_for_value(selected_value)
            rule = field_rules.get(key)
            if not isinstance(rule, dict):
                continue
            try:
                clause, params = _rule_to_sql(rule)
            except ValueError:
                continue
            all_clauses.append(f"({clause})")
            all_params.extend(params)
            continue

    if not all_clauses:
        return "1=1", []
    return " AND ".join(all_clauses), all_params
