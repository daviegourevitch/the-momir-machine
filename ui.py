from __future__ import annotations

from typing import Any, Dict, List, Optional

import pygame

from constants import BACKGROUND_PATH, SCREEN_HEIGHT, SCREEN_WIDTH, TOP_BANNER_HEIGHT
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

    def setup(self) -> None:
        pygame.init()
        pygame.display.set_caption("Momir Machine")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
        pygame.mouse.set_visible(False)
        self.title_font = pygame.font.Font(None, 24)
        self.banner_label_font = pygame.font.Font(None, 17)
        self.menu_font = pygame.font.Font(None, 20)
        self.hint_font = pygame.font.Font(None, 16)
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

    def draw_main_menu(self, mana_value: int) -> None:
        if self.screen is None or self.banner_label_font is None:
            return
        self.screen.fill((0, 0, 0))
        if self.background_surface is not None:
            self.screen.blit(self.background_surface, (0, self.background_y))

        pygame.draw.rect(self.screen, (0, 0, 0), (0, 0, SCREEN_WIDTH, TOP_BANNER_HEIGHT))

        label = self.banner_label_font.render("Current mana value", True, (255, 255, 255))
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
        elif self.title_font is not None:
            value_text = self.title_font.render(str(mana_value), True, (255, 255, 255))
            value_x = SCREEN_WIDTH - BANNER_PAD_X - value_text.get_width()
            value_y = (TOP_BANNER_HEIGHT - value_text.get_height()) // 2
            self.screen.blit(value_text, (value_x, value_y))

    def draw_settings_menu(
        self,
        items: List[Dict[str, Any]],
        selected: int,
        current_path: str,
        settings: Dict[str, bool],
        current_key_fn: Any,
    ) -> None:
        if self.screen is None or self.title_font is None or self.menu_font is None:
            return
        self.screen.fill((10, 10, 10))

        title = self.title_font.render(f"Settings: {current_path}", True, (230, 230, 230))
        self.screen.blit(title, (8, 8))

        if not items:
            empty_text = self.menu_font.render("No menu items", True, (220, 220, 220))
            self.screen.blit(empty_text, (8, 50))
            return

        row_height = 22
        top_y = 38
        max_rows = max(1, (SCREEN_HEIGHT - top_y - 24) // row_height)
        start = max(0, min(selected - max_rows + 1, len(items) - max_rows))
        end = min(len(items), start + max_rows)

        for row, idx in enumerate(range(start, end)):
            item = items[idx]
            y = top_y + row * row_height
            is_selected = idx == selected
            if is_selected:
                pygame.draw.rect(self.screen, (70, 70, 70), (4, y - 2, SCREEN_WIDTH - 8, row_height))

            key = current_key_fn(item)
            value = "ON" if settings.get(key, False) else "OFF"
            suffix = " >" if isinstance(item.get("submenu"), list) and item.get("submenu") else ""
            line = f"{item['label']}: {value}{suffix}"
            text_surface = self.menu_font.render(line, True, (255, 255, 255))
            self.screen.blit(text_surface, (8, y))

        if self.hint_font is not None:
            hint = self.hint_font.render("K1 open  K2/JOY back  K3 save", True, (170, 170, 170))
            self.screen.blit(hint, (6, SCREEN_HEIGHT - 18))

    def flip(self) -> None:
        pygame.display.flip()

    def shutdown(self) -> None:
        pygame.quit()
