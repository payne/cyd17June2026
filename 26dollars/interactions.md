# Session: Flashing MicroPython to the connected CYD

## 1. Identify the board

From `2lsusb.txt`:
```
Bus 001 Device 002: ID 303a:1001 Espressif USB JTAG/serial debug unit
```

From `2chip_id.txt` (`esptool chip_id`):
```
Chip type:          ESP32-S3 (QFN56) (revision v0.2)
Features:           Wi-Fi, BT 5 (LE), Dual Core + LP Core, 240MHz, Embedded PSRAM 8MB (AP_3v3)
Crystal frequency:  40MHz
USB mode:           USB-Serial/JTAG
MAC:                44:1b:f6:85:e0:14
```

The "AP_3v3" embedded-PSRAM package designation indicates the ESP32-S3R8
variant (8MB Octal SPI PSRAM), which is what this CYD board uses.

## 2. Pick the firmware

Matching MicroPython build for an S3 + Octal PSRAM module is
`ESP32_GENERIC_S3-SPIRAM_OCT` (not the plain S3 or Quad-PSRAM build).

Checked https://micropython.org/download/ESP32_GENERIC_S3/ — latest stable
at the time was:

- **v1.28.0 (2026-04-06)** — `ESP32_GENERIC_S3-SPIRAM_OCT-20260406-v1.28.0.bin`

The file was already present in the working directory. Verified it wasn't
corrupted/truncated by downloading a fresh copy and comparing SHA256:

```
67c19ae123d84152019b57526ed5291dd0a2b4edd87655c5f76b46c9a62ff5dd  ESP32_GENERIC_S3-SPIRAM_OCT-20260406-v1.28.0.bin
67c19ae123d84152019b57526ed5291dd0a2b4edd87655c5f76b46c9a62ff5dd  /tmp/firmware_check.bin
```
Match — no re-download needed.

## 3. Flash it

```
esptool --chip esp32s3 --port /dev/ttyACM0 erase_flash
esptool --chip esp32s3 --port /dev/ttyACM0 write_flash -z 0 ESP32_GENERIC_S3-SPIRAM_OCT-20260406-v1.28.0.bin
```

- Erase: completed in 8.2s.
- Write: 1,758,064 bytes (1,150,760 compressed) written at offset 0x0 in
  11.8s, hash verified successfully.

## 4. Verify it booted

Immediately after the flash, `mpremote` failed to open `/dev/ttyACM0` and
the device actually disappeared from `lsusb` entirely. dmesg showed a USB
transfer error and disconnect:

```
xhci_hcd 0000:00:0c.0: ERROR Transfer event TRB DMA ptr not part of current TD ...
usb 1-1: USB disconnect, device number 2
```

This was a USB passthrough glitch in the environment, not a firmware
problem — the device did not re-enumerate on its own. Asked the user to
physically unplug/replug the board. After replugging:

```
Bus 001 Device 003: ID 303a:4001 Espressif Systems Espressif Device
```

Note the USB ID changed from `303a:1001` (JTAG/serial debug bridge, used
during flashing) to `303a:4001` (native USB CDC served by MicroPython
itself) — confirms the new firmware's own USB stack is running.

Confirmed via mpremote:

```
$ mpremote connect /dev/ttyACM0 exec "import sys; print(sys.implementation); print(sys.platform)"
(name='micropython', version=(1, 28, 0, ''), _machine='Generic ESP32S3 module with Octal-SPIRAM with ESP32S3', _mpy=11014, _build='ESP32_GENERIC_S3-SPIRAM_OCT', _thread='GIL')
esp32
```

## 5. Quick functional test

`test_quick.py`:
```python
import time

print("Hello from MicroPython on CYD!")
for i in range(5):
    print("tick", i)
    time.sleep(0.2)

import machine
print("Free heap:", __import__("gc").mem_free())
print("CPU freq:", machine.freq())
```

Ran with `mpremote connect /dev/ttyACM0 run test_quick.py`:

```
Hello from MicroPython on CYD!
tick 0
tick 1
tick 2
tick 3
tick 4
Free heap: 8318560
CPU freq: 240000000
```

~8.3MB free heap confirms the Octal PSRAM is active and being counted
toward the heap; CPU running at the expected 240MHz.

## Outcome (firmware flashing)

CYD (ESP32-S3, Octal 8MB PSRAM) is flashed with MicroPython v1.28.0
(`ESP32_GENERIC_S3-SPIRAM_OCT` build) and confirmed fully functional.

# Session continued: building a clock display for the board

