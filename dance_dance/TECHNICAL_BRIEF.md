# Technical Documentation Brief — Quantum Dance

> **Purpose of this file:** This is a briefing document for a Claude (AI)
> coworker. Use the reference material below to write a formal, polished
> **technical document** explaining the Quantum Dance game (the `dance_dance/`
> project only — ignore `quantum_maze/`). Everything here is accurate to the
> shipped code as of this writing. Expand, reorganize, and add diagrams/prose
> as needed, but do not invent mechanics that contradict the facts below.

---

## 0. Instructions for the AI writer

Produce a technical document with these sections:
1. **Overview & Educational Goal** — what the game is and the quantum concept it teaches.
2. **System Architecture** — files, the game state machine, the render pipeline.
3. **Game Mechanics** — note types, timing, scoring, the quantum collapse, leaderboard.
4. **Hardware & Deployment** — Raspberry Pi, dual screens, dance mats, audio, autostart.
5. **Performance Engineering** — how it was tuned to run on a Pi 4B.
6. **Configuration & Tuning** — the constants an operator can change.

Audience: technically literate (a senior-design committee / new developer).
Tone: clear, precise, professional. Use the exact numbers from this brief.
Reference the two companion docs where relevant: `USER_GUIDE.md` (operators)
and `CONTEXT.md` (debugging). Where a claim is code-specific, keep it faithful.

---

## 1. What the project is

**Quantum Dance** is a Dance-Dance-Revolution–style rhythm game built for a
science-exhibition / summer-camp setting. Players step on arrows (on a dance
mat) in time with music. Its educational hook is a live demonstration of a
**quantum superposition → measurement (collapse)** using special "quantum notes."

- Single Python file per build, ~2,450 lines, using **pygame-ce** and **numpy**.
- Built to run on a **Raspberry Pi 4B** driving **two vertical HDMI screens**
  with **two USB dance mats**.
- Kid-friendly: **no fail state**; results are a 1–5 star rating.

### Files in `dance_dance/`
| File | Role |
|------|------|
| `quantum_optimized.py` | **Active build** — portrait 768×1024, Pi-optimized. |
| `dance_optimized_horizontal.py` | Landscape 1024×768 variant. Byte-for-byte identical to the portrait build except `SW,SH` and the docstring. |
| `quantum_dance.py` | Original un-optimized prototype. Kept only as reference — **do not edit**. |
| `music/` | The MP3 song files. |
| `leaderboard.json` | Runtime high-score storage (auto-created, git-ignored). |
| `USER_GUIDE.md` | Operator guide (controls, adding songs, tuning). |
| `CONTEXT.md` | Developer/AI debugging reference (runtime env, gotchas). |

> Both playable builds share all logic; only the screen resolution differs. When
> documenting "the code," describe `quantum_optimized.py`.

---

## 2. System Architecture

### 2.1 Game state machine
A single `main()` loop drives a `GameState` enum:

```
MENU  →  SONG_SELECT  →  PLAYING  →  (NAME_ENTRY)  →  RESULTS  →  back to MENU
                    ↘  LEADERBOARD (view a song's board, then back to SONG_SELECT)
```

- **MENU** — choose 1 or 2 players (mat Up/Down toggles, START confirms).
- **SONG_SELECT** — pick a track; the highlighted song plays a live preview
  (`pygame.mixer.music.play(start=30s)` at reduced volume). LEFT/RIGHT (or Tab)
  opens the **LEADERBOARD** view for that song.
- **PLAYING** — the actual rhythm game.
- **NAME_ENTRY** — only if a player's score cracks the song's Top-5; arcade
  3-initial reel (mat) or typed name (keyboard).
- **RESULTS** — star rating, stats, and the song's Top-5 board.

### 2.2 Render pipeline
- Main window: `pygame.display.set_mode((SW,SH), DOUBLEBUF, vsync=1)` for
  GPU-accelerated buffer flips.
- Second monitor: a `pygame._sdl2.video.Window` opened at startup, drawn to via
  `Texture.from_surface(...)`. It shows the game logo when idle, becomes Player
  2's screen during 2-player games, and shows each player's own results/name-entry.
- `_render_player(surf, ps, ctx, label)` draws one player's full field onto a
  target surface, so the same code serves the main window, the 2nd window, and
  split-screen subsurfaces.
