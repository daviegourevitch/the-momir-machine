# Waveshare 1.3" LCD HAT — GPIO mouse
#
# Clicks: PyMouse → X11/XWayland (needs DISPLAY=:0 in a desktop terminal).
# Joystick moves: linux uinput REL_X/REL_Y (works when XWarpPointer is blocked on Wayland).
#
# Setup:
#   ~/waveshare-mouse-venv/bin/pip install pymouse evdev RPi.GPIO
#   sudo usermod -aG input $USER   # then log out and back in (for /dev/uinput)
#   DISPLAY=:0 ~/waveshare-mouse-venv/bin/python3 mouse.py

from pymouse import PyMouse
import time
import os
import RPi.GPIO as GPIO

_ui = None
try:
    from evdev import UInput, ecodes as e

    _ui = UInput(
        {e.EV_REL: (e.REL_X, e.REL_Y)},
        name="waveshare-hat-joy",
        version=0x1,
    )

    def move_rel(dx: int, dy: int) -> None:
        if _ui is None:
            return
        if dx:
            _ui.write(e.EV_REL, e.REL_X, dx)
        if dy:
            _ui.write(e.EV_REL, e.REL_Y, dy)
        _ui.syn()

    _HAVE_UINPUT = True
    _UINPUT_ERR = None
except Exception as ex:
    _HAVE_UINPUT = False
    _UINPUT_ERR = ex

    def move_rel(dx: int, dy: int) -> None:
        pass


GPIO.setmode(GPIO.BCM)

JOY_UP = 6
JOY_DOWN = 19
JOY_LEFT = 5
JOY_RIGHT = 26
BTN_KEY1 = 21
BTN_KEY2 = 20

STEP = 12

for pin in (JOY_UP, JOY_DOWN, JOY_LEFT, JOY_RIGHT, BTN_KEY1, BTN_KEY2):
    GPIO.setup(pin, GPIO.IN, GPIO.PUD_UP)


def main() -> None:
    if not _HAVE_UINPUT:
        print(
            "uinput relative moves are unavailable:",
            _UINPUT_ERR,
            "\nFix: ~/waveshare-mouse-venv/bin/pip install evdev,"
            " sudo usermod -aG input $USER, then log out and back in.",
        )
        print("Joystick falls back to PyMouse.move (often broken on Wayland).")

    DEBUG = os.environ.get("JOY_DEBUG", "") == "1"
    m = PyMouse()
    key1_down = False
    key2_down = False

    while True:
        x, y = m.position()

        if (not GPIO.input(BTN_KEY1)) and (not key1_down):
            key1_down = True
            print("KEY1")
            m.click(x, y, 1)
        if GPIO.input(BTN_KEY1):
            key1_down = False

        if (not GPIO.input(BTN_KEY2)) and (not key2_down):
            key2_down = True
            print("KEY2")
            m.click(x, y, 2)
        if GPIO.input(BTN_KEY2):
            key2_down = False

        du = not GPIO.input(JOY_UP)
        dd = not GPIO.input(JOY_DOWN)
        dl = not GPIO.input(JOY_LEFT)
        dr = not GPIO.input(JOY_RIGHT)

        if DEBUG and (du or dd or dl or dr):
            print(f"JOY raw up={du} down={dd} left={dl} right={dr}")

        if _HAVE_UINPUT:
            if du:
                move_rel(0, -STEP)
            if dd:
                move_rel(0, STEP)
            if dl:
                move_rel(-STEP, 0)
            if dr:
                move_rel(STEP, 0)
        else:
            if du:
                m.move(x, y - STEP)
            if dd:
                m.move(x, y + STEP)
            if dl:
                m.move(x - STEP, y)
            if dr:
                m.move(x + STEP, y)

        time.sleep(0.02)


if __name__ == "__main__":
    try:
        main()
    finally:
        if _ui is not None:
            try:
                _ui.close()
            except Exception:
                pass
        GPIO.cleanup()
