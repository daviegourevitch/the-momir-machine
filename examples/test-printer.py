#!/usr/bin/env python3
from __future__ import annotations

from io import BytesIO
import sys
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageEnhance, ImageFilter

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

    image = Image.open(BytesIO(response.content))
    image = flatten_alpha_to_white(image)
    if image.width != target_width:
        ratio = target_width / float(image.width)
        target_height = max(1, int(image.height * ratio))
        image = image.resize((target_width, target_height), Image.Resampling.BICUBIC)
    return image


def flatten_alpha_to_white(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    background.paste(rgba, mask=rgba.split()[3])
    return background.convert("RGB")


def to_grayscale(image: Image.Image) -> Image.Image:
    return image.convert("L")


def apply_gamma(image: Image.Image, gamma: float) -> Image.Image:
    arr = np.array(image, dtype=np.float32) / 255.0
    arr = np.power(arr, 1.0 / gamma)
    return Image.fromarray((arr * 255).astype(np.uint8), mode="L")


def enhance_contrast(image: Image.Image, factor: float) -> Image.Image:
    return ImageEnhance.Contrast(image).enhance(factor)


def apply_unsharp(
    image: Image.Image, radius: float, percent: int, threshold: int
) -> Image.Image:
    return image.filter(
        ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=threshold)
    )


def threshold_image(image: Image.Image, threshold: int) -> Image.Image:
    # Convert to hard black/white without dithering for cleaner text edges.
    return image.point(lambda pixel: 255 if pixel > threshold else 0, mode="1")


def build_preprocessed_image(source_image: Image.Image) -> Image.Image:
    image = to_grayscale(source_image)
    image = apply_gamma(image, gamma=1.8)
    image = enhance_contrast(image, factor=2.0)
    image = apply_unsharp(image, radius=1.0, percent=150, threshold=3)
    return image


def build_variants(source_image: Image.Image) -> list[tuple[str, str, Image.Image]]:
    baseline_gray = to_grayscale(source_image)
    preprocessed = build_preprocessed_image(source_image)

    return [
        (
            "Baseline Floyd-Steinberg",
            "Pipeline: grayscale -> Floyd-Steinberg dither",
            baseline_gray.convert("1"),
        ),
        (
            "Preprocessed Floyd-Steinberg",
            "Pipeline: alpha flatten, gray, gamma=1.8, contrast=2.0, unsharp=1/150/3, dither",
            preprocessed.convert("1"),
        ),
        (
            "Preprocessed Hard Threshold 50%",
            "Pipeline: alpha flatten, gray, gamma=1.8, contrast=2.0, unsharp=1/150/3, threshold=128",
            threshold_image(preprocessed, 128),
        ),
        (
            "Preprocessed Hard Threshold 55%",
            "Pipeline: alpha flatten, gray, gamma=1.8, contrast=2.0, unsharp=1/150/3, threshold=140",
            threshold_image(preprocessed, 140),
        ),
        (
            "Preprocessed Hard Threshold 60%",
            "Pipeline: alpha flatten, gray, gamma=1.8, contrast=2.0, unsharp=1/150/3, threshold=153",
            threshold_image(preprocessed, 153),
        ),
    ]


def main() -> int:
    printer = detect_usb_printer()
    if printer is None:
        print("no printer")
        return 0

    try:
        source_image = fetch_source_image(DEFAULT_URL)
        variants = build_variants(source_image)
        printer.text("Top 5 print option comparison\n")
        printer.text("=============================\n\n")

        for index, (label, details, image) in enumerate(variants, start=1):
            printer.text(f"Option {index}: {label}\n")
            printer.text(f"{details}\n")
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
