"""Rotary encoder + push-button test (BCM GPIO) for the Waveshare HAT wiring.

Try this minimal setup first: ``bounce_time=None`` avoids gpiozero ignoring the
second edge of a detent; swapped pins ``23, 17`` fix inverted rotation vs the
old ``17, 23`` order.

If you still get exactly one event every *two* detents, the encoder’s detents
may not match gpiozero’s step model — then use a full quadrature table or
another decoder (see project history / discussion).

Run on a Raspberry Pi with gpiozero (prefer ``python3-lgpio`` / ``rpi-lgpio``
on Pi 5). Other platforms will fail at runtime; that is expected.
"""

import os
from signal import pause

# Prefer lgpio before gpiozero is imported (Pi 5 / edge detection).
if not os.environ.get("GPIOZERO_PIN_FACTORY", "").strip():
    try:
        import lgpio  # noqa: F401

        os.environ["GPIOZERO_PIN_FACTORY"] = "lgpio"
    except ImportError:
        pass

from gpiozero import Button, RotaryEncoder

# Phase A = GPIO23, phase B = GPIO17 (swap vs 17,23 if direction is wrong).
encoder = RotaryEncoder(23, 17, bounce_time=None)
button = Button(4, pull_up=True, bounce_time=0.05)

encoder.when_rotated_clockwise = lambda: print("▶ Clockwise")
encoder.when_rotated_counter_clockwise = lambda: print("◀ Counter-clockwise")
button.when_pressed = lambda: print("Button pressed!")

pause()
