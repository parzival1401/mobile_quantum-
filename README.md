# Quantum Dance & Quantum Maze
**Quantum Exhibition** — Interactive games for summer camps and science exhibitions.  
Demonstrates Classical vs Quantum Computing concepts through gameplay.

---

## Games

### 🎮 Quantum Dance (`dance_dance/`)
A Dance Dance Revolution-style rhythm game where players hit arrow notes in time with music.

- **Classical notes** — appear in one fixed lane
- **Quantum notes** — exist in two lanes simultaneously and collapse to one before the hit zone (superposition → measurement)
- **1 or 2 players** — dual-display support for exhibition setups
- **Arcade retro aesthetic** — rainbow titles, neon glow, CRT scanlines, star field

### 🌀 Quantum Maze (`quantum_maze/`)
A maze game with quantum mechanics — fog of war, ray-based BFS solver, and wavefunction collapse.

---

## Raspberry Pi 4 Setup

### 1. Update the system
```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Install Python 3 and SDL2 dependencies
```bash
sudo apt install -y python3 python3-pip python3-venv git \
  libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev
```

### 3. Clone the repository
```bash
git clone https://github.com/parzival1401/mobile_quantum-.git
cd mobile_quantum-
```

### 4. Create and activate a virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 5. Install Python packages
```bash
pip install pygame-ce numpy
```

### 6. Run Quantum Dance
```bash
cd dance_dance
python quantum_dance.py
```

### 6b. Run Quantum Maze
```bash
cd quantum_maze
python main.py
```

---

## Controls

### Quantum Dance
| Action | Player 1 | Player 2 |
|---|---|---|
| Lane ← | ← Arrow | A |
| Lane ↓ | ↓ Arrow | S |
| Lane ↑ | ↑ Arrow | W |
| Lane → | → Arrow | D |
| Back to menu | ESC | ESC |

### Quantum Maze
| Action | Key |
|---|---|
| Move | W A S D or Arrow keys |
| Quantum Jump | Space |
| Restart | R |
| Quit | ESC |

---

## 2-Player Display Modes

The game detects your display setup automatically at runtime:

| Setup | Behavior |
|---|---|
| **2 monitors connected** | P2 window opens on the second display (Option A) |
| **1 monitor** | Window splits 50/50 side-by-side (Option B) |
| **Option A fails** | Automatically falls back to split screen |

Connect both monitors **before booting** the Raspberry Pi for dual-display to work.

---

## Raspberry Pi Notes

- Must run in the **desktop environment** (not headless SSH) — pygame requires a display
- If you get `No available video device`, connect a monitor via HDMI before booting
- **Audio**: if sound doesn't work, run `sudo raspi-config` → System Options → Audio → select HDMI or headphone jack
- **Performance**: Raspberry Pi 4 handles the game at 60 FPS without issues
- **Hardware controls**: any USB device that emulates a keyboard (arcade buttons, dance pads, custom matrices) works plug-and-play — map buttons to the arrow keys and WASD

---

## Song List

| # | Title | Artist | BPM | Difficulty | Duration |
|---|---|---|---|---|---|
| 1 | Faded | Alan Walker | 90 | Easy | 120s |
| 2 | Alone | Alan Walker | 150 | Hard | 90s |
| 3 | Bad Guy | Billie Eilish | 135 | Hard | 100s |
| 4 | Dynamite | BTS | 114 | Easy | 110s |
| 5 | Can't Stop the Feeling | Justin Timberlake | 113 | Easy | 120s |
| 6 | Party Rock Anthem | LMFAO | 130 | Extreme | 90s |

Songs fade out smoothly over the last 10 seconds and end automatically — no need to edit audio files.

---

## Requirements

- Python 3.10+
- `pygame-ce >= 2.5`
- `numpy`
- SDL2 (installed via apt on Raspberry Pi / Linux)
