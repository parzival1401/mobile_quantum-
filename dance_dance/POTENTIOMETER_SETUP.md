# Potentiometer → COLLAPSE bar (Raspberry Pi 4)

A physical knob moves the quantum **COLLAPSE line** (the bar on the left of each
screen). It works in 1P and 2P and in every song. The `+` / `-` keys and mouse
still work, but turning the knob takes control back.

```
knob ─► pot_input.py (RC timing or ADS1115) ─► pot_reader.py ─► UDP 127.0.0.1:50555 ─► game
```

| File                   | Role                                                                 |
|------------------------|----------------------------------------------------------------------|
| `pot_input.py`         | Reader module. Every backend exposes `read() -> 0.0..1.0`.           |
| `pot_reader.py`        | Main script: `--test`, `--calibrate`, or streams values to the game. |
| `pot_config.json`      | Created by `--calibrate` (not in git). Holds the backend and knob ends. |
| `requirements-pot.txt` | Python packages for the Pi.                                          |

The game starts `pot_reader.py` **automatically on Linux once `pot_config.json`
exists**, so no autostart changes are needed. Without that file, the knob reader
doesn't run and the game behaves exactly as before.

---

## 1. Wiring: RC timing (default, no ADC chip)

The Pi 4 has no analog input. Instead, the reader times how long a capacitor
takes to charge through the potentiometer: more resistance means a longer time.

**3.3 V only. Never connect 5 V to a GPIO pin.**

```
 3.3V (pin 1) ── 1 kΩ ── pot outer pin            (other outer pin: not connected)
                         pot wiper ──┬── GPIO18 (pin 12)
                                     │
                                   1 µF
                                     │
                                 GND (pin 6)
```

- Pot: 10 kΩ **linear** (B10K).
- The **1 kΩ resistor is required**. It limits the current when the Pi pulls the
  pin LOW to empty the capacitor.
- For an electrolytic capacitor, connect its **− stripe to GND**.
- Expected charge times are about **0.7 ms at one end and 7 ms at the other**.

## 2. Wiring: ADS1115 (optional, smoother)

| ADS1115 | Pi                    |
|---------|-----------------------|
| VDD     | 3.3 V (pin 1)         |
| GND     | GND (pin 6)           |
| SCL     | GPIO3 / SCL (pin 5)   |
| SDA     | GPIO2 / SDA (pin 3)   |
| A0      | pot wiper             |

Pot outer pins go to 3.3 V and GND. Enable I2C once (`sudo raspi-config` →
Interface Options → I2C), then set `"backend": "ads1115"` in `pot_config.json`
or pass `--backend ads1115` when calibrating.

## 3. Install (on the Pi)

```bash
cd /home/quantummobile/mobile_quantum-/dance_dance
../.venv/bin/pip install -r requirements-pot.txt
```

If `RPi.GPIO` won't install or import on Trixie, run
`../.venv/bin/pip install rpi-lgpio` instead (it's a drop-in replacement with
the same `import RPi.GPIO`). The user needs to be in the `gpio` group, which it
is by default on Raspberry Pi OS.

## 4. Test and calibrate (game **not** running: it would hold the pin)

```bash
../.venv/bin/python pot_reader.py --test        # raw time + 0..1 bar; turn the knob
../.venv/bin/python pot_reader.py --calibrate   # LOW end, Enter, HIGH end, Enter
```

- In `--test`, the **raw** value must change smoothly as you turn the knob. If it
  stays flat or shows `no reading`, **stop and check the wiring**: wrong pin, a
  missing capacitor, or a loose wiper.
- `--calibrate` prints the median and spread of each end, then saves
  `pot_config.json`. It refuses to save if both ends read the same.
- Recalibrate after changing the capacitor, the pot or the backend.
- Wrong pin? Use `--gpio N` (a BCM number) with both commands.

Then restart the game. Turning the knob should move the COLLAPSE line on both
screens.

## 5. Testing without hardware (any computer)

```bash
python pot_reader.py --backend fake     # in one terminal: sweeps the bar up/down
python quantum_optimized.py             # in another: the bar follows
```

## Tuning

| Setting          | Where              | Effect                                                       |
|------------------|--------------------|--------------------------------------------------------------|
| `POT_ENABLED`    | game, top section  | `False` turns the knob off completely                        |
| `POT_DEADBAND`   | game               | How far the knob must turn to take control back from keys/mouse (default 2 %) |
| `RATE_HZ`        | `pot_reader.py`    | Readings per second (20)                                     |
| `SMOOTHING`      | `pot_reader.py`    | Lower = steadier but slower line                             |
| `samples`        | `pot_config.json`  | Raw samples per reading (median of 3)                        |

## Troubleshooting

| Symptom                                  | Check                                                              |
|------------------------------------------|--------------------------------------------------------------------|
| Bar doesn't move                         | Does `pot_config.json` exist? Are you on Linux? Does `--test` work with the game closed? |
| `RPi.GPIO is missing`                    | Install into the **venv** the game runs with (section 3)           |
| Line jitters                             | Lower `SMOOTHING`, raise `samples`, or use a film/ceramic capacitor |
| Knob works backwards                     | Recalibrate, turning to the ends the prompts ask for               |
| `no reading` / always times out          | Capacitor not to GND, wiper not on GPIO18, or a wrong `--gpio`     |
