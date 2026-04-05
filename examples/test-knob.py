from gpiozero import RotaryEncoder, Button
from signal import pause

# Pure gpiozero — no conflicts
encoder = RotaryEncoder(17, 23, bounce_time=0.01)   # GPIO17 = pin 11, GPIO23 = pin 16
button  = Button(4, pull_up=True)                    # GPIO4 = pin 7

encoder.when_rotated_clockwise = lambda: print("▶ Clockwise")
encoder.when_rotated_counter_clockwise = lambda: print("◀ Counter-clockwise")
button.when_pressed = lambda: print("Button pressed!")

pause()