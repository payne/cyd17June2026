# ILI9341 Display Driver Notes (ESP32-2432S028R / CYD)

## File
`ili9341.py` — minimal driver, no external dependencies beyond MicroPython builtins.

## Hardware pins (ESP32-2432S028R)

| Signal   | GPIO |
|----------|------|
| TFT_MOSI | 13   |
| TFT_SCLK | 14   |
| TFT_CS   | 15   |
| TFT_DC   | 2    |
| TFT_RST  | –1 (tied to EN) |
| TFT_BL   | 21 (active high) |

## Setup

```python
from machine import Pin, SPI
from ili9341 import ILI9341

spi = SPI(1, baudrate=40_000_000, polarity=0, phase=0, sck=Pin(14), mosi=Pin(13))
display = ILI9341(spi, cs=Pin(15), dc=Pin(2), rst=None, bl=Pin(21), rotation=1)
```

`rotation=1` → landscape, 320 × 240 px (width × height).

## Key API

| Method | Description |
|--------|-------------|
| `fill(color)` | Fill entire screen |
| `fill_rect(x, y, w, h, color)` | Filled rectangle |
| `pixel(x, y, color)` | Single pixel |
| `text(s, x, y, color, scale=1, bg=None)` | Draw string using 8×8 font |
| `blit_buffer(fbuf, x, y, w, h)` | Blit raw RGB565 framebuffer |
| `rotation(r)` | Change rotation 0–3; updates `width`/`height` |

## Color format
RGB565 (16-bit): `RRRRR GGGGGG BBBBB`

Common values:
- `0x0000` black, `0xFFFF` white
- `0xFFE0` yellow, `0x07FF` cyan, `0xF800` red, `0x07E0` green
- `0x3186` dark gray (buttons), `0x0842` dimmed gray

## `text()` internals
- Renders into an offscreen `framebuf.RGB565` buffer at 8×8 per character
- `scale > 1` triggers manual nearest-neighbor upscale (slow for large strings)
- With `bg=None` the background defaults to black (0x0000)

## Text width limit (important)
Each character is `8 * scale` px wide.  
Max characters that fit: `(display.width - 2*MARGIN) // (8 * scale)`  
**Always clamp to this value before drawing** — overflow writes past the right edge and wraps into the next row, producing visual garbage / snow.  See `wrap_text()` in `chuck.py` for the reference implementation.

## Rotation MADCTL values
| rotation | MADCTL | width × height |
|----------|--------|----------------|
| 0 | 0x48 | 240 × 320 |
| 1 | 0x28 | 320 × 240 |
| 2 | 0x88 | 240 × 320 |
| 3 | 0xE8 | 320 × 240 |

## XPT2046 touch (separate SPI bus)

The CYD has a resistive touchscreen driven by XPT2046 on **SPI(2)**:

| Signal | GPIO |
|--------|------|
| T_CLK  | 25   |
| T_DIN  | 32 (MOSI) |
| T_OUT  | 39 (MISO, input-only) |
| T_CS   | 33   |
| T_IRQ  | 36 (input-only, active-low) |

```python
spi2 = SPI(2, baudrate=1_000_000, polarity=0, phase=0,
           sck=Pin(25), mosi=Pin(32), miso=Pin(39))
```

ADC commands: `0xD0` = X channel, `0x90` = Y channel (12-bit differential).  
In **landscape rotation=1**, raw Y → screen X and raw X → screen Y.  
Calibration constants (may need per-unit tuning): X_MIN/MAX ≈ 300/3800, Y_MIN/MAX ≈ 300/3800.
