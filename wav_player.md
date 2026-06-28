# WAV Player for ESP32-2432S028R (CYD)

Plays PCM WAV files through the CYD's built-in audio output using MicroPython.

---

## How it works

`wav_player.py` streams a WAV file from the board's filesystem, converts samples
to 8-bit unsigned values, and outputs them via the ESP32's DAC2 peripheral
(GPIO 26) at the correct sample rate. Timing uses `ticks_us()` busy-wait so
drift does not accumulate across chunks.

Supports:
- 8-bit and 16-bit PCM (stereo files use the left channel only)
- Any sample rate (8 kHz and 11025 Hz recommended — see below)

---

## Hardware — the SPEAK connector

The CYD has a **2-pin 1.25 mm pitch** connector labeled **SPEAK** on the back of
the board. It sits next to the USB-C port.

```
Signal path:
  GPIO 26 (DAC2) → cap-coupled → SC8002B 1 W amplifier → SPEAK connector
```

The onboard **SC8002B** is a bridge-tied-load (BTL) class-AB amplifier rated at
1 W into 8 Ω. No external amplifier is needed — plug a passive 8 Ω speaker
directly into SPEAK.

| SPEAK pin | Signal  |
|-----------|---------|
| 1         | Speaker+ |
| 2         | Speaker− |

Polarity is marked on the PCB silkscreen. Swapping + and − on a speaker just
inverts phase — for a single speaker it makes no audible difference.

Reference:
- [Random Nerd Tutorials — CYD pinout](https://randomnerdtutorials.com/esp32-cheap-yellow-display-cyd-pinout-esp32-2432s028r/)
- [Kafkar — CYD connectors and pinout](https://kafkar.com/projects/smart-home/understanding-connectors-and-pinout-cheap-yellow-display-boardcyd-esp32-2432s028r/)
- [witnessmenow/ESP32-Cheap-Yellow-Display PINS.md](https://github.com/witnessmenow/ESP32-Cheap-Yellow-Display/blob/main/PINS.md)

---

## Buying a speaker

You need an **8 Ω** speaker with a **2-pin JST PH 1.25 mm** connector
(also sold as "Molex PicoBlade 1.25 mm"). Small cavity speakers in the 0.5–1 W
range are ideal; the SC8002B is only rated at 1 W so higher-wattage speakers
work fine electrically (just buy a small form factor that fits your enclosure).

| Option | Qty | Connector | Link | Approx. price |
|--------|-----|-----------|------|---------------|
| Treedix 1 W 8 Ω | 8-pack | JST-PH1.25mm-2 | [Amazon B0D878Q3JH](https://www.amazon.com/Treedix-Full-Range-Advertising-JST-PH1-25mm-2-Electronic/dp/B0D878Q3JH) | ~$10 |
| Treedix 0.5 W 8 Ω | 6-pack | JST-PH1.25mm-2 | [Amazon B0D8Q4XZ14](https://www.amazon.com/Treedix-Full-Range-Advertising-JST-PH1-25mm-2-Electronic/dp/B0D8Q4XZ14) | ~$8 |
| ACEIRMC 2 W 8 Ω | 4-pack | JST-PH1.25-2Pin | [Amazon B0GWH7W4MR](https://www.amazon.com/ACEIRMC-Speaker-Loundspeaker-JST-PH1-25-2Pin-Advertising/dp/B0GWH7W4MR) | ~$9 |
| JUZITAO 1 W 8 Ω | 6-pack | JST-PH1.25mm-2 | [Amazon B0F23HC439](https://www.amazon.com/JUZITAO-Loudspeaker-Full-Range-Advertising-JST-PH2-54mm-2/dp/B0F23HC439) | ~$9 |

> Prices are approximate and change frequently; check the links for current pricing.

All of the above plug directly into the SPEAK connector with no wiring needed.

---

## WAV file requirements

| Setting | Recommended | Also works |
|---------|-------------|------------|
| Sample rate | 8000 Hz | up to ~22050 Hz |
| Bit depth | 8-bit | 16-bit (auto-converted) |
| Channels | Mono | Stereo (left channel used) |
| Format | PCM (uncompressed) | — |

**Why 8 kHz?** The inner playback loop runs in MicroPython, which adds roughly
20–40 µs of overhead per sample. At 8 kHz (125 µs/sample) that overhead is
absorbed by the `ticks_us()` busy-wait with plenty of margin. At 22050 Hz
(45 µs/sample) you may hear slight pitch deviation. For speech, 8 kHz is
indistinguishable from higher rates. For music, 11025 Hz is a reasonable
compromise.

### Converting audio on your PC

Using [ffmpeg](https://ffmpeg.org):

```bash
# Convert anything → 8 kHz mono 8-bit WAV (smallest, most reliable)
ffmpeg -i input.mp3 -ar 8000 -ac 1 -acodec pcm_u8 sound.wav

# Convert anything → 11025 Hz mono 16-bit WAV (better quality)
ffmpeg -i input.mp3 -ar 11025 -ac 1 -acodec pcm_s16le sound.wav
```

---

## Usage

### 1. Copy the files to the board

```bash
mpremote fs cp wav_player.py :wav_player.py
mpremote fs cp sound.wav :sound.wav
```

### 2. Run directly

```bash
mpremote run wav_player.py
```

This plays `sound.wav` (hardcoded filename at the bottom of the file). Press
Ctrl-C to stop; the DAC is left at mid-rail (128) to avoid a pop.

### 3. Import and call from your own code

```python
import wav_player

wav_player.play("beep.wav")          # plays beep.wav, blocks until done
wav_player.play("alert.wav", pin=25) # use GPIO 25 (DAC1) instead
```

`play()` accepts an optional `pin` argument if you want to route audio to
GPIO 25 (DAC1) rather than the default GPIO 26 (DAC2 / SPEAK).

---

## File layout

```
wav_player.py   — the player (import or run directly)
sound.wav       — your audio file (copy to board filesystem)
```

---

## Limitations

- **RAM**: no limit on WAV file size — audio streams from flash in 256-frame
  chunks. Flash on the board is 4 MB; a 30-second 8 kHz 8-bit mono clip is
  ~240 KB.
- **Quality**: single-channel 8-bit output through a 1 W amplifier — adequate
  for voice prompts, beeps, and simple melodies.
- **No I2S DAC**: the CYD does not have an external I2S DAC chip, so hardware-
  timed DMA playback is not available. Timing is software-controlled via
  `ticks_us()` busy-wait.