- A `RenderCtx` dataclass holds per-surface layout (lane width, offsets) so the
  UI scales to a full screen or a 50%-width split half.

### 2.3 Frame-rate-independent timing (critical design rule)
All motion uses **delta-time**, never per-frame constants, so the game behaves
identically at the Pi's 30 FPS and a desktop's 60 FPS:
- `dt = min(clk.tick(...) / 1000.0, 0.05)` (capped to survive lag spikes).
- Note speed is stored as **px/second**; `note.y += speed * dt`.
- The song timer and free-play spawn timer also accumulate in seconds via `dt`.

---

## 3. Game Mechanics

### 3.1 Lanes and note types
- **4 lanes:** index `0=← (left), 1=↓ (down), 2=↑ (up), 3=→ (right)`.
- **Classical note** — falls in ONE fixed lane. Deterministic.
- **Quantum note** — spawns in TWO lanes simultaneously (a superposition),
  drawn as two linked ghost notes with a "?" until it **collapses**.
- On each spawn, there is a **38% chance** the note is quantum, otherwise classical.

### 3.2 The quantum collapse (the educational centerpiece)
- A quantum note travels down still "undecided." At the **collapse line**
  (`COLLAPSE_THRESHOLD` beats above the hit zone) it **collapses** into exactly
  one real lane — mimicking a wavefunction being measured.
- The chosen lane is random, weighted by the **BIAS** slider (`get_collapse_bias`).
- **Entanglement (2-player):** both players share the same note via a common
  `nid` in a `collapsed_outcomes` dict. The first note to reach the line sets the
  shared outcome `(p1_lane, p2_lane)`; the two players collapse to **opposite**
  lanes. This is the visible "entanglement" demo — measuring one determines the other.
- Classical notes for Player 2 are **mirrored** (`_m()`: lane 0↔3, 1↔2) so the
  two screens look like complementary partners.

### 3.3 Timing, spawning, and speed
Constants at the top of the file (independent of song BPM/difficulty):
| Constant | Value | Meaning |
|----------|-------|---------|
| `BEATS_PER_NOTE` | 2 | Spawn a note every N beats. |
| `BEATS_TO_FALL` | 5 | Beats for a note to fall spawn→hit zone (scaled by difficulty). |
| `COLLAPSE_THRESHOLD` | 1 | Beats above the hit zone where quantum notes collapse. |

- Notes spawn **on the beat**, driven by the music position
  (`pygame.mixer.music.get_pos()`); a catch-up loop spawns any beats missed on a
  slow frame so nothing desyncs.
- Per-song difficulty scales fall speed: `DIFF_SPEED = {Easy:1.0, Hard:1.5, Extreme:2.0}`
  (higher = faster fall / less reaction time).

### 3.4 Scoring, judgment, combos
- Hit windows (pixels from the target line): **PERFECT ≤ 22 px**, **GOOD ≤ 46 px**,
  beyond that a **MISS**.
- Score: PERFECT = `300 × max(1, combo//5)`, GOOD = `100 × max(1, combo//10)`.
- **Combo milestones** at `[10, 25, 50, 100, 200]` trigger a banner + sound + a
  screen-flash + particle burst.
- **No fail state.** Missing never ends the game.

### 3.5 Results (star rating)
Accuracy = `(perfect + good) / total_notes`. Stars:
`≥0.90 → 5`, `≥0.70 → 4`, `≥0.50 → 3`, `≥0.30 → 2`, else `1`, each with an
encouraging message.

### 3.6 Leaderboard
- One **Top-5** list per song in `leaderboard.json` (shared by both builds).
- After a song, each qualifying player enters a name; in 2-player mode each is
  checked and entered separately, and each player's results/name-entry appears
  on **their own** screen.
- Reset all boards: **Shift+Delete** on the main menu.

### 3.7 Audio
- Song playback via `pygame.mixer.music`; short generated SFX (numpy sine tones)
  for miss / collapse / milestone / menu navigation.
- PERFECT/GOOD hits intentionally have **no** sound (they clashed with the music).
- An 8-bit menu jingle loops on the menu (procedurally generated).

---

## 4. Hardware & Deployment

