from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Union

import pygame

from constants import (
    BACKGROUND_PATH,
    BELEREN_FONT_PATH,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TOP_BANNER_HEIGHT,
)
from mana_icons import scaled_mana_icon


BANNER_PAD_X = 8
BANNER_PAD_Y = 4
BANNER_LABEL_ICON_GAP = 6


class UI:
    def __init__(self) -> None:
        self.screen: Optional[pygame.Surface] = None
        self.background_surface: Optional[pygame.Surface] = None
        self.background_y = 0
        self.title_font: Optional[pygame.font.Font] = None
        self.banner_label_font: Optional[pygame.font.Font] = None
        self.menu_font: Optional[pygame.font.Font] = None
        self.hint_font: Optional[pygame.font.Font] = None
        self.main_menu_label_font: Optional[pygame.font.Font] = None
        self.main_menu_value_font: Optional[pygame.font.Font] = None

    def _draw_loading_overlay(self) -> None:
        if self.screen is None:
            return
        title_font = self.title_font or self.menu_font
        hint_font = self.hint_font
        if title_font is None or hint_font is None:
            return

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))

        ticks = pygame.time.get_ticks()
        dots = "." * ((ticks // 250) % 4)
        loading_text = title_font.render(f"Loading{dots}", True, (255, 255, 255))
        hint_text = hint_font.render("Please wait", True, (210, 210, 210))

        self.screen.blit(
            loading_text,
            (
                (SCREEN_WIDTH - loading_text.get_width()) // 2,
                (SCREEN_HEIGHT // 2) - loading_text.get_height(),
            ),
        )
        self.screen.blit(
            hint_text,
            (
                (SCREEN_WIDTH - hint_text.get_width()) // 2,
                (SCREEN_HEIGHT // 2) + 6,
            ),
        )

    def _draw_status_banner(self, text: str) -> None:
        if self.screen is None or self.hint_font is None:
            return
        pad_x = 6
        pad_y = 3
        text_surface = self.hint_font.render(text, True, (255, 255, 255))
        width = min(SCREEN_WIDTH - 8, text_surface.get_width() + pad_x * 2)
        rect = pygame.Rect(4, SCREEN_HEIGHT - 36, width, text_surface.get_height() + pad_y * 2)
        pygame.draw.rect(self.screen, (120, 30, 30), rect)
        self.screen.blit(text_surface, (rect.x + pad_x, rect.y + pad_y))

    def _draw_life_panel(self, player_life: Dict[int, int], selected_player: int) -> None:
        if self.screen is None or self.menu_font is None:
            return
        panel_x = 8
        panel_y = TOP_BANNER_HEIGHT + 8
        panel_width = SCREEN_WIDTH - 16
        panel_height = 48
        pygame.draw.rect(self.screen, (0, 0, 0), (panel_x, panel_y, panel_width, panel_height))
        pygame.draw.rect(
            self.screen, (110, 110, 110), (panel_x, panel_y, panel_width, panel_height), 1
        )

        rows = (
            (1, f"P1: {player_life.get(1, 20)}"),
            (2, f"P2: {player_life.get(2, 20)}"),
        )
        for idx, (player, label) in enumerate(rows):
            y = panel_y + 4 + (idx * 22)
            is_selected = player == selected_player
            if is_selected:
                pygame.draw.rect(self.screen, (60, 60, 60), (panel_x + 3, y - 2, panel_width - 6, 20))
            text = self.menu_font.render(label, True, (255, 255, 255))
            self.screen.blit(text, (panel_x + 6, y))

    def _draw_popup(
        self,
        text: str,
        title: str = "Random Card",
        options: List[str] | None = None,
        selected_index: int = 0,
    ) -> None:
        if self.screen is None:
            return
        title_font = self.title_font or self.menu_font
        body_font = self.menu_font or self.hint_font
        if title_font is None or body_font is None:
            return

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))

        box_width = SCREEN_WIDTH - 26
        box_height = 140 if options else 96
        box_x = (SCREEN_WIDTH - box_width) // 2
        box_y = (SCREEN_HEIGHT - box_height) // 2
        pygame.draw.rect(self.screen, (28, 28, 28), (box_x, box_y, box_width, box_height))
        pygame.draw.rect(self.screen, (220, 220, 220), (box_x, box_y, box_width, box_height), 1)

        heading = title_font.render(title, True, (255, 255, 255))
        self.screen.blit(heading, (box_x + 8, box_y + 8))

        body = body_font.render(text, True, (255, 255, 255))
        self.screen.blit(body, (box_x + 8, box_y + 40))

        if self.hint_font is not None:
            dismiss_text = (
                "D-pad select, press in to confirm"
                if options
                else "Press in or knob to dismiss"
            )
            dismiss = self.hint_font.render(dismiss_text, True, (200, 200, 200))
            self.screen.blit(dismiss, (box_x + 8, box_y + box_height - 20))

        if options and self.menu_font is not None:
            selected = max(0, min(selected_index, len(options) - 1))
            for index, option in enumerate(options):
                option_y = box_y + 62 + (index * 20)
                is_selected = index == selected
                if is_selected:
                    pygame.draw.rect(
                        self.screen,
                        (70, 70, 70),
                        (box_x + 6, option_y - 2, box_width - 12, 18),
                    )
                option_surface = self.menu_font.render(option, True, (255, 255, 255))
                self.screen.blit(option_surface, (box_x + 10, option_y))

    def setup(self) -> None:
        pygame.init()
        pygame.display.set_caption("Momir Machine")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
        pygame.mouse.set_visible(False)
        self.title_font = pygame.font.Font(None, 24)
        self.banner_label_font = pygame.font.Font(None, 17)
        self.menu_font = pygame.font.Font(None, 20)
        self.hint_font = pygame.font.Font(None, 16)
        if BELEREN_FONT_PATH.is_file():
            self.main_menu_label_font = pygame.font.Font(str(BELEREN_FONT_PATH), 17)
            self.main_menu_value_font = pygame.font.Font(str(BELEREN_FONT_PATH), 24)
        else:
            self.main_menu_label_font = pygame.font.Font(None, 17)
            self.main_menu_value_font = pygame.font.Font(None, 24)
        self._load_background()

    def _load_background(self) -> None:
        if self.screen is None:
            return
        if not BACKGROUND_PATH.exists():
            self.background_surface = None
            self.background_y = 0
            return
        image = pygame.image.load(str(BACKGROUND_PATH)).convert()
        width = SCREEN_WIDTH
        height = max(1, int((image.get_height() / image.get_width()) * width))
        self.background_surface = pygame.transform.smoothscale(image, (width, height))
        self.background_y = SCREEN_HEIGHT - self.background_surface.get_height()

    def draw_main_menu(
        self,
        mana_value: Union[int, float],
        popup_message: str | None = None,
        popup_title: str = "Random Card",
        popup_options: List[str] | None = None,
        popup_selected_index: int = 0,
        selected_player: int = 1,
        player_life: Dict[int, int] | None = None,
        status_message: str | None = None,
        is_loading: bool = False,
    ) -> None:
        if self.screen is None:
            return
        label_font = self.main_menu_label_font or self.banner_label_font
        value_font = self.main_menu_value_font or self.title_font
        if label_font is None:
            return
        self.screen.fill((0, 0, 0))
        if self.background_surface is not None:
            self.screen.blit(self.background_surface, (0, self.background_y))

        pygame.draw.rect(self.screen, (0, 0, 0), (0, 0, SCREEN_WIDTH, TOP_BANNER_HEIGHT))

        label = label_font.render("Current mana value", True, (255, 255, 255))
        label_y = (TOP_BANNER_HEIGHT - label.get_height()) // 2
        self.screen.blit(label, (BANNER_PAD_X, label_y))

        inner_h = max(1, TOP_BANNER_HEIGHT - 2 * BANNER_PAD_Y)
        max_icon_w = SCREEN_WIDTH - BANNER_PAD_X - label.get_width() - BANNER_LABEL_ICON_GAP - BANNER_PAD_X
        max_icon_w = max(0, max_icon_w)

        icon = scaled_mana_icon(mana_value, max_icon_w, inner_h)
        if icon is not None:
            icon_x = SCREEN_WIDTH - BANNER_PAD_X - icon.get_width()
            icon_y = (TOP_BANNER_HEIGHT - icon.get_height()) // 2
            self.screen.blit(icon, (icon_x, icon_y))
        elif value_font is not None:
            value_text = value_font.render(str(mana_value), True, (255, 255, 255))
            value_x = SCREEN_WIDTH - BANNER_PAD_X - value_text.get_width()
            value_y = (TOP_BANNER_HEIGHT - value_text.get_height()) // 2
            self.screen.blit(value_text, (value_x, value_y))

        self._draw_life_panel(player_life or {1: 20, 2: 20}, selected_player)

        if self.hint_font is not None:
            hint = self.hint_font.render(
                "K1 Game Settings / K2 Print Settings / K3 Quit",
                True,
                (170, 170, 170),
            )
            self.screen.blit(hint, (6, SCREEN_HEIGHT - 18))

        if status_message:
            self._draw_status_banner(status_message)
        if popup_message:
            self._draw_popup(
                popup_message,
                title=popup_title,
                options=popup_options,
                selected_index=popup_selected_index,
            )
        if is_loading:
            self._draw_loading_overlay()

    def draw_settings_menu(
        self,
        settings_schema: List[Dict[str, Any]],
        selected_setting: int,
        settings: Dict[str, Dict[str, bool | int | float | str]],
        in_advanced_mode: bool,
        selected_field: int,
        current_setting: Dict[str, Any],
        quick_labels: Dict[str, str],
        divider_after_setting_id: str | None = None,
        disabled_setting_ids: Set[str] | None = None,
        status_message: str | None = None,
        is_loading: bool = False,
    ) -> None:
        if self.screen is None or self.title_font is None or self.menu_font is None:
            return
        self.screen.fill((10, 10, 10))

        title_text = "Settings" if not in_advanced_mode else f"Advanced: {current_setting.get('label', '')}"
        title = self.title_font.render(title_text, True, (230, 230, 230))
        self.screen.blit(title, (8, 8))

        row_height = 22
        top_y = 38
        max_rows = max(1, (SCREEN_HEIGHT - top_y - 24) // row_height)

        if in_advanced_mode:
            fields = current_setting.get("advanced_fields", [])
            setting_id = str(current_setting.get("id", ""))
            setting_values = settings.get(setting_id, {})
            if not isinstance(fields, list) or not fields:
                empty_text = self.menu_font.render("No advanced fields", True, (220, 220, 220))
                self.screen.blit(empty_text, (8, 50))
                return

            selected_field = max(0, min(selected_field, len(fields) - 1))
            start = max(0, min(selected_field - max_rows + 1, len(fields) - max_rows))
            end = min(len(fields), start + max_rows)

            for row, idx in enumerate(range(start, end)):
                field = fields[idx]
                y = top_y + row * row_height
                is_selected = idx == selected_field
                if is_selected:
                    pygame.draw.rect(self.screen, (70, 70, 70), (4, y - 2, SCREEN_WIDTH - 8, row_height))

                field_id = str(field.get("id", ""))
                label = str(field.get("label", field_id))
                value = setting_values.get(field_id, field.get("default"))
                if isinstance(value, bool):
                    value_text = "ON" if value else "OFF"
                else:
                    value_text = str(value)
                line = f"{label}: {value_text}"
                text_surface = self.menu_font.render(line, True, (255, 255, 255))
                self.screen.blit(text_surface, (8, y))

            if self.hint_font is not None:
                hint = self.hint_font.render("L/R change  K2/JOY back  K3 save", True, (170, 170, 170))
                self.screen.blit(hint, (6, SCREEN_HEIGHT - 18))
                if status_message:
                    self._draw_status_banner(status_message)
            return

        if not settings_schema:
            empty_text = self.menu_font.render("No menu items", True, (220, 220, 220))
            self.screen.blit(empty_text, (8, 50))
            return

        settings_rows = len(settings_schema)
        selected_setting = max(0, min(selected_setting, settings_rows - 1))
        selected_setting_id = str(settings_schema[selected_setting].get("id", ""))
        disabled_ids = disabled_setting_ids or set()
        selected_is_disabled = selected_setting_id in disabled_ids
        selected_can_advanced = (
            bool(settings_schema[selected_setting].get("show_advanced", False))
            and not selected_is_disabled
        )
        start = max(0, min(selected_setting - max_rows + 1, settings_rows - max_rows))
        end = min(settings_rows, start + max_rows)

        for row, idx in enumerate(range(start, end)):
            y = top_y + row * row_height
            is_selected = idx == selected_setting
            if is_selected:
                pygame.draw.rect(self.screen, (70, 70, 70), (4, y - 2, SCREEN_WIDTH - 8, row_height))

            item = settings_schema[idx]
            setting_id = str(item.get("id", ""))
            label = str(item.get("label", setting_id))
            quick_label = quick_labels.get(setting_id, "Custom")
            advanced_suffix = " >" if bool(item.get("show_advanced", False)) else ""
            line = f"{label}: {quick_label}{advanced_suffix}"
            text_color = (130, 130, 130) if setting_id in disabled_ids else (255, 255, 255)
            text_surface = self.menu_font.render(line, True, text_color)
            self.screen.blit(text_surface, (8, y))
            if (
                idx < len(settings_schema)
                and str(settings_schema[idx].get("id", "")) == divider_after_setting_id
            ):
                line_y = y + row_height - 4
                pygame.draw.line(
                    self.screen,
                    (95, 95, 95),
                    (8, line_y),
                    (SCREEN_WIDTH - 8, line_y),
                    1,
                )

        if self.hint_font is not None:
            if selected_is_disabled:
                hint_text = "List selected: this setting is disabled  K2/JOY back  K3 save"
            else:
                hint_text = (
                    "L/R quick  K1 advanced  K2/JOY back  K3 save"
                    if selected_can_advanced
                    else "L/R quick  K2/JOY back  K3 save"
                )
            hint = self.hint_font.render(hint_text, True, (170, 170, 170))
            self.screen.blit(hint, (6, SCREEN_HEIGHT - 18))
            if status_message:
                self._draw_status_banner(status_message)

        if is_loading:
            self._draw_loading_overlay()

    def draw_printer_settings_menu(
        self,
        fields: List[Dict[str, Any]],
        selected_index: int,
        settings: Dict[str, bool | int | float],
        status_message: str | None = None,
        is_loading: bool = False,
    ) -> None:
        if self.screen is None or self.title_font is None or self.menu_font is None:
            return

        self.screen.fill((10, 10, 10))
        title = self.title_font.render("Printer Settings", True, (230, 230, 230))
        self.screen.blit(title, (8, 8))

        row_height = 22
        top_y = 38
        rows: List[str] = []

        for field in fields:
            field_id = str(field.get("id", ""))
            label = str(field.get("label", field_id))
            value = settings.get(field_id, "")
            if isinstance(value, bool):
                value_text = "ON" if value else "OFF"
            elif isinstance(value, float):
                value_text = f"{value:.2f}"
            else:
                value_text = str(value)
            rows.append(f"{label}: {value_text}")

        rows.append("Save settings")
        rows.append("Reset to baseline")

        if not rows:
            return

        selected_index = max(0, min(selected_index, len(rows) - 1))
        max_rows = max(1, (SCREEN_HEIGHT - top_y - 24) // row_height)
        start = max(0, min(selected_index - max_rows + 1, len(rows) - max_rows))
        end = min(len(rows), start + max_rows)

        for row, idx in enumerate(range(start, end)):
            y = top_y + row * row_height
            is_selected = idx == selected_index
            if is_selected:
                pygame.draw.rect(self.screen, (70, 70, 70), (4, y - 2, SCREEN_WIDTH - 8, row_height))
            text_surface = self.menu_font.render(rows[idx], True, (255, 255, 255))
            self.screen.blit(text_surface, (8, y))

        if self.hint_font is not None:
            hint = self.hint_font.render(
                "U/D select  L/R adjust  K1 action  K2/JOY back  K3 save",
                True,
                (170, 170, 170),
            )
            self.screen.blit(hint, (6, SCREEN_HEIGHT - 18))
            if status_message:
                self._draw_status_banner(status_message)

        if is_loading:
            self._draw_loading_overlay()

    def flip(self) -> None:
        pygame.display.flip()

    def shutdown(self) -> None:
        pygame.quit()
