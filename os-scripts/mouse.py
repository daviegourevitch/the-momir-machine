# Waveshare 1.3" LCD HAT — GPIO mouse with Momir-aware standby.
#
# Behavior:
# - Start this script at login/boot and leave it running.
# - While Momir is running, this script enters standby and releases GPIO/uinput.
# - When Momir exits, this script resumes desktop pointer control.

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import RPi.GPIO as GPIO
from pymouse import PyMouse

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime_coordination import is_momir_running

try:
    from evdev import UInput, ecodes as e

    HAVE_EVDEV = True
    EVDEV_IMPORT_ERR: Optional[Exception] = None
except Exception as ex:
    HAVE_EVDEV = False
    EVDEV_IMPORT_ERR = ex
    UInput = None  # type: ignore[assignment]
    e = None  # type: ignore[assignment]


JOY_UP = 6
JOY_DOWN = 19
JOY_LEFT = 5
JOY_RIGHT = 26
JOY_PRESS = 13
BTN_KEY1 = 21
BTN_KEY2 = 20
BTN_KEY3 = 16

STEP = 8
POLL_INTERVAL_S = 0.05
STANDBY_POLL_INTERVAL_S = 0.2
ACTIVATE_DEBOUNCE_S = 0.2

SCROLL_WHEEL_DELTA = 1

_RUNNING = True


@dataclass
class ActiveResources:
    m: PyMouse
    ui: Optional[UInput]

    @property
    def have_uinput(self) -> bool:
        return self.ui is not None


@dataclass
class InputState:
    key1_down: bool = False
    key2_held: bool = False
    key3_down: bool = False
    joy_left_held: bool = False
    prev_joy_dirs: tuple[bool, bool, bool, bool] = (False, False, False, False)


def _request_shutdown(_signum, _frame) -> None:
    global _RUNNING
    _RUNNING = False


def _create_uinput() -> Optional[UInput]:
    if not HAVE_EVDEV:
        return None
    try:
        return UInput(
            {
                e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE],
                e.EV_REL: [e.REL_X, e.REL_Y, e.REL_WHEEL],
            },
            name="waveshare-hat-joy",
            vendor=0xF00F,
            product=0x0001,
            version=1,
        )
    except Exception as ex:
        print(f"[mouse.py] uinput unavailable, falling back to X11 mouse paths: {ex}")
        return None


def _move_rel(ui: Optional[UInput], dx: int, dy: int) -> None:
    if ui is None:
        return
    if dx:
        ui.write(e.EV_REL, e.REL_X, dx)
    if dy:
        ui.write(e.EV_REL, e.REL_Y, dy)
    ui.syn()


def _set_left_evdev(ui: Optional[UInput], pressed: bool) -> None:
    if ui is None:
        return
    ui.write(e.EV_KEY, e.BTN_LEFT, 1 if pressed else 0)
    ui.syn()


def _set_right_evdev(ui: Optional[UInput], pressed: bool) -> None:
    if ui is None:
        return
    ui.write(e.EV_KEY, e.BTN_RIGHT, 1 if pressed else 0)
    ui.syn()


def _scroll_wheel_evdev(ui: Optional[UInput], delta: int) -> None:
    if ui is None or delta == 0:
        return
    ui.write(e.EV_REL, e.REL_WHEEL, delta)
    ui.syn()


def scroll_x11(button: str) -> None:
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
    if pressed:
        if hasattr(m, "press"):
            m.press(x, y, button)
        else:
            m.click(x, y, button)
    elif hasattr(m, "release"):
        m.release(x, y, button)


def _setup_gpio() -> None:
    GPIO.setmode(GPIO.BCM)
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


def _activate() -> ActiveResources:
    _setup_gpio()
    return ActiveResources(m=PyMouse(), ui=_create_uinput())


def _release_all_buttons(resources: ActiveResources, state: InputState) -> None:
    try:
        x, y = resources.m.position()
    except Exception:
        x, y = 0, 0
    if state.joy_left_held:
        _set_left_evdev(resources.ui, False)
        pymouse_set_button(resources.m, x, y, 1, False)
        state.joy_left_held = False
    if state.key2_held:
        _set_right_evdev(resources.ui, False)
        pymouse_set_button(resources.m, x, y, 3, False)
        state.key2_held = False


def _deactivate(resources: ActiveResources, state: InputState) -> None:
    try:
        _release_all_buttons(resources, state)
    except Exception:
        pass
    if resources.ui is not None:
        try:
            resources.ui.close()
        except Exception:
            pass
    try:
        GPIO.cleanup()
    except Exception:
        pass


