# Quantum Dance — User Guide

**File:** `quantum_optimized.py` (the Raspberry-Pi-tuned build — use this one)

Quantum Dance is a Dance-Dance-Revolution–style rhythm game built for a
summer-camp / science-exhibition setting. It teaches the difference between
**classical** and **quantum** computing through gameplay:

- **Classical notes** fall in a single fixed lane — you always know where to step.
- **Quantum notes** exist in **two lanes at once** (superposition) and only
  *collapse* into one real lane shortly before they reach the hit zone
  (measurement). In 2-player mode the two screens collapse to **opposite**
  lanes — they are entangled.

---

## 1. How to Play

1. The game boots straight into the **main menu** (rainbow "QUANTUM DANCE" title).
2. Choose **1 Player** or **2 Players**.
3. Pick a song from the list — the highlighted song plays a short preview.
4. Arrows fall from the top. Step on / press the matching arrow when it reaches
   the **hit zone** (the glowing receptors near the bottom).
5. Timing is graded **PERFECT**, **GOOD**, or **MISS**. Combos build a score.
6. The song fades out and a **results screen** shows stars + stats.

There is **no fail state** — kids can never "lose", they just get a star rating.

---

## 2. Controls

### Dance Mats (primary input)

Both mats use the same buttons; the only difference is which one is Player 1
vs Player 2 (decided by USB plug order at boot).

| Screen        | Arrows (Up/Down/Left/Right)         | START            | SELECT            |
|---------------|-------------------------------------|------------------|-------------------|
| Main menu     | Toggle 1P ↔ 2P                      | Go to song list  | *(nothing)*       |
| Song select   | Up/Down = move list, ◄►= high scores| Play song        | Back to menu      |
| **Gameplay**  | **Step the falling arrows**         | —                | Exit to menu      |
| Name entry    | Up/Down = change letter, ◄►= move   | Next / confirm   | Confirm name      |
| Results       | —                                   | Play again       | Back to menu      |
| Leaderboard   | —                                   | —                | Back to song list |

### Keyboard (for testing without mats)

