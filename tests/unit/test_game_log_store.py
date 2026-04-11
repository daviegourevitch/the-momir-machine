from __future__ import annotations

import json

from game_log_store import build_game_log_record, save_game_log


def test_build_game_log_record_shapes_output() -> None:
    record = build_game_log_record(
        started_at="2026-04-10T10:00:00+00:00",
        ended_at="2026-04-10T10:10:00+00:00",
        starting_player=2,
        cards=[
            {
                "card_index": 1,
                "player": 2,
                "card_name": "Alpha",
                "mana_value": 3,
                "life_before_card": {"player1": 20, "player2": 20},
                "life_delta_since_previous_card": {"player1": 0, "player2": 0},
            }
        ],
        final_life_totals={1: 18, 2: 6},
    )

    assert record["starting_player"] == 2
    assert record["final_life_totals"] == {"player1": 18, "player2": 6}
    assert record["cards"][0]["card_name"] == "Alpha"


def test_save_game_log_writes_json_file(tmp_path) -> None:
    record = build_game_log_record(
        started_at="2026-04-10T10:00:00+00:00",
        ended_at="2026-04-10T10:10:00+00:00",
        starting_player=1,
        cards=[],
        final_life_totals={1: 20, 2: 20},
    )

    destination = save_game_log(record, logs_dir=tmp_path)
    payload = json.loads(destination.read_text(encoding="utf-8"))

    assert destination.is_file()
    assert payload["started_at"] == "2026-04-10T10:00:00+00:00"
    assert payload["ended_at"] == "2026-04-10T10:10:00+00:00"
    assert payload["final_life_totals"] == {"player1": 20, "player2": 20}