def _poll_once(resources: ActiveResources, state: InputState, debug: bool) -> None:
    x, y = resources.m.position()

    if not GPIO.input(BTN_KEY1):
        if not state.key1_down:
            print("KEY1 (scroll up)")
        state.key1_down = True
        if resources.have_uinput:
            _scroll_wheel_evdev(resources.ui, SCROLL_WHEEL_DELTA)
        else:
            scroll_x11("up")
    else:
        state.key1_down = False

    key2_pressed = not GPIO.input(BTN_KEY2)
    if key2_pressed:
        if not state.key2_held:
            state.key2_held = True
            print("KEY2 (right button down)")
            if resources.have_uinput:
                _set_right_evdev(resources.ui, True)
            else:
                pymouse_set_button(resources.m, x, y, 3, True)
    else:
        if state.key2_held:
            state.key2_held = False
            print("KEY2 (right button up)")
            if resources.have_uinput:
                _set_right_evdev(resources.ui, False)
            else:
                pymouse_set_button(resources.m, x, y, 3, False)

    if not GPIO.input(BTN_KEY3):
        if not state.key3_down:
            print("KEY3 (scroll down)")
        state.key3_down = True
        if resources.have_uinput:
            _scroll_wheel_evdev(resources.ui, -SCROLL_WHEEL_DELTA)
        else:
            scroll_x11("down")
    else:
        state.key3_down = False

    joy_press_pressed = not GPIO.input(JOY_PRESS)
    if joy_press_pressed:
        if not state.joy_left_held:
            state.joy_left_held = True
            print("JOY_PRESS (left button down)")
            if resources.have_uinput:
                _set_left_evdev(resources.ui, True)
            else:
                pymouse_set_button(resources.m, x, y, 1, True)
    else:
        if state.joy_left_held:
            state.joy_left_held = False
            print("JOY_PRESS (left button up)")
            if resources.have_uinput:
                _set_left_evdev(resources.ui, False)
            else:
                pymouse_set_button(resources.m, x, y, 1, False)

    du = not GPIO.input(JOY_UP)
    dd = not GPIO.input(JOY_DOWN)
    dl = not GPIO.input(JOY_LEFT)
    dr = not GPIO.input(JOY_RIGHT)
    joy_dirs = (du, dd, dl, dr)

    if debug and joy_dirs != state.prev_joy_dirs:
        print(f"JOY up={du} down={dd} left={dl} right={dr}")
    state.prev_joy_dirs = joy_dirs

    if resources.have_uinput:
        if du:
            _move_rel(resources.ui, 0, -STEP)
        if dd:
            _move_rel(resources.ui, 0, STEP)
        if dl:
            _move_rel(resources.ui, -STEP, 0)
        if dr:
            _move_rel(resources.ui, STEP, 0)
    else:
        if du:
            resources.m.move(x, y - STEP)
        if dd:
            resources.m.move(x, y + STEP)
        if dl:
            resources.m.move(x - STEP, y)
        if dr:
            resources.m.move(x + STEP, y)


def main() -> None:
    if not HAVE_EVDEV:
        print(
            "[mouse.py] evdev/uinput unavailable:",
            EVDEV_IMPORT_ERR,
            "\n  pip install evdev && sudo usermod -aG input $USER  (log out/in)",
        )

    debug = os.environ.get("JOY_DEBUG", "").strip() == "1"
    resources: Optional[ActiveResources] = None
    state = InputState()
    activated_at = 0.0

    while _RUNNING:
        if is_momir_running():
            if resources is not None:
                print("[mouse.py] Momir lock detected; entering standby.")
                _deactivate(resources, state)
                resources = None
                state = InputState()
            time.sleep(STANDBY_POLL_INTERVAL_S)
            continue

        if resources is None:
            try:
                resources = _activate()
                state = InputState()
                activated_at = time.monotonic()
                print("[mouse.py] Momir not running; mouse control active.")
            except Exception as ex:
                print(f"[mouse.py] Failed to activate GPIO/input: {ex}")
                resources = None
                time.sleep(STANDBY_POLL_INTERVAL_S)
            continue

        if (time.monotonic() - activated_at) < ACTIVATE_DEBOUNCE_S:
            time.sleep(POLL_INTERVAL_S)
            continue

        try:
            _poll_once(resources, state, debug=debug)
        except Exception as ex:
            print(f"[mouse.py] Input loop error; resetting to standby: {ex}")
            _deactivate(resources, state)
            resources = None
            state = InputState()
            time.sleep(STANDBY_POLL_INTERVAL_S)
            continue

        time.sleep(POLL_INTERVAL_S)

    if resources is not None:
        _deactivate(resources, state)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _request_shutdown)
    signal.signal(signal.SIGTERM, _request_shutdown)
    main()
