from __future__ import annotations

import importlib
import sys
import types
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    import app


class StubUI:
    def setup(self) -> None:
        return

    def shutdown(self) -> None:
        return

    def draw_main_menu(self, *args: Any, **kwargs: Any) -> None:
        return

    def draw_settings_menu(self, *args: Any, **kwargs: Any) -> None:
        return

    def draw_printer_settings_menu(self, *args: Any, **kwargs: Any) -> None:
        return

    def flip(self) -> None:
        return


class StubInputController:
    def __init__(self, _queue: Any) -> None:
        pass

    def setup_gpio(self) -> None:
        return

    def close_gpio(self) -> None:
        return


class StubCardService:
    def __init__(self, _db_path: Any) -> None:
        self._preview: Dict[str, Any] = {
            "signature": "sig",
            "available_mana_values": [1, 2, 3],
            "cards_by_mana": {1: ["Alpha"]},
        }
        self._random_card = {"name": "Alpha", "image_url": "https://example.test/alpha.png"}
        self.applied_preview: Dict[str, Any] | None = None

    def warm_runtime_cache(self, _schema: Any, _settings: Any) -> list[int]:
        return [1, 2, 3]

    def has_database(self) -> bool:
        return True

    def preview_runtime_cache(self, _schema: Any, _settings: Any) -> Dict[str, Any]:
        return deepcopy(self._preview)

    def apply_runtime_cache_preview(self, preview: Dict[str, Any]) -> None:
        self.applied_preview = deepcopy(preview)

    def get_random_card(self, _mana: Any, _schema: Any, _settings: Any) -> Dict[str, Any] | None:
        return deepcopy(self._random_card)


@pytest.fixture
def build_app(monkeypatch: pytest.MonkeyPatch):
    stub_printer_service = types.SimpleNamespace(
        is_printer_connected=lambda: True,
        print_card_image=lambda _url: True,
    )
    monkeypatch.setitem(sys.modules, "printer_service", stub_printer_service)
    if "app" in sys.modules:
        monkeypatch.delitem(sys.modules, "app", raising=False)
    app = importlib.import_module("app")

    schema = [
        {
            "id": "card_list",
            "label": "Card List",
            "advanced_fields": [{"id": "list_id", "type": "string", "default": "na"}],
            "quick_options": [],
            "show_advanced": False,
        },
        {
            "id": "card_type",
            "label": "Card Type",
            "advanced_fields": [{"id": "creature", "type": "boolean", "default": True}],
            "quick_options": [],
            "show_advanced": False,
        },
    ]
    defaults = {"card_list": {"list_id": "na"}, "card_type": {"creature": True}}
    settings = deepcopy(defaults)

    saved_settings: list[dict[str, Any]] = []
    saved_logs: list[dict[str, Any]] = []

    monkeypatch.setattr(app, "InputController", StubInputController)
    monkeypatch.setattr(app, "UI", StubUI)
    monkeypatch.setattr(app, "CardService", StubCardService)
    monkeypatch.setattr(app, "is_printer_connected", lambda: True)
    monkeypatch.setattr(app, "load_menu_schema", lambda _path: deepcopy(schema))
    monkeypatch.setattr(app, "sync_card_lists", lambda _db_path, _lists_dir: [])
    monkeypatch.setattr(app, "apply_card_list_setting", lambda base, _lists: base)
    monkeypatch.setattr(app, "build_default_settings", lambda _schema: deepcopy(defaults))
    monkeypatch.setattr(app, "load_settings", lambda _path, _defaults, _schema: deepcopy(settings))
    monkeypatch.setattr(app, "load_print_settings", lambda _path: deepcopy(app.DEFAULT_PRINT_SETTINGS))
    monkeypatch.setattr(
        app,
        "save_settings",
        lambda _path, payload: saved_settings.append(deepcopy(payload)),
    )
    monkeypatch.setattr(
        app,
        "save_game_log",
        lambda record, logs_dir: (saved_logs.append(deepcopy(record)) or (Path(logs_dir) / "game-log-test.json")),
    )
    monkeypatch.setattr(app.pygame.time, "get_ticks", lambda: 10_000)
    monkeypatch.setattr(app.pygame.event, "pump", lambda: None)

    def _build():
        instance = app.MomirApp()
        instance._render = lambda: None
        return instance, saved_settings, saved_logs, app

    return _build


def test_save_settings_rejects_when_preview_has_no_mana(build_app) -> None:
    instance, saved_settings, _saved_logs, _app = build_app()
    instance.card_service._preview["available_mana_values"] = []

    instance._save_settings_if_valid()

    assert instance.status_message == "No cards match current filters. Not saved."
    assert saved_settings == []


def test_save_settings_persists_and_updates_runtime_cache(build_app) -> None:
    instance, saved_settings, _saved_logs, _app = build_app()
    candidate = deepcopy(instance.settings)
    candidate["card_type"]["creature"] = False
    instance.edit_settings = candidate
    instance.card_service._preview = {
        "signature": "new",
        "available_mana_values": [2, 4],
        "cards_by_mana": {2: ["Two Drop"]},
    }

    instance._save_settings_if_valid()

    assert instance.mana_pool.values() == [2, 4]
    assert instance.settings["card_type"]["creature"] is False
    assert instance.card_service.applied_preview == instance.card_service._preview
    assert saved_settings and saved_settings[-1]["card_type"]["creature"] is False


def test_pick_random_card_handles_missing_result(build_app) -> None:
    instance, _saved, _saved_logs, _app = build_app()
    instance._start_new_game(1)
    instance.card_service._random_card = None

    instance._pick_random_card()

    assert instance.popup_message == "No matching card found."


