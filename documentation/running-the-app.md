# Running the Momir app

This project targets a **Raspberry Pi** with the Waveshare 1.3" LCD HAT (see [set-up-hat.md](set-up-hat.md) for display firmware). The app expects **GPIO** for the rotary knob and HAT buttons; without it, it falls back to **keyboard** controls for testing.

Python dependencies are listed in the repo root [`requirements.txt`](../requirements.txt) (`pygame-ce`, `gpiozero`, `cairosvg`, etc.).

On recent Debian / Raspberry Pi OS, the system Python is **externally managed** (PEP 668), so use a **virtual environment** for `pip` installs. To use **`lgpio` from apt** inside that venv, create the venv with **`--system-site-packages`** so `import lgpio` works without building from source.

## Virtual environment (lgpio + pip packages)

1. Install system GPIO bindings and venv support (once):

   ```bash
   sudo apt update && sudo apt install -y python3-lgpio python3-venv
   ```

2. Remove or ignore the old venv if you want a clean one (optional):

   ```bash
   rm -rf ~/momir-venv
   ```

3. Create a **new** venv **with system site-packages** (so `lgpio` from apt is visible):

   ```bash
   python3 -m venv --system-site-packages ~/momir-venv
   ```

4. Activate it:

   ```bash
   source ~/momir-venv/bin/activate
   ```

5. Upgrade pip (optional):

   ```bash
   pip install -U pip
   ```

6. Install project dependencies **inside** the venv (from the repository root):

   ```bash
   cd /path/to/The-Momir-Machine
   pip install -r requirements.txt
   ```

7. Confirm `lgpio` works **in this venv**:

   ```bash
   python -c "import lgpio; print('ok')"
   ```

8. Run the app with this venv’s Python:

   ```bash
   python app.py
   ```

## After setup

- **HAT mouse helper vs Momir:** If you use `mouse.py` for desktop pointer control, do not run it at the same time as Momir (same GPIO). Use [`scripts/run-momir.sh`](../scripts/run-momir.sh): it stops the mouse process, runs Momir with `~/momir-venv/bin/python`, then restarts the mouse when Momir exits (`chmod +x` once on the Pi).
- **Fullscreen / display:** Run from a graphical session on the Pi (or set `DISPLAY` appropriately) so pygame can open a fullscreen window on the LCD.
- **GPIO troubleshooting:** If you still see fallback from `lgpio` or edge-detection errors, see [set-up-hat.md](set-up-hat.md) § **Python GPIO (Momir app / gpiozero)**.
- **Keyboard fallback (dev / no hardware):** With the venv active, `python app.py` still accepts mapped keys when GPIO is unavailable; **Escape** quits.
- **Force GPIO on non-Linux (advanced):** Set `MOMIR_FORCE_GPIO=1` only if you know you need it; see `input_controller.py`.
