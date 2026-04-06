# Waveshare 1.3" LCD HAT — GPIO mouse
#
# Keys: KEY1 = scroll up (repeats while held), KEY2 = right button hold, KEY3 = scroll down (repeats).
# Clicks: PyMouse press/release (needs DISPLAY=:0 in a desktop terminal).
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
import subprocess

_ui = None
_HAVE_UINPUT = False
_UINPUT_ERR = None

try:
    from evdev import UInput, ecodes as e

    # libinput often ignores REL-only devices; advertise normal mouse buttons too.
    _ui = UInput(
        {
            e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE],
            e.EV_REL: [e.REL_X, e.REL_Y, e.REL_WHEEL],
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

    def set_left_evdev(pressed: bool) -> None:
        """Left button down/up on the uinput pointer (matches joystick REL moves on Wayland)."""
        if _ui is None:
            return
        _ui.write(e.EV_KEY, e.BTN_LEFT, 1 if pressed else 0)
        _ui.syn()

    def set_right_evdev(pressed: bool) -> None:
        """Right button down/up on the uinput pointer."""
        if _ui is None:
            return
        _ui.write(e.EV_KEY, e.BTN_RIGHT, 1 if pressed else 0)
        _ui.syn()

    def scroll_wheel_evdev(delta: int) -> None:
        """Vertical scroll on the uinput pointer (signs tuned so KEY1=up, KEY3=down)."""
        if _ui is None or delta == 0:
            return
        _ui.write(e.EV_REL, e.REL_WHEEL, delta)
        _ui.syn()

    _HAVE_UINPUT = True
except Exception as ex:
    _HAVE_UINPUT = False
    _UINPUT_ERR = ex

    def move_rel(dx: int, dy: int) -> None:
        pass

    def set_left_evdev(pressed: bool) -> None:
        pass

    def set_right_evdev(pressed: bool) -> None:
        pass

    def scroll_wheel_evdev(delta: int) -> None:
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

# Joystick speed: lower STEP = smaller nudge each tick; higher POLL_INTERVAL_S = fewer ticks per second.
STEP = 8
POLL_INTERVAL_S = 0.05

# Key1 = scroll up, Key3 = scroll down (uinput REL_WHEEL units per press).
SCROLL_WHEEL_DELTA = 1


def scroll_x11(button: str) -> None:
    """X11 scroll via xdotool. Mapping reversed vs common 4=up/5=down so it matches uinput."""
    if button not in ("up", "down"):
        return
    n = "5" if button == "up" else "4"
    try:
        subprocess.run(
            ["xdotool", "click", n],
            check=False,
            timeout=2,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass


def pymouse_set_button(m: PyMouse, x: int, y: int, button: int, pressed: bool) -> None:
    """X11 fallback: hold or release a button (same numbering as PyMouse.click)."""
    if pressed:
        if hasattr(m, "press"):
            m.press(x, y, button)
        else:
            m.click(x, y, button)
    elif hasattr(m, "release"):
        m.release(x, y, button)


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
    key2_held = False
    key3_down = False
    joy_left_held = False
    prev_joy_dirs = (False, False, False, False)

    while True:
        x, y = m.position()

        if not GPIO.input(BTN_KEY1):
            if not key1_down:
                print("KEY1 (scroll up)")
            key1_down = True
            if _HAVE_UINPUT:
                scroll_wheel_evdev(SCROLL_WHEEL_DELTA)
            else:
                scroll_x11("up")
        else:
            key1_down = False

        key2_pressed = not GPIO.input(BTN_KEY2)
        if key2_pressed:
            if not key2_held:
                key2_held = True
                print("KEY2 (right button down)")
                if _HAVE_UINPUT:
                    set_right_evdev(True)
                else:
                    pymouse_set_button(m, x, y, 3, True)
        else:
            if key2_held:
                key2_held = False
                print("KEY2 (right button up)")
                if _HAVE_UINPUT:
                    set_right_evdev(False)
                else:
                    pymouse_set_button(m, x, y, 3, False)

        if not GPIO.input(BTN_KEY3):
            if not key3_down:
                print("KEY3 (scroll down)")
            key3_down = True
            if _HAVE_UINPUT:
                scroll_wheel_evdev(-SCROLL_WHEEL_DELTA)
            else:
                scroll_x11("down")
        else:
            key3_down = False

        joy_press_pressed = not GPIO.input(JOY_PRESS)
        if joy_press_pressed:
            if not joy_left_held:
                joy_left_held = True
                print("JOY_PRESS (left button down)")
                if _HAVE_UINPUT:
                    set_left_evdev(True)
                else:
                    pymouse_set_button(m, x, y, 1, True)
        else:
            if joy_left_held:
                joy_left_held = False
                print("JOY_PRESS (left button up)")
                if _HAVE_UINPUT:
                    set_left_evdev(False)
                else:
                    pymouse_set_button(m, x, y, 1, False)

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

        time.sleep(POLL_INTERVAL_S)


if __name__ == "__main__":
    try:
        main()
    finally:
        if _HAVE_UINPUT:
            try:
                set_left_evdev(False)
                set_right_evdev(False)
            except Exception:
                pass
        if _ui is not None:
            try:
                _ui.close()
            except Exception:
                pass
        GPIO.cleanup()
