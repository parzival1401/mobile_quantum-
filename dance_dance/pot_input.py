"""
pot_input.py  -  Swappable potentiometer readers for Quantum Dance
==================================================================
Every reader has the same small interface:

    pot = make_pot(cfg)        # cfg["backend"] picks the implementation
    pot.read()      -> 0.0 .. 1.0, or None if there is no reading
    pot.read_raw()  -> the raw measurement (used by calibration)
    pot.close()

Implementations
---------------
  rc       RC timing, no ADC chip (default). Measures how long the capacitor
           takes to charge through the pot. Uses RPi.GPIO (Pi 4).
  ads1115  ADS1115 16-bit ADC on I2C (pot wired as a voltage divider).
  fake     No hardware: a slow sweep, for testing on any computer.

Wiring for rc (3.3 V ONLY - never 5 V on a GPIO pin):

    3.3V (pin 1) --- 1k --- pot outer pin      (other outer pin: unconnected)
                            pot wiper ---+--- GPIO18 (pin 12)
                                         |
                                       1 uF
                                         |
                                     GND (pin 6)
"""

import json
import os
import statistics
import time

HERE        = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "pot_config.json")

DEFAULTS = {
    "backend":     "rc",   # rc | ads1115 | fake
    "gpio":        18,     # BCM number (physical pin 12) - rc
    "channel":     0,      # ADS1115 input A0..A3 - ads1115
    "i2c_bus":     1,
    "ads_address": 0x48,
    "samples":     3,      # raw samples per read() (median)
    "raw_min":     None,   # raw value at the LOW end  (line near hit zone)
    "raw_max":     None,   # raw value at the HIGH end (line near top)
}


def load_config(overrides=None) -> dict:
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            cfg.update(json.load(f))
    for k, v in (overrides or {}).items():
        if v is not None:
            cfg[k] = v
    return cfg


def save_config(cfg: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# Interface
# ─────────────────────────────────────────────────────────────────────────────
class PotReader:
    """read() maps the median raw sample onto 0..1 with the calibrated ends.
    Works whichever way the knob is wired. Before calibration it auto-ranges
    on the smallest/largest raw value seen so far."""

    def __init__(self, cfg):
        self.samples = max(1, int(cfg["samples"]))
        self.lo, self.hi = cfg["raw_min"], cfg["raw_max"]
        self.calibrated = not (self.lo is None or self.hi is None or self.lo == self.hi)

    def read_raw(self):
        raise NotImplementedError

    def read(self):
        vals = [v for v in (self.read_raw() for _ in range(self.samples)) if v is not None]
        if not vals:
            return None
        raw = statistics.median(vals)
        if not self.calibrated:
            self.lo = raw if self.lo is None else min(self.lo, raw)
            self.hi = raw if self.hi is None else max(self.hi, raw)
            if self.hi - self.lo < 1e-9:
                return 0.5
        return max(0.0, min(1.0, (raw - self.lo) / (self.hi - self.lo)))

    def close(self):
        pass


# ─────────────────────────────────────────────────────────────────────────────
# RC timing (no ADC) - RPi.GPIO
# ─────────────────────────────────────────────────────────────────────────────
class RCTimingPot(PotReader):
    """Drain the capacitor (pin LOW), switch the pin to input, and time how
    long it takes to read HIGH. Raw value = charge time in microseconds.
    With 1k + 10k pot + 1 uF that is roughly 0.7 ms .. 7.5 ms."""

    DRAIN_S   = 0.003   # pin LOW this long empties the capacitor
    TIMEOUT_S = 0.05    # still LOW after this -> open circuit / wrong pin

    def __init__(self, cfg):
        super().__init__(cfg)
        try:
            import RPi.GPIO as GPIO
        except ImportError as e:
            raise RuntimeError("RPi.GPIO is missing - see POTENTIOMETER_SETUP.md "
                               "(pip install RPi.GPIO  or  pip install rpi-lgpio)") from e
        self.GPIO = GPIO
        self.pin  = int(cfg["gpio"])
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

    def read_raw(self):
        GPIO, pin = self.GPIO, self.pin
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)
        time.sleep(self.DRAIN_S)
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_OFF)
        t0 = time.perf_counter()
        while GPIO.input(pin) == GPIO.LOW:
            if time.perf_counter() - t0 > self.TIMEOUT_S:
                return None
        return (time.perf_counter() - t0) * 1e6

    def close(self):
        self.GPIO.cleanup(self.pin)


# ─────────────────────────────────────────────────────────────────────────────
# ADS1115 (I2C ADC) - smbus2
# ─────────────────────────────────────────────────────────────────────────────
class ADS1115Pot(PotReader):
    """Single-shot read of one input vs GND, +/-4.096 V range, 128 SPS.
    Wire the pot as a divider: outer pins to 3.3 V and GND, wiper to A0..A3;
    ADS1115 VDD to 3.3 V so nothing on the Pi side ever sees 5 V."""

    def __init__(self, cfg):
        super().__init__(cfg)
        try:
            from smbus2 import SMBus
        except ImportError as e:
            raise RuntimeError("smbus2 is missing - pip install smbus2") from e
        self.bus  = SMBus(int(cfg["i2c_bus"]))
        self.addr = int(cfg["ads_address"])
        self.cfg  = (0x8000 | ((4 + int(cfg["channel"])) << 12)
                     | 0x0200 | 0x0100 | 0x0080 | 0x0003)

    def read_raw(self):
        self.bus.write_i2c_block_data(self.addr, 0x01, [self.cfg >> 8, self.cfg & 0xFF])
        time.sleep(0.009)                    # one conversion at 128 SPS
        hi, lo = self.bus.read_i2c_block_data(self.addr, 0x00, 2)
        val = (hi << 8) | lo
        return float(val - 0x10000 if val & 0x8000 else val)

    def close(self):
        self.bus.close()


# ─────────────────────────────────────────────────────────────────────────────
# Fake (no hardware)
# ─────────────────────────────────────────────────────────────────────────────
class FakePot(PotReader):
    """A slow up/down sweep over 8 s - for testing the game on any computer."""

    def __init__(self, cfg):
        cfg = dict(cfg)
        if cfg["raw_min"] is None or cfg["raw_max"] is None:
            cfg["raw_min"], cfg["raw_max"] = 0.0, 1000.0
        super().__init__(cfg)

    def read_raw(self):
        t = time.monotonic() % 8.0
        return 1000.0 * (t / 4.0 if t < 4.0 else (8.0 - t) / 4.0)


BACKENDS = {"rc": RCTimingPot, "ads1115": ADS1115Pot, "fake": FakePot}


def make_pot(cfg) -> PotReader:
    try:
        cls = BACKENDS[cfg["backend"]]
    except KeyError:
        raise RuntimeError(f"unknown backend {cfg['backend']!r} "
                           f"(use one of: {', '.join(BACKENDS)})")
    return cls(cfg)
