#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import ijson
except ImportError as exc:  # pragma: no cover - handled at runtime
    raise SystemExit(
        "fetch-db: missing dependency 'ijson'. Install with: pip install -r requirements.txt"
    ) from exc


BULK_DATA_URL = "https://api.scryfall.com/bulk-data"
USER_AGENT = (
    "The-Momir-Machine fetch-db/1.0 "
    "(+https://github.com/daviegourevitch/the-momir-machine)"
)
EXCLUDED_FIELDS = {"all_parts", "preview", "prices", "related_uris", "purchase_uris"}
EXCLUDED_SET_TYPES = {"memorabilia"}
EXCLUDED_LAYOUTS = {"meld"}

# Keep this map explicit so schema changes are intentional and reviewable.
COLUMN_TYPES: dict[str, str] = {
    "object": "TEXT",
    "id": "TEXT",
    "arena_id": "INTEGER",
    "lang": "TEXT",
    "mtgo_id": "INTEGER",
    "mtgo_foil_id": "INTEGER",
    "multiverse_ids": "TEXT",
    "tcgplayer_id": "INTEGER",
    "tcgplayer_etched_id": "INTEGER",
    "cardmarket_id": "INTEGER",
    "layout": "TEXT",
    "oracle_id": "TEXT",
    "prints_search_uri": "TEXT",
    "rulings_uri": "TEXT",
    "scryfall_uri": "TEXT",
    "uri": "TEXT",
    "card_faces": "TEXT",
    "cmc": "REAL",
    "color_identity": "TEXT",
    "color_indicator": "TEXT",
    "colors": "TEXT",
    "defense": "TEXT",
    "edhrec_rank": "INTEGER",
    "game_changer": "INTEGER",
    "hand_modifier": "TEXT",
    "keywords": "TEXT",
    "legalities": "TEXT",
    "life_modifier": "TEXT",
    "loyalty": "TEXT",
    "mana_cost": "TEXT",
    "name": "TEXT",
    "oracle_text": "TEXT",
    "penny_rank": "INTEGER",
    "power": "TEXT",
    "produced_mana": "TEXT",
    "reserved": "INTEGER",
    "toughness": "TEXT",
    "type_line": "TEXT",
    "card_types": "TEXT",
    "artist": "TEXT",
    "artist_ids": "TEXT",
    "attraction_lights": "TEXT",
    "booster": "INTEGER",
    "border_color": "TEXT",
    "card_back_id": "TEXT",
    "collector_number": "TEXT",
    "content_warning": "INTEGER",
    "digital": "INTEGER",
    "finishes": "TEXT",
    "flavor_name": "TEXT",
    "flavor_text": "TEXT",
    "frame_effects": "TEXT",
    "frame": "TEXT",
    "full_art": "INTEGER",
    "games": "TEXT",
    "highres_image": "INTEGER",
    "illustration_id": "TEXT",
    "image_status": "TEXT",
    "image_uris": "TEXT",
    "oversized": "INTEGER",
    "printed_name": "TEXT",
    "printed_text": "TEXT",
    "printed_type_line": "TEXT",
    "promo": "INTEGER",
    "promo_types": "TEXT",
    "rarity": "TEXT",
    "released_at": "TEXT",
    "reprint": "INTEGER",
    "scryfall_set_uri": "TEXT",
    "set_name": "TEXT",
    "set_search_uri": "TEXT",
    "set_type": "TEXT",
    "set_uri": "TEXT",
    "set": "TEXT",
    "set_id": "TEXT",
    "story_spotlight": "INTEGER",
    "textless": "INTEGER",
    "variation": "INTEGER",
    "variation_of": "TEXT",
    "security_stamp": "TEXT",
    "watermark": "TEXT",
}

JSON_COLUMNS = {
    "multiverse_ids",
    "card_faces",
    "color_identity",
    "color_indicator",
    "colors",
    "keywords",
    "legalities",
    "card_types",
    "produced_mana",
    "artist_ids",
    "attraction_lights",
    "finishes",
    "frame_effects",
    "games",
    "image_uris",
    "promo_types",
}
BOOL_COLUMNS = {
    "game_changer",
    "reserved",
    "booster",
    "content_warning",
    "digital",
    "full_art",
    "highres_image",
    "oversized",
    "promo",
    "reprint",
    "story_spotlight",
    "textless",
    "variation",
}
REAL_COLUMNS = {"cmc"}
INTEGER_COLUMNS = {
    "arena_id",
    "mtgo_id",
    "mtgo_foil_id",
    "tcgplayer_id",
    "tcgplayer_etched_id",
    "cardmarket_id",
    "edhrec_rank",
    "penny_rank",
}


def log(msg: str) -> None:
    print(msg, flush=True)


def fetch_json(url: str) -> dict[str, Any]:
    req = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except HTTPError as exc:
        raise RuntimeError(f"HTTP error fetching {url}: {exc.code} {exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error fetching {url}: {exc.reason}") from exc


