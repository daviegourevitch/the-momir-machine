#!/usr/bin/env python3
from __future__ import annotations

from io import BytesIO
import sys
from pathlib import Path

import requests
from PIL import Image, ImageFilter, ImageOps

# Ensure the repository root is importable when running this script directly.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from printer_service import PRINTER_WIDTH_PX, detect_usb_printer


DEFAULT_URL = (
    "https://cards.scryfall.io/png/front/b/9/b93c5869-7777-44bb-967a-e9439b25ced4.png?1559591655"
)


def fetch_source_image(url: str, target_width: int = PRINTER_WIDTH_PX) -> Image.Image:
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    image = Image.open(BytesIO(response.content)).convert("L")
    if image.width != target_width:
        ratio = target_width / float(image.width)
        target_height = max(1, int(image.height * ratio))
        image = image.resize((target_width, target_height), Image.Resampling.BICUBIC)
    return image


def threshold_image(image: Image.Image, threshold: int) -> Image.Image:
    # Convert to hard black/white without dithering for cleaner text edges.
    return image.point(lambda pixel: 255 if pixel > threshold else 0, mode="1")


def build_variants(source_image: Image.Image) -> list[tuple[str, Image.Image]]:
    enhanced = ImageOps.autocontrast(source_image, cutoff=2)
    enhanced = enhanced.filter(
        ImageFilter.UnsharpMask(radius=1.0, percent=180, threshold=2)
    )

    return [
        ("Baseline dither", source_image.convert("1")),
        ("No dither threshold 160", threshold_image(source_image, 160)),
        ("No dither threshold 180", threshold_image(source_image, 180)),
        ("Auto contrast + sharpen + threshold 170", threshold_image(enhanced, 170)),
    ]


def main() -> int:
    printer = detect_usb_printer()
    if printer is None:
        print("no printer")
        return 0

    try:
        source_image = fetch_source_image(DEFAULT_URL)
        variants = build_variants(source_image)
        printer.text("Image conversion comparison\n")
        printer.text("=========================\n\n")

        for index, (label, image) in enumerate(variants, start=1):
            printer.text(f"{index}. {label}\n")
            printer.image(image)
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
