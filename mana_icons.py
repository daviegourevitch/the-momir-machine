from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Optional

import pygame

from constants import MANA_ICONS_DIR

_RASTER_HEIGHT = 256
_master_cache: dict[int, pygame.Surface] = {}
_miss_cache: set[int] = set()
_have_cairo: Optional[bool] = None


def _get_cairosvg():
    global _have_cairo
    if _have_cairo is False:
        return None
    try:
        import cairosvg

        _have_cairo = True
        return cairosvg
    except ImportError:
        _have_cairo = False
        return None


def svg_path_for_mana(mana_value: int) -> Optional[Path]:
    path = MANA_ICONS_DIR / f"{mana_value}.svg"
    return path if path.is_file() else None


def load_mana_icon_master(mana_value: int) -> Optional[pygame.Surface]:
    if mana_value in _master_cache:
        return _master_cache[mana_value]
    if mana_value in _miss_cache:
        return None

    path = svg_path_for_mana(mana_value)
    if path is None:
        _miss_cache.add(mana_value)
        return None

    cairosvg = _get_cairosvg()
    if cairosvg is None:
        return None

    try:
        buf = BytesIO()
        cairosvg.svg2png(url=str(path), write_to=buf, output_height=_RASTER_HEIGHT)
        buf.seek(0)
        surface = pygame.image.load(buf).convert_alpha()
        _master_cache[mana_value] = surface
        return surface
    except Exception:
        _miss_cache.add(mana_value)
        return None


def scaled_mana_icon(
    mana_value: int, max_width: int, max_height: int
) -> Optional[pygame.Surface]:
    if max_width < 2 or max_height < 2:
        return None
    master = load_mana_icon_master(mana_value)
    if master is None:
        return None
    w, h = master.get_size()
    scale = min(max_width / w, max_height / h)
    if scale >= 1:
        return master
    nw = max(1, int(w * scale))
    nh = max(1, int(h * scale))
    return pygame.transform.smoothscale(master, (nw, nh))
