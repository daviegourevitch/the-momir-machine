# `mouse.py` from scratch — build, run, autostart

Replace **`YOURUSER`** / paths if yours differ.

---

## 1. Virtualenv and Python packages

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip
python3 -m venv ~/waveshare-mouse-venv
~/waveshare-mouse-venv/bin/pip install evdev pymouse RPi.GPIO
```

Put **`mouse.py`** somewhere fixed, e.g. **`~/Code/waveshare-mouse/mouse.py`**.

---

## 2. `uinput` access (one reboot after groups)

```bash
sudo usermod -aG input YOURUSER
echo uinput | sudo tee /etc/modules-load.d/uinput.conf
echo 'SUBSYSTEM=="misc", KERNEL=="uinput", GROUP="input", MODE="0660"' | sudo tee /etc/udev/rules.d/99-uinput.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

**Log out and log in** (or reboot) so group **`input`** is active.

---

## 3. Test by hand

On the **desktop** (HDMI), open **Terminal**:

```bash
DISPLAY=:0 ~/waveshare-mouse-venv/bin/python3 ~/Code/waveshare-mouse/mouse.py
```

*(Adjust the path to `mouse.py`.)* Stop with **Ctrl+C**.

---

## 4. Autostart at login

```bash
mkdir -p ~/.config/autostart
nano ~/.config/autostart/waveshare-mouse.desktop
```

Paste **one line** for `Exec=` (no line break), with **your** username and paths:

```ini
[Desktop Entry]
Type=Application
Name=Waveshare HAT Mouse
Exec=env DISPLAY=:0 XAUTHORITY=/home/YOURUSER/.Xauthority /home/YOURUSER/waveshare-mouse-venv/bin/python3 /home/YOURUSER/Code/waveshare-mouse/mouse.py
```

Save, **log out**, log in — the script should start with the session.

---

## 5. If movement or stick-click fails

- Confirm **`groups`** includes **`input`** and **`ls -l /dev/uinput`** is **`root input`** and **`crw-rw----`**.
- Use a **desktop** terminal; **`DISPLAY=:0`** is required for **PyMouse** (KEY1/KEY2/KEY3).
- Do **not** run this script with **`sudo`** for normal use.

See also **`mouse.py`** header comments and **`HAT_MINIMAL_WIRING.md`** if you rewire the HAT.