def test_pick_random_card_handles_missing_printer(build_app) -> None:
    instance, _saved, _saved_logs, _app = build_app()
    instance._start_new_game(1)
    instance.printer_connected = False
    instance.card_service._random_card = {
        "name": "Lightning Bolt",
        "image_url": "https://example.test/bolt.png",
    }

    instance._pick_random_card()

    assert instance.popup_message == "Your card is Lightning Bolt (no printer connected)"


def test_pick_random_card_handles_missing_image_url(build_app, monkeypatch: pytest.MonkeyPatch) -> None:
    instance, _saved, _saved_logs, app_module = build_app()
    instance._start_new_game(1)
    instance.card_service._random_card = {"name": "Mystery Card", "image_url": None}
    monkeypatch.setattr(app_module, "print_card_image", lambda _url: True)

    instance._pick_random_card()

    assert instance.popup_message == "Your card is Mystery Card"
    assert instance.status_message == "Could not print card: missing image URL."


def test_pick_random_card_marks_printer_disconnected_on_print_failure(
    build_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance, _saved, _saved_logs, app_module = build_app()
    instance._start_new_game(1)
    instance.printer_connected = True
    instance.card_service._random_card = {
        "name": "Primeval Titan",
        "image_url": "https://example.test/titan.png",
    }
    monkeypatch.setattr(app_module, "print_card_image", lambda _url: False)

    instance._pick_random_card()

    assert instance.printer_connected is False
    assert instance.popup_message == "Your card is Primeval Titan (no printer connected)"


def test_start_player_popup_defaults_on_boot(build_app) -> None:
    instance, _saved, _saved_logs, _app = build_app()

    assert instance.popup_mode == "start_player"
    assert instance.popup_message == "Which player will start?"
    assert instance.popup_options == ["Player 1", "Player 2", "Randomize for me"]


def test_left_right_selects_expected_player(build_app) -> None:
    instance, _saved, _saved_logs, _app = build_app()
    instance._start_new_game(1)

    instance._handle_action("right")
    assert instance.selected_player == 2
    instance._handle_action("left")
    assert instance.selected_player == 1


def test_up_down_adjust_selected_player_life_by_one(build_app) -> None:
    instance, _saved, _saved_logs, _app = build_app()
    instance._start_new_game(1)
    instance._handle_action("right")

    instance._handle_action("up")
    assert instance.player_life[2] == 21
    instance._handle_action("down")
    assert instance.player_life[2] == 20


def test_randomized_start_shows_second_popup_then_starts(build_app, monkeypatch: pytest.MonkeyPatch) -> None:
    instance, _saved, _saved_logs, app_module = build_app()
    monkeypatch.setattr(app_module.random, "choice", lambda _values: 2)

    instance.popup_selected_index = 2
    instance._handle_action("joy_press")
    assert instance.popup_mode == "random_start_result"
    assert instance.popup_message == "Player 2 will start."
    instance._handle_action("joy_press")

    assert instance.game_active is True
    assert instance.starting_player == 2
    assert instance.selected_player == 2


def test_end_game_prompt_no_keeps_game_active(build_app) -> None:
    instance, _saved, _saved_logs, _app = build_app()
    instance._start_new_game(1)

    instance._handle_action("joy_press")
    assert instance.popup_mode == "game_complete"
    instance._handle_action("joy_press")

    assert instance.game_active is True
    assert instance.popup_message is None


def test_end_game_yes_resets_and_writes_log(build_app) -> None:
    instance, _saved, saved_logs, _app = build_app()
    instance._start_new_game(1)
    instance._record_generated_card({"name": "Alpha", "image_url": "https://example.test/alpha.png"})
    instance.selected_player = 1
    instance._adjust_life(-1)

    instance._handle_action("joy_press")
    instance.popup_selected_index = 1
    instance._handle_action("joy_press")

    assert len(saved_logs) == 1
    assert instance.game_active is False
    assert instance.popup_mode == "start_player"
    assert instance.player_life == {1: 20, 2: 20}


def test_generated_cards_alternate_players_from_starter(build_app) -> None:
    instance, _saved, _saved_logs, _app = build_app()
    instance._start_new_game(2)

    instance._record_generated_card({"name": "First", "image_url": "https://example.test/1.png"})
    instance._record_generated_card({"name": "Second", "image_url": "https://example.test/2.png"})
    instance._record_generated_card({"name": "Third", "image_url": "https://example.test/3.png"})

    assert [entry["player"] for entry in instance.current_game_cards] == [2, 1, 2]


def test_life_delta_is_logged_between_cards(build_app) -> None:
    instance, _saved, _saved_logs, _app = build_app()
    instance._start_new_game(1)
    instance._record_generated_card({"name": "First", "image_url": "https://example.test/1.png"})
    instance._adjust_life(-1)
    instance._handle_action("right")
    instance._adjust_life(1)
    instance._record_generated_card({"name": "Second", "image_url": "https://example.test/2.png"})

    assert instance.current_game_cards[1]["life_delta_since_previous_card"] == {
        "player1": -1,
        "player2": 1,
    }


def test_back_from_printer_settings_returns_to_main_menu(build_app) -> None:
    instance, _saved, _saved_logs, _app = build_app()

    instance._open_printer_settings()
    assert instance.state == "printer_settings_menu"
    instance._handle_action("key2")

    assert instance.state == "main_menu"


def test_settings_selection_wraps_only_game_settings_rows(build_app) -> None:
    instance, _saved, _saved_logs, _app = build_app()

    instance._open_settings()
    assert instance.state == "settings_menu"
    assert len(instance.settings_schema) == 2

    instance.settings_index = len(instance.settings_schema) - 1
    instance._move_selection(1)
    assert instance.settings_index == 0

    instance.settings_index = 0
    instance._move_selection(-1)
    assert instance.settings_index == len(instance.settings_schema) - 1
