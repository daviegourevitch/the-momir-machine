from __future__ import annotations

import queue
from typing import Any, Dict, Optional

import pygame

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
    ALL_HAT_ACTIONS,
    MANA_VALUES,
    MENU_SCHEMA_PATH,
    SETTINGS_PATH,
    STATE_MAIN_MENU,
    STATE_SETTINGS_MENU,
)
from input_controller import InputController
from settings_store import (
    build_default_settings,
    load_menu_schema,
    load_settings,
    quick_option_index,
    quick_option_label,
    save_settings,
)
from ui import UI
from runtime_coordination import RuntimeLock


def printCard(
    mana_value: int | float, settings: Dict[str, Dict[str, bool | int | float | str]]
) -> None:
    # Keep settings accessible for future expansion.
    _ = settings
    print(f"Chose mana value {mana_value}")


class MomirApp:
    def __init__(self) -> None:
        self.running = True
        self.state = STATE_MAIN_MENU
        self.mana_index = 0

        self.action_queue: "queue.SimpleQueue[str]" = queue.SimpleQueue()
        self.input = InputController(self.action_queue)
        self.ui = UI()

        self.settings_schema = load_menu_schema(MENU_SCHEMA_PATH)
        self.default_settings = build_default_settings(self.settings_schema)
        self.settings = load_settings(
            SETTINGS_PATH, self.default_settings, self.settings_schema
        )

        self.settings_index = 0
        self.advanced_field_index = 0
        self.in_advanced_mode = False
        self.runtime_lock = RuntimeLock()

    def _inc_mana_index(self) -> None:
        self.mana_index = min(self.mana_index + 1, len(MANA_VALUES) - 1)

    def _dec_mana_index(self) -> None:
        self.mana_index = max(self.mana_index - 1, 0)

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
        return self.settings.setdefault(setting_id, {})

    def _current_advanced_field(self) -> Dict[str, Any]:
        setting = self._current_setting()
        fields = setting.get("advanced_fields", [])
        if not isinstance(fields, list) or not fields:
            return {}
        idx = max(0, min(self.advanced_field_index, len(fields) - 1))
        self.advanced_field_index = idx
        return fields[idx]

    def _open_settings(self) -> None:
        self.state = STATE_SETTINGS_MENU
        self.in_advanced_mode = False

    def _move_selection(self, delta: int) -> None:
        if self.in_advanced_mode:
            fields = self._current_setting().get("advanced_fields", [])
            if not isinstance(fields, list) or not fields:
                return
            self.advanced_field_index = (self.advanced_field_index + delta) % len(fields)
            return

        if not self.settings_schema:
            return
        self.settings_index = (self.settings_index + delta) % len(self.settings_schema)

    @staticmethod
    def _is_number(value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    def _cycle_quick_option(self, delta: int) -> None:
        setting = self._current_setting()
        if not setting:
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

    def _enter_submenu(self) -> None:
        setting = self._current_setting()
        fields = setting.get("advanced_fields", [])
        if not isinstance(fields, list) or not fields:
            return
        self.in_advanced_mode = True
        self.advanced_field_index = 0

    def _back(self) -> None:
        if self.in_advanced_mode:
            self.in_advanced_mode = False
            return
        self.state = STATE_MAIN_MENU

    def _handle_action(self, action: str) -> None:
        if self.state == STATE_MAIN_MENU:
            if action == ACTION_ROTARY_CW:
                self._inc_mana_index()
            elif action == ACTION_ROTARY_CCW:
                self._dec_mana_index()
            elif action == ACTION_KNOB_PRESS:
                printCard(MANA_VALUES[self.mana_index], self.settings)
            elif action in ALL_HAT_ACTIONS:
                self._open_settings()
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
                save_settings(SETTINGS_PATH, self.settings)
                print("Settings saved.")

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
        if self.state == STATE_MAIN_MENU:
            self.ui.draw_main_menu(MANA_VALUES[self.mana_index])
        else:
            current_setting = self._current_setting()
            quick_labels: Dict[str, str] = {}
            for setting in self.settings_schema:
                setting_id = str(setting.get("id", ""))
                values = self.settings.get(setting_id, {})
                quick_labels[setting_id] = quick_option_label(setting, values)
            self.ui.draw_settings_menu(
                settings_schema=self.settings_schema,
                selected_setting=self.settings_index,
                settings=self.settings,
                in_advanced_mode=self.in_advanced_mode,
                selected_field=self.advanced_field_index,
                current_setting=current_setting,
                quick_labels=quick_labels,
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
