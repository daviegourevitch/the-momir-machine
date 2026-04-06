from __future__ import annotations

import os
import queue
import sys
from typing import Any, Optional

from constants import (
    ACTION_DOWN,
    ACTION_JOY_PRESS,
    ACTION_KEY1,
    ACTION_KEY2,
    ACTION_KEY3,
    ACTION_KNOB_PRESS,
    ACTION_LEFT,
    ACTION_RIGHT,
    ACTION_ROTARY_CCW,
    ACTION_ROTARY_CW,
    ACTION_UP,
)

def _gpio_enabled() -> bool:
    if os.environ.get("MOMIR_FORCE_GPIO", "").strip().lower() in ("1", "true", "yes"):
        return True
    if sys.platform == "win32":
        return False
    return True


def _configure_gpiozero_pin_factory() -> None:
    """Prefer lgpio before gpiozero is imported.

    On recent Raspberry Pi OS, gpiozero tries ``lgpio`` first. If the Python
    module is missing, it falls back to RPi.GPIO, which often fails with
    "Failed to add edge detection" (especially on Pi 5). Installing
    ``python3-lgpio`` (apt) or ``rpi-lgpio`` (pip) and forcing this factory
    avoids that path.
    """
    if os.environ.get("GPIOZERO_PIN_FACTORY", "").strip():
        return
    try:
        import lgpio  # noqa: F401

        os.environ["GPIOZERO_PIN_FACTORY"] = "lgpio"
    except ImportError:
        pass


try:
    if not _gpio_enabled():
        raise ImportError("GPIO disabled on this platform (set MOMIR_FORCE_GPIO=1 to override).")
    _configure_gpiozero_pin_factory()
    from gpiozero import Button

    from quadrature_knob import KNOB_PIN_A_BCM, KNOB_PIN_B_BCM, QuadratureKnob

    HAVE_GPIOZERO = True
except Exception:
    HAVE_GPIOZERO = False
    Button = None  # type: ignore[assignment]
    QuadratureKnob = None  # type: ignore[assignment]


class InputController:
    def __init__(self, action_queue: "queue.SimpleQueue[str]") -> None:
        self.action_queue = action_queue
        self.encoder: Optional[Any] = None
        self.knob_button: Optional[Any] = None
        self.hat_buttons: list[Any] = []

    def setup_gpio(self) -> None:
        if not HAVE_GPIOZERO:
            print("gpiozero unavailable; running with keyboard controls only.")
            return

        try:
            self.encoder = QuadratureKnob(KNOB_PIN_A_BCM, KNOB_PIN_B_BCM)
            self.encoder.when_rotated_clockwise = lambda: self.action_queue.put(ACTION_ROTARY_CW)
            self.encoder.when_rotated_counter_clockwise = (
                lambda: self.action_queue.put(ACTION_ROTARY_CCW)
            )

            self.knob_button = Button(4, pull_up=True, bounce_time=0.05)
            self.knob_button.when_pressed = lambda: self.action_queue.put(ACTION_KNOB_PRESS)

            pin_map = [
                (6, ACTION_UP),
                (19, ACTION_DOWN),
                (5, ACTION_LEFT),
                (26, ACTION_RIGHT),
                (13, ACTION_JOY_PRESS),
                (21, ACTION_KEY1),
                (20, ACTION_KEY2),
                (16, ACTION_KEY3),
            ]
            for pin, action in pin_map:
                btn = Button(pin, pull_up=True, bounce_time=0.08)
                btn.when_pressed = lambda action_name=action: self.action_queue.put(action_name)
                self.hat_buttons.append(btn)
        except Exception as exc:
            print(f"GPIO unavailable ({exc}); running with keyboard controls only.")
            print(
                "Hint: on Raspberry Pi OS install lgpio for Python, e.g. "
                "`sudo apt install python3-lgpio` or `pip install rpi-lgpio`, "
                "then retry (see documentation/set-up-hat.md)."
            )
            self.close_gpio()

    def close_gpio(self) -> None:
        if self.encoder is not None:
            self.encoder.close()
        if self.knob_button is not None:
            self.knob_button.close()
        for btn in self.hat_buttons:
            btn.close()
