from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List

from card_query_engine import build_filter_where


ManaValue = int | float


class CardService:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

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

    def get_available_mana_values(
        self,
        settings_schema: List[Dict[str, object]],
        settings: Dict[str, Dict[str, bool | int | float | str]],
    ) -> List[ManaValue]:
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
        if not self.has_database():
            return None

        where_sql, where_params = build_filter_where(settings_schema, settings)
        sql = (
            f'SELECT "name" FROM cards '
            f'WHERE "cmc" = ? AND ({where_sql}) '
            f'ORDER BY RANDOM() LIMIT 1;'
        )
        params = [mana_value, *where_params]

        try:
            with self._connect() as conn:
                row = conn.execute(sql, params).fetchone()
        except sqlite3.Error as exc:
            print(f"CardService: failed random-card query: {exc}")
            return None

        if row is None:
            return None
        value = row["name"]
        return str(value) if isinstance(value, str) else None
