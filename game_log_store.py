from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable

from constants import GAME_LOGS_DIR


def build_game_log_record(
    *,
    started_at: str,
    ended_at: str,
    starting_player: int,
    cards: Iterable[Dict[str, Any]],
    final_life_totals: Dict[int, int],
) -> Dict[str, Any]:
    return {
        "started_at": started_at,
        "ended_at": ended_at,
        "starting_player": 1 if starting_player == 1 else 2,
        "cards": list(cards),
        "final_life_totals": {
            "player1": int(final_life_totals.get(1, 20)),
            "player2": int(final_life_totals.get(2, 20)),
        },
    }


def _sanitize_timestamp(value: str) -> str:
    return value.replace(":", "-").replace(".", "-").replace("+", "_")


def save_game_log(record: Dict[str, Any], logs_dir: Path = GAME_LOGS_DIR) -> Path:
    logs_dir.mkdir(parents=True, exist_ok=True)
    ended_at = str(record.get("ended_at", "unknown-time"))
    filename = f"game-log-{_sanitize_timestamp(ended_at)}.json"
    destination = logs_dir / filename
    destination.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    return destination
