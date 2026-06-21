"""
Minimal MicroPython driver for the QST QMI8658C 6-axis IMU (accelerometer +
gyroscope) on the Waveshare ESP32-S3-Touch-LCD-2's onboard motion sensor,
which shares the touch controller's I2C bus (GPIO47=SCL, GPIO48=SDA).

Register map taken from the QMI8658C datasheet (rev 0.9) / the published
CircuitPython QMI8658C driver (jins-tkomoda/CircuitPython_QMI8658C).
"""
import time
from struct import unpack

_WHO_AM_I = 0x00
_CTRL1 = 0x02
_CTRL2 = 0x03   # accel range (bits 6:4) + accel ODR (bits 3:0)
_CTRL3 = 0x04   # gyro range (bits 6:4) + gyro ODR (bits 3:0)
_CTRL4 = 0x05
_CTRL5 = 0x06
_CTRL6 = 0x07
_CTRL7 = 0x08   # bit0 = accel enable, bit1 = gyro enable
_ACCEL_OUT = 0x35  # 6 bytes: ax, ay, az (int16 little-endian)
_GYRO_OUT = 0x3B   # 6 bytes: gx, gy, gz (int16 little-endian)

_DEVICE_ID = 0x05

# Accel range=8g (code 2), ODR=125Hz (code 6); scale = 4096 LSB/g
_ACCEL_RANGE_CODE = 2
_ACCEL_ODR_CODE = 6
_ACCEL_SCALE = 4096.0

# Gyro range=512dps (code 5), ODR=125Hz (code 6); scale = 64 LSB/dps
_GYRO_RANGE_CODE = 5
_GYRO_ODR_CODE = 6
_GYRO_SCALE = 64.0


class QMI8658C:
    def __init__(self, i2c, address=None):
        self.i2c = i2c
        self.address = address or self._find_address(i2c)

        device_id = self.i2c.readfrom_mem(self.address, _WHO_AM_I, 1)[0]
        if device_id != _DEVICE_ID:
            raise RuntimeError("QMI8658C not found (WHO_AM_I=0x%02x)" % device_id)

        self._write(_CTRL1, 0x60)  # address auto-increment
        self._write(_CTRL2, (_ACCEL_RANGE_CODE << 4) | _ACCEL_ODR_CODE)
        time.sleep_ms(10)
        self._write(_CTRL3, (_GYRO_RANGE_CODE << 4) | _GYRO_ODR_CODE)
        time.sleep_ms(10)
        self._write(_CTRL4, 0x00)  # no magnetometer
        self._write(_CTRL5, 0x00)  # no low-pass filter
        self._write(_CTRL6, 0x00)  # no motion-on-demand
        self._write(_CTRL7, 0x03)  # enable accel (bit0) + gyro (bit1)
        time.sleep_ms(100)

    @staticmethod
    def _find_address(i2c):
        for addr in (0x6B, 0x6A):
            if addr in i2c.scan():
                return addr
        raise RuntimeError("QMI8658C not found on I2C bus")

    def _write(self, reg, value):
        self.i2c.writeto_mem(self.address, reg, bytes([value]))

    def read_accel_g(self):
        """Acceleration on (x, y, z) in units of g."""
        raw = self.i2c.readfrom_mem(self.address, _ACCEL_OUT, 6)
        x, y, z = unpack("<hhh", raw)
        return (x / _ACCEL_SCALE, y / _ACCEL_SCALE, z / _ACCEL_SCALE)

    def read_gyro_dps(self):
        """Angular velocity on (x, y, z) in degrees/second."""
        raw = self.i2c.readfrom_mem(self.address, _GYRO_OUT, 6)
        x, y, z = unpack("<hhh", raw)
        return (x / _GYRO_SCALE, y / _GYRO_SCALE, z / _GYRO_SCALE)
