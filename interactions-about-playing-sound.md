# Session: WAV playback on the ESP32-2432S028R CYD

Target boards: the two classic CYD boards in `2514/` and `26June26/` (both
ESP32-D0WD-V3, same family as the board that runs `chuck.py` / `clock.py`).

---

## 1. Identify the hardware

`2514/flash_id.txt` and `26June26/flash_id.txt` both show:

```
Chip type:   ESP32-D0WD-V3 (revision v3.1)
Features:    Wi-Fi, BT, Dual Core + LP Core, 240MHz
Flash:       4 MB
```

These are classic ESP32s, the same silicon as the original CYD. The `2514`
directory name comes from the last four hex digits of that board's MAC address
(`78:42:1c:94:c5:14`); `26June26` is a board acquired 2026-06-26.

The relevant existing code in the repo root (`chuck.py`, `clock.py`,
`ili9341.py`) targets this same family.

---

## 2. Research the audio hardware

### SPEAK connector

The CYD has a 2-pin **1.25 mm pitch** connector labeled **SPEAK** on the back
of the board (near the USB-C port). The signal path is:

```
GPIO 26 (DAC2)  →  capacitor coupling  →  SC8002B amplifier  →  SPEAK connector
```

The **SC8002B** is a 1 W bridge-tied-load (BTL) class-AB audio amplifier. It
is already on the board — no external amp is needed. Plug any passive 8 Ω
speaker directly into SPEAK.

**Important correction from early in the session:** the speaker connector was
initially described as "CN1". That was wrong. CN1 is an unrelated expansion
header (GPIO 22, GPIO 27, 3.3 V, GND). The speaker connector is distinctly
labeled SPEAK.

Sources:
- [Random Nerd Tutorials — CYD pinout](https://randomnerdtutorials.com/esp32-cheap-yellow-display-cyd-pinout-esp32-2432s028r/)
- [Kafkar — CYD connectors and pinout](https://kafkar.com/projects/smart-home/understanding-connectors-and-pinout-cheap-yellow-display-boardcyd-esp32-2432s028r/)
- [witnessmenow/ESP32-Cheap-Yellow-Display PINS.md](https://github.com/witnessmenow/ESP32-Cheap-Yellow-Display/blob/main/PINS.md)

### Why DAC, not I2S or PWM

The ESP32 has two 8-bit DAC channels:
- **DAC1** → GPIO 25
- **DAC2** → GPIO 26 ← routed to the SC8002B on the CYD

The `machine.DAC` class in MicroPython (ESP32 port, v1.28.0) exposes a
`write(value)` method that outputs a DC voltage proportional to the 8-bit
value. This is the correct interface for this board.

`machine.I2S` exists in MicroPython v1.28 but requires an external I2S DAC
chip (e.g., PCM5102, MAX98357). The CYD has no such chip. `write_timed()`
with DMA is available on the STM32 port only — not ESP32.

---

## 3. Write the WAV player

Created `wav_player.py` at the repo root.

### Design decisions

**Streaming, not pre-loading.** Reading the entire WAV into RAM would work
for short clips (the board has ~520 KB internal SRAM and no PSRAM), but fails
for anything over ~30 seconds at 8 kHz. The player reads in 256-frame chunks
from flash.

**`ticks_us()` busy-wait for timing.** A simple `time.sleep_us(N)` call drifts
because it sleeps *at least* N µs; accumulated error is noticeable over a few
seconds. Using an anchor timestamp (`t_next`) and busy-waiting until it is
reached compensates for Python loop overhead and keeps timing accurate across
the full clip.

**8-bit and 16-bit support.** 16-bit samples (signed, little-endian) are
converted to 8-bit unsigned on the fly: `val = (s16 >> 8) + 128`. Stereo
files use the left channel only.

**Graceful header parsing.** Many WAV editors insert extra chunks (`LIST`,
`JUNK`, `bext`, etc.) before or between `fmt ` and `data`. The parser scans
forward chunk-by-chunk rather than assuming a fixed 44-byte header.

### Recommended WAV format

8000 Hz, 8-bit, mono. At 8 kHz the inter-sample interval is 125 µs, which
comfortably absorbs the ~20–40 µs of Python overhead per iteration. At
22050 Hz (45 µs/sample) the margin is gone and playback runs slightly fast.

Convert on the host with ffmpeg:

```bash
# Best choice — 8 kHz mono 8-bit
ffmpeg -i input.mp3 -ar 8000 -ac 1 -acodec pcm_u8 sound.wav

# Higher quality option
ffmpeg -i input.mp3 -ar 11025 -ac 1 -acodec pcm_s16le sound.wav
```

### Key code sections

```python
SPEAKER_PIN = 26  # DAC2 → SC8002B 1W amp → SPEAK connector (2-pin 1.25mm JST)

def _parse_header(f):
    # Scans RIFF chunks generically; handles non-standard headers
    ...

def play(filename, pin=SPEAKER_PIN):
    # Streams in 256-frame chunks; uses ticks_us() anchor for sample timing
    t_next = time.ticks_us()
    while frames_done < total_frames:
        n = f.readinto(buf)
        for i in range(nf):
            # convert sample to 8-bit unsigned ...
            while time.ticks_diff(t_next, time.ticks_us()) > 0:
                pass
            dac.write(val)
            t_next = time.ticks_add(t_next, us)
    dac.write(128)  # leave at mid-rail (silence) to avoid pop
```

Full source: `wav_player.py`

---

## 4. Speaker shopping

Connector needed: **2-pin JST PH 1.25 mm** (also marketed as "Molex PicoBlade
1.25 mm"). Speaker impedance: **8 Ω**. Wattage: anything 0.5 W–1 W is ideal;
higher wattage speakers work electrically, the SC8002B will just run below
their rated power.

| Product | Qty | Link | Approx. price |
|---------|-----|------|---------------|
| Treedix 1 W 8 Ω, JST-PH1.25mm | 8-pack | [Amazon B0D878Q3JH](https://www.amazon.com/Treedix-Full-Range-Advertising-JST-PH1-25mm-2-Electronic/dp/B0D878Q3JH) | ~$10 |
| Treedix 0.5 W 8 Ω, JST-PH1.25mm | 6-pack | [Amazon B0D8Q4XZ14](https://www.amazon.com/Treedix-Full-Range-Advertising-JST-PH1-25mm-2-Electronic/dp/B0D8Q4XZ14) | ~$8 |
| ACEIRMC 2 W 8 Ω, JST-PH1.25 | 4-pack | [Amazon B0GWH7W4MR](https://www.amazon.com/ACEIRMC-Speaker-Loundspeaker-JST-PH1-25-2Pin-Advertising/dp/B0GWH7W4MR) | ~$9 |
| JUZITAO 1 W 8 Ω, JST-PH1.25mm | 6-pack | [Amazon B0F23HC439](https://www.amazon.com/JUZITAO-Loudspeaker-Full-Range-Advertising-JST-PH2-54mm-2/dp/B0F23HC439) | ~$9 |

Prices checked June 2026; verify at checkout.

---

## 5. Deploy and run

```bash
# Copy player and audio file to the board
mpremote fs cp wav_player.py :wav_player.py
mpremote fs cp sound.wav :sound.wav

# Run (plays sound.wav, blocks until done, Ctrl-C to stop)
mpremote run wav_player.py
```

From another MicroPython script:

```python
import wav_player
wav_player.play("beep.wav")
```

---

## 6. Files created this session

| File | Description |
|------|-------------|
| `wav_player.py` | MicroPython WAV player |
| `wav_player.md` | Full hardware and usage documentation |
| `interactions-about-playing-sound.md` | This file |
