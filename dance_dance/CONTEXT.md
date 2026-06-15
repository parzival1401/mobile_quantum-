# Quantum Dance — AI / Developer Context

> Purpose: give an AI agent (or a new developer) enough context to debug and
> extend **`quantum_optimized.py`** without re-reading the whole 2000-line file.
> This is the **active, production** build. `quantum_dance.py` is the older
> unoptimized original kept only as a fallback — **do not edit it**; all work
> happens in `quantum_optimized.py`.

---

## 1. What this program is

A single-file pygame (pygame-ce) rhythm game (DDR-style) for a science-camp
exhibition, running on a **Raspberry Pi 4B** with two HDMI screens and two USB
dance mats. Teaches classical vs quantum computing:

- **Classical note** → one fixed lane.
- **Quantum note** → spawned in two lanes (superposition); collapses to one
  lane before the hit zone. In 2P the two players' screens are **entangled** and
  collapse to **opposite** lanes (shared `nid` in `collapsed_outcomes`).

There is **no fail state** (kid-friendly). Star-rating results screen only.

---

## 2. Runtime environment (the part that breaks most)

| Thing            | Value                                                                 |
|------------------|-----------------------------------------------------------------------|
| Hardware         | Raspberry Pi 4B, Debian Trixie (13), 64-bit                           |
| Compositor       | **labwc** (Wayland / wlroots). **NOT X11.**                           |
| Display tool     | **`wlr-randr`** — `xrandr` does NOT work here                         |
| Screens          | HDMI-A-1 + HDMI-A-2, both 1024×768, rotated `--transform 90` → 768×1024 portrait |
| Audio cards      | card0 = headphones, card1 = `vc4-hdmi-0`, card2 = `vc4-hdmi-1`        |
| Audio routing    | `/etc/asound.conf` maps `default` → HDMI; game sets `SDL_AUDIODRIVER=alsa`, `AUDIODEV=default` |
| Python           | venv at `/home/quantummobile/mobile_quantum-/.venv`                   |
| User / home      | `quantummobile` / `/home/quantummobile/mobile_quantum-/`             |
| Game resolution  | `SW, SH = 768, 1024` (portrait, matches rotated screen)              |
| Frame rate       | `_LOW_PERF = True` → capped at **30 FPS** on the Pi                   |

### Autostart chain (boot → game)
1. `~/.bash_profile` on tty1 runs `exec labwc`.
2. `~/.config/labwc/autostart`:
   - hides cursor (`unclutter-xfixes`)
   - rotates both screens: `wlr-randr --output HDMI-A-1 --mode 1024x768 --transform 90 --pos 0,0 --output HDMI-A-2 ... --pos 768,0`
   - `cd`s into `dance_dance/` (so relative `music/...` paths resolve) and launches `quantum_optimized.py`.

**Critical gotcha:** the game uses **relative** paths (`music/...`). Autostart
MUST `cd` into `dance_dance/` first or every song fails to load with
"No file ... in working directory '/home/quantummobile'". This is logged to
`/tmp/audio_debug.txt`.

---

## 3. Frame-rate-independent timing (do not regress this)

The single most important architectural rule: **all motion uses delta-time
(`dt`), never per-frame constants.** The Pi runs at 30 FPS, the Mac at 60 —
the game must behave identically.

- `dt = min(clk.tick(...) / 1000.0, 0.05)` in `main()` (capped to avoid spiral).
- `_bpm_fall_speed()` returns **px/second** (NOT px/frame).
- `Note.update(..., dt)` moves `self.y += self.speed * dt`.
- `_game_elapsed += dt` (fallback song timer).
- Free-mode `spawn_timer` is in **seconds**, decremented by `dt`.

If notes ever fall at "half speed on the Pi", someone reintroduced a
divide-by-`FPS` somewhere. That was the original bug.

---

## 3b. Leaderboard

- Stored in `leaderboard.json` (same folder as the script, via `__file__`).
  Both the portrait and landscape builds share this one file.
- Shape: `{ song_title: [ {"name": str, "score": int}, ... up to 5 ] }`.
- Helpers: `_load_leaderboard`, `_save_leaderboard`, `_board_for`,
  `_qualifies`, `_add_score`. All in the leaderboard section near the top.
