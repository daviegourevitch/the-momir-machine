# The Momir Machine — notes for Claude

## Deploying to the Raspberry Pi

- SSH: `ssh momir` (alias in `~/.ssh/config` → `the-momir-machine.local`, user `david`). Passwordless `sudo` works.
- Checkout on the Pi: `~/Code/the-momir-machine`. App venv: `~/momir-venv` (Python 3.13, `--system-site-packages`).
- **The Pi has no GitHub SSH key**, so `git fetch origin` fails (origin is `git@github.com:...`). Update over HTTPS without changing the remote:
  ```bash
  cd ~/Code/the-momir-machine
  git fetch https://github.com/daviegourevitch/the-momir-machine main
  git merge --ff-only FETCH_HEAD
  git update-ref refs/remotes/origin/main FETCH_HEAD   # keeps `git status` tidy
  ```
  Push changes to GitHub from the Mac first; the Pi only pulls.
- **Never reset/clean the Pi checkout.** It intentionally has an uncommitted `config/settings.json` (the user's live game settings) and an untracked `data/scryfall/cards.db` (~160 MB card DB). Back up `config/settings.json` before risky git operations.
- Check deps without changing anything: `~/momir-venv/bin/pip install --dry-run -r requirements.txt`.
- Run tests on the Pi without installing into the app venv:
  ```bash
  ~/momir-venv/bin/pip install -q --target /tmp/momir-pytest pytest
  PYTHONPATH=/tmp/momir-pytest SDL_VIDEODRIVER=dummy ~/momir-venv/bin/python -m pytest -q -p no:cacheprovider
  rm -rf /tmp/momir-pytest
  ```
- Start the app on the LCD from an SSH session (runs as root via the launcher's `sudo`):
  ```bash
  cd ~/Code/the-momir-machine && DISPLAY=:0 XAUTHORITY=/home/david/.Xauthority \
    WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 \
    setsid nohup bash scripts/run-momir.sh > ~/momir-run.log 2>&1 < /dev/null &
  ```
  Check with `ps aux | grep app.py`. The HAT mouse helper (`os-scripts/mouse.py`, venv `~/waveshare-mouse-venv`) autostarts from `~/.config/autostart/waveshare-mouse.desktop` and should be left running.
- Thermal printer shows in `lsusb` as `28e9:0289 GDMicroelectronics micro-printer`.
- The user can watch the LCD and confirm things visually; ask them when a check needs eyes on the screen.

## Scryfall

- Scryfall rejects requests that lack a descriptive `User-Agent` and an `Accept` header — **including image downloads from `cards.scryfall.io`** (returns HTTP 400 without them). Shared headers live in `constants.py` (`SCRYFALL_USER_AGENT`, `SCRYFALL_IMAGE_HEADERS`); `fetch-db.py` sets its own.
- Network/image failures must never crash the app: `printer_service` raises `CardImageError`, which `app.py` catches; `_drain_actions` also has a catch-all so one bad action can't kill the main loop.

## Local development

- There's no global `pytest` on the Mac; create a venv (e.g. in a scratch dir) and `pip install -r requirements-dev.txt`, then `python -m pytest -q`.
