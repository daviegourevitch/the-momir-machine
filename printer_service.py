from __future__ import annotations

from io import BytesIO
from typing import Optional

import numpy as np
import requests
import usb.core
import usb.util
from escpos.exceptions import Error as EscposError
from escpos.printer import Usb
from PIL import Image, ImageEnhance, ImageFilter

from constants import PRINT_SETTINGS_PATH
from print_settings_store import PrintSettings, load_print_settings

PRINTER_WIDTH_PX = 384


def flatten_alpha_to_white(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    background.paste(rgba, mask=rgba.split()[3])
    return background.convert("RGB")


def apply_gamma(image: Image.Image, gamma: float) -> Image.Image:
    arr = np.array(image, dtype=np.float32) / 255.0
    arr = np.power(arr, 1.0 / max(gamma, 0.01))
    return Image.fromarray((arr * 255).astype(np.uint8), mode="L")


def threshold_image(image: Image.Image, threshold: int) -> Image.Image:
    bounded = max(0, min(255, threshold))
    return image.point(lambda pixel: 255 if pixel > bounded else 0, mode="1")


def apply_preprocess_pipeline(
    image: Image.Image, print_settings: PrintSettings
) -> Image.Image:
    # Option 2 baseline: alpha flatten, grayscale, gamma, contrast, unsharp.
    image = flatten_alpha_to_white(image).convert("L")
    image = apply_gamma(image, float(print_settings["gamma"]))
    image = ImageEnhance.Contrast(image).enhance(float(print_settings["contrast"]))
    image = image.filter(
        ImageFilter.UnsharpMask(
            radius=float(print_settings["unsharp_radius"]),
            percent=int(print_settings["unsharp_percent"]),
            threshold=int(print_settings["unsharp_threshold"]),
        )
    )
    return image


def fetch_and_prepare_image(
    url: str,
    target_width: int = PRINTER_WIDTH_PX,
    print_settings: Optional[PrintSettings] = None,
) -> Image.Image:
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    image = Image.open(BytesIO(response.content))
    settings = (
        print_settings if print_settings is not None else load_print_settings(PRINT_SETTINGS_PATH)
    )
    image = apply_preprocess_pipeline(image, settings)

    if image.width != target_width:
        ratio = target_width / float(image.width)
        target_height = max(1, int(image.height * ratio))
        image = image.resize((target_width, target_height), Image.Resampling.BICUBIC)

    if bool(settings["dither_enabled"]):
        # Floyd-Steinberg dithering in PIL default conversion to 1-bit.
        return image.convert("1")

    return threshold_image(image, int(settings["threshold"]))


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


def is_printer_connected() -> bool:
    printer = detect_usb_printer()
    if printer is None:
        return False
    try:
        return True
    finally:
        try:
            printer.close()
        except Exception:
            pass


def print_card_image(url: str) -> bool:
    printer = detect_usb_printer()
    if printer is None:
        return False

    try:
        image = fetch_and_prepare_image(url)
        printer.image(image)
        try:
            printer.cut()
        except EscposError:
            # Not all thermal printers support cut.
            pass
        return True
    finally:
        try:
            printer.close()
        except Exception:
            pass
