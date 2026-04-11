from __future__ import annotations

import queue
import random
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import pygame

from card_lists import (
    CARD_LIST_SETTING_ID,
    apply_card_list_setting,
    selected_card_list_id,
    sync_card_lists,
)
from card_service import CardService
from constants import (
    ACTION_DOWN,
    ACTION_JOY_PRESS,
    ACTION_KEY1,
    ACTION_KEY2,
    ACTION_KEY3,
    ACTION_KNOB_PRESS,
    ACTION_LEFT,
    ACTION_RIGHT,
    ACTION_ROTARY_CCW,
    ACTION_ROTARY_CW,
    ACTION_UP,
    CARD_DB_PATH,
    GAME_LOGS_DIR,
    LISTS_DIR,
    MANA_VALUES,
    MENU_SCHEMA_PATH,
    PRINT_SETTINGS_PATH,
    SETTINGS_PATH,
    STATE_MAIN_MENU,
    STATE_PRINTER_SETTINGS_MENU,
    STATE_SETTINGS_MENU,
)
from input_controller import InputController
from game_log_store import build_game_log_record, save_game_log
from runtime_mana_pool import RuntimeManaPool
from runtime_coordination import RuntimeLock
from printer_service import is_printer_connected, print_card_image
from print_settings_store import (
    DEFAULT_PRINT_SETTINGS,
    PRINT_SETTING_FIELDS,
    PrintSettingField,
    PrintSettings,
    load_print_settings,
    save_print_settings,
)
from settings_store import (
    build_default_settings,
    load_menu_schema,
    load_settings,
    quick_option_index,
    quick_option_label,
    save_settings,
)
from ui import UI

POPUP_MODE_NONE = "none"
POPUP_MODE_START_PLAYER = "start_player"
POPUP_MODE_RANDOM_START_RESULT = "random_start_result"
POPUP_MODE_GAME_COMPLETE = "game_complete"


