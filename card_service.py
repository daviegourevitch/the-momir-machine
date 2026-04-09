from __future__ import annotations

import json
import random
import sqlite3
from json import dumps
from pathlib import Path
from typing import Any, Dict, List, TypedDict

from card_query_engine import build_filter_where


ManaValue = int | float
RuntimeCache = Dict[str, Any]


class RandomCard(TypedDict):
    name: str
    image_url: str | None


class CardService:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._cache_signature: str | None = None
        self._cached_available_mana: List[ManaValue] = []
        self._cached_cards_by_mana: Dict[ManaValue, List[str]] = {}

    def has_database(self) -> bool:
        return self.db_path.is_file()

    @staticmethod
    def _normalize_mana_value(raw_value: object) -> ManaValue | None:
        if not isinstance(raw_value, (int, float)):
            return None
        numeric = float(raw_value)
        if numeric.is_integer():
            return int(numeric)
        return numeric

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _settings_signature(
        settings: Dict[str, Dict[str, bool | int | float | str]],
    ) -> str:
        return dumps(settings, sort_keys=True, separators=(",", ":"))

    def _build_runtime_cache_preview(
        self,
        settings_schema: List[Dict[str, object]],
        settings: Dict[str, Dict[str, bool | int | float | str]],
    ) -> RuntimeCache:
        signature = self._settings_signature(settings)
        cards_by_mana: Dict[ManaValue, List[str]] = {}
        available: List[ManaValue] = []
        seen: set[ManaValue] = set()
        if not self.has_database():
            return {
                "signature": signature,
                "available_mana_values": [],
                "cards_by_mana": {},
            }

        where_sql, where_params = build_filter_where(settings_schema, settings)
        sql = (
            f'SELECT "cmc", "name" FROM cards '
            f'WHERE "cmc" IS NOT NULL AND "name" IS NOT NULL AND ({where_sql});'
        )

        try:
            with self._connect() as conn:
                for row in conn.execute(sql, where_params):
                    mana_value = self._normalize_mana_value(row["cmc"])
                    name_value = row["name"]
                    if mana_value is None or not isinstance(name_value, str):
                        continue
                    if mana_value not in cards_by_mana:
                        cards_by_mana[mana_value] = []
                    cards_by_mana[mana_value].append(name_value)
                    if mana_value not in seen:
                        seen.add(mana_value)
                        available.append(mana_value)
        except sqlite3.Error as exc:
            print(f"CardService: failed to build runtime cache: {exc}")
            return {
                "signature": signature,
                "available_mana_values": [],
                "cards_by_mana": {},
            }

        available.sort()
        return {
            "signature": signature,
            "available_mana_values": available,
            "cards_by_mana": cards_by_mana,
        }

    def apply_runtime_cache_preview(self, preview: RuntimeCache) -> None:
        signature = preview.get("signature")
        available = preview.get("available_mana_values")
        cards_by_mana = preview.get("cards_by_mana")
        if not isinstance(signature, str):
            return
        if not isinstance(available, list):
            return
        if not isinstance(cards_by_mana, dict):
            return
        self._cache_signature = signature
        self._cached_available_mana = list(available)
        self._cached_cards_by_mana = {
            mana: list(names)
            for mana, names in cards_by_mana.items()
            if isinstance(mana, (int, float)) and isinstance(names, list)
        }

    def warm_runtime_cache(
        self,
        settings_schema: List[Dict[str, object]],
        settings: Dict[str, Dict[str, bool | int | float | str]],
    ) -> List[ManaValue]:
        preview = self._build_runtime_cache_preview(settings_schema, settings)
        self.apply_runtime_cache_preview(preview)
        return list(self._cached_available_mana)

    def preview_runtime_cache(
        self,
        settings_schema: List[Dict[str, object]],
        settings: Dict[str, Dict[str, bool | int | float | str]],
    ) -> RuntimeCache:
        return self._build_runtime_cache_preview(settings_schema, settings)

    def has_runtime_cache_for(
        self, settings: Dict[str, Dict[str, bool | int | float | str]]
    ) -> bool:
        return self._cache_signature == self._settings_signature(settings)

    def get_available_mana_values(
        self,
        settings_schema: List[Dict[str, object]],
        settings: Dict[str, Dict[str, bool | int | float | str]],
    ) -> List[ManaValue]:
        if self.has_runtime_cache_for(settings):
            return list(self._cached_available_mana)
        if not self.has_database():
            return []

        where_sql, where_params = build_filter_where(settings_schema, settings)
        sql = (
            f'SELECT DISTINCT "cmc" FROM cards '
            f'WHERE "cmc" IS NOT NULL AND ({where_sql}) '
            f'ORDER BY "cmc" ASC;'
        )

        values: List[ManaValue] = []
        seen: set[ManaValue] = set()
        try:
            with self._connect() as conn:
                for row in conn.execute(sql, where_params):
                    mana_value = self._normalize_mana_value(row["cmc"])
                    if mana_value is None or mana_value in seen:
                        continue
                    seen.add(mana_value)
                    values.append(mana_value)
        except sqlite3.Error as exc:
            print(f"CardService: failed to load available mana values: {exc}")
            return []

        return values

    def get_random_card_name(
        self,
        mana_value: ManaValue,
        settings_schema: List[Dict[str, object]],
        settings: Dict[str, Dict[str, bool | int | float | str]],
    ) -> str | None:
        card = self.get_random_card(mana_value, settings_schema, settings)
        if card is None:
            return None
        return card["name"]

    @staticmethod
    def _decode_json_object(raw_value: object) -> Dict[str, Any]:
        if isinstance(raw_value, dict):
            return raw_value
        if not isinstance(raw_value, str) or not raw_value:
            return {}
        try:
            decoded = json.loads(raw_value)
        except json.JSONDecodeError:
            return {}
        if isinstance(decoded, dict):
            return decoded
        return {}

    @staticmethod
    def _decode_json_array(raw_value: object) -> List[Dict[str, Any]]:
        if isinstance(raw_value, list):
            return [entry for entry in raw_value if isinstance(entry, dict)]
        if not isinstance(raw_value, str) or not raw_value:
            return []
        try:
            decoded = json.loads(raw_value)
        except json.JSONDecodeError:
            return []
        if not isinstance(decoded, list):
            return []
        return [entry for entry in decoded if isinstance(entry, dict)]

    @staticmethod
    def _preferred_image_url(image_uris: Dict[str, Any]) -> str | None:
        for key in ("png", "large", "normal", "small", "art_crop", "border_crop"):
            value = image_uris.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    @classmethod
    def _extract_print_image_url(cls, image_uris_raw: object, card_faces_raw: object) -> str | None:
        image_uris = cls._decode_json_object(image_uris_raw)
        direct_url = cls._preferred_image_url(image_uris)
        if direct_url:
            return direct_url

        for face in cls._decode_json_array(card_faces_raw):
            face_image_uris = cls._decode_json_object(face.get("image_uris"))
            face_url = cls._preferred_image_url(face_image_uris)
            if face_url:
                return face_url
        return None

    def get_random_card(
        self,
        mana_value: ManaValue,
        settings_schema: List[Dict[str, object]],
        settings: Dict[str, Dict[str, bool | int | float | str]],
    ) -> RandomCard | None:
        if self.has_runtime_cache_for(settings):
            cached_names = self._cached_cards_by_mana.get(mana_value, [])
            if cached_names:
                chosen_name = random.choice(cached_names)
                image_url = self.get_card_image_url_by_name(chosen_name)
                return {"name": chosen_name, "image_url": image_url}

        where_sql, where_params = build_filter_where(settings_schema, settings)
        sql = (
            f'SELECT "name", "image_uris", "card_faces" FROM cards '
            f'WHERE "cmc" = ? AND ({where_sql});'
        )
        params = [mana_value, *where_params]

        if not self.has_database():
            return None

        try:
            with self._connect() as conn:
                cursor = conn.execute(sql, params)
                chosen_card: RandomCard | None = None
                row_count = 0
                for row in cursor:
                    value = row["name"]
                    if not isinstance(value, str):
                        continue
                    row_count += 1
                    if random.randrange(row_count) == 0:
                        chosen_card = {
                            "name": value,
                            "image_url": self._extract_print_image_url(
                                row["image_uris"], row["card_faces"]
                            ),
                        }
        except sqlite3.Error as exc:
            print(f"CardService: failed random-card query: {exc}")
            return None

        return chosen_card

    def get_card_image_url_by_name(self, card_name: str) -> str | None:
        if not self.has_database():
            return None
        sql = (
            'SELECT "image_uris", "card_faces" FROM cards '
            'WHERE "name" = ? ORDER BY "released_at" DESC LIMIT 1;'
        )
        try:
            with self._connect() as conn:
                row = conn.execute(sql, [card_name]).fetchone()
        except sqlite3.Error as exc:
            print(f"CardService: failed image-url lookup for '{card_name}': {exc}")
            return None
        if row is None:
            return None
        return self._extract_print_image_url(row["image_uris"], row["card_faces"])
