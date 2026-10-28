#!/usr/bin/env python3
"""
pot_reader.py  -  Potentiometer -> COLLAPSE bar for Quantum Dance (Raspberry Pi)
================================================================================
Reads the knob (via pot_input.py) and streams its position, 0.0 .. 1.0, to the
game over UDP 127.0.0.1:50555. The game moves the shared COLLAPSE line on both
screens. Wiring and setup: POTENTIOMETER_SETUP.md.

It runs as its own process (the game starts it once pot_config.json exists),
with the blocking pot reads on a background thread, so a slow RC read can
never stall the game's frame loop.

Usage (from the dance_dance/ folder, game NOT running)
-----
  python pot_reader.py --test          live readings: check the wiring
  python pot_reader.py --calibrate     record both knob ends -> pot_config.json
  python pot_reader.py                 stream to the game
Options: --backend rc|ads1115|fake   --gpio N   --channel N   --port N
"""

import argparse
import os
import socket
import statistics
import sys
import threading
import time

from pot_input import load_config, make_pot, save_config

RATE_HZ     = 20      # readings per second
SMOOTHING   = 0.35    # EMA weight of a new reading (lower = smoother, slower)
MIN_CHANGE  = 0.004   # deadband: don't resend changes smaller than 0.4 %
KEEPALIVE_S = 1.0     # resend anyway this often (a restarted game catches up)


class PotThread(threading.Thread):
    """Calls pot.read() in the background; `latest` holds the newest value."""

    def __init__(self, pot):
        super().__init__(daemon=True)
        self.pot    = pot
        self.latest = None
        self.misses = 0

    def run(self):
        period = 1.0 / RATE_HZ
        while True:
            t0 = time.monotonic()
            v  = self.pot.read()
            if v is None:
                self.misses += 1
                if self.misses == 20:
                    print("[pot] no readings - check the wiring (POTENTIOMETER_SETUP.md)")
                time.sleep(2.0 if self.misses >= 20 else period)   # back off: saves CPU
                continue
            self.misses = 0
            self.latest = v
            time.sleep(max(0.0, period - (time.monotonic() - t0)))


def run_stream(pot, port):
    if not pot.calibrated:
        print("[pot] not calibrated - auto-ranging; turn the knob end to end once. "
              "Run --calibrate for a fixed range.")
    sock      = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    reader    = PotThread(pot)
    reader.start()
    smooth    = None
    last_sent = None
    last_time = 0.0
    parent    = os.getppid()
    print(f"[pot] {type(pot).__name__} -> udp 127.0.0.1:{port}")
    while os.getppid() == parent:          # exit when the game (our parent) exits
        time.sleep(1.0 / RATE_HZ)
        v = reader.latest
        if v is None:
            continue
        smooth = v if smooth is None else smooth + SMOOTHING * (v - smooth)
        now    = time.monotonic()
        if (last_sent is None or abs(smooth - last_sent) >= MIN_CHANGE
                or now - last_time >= KEEPALIVE_S):
            sock.sendto(f"{smooth:.4f}".encode(), ("127.0.0.1", port))
            last_sent, last_time = smooth, now


def run_test(pot):
    print(f"[pot] {type(pot).__name__} - turn the knob; Ctrl+C to stop")
    if not pot.calibrated:
        print("      (not calibrated: the 0..1 value auto-ranges as you turn it)")
    try:
        while True:
            raw = pot.read_raw()
            v   = pot.read()
            if raw is None or v is None:
                print("  raw:   ----   no reading (open circuit / wrong pin?)      ", end="\r")
            else:
                print(f"  raw: {raw:9.1f}   value: {v:5.3f}  |{'#' * int(v * 40):<40}|", end="\r")
            time.sleep(0.05)
    except KeyboardInterrupt:
        print()


def run_calibrate(pot, cfg):
    def measure_end(prompt):
        input(prompt)
        vals = [v for v in (pot.read_raw() for _ in range(40)) if v is not None]
        if len(vals) < 20:
            sys.exit("No readings - check the wiring before calibrating.")
        print(f"   median {statistics.median(vals):.1f}   "
              f"(spread {min(vals):.1f} .. {max(vals):.1f})")
        return statistics.median(vals)

    print(f"Calibrating ({cfg['backend']}).")
    lo = measure_end("1) Turn the knob fully to the LOW end "
                     "(collapse line near the hit zone), then press Enter... ")
    hi = measure_end("2) Turn the knob fully to the HIGH end "
                     "(collapse line near the top), then press Enter... ")
    if abs(hi - lo) < 0.05 * max(abs(hi), abs(lo), 1.0):
        sys.exit(f"STOP: both ends read almost the same ({lo:.1f} vs {hi:.1f}) - "
                 "the knob is not changing the reading. Check the wiring.")
    cfg["raw_min"], cfg["raw_max"] = lo, hi
    save_config(cfg)
    print(f"Saved pot_config.json  (low end {lo:.1f}, high end {hi:.1f}).")
    print("The game will now start the knob reader automatically.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test",      action="store_true", help="print live readings")
    ap.add_argument("--calibrate", action="store_true", help="record both knob ends")
    ap.add_argument("--backend",   choices=["rc", "ads1115", "fake"])
    ap.add_argument("--gpio",      type=int, help="BCM pin for rc (default 18)")
    ap.add_argument("--channel",   type=int, help="ADS1115 input 0..3")
    ap.add_argument("--port",      type=int, default=50555, help="game UDP port")
    args = ap.parse_args()

    cfg = load_config({"backend": args.backend, "gpio": args.gpio, "channel": args.channel})
    try:
        pot = make_pot(cfg)
    except RuntimeError as e:
        sys.exit(f"[pot] {e}")
    try:
        if args.calibrate:
            run_calibrate(pot, cfg)
        elif args.test:
            run_test(pot)
        else:
            run_stream(pot, args.port)
    except KeyboardInterrupt:
        pass
    finally:
        pot.close()


if __name__ == "__main__":
    main()
