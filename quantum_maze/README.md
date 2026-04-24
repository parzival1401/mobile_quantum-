# Quantum Maze

A playable puzzle game that uses a maze as a metaphor for quantum mechanics.

## Install

```bash
pip install -r requirements.txt
python main.py
```

## Controls

| Key | Action |
|-----|--------|
| WASD / Arrow keys | Move one cell |
| Mouse | Aim the observation ray |
| SPACE / click button | Quantum Jump to ray endpoint |
| Drag slider | Collapse the maze to a new configuration |
| R | Restart |
| ESC | Quit |

## Quantum metaphors

**Fog of war** represents a quantum system before measurement — the maze
layout beyond the player's immediate vicinity is unknown (superposed).

**The observation ray** is the act of measurement: pointing at a path
collapses its state into something definite, revealing cells along the ray.

**Quantum Jump** maps to quantum tunnelling — the player leaps to the far
end of the observed ray instantly, bypassing the intervening cells.

**Maze collapse** (slider) represents a wavefunction collapse: dragging the
Observation Level slider forces the entire maze to re-collapse into a new
random configuration. Each collapse increments the score penalty, rewarding
players who navigate with fewer observations.

## Scoring

`Score = elapsed seconds + (collapse count × 5 s penalty)` — lower is better.
