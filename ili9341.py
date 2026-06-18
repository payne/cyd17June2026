"""
Minimal ILI9341 driver for ESP32-2432S028R ("Cheap Yellow Display").
SPI display only (no touch). Supports fill, pixel, and text via 8x8 font.
"""
from micropython import const
from machine import Pin, SPI
import framebuf
import time

_SWRESET = const(0x01)
_SLPOUT = const(0x11)
_DINVOFF = const(0x20)
_DINVON = const(0x21)
_DISPOFF = const(0x28)
_DISPON = const(0x29)
_CASET = const(0x2A)
_PASET = const(0x2B)
_RAMWR = const(0x2C)
_MADCTL = const(0x36)
_COLMOD = const(0x3A)


class ILI9341:
    def __init__(self, spi, cs, dc, rst=None, bl=None, width=240, height=320, rotation=1):
        self.spi = spi
        self.cs = cs
        self.dc = dc
        self.rst = rst
        self.bl = bl
        self.width = width
        self.height = height

        self.cs.init(Pin.OUT, value=1)
        self.dc.init(Pin.OUT, value=0)
        if self.rst:
            self.rst.init(Pin.OUT, value=1)
        if self.bl:
            self.bl.init(Pin.OUT, value=1)

        self.reset()
        self._init_display()
        self.rotation(rotation)

    def reset(self):
        if self.rst:
            self.rst(1)
            time.sleep_ms(10)
            self.rst(0)
            time.sleep_ms(10)
            self.rst(1)
            time.sleep_ms(120)

    def _write(self, cmd=None, data=None):
        self.cs(0)
        if cmd is not None:
            self.dc(0)
            self.spi.write(bytes([cmd]))
        if data is not None:
            self.dc(1)
            self.spi.write(data)
        self.cs(1)

    def _init_display(self):
        self._write(_SWRESET)
        time.sleep_ms(150)
        self._write(_SLPOUT)
        time.sleep_ms(120)
        self._write(_COLMOD, b"\x55")  # 16-bit color
        self._write(_MADCTL, b"\x48")
        self._write(_DISPON)
        time.sleep_ms(100)

    def rotation(self, r):
        # 0=portrait,1=landscape,2=portrait flipped,3=landscape flipped
        modes = [0x48, 0x28, 0x88, 0xE8]
        self._write(_MADCTL, bytes([modes[r % 4]]))
        if r % 2 == 1:
            self.width, self.height = 320, 240
        else:
            self.width, self.height = 240, 320

    def set_window(self, x0, y0, x1, y1):
        self._write(_CASET, bytes([x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF]))
        self._write(_PASET, bytes([y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF]))
        self._write(_RAMWR)

    def fill_rect(self, x, y, w, h, color):
        self.set_window(x, y, x + w - 1, y + h - 1)
        hi = color >> 8
        lo = color & 0xFF
        line = bytes([hi, lo]) * w
        self.dc(1)
        self.cs(0)
        for _ in range(h):
            self.spi.write(line)
        self.cs(1)

    def fill(self, color):
        self.fill_rect(0, 0, self.width, self.height, color)

    def pixel(self, x, y, color):
        self.fill_rect(x, y, 1, 1, color)

    def text(self, fb_text, x, y, color, scale=1, bg=None):
        """Draw text using an offscreen 8px-tall framebuffer, scaled up, then blit."""
        w = len(fb_text) * 8
        h = 8
        buf = bytearray(w * h // 8 + w)  # generous buffer for MONO_HLSB-ish use
        fbuf = framebuf.FrameBuffer(bytearray(w * h * 2), w, h, framebuf.RGB565)
        if bg is not None:
            fbuf.fill(bg)
        else:
            fbuf.fill(0x0000)
        fbuf.text(fb_text, 0, 0, color)

        if scale == 1:
            self.blit_buffer(fbuf, x, y, w, h)
        else:
            # manual nearest-neighbor scale
            sw, sh = w * scale, h * scale
            big = framebuf.FrameBuffer(bytearray(sw * sh * 2), sw, sh, framebuf.RGB565)
            for yy in range(h):
                for xx in range(w):
                    c = fbuf.pixel(xx, yy)
                    if c:
                        big.fill_rect(xx * scale, yy * scale, scale, scale, color)
            self.blit_buffer(big, x, y, sw, sh)

    def blit_buffer(self, fbuf, x, y, w, h):
        self.set_window(x, y, x + w - 1, y + h - 1)
        self.dc(1)
        self.cs(0)
        self.spi.write(fbuf)
        self.cs(1)
