"""
CYD (ESP32-2432S028R) clock display.
Syncs time over NTP at boot, then redraws the clock each second using
the ESP32's internal RTC.

Pinout for the most common ESP32-2432S028R revision:
  TFT_MOSI = 13
  TFT_SCLK = 14
  TFT_CS   = 15
  TFT_DC   = 2
  TFT_RST  = -1 (tied to EN, not separately controlled)
  TFT_BL   = 21  (backlight, active high)
"""
import network
import ntptime
import time
from machine import Pin, SPI, RTC
from ili9341 import ILI9341


def load_env(path=".env"):
    env = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                env[key.strip()] = val.strip()
    except OSError:
        pass
    return env


_env = load_env()
WIFI_SSID = _env.get("WIFI_SSID", "")
WIFI_PASSWORD = _env.get("WIFI_PASSWORD", "")

# Set to your UTC offset in seconds. Central US (CST=-6, CDT=-5).
# Omaha is currently on Central Daylight Time (UTC-5) in June.
UTC_OFFSET_SECONDS = -5 * 3600

BG_COLOR = 0x0000      # black
TEXT_COLOR = 0xFFE0    # yellow
DATE_COLOR = 0x07FF    # cyan


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to Wi-Fi...")
        try:
            wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        except OSError as e:
            print("Wi-Fi connect failed:", e)
            return False
        timeout = 15
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
    if wlan.isconnected():
        print("Wi-Fi connected:", wlan.ifconfig())
        return True
    print("Wi-Fi connection failed")
    return False


def sync_time():
    try:
        ntptime.settime()  # sets RTC to UTC
        print("Time synced via NTP")
        return True
    except Exception as e:
        print("NTP sync failed:", e)
        return False


def local_time():
    t = time.time() + UTC_OFFSET_SECONDS
    return time.localtime(t)


def setup_display():
    spi = SPI(1, baudrate=40000000, polarity=0, phase=0,
              sck=Pin(14), mosi=Pin(13))
    cs = Pin(15)
    dc = Pin(2)
    bl = Pin(21)
    display = ILI9341(spi, cs=cs, dc=dc, rst=None, bl=bl, rotation=1)
    display.fill(BG_COLOR)
    return display


def _draw_clock_frame(display, last_drawn):
    lt = local_time()
    time_str = "{:02d}:{:02d}:{:02d}".format(lt[3], lt[4], lt[5])
    date_str = "{:04d}-{:02d}-{:02d}".format(lt[0], lt[1], lt[2])

    if time_str != last_drawn:
        display.fill_rect(0, 80, display.width, 60, BG_COLOR)
        display.text(time_str, 60, 90, TEXT_COLOR, scale=4)
        display.text(date_str, 80, 150, DATE_COLOR, scale=2)
        last_drawn = time_str

    return last_drawn


def run_for(display, seconds):
    """Show the clock, updating once a second, for `seconds` seconds."""
    display.fill(BG_COLOR)
    last_drawn = ""
    end = time.time() + seconds
    while time.time() < end:
        last_drawn = _draw_clock_frame(display, last_drawn)
        time.sleep_ms(200)


def main():
    display = setup_display()
    display.text("Connecting WiFi...", 10, 10, 0xFFFF)

    wifi_ok = connect_wifi()
    display.fill(BG_COLOR)

    if wifi_ok:
        sync_time()
    else:
        display.text("No WiFi - using", 10, 10, 0xF800)
        display.text("internal clock only", 10, 25, 0xF800)
        time.sleep(2)

    display.fill(BG_COLOR)

    last_drawn = ""
    while True:
        last_drawn = _draw_clock_frame(display, last_drawn)
        time.sleep_ms(200)


if __name__ == "__main__":
    main()