- States added: `GameState.NAME_ENTRY` (arcade 3-initial OR keyboard typing)
  and `GameState.LEADERBOARD` (view a song's board from song select).
- Flow: song ends → grace timer → build a queue of qualifying players
  (`_begin_name_entry`) → NAME_ENTRY per player (`_commit_name_entry` advances
  the queue) → RESULTS (which also renders the Top-5 via `_draw_board_list`).
- 2P: each player checked separately; P1 enters first, then P2.
- Reset: Shift+Delete on the menu calls `_leaderboard.clear()` + save.
- Module-level entry state: `_entry_queue`, `_entry_initials`, `_entry_pos`,
  `_entry_typed`, `_entry_label`, `_entry_score`, `_leader_view_idx`. Functions
  that mutate these by reassignment declare them `global` (see `main()`).

---

## 4. Key functions (line numbers approximate — search by name)

| Symbol                     | Role                                                            |
|----------------------------|----------------------------------------------------------------|
| `main()`                   | Event loop + state machine (MENU / SONG_SELECT / PLAYING / RESULTS). Computes `dt`, reads `music_pos_ms` once/frame. |
| `update(dt, music_pos_ms)` | Per-frame logic: spawns notes on beat (catches up missed beats), updates both players. |
| `spawn_note()`             | 38% chance quantum (2 lanes, shared `nid`), else classical. P2 classical lanes are mirrored via `_m()`. |
| `Note.update(...,dt,collapse_y)` | Moves note, handles collapse, marks missed. `collapse_y` passed in (computed once/frame). |
| `PlayerState.handle_key()` | Hit detection (PERFECT/GOOD/MISS), scoring, combos, particle bursts. |
| `PlayerState.update()`     | Note/particle/float lifecycle, milestone & flash timers.       |
| `start_game()`             | Sets song, builds `PlayerState`s, picks display mode, starts music. Reuses logo window as P2 window in 2P. |
| `stop_game()`              | Back to menu. Does **not** destroy the logo window.            |
| `_render_player()`         | Draws one player's full screen onto a surface.                 |
| `draw_menu / draw_song_select / draw_results` | The non-gameplay screens.                   |
| `_open_logo_window()`      | Opens the persistent 2nd-monitor window at startup. Positions main window left, logo window right (via `wlr-randr` X offsets). |
| `_present_logo()`          | Blits the logo screen to the 2nd window (when not in 2P game). |
| `_start_preview / _stop_preview` | Song-list audio preview via `pygame.mixer.music.play(start=30)`. |
| `_get_monitor_x_positions()` | Returns sorted monitor X offsets. Left=P1, right=P2 — **plug-order independent.** |

---

## 5. Input mapping (mats are physically rotated 90°)

Dance mats: Vendor `0e8f`, Product `0035`. Buttons (confirmed by hardware test):

```
MAT_DOWN=0  MAT_RIGHT=1  MAT_LEFT=2  MAT_UP=3   MAT_SELECT=8  MAT_START=9
```

Lane mapping (corrected for the mat's physical rotation; both players same):
```python
_MAT_BTN_TO_LANE = {MAT_DOWN: 0, MAT_RIGHT: 1, MAT_LEFT: 2, MAT_UP: 3}
```
Lane index → arrow: `0=← 1=↓ 2=↑ 3=→`.

- `event.joy` = which mat (0 = P1, 1 = P2). Assignment depends on USB plug order.
- 6-frame debounce per (joy, button) — mats fire rapid double events.
- Keyboard parallel input: P1 = `← ↓ ↑ →`, P2 = `A S W D` (unchanged for testing).

**If directions feel wrong after a hardware/firmware change:** the fix is almost
always editing `_MAT_BTN_TO_LANE` only — do NOT touch gameplay logic. History
shows several remaps (90° rotation, then a full UP↔DOWN/LEFT↔RIGHT invert).

---

## 6. Audio architecture (the other thing that breaks)

- Song music = `pygame.mixer.music` (streaming, one MP3 at a time).
- Song-list preview = same `pygame.mixer.music` but `play(start=30.0)` at low vol.
- SFX (miss/collapse/milestone/nav/confirm) = generated numpy tones on mixer
  **channels** (separate from the music streamer).
- Menu jingle = generated 8-bit loop (`_make_menu_music`) on a looping channel.

**Known gotchas:**
- `pygame.mixer.music` and the SFX channels share **one ALSA device**. The Pi's
  HDMI device only accepts the format the `default`/`plug` ALSA wrapper provides;
  `hw:1,0` directly fails with "Sample format non available" (IEC958 only).
- Env vars `SDL_AUDIODRIVER=alsa` / `AUDIODEV=default` MUST be set **before**
  `pygame.init()` (they are, at the top of the file). Forced unconditionally
  because labwc autostart doesn't reliably pass shell env into children.
- PERFECT/GOOD have **no SFX on purpose** (they clashed with the music).

---

## 7. Display / windowing

- Main pygame window = `pygame.display.set_mode((SW,SH), DOUBLEBUF, vsync=1)`.
- Second monitor = a `pygame._sdl2.video.Window` (`_win_logo`) opened at startup,
  positioned at the right monitor's X offset.
- In 2P mode the logo window is **reused** as the P2 gameplay window (no new
  window created), then reverts to logo on return to menu.
- 1 monitor → falls back to split-screen 50/50 (`split_mode`), each half 384px
  wide via a scaled `RenderCtx`.

---

## 8. Performance rules (it must stay smooth on Pi 4B)

`_LOW_PERF = True` does: 30 FPS cap, no starfields, no CRT scanlines.
Other always-on optimizations already in place:
- Pre-baked surfaces: scanlines, border strips (30-frame cycle), note bodies,
  arrow glyphs, rainbow title chars, static text (`_tcache`).
- `get_collapse_y()` computed **once per frame**, not per note.
- Particles: hard-capped (`_PARTICLE_MAX=40`/player), `__slots__`, plain
  `draw.circle`, no per-particle alpha. Smaller bursts when `_LOW_PERF`.

When adding visuals, **pre-bake anything static** and **never allocate a Surface
per-object per-frame**. That was the original lag cause.

---

## 9. Debugging checklist

| Symptom                          | Likely cause / where to look                                   |
|----------------------------------|----------------------------------------------------------------|
| Notes fall too slow on Pi        | A divide-by-`FPS` reintroduced; check `_bpm_fall_speed` & `dt`. |
| Music silent but SFX works (or vice versa) | ALSA device/format; check `/tmp/audio_debug.txt`, `AUDIODEV`. |
| "No file 'music/...'" on autostart | Autostart didn't `cd` into `dance_dance/`.                   |
| Both screens on one monitor      | `wlr-randr` positions / `_open_logo_window` window placement.  |
| P1 and P2 swapped                | USB plug order — swap cables, or it's `_get_monitor_x_positions`. |
| Wrong arrow directions on mat    | `_MAT_BTN_TO_LANE` only.                                        |
| Game jumps straight to results   | `_game_elapsed` / `SONG_DURATION` timing, or music never started. |
| Lag / stutter                    | A per-frame Surface allocation or un-baked draw; check `_LOW_PERF`. |

Useful commands on the Pi:
```bash
cat /tmp/audio_debug.txt              # audio env + music load status, written at startup
wlr-randr                             # monitor positions / transforms
cat /proc/bus/input/devices | grep -A5 ga451   # find mat event devices
aplay -D default /usr/share/sounds/alsa/Front_Left.wav   # test HDMI audio
```

---

## 10. Editing rules of thumb

- **Only edit `quantum_optimized.py`.** Mirror changes to `quantum_dance.py`
  are not needed.
- Keep gameplay/playability identical when "optimizing" — the quantum collapse,
  song select, and scoring must produce the same outcomes.
- New tunables go as named constants **at the top** of their section so they're
  easy to find (see `BEATS_TO_FALL`, `COLLAPSE_THRESHOLD`, `PREVIEW_START_S`,
  `_PARTICLE_MAX`).
- After any change: `python -c "import py_compile; py_compile.compile('quantum_optimized.py', doraise=True)"`
  then test on a desktop with `_LOW_PERF = False` before pushing to the Pi.
