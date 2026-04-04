# Waveshare 1.3" LCD HAT — GPIO mouse
#
# Clicks: PyMouse (needs DISPLAY=:0 in a desktop terminal).
# Joystick moves: linux uinput (works when XWarpPointer is blocked on Wayland).
#
#   ~/waveshare-mouse-venv/bin/pip install pymouse evdev RPi.GPIO
#   sudo usermod -aG input $USER   # then log out and back in
#   DISPLAY=:0 ~/waveshare-mouse-venv/bin/python3 mouse.py
#
# JOY_DEBUG=1 logs direction changes only (not every 20 ms while held).

from pymouse import PyMouse
import time
import os
import RPi.GPIO as GPIO

_ui = None
_HAVE_UINPUT = False
_UINPUT_ERR = None

try:
    from evdev import UInput, ecodes as e

    # libinput often ignores REL-only devices; advertise normal mouse buttons too.
    _ui = UInput(
        {
            e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE],
            e.EV_REL: [e.REL_X, e.REL_Y],
        },
        name="waveshare-hat-joy",
        vendor=0xF00F,
        product=0x0001,
        version=1,
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
JOY_PRESS = 13
BTN_KEY1 = 21
BTN_KEY2 = 20
BTN_KEY3 = 16

STEP = 12

for pin in (
    JOY_UP,
    JOY_DOWN,
    JOY_LEFT,
    JOY_RIGHT,
    JOY_PRESS,
    BTN_KEY1,
    BTN_KEY2,
    BTN_KEY3,
):
    GPIO.setup(pin, GPIO.IN, GPIO.PUD_UP)


def main() -> None:
    if not _HAVE_UINPUT:
        print(
            "uinput unavailable:",
            _UINPUT_ERR,
            "\n  pip install evdev && sudo usermod -aG input $USER  (log out/in)",
        )

    DEBUG = os.environ.get("JOY_DEBUG", "") == "1"
    m = PyMouse()
    key1_down = False
    key2_down = False
    key3_down = False
    joy_press_down = False
    prev_joy_dirs = (False, False, False, False)

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

        if (not GPIO.input(BTN_KEY3)) and (not key3_down):
            key3_down = True
            print("KEY3")
            m.click(x, y, 3)
        if GPIO.input(BTN_KEY3):
            key3_down = False

        if (not GPIO.input(JOY_PRESS)) and (not joy_press_down):
            joy_press_down = True
            print("JOY_PRESS")
            m.click(x, y, 1)
        if GPIO.input(JOY_PRESS):
            joy_press_down = False

        du = not GPIO.input(JOY_UP)
        dd = not GPIO.input(JOY_DOWN)
        dl = not GPIO.input(JOY_LEFT)
        dr = not GPIO.input(JOY_RIGHT)
        joy_dirs = (du, dd, dl, dr)

        if DEBUG and joy_dirs != prev_joy_dirs:
            print(f"JOY up={du} down={dd} left={dl} right={dr}")
        prev_joy_dirs = joy_dirs

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
