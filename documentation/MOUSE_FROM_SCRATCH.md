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

Use the repo copy at **`/home/YOURUSER/Code/The-Momir-Machine/os-scripts/mouse.py`**.

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
DISPLAY=:0 ~/waveshare-mouse-venv/bin/python3 ~/Code/The-Momir-Machine/os-scripts/mouse.py
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
Exec=env DISPLAY=:0 XAUTHORITY=/home/YOURUSER/.Xauthority /home/YOURUSER/waveshare-mouse-venv/bin/python3 /home/YOURUSER/Code/The-Momir-Machine/os-scripts/mouse.py
```

Save, **log out**, log in — the script should start with the session.

---

## 5. Momir coexistence

- Keep `mouse.py` running at login; do not kill/restart it when launching Momir.
- `app.py` and `mouse.py` coordinate via a shared runtime lock (`MOMIR_RUNTIME_LOCK`, default `/tmp/momir-runtime.lock`).
- Launch Momir with `bash /home/YOURUSER/Code/The-Momir-Machine/scripts/run-momir.sh` (or `python app.py`) so Momir acquires the lock while running.
- While Momir holds the lock, `mouse.py` automatically enters standby and releases GPIO/uinput; it resumes when Momir exits.

---

## 6. If movement or stick-click fails

- Confirm **`groups`** includes **`input`** and **`ls -l /dev/uinput`** is **`root input`** and **`crw-rw----`**.
- Use a **desktop** terminal; **`DISPLAY=:0`** is required for **PyMouse** (KEY1/KEY2/KEY3).
- Do **not** run this script with **`sudo`** for normal use.
- Ensure both Momir and `mouse.py` use the same lock path if you set `MOMIR_RUNTIME_LOCK`.

See also **`mouse.py`** header comments and **`HAT_MINIMAL_WIRING.md`** if you rewire the HAT.
