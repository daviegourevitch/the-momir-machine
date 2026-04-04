# Fix LCD rotation (`panel.bin` / MADCTL)

This file AI-generated based on the steps I took to fix my rotation problem.

Rotation for the Waveshare 1.3" HAT (DRM `mipi-dbi-spi`) is set in **`panel.bin`** with DCS register **`0x36`** (**MADCTL**). The **first** hex value after `command` must stay **`0x36`**; only the **second** value changes orientation.

**Common mistake:** `command 0x40 0xa0` is wrong — **`0x40`** is not the register. It must be **`command 0x36 0x??`**.

---

## Steps (each time you change rotation)

1. Edit your init text file (path depends on where you cloned the repo), e.g.:
   ```bash
   nano ~/Code/panel-mipi-dbi/waveshare-13-lcd-hat.txt
   ```

2. Set exactly one line (keep **`0x36`**):
   ```text
   command 0x36 0x??
   ```
   Replace **`0x??`** with a value from the table below.

3. Rebuild the firmware blob:
   ```bash
   cd ~/Code/panel-mipi-dbi
   python3 mipi-dbi-cmd /tmp/panel.bin ./waveshare-13-lcd-hat.txt -v
   ```

4. Install it:
   ```bash
   sudo cp /tmp/panel.bin /lib/firmware/panel.bin
   ```

5. Confirm MADCTL is present (should show **`command 0x36`**):
   ```bash
   python3 ~/Code/panel-mipi-dbi/mipi-dbi-cmd /lib/firmware/panel.bin
   ```

6. Reboot:
   ```bash
   sudo reboot
   ```

Upper/lower case in hex (`0xA0` vs `0xa0`) does not matter.

---

## Valid MADCTL values to try (`command 0x36 …`)

Try one value at a time until the picture matches how the HAT is mounted.

| Value   | Notes |
|--------|--------|
| `0x40` | Matches [`waveshare_fbcp` InitST7789](waveshare_fbcp/src/lcd_driver/st7789.cpp) for **`WAVESHARE_1INCH3_LCD_HAT`** (default orientation in that driver). |
| `0xA0` | Common 90° option on ST7789; often paired opposite to `0x60`. |
| `0x60` | Other 90° direction; if `0xA0` is wrong-way 90°, try this next. |
| `0x00` | Common base / 0°–style orientation on many panels. |
| `0xC0` | Common 180° / flipped option in many ST7789 init tables. |

There is no single “correct” value for all mountings—pick the one that looks right.

---

## If changing `0x36` fixes rotation but a band looks corrupt

MADCTL changes how the ST7789’s internal RAM maps to the 240×240 window. You may need to **adjust or remove** the scroll line:

```text
command 0x37 0x00 0x50
```

See [`st7789.cpp`](waveshare_fbcp/src/lcd_driver/st7789.cpp) (`0x37` / `VSCSAD` logic). You can also lower SPI **`speed`** in `config.txt` if you see noise.

---

## Optional: compositor rotation (Wayland)

If `panel.bin` changes don’t move the image, try **`wlr-randr`** on the SPI output name:

```bash
wlr-randr
wlr-randr --output NAME_OF_SPI --transform 90
```

Try **`270`**, **`180`**, or **`normal`** if needed.