def find_oracle_cards_entry(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    if not isinstance(data, list):
        raise RuntimeError("Unexpected bulk-data payload: missing list at 'data'.")

    for entry in data:
        if isinstance(entry, dict) and entry.get("type") == "oracle_cards":
            return entry

    raise RuntimeError("No entry with type='oracle_cards' found in bulk-data response.")


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    req = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=120) as resp, destination.open("wb") as out:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
    except HTTPError as exc:
        raise RuntimeError(
            f"HTTP error downloading bulk file {url}: {exc.code} {exc.reason}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"Network error downloading bulk file {url}: {exc.reason}") from exc


def configure_sqlite(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA cache_size=-32768;")  # ~32MB
    conn.execute("PRAGMA foreign_keys=ON;")


def create_schema(conn: sqlite3.Connection) -> None:
    columns_sql: list[str] = []
    for column, col_type in COLUMN_TYPES.items():
        if column == "id":
            columns_sql.append('"id" TEXT PRIMARY KEY NOT NULL')
        else:
            columns_sql.append(f'"{column}" {col_type}')

    columns_sql.append('"extra_json" TEXT')

    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS cards (
            {", ".join(columns_sql)}
        );
        """
    )
    ensure_cards_columns(conn)

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS import_runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            imported_at TEXT NOT NULL,
            bulk_id TEXT NOT NULL,
            bulk_updated_at TEXT,
            bulk_download_uri TEXT NOT NULL,
            card_count INTEGER NOT NULL
        );
        """
    )

    conn.execute('CREATE INDEX IF NOT EXISTS idx_cards_name ON cards("name");')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_cards_cmc ON cards("cmc");')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_cards_oracle_id ON cards("oracle_id");')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_cards_set ON cards("set");')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_cards_set_type ON cards("set_type");')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_cards_border_color ON cards("border_color");')
    conn.execute(
        'CREATE INDEX IF NOT EXISTS idx_cards_cmc_set_type_border_color '
        'ON cards("cmc", "set_type", "border_color");'
    )
    conn.execute(
        'CREATE INDEX IF NOT EXISTS idx_cards_card_faces_present '
        'ON cards("id") WHERE "card_faces" IS NOT NULL;'
    )
    conn.execute(
        'CREATE INDEX IF NOT EXISTS idx_cards_collector_number ON cards("collector_number");'
    )
    conn.execute('CREATE INDEX IF NOT EXISTS idx_cards_released_at ON cards("released_at");')


def ensure_cards_columns(conn: sqlite3.Connection) -> None:
    existing = {
        str(row[1]) for row in conn.execute("PRAGMA table_info(cards);").fetchall()
    }
    expected = list(COLUMN_TYPES.items()) + [("extra_json", "TEXT")]

    for column, col_type in expected:
        if column in existing:
            continue
        conn.execute(f'ALTER TABLE cards ADD COLUMN "{column}" {col_type};')


def json_text(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True, ensure_ascii=True)


def normalize_value(column: str, value: Any) -> Any:
    if value is None:
        return None
    if column in JSON_COLUMNS:
        return json_text(value)
    if column in BOOL_COLUMNS:
        return 1 if bool(value) else 0
    if column in INTEGER_COLUMNS:
        return int(value)
    if column in REAL_COLUMNS:
        return float(value)
    if isinstance(value, str):
        return value
    return str(value)


