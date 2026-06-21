# Session: orientation display for the Waveshare ESP32-S3-Touch-LCD-2

Continuation of the project in [interactions.md](interactions.md). That session
left the board flashed with MicroPython and running `clock_s3.py` +
`st7789.py`. This session adds a new program that reads the board's onboard
IMU and shows live tilt/orientation info on the LCD.

## 1. Identifying the sensor and its pins

The board (Waveshare ESP32-S3-Touch-LCD-2) has an onboard QMI8658C 6-axis
IMU (accelerometer + gyroscope), per the schematic table already recorded in
`interactions.md`:

| Signal     | GPIO | Notes |
|------------|------|-------|
| IMU_INT1   | 3    | interrupt pin, unused — this program polls instead |
| TP_SCL / IMU_SCL | 47 | I2C clock, shared with the touch controller |
| TP_SDA / IMU_SDA | 48 | I2C data, shared with the touch controller |

## 2. Finding the QMI8658C register map

The official QST datasheet PDFs (qstcorp.com, files.waveshare.com) didn't
extract cleanly through `WebFetch` (binary/encoded PDF stream, no readable
text layer came through). Found an actual register map by fetching the raw
source of a published CircuitPython driver instead:

`https://raw.githubusercontent.com/ROSMicroPy/QMI8658/main/qmi8658c.py`
(jins-tkomoda/CircuitPython_QMI8658C)

Key facts pulled from it:

- WHO_AM_I (`0x00`) must read `0x05` to confirm the chip.
- CTRL2 (`0x03`): accel range in bits 6:4, accel ODR in bits 3:0.
- CTRL3 (`0x04`): gyro range in bits 6:4, gyro ODR in bits 3:0.
- CTRL7 (`0x08`): bit0 = accel enable, bit1 = gyro enable.
- Accel data at `0x35`, gyro data at `0x3B`, each 6 bytes / 3×int16 little-endian.
- Default I2C address `0x6B` (SA0 pin low); `0x6A` if SA0 is pulled high.
- Scale factors: ±8g range → 4096 LSB/g; ±512dps range → 64 LSB/dps.

Confirmed the address on the real board with an I2C scan before writing
the driver:

```
mpremote connect /dev/ttyACM0 exec "
from machine import I2C, Pin
i2c = I2C(0, scl=Pin(47), sda=Pin(48), freq=400000)
print('scan:', [hex(a) for a in i2c.scan()])
"
# scan: ['0x15', '0x6b']
```

`0x6b` is the IMU; `0x15` is the touch controller sharing the same bus.

## 3. Writing the driver and program

- **`qmi8658c.py`** — new minimal MicroPython driver (`machine.I2C`-based,
  not the `busio`/CircuitPython style of the reference). Probes for the
  device at `0x6B` then `0x6A`, checks `WHO_AM_I`, configures ±8g/125Hz
  accel and ±512dps/125Hz gyro, enables both sensors, and exposes
  `read_accel_g()` / `read_gyro_dps()` returning physical units.
- **`orientation.py`** — new program. Sets up the ST7789 display (same
  pins/pattern as `clock_s3.py`) and the IMU, then loops ~6.7Hz:
  - reads accel (g) and gyro (dps)
  - computes pitch/roll in degrees via `atan2` on the accel vector
  - picks a face label (`Face Up`/`Face Down`/`Left Up`/`Right Up`/
    `Top Up`/`Bottom Up`) from whichever axis has the largest gravity
    component
  - redraws only the changed text rows (`fill_rect` + `text` per line,
    not a full-screen clear) to avoid flicker

Verified raw sensor output before wiring up the display, to separate IMU
bugs from display bugs:

```
mpremote connect /dev/ttyACM0 exec "<read 5 samples in a loop>"
(0.0220, -0.2117, 0.9380) (1.75, -2.14, -0.25)
(0.0271, -0.2183, 0.9451) (0.34, -0.67, -0.69)
...
```

`az ≈ 0.94g`, `ax`/`ay` near zero — consistent with the board lying flat,
screen up. Confirms the driver and scale factors are correct.

## 4. Bug: garbled "snow" text on long orientation labels

First on-device check: numbers displayed but didn't change when the user
tilted the board. Root cause turned out to be a **test artifact, not a
bug** — the first run had been started under `timeout 12 mpremote run
orientation.py` and got killed by the timeout, leaving a frozen frame on
screen. Re-ran it as a genuine long-lived background process
(`run_in_background`) and the user confirmed it then updated live.

Second issue, real this time: **garbled/corrupted characters on the longer
orientation labels** ("Right Side Up", "Bottom Side Up") specifically,
while short labels and the numeric rows were fine.

This is the *same bug class* already hit and fixed once before in this
project's history, on the older ILI9341 board:

```
git log --oneline -- chuck.py
279ab56 attempt to fix the fuzzing of long lines.
e17d532 long lines turn to snow.
```

`git show 279ab56` shows the original fix: text whose pixel width exceeds
the display's width overruns the controller's addressed column window, and
the panel wraps/garbles instead of drawing correctly — fixed there by
clamping `max_chars` to `(display.width - 2*MARGIN) // (8*scale)` before
wrapping/drawing.

Same arithmetic applied here: `orientation_label()` drew at `x=10` with
`scale=3` (24px/char), leaving `320 - 10 = 310px` of room → max 12 chars.
"Right Side Up" (13 chars) and "Bottom Side Up" (14 chars) both overflowed
the addressable window. Fixed by shortening the labels to
`Right Up`/`Left Up`/`Top Up`/`Bottom Up` (all ≤9 chars), comfortably under
the 12-char budget, instead of changing the driver itself — consistent with
how the equivalent bug was fixed previously at the call site rather than in
the framebuffer driver.

Confirmed fixed by the user after redeploying and tilting the board through
multiple orientations — all labels render cleanly now.

## 5. Saved cross-session memory

Recorded two persistent memory entries (outside this repo, in Claude's
memory store) so future sessions on this board don't have to re-derive
them:

- **`feedback_spi_text_overflow.md`** — the SPI-display "snow" bug class
  (Section 4 above) is now hit twice in this project (ILI9341 *and*
  ST7789); future sessions should clamp text width to the display bounds
  at the call site before adding any variable-length string to a screen.
- **`project_cyd_waveshare_s3.md`** — hardware facts for this specific
  board: pin assignments, the QMI8658C's I2C address/bus, the MADCTL
  rotation quirk, and the fact that the repo's real git root is the parent
  directory (`/home/mpayne/cyd17June2026`), not `26dollars/`.

## Outcome

New files `qmi8658c.py` (QMI8658C IMU driver) and `orientation.py` (live
orientation display: face label + pitch/roll + raw accel/gyro) added to
the Waveshare ESP32-S3-Touch-LCD-2 project, deployed via `mpremote fs cp`,
and confirmed working live on hardware — including tilt-responsiveness and
clean (non-garbled) text across all six orientation labels. Not yet
installed as `main.py`, so — like `clock_s3.py` — it currently must be
started manually via `mpremote run orientation.py`.
