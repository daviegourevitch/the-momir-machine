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


try:
    if not _gpio_enabled():
        raise ImportError("GPIO disabled on this platform (set MOMIR_FORCE_GPIO=1 to override).")
    from gpiozero import Button, RotaryEncoder

    HAVE_GPIOZERO = True
except Exception:
    HAVE_GPIOZERO = False
    Button = None  # type: ignore[assignment]
    RotaryEncoder = None  # type: ignore[assignment]


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
            self.encoder = RotaryEncoder(17, 23, bounce_time=0.01)
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
            self.close_gpio()

    def close_gpio(self) -> None:
        if self.encoder is not None:
            self.encoder.close()
        if self.knob_button is not None:
            self.knob_button.close()
        for btn in self.hat_buttons:
            btn.close()
