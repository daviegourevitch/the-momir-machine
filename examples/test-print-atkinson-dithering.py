#!/usr/bin/env python3
from __future__ import annotations

from io import BytesIO
import sys
from pathlib import Path

import requests
from PIL import Image

# Ensure the repository root is importable when running this script directly.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from printer_service import PRINTER_WIDTH_PX, detect_usb_printer


DEFAULT_URL = (
    "https://cards.scryfall.io/png/front/b/9/b93c5869-7777-44bb-967a-e9439b25ced4.png?1559591655"
)


def flatten_alpha_to_white(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    background.paste(rgba, mask=rgba.split()[3])
    return background.convert("RGB")


def fetch_source_image(url: str, target_width: int = PRINTER_WIDTH_PX) -> Image.Image:
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    image = Image.open(BytesIO(response.content))
    image = flatten_alpha_to_white(image).convert("L")
    if image.width != target_width:
        ratio = target_width / float(image.width)
        target_height = max(1, int(image.height * ratio))
        image = image.resize((target_width, target_height), Image.Resampling.BICUBIC)
    return image


def atkinson_dither(image: Image.Image) -> Image.Image:
    grayscale = image.convert("L")
    width, height = grayscale.size
    buffer = [float(pixel) for pixel in grayscale.getdata()]
    out_pixels = [255] * (width * height)

    def add_error(nx: int, ny: int, amount: float) -> None:
        if 0 <= nx < width and 0 <= ny < height:
            idx = ny * width + nx
            value = buffer[idx] + amount
            if value < 0.0:
                value = 0.0
            elif value > 255.0:
                value = 255.0
            buffer[idx] = value

    for y in range(height):
        row_start = y * width
        for x in range(width):
            idx = row_start + x
            old_pixel = buffer[idx]
            new_pixel = 255.0 if old_pixel >= 128.0 else 0.0
            out_pixels[idx] = int(new_pixel)
            error = (old_pixel - new_pixel) / 8.0

            add_error(x + 1, y, error)
            add_error(x + 2, y, error)
            add_error(x - 1, y + 1, error)
            add_error(x, y + 1, error)
            add_error(x + 1, y + 1, error)
            add_error(x, y + 2, error)

    dithered = Image.new("L", (width, height))
    dithered.putdata(out_pixels)
    return dithered.convert("1", dither=Image.Dither.NONE)


def main() -> int:
    printer = detect_usb_printer()
    if printer is None:
        print("no printer")
        return 0

    try:
        source_image = fetch_source_image(DEFAULT_URL)
        dithered = atkinson_dither(source_image)
        printer.text("Atkinson dithering test\n")
        printer.text("=======================\n")
        printer.text("Pipeline: alpha flatten, grayscale, Atkinson error diffusion\n\n")
        printer.image(dithered)
        printer.text("\n")
        try:
            printer.cut()
        except Exception:
            # Not all thermal printers support cut.
            pass
    finally:
        try:
            printer.close()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
