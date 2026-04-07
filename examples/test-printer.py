#!/usr/bin/env python3
from __future__ import annotations

from io import BytesIO
from typing import Optional

import requests
import usb.core
from escpos.exceptions import Error as EscposError
from escpos.printer import Usb
from PIL import Image


DEFAULT_URL = (
    "https://cards.scryfall.io/png/front/b/0/"
    "b0faa7f2-b547-42c4-a810-839da50dadfe.png?1559591477"
)
PRINTER_WIDTH_PX = 384


def fetch_and_prepare_image(url: str, target_width: int = PRINTER_WIDTH_PX) -> Image.Image:
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    image = Image.open(BytesIO(response.content))
    image = image.convert("L")

    if image.width > target_width:
        ratio = target_width / float(image.width)
        target_height = max(1, int(image.height * ratio))
        image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)

    # Dither to 1-bit bitmap for thermal ESC/POS output.
    return image.convert("1")


def detect_usb_printer() -> Optional[Usb]:
    try:
        devices = usb.core.find(find_all=True)
    except Exception:
        return None

    if devices is None:
        return None

    for device in devices:
        vendor_id = int(getattr(device, "idVendor", 0))
        product_id = int(getattr(device, "idProduct", 0))
        if vendor_id <= 0 or product_id <= 0:
            continue

        try:
            printer = Usb(vendor_id, product_id, timeout=0, in_ep=0x82, out_ep=0x01)
            printer.hw("INIT")
            return printer
        except Exception:
            continue

    return None


def main() -> int:
    printer = detect_usb_printer()
    if printer is None:
        print("no printer")
        return 0

    try:
        image = fetch_and_prepare_image(DEFAULT_URL)
        printer.image(image)
        printer.text("\n\n")
        try:
            printer.cut()
        except EscposError:
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
