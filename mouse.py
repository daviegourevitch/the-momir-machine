# Waveshare 1.3" LCD HAT — GPIO mouse (BCM numbers per Waveshare wiki)
# Run under XWayland with: DISPLAY=:0 ./your-venv/bin/python3 mouse.py
# If joystick "does nothing" but keys work: cursor may be moving on the *other*
# display (SPI vs HDMI). Try a larger STEP or look at both screens.

from pymouse import PyMouse
import time
import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)

# Joystick — wiki: Up=6, Down=19, Left=5, Right=26
JOY_UP = 6
JOY_DOWN = 19
JOY_LEFT = 5
JOY_RIGHT = 26

# Keys — wiki: KEY1=21, KEY2=20
BTN_KEY1 = 21
BTN_KEY2 = 20

STEP = 12  # pixels per tick (was 5; easier to see on dual-head setups)

for pin in (JOY_UP, JOY_DOWN, JOY_LEFT, JOY_RIGHT, BTN_KEY1, BTN_KEY2):
    GPIO.setup(pin, GPIO.IN, GPIO.PUD_UP)


def main():
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

        # Screen coords: +X right, +Y down
        if not GPIO.input(JOY_UP):
            m.move(x, y - STEP)
        if not GPIO.input(JOY_DOWN):
            m.move(x, y + STEP)
        if not GPIO.input(JOY_LEFT):
            m.move(x - STEP, y)
        if not GPIO.input(JOY_RIGHT):
            m.move(x + STEP, y)

        time.sleep(0.02)


if __name__ == "__main__":
    try:
        main()
    finally:
        GPIO.cleanup()
