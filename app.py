from __future__ import annotations

import queue
from typing import Any, Dict, List, Optional

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
    MANA_JUMP_THRESHOLD,
    MANA_JUMP_VALUE,
    MANA_MIN,
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
    save_settings,
)
from ui import UI


def printCard(mana_value: int, settings: Dict[str, bool]) -> None:
    # Keep settings accessible for future expansion.
    _ = settings
    print(f"Chose mana value {mana_value}")


class MomirApp:
    def __init__(self) -> None:
        self.running = True
        self.state = STATE_MAIN_MENU
        self.mana_value = 0

        self.action_queue: "queue.SimpleQueue[str]" = queue.SimpleQueue()
        self.input = InputController(self.action_queue)
        self.ui = UI()

        self.menu_tree = load_menu_schema(MENU_SCHEMA_PATH)
        self.default_settings = build_default_settings(self.menu_tree)
        self.settings = load_settings(SETTINGS_PATH, self.default_settings)

        self.menu_stack: List[List[Dict[str, Any]]] = [self.menu_tree]
        self.selection_stack: List[int] = [0]
        self.prefix_stack: List[str] = [""]

    def _inc_mana(self) -> None:
        if self.mana_value == MANA_JUMP_THRESHOLD:
            self.mana_value = MANA_JUMP_VALUE
        else:
            self.mana_value += 1

    def _dec_mana(self) -> None:
        self.mana_value = max(MANA_MIN, self.mana_value - 1)

    def _current_menu(self) -> List[Dict[str, Any]]:
        return self.menu_stack[-1]

    def _current_index(self) -> int:
        return self.selection_stack[-1]

    def _current_item(self) -> Dict[str, Any]:
        menu = self._current_menu()
        if not menu:
            return {}
        idx = max(0, min(self._current_index(), len(menu) - 1))
        self.selection_stack[-1] = idx
        return menu[idx]

    def _current_key(self, item: Dict[str, Any]) -> str:
        prefix = self.prefix_stack[-1]
        item_id = str(item.get("id", ""))
        return f"{prefix}.{item_id}" if prefix else item_id

    def _open_settings(self) -> None:
        self.state = STATE_SETTINGS_MENU

    def _move_selection(self, delta: int) -> None:
        menu = self._current_menu()
        if not menu:
            return
        idx = (self._current_index() + delta) % len(menu)
        self.selection_stack[-1] = idx

    def _toggle_selected(self) -> None:
        item = self._current_item()
        if not item:
            return
        key = self._current_key(item)
        current = bool(self.settings.get(key, False))
        self.settings[key] = not current

    def _enter_submenu(self) -> None:
        item = self._current_item()
        submenu = item.get("submenu")
        if not isinstance(submenu, list) or not submenu:
            return
        self.menu_stack.append(submenu)
        self.selection_stack.append(0)
        self.prefix_stack.append(self._current_key(item))

    def _back(self) -> None:
        if len(self.menu_stack) > 1:
            self.menu_stack.pop()
            self.selection_stack.pop()
            self.prefix_stack.pop()
            return
        self.state = STATE_MAIN_MENU

    def _handle_action(self, action: str) -> None:
        if self.state == STATE_MAIN_MENU:
            if action == ACTION_ROTARY_CW:
                self._inc_mana()
            elif action == ACTION_ROTARY_CCW:
                self._dec_mana()
            elif action == ACTION_KNOB_PRESS:
                printCard(self.mana_value, self.settings)
            elif action in ALL_HAT_ACTIONS:
                self._open_settings()
            return

        if self.state == STATE_SETTINGS_MENU:
            if action == ACTION_UP:
                self._move_selection(-1)
            elif action == ACTION_DOWN:
                self._move_selection(1)
            elif action in (ACTION_LEFT, ACTION_RIGHT):
                self._toggle_selected()
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
            self.ui.draw_main_menu(self.mana_value)
        else:
            current_path = self.prefix_stack[-1] if self.prefix_stack[-1] else "root"
            self.ui.draw_settings_menu(
                items=self._current_menu(),
                selected=self._current_index(),
                current_path=current_path,
                settings=self.settings,
                current_key_fn=self._current_key,
            )
        self.ui.flip()

    def run(self) -> None:
        self.ui.setup()
        self.input.setup_gpio()
        clock = pygame.time.Clock()
        try:
            while self.running:
                self._process_pygame_events()
                self._drain_actions()
                self._render()
                clock.tick(30)
        finally:
            self.input.close_gpio()
            self.ui.shutdown()


if __name__ == "__main__":
    MomirApp().run()
