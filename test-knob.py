from gpiozero import RotaryEncoder, Button
from signal import pause

# Example assignment (change the numbers if you wired differently)
encoder = RotaryEncoder(17, 23)      # GPIO 17 = pin 11, GPIO 23 = pin 16
button  = Button(4, pull_up=True)    # GPIO 4 = pin 7, active LOW

encoder.when_rotated_clockwise = lambda: print("▶ Clockwise")
encoder.when_rotated_counter_clockwise = lambda: print("◀ Counter-clockwise")
button.when_pressed = lambda: print("Button pressed!")

pause()   # keeps the script running