class MomirApp:
    def __init__(self) -> None:
        self.running = True
        self.state = STATE_MAIN_MENU

        self.action_queue: "queue.SimpleQueue[str]" = queue.SimpleQueue()
        self.input = InputController(self.action_queue)
        self.ui = UI()

        self.settings_schema = load_menu_schema(MENU_SCHEMA_PATH)
        self.card_lists = sync_card_lists(CARD_DB_PATH, LISTS_DIR)
        self.settings_schema = apply_card_list_setting(self.settings_schema, self.card_lists)
        self.default_settings = build_default_settings(self.settings_schema)
        self.settings = load_settings(
            SETTINGS_PATH, self.default_settings, self.settings_schema
        )
        self.edit_settings: Optional[Dict[str, Dict[str, bool | int | float | str]]] = None
        self.default_print_settings: PrintSettings = dict(DEFAULT_PRINT_SETTINGS)
        self.print_settings: PrintSettings = load_print_settings(PRINT_SETTINGS_PATH)
        self.edit_print_settings: Optional[PrintSettings] = None
        self.card_service = CardService(CARD_DB_PATH)
        self.mana_pool = RuntimeManaPool(MANA_VALUES)

        self.settings_index = 0
        self.advanced_field_index = 0
        self.printer_settings_index = 0
        self.in_advanced_mode = False
        self.popup_message: Optional[str] = None
        self.popup_title = "Random Card"
        self.popup_options: Optional[list[str]] = None
        self.popup_selected_index = 0
        self.popup_mode = POPUP_MODE_NONE
        self.status_message: Optional[str] = None
        self.status_message_until_ms = 0
        self.startup_status_message: Optional[str] = None
        self.player_life = {1: 20, 2: 20}
        self.selected_player = 1
        self.starting_player: Optional[int] = None
        self.next_card_player = 1
        self.pending_random_starting_player: Optional[int] = None
        self.game_active = False
        self.current_game_started_at: Optional[str] = None
        self.current_game_cards: list[dict[str, Any]] = []
        self.pending_life_delta = {1: 0, 2: 0}
        self.printer_connected = False
        self.is_loading = False
        self.runtime_lock = RuntimeLock()
        self._load_mana_values_for_current_settings()
        self._detect_printer_at_startup()
        self._open_start_player_prompt()

    def _load_mana_values_for_current_settings(self) -> None:
        available_values = self.card_service.warm_runtime_cache(
            self.settings_schema, self.settings
        )
        if available_values:
            self.mana_pool.set_values(available_values)
            return
        if self.card_service.has_database():
            self.startup_status_message = "Saved settings currently match no cards."
        else:
            self.startup_status_message = "Card database missing. Run fetch-db.py."

    def _current_mana_value(self) -> int | float:
        return self.mana_pool.current()

    def _inc_mana_index(self) -> None:
        self.mana_pool.step(1)

    def _dec_mana_index(self) -> None:
        self.mana_pool.step(-1)

    def _current_setting(self) -> Dict[str, Any]:
        if not self.settings_schema:
            return {}
        idx = max(0, min(self.settings_index, len(self.settings_schema) - 1))
        self.settings_index = idx
        return self.settings_schema[idx]

    def _current_setting_values(self) -> Dict[str, bool | int | float | str]:
        setting = self._current_setting()
        if not setting:
            return {}
        setting_id = str(setting.get("id", ""))
        return self._menu_settings().setdefault(setting_id, {})

    def _menu_settings(self) -> Dict[str, Dict[str, bool | int | float | str]]:
        if self.edit_settings is not None:
            return self.edit_settings
        return self.settings

    def _is_card_list_active(
        self,
        settings: Optional[Dict[str, Dict[str, bool | int | float | str]]] = None,
    ) -> bool:
        settings_view = self._menu_settings() if settings is None else settings
        return selected_card_list_id(settings_view) is not None

    def _is_setting_locked_by_card_list(
        self,
        setting_id: str,
        settings: Optional[Dict[str, Dict[str, bool | int | float | str]]] = None,
    ) -> bool:
        if setting_id == CARD_LIST_SETTING_ID:
            return False
        return self._is_card_list_active(settings)

    def _notify_card_list_lock(self) -> None:
        self._set_status_message("Card list selected: other filters are locked.", 1700)

    def _is_printer_settings_item_selected(self) -> bool:
        return not self.in_advanced_mode and self.settings_index >= len(self.settings_schema)

    def _printer_settings(self) -> PrintSettings:
        if self.edit_print_settings is not None:
            return self.edit_print_settings
        return self.print_settings

    def _printer_row_count(self) -> int:
        # Adjustable fields + Save + Reset rows.
        return len(PRINT_SETTING_FIELDS) + 2

    def _printer_field_for_index(self) -> Optional[PrintSettingField]:
        if self.printer_settings_index < len(PRINT_SETTING_FIELDS):
            return PRINT_SETTING_FIELDS[self.printer_settings_index]
        return None

    def _current_advanced_field(self) -> Dict[str, Any]:
        setting = self._current_setting()
        fields = setting.get("advanced_fields", [])
        if not isinstance(fields, list) or not fields:
            return {}
        idx = max(0, min(self.advanced_field_index, len(fields) - 1))
        self.advanced_field_index = idx
        return fields[idx]

    @staticmethod
    def _setting_allows_advanced(setting: Dict[str, Any]) -> bool:
        fields = setting.get("advanced_fields", [])
        if not isinstance(fields, list) or not fields:
            return False
        show_advanced = setting.get("show_advanced")
        if isinstance(show_advanced, bool):
            return show_advanced
        return len(fields) > 1

    def _open_settings(self) -> None:
        self.state = STATE_SETTINGS_MENU
        self.in_advanced_mode = False
        self.settings_index = max(0, min(self.settings_index, len(self.settings_schema)))
        self._set_popup(None)
        self.edit_settings = deepcopy(self.settings)

    def _open_printer_settings(self) -> None:
        self.state = STATE_PRINTER_SETTINGS_MENU
        self.printer_settings_index = 0
        self.edit_print_settings = dict(self.print_settings)

    def _move_selection(self, delta: int) -> None:
        if self.in_advanced_mode:
            fields = self._current_setting().get("advanced_fields", [])
            if not isinstance(fields, list) or not fields:
                return
            self.advanced_field_index = (self.advanced_field_index + delta) % len(fields)
            return

        if not self.settings_schema:
            return
        total_rows = len(self.settings_schema) + 1  # +1 for Printer Settings entry
        self.settings_index = (self.settings_index + delta) % total_rows

    def _move_printer_selection(self, delta: int) -> None:
        total_rows = self._printer_row_count()
        self.printer_settings_index = (self.printer_settings_index + delta) % total_rows

    @staticmethod
    def _is_number(value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    def _cycle_quick_option(self, delta: int) -> None:
        if self._is_printer_settings_item_selected():
            return
        setting = self._current_setting()
        if not setting:
            return
        setting_id = str(setting.get("id", ""))
        if self._is_setting_locked_by_card_list(setting_id):
            self._notify_card_list_lock()
            return
        quick_options = setting.get("quick_options", [])
        if not isinstance(quick_options, list) or not quick_options:
            return

        values = self._current_setting_values()
        idx = quick_option_index(setting, values)
        if idx < 0:
            idx = 0 if delta > 0 else len(quick_options) - 1
        else:
            idx = (idx + delta) % len(quick_options)

        option_values = quick_options[idx].get("values", {})
        if not isinstance(option_values, dict):
            return
        for field_id, value in option_values.items():
            values[str(field_id)] = value

    def _adjust_advanced_value(self, delta: int) -> None:
        setting_id = str(self._current_setting().get("id", ""))
        if self._is_setting_locked_by_card_list(setting_id):
            self._notify_card_list_lock()
            return
        field = self._current_advanced_field()
        if not field:
            return

        field_id = str(field["id"])
        values = self._current_setting_values()
        current_value = values.get(field_id, field.get("default"))
        field_type = str(field.get("type", ""))

        if field_type == "boolean":
            values[field_id] = not bool(current_value)
            return

        if field_type == "number":
            step = field.get("step", 1)
            if not self._is_number(step) or step == 0:
                step = 1
            if not self._is_number(current_value):
                current_value = field.get("default", 0)
            if not self._is_number(current_value):
                current_value = 0

            next_value = current_value + (step if delta > 0 else -step)
            default_value = field.get("default")
            if (
                isinstance(default_value, int)
                and not isinstance(default_value, bool)
                and float(step).is_integer()
                and float(next_value).is_integer()
            ):
                values[field_id] = int(next_value)
            else:
                values[field_id] = next_value
            return

        if field_type == "string":
            options = field.get("options", [])
            if not isinstance(options, list) or not options:
                return
            clean_options = [opt for opt in options if isinstance(opt, str)]
            if not clean_options:
                return
            current_str = str(current_value) if isinstance(current_value, str) else None
            if current_str not in clean_options:
                idx = 0 if delta > 0 else len(clean_options) - 1
            else:
                idx = clean_options.index(current_str)
                idx = (idx + (1 if delta > 0 else -1)) % len(clean_options)
            values[field_id] = clean_options[idx]

    def _adjust_printer_value(self, delta: int) -> None:
        field = self._printer_field_for_index()
        if field is None:
            return

        field_id = field["id"]
        values = self._printer_settings()
        current_value = values.get(field_id, self.default_print_settings[field_id])
        field_type = field["type"]

        if field_type == "boolean":
            values[field_id] = not bool(current_value)
            return

        step = float(field["step"])
        direction = 1.0 if delta > 0 else -1.0
        if field["number_type"] == "int":
            base = int(current_value) if self._is_number(current_value) else int(field["min"])
            next_value = int(round(base + (step * direction)))
            next_value = max(int(field["min"]), min(int(field["max"]), next_value))
            values[field_id] = next_value
            return

        base_float = (
            float(current_value) if self._is_number(current_value) else float(field["min"])
        )
        next_float = base_float + (step * direction)
        next_float = max(float(field["min"]), min(float(field["max"]), next_float))
        values[field_id] = round(next_float, 2)

    def _save_printer_settings(self) -> None:
        candidate_settings = dict(self._printer_settings())
        save_print_settings(PRINT_SETTINGS_PATH, candidate_settings)
        self.print_settings = load_print_settings(PRINT_SETTINGS_PATH)
        self.edit_print_settings = dict(self.print_settings)
        self._set_status_message("Printer settings saved.", 2200)
        print("Printer settings saved.")

    def _reset_printer_settings_to_baseline(self) -> None:
        self.edit_print_settings = dict(self.default_print_settings)
        self._set_status_message("Printer settings reset to baseline.", 2200)

    def _enter_submenu(self) -> None:
        if self._is_printer_settings_item_selected():
            self._open_printer_settings()
            return
        setting = self._current_setting()
        setting_id = str(setting.get("id", ""))
        if self._is_setting_locked_by_card_list(setting_id):
            self._notify_card_list_lock()
            return
        if not self._setting_allows_advanced(setting):
            return
        self.in_advanced_mode = True
        self.advanced_field_index = 0

    def _back(self) -> None:
        if self.state == STATE_PRINTER_SETTINGS_MENU:
            self.edit_print_settings = None
            self.state = STATE_SETTINGS_MENU
            return
        if self.in_advanced_mode:
            self.in_advanced_mode = False
            return
        self.edit_settings = None
        self.state = STATE_MAIN_MENU

    def _set_status_message(self, text: str, duration_ms: int = 2200) -> None:
        self.status_message = text
        self.status_message_until_ms = pygame.time.get_ticks() + max(200, duration_ms)

    def _set_popup(
        self,
        text: Optional[str],
        title: str = "Random Card",
        options: Optional[list[str]] = None,
        selected_index: int = 0,
        mode: str = POPUP_MODE_NONE,
    ) -> None:
        self.popup_message = text
        self.popup_title = title
        self.popup_options = options if options else None
        if self.popup_options:
            self.popup_selected_index = max(
                0, min(selected_index, len(self.popup_options) - 1)
            )
        else:
            self.popup_selected_index = 0
        self.popup_mode = mode

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _open_start_player_prompt(self) -> None:
        self.game_active = False
        self.player_life = {1: 20, 2: 20}
        self.selected_player = 1
        self._set_popup(
            "Which player will start?",
            title="Game Setup",
            options=["Player 1", "Player 2", "Randomize for me"],
            selected_index=0,
            mode=POPUP_MODE_START_PLAYER,
        )

    def _start_new_game(self, starting_player: int) -> None:
        self.player_life = {1: 20, 2: 20}
        self.starting_player = 1 if starting_player == 1 else 2
        self.selected_player = self.starting_player
        self.next_card_player = self.starting_player
        self.pending_random_starting_player = None
        self.pending_life_delta = {1: 0, 2: 0}
        self.current_game_cards = []
        self.current_game_started_at = self._now_iso()
        self.game_active = True
        self._set_popup(None)

    def _select_player(self, player: int) -> None:
        if not self.game_active:
            return
        self.selected_player = 1 if player == 1 else 2

    def _adjust_life(self, delta: int) -> None:
        if not self.game_active or delta == 0:
            return
        player = self.selected_player
        self.player_life[player] += 1 if delta > 0 else -1
        self.pending_life_delta[player] += 1 if delta > 0 else -1

    def _record_generated_card(self, card: Dict[str, Any]) -> None:
        if not self.game_active:
            return
        card_name = str(card.get("name", "Unknown Card"))
        event = {
            "card_index": len(self.current_game_cards) + 1,
            "player": self.next_card_player,
            "card_name": card_name,
            "mana_value": self._current_mana_value(),
            "life_before_card": {
                "player1": self.player_life[1],
                "player2": self.player_life[2],
            },
            "life_delta_since_previous_card": {
                "player1": self.pending_life_delta[1],
                "player2": self.pending_life_delta[2],
            },
        }
        self.current_game_cards.append(event)
        self.pending_life_delta = {1: 0, 2: 0}
        self.next_card_player = 2 if self.next_card_player == 1 else 1

    def _open_end_game_prompt(self) -> None:
        if not self.game_active:
            return
        self._set_popup(
            "Was this game completed?",
            title="End Game",
            options=["No", "Yes"],
            selected_index=0,
            mode=POPUP_MODE_GAME_COMPLETE,
        )

    def _finalize_game_log(self) -> None:
        if not self.current_game_started_at:
            return
        record = build_game_log_record(
            started_at=self.current_game_started_at,
            ended_at=self._now_iso(),
            starting_player=self.starting_player or 1,
            cards=self.current_game_cards,
            final_life_totals=self.player_life,
        )
        try:
            path = save_game_log(record, logs_dir=GAME_LOGS_DIR)
            self._set_status_message(f"Game logged: {path.name}", 3000)
        except OSError:
            self._set_status_message("Could not save game log.", 3000)

    def _resolve_popup_selection(self) -> None:
        if self.popup_mode == POPUP_MODE_START_PLAYER:
            if self.popup_selected_index == 0:
                self._start_new_game(1)
                return
            if self.popup_selected_index == 1:
                self._start_new_game(2)
                return
            randomized = random.choice((1, 2))
            self.pending_random_starting_player = randomized
            self._set_popup(
                f"Player {randomized} will start.",
                title="Starting Player",
                mode=POPUP_MODE_RANDOM_START_RESULT,
            )
            return

        if self.popup_mode == POPUP_MODE_GAME_COMPLETE:
            if self.popup_selected_index == 1:
                self._finalize_game_log()
                self._open_start_player_prompt()
                return
            self._set_popup(None)

    def _handle_popup_action(self, action: str) -> bool:
        if self.popup_mode == POPUP_MODE_NONE:
            return False
        if self.popup_mode in (POPUP_MODE_START_PLAYER, POPUP_MODE_GAME_COMPLETE):
            if not self.popup_options:
                return True
            if action in (ACTION_UP, ACTION_LEFT):
                self.popup_selected_index = (
                    self.popup_selected_index - 1
                ) % len(self.popup_options)
                return True
            if action in (ACTION_DOWN, ACTION_RIGHT):
                self.popup_selected_index = (
                    self.popup_selected_index + 1
                ) % len(self.popup_options)
                return True
            if action in (ACTION_JOY_PRESS, ACTION_KEY1, ACTION_KNOB_PRESS):
                self._resolve_popup_selection()
                return True
            return True

        if self.popup_mode == POPUP_MODE_RANDOM_START_RESULT:
            if action in (ACTION_JOY_PRESS, ACTION_KEY1, ACTION_KNOB_PRESS):
                self._start_new_game(self.pending_random_starting_player or 1)
            return True
        return False

    def _detect_printer_at_startup(self) -> None:
        self.printer_connected = is_printer_connected()
        if not self.printer_connected:
            self.startup_status_message = "No printer connected. Printing is disabled."

    def _active_status_message(self) -> Optional[str]:
        if not self.status_message:
            return None
        if pygame.time.get_ticks() > self.status_message_until_ms:
            self.status_message = None
            return None
        return self.status_message

    def _pick_random_card(self) -> None:
        if not self.game_active:
            self._open_start_player_prompt()
            return
        self.is_loading = True
        self._set_popup(None)
        self._drop_pending_actions()
        self._render()
        pygame.event.pump()
        card = self.card_service.get_random_card(
            self._current_mana_value(), self.settings_schema, self.settings
        )
        self.is_loading = False
        self._drop_pending_actions()
        if card is None:
            self._set_popup("No matching card found.")
            return

        self._record_generated_card(card)
        card_name = card["name"]
        image_url = card["image_url"]
        if not self.printer_connected:
            self._set_popup(f"Your card is {card_name} (no printer connected)")
            return

        self._set_popup("Printing...", "Printer")
        self._render()
        pygame.event.pump()

        if not image_url:
            self._set_popup(f"Your card is {card_name}")
            self._set_status_message("Could not print card: missing image URL.", 3000)
            return

        printed = print_card_image(image_url)
        if printed:
            self._set_popup(None)
            return

        self.printer_connected = False
        self._set_popup(f"Your card is {card_name} (no printer connected)")

    def _drop_pending_actions(self) -> None:
        while True:
            try:
                self.action_queue.get_nowait()
            except queue.Empty:
                break

    def _save_settings_if_valid(self) -> None:
        self.is_loading = True
        self._drop_pending_actions()
        self._render()
        pygame.event.pump()

        candidate_settings = self._menu_settings()
        cache_preview = self.card_service.preview_runtime_cache(
            self.settings_schema, candidate_settings
        )
        preview_values = cache_preview.get("available_mana_values", [])
        available_values = (
            list(preview_values)
            if isinstance(preview_values, list)
            else []
        )
        self.is_loading = False
        self._drop_pending_actions()
        if not available_values:
            self._set_status_message("No cards match current filters. Not saved.", 3000)
            print("Settings not saved: no cards match current filters.")
            return

        previous_mana = self._current_mana_value()
        self.mana_pool.set_values(available_values, preferred_value=previous_mana)
        self.settings = deepcopy(candidate_settings)
        self.card_service.apply_runtime_cache_preview(cache_preview)
        save_settings(SETTINGS_PATH, self.settings)
        self.edit_settings = deepcopy(self.settings)
        self._set_status_message(
            f"Settings saved. {len(available_values)} mana values available.", 2600
        )
        print("Settings saved.")

    def _handle_action(self, action: str) -> None:
        if self.is_loading:
            return

        if self.state == STATE_MAIN_MENU:
            if self._handle_popup_action(action):
                return
            if action == ACTION_ROTARY_CW:
                self._inc_mana_index()
            elif action == ACTION_ROTARY_CCW:
                self._dec_mana_index()
            elif action == ACTION_KNOB_PRESS:
                if self.popup_message is not None:
                    self._set_popup(None)
                else:
                    self._pick_random_card()
            elif action == ACTION_LEFT:
                self._select_player(1)
            elif action == ACTION_RIGHT:
                self._select_player(2)
            elif action == ACTION_UP:
                self._adjust_life(1)
            elif action == ACTION_DOWN:
                self._adjust_life(-1)
            elif action == ACTION_JOY_PRESS:
                self._open_end_game_prompt()
            elif action == ACTION_KEY1:
                self._open_settings()
            elif action == ACTION_KEY2:
                self._open_printer_settings()
            elif action == ACTION_KEY3:
                self.running = False
            return

        if self.state == STATE_SETTINGS_MENU:
            if action == ACTION_UP:
                self._move_selection(-1)
            elif action == ACTION_DOWN:
                self._move_selection(1)
            elif action == ACTION_LEFT:
                if self.in_advanced_mode:
                    self._adjust_advanced_value(-1)
                else:
                    self._cycle_quick_option(-1)
            elif action == ACTION_RIGHT:
                if self.in_advanced_mode:
                    self._adjust_advanced_value(1)
                else:
                    self._cycle_quick_option(1)
            elif action == ACTION_KEY1:
                self._enter_submenu()
            elif action in (ACTION_KEY2, ACTION_JOY_PRESS):
                self._back()
            elif action == ACTION_KEY3:
                self._save_settings_if_valid()
            return

        if self.state == STATE_PRINTER_SETTINGS_MENU:
            if action == ACTION_UP:
                self._move_printer_selection(-1)
            elif action == ACTION_DOWN:
                self._move_printer_selection(1)
            elif action == ACTION_LEFT:
                self._adjust_printer_value(-1)
            elif action == ACTION_RIGHT:
                self._adjust_printer_value(1)
            elif action == ACTION_KEY1:
                if self.printer_settings_index == len(PRINT_SETTING_FIELDS):
                    self._save_printer_settings()
                elif self.printer_settings_index == len(PRINT_SETTING_FIELDS) + 1:
                    self._reset_printer_settings_to_baseline()
            elif action == ACTION_KEY3:
                self._save_printer_settings()
            elif action in (ACTION_KEY2, ACTION_JOY_PRESS):
                self._back()

    def _map_keyboard(self, key: int) -> Optional[str]:
        keyboard_map = {
            pygame.K_d: ACTION_ROTARY_CW,
            pygame.K_a: ACTION_ROTARY_CCW,
            pygame.K_SPACE: ACTION_KNOB_PRESS,
            pygame.K_UP: ACTION_UP,
            pygame.K_DOWN: ACTION_DOWN,
            pygame.K_LEFT: ACTION_LEFT,
            pygame.K_RIGHT: ACTION_RIGHT,
            pygame.K_RETURN: ACTION_KEY1,
            pygame.K_BACKSPACE: ACTION_KEY2,
            pygame.K_s: ACTION_KEY3,
        }
        return keyboard_map.get(key)

    def _process_pygame_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                    continue
                action = self._map_keyboard(event.key)
                if action:
                    self.action_queue.put(action)

    def _drain_actions(self) -> None:
        while True:
            try:
                action = self.action_queue.get_nowait()
            except queue.Empty:
                break
            self._handle_action(action)

    def _render(self) -> None:
        status_message = self._active_status_message()
        if self.state == STATE_MAIN_MENU:
            self.ui.draw_main_menu(
                self._current_mana_value(),
                popup_message=self.popup_message,
                popup_title=self.popup_title,
                popup_options=self.popup_options,
                popup_selected_index=self.popup_selected_index,
                selected_player=self.selected_player,
                player_life=self.player_life,
                status_message=status_message,
                is_loading=self.is_loading,
            )
        elif self.state == STATE_SETTINGS_MENU:
            current_setting = self._current_setting()
            menu_settings = self._menu_settings()
            disabled_setting_ids: set[str] = set()
            if self._is_card_list_active(menu_settings):
                disabled_setting_ids = {
                    str(setting.get("id", ""))
                    for setting in self.settings_schema
                    if str(setting.get("id", "")) != CARD_LIST_SETTING_ID
                }
            quick_labels: Dict[str, str] = {}
            for setting in self.settings_schema:
                setting_id = str(setting.get("id", ""))
                values = menu_settings.get(setting_id, {})
                quick_labels[setting_id] = quick_option_label(setting, values)
            self.ui.draw_settings_menu(
                settings_schema=self.settings_schema,
                selected_setting=self.settings_index,
                settings=menu_settings,
                in_advanced_mode=self.in_advanced_mode,
                selected_field=self.advanced_field_index,
                current_setting=current_setting,
                quick_labels=quick_labels,
                printer_entry_label="Printer Settings",
                divider_after_setting_id=CARD_LIST_SETTING_ID,
                disabled_setting_ids=disabled_setting_ids,
                status_message=status_message,
                is_loading=self.is_loading,
            )
        elif self.state == STATE_PRINTER_SETTINGS_MENU:
            self.ui.draw_printer_settings_menu(
                fields=PRINT_SETTING_FIELDS,
                selected_index=self.printer_settings_index,
                settings=self._printer_settings(),
                status_message=status_message,
                is_loading=self.is_loading,
            )
        self.ui.flip()

    def run(self) -> None:
        if not self.runtime_lock.acquire(blocking=False):
            print(
                "Momir is already running (or lock is busy). "
                "If this is unexpected, remove the stale lock and retry: "
                f"{self.runtime_lock.path}"
            )
            return

        try:
            self.ui.setup()
            if self.startup_status_message:
                self._set_status_message(self.startup_status_message, 3500)
            self.input.setup_gpio()
            clock = pygame.time.Clock()
            while self.running:
                self._process_pygame_events()
                self._drain_actions()
                self._render()
                clock.tick(30)
        finally:
            self.input.close_gpio()
            self.ui.shutdown()
            self.runtime_lock.release()


if __name__ == "__main__":
    MomirApp().run()
