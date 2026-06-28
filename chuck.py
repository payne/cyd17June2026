"""
CYD (ESP32-2432S028R) Chuck Norris quote display.
Shows a Chuck Norris joke, preferring quotes with a low shown count, swapping
to a new one every 20 seconds with a countdown timer in the top-right corner.
Fetches additional quotes from the internet and caches them locally.
Touch the left button (< BACK) or right button (NEXT >) to navigate quotes.

Pinout for the most common ESP32-2432S028R revision:
  TFT_MOSI = 13        T_CLK  = 25
  TFT_SCLK = 14        T_DIN  = 32  (MOSI)
  TFT_CS   = 15        T_OUT  = 39  (MISO, input-only pin)
  TFT_DC   = 2         T_CS   = 33
  TFT_RST  = -1        T_IRQ  = 36  (input-only pin, active-low)
  TFT_BL   = 21
"""
import random
import time

try:
    import ujson as json
except ImportError:
    import json

from machine import Pin, SPI
from ili9341 import ILI9341

BG_COLOR    = 0x0000   # black
TEXT_COLOR  = 0xFFE0   # yellow
TIMER_COLOR = 0x07FF   # cyan
BTN_COLOR   = 0x3186   # dark-gray buttons
BTN_DIM     = 0x0842   # dimmed button (can't-go-back state)
BTN_LABEL   = 0xFFFF   # white
BTN_LABEL_DIM = 0x4208 # dimmed label

QUOTE_INTERVAL_S  = 20
STATE_FILE        = "chuck_state.json"
MAX_CACHED_QUOTES = 200
MAX_HISTORY       = 50

# XPT2046 calibration for ESP32-2432S028R in landscape (rotation=1).
# If taps feel off, tweak these four values.
TOUCH_X_MIN = 300
TOUCH_X_MAX = 3800
TOUCH_Y_MIN = 300
TOUCH_Y_MAX = 3800
TOUCH_DEBOUNCE_MS = 400

MARGIN = 5
BTN_W  = 100
BTN_H  = 36
BTN_Y  = 200   # buttons occupy rows 200-239 (bottom 40px of 240px screen)

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


class XPT2046:
    """Minimal driver for the XPT2046 resistive touch controller.

    Does not use the IRQ pin — GPIO 36 has no internal pull-up on the ESP32
    and may float.  Touch presence is inferred from the ADC value range
    instead: untouched readings saturate near 0 or 4095; valid touches
    stay in the 200-3900 window.
    """

    def __init__(self, spi, cs):
        self._spi = spi
        self._cs  = cs

    def _sample(self, cmd):
        self._cs(0)
        self._spi.write(bytes([cmd]))
        data = self._spi.read(2)
        self._cs(1)
        return ((data[0] << 8) | data[1]) >> 3

    def read_raw(self):
        """Return (rx, ry) raw ADC values, or None if not touched."""
        rx = (self._sample(0xD0) + self._sample(0xD0)) >> 1  # X channel
        ry = (self._sample(0x90) + self._sample(0x90)) >> 1  # Y channel
        if not (200 <= rx <= 3900 and 200 <= ry <= 3900):
            return None
        return rx, ry

    def read_screen(self, w, h):
        """Return (sx, sy) clamped to screen bounds, or None if not pressed.

        In landscape (rotation=1) on the CYD the raw Y channel maps to screen
        X and the raw X channel maps to screen Y.
        """
        raw = self.read_raw()
        if raw is None:
            return None
        rx, ry = raw
        sx = int((ry - TOUCH_Y_MIN) * w / (TOUCH_Y_MAX - TOUCH_Y_MIN))
        sy = int((rx - TOUCH_X_MIN) * h / (TOUCH_X_MAX - TOUCH_X_MIN))
        return (max(0, min(w - 1, sx)), max(0, min(h - 1, sy)))


def _load_state():
    try:
        with open(STATE_FILE) as f:
            state = json.loads(f.read())
        for q in QUOTES:
            if q not in state["quotes"]:
                state["quotes"].append(q)
                state["counts"].append(0)
        return state
    except Exception:
        return {"quotes": list(QUOTES), "counts": [0] * len(QUOTES)}


def _save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            f.write(json.dumps(state))
    except Exception:
        pass


def _fetch_quote():
    try:
        import urequests
        import network
        wlan = network.WLAN(network.STA_IF)
        if not wlan.isconnected():
            return None
        r = urequests.get("https://api.chucknorris.io/jokes/random", timeout=5)
        data = json.loads(r.text)
        r.close()
        return data.get("value")
    except Exception:
        return None


def setup_display():
    spi = SPI(1, baudrate=40000000, polarity=0, phase=0,
              sck=Pin(14), mosi=Pin(13))
    display = ILI9341(spi, cs=Pin(15), dc=Pin(2), rst=None, bl=Pin(21), rotation=1)
    display.fill(BG_COLOR)
    return display


def setup_touch():
    try:
        spi = SPI(2, baudrate=1_000_000, polarity=0, phase=0,
                  sck=Pin(25), mosi=Pin(32), miso=Pin(39))
        t = XPT2046(spi, Pin(33, Pin.OUT, value=1))
        print("chuck: touch OK")
        return t
    except Exception as e:
        print("chuck: touch FAILED:", e)
        return None


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