| Action            | Player 1      | Player 2   |
|-------------------|---------------|------------|
| Lanes (L/D/U/R)   | ← ↓ ↑ →       | A S W D    |
| Menu navigate     | Arrow keys    | —          |
| Confirm           | Enter / Space | —          |
| Back / Exit       | Esc           | —          |
| Type name (entry) | Letters + Enter | —        |
| View high scores  | Tab (in song select) | —   |
| Nudge BIAS slider | `[` and `]`   | —          |
| Reset BIAS to 50% | `\`           | —          |

---

## 2b. High-Score Leaderboard

Each song keeps its own **Top 5** list, saved to `leaderboard.json` in this
folder (survives reboots; shared between the portrait and landscape builds).

- **After a song**, if a player's score makes that song's Top 5, a
  **NEW HIGH SCORE** screen appears to enter a name:
  - **On a mat:** scroll each of 3 letters with Up/Down, move with ◄►/START,
    SELECT confirms (classic arcade initials).
  - **On a keyboard:** just type a name (up to 10 letters) and press Enter.
- In **2-player** mode each player is checked separately — both can make the
  same song's board. Player 1 enters first, then Player 2.
- The results screen and the **high-scores view** both show the Top 5 with the
  newest entry highlighted in gold.
- **View a song's scores without playing:** in the song-select screen press
  **◄ or ►** on a mat (or **Tab** on a keyboard).

### Resetting the leaderboard (between exhibition days)

On the **main menu**, press **Shift + Delete** to wipe all high scores.
(Or just delete the `leaderboard.json` file while the game is closed.)

---

## 3. Adding or Changing Songs

All songs live in one list called `SONGS` near the top of `quantum_optimized.py`
(search for `SONGS = [`). Each entry looks like this:

```python
{"title": "Faded", "artist": "Alan Walker",
 "file": "music/Alan Walker - Faded.mp3",
 "bpm": 90, "offset": 0.0, "difficulty": "Easy", "duration": 120},
```

### Steps to add a new song

1. **Copy the MP3** into the `dance_dance/music/` folder.
2. **Add a new entry** to the `SONGS` list with these fields:

| Field        | What it means                                                            |
|--------------|--------------------------------------------------------------------------|
| `title`      | Shown in the song list.                                                   |
| `artist`     | Shown under the title.                                                    |
| `file`       | Path **relative to the `dance_dance/` folder** — `"music/yourfile.mp3"`.  |
| `bpm`        | Beats per minute of the song. This drives note timing — **get it right.** |
| `offset`     | Seconds to skip at the start before notes begin (use if there's silence/intro). |
| `difficulty` | `"Easy"`, `"Hard"`, or `"Extreme"` — controls fall speed (see below).     |
| `duration`   | How many seconds the round lasts before fading out and ending.            |

3. Save the file and restart the game. The new song appears automatically.

### Finding the BPM

Use any "BPM finder" website/app, or tap along to the beat. If the BPM is wrong,
the arrows will drift out of sync with the music. The `offset` lets you nudge
where the first note lands if the song has an intro.

### Difficulty → speed

`DIFF_SPEED = {"Easy": 1.0, "Hard": 1.5, "Extreme": 2.0}` — higher numbers make
notes fall faster (less reaction time). Match difficulty to the song's energy:
fast songs → Hard/Extreme, slow songs → Easy.

---

## 4. Tuning the Gameplay

These constants are at the very top of `quantum_optimized.py` and affect **every**
song equally (they are independent of BPM and difficulty):

| Constant             | Default | Effect                                                                 |
|----------------------|---------|------------------------------------------------------------------------|
| `BEATS_PER_NOTE`     | `2`     | Spawn a note every N beats. Lower = more notes. **Must be a whole number.** |
| `BEATS_TO_FALL`      | `5`     | How many beats a note takes to fall. Higher = slower / more reaction time. |
| `COLLAPSE_THRESHOLD` | `1`     | How far above the hit zone quantum notes collapse. Higher = earlier warning. |

Other handy knobs:

| Constant          | Where                  | Effect                                       |
|-------------------|------------------------|----------------------------------------------|
| `PREVIEW_START_S` | preview section        | Where in the song the song-list preview starts (seconds). |
| `PREVIEW_VOLUME`  | preview section        | Loudness of the preview (0.0–1.0).           |
| `_PARTICLE_MAX`   | particle section       | Max particles per player (keep low on Pi).   |
| `_LOW_PERF`       | screen & timing section| `True` on Raspberry Pi (30 FPS, fewer effects). Set `False` on a desktop for full visuals. |

---

## 5. Display & Audio Notes

- **Resolution:** the game runs at **768 × 1024 (portrait)**, designed for a
  1024 × 768 monitor rotated 90°.
- **Two screens:** in 2-player mode the second monitor shows Player 2's lanes.
  When idle / 1-player, the second monitor shows the Quantum Dance logo.
  The **left** screen is always Player 1 regardless of cable order.
- **Audio:** routed through ALSA's `default` device (configured in
  `/etc/asound.conf` on the Pi) so sound comes out of the HDMI screen speakers.
- **Music vs sound effects:** the song plays through pygame's music streamer;
  hit/miss/collapse effects are short generated tones. There is intentionally
  **no sound on PERFECT/GOOD hits** so they don't clash with the music.

---

## 6. Running the Game

On the Raspberry Pi the game **auto-starts on boot**. To run it manually:

```bash
cd ~/mobile_quantum-/dance_dance
python quantum_optimized.py
```

To stop it: press **SELECT** on a mat during a game, then **SELECT** again to
exit, or press **Esc** on a keyboard.

---

*For developer / debugging details, see `CONTEXT.md` in this same folder.*