def normalize_card(card: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {column: None for column in COLUMN_TYPES}
    extras: dict[str, Any] = {}

    for key, value in card.items():
        if key in EXCLUDED_FIELDS:
            continue
        if key in COLUMN_TYPES:
            row[key] = normalize_value(key, value)
        else:
            extras[key] = value

    row["card_types"] = normalize_value("card_types", parse_card_types(card.get("type_line")))
    row["extra_json"] = json_text(extras) if extras else None
    return row


def parse_card_types(type_line: Any) -> list[str]:
    if not isinstance(type_line, str):
        return []

    main_part = type_line.split("—", 1)[0].strip()
    if not main_part:
        return []

    return [token for token in main_part.split() if token]


def should_import_card(card: dict[str, Any]) -> bool:
    set_type = card.get("set_type")
    if isinstance(set_type, str) and set_type in EXCLUDED_SET_TYPES:
        return False
    layout = card.get("layout")
    if isinstance(layout, str) and layout in EXCLUDED_LAYOUTS:
        return False
    return True


def import_cards(
    conn: sqlite3.Connection, source_gz_path: Path, batch_size: int, *, progress_every: int
) -> int:
    insert_columns = list(COLUMN_TYPES.keys()) + ["extra_json"]
    quoted_cols = ", ".join(f'"{c}"' for c in insert_columns)
    placeholders = ", ".join("?" for _ in insert_columns)
    update_clause = ", ".join(f'"{c}"=excluded."{c}"' for c in insert_columns if c != "id")
    sql = (
        f'INSERT INTO cards ({quoted_cols}) VALUES ({placeholders}) '
        f'ON CONFLICT("id") DO UPDATE SET {update_clause};'
    )

    total = 0
    pending: list[tuple[Any, ...]] = []

    with open_json_stream(source_gz_path) as source:
        for card in ijson.items(source, "item"):
            if not isinstance(card, dict):
                continue
            if not should_import_card(card):
                continue
            row = normalize_card(card)
            pending.append(tuple(row[col] for col in insert_columns))
            if len(pending) >= batch_size:
                conn.executemany(sql, pending)
                conn.commit()
                total += len(pending)
                if total % progress_every == 0:
                    log(f"Imported {total:,} cards...")
                pending.clear()

    if pending:
        conn.executemany(sql, pending)
        conn.commit()
        total += len(pending)

    return total


def remove_excluded_cards(conn: sqlite3.Connection) -> int:
    set_type_placeholders = ", ".join("?" for _ in EXCLUDED_SET_TYPES)
    layout_placeholders = ", ".join("?" for _ in EXCLUDED_LAYOUTS)
    params = [*EXCLUDED_SET_TYPES, *EXCLUDED_LAYOUTS]
    cursor = conn.execute(
        f"""
        DELETE FROM cards
        WHERE "set_type" IN ({set_type_placeholders})
           OR "layout" IN ({layout_placeholders});
        """,
        params,
    )
    conn.commit()
    return int(cursor.rowcount)


def open_json_stream(path: Path):
    with path.open("rb") as probe:
        magic = probe.read(2)

    if magic == b"\x1f\x8b":
        return gzip.open(path, mode="rb")
    return path.open("rb")


def run_smoke_checks(conn: sqlite3.Connection) -> tuple[int, tuple[str, str] | None]:
    total = conn.execute("SELECT COUNT(*) FROM cards;").fetchone()[0]
    sample = conn.execute(
        'SELECT "id", "name" FROM cards WHERE "name" IS NOT NULL ORDER BY RANDOM() LIMIT 1;'
    ).fetchone()
    return int(total), sample


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Scryfall oracle_cards bulk data and import into SQLite."
    )
    parser.add_argument(
        "--db-path",
        default="data/scryfall/cards.db",
        help="Path to SQLite database file (default: data/scryfall/cards.db).",
    )
    parser.add_argument(
        "--download-path",
        default="data/scryfall/oracle-cards-latest.json.gz",
        help="Path to downloaded gzip file (default: data/scryfall/oracle-cards-latest.json.gz).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Rows per transaction batch during import (default: 1000).",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=10000,
        help="Print progress every N imported rows (default: 10000).",
    )
    parser.add_argument(
        "--keep-download",
        action="store_true",
        help="Keep the downloaded gzip file after import (default: keep).",
        default=True,
    )
    parser.add_argument(
        "--remove-download",
        dest="keep_download",
        action="store_false",
        help="Delete downloaded gzip file after successful import.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.batch_size <= 0:
        raise SystemExit("fetch-db: --batch-size must be > 0")
    if args.progress_every <= 0:
        raise SystemExit("fetch-db: --progress-every must be > 0")

    db_path = Path(args.db_path).expanduser().resolve()
    download_path = Path(args.download_path).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    download_path.parent.mkdir(parents=True, exist_ok=True)

    log("Fetching Scryfall bulk-data index...")
    bulk_payload = fetch_json(BULK_DATA_URL)
    oracle_entry = find_oracle_cards_entry(bulk_payload)

    download_uri = str(oracle_entry.get("download_uri", "")).strip()
    if not download_uri:
        raise RuntimeError("oracle_cards entry is missing a non-empty download_uri.")

    log(f"Downloading oracle_cards file to {download_path} ...")
    download_file(download_uri, download_path)
    log("Download complete. Importing into SQLite...")

    with sqlite3.connect(db_path) as conn:
        configure_sqlite(conn)
        create_schema(conn)

        imported_count = import_cards(
            conn,
            download_path,
            batch_size=args.batch_size,
            progress_every=args.progress_every,
        )
        removed_count = remove_excluded_cards(conn)
        conn.execute("ANALYZE;")

        conn.execute(
            """
            INSERT INTO import_runs (imported_at, bulk_id, bulk_updated_at, bulk_download_uri, card_count)
            VALUES (?, ?, ?, ?, ?);
            """,
            (
                datetime.now(UTC).isoformat(),
                str(oracle_entry.get("id", "")),
                str(oracle_entry.get("updated_at", "")),
                download_uri,
                imported_count,
            ),
        )
        conn.commit()

        row_count, sample = run_smoke_checks(conn)

    if row_count <= 0:
        raise RuntimeError("Import completed but cards table is empty.")

    if not args.keep_download and download_path.exists():
        download_path.unlink()

    log(f"Imported {imported_count:,} cards into {db_path}")
    if removed_count > 0:
        log(
            "Removed "
            f"{removed_count:,} excluded cards "
            f'(set_type in {sorted(EXCLUDED_SET_TYPES)} or layout in {sorted(EXCLUDED_LAYOUTS)})'
        )
    log(f"cards row count: {row_count:,}")
    if sample:
        log(f'sample card: id={sample[0]} name="{sample[1]}"')
    else:
        log("sample card: none")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit("fetch-db: interrupted by user")
    except Exception as exc:
        raise SystemExit(f"fetch-db: {exc}")
