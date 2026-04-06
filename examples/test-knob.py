"""Rotary encoder + push-button test (BCM GPIO) for the Waveshare HAT wiring.

Uses the same ``QuadratureKnob`` implementation as the Momir app
(``quadrature_knob``). Run from the repo root, e.g.:

    python3 examples/test-knob.py

If rotation is reversed, swap ``KNOB_PIN_A_BCM`` / ``KNOB_PIN_B_BCM`` in
``quadrature_knob.py``. If you get two events per detent (or still skip
detents), adjust ``DETENT_ACCUM_STEPS`` there.

On Pi 5, install ``python3-lgpio`` or ``rpi-lgpio`` so edge detection works.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from signal import pause

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

# Prefer lgpio before gpiozero is imported (Pi 5 / edge detection).
if not os.environ.get("GPIOZERO_PIN_FACTORY", "").strip():
    try:
        import lgpio  # noqa: F401

        os.environ["GPIOZERO_PIN_FACTORY"] = "lgpio"
    except ImportError:
        pass

from gpiozero import Button

from quadrature_knob import KNOB_PIN_A_BCM, KNOB_PIN_B_BCM, QuadratureKnob

encoder = QuadratureKnob(KNOB_PIN_A_BCM, KNOB_PIN_B_BCM)
button = Button(4, pull_up=True, bounce_time=0.05)

encoder.when_rotated_clockwise = lambda: print("▶ Clockwise")
encoder.when_rotated_counter_clockwise = lambda: print("◀ Counter-clockwise")
button.when_pressed = lambda: print("Button pressed!")

pause()
