"""Rotary encoder + push-button test (BCM GPIO) for the Waveshare HAT wiring.

``gpiozero.RotaryEncoder`` tends to register one step per full internal cycle; on
many panel encoders that lines up with every *second* mechanical detent. This
script decodes each quadrature edge (no bounce on A/B) and collapses two
same-direction edges into one print so one detent ≈ one event.

Pins ``23, 17`` match the swapped order that fixes clockwise vs counter-clockwise
on this HAT. If rotation labels are wrong, swap only those two numbers.

If you get two prints per detent, try ``_DETENT_ACCUM_STEPS = 1``. If you still
skip detents, try ``4`` (see comment on the constant).

Run on a Raspberry Pi with gpiozero (prefer ``python3-lgpio`` / ``rpi-lgpio``
on Pi 5). Other platforms will fail at runtime; that is expected.
"""

from __future__ import annotations

import os
from signal import pause
from typing import Callable, Optional

# Prefer lgpio before gpiozero is imported (Pi 5 / edge detection).
if not os.environ.get("GPIOZERO_PIN_FACTORY", "").strip():
    try:
        import lgpio  # noqa: F401

        os.environ["GPIOZERO_PIN_FACTORY"] = "lgpio"
    except ImportError:
        pass

from gpiozero import Button, InputDevice

# How many raw +1 / -1 transitions from the table map to one detent click.
# 2 matches "gpiozero only saw every other detent" on typical 2-detents-per-cycle encoders.
_DETENT_ACCUM_STEPS = 2

# Pin state = (A << 1) | B. Clockwise Gray cycle: 0 -> 2 -> 3 -> 1 -> 0.
# Index (old_state << 2) | new_state -> signed step (-1, 0, +1).
_QUAD_DELTA: tuple[int, ...] = (
    0,
    -1,
    1,
    0,
    1,
    0,
    0,
    -1,
    -1,
    0,
    0,
    1,
    0,
    1,
    -1,
    0,
)


class QuadratureKnob:
    def __init__(self, pin_a: int, pin_b: int) -> None:
        self._a = InputDevice(pin_a, pull_up=True)
        self._b = InputDevice(pin_b, pull_up=True)
        for dev in (self._a, self._b):
            dev.pin.edges = "both"
            dev.pin.bounce_time = None
            dev.pin.when_changed = self._on_pin_changed

        a = int(self._a.value)
        b = int(self._b.value)
        self._state = (a << 1) | b
        self._accum = 0

        self.when_rotated_clockwise: Optional[Callable[[], None]] = None
        self.when_rotated_counter_clockwise: Optional[Callable[[], None]] = None

    def _on_pin_changed(self, _ticks: object, _state: object) -> None:
        a = int(self._a.value)
        b = int(self._b.value)
        new = (a << 1) | b
        idx = (self._state << 2) | new
        delta = _QUAD_DELTA[idx]
        self._state = new
        if delta == 0:
            return
        self._accum += delta
        while self._accum >= _DETENT_ACCUM_STEPS:
            self._accum -= _DETENT_ACCUM_STEPS
            if self.when_rotated_clockwise:
                self.when_rotated_clockwise()
        while self._accum <= -_DETENT_ACCUM_STEPS:
            self._accum += _DETENT_ACCUM_STEPS
            if self.when_rotated_counter_clockwise:
                self.when_rotated_counter_clockwise()

    def close(self) -> None:
        self._a.close()
        self._b.close()


encoder = QuadratureKnob(23, 17)
button = Button(4, pull_up=True, bounce_time=0.05)

encoder.when_rotated_clockwise = lambda: print("▶ Clockwise")
encoder.when_rotated_counter_clockwise = lambda: print("◀ Counter-clockwise")
button.when_pressed = lambda: print("Button pressed!")

pause()
