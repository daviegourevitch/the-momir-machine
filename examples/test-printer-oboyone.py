#!/usr/bin/env python3
from __future__ import annotations

from io import BytesIO
import subprocess
import sys
import tempfile
from pathlib import Path

import requests
from PIL import Image

# Ensure the repository root is importable when running this script directly.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from printer_service import detect_usb_printer

DEFAULT_URL = (
    "https://cards.scryfall.io/png/front/b/9/b93c5869-7777-44bb-967a-e9439b25ced4.png?1559591655"
)
PRINTER_WIDTH_PX = 384


def fetch_image_bytes(url: str) -> bytes:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.content


def run_imagemagick_convert(
    input_path: Path, output_path: Path, target_width: int = PRINTER_WIDTH_PX
) -> None:
    commands = [
        [
            "magick",
            str(input_path),
            "-resize",
            f"{target_width}x",
            "-colorspace",
            "Gray",
            "-monochrome",
            str(output_path),
        ],
        [
            "magick",
            "convert",
            str(input_path),
            "-resize",
            f"{target_width}x",
            "-colorspace",
            "Gray",
            "-monochrome",
            str(output_path),
        ],
        [
            "convert",
            str(input_path),
            "-resize",
            f"{target_width}x",
            "-colorspace",
            "Gray",
            "-monochrome",
            str(output_path),
        ],
    ]

    last_error: Exception | None = None
    for command in commands:
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
            return
        except FileNotFoundError as exc:
            last_error = exc
        except subprocess.CalledProcessError as exc:
            last_error = RuntimeError(
                f"ImageMagick command failed: {' '.join(command)}\n"
                f"stdout: {exc.stdout}\n"
                f"stderr: {exc.stderr}"
            )

    if last_error is None:
        raise RuntimeError("failed to run ImageMagick convert command")
    raise last_error


def fetch_and_prepare_oboyone_image(url: str) -> Image.Image:
    image_bytes = fetch_image_bytes(url)
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        input_path = temp_path / "source.png"
        output_path = temp_path / "converted.bmp"
        input_path.write_bytes(image_bytes)

        run_imagemagick_convert(input_path=input_path, output_path=output_path)
        converted = Image.open(output_path)
        return converted.copy()


def main() -> int:
    printer = detect_usb_printer()
    if printer is None:
        print("no printer")
        return 0

    try:
        image = fetch_and_prepare_oboyone_image(DEFAULT_URL)
        printer.text("ImageMagick: resize 384x, gray, monochrome\n\n")
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
