"""Quadrature rotary encoder for the Waveshare HAT (BCM GPIO).

``gpiozero.RotaryEncoder`` often registers one step per full electrical cycle while
mechanical detents are twice as frequent. This module decodes every valid edge
(no software bounce on A/B) and groups raw steps so one detent ≈ one callback.

See ``examples/test-knob.py`` for a standalone test.
"""

from __future__ import annotations

from typing import Callable, Optional

from gpiozero import InputDevice

# HAT wiring: phase A on BCM23, phase B on BCM17 (swap vs 17,23 fixes direction).
KNOB_PIN_A_BCM = 23
KNOB_PIN_B_BCM = 17

# Raw +1/-1 table steps before firing one detent callback. Typical EC11 HAT: 2.
DETENT_ACCUM_STEPS = 2

# Pin state = (A << 1) | B. Clockwise Gray cycle: 0 -> 2 -> 3 -> 1 -> 0.
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
        n = DETENT_ACCUM_STEPS
        while self._accum >= n:
            self._accum -= n
            if self.when_rotated_clockwise:
                self.when_rotated_clockwise()
        while self._accum <= -n:
            self._accum += n
            if self.when_rotated_counter_clockwise:
                self.when_rotated_counter_clockwise()

    def close(self) -> None:
        self._a.close()
        self._b.close()
