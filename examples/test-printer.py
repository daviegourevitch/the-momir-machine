#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the repository root is importable when running this script directly.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from printer_service import detect_usb_printer, fetch_and_prepare_image


DEFAULT_URL = (
    "https://cards.scryfall.io/png/front/b/9/b93c5869-7777-44bb-967a-e9439b25ced4.png?1559591655"
)


def main() -> int:
    printer = detect_usb_printer()
    if printer is None:
        print("no printer")
        return 0

    try:
        image = fetch_and_prepare_image(DEFAULT_URL)
        printer.image(image)
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
