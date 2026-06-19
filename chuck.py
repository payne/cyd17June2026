"""
CYD (ESP32-2432S028R) Chuck Norris quote display.
Shows a random Chuck Norris joke from a built-in list, swapping to a new
one every 20 seconds, with a countdown timer in the top-right corner.

Pinout for the most common ESP32-2432S028R revision:
  TFT_MOSI = 13
  TFT_SCLK = 14
  TFT_CS   = 15
  TFT_DC   = 2
  TFT_RST  = -1 (tied to EN, not separately controlled)
  TFT_BL   = 21  (backlight, active high)
"""
import random
import time
from machine import Pin, SPI
from ili9341 import ILI9341

BG_COLOR = 0x0000      # black
TEXT_COLOR = 0xFFE0    # yellow
TIMER_COLOR = 0x07FF   # cyan

QUOTE_INTERVAL_S = 20

QUOTES = [
    "Chuck Norris can divide by zero.",
    "Chuck Norris counted to infinity. Twice.",
    "Time waits for no man. Unless that man is Chuck Norris.",
    "Chuck Norris's calendar goes straight from March 31st to April 2nd.",
    "Death once had a near-Chuck Norris experience.",
    "Chuck Norris can slam a revolving door.",
    "Chuck Norris does not sleep. He waits.",
    "When Chuck Norris does a push-up, he pushes the Earth down.",
    "Chuck Norris can hear sign language.",
    "Chuck Norris's beard can cure cancer.",
    "Chuck Norris doesn't read books. He stares them down until he gets the information he wants.",
    "Chuck Norris ordered a Big Mac at Burger King and got one.",
    "There is no theory of evolution, just a list of animals Chuck Norris allows to live.",
    "Chuck Norris can win a game of Connect Four in three moves.",
    "Chuck Norris once rode a nine foot grizzly bear through an automatic car wash.",
    "Chuck Norris can light a fire by rubbing two ice cubes together.",
    "Chuck Norris's tears cure cancer. Too bad he has never cried.",
    "Chuck Norris doesn't wear a watch. He decides what time it is.",
    "Chuck Norris can speak braille.",
    "Chuck Norris can win at solitaire with only three cards.",
    "Chuck Norris can unscramble an egg.",
    "Chuck Norris once ate an entire bottle of sleeping pills. They made him blink.",
    "Chuck Norris's roundhouse kick is so fast it can cross multiple time zones.",
    "Chuck Norris can drown a fish.",
    "Chuck Norris can blow bubbles with beef jerky.",
    "Outer space exists because it's afraid to be on the same planet as Chuck Norris.",
    "Chuck Norris doesn't use Twitter, because he can already break 140 characters with one punch.",
    "When Chuck Norris goes to donate blood, he declines the syringe and asks for a knife and a bucket.",
    "Chuck Norris can make a clock tick faster just by staring at it.",
    "Chuck Norris doesn't need a parachute. He just holds his breath and falls slower.",
]


def setup_display():
    spi = SPI(1, baudrate=40000000, polarity=0, phase=0,
              sck=Pin(14), mosi=Pin(13))
    cs = Pin(15)
    dc = Pin(2)
    bl = Pin(21)
    display = ILI9341(spi, cs=cs, dc=dc, rst=None, bl=bl, rotation=1)
    display.fill(BG_COLOR)
    return display


def wrap_text(text, max_chars):
    words = text.split(" ")
    lines = []
    line = ""
    for word in words:
        candidate = (line + " " + word).strip()
        if len(candidate) > max_chars and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


MARGIN = 5


def draw_quote(display, quote, scale=2):
    display.fill_rect(0, 0, display.width, display.height, BG_COLOR)
    max_chars = (display.width - 2 * MARGIN) // (8 * scale)
    lines = wrap_text(quote, max_chars)
    line_height = 8 * scale + 6
    total_h = len(lines) * line_height
    y = max(10, (display.height - total_h) // 2)
    for line in lines:
        x = max(MARGIN, (display.width - len(line) * 8 * scale) // 2)
        display.text(line, x, y, TEXT_COLOR, scale=scale)
        y += line_height


def draw_timer(display, seconds_left):
    x, y, w, h = display.width - 50, 0, 50, 24
    display.fill_rect(x, y, w, h, BG_COLOR)
    display.text("{:2d}".format(seconds_left), x + 5, y + 4, TIMER_COLOR, scale=2)


def _pick_index(exclude_index):
    index = random.randrange(len(QUOTES))
    while index == exclude_index and len(QUOTES) > 1:
        index = random.randrange(len(QUOTES))
    return index


def run_for(display, seconds, exclude_index=None):
    """Show one random quote with a countdown timer for `seconds`, then return its index."""
    quote_index = _pick_index(exclude_index)
    draw_quote(display, QUOTES[quote_index])

    seconds_left = seconds
    draw_timer(display, seconds_left)
    while seconds_left > 0:
        time.sleep(1)
        seconds_left -= 1
        draw_timer(display, seconds_left)

    return quote_index


def main():
    display = setup_display()
    random.seed(time.ticks_us())

    last_index = None
    while True:
        last_index = run_for(display, QUOTE_INTERVAL_S, exclude_index=last_index)


if __name__ == "__main__":
    main()
