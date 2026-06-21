"""
Waveshare ESP32-S3-Touch-LCD-2 orientation display.
Reads the onboard QMI8658C IMU over I2C and shows tilt/orientation info on
the ST7789 LCD, redrawn several times per second.

Pinout (from the official schematic, same as clock_s3.py for the display):
  LCD_SCLK = GPIO39   LCD_MOSI = GPIO38
  LCD_CS   = GPIO45   LCD_DC   = GPIO42
  LCD_RST  = GPIO0    LCD_BL   = GPIO1
  IMU_SCL  = GPIO47   IMU_SDA  = GPIO48  (shared with the touch controller)
"""
import math
import time
from machine import I2C, Pin, SPI
from qmi8658c import QMI8658C
from st7789 import ST7789

BG_COLOR = 0x0000      # black
LABEL_COLOR = 0xFFE0   # yellow
VALUE_COLOR = 0x07FF   # cyan
WARN_COLOR = 0xF800    # red


def setup_display():
    spi = SPI(1, baudrate=40000000, polarity=0, phase=0,
              sck=Pin(39), mosi=Pin(38))
    display = ST7789(spi, cs=Pin(45), dc=Pin(42), rst=Pin(0), bl=Pin(1), rotation=1)
    display.fill(BG_COLOR)
    return display


def setup_imu():
    i2c = I2C(0, scl=Pin(47), sda=Pin(48), freq=400000)
    return QMI8658C(i2c)


def orientation_label(ax, ay, az):
    """Name the face that's pointing "up" by picking the dominant gravity axis.

    Kept to <=12 chars: at scale=3 from x=10, longer text overflows the
    320px display width and wraps the controller's address window into
    garbled "snow" (same bug fixed for chuck.py in commit 279ab56).
    """
    abs_ax, abs_ay, abs_az = abs(ax), abs(ay), abs(az)
    if abs_az >= abs_ax and abs_az >= abs_ay:
        return "Face Up" if az > 0 else "Face Down"
    if abs_ax >= abs_ay:
        return "Right Up" if ax > 0 else "Left Up"
    return "Top Up" if ay > 0 else "Bottom Up"


def draw_line(display, y, text, color, scale, height):
    display.fill_rect(0, y, display.width, height, BG_COLOR)
    display.text(text, 10, y, color, scale=scale)


def main():
    display = setup_display()
    display.text("Starting IMU...", 10, 10, LABEL_COLOR)

    try:
        imu = setup_imu()
    except Exception as e:
        display.fill(BG_COLOR)
        display.text("IMU init failed:", 10, 10, WARN_COLOR)
        display.text(str(e), 10, 25, WARN_COLOR)
        return

    display.fill(BG_COLOR)

    while True:
        ax, ay, az = imu.read_accel_g()
        gx, gy, gz = imu.read_gyro_dps()
        pitch = math.degrees(math.atan2(-ax, math.sqrt(ay * ay + az * az)))
        roll = math.degrees(math.atan2(ay, az))
        label = orientation_label(ax, ay, az)

        draw_line(display, 10, label, LABEL_COLOR, 3, 30)
        draw_line(display, 50, "Pitch: {:6.1f}".format(pitch), VALUE_COLOR, 2, 20)
        draw_line(display, 75, "Roll:  {:6.1f}".format(roll), VALUE_COLOR, 2, 20)
        draw_line(display, 105, "Ax: {:+.2f}g".format(ax), VALUE_COLOR, 2, 20)
        draw_line(display, 130, "Ay: {:+.2f}g".format(ay), VALUE_COLOR, 2, 20)
        draw_line(display, 155, "Az: {:+.2f}g".format(az), VALUE_COLOR, 2, 20)
        draw_line(display, 185, "Gx: {:+.1f} dps".format(gx), VALUE_COLOR, 1, 10)
        draw_line(display, 200, "Gy: {:+.1f} dps".format(gy), VALUE_COLOR, 1, 10)
        draw_line(display, 215, "Gz: {:+.1f} dps".format(gz), VALUE_COLOR, 1, 10)

        time.sleep_ms(150)


if __name__ == "__main__":
    main()
