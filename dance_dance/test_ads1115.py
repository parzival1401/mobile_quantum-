#!/usr/bin/env python3
"""
test_ads1115.py  -  Quick check that the ADS1115 + potentiometer work on the Pi.

Wiring on the Pi 4's I2C6 bus (pins 1-6 are taken by the fan).
ADS1115 VDD on 3.3 V, never 5 V:
    ADS1115 VDD  -> Pi pin 17 (3.3 V)
    ADS1115 GND  -> Pi pin 14 (GND)
    ADS1115 SDA  -> Pi pin 15 (GPIO22 / I2C6 SDA)
    ADS1115 SCL  -> Pi pin 16 (GPIO23 / I2C6 SCL)
    ADS1115 ADDR -> GND       (address 0x48)
    ADS1115 A0   -> pot middle pin (wiper)
    Pot outer pins -> ADS1115 VDD and GND (same 3.3 V / GND)

Enable I2C6 once: add this line to /boot/firmware/config.txt, then reboot
    dtoverlay=i2c6

Run:
    ls /dev/i2c-*              # should list /dev/i2c-6
    i2cdetect -y 6             # should show 48
    pip install smbus2
    python3 test_ads1115.py    # turn the knob; Ctrl+C to stop
    python3 test_ads1115.py 1  # (bus 1 instead, if wired to pins 3/5)
"""
import sys
import time

from smbus2 import SMBus

I2C_BUS = int(sys.argv[1]) if len(sys.argv) > 1 else 6
ADDR = 0x48
CHANNEL = 0          # A0
FSR = 4.096          # +/-4.096 V full-scale range (fits 3.3 V)
VREF = 3.3           # pot supply voltage, for the 0-100 % bar

# Config: start single-shot | input AINx vs GND | gain +/-4.096 V | single-shot
#         mode | 128 samples/s | comparator off
CONFIG = (0x8000 | ((4 + CHANNEL) << 12) | 0x0200 | 0x0100 | 0x0080 | 0x0003)


def read_raw(bus):
    bus.write_i2c_block_data(ADDR, 0x01, [CONFIG >> 8, CONFIG & 0xFF])
    time.sleep(0.009)                         # one conversion at 128 SPS
    hi, lo = bus.read_i2c_block_data(ADDR, 0x00, 2)
    val = (hi << 8) | lo
    return val - 0x10000 if val & 0x8000 else val


def main():
    with SMBus(I2C_BUS) as bus:
        print(f"Reading ADS1115 on i2c-{I2C_BUS} @0x{ADDR:02X} channel A{CHANNEL}. Turn the knob (Ctrl+C to stop).")
        while True:
            raw = read_raw(bus)
            volts = raw * FSR / 32768
            pct = max(0.0, min(1.0, volts / VREF))
            bar = "#" * int(pct * 40)
            print(f"\rraw {raw:6d}  {volts:5.3f} V  [{bar:<40}] {pct*100:5.1f}%", end="", flush=True)
            time.sleep(0.05)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nbye")
    except OSError as e:
        print(f"\nI2C error: {e}\nCheck wiring, that dtoverlay=i2c6 is in config.txt, "
              f"and that `i2cdetect -y {I2C_BUS}` shows 48.")
