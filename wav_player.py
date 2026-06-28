"""
WAV player for ESP32-2432S028R CYD.
Plays audio via GPIO26 DAC2 → SC8002B amp → SPEAK connector.

Best results: 8000 Hz or 11025 Hz, 8-bit, mono PCM WAV.
16-bit PCM and stereo are also supported (stereo uses the left channel only).

Usage:
    import wav_player
    wav_player.play("sound.wav")

Or run directly (plays "sound.wav" from the filesystem):
    mpremote run wav_player.py

Copy a WAV to the board first:
    mpremote fs cp sound.wav :sound.wav
"""

from machine import Pin, DAC
import time

SPEAKER_PIN = 26  # DAC2 → SC8002B 1W amp → SPEAK connector (2-pin 1.25mm JST)


def _parse_header(f):
    """
    Parse RIFF/WAV header; leave f positioned at the start of PCM data.
    Returns (channels, sample_rate, bits_per_sample, data_size_bytes).
    Handles non-standard chunk ordering and extra chunks (e.g. LIST, JUNK).
    """
    if f.read(4) != b'RIFF':
        raise ValueError("not a RIFF file")
    f.read(4)  # file size (ignored)
    if f.read(4) != b'WAVE':
        raise ValueError("not a WAVE file")

    channels = rate = bits = 0
    while True:
        tag = f.read(4)
        if len(tag) < 4:
            raise ValueError("data chunk not found")
        size = tag[0] | tag[1] << 8  # reuse tag bytes as scratch — re-read size properly
        size = int.from_bytes(f.read(4), 'little')

        if tag == b'fmt ':
            b = f.read(size)
            fmt_type = b[0] | (b[1] << 8)
            if fmt_type != 1:
                raise ValueError("only PCM WAV supported (fmt={})".format(fmt_type))
            channels = b[2] | (b[3] << 8)
            rate = b[4] | (b[5] << 8) | (b[6] << 16) | (b[7] << 24)
            bits = b[14] | (b[15] << 8)
            if bits not in (8, 16):
                raise ValueError("only 8 or 16-bit WAV supported")

        elif tag == b'data':
            return channels, rate, bits, size

        else:
            f.seek(size, 1)  # skip unknown/unneeded chunk


def play(filename, pin=SPEAKER_PIN):
    """
    Play a WAV file through the CYD speaker. Blocks until playback completes.
    Press Ctrl-C to stop early.
    """
    dac = DAC(Pin(pin))
    try:
        with open(filename, 'rb') as f:
            channels, rate, bits, data_size = _parse_header(f)
            frame = (bits // 8) * channels
            total_frames = data_size // frame
            us_per_frame = 1_000_000 // rate

            print("{} ch  {} Hz  {}-bit  {:.1f} s".format(
                channels, rate, bits, total_frames / rate))

            # 256-frame read buffer; small enough to limit SD/flash latency spikes
            buf = bytearray(256 * frame)
            frames_done = 0

            # Anchor time so per-sample drift doesn't accumulate
            t_next = time.ticks_us()

            while frames_done < total_frames:
                n = f.readinto(buf)
                if not n:
                    break
                nf = min(n // frame, total_frames - frames_done)

                for i in range(nf):
                    off = i * frame
                    if bits == 8:
                        val = buf[off]          # unsigned 0–255
                    else:
                        # 16-bit signed little-endian → unsigned 8-bit
                        s = buf[off] | (buf[off + 1] << 8)
                        if s > 32767:
                            s -= 65536
                        val = (s >> 8) + 128    # 0–255

                    # Busy-wait for the right moment, then write
                    while time.ticks_diff(t_next, time.ticks_us()) > 0:
                        pass
                    dac.write(val)
                    t_next = time.ticks_add(t_next, us_per_frame)

                frames_done += nf

    except KeyboardInterrupt:
        print("stopped")
    finally:
        dac.write(128)  # mid-rail = silence, avoids a pop on disconnect
        print("done")


if __name__ == "__main__":
    play("sound.wav")
