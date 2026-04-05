import RPi.GPIO as GPIO          # already installed on your Pi — no pip needed
from gpiozero import RotaryEncoder, Button
from signal import pause

# === Enable internal pull-ups on the encoder pins (this fixes the "every other dent") ===
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)   # physical pin 11
GPIO.setup(23, GPIO.IN, pull_up_down=GPIO.PUD_UP)   # physical pin 16

# === Create the encoder (we'll fix direction next) ===
encoder = RotaryEncoder(17, 23, bounce_time=0.01)   # bounce_time cleans up mechanical noise
button  = Button(4, pull_up=True)                    # your existing button on pin 7 / GPIO 4

# === Callbacks ===
encoder.when_rotated_clockwise = lambda: print("▶ Clockwise")
encoder.when_rotated_counter_clockwise = lambda: print("◀ Counter-clockwise")
button.when_pressed = lambda: print("Button pressed!")

pause()