> Full runtime detail is in `CONTEXT.md`; summarize it here.

| Item | Value |
|------|-------|
| Compute | Raspberry Pi 4B, Debian Trixie (13), 64-bit |
| Compositor | **labwc** (Wayland/wlroots) — **not X11** |
| Display control | **`wlr-randr`** (xrandr does not work) |
| Screens | 2× HDMI, 1024×768, rotated `--transform 90` → 768×1024 portrait |
| Input | 2× USB dance mats, Vendor `0e8f` Product `0035`, read via `pygame.joystick` |
| Audio | HDMI screen speakers via ALSA `default` (`/etc/asound.conf`); game sets `SDL_AUDIODRIVER=alsa`, `AUDIODEV=default` |

### 4.1 Dance mat mapping
Buttons (confirmed by hardware test):
`DOWN=0, RIGHT=1, LEFT=2, UP=3, SELECT=8, START=9`.
The mats are physically rotated 90° vs the screen, so the button→lane map is
`{UP→lane0(←), LEFT→lane1(↓), RIGHT→lane2(↑), DOWN→lane3(→)}` — see
`_MAT_BTN_TO_LANE`. `event.joy` (0/1) identifies which mat = which player; a
6-frame debounce absorbs the mats' rapid double-events.

### 4.2 Dual-screen logic
- `_get_monitor_x_positions()` reads `wlr-randr` and sorts monitors by X. The
  **leftmost** screen is always Player 1, **rightmost** is Player 2 — plug order
  is irrelevant.
- 2 monitors → each player on their own screen. 1 monitor → 50/50 split fallback.

### 4.3 Autostart (boot → game)
`~/.bash_profile` on tty1 runs `exec labwc`; `~/.config/labwc/autostart` then
hides the cursor, rotates/positions both screens with `wlr-randr`, `cd`s into
`dance_dance/` (so relative `music/...` paths resolve), and launches the game.
**Gotcha:** the `cd` is mandatory — without it every song fails to load.

---

## 5. Performance Engineering (Pi 4B)

The game must hold a steady frame rate on a fill-rate-limited GPU. Techniques:
- `_LOW_PERF = True` → **30 FPS cap**, skips starfields and CRT scanlines.
- **Pre-baked surfaces** built once, blitted per frame: scanlines, animated
  border strips (30-frame cycle), note bodies, arrow glyphs, rainbow title chars,
  and all static text (`_tcache`).
- `get_collapse_y()` computed **once per frame**, not per note.
- **Particles** are hard-capped (40/player), use `__slots__`, plain `draw.circle`,
  no per-particle alpha; bursts shrink in low-perf mode.
- DOUBLEBUF + vsync for GPU buffer flips.
- Rule for future edits: pre-bake anything static; never allocate a Surface
  per-object per-frame (that was the original lag source).

---

## 6. Configuration & Tuning (operator-facing)

All near the top of the file, safe to edit:
| Constant | Effect |
|----------|--------|
| `SONGS` list | Add/edit songs — `title, artist, file, bpm, offset, difficulty, duration`. |
| `BEATS_PER_NOTE` | Note density (whole number). |
| `BEATS_TO_FALL` | Reaction time (higher = slower fall). |
| `COLLAPSE_THRESHOLD` | How early quantum notes collapse. |
| `PREVIEW_START_S`, `PREVIEW_VOLUME` | Song-preview start point and loudness. |
| `_PARTICLE_MAX` | Particle cap. |
| `_LOW_PERF` | `True` on Pi (30 FPS), `False` on desktop (full 60 FPS visuals). |

Adding a song = drop the MP3 in `music/`, add a `SONGS` entry with the correct
BPM, restart. See `USER_GUIDE.md §3` for the field-by-field walkthrough.

---

## 7. Notes for the writer

- The two playable builds are kept in sync; call out that the **only** difference
  is orientation (`SW,SH = 768×1024` portrait vs `1024×768` landscape).
- On-screen text uses **plain ASCII only** — the Pi font lacks glyphs for
  decorative symbols, so those were removed (lane arrows `← ↓ ↑ →` are the
  exception; they render fine).
- If you want exact line numbers or code excerpts, read `quantum_optimized.py`
  directly; they drift as the file changes, so prefer describing by
  function/constant name.
