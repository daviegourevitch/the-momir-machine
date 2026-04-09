#!/usr/bin/env python3
from __future__ import annotations

from io import BytesIO
from typing import Optional

import requests
import usb.core
import usb.util
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
        devices = list(usb.core.find(find_all=True) or [])
    except Exception as exc:
        print(f"unable to enumerate USB devices: {exc}")
        return None

    if not devices:
        print("no USB devices found")
        return None

    errors: list[str] = []

    for device in devices:
        vendor_id = int(getattr(device, "idVendor", 0))
        product_id = int(getattr(device, "idProduct", 0))
        if vendor_id <= 0 or product_id <= 0:
            continue

        try:
            configuration = device.get_active_configuration()
        except Exception as exc:
            errors.append(
                f"{vendor_id:04x}:{product_id:04x} failed to read active configuration: {exc}"
            )
            continue

        interfaces = list(configuration)
        interfaces.sort(
            key=lambda interface: 0 if int(getattr(interface, "bInterfaceClass", 0)) == 7 else 1
        )

        for interface in interfaces:
            interface_number = int(getattr(interface, "bInterfaceNumber", 0))
            in_ep: Optional[int] = None
            out_ep: Optional[int] = None

            for endpoint in interface:
                endpoint_type = usb.util.endpoint_type(int(endpoint.bmAttributes))
                if endpoint_type != usb.util.ENDPOINT_TYPE_BULK:
                    continue

                address = int(endpoint.bEndpointAddress)
                direction = usb.util.endpoint_direction(address)
                if direction == usb.util.ENDPOINT_OUT and out_ep is None:
                    out_ep = address
                elif direction == usb.util.ENDPOINT_IN and in_ep is None:
                    in_ep = address

            if out_ep is None:
                continue

            kwargs = {
                "timeout": 0,
                "interface": interface_number,
                "out_ep": out_ep,
            }
            if in_ep is not None:
                kwargs["in_ep"] = in_ep

            endpoint_details = (
                f"in_ep=0x{in_ep:02x}" if in_ep is not None else "in_ep=(default)"
            )

            try:
                printer = Usb(vendor_id, product_id, **kwargs)
                printer.hw("INIT")
                print(
                    "using USB printer "
                    f"{vendor_id:04x}:{product_id:04x} interface={interface_number} "
                    f"out_ep=0x{out_ep:02x} {endpoint_details}"
                )
                return printer
            except Exception as exc:
                errors.append(
                    f"{vendor_id:04x}:{product_id:04x} interface={interface_number} "
                    f"out_ep=0x{out_ep:02x} {endpoint_details}: {exc}"
                )

    if errors:
        print("unable to initialize USB printer; attempted configurations:")
        for message in errors:
            print(f" - {message}")

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
