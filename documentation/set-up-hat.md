
# Setting up the Waveshare HAT

I set up my waveshare hat using these steps. Note that I am on the latest 64-bit raspberry pi os (Port of Trixie from December 2025)

## Display

### 1. Build and install `panel.bin`

**a.** Install tools and clone:

```bash
sudo apt update
sudo apt install -y python3 git
cd ~
git clone https://github.com/notro/panel-mipi-dbi.git
```

**b.** Create **`~/panel-mipi-dbi/waveshare-13-lcd-hat.txt`** with exactly this content:

```text
# Waveshare 1.3" LCD HAT ST7789VW - derived from waveshare_fbcp
command 0x11
delay 120

command 0x3A 0x05
delay 20

# This modifies the rotation of the display
command 0x36 0x60

command 0x21

command 0x13
delay 10

# Commented this out while trying to fix the black bar problem
# command 0x37 0x00 0x50

command 0x29
delay 100
```

**c.** Generate **`panel.bin`** and install it:

```bash
cd ~/panel-mipi-dbi
python3 mipi-dbi-cmd /tmp/panel.bin ./waveshare-13-lcd-hat.txt -v
sudo cp /tmp/panel.bin /lib/firmware/panel.bin
```


### 2. Edit `config.txt` (required lines only)

Edit as root, e.g. `sudo nano /boot/firmware/config.txt`.

**a.** Ensure SPI is on (it probably is):

```ini
dtparam=spi=on
```

**b.** Uncomment this line (or add it if it's absent)

```ini
dtoverlay=vc4-kms-v3d
```

**c.** Add these lines

```ini
dtoverlay=mipi-dbi-spi,spi0-0,speed=32000000,write-only
dtparam=width=240,height=240,width-mm=23,height-mm=23
dtparam=reset-gpio=27,dc-gpio=25,backlight-gpio=24
```

**d.** Save, then reboot:

```bash
sudo reboot
```

## Python GPIO (Momir app / gpiozero)

If you see `No module named 'lgpio'` or `Failed to add edge detection` when running the app, gpiozero is falling back from the preferred **lgpio** backend. Install Python bindings for **lgpio** (pick one):

```bash
sudo apt install python3-lgpio
```

Or, in your venv on the Pi:

```bash
pip install rpi-lgpio
```

The app sets `GPIOZERO_PIN_FACTORY=lgpio` when `import lgpio` succeeds so gpiozero does not rely on RPi.GPIO for edges.

## Mouse