## 6. Discovering this is a different repo/board than expected

While starting the clock program, `git ls-tree -r HEAD` came up empty in
this directory even though `git log` showed real commits. Turned out
`/home/mpayne/cyd17June2026/26dollars` (where this whole session had been
working) is an **untracked subdirectory** — the actual git repo root is
the parent, `/home/mpayne/cyd17June2026`, which already contains a working
project from earlier sessions:

- `clock.py` / `chuck.py` / `main.py` / `ili9341.py` — written for the
  classic ESP32 **ESP32-2432S028R** CYD (display on GPIO 13/14/15/2/21).

The board flashed in this session identifies as **ESP32-S3**, a different
chip from that older code's target, so the existing driver/pins don't
necessarily apply.

Asked the user to confirm: this is a **different/newer S3 board**, not the
one the existing code targets. Asked for the model printed on the PCB —
user identified it as a **Waveshare ESP32-S3-Touch-LCD-2** (240×320,
capacitive touch).

## 7. Finding the real pinout

Waveshare's wiki page returned HTTP 403 to WebFetch, and demo code wasn't
indexed well enough to find exact GPIO numbers via search. Downloaded the
official schematic PDF directly and read it:
`https://files.waveshare.com/wiki/ESP32-S3-Touch-LCD-2/ESP32-S3-Touch-LCD-2-SchDoc.pdf`

Extracted from the schematic's net-label table:

| Signal     | GPIO | Notes |
|------------|------|-------|
| LCD_SCLK   | 39   | shared with SD_SCLK |
| LCD_MOSI   | 38   | shared with SD_MOSI |
| LCD_DC     | 42   | |
| LCD_CS     | 45   | |
| LCD_RST    | 0    | shared with BOOT strap pin — safe to drive after boot |
| LCD_BL     | 1    | backlight, active high |
| TP_INT     | 46   | touch interrupt |
| TP_SCL     | 47   | shared with IMU_SCL (I2C) |
| TP_SDA     | 48   | shared with IMU_SDA (I2C) |
| IMU_INT1   | 3    | onboard QMI8658C IMU, unrelated to clock |

Display controller is **ST7789** (not ILI9341 like the older board), so
the existing `ili9341.py` driver wouldn't have worked even with correct
pins — different init/register quirks.

## 8. Writing the driver and clock script

- `st7789.py` — minimal ST7789 driver, deliberately mirroring the API of
  the existing `ili9341.py` (`fill`, `fill_rect`, `pixel`, `text` with
  `scale=`, `blit_buffer`) so it's a drop-in style match for this project.
- `clock_s3.py` — same structure as the original `clock.py` (load `.env`
  for Wi-Fi creds, connect, NTP sync, redraw once/sec only when the
  second changes), just repointed at the new pins/driver.

Deployed to the device with `mpremote fs cp` (`.env`, `st7789.py`,
`clock_s3.py`) and ran with `mpremote run clock_s3.py`.

## 9. Debugging along the way

**Wi-Fi scan found 0 networks** on the first run even though the radio
was healthy (`active=True`, correct MAC). Confirmed it wasn't a code bug
by scanning 3x with diagnostics — board just couldn't see any 2.4GHz
network from where it was. Worked around it for the test by manually
setting `machine.RTC().datetime(...)` from the host's `date -u` output
(careful to strip leading zeros — MicroPython's `exec` parses `06` as an
invalid octal literal) so the clock displayed the real time immediately.
On a later run, Wi-Fi connected fine (hotspot `172.20.10.x`) and NTP sync
succeeded normally — the original failure was transient/environmental,
not a bug.

**Font appeared mirrored** once the display was visually checked. Root
cause: the `MADCTL` row/column-exchange bit (`MV`) was set for landscape
rotation but the column-address-order bit (`MX`) was not, and this
specific panel's physical mounting needs both to read non-mirrored
(the older ILI9341 panel needed a different bit combination for the same
reason — these MADCTL values are panel-mount-specific, not a fixed
standard). Fixed by changing the landscape rotation value in
`st7789.py` from `0x20` to `0x60` (added `MX`). Confirmed fixed by the
user after reflashing — text now reads correctly.

## Outcome (clock display)

`clock_s3.py` + `st7789.py` now run on the Waveshare ESP32-S3-Touch-LCD-2,
connecting to Wi-Fi, syncing real time via NTP, and redrawing the
date/time once per second with correct (non-mirrored) text orientation.
Not yet installed as `main.py`, so it currently must be started manually
via `mpremote run clock_s3.py` rather than running automatically on
power-up.