def draw_quote(display, quote, scale=2):
    """Draw the quote centered in the upper 200px of the screen."""
    display.fill_rect(0, 0, display.width, BTN_Y, BG_COLOR)
    max_chars = (display.width - 2 * MARGIN) // (8 * scale)
    lines = wrap_text(quote, max_chars)
    line_height = 8 * scale + 6
    total_h = len(lines) * line_height
    y = max(10, (BTN_Y - total_h) // 2)
    for line in lines:
        x = max(MARGIN, (display.width - len(line) * 8 * scale) // 2)
        display.text(line, x, y, TEXT_COLOR, scale=scale)
        y += line_height


def draw_timer(display, seconds_left):
    x, y, w, h = display.width - 50, 0, 50, 24
    display.fill_rect(x, y, w, h, BG_COLOR)
    display.text("{:2d}".format(seconds_left), x + 5, y + 4, TIMER_COLOR, scale=2)


def draw_buttons(display, can_go_back):
    """Draw the < BACK and NEXT > buttons in the bottom strip."""
    display.fill_rect(0, BTN_Y, display.width, display.height - BTN_Y, BG_COLOR)

    # Back button
    bx = MARGIN
    bc = BTN_COLOR if can_go_back else BTN_DIM
    lc = BTN_LABEL if can_go_back else BTN_LABEL_DIM
    display.fill_rect(bx, BTN_Y + 2, BTN_W, BTN_H, bc)
    lbl = "< BACK"
    display.text(lbl, bx + (BTN_W - len(lbl) * 8) // 2, BTN_Y + 2 + (BTN_H - 8) // 2, lc)

    # Next button
    nx = display.width - MARGIN - BTN_W
    display.fill_rect(nx, BTN_Y + 2, BTN_W, BTN_H, BTN_COLOR)
    lbl = "NEXT >"
    display.text(lbl, nx + (BTN_W - len(lbl) * 8) // 2, BTN_Y + 2 + (BTN_H - 8) // 2, BTN_LABEL)


def _pick_index(state, exclude_index):
    quotes = state["quotes"]
    counts = state["counts"]
    n = len(quotes)
    eligible = [i for i in range(n) if i != exclude_index] if n > 1 else list(range(n))
    min_count = min(counts[i] for i in eligible)
    candidates = [i for i in eligible if counts[i] == min_count]
    return candidates[random.randrange(len(candidates))]


def show_quote(display, touch, quote, seconds, can_go_back):
    """Display a quote with countdown and buttons; return 'next', 'back', or 'timeout'."""
    draw_quote(display, quote)
    draw_buttons(display, can_go_back)

    last_touch_ms = -TOUCH_DEBOUNCE_MS  # allow immediate first touch
    for t in range(seconds, 0, -1):
        draw_timer(display, t)
        for _ in range(20):
            if touch is not None:
                now = time.ticks_ms()
                if time.ticks_diff(now, last_touch_ms) >= TOUCH_DEBOUNCE_MS:
                    pos = touch.read_screen(display.width, display.height)
                    if pos is not None:
                        sx, sy = pos
                        last_touch_ms = now
                        if sy >= BTN_Y - 15:
                            if sx <= BTN_W + MARGIN + 15:
                                return "back"
                            if sx >= display.width - BTN_W - MARGIN - 15:
                                return "next"
            time.sleep_ms(50)

    return "timeout"


# ---------------------------------------------------------------------------
# Module-level navigation state — shared by step() and main()
# ---------------------------------------------------------------------------
_state   = None
_history = []
_hist_pos = -1
_touch   = None


def _advance():
    """Append a new quote to _history and update _hist_pos."""
    global _state, _history, _hist_pos
    if _state is None:
        _state = _load_state()
    exclude = _history[_hist_pos] if _history else None
    idx = _pick_index(_state, exclude)
    _state["counts"][idx] += 1
    _save_state(_state)
    del _history[_hist_pos + 1:]
    _history.append(idx)
    _hist_pos = len(_history) - 1
    if len(_history) > MAX_HISTORY:
        _history.pop(0)
        _hist_pos = len(_history) - 1


def init():
    """Load quote state and initialise touch hardware. Call once before step()."""
    global _state, _touch
    _state = _load_state()
    _touch = setup_touch()


def step(display, seconds=QUOTE_INTERVAL_S):
    """Show one chuck quote cycle with Back/Next navigation.

    Always advances to the next (or a new) quote first, then handles touch
    navigation until the auto-advance timer expires, at which point it returns
    so the caller can hand off to other tasks (e.g. the clock).
    """
    global _hist_pos
    if _state is None:
        init()

    # Fetch one new quote per cycle (before drawing, so button presses stay instant)
    if len(_state["quotes"]) < MAX_CACHED_QUOTES:
        fetched = _fetch_quote()
        if fetched and fetched not in _state["quotes"]:
            _state["quotes"].append(fetched)
            _state["counts"].append(0)

    # Advance to the next quote (replay history or pick a new one)
    if _hist_pos < len(_history) - 1:
        _hist_pos += 1
    else:
        _advance()

    while True:
        quote  = _state["quotes"][_history[_hist_pos]]
        action = show_quote(display, _touch, quote, seconds, can_go_back=(_hist_pos > 0))
        if action == "timeout":
            return
        elif action == "next":
            if _hist_pos < len(_history) - 1:
                _hist_pos += 1
            else:
                _advance()
        elif action == "back" and _hist_pos > 0:
            _hist_pos -= 1


def main():
    display = setup_display()
    random.seed(time.ticks_us())
    init()
    while True:
        step(display)


if __name__ == "__main__":
    main()
