"""
quantum_optimized.py  —  Quantum Dance (Raspberry Pi 4B optimized)
==================================================================
Quantum Exhibition  |  Classical vs Quantum Computing

Same gameplay, song select, and dual-screen quantum collapse as
quantum_dance.py — tuned to run smoothly on a Raspberry Pi 4B.

Performance changes vs quantum_dance.py (NO gameplay/visual difference):
  - GPU-accelerated present: DOUBLEBUF + vsync on the main window
  - get_collapse_y() computed ONCE per frame, not per note
  - Classical + collapsed note bodies are pre-baked surfaces (1 blit
    instead of 2 draw.rect per note per frame)
  - Lane center X precomputed once per ctx per frame
  - FloatText pre-bakes its alpha fade frames (no per-frame .copy())
  - event.get() filtered to the event types each state actually handles

MENU → SONG SELECT → PLAYING

Controls (in-game)
------------------
  ←↓↑→        P1 lanes 0-3
  A S W D      P2 lanes 0-3  (2P only)
  [  /  ]      Nudge BIAS slider ±5%
  \\            Reset BIAS to 50%
  ESC          Return to menu
"""

# ─────────────────────────────────────────────────────────────────────────────
# FIXED TIMING CONSTANTS  (overridden at runtime by song selection)
# ─────────────────────────────────────────────────────────────────────────────
BEATS_PER_NOTE       = 2    # spawn one note every N beats
BEATS_TO_FALL        = 5    # base beats from spawn to hit zone (scaled by difficulty)
COLLAPSE_THRESHOLD   = 1  # multiplier: higher = collapse line moves up (more warning)

# Active song settings — set by song select, do not edit directly
SONG_FILE     = None
SONG_BPM      = 128.0
SONG_OFFSET   = 0.0
SONG_DURATION = 120.0   # seconds — set per song at start_game
_active_beats_fall = float(BEATS_TO_FALL)

FADE_START  = 10.0   # seconds before end to begin fade-out                               

# ─────────────────────────────────────────────────────────────────────────────
# SERIAL PORT HOOK  (hardware potentiometer → BIAS slider)
# ─────────────────────────────────────────────────────────────────────────────
# import threading, serial as _serial
# bias_serial_val = None
# def _serial_reader():
#     global bias_serial_val
#     try:
#         with _serial.Serial("/dev/ttyUSB0", 9600, timeout=1) as port:
#             while True:
#                 line = port.readline().decode(errors="ignore").strip()
#                 if line.isdigit():
#                     bias_serial_val = max(0, min(100, int(line)))
#     except Exception:
#         pass
# threading.Thread(target=_serial_reader, daemon=True).start()
# ─────────────────────────────────────────────────────────────────────────────

import os as _os
import pygame
import sys
import random
import math
import numpy as np
from enum import Enum, auto

# Audio env vars MUST be set before pygame.init() so SDL2 picks them up.
# Force them unconditionally — labwc autostart does not reliably pass
# shell env vars into child processes on this Pi setup.
# plug:both_hdmi routes to both HDMI screens via /etc/asound.conf on Pi.
_os.environ["SDL_AUDIODRIVER"] = "alsa"
_os.environ["AUDIODEV"]        = "default"

# pre_init reserves the audio device BEFORE pygame.init() opens it,
# so both mixer channels and mixer.music share the same single device handle.
# This prevents the "device busy" error when music tries to open a second stream.
pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=2048)
pygame.init()
pygame.mixer.init()

# Debug: log audio environment to file so we can check from SSH
try:
    import datetime
    with open('/tmp/audio_debug.txt', 'w') as _dbg:
        _dbg.write(f"time={datetime.datetime.now()}\n")
        _dbg.write(f"SDL_AUDIODRIVER={_os.environ.get('SDL_AUDIODRIVER','NOT SET')}\n")
        _dbg.write(f"AUDIODEV={_os.environ.get('AUDIODEV','NOT SET')}\n")
        _dbg.write(f"mixer_init={pygame.mixer.get_init()}\n")
except Exception:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Sound effects (procedurally generated — no audio files needed)
# ─────────────────────────────────────────────────────────────────────────────
def _make_tone(freq, duration_ms, vol=0.22, fade_ms=40):
    sr   = 44100
    n    = int(sr * duration_ms / 1000)
    t    = np.linspace(0, duration_ms / 1000, n, False)
    wave = np.sin(2 * np.pi * freq * t) * vol
    fade = max(1, int(sr * fade_ms / 1000))
    wave[-fade:] *= np.linspace(1, 0, fade)
    arr  = (wave * 32767).astype(np.int16)
    return pygame.sndarray.make_sound(np.column_stack([arr, arr]))

def _make_chord(freqs, duration_ms, vol=0.18, fade_ms=60):
    """Mix multiple sine waves for a richer arcade chord."""
    sr  = 44100
    n   = int(sr * duration_ms / 1000)
    t   = np.linspace(0, duration_ms / 1000, n, False)
    wave = sum(np.sin(2 * np.pi * f * t) for f in freqs) * (vol / len(freqs))
    fade = max(1, int(sr * fade_ms / 1000))
    wave[-fade:] *= np.linspace(1, 0, fade)
    arr = (wave * 32767).astype(np.int16)
    return pygame.sndarray.make_sound(np.column_stack([arr, arr]))

def _make_menu_music(bpm=140, bars=4, vol=0.18):
    """Generate a looping 8-bit style arcade jingle."""
    sr       = 44100
    beat_s   = 60.0 / bpm
    bar_s    = beat_s * 4
    total_s  = bar_s * bars
    n        = int(sr * total_s)
    t        = np.linspace(0, total_s, n, False)
    wave     = np.zeros(n)
    # Simple 8-bit melody — square-ish wave via harmonics
    melody = [  # (start_beat, duration_beats, freq)
        (0,0.5,523),(0.5,0.5,659),(1,0.5,784),(1.5,0.5,1047),
        (2,0.5,880),(2.5,0.5,784),(3,1.0,659),
        (4,0.5,523),(4.5,0.5,440),(5,0.5,523),(5.5,0.5,659),
        (6,0.5,784),(6.5,0.5,880),(7,1.0,1047),
        (8,0.5,784),(8.5,0.5,659),(9,0.5,523),(9.5,0.5,440),
        (10,0.5,392),(10.5,0.5,440),(11,1.0,523),
        (12,0.5,659),(12.5,0.5,784),(13,0.5,880),(13.5,0.5,784),
        (14,0.5,659),(14.5,0.5,523),(15,1.0,440),
    ]
    for start_beat, dur_beats, freq in melody:
        i0 = int(start_beat * beat_s * sr)
        i1 = min(n, int((start_beat + dur_beats * 0.85) * beat_s * sr))
        if i0 >= n: continue
        seg_t = t[i0:i1] - t[i0]
        # Square-ish: fundamental + 3rd harmonic
        seg = (np.sin(2*np.pi*freq*seg_t) + 0.3*np.sin(2*np.pi*freq*3*seg_t)) * vol
        fade = max(1, int(sr * 0.02))
        seg[-fade:] *= np.linspace(1, 0, fade)
        wave[i0:i1] += seg
    wave = np.clip(wave, -1, 1)
    arr  = (wave * 32767).astype(np.int16)
    return pygame.sndarray.make_sound(np.column_stack([arr, arr]))

try:
    # Hit SFX — PERFECT and GOOD removed (interfere with music)
    # Keep miss (low freq, doesn't clash) and collapse/milestone
    SFX_PERFECT   = None   # silenced — visual feedback only
    SFX_GOOD      = None   # silenced — visual feedback only
    SFX_MISS      = _make_tone(180, 90, vol=0.15)
    SFX_COLLAPSE  = _make_chord([220, 277, 330], 160, vol=0.16)
    SFX_MILESTONE = _make_chord([523, 659, 784, 1047], 220, vol=0.18)
    SFX_NAV       = _make_tone(660, 40, vol=0.12)    # menu navigation beep
    SFX_CONFIRM   = _make_chord([523, 659, 784], 120, vol=0.15)  # menu confirm
    SFX_MENU_MUSIC = _make_menu_music()
    _sfx_ok = True
except Exception:
    SFX_PERFECT = SFX_GOOD = SFX_MISS = SFX_COLLAPSE = None
    SFX_MILESTONE = SFX_NAV = SFX_CONFIRM = SFX_MENU_MUSIC = None
    _sfx_ok = False

def _play(sfx):
    if _sfx_ok and sfx is not None:
        try: sfx.play()
        except Exception: pass

# ─────────────────────────────────────────────────────────────────────────────
# Song preview (plays a short fragment while browsing the song list)
# ─────────────────────────────────────────────────────────────────────────────
PREVIEW_START_S  = 30.0   # seconds into the song to start the preview
PREVIEW_VOLUME   = 0.55   # quieter than full playback
_preview_idx     = -1     # which SONGS index is currently previewed (-1 = none)

def _start_preview(song: dict, idx: int):
    """Load `song` into the streaming player and play a fragment from ~30s in."""
    global _preview_idx
    if idx == _preview_idx:
        return                      # already previewing this one
    _preview_idx = idx
    try:
        pygame.mixer.music.stop()
        pygame.mixer.music.load(song["file"])
        pygame.mixer.music.set_volume(PREVIEW_VOLUME)
        # play(start=...) seeks into the track (works for mp3/ogg)
        try:
            pygame.mixer.music.play(start=PREVIEW_START_S)
        except Exception:
            pygame.mixer.music.play()   # fallback: from the beginning
    except Exception as e:
        print(f"[INFO] Preview failed for {song.get('title')}: {e}")

def _stop_preview():
    global _preview_idx
    _preview_idx = -1
    try: pygame.mixer.music.stop()
    except Exception: pass

# ─────────────────────────────────────────────────────────────────────────────
# Screen & timing
# ─────────────────────────────────────────────────────────────────────────────
SW, SH    = 768, 1024
FPS       = 60
_LOW_PERF = True   # True = Raspberry Pi: skip stars/scanlines, cap 30 FPS

# GPU-accelerated present: DOUBLEBUF lets SDL flip buffers on the GPU instead
# of copying the whole 1080x1920 framebuffer in software every frame.
# vsync=1 avoids tearing and caps redundant draws. Falls back gracefully.
_flags = pygame.DOUBLEBUF
try:
    screen = pygame.display.set_mode((SW, SH), _flags, vsync=1)
except Exception:
    screen = pygame.display.set_mode((SW, SH), _flags)
pygame.display.set_caption("Quantum Dance  |  Quantum Exhibition")
clk    = pygame.time.Clock()

# ─────────────────────────────────────────────────────────────────────────────
# Music player — uses a dedicated mixer channel instead of pygame.mixer.music
# so it shares the same audio device as SFX (avoids ALSA "device busy" error)
# ─────────────────────────────────────────────────────────────────────────────
pygame.mixer.set_num_channels(16)   # reserve extra channels; ch 15 = music
_MUSIC_CHANNEL   = pygame.mixer.Channel(15)
_music_sound     = None   # currently loaded Sound object
_music_start_ms  = 0      # pygame.time.get_ticks() when music started
_music_volume    = 1.0

def _music_load(path: str):
    global _music_sound
    try:
        _music_sound = pygame.mixer.Sound(path)
    except Exception as e:
        print(f"[WARNING] Could not load music: {e}")
        _music_sound = None

def _music_play():
    global _music_start_ms
    if _music_sound is None: return
    _MUSIC_CHANNEL.set_volume(_music_volume)
    _MUSIC_CHANNEL.play(_music_sound)
    _music_start_ms = pygame.time.get_ticks()

def _music_stop():
    _MUSIC_CHANNEL.stop()

def _music_get_busy() -> bool:
    return _MUSIC_CHANNEL.get_busy()

def _music_get_pos() -> int:
    """Returns milliseconds since music started, like pygame.mixer.music.get_pos()."""
    if not _MUSIC_CHANNEL.get_busy():
        return -1
    return pygame.time.get_ticks() - _music_start_ms

def _music_set_volume(vol: float):
    global _music_volume
    _music_volume = max(0.0, min(1.0, vol))
    _MUSIC_CHANNEL.set_volume(_music_volume)

# ─────────────────────────────────────────────────────────────────────────────
# Game state enum
# ─────────────────────────────────────────────────────────────────────────────
class GameState(Enum):
    MENU        = auto()
    SONG_SELECT = auto()
    PLAYING     = auto()
    NAME_ENTRY  = auto()   # entering initials for a top-5 score
    RESULTS     = auto()
    LEADERBOARD = auto()   # viewing a song's top-5 (from song select)

game_state    = GameState.MENU
n_players     = 1
song_cursor   = 0      # highlighted row in song select screen
last_song     = None   # dict of the last played song (for retry)

# ─────────────────────────────────────────────────────────────────────────────
# Leaderboard — one top-5 list per song, saved to leaderboard.json
# ─────────────────────────────────────────────────────────────────────────────
import json as _json
LEADERBOARD_FILE = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                 "leaderboard.json")
LEADERBOARD_SIZE = 5
_leaderboard: dict = {}   # { song_title: [ {"name": str, "score": int}, ... ] }

def _load_leaderboard():
    global _leaderboard
    try:
        with open(LEADERBOARD_FILE, "r") as f:
            _leaderboard = _json.load(f)
    except Exception:
        _leaderboard = {}

def _save_leaderboard():
    try:
        with open(LEADERBOARD_FILE, "w") as f:
            _json.dump(_leaderboard, f, indent=2)
    except Exception as e:
        print(f"[WARNING] Could not save leaderboard: {e}")

def _board_for(song_title: str) -> list:
    return _leaderboard.get(song_title, [])

def _qualifies(song_title: str, score: int) -> bool:
    """True if `score` would make the song's top-5."""
    board = _board_for(song_title)
    if len(board) < LEADERBOARD_SIZE:
        return score > 0
    return score > board[-1]["score"]

def _add_score(song_title: str, name: str, score: int) -> int:
    """Insert a score, keep top-5 sorted. Returns the placed rank (0-based) or -1."""
    board = list(_board_for(song_title))
    board.append({"name": name, "score": int(score)})
    board.sort(key=lambda e: e["score"], reverse=True)
    board = board[:LEADERBOARD_SIZE]
    _leaderboard[song_title] = board
    _save_leaderboard()
    for i, e in enumerate(board):
        if e["name"] == name and e["score"] == int(score):
            return i
    return -1

_load_leaderboard()

# ── Name-entry state (arcade 3-initial input + optional keyboard typing) ──────
_NAME_CHARS  = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 "   # last char = blank/space
_entry_queue : list = []   # players still needing to enter, e.g. [(p_ref,"P1"), ...]
_entry_initials = ["A", "A", "A"]   # current 3 initials being scrolled
_entry_pos      = 0        # which of the 3 initials is active
_entry_typed    = ""       # keyboard-typed name (overrides initials if non-empty)
_entry_label    = ""       # "PLAYER 1" / "PLAYER 2" / "" for 1P
_entry_score    = 0        # score being entered
_leader_view_idx = 0       # which song's board is shown in LEADERBOARD state

def _begin_name_entry(queue: list):
    """queue = list of (player_state, label) that qualified. Sets up the first."""
    global _entry_queue, _entry_initials, _entry_pos, _entry_typed
    global _entry_label, _entry_score, game_state
    _entry_queue = queue
    if not _entry_queue:
        game_state = GameState.RESULTS
        return
    ps, label = _entry_queue[0]
    _entry_initials = ["A", "A", "A"]
    _entry_pos      = 0
    _entry_typed    = ""
    _entry_label    = label
    _entry_score    = ps.score
    game_state = GameState.NAME_ENTRY

def _commit_name_entry():
    """Save the current entry and advance to the next player or to RESULTS."""
    global _entry_queue, game_state
    name = _entry_typed.strip().upper()[:10] if _entry_typed.strip() else "".join(_entry_initials).strip()
    if not name:
        name = "---"
    _add_score(last_song["title"], name, _entry_score)
    _entry_queue = _entry_queue[1:]
    if _entry_queue:
        _begin_name_entry(_entry_queue)   # set up next player
    else:
        game_state = GameState.RESULTS

# ── Permanent second window (logo screen until 2P game starts) ────────────────
_win_logo  = None   # SDL2 Window on the second monitor
_ren_logo  = None   # Renderer for that window
_surf_logo = None   # Surface we draw onto

def _open_logo_window():
    """Open the second monitor window showing the logo. Called once at startup."""
    global _win_logo, _ren_logo, _surf_logo
    try:
        import subprocess, re
        out = subprocess.check_output(["wlr-randr"], stderr=subprocess.DEVNULL).decode()
        positions = sorted(set(int(m.group(1))
                               for m in re.finditer(r'Position:\s*(\d+),\d+', out)))
        if len(positions) < 2:
            return
        p1_x = positions[0]   # leftmost = main/P1 screen
        p2_x = positions[1]   # rightmost = logo/P2 screen
        from pygame._sdl2.video import Window, Renderer
        # Explicitly place the main pygame window on the left screen
        try:
            _main = Window.from_display_module()
            _main.position = (p1_x, 0)
        except Exception:
            pass
        # Open logo window on the right screen
        _win_logo  = Window("Quantum Dance", size=(SW, SH))
        _win_logo.position = (p2_x, 0)
        _ren_logo  = Renderer(_win_logo)
        _surf_logo = pygame.Surface((SW, SH))
        print(f"[INFO] Logo window opened at x={p2_x}, main at x={p1_x}")
    except Exception as e:
        print(f"[INFO] Logo window not opened: {e}")

def _close_logo_window():
    global _win_logo, _ren_logo, _surf_logo
    if _win_logo:
        try: _win_logo.destroy()
        except Exception: pass
    _win_logo = _ren_logo = _surf_logo = None

def _draw_logo_screen(surf):
    """Black screen with centred QUANTUM DANCE title — shown on second monitor."""
    t = pygame.time.get_ticks() // 33   # ~30fps tick counter
    surf.fill((4, 2, 14))
    title_str = "QUANTUM DANCE"
    tx = SW // 2 - sum(F_BIG.size(ch)[0] for ch in title_str) // 2
    ty = SH // 2 - F_BIG.get_height() // 2
    for i, ch in enumerate(title_str):
        hue = (t * 2 + i * 18) % 360
        h   = hue / 60.0
        xv  = int(255 * (1 - abs(h % 2 - 1)))
        if   h < 1: r, g, b = 255,  xv,   0
        elif h < 2: r, g, b =  xv, 255,   0
        elif h < 3: r, g, b =   0, 255,  xv
        elif h < 4: r, g, b =   0,  xv, 255
        elif h < 5: r, g, b =  xv,   0, 255
        else:       r, g, b = 255,   0,  xv
        cs = _rainbow_char(ch, r, g, b, F_BIG)
        surf.blit(cs, (tx, ty))
        tx += cs.get_width()
    sub = _tcache('logo_sub', "Quantum Exhibition", F_MENUSM, (140, 100, 200))
    surf.blit(sub, (SW // 2 - sub.get_width() // 2, ty + F_BIG.get_height() + 20))

def _present_logo():
    """Blit the logo surface to the second window."""
    if not (_win_logo and _ren_logo and _surf_logo):
        return
    try:
        from pygame._sdl2.video import Texture
        _draw_logo_screen(_surf_logo)
        tex = Texture.from_surface(_ren_logo, _surf_logo)
        _ren_logo.clear()
        tex.draw()
        _ren_logo.present()
        tex.destroy()
    except Exception:
        pass

# 2P window objects (created only when n_players == 2)
win2  = None
ren2  = None
surf2 = None

# ─────────────────────────────────────────────────────────────────────────────
# Colours
# ─────────────────────────────────────────────────────────────────────────────
BG        = (8,   6,  20)
LANE_BG   = (16,  13,  36)
LANE_LINE = (45,  38,  80)
GOLD      = (255, 200,   0)
WHITE     = (240, 240, 255)
RED       = (255,  55,  55)
DIM       = (90,  80, 130)
Q_PURPLE  = (210,  70, 255)
Q_WAVE    = (255,  90, 210)
PANEL_BG  = (11,   9,  26)

LANE_C = [
    ( 50, 130, 255),   # 0  ←  blue
    ( 40, 220, 120),   # 1  ↓  teal
    (255, 160,  45),   # 2  ↑  orange
    (200,  70, 255),   # 3  →  purple
]

# P2 classical note palette — warm/distinct so screens are instantly told apart
LANE_C_P2 = [
    (255, 100,  80),   # 0  ←  coral-red
    (255, 200,  50),   # 1  ↓  yellow
    ( 80, 220, 255),   # 2  ↑  sky-blue
    (180, 255, 100),   # 3  →  lime-green
]

SL_SPAWN_C    = ( 80, 200, 255)
SL_SPEED_C    = ( 80, 255, 160)
SL_COLLAPSE_C = (210,  70, 255)
SL_BIAS_C     = (255, 180,  60)

# ─────────────────────────────────────────────────────────────────────────────
# Fonts
# ─────────────────────────────────────────────────────────────────────────────
def _f(sz, bold=True):
    for n in ("Segoe UI", "Arial", "Helvetica", "DejaVu Sans", "sans-serif"):
        try:
            return pygame.font.SysFont(n, sz, bold=bold)
        except Exception:
            pass
    return pygame.font.Font(None, sz)

F_TITLE  = _f(40)
F_BIG    = _f(52)
F_MENU   = _f(33)
F_MENUSM = _f(22)
F_MED    = _f(22)
F_SM     = _f(16)
F_XSM    = _f(12, bold=False)
F_ARROW  = _f(32)

# ─────────────────────────────────────────────────────────────────────────────
# Song catalogue  (sourced from music/ddr_songs.txt)
# ─────────────────────────────────────────────────────────────────────────────
SONGS = [
    {"title": "Faded",                  "artist": "Alan Walker",
     "file": "music/Alan Walker - Faded.mp3",
     "bpm": 90,  "offset": 0.0, "difficulty": "Easy",    "duration": 120},
    {"title": "Alone",                  "artist": "Alan Walker",
     "file": "music/Alan Walker - Alone.mp3",
     "bpm": 150, "offset": 3.0, "difficulty": "Extreme", "duration":  90},
    {"title": "Bad Guy",                "artist": "Billie Eilish",
     "file": "music/Billie Eilish - bad guy (Lyrics).mp3",
     "bpm": 135, "offset": 0.0, "difficulty": "Hard",    "duration": 100},
    {"title": "Dynamite",               "artist": "BTS",
     "file": "music/BTS - Dynamite (Lyrics).mp3",
     "bpm": 114, "offset": 0.0, "difficulty": "Easy",    "duration": 110},
    {"title": "Can't Stop the Feeling", "artist": "Justin Timberlake",
     "file": "music/Justin Timberlake - CAN'T STOP THE FEELING! (Lyrics).mp3",
     "bpm": 113, "offset": 0.0, "difficulty": "Easy",    "duration": 120},
    {"title": "Party Rock Anthem",      "artist": "LMFAO",
     "file": "music/LMFAO - Party Rock Anthem (Lyrics) ft. Lauren Bennett, GoonRock.mp3",
     "bpm": 130, "offset": 0.0, "difficulty": "Hard",    "duration":  90},
]

DIFF_SPEED = {"Easy": 1.0, "Hard": 1.5, "Extreme": 2.0}
DIFF_COLOR = {"Easy": (80, 220, 120), "Hard": (255, 180, 60), "Extreme": (255, 60, 60)}

# ─────────────────────────────────────────────────────────────────────────────
# Arcade constants
# ─────────────────────────────────────────────────────────────────────────────
MAX_HP           = 100
HP_GAIN_PERFECT  =  2
HP_GAIN_GOOD     =  1
HP_LOSS_MISS     = 10
HP_LOSS_QUANTUM  =  8
COMBO_MILESTONES = [10, 25, 50, 100, 200]

# ─────────────────────────────────────────────────────────────────────────────
# Layout constants
# ─────────────────────────────────────────────────────────────────────────────
N_LANES  = 4
LANE_W   = 170
LANE_GAP = 11
TOTAL_W  = N_LANES * LANE_W + (N_LANES - 1) * LANE_GAP   # 713
LX0      = (SW - TOTAL_W) // 2                            #   27 — side margins

TOP_H    = 90
BOT_H    = 90
LANE_TOP = TOP_H
LANE_BOT = SH - BOT_H        # 934

TARGET_Y   = LANE_BOT - 34
HIT_ZONE_H = 60
NOTE_W     = LANE_W - 14
NOTE_H     = 54

HIT_PERFECT = 22
HIT_GOOD    = 46

KEYS_P1 = [pygame.K_LEFT, pygame.K_DOWN, pygame.K_UP, pygame.K_RIGHT]
KEYS_P2 = [pygame.K_a,    pygame.K_s,    pygame.K_w,  pygame.K_d]
ARROWS  = ["←", "↓", "↑", "→"]

# ── Dance mat joystick input ──────────────────────────────────────────────────
# Button mapping confirmed by hardware test (Vendor 0e8f, Product 0035)
MAT_DOWN   = 0   # BTN_TRIGGER  code 288
MAT_RIGHT  = 1   # BTN_THUMB    code 289
MAT_LEFT   = 2   # BTN_THUMB2   code 290  (also START on mat1)
MAT_UP     = 3   # BTN_TOP      code 291
MAT_SELECT = 8   # BTN_BASE3    code 296
MAT_START  = 9   # BTN_BASE4    code 297  (mat2 canonical START)
# MAT button → lane index (left=0 down=1 up=2 right=3)
# Corrected for physical mat rotation — mat is rotated 90° relative to screen:
#   physical UP    → lane 0 (← left arrow)
#   physical LEFT  → lane 1 (↓ down arrow)
#   physical RIGHT → lane 2 (↑ up arrow)
#   physical DOWN  → lane 3 (→ right arrow)
_MAT_BTN_TO_LANE = {MAT_DOWN: 0, MAT_RIGHT: 1, MAT_LEFT: 2, MAT_UP: 3}

# Debounce: track last-press tick per (joy_id, button)
_mat_last: dict = {}
_MAT_DEBOUNCE = 6   # frames

def _mat_lane(btn: int) -> int | None:
    return _MAT_BTN_TO_LANE.get(btn)

pygame.joystick.init()
_mats: list = [pygame.joystick.Joystick(i)
               for i in range(pygame.joystick.get_count())]
if _mats:
    print(f"[INFO] {len(_mats)} dance mat(s) detected")

# Block high-volume event types the game never reads. Mouse hover uses
# pygame.mouse.get_pos() (polled), so MOUSEMOTION is pure noise — blocking it
# keeps the event queue tiny each frame, lowering per-frame input overhead.
pygame.event.set_blocked([
    pygame.MOUSEMOTION,
    pygame.JOYAXISMOTION,
    pygame.JOYHATMOTION,
    pygame.JOYBALLMOTION,
    pygame.TEXTINPUT,
    pygame.TEXTEDITING,
])

RP_X = LX0 + TOTAL_W   # 736
RP_W = SW - RP_X        # 224

FALL_DISTANCE = TARGET_Y - LANE_TOP   # ~522 px


def lx(lane):  return LX0 + lane * (LANE_W + LANE_GAP)
def lcx(lane): return lx(lane) + LANE_W // 2

# P2 key mirror map: physical key index → logical lane
# Lane 0(←)↔3(→), Lane 1(↓)↔2(↑)
_P2_KEY_MAP = [3, 2, 1, 0]

# ─────────────────────────────────────────────────────────────────────────────
# Pre-baked surfaces and caches (built once, reused every frame)
# ─────────────────────────────────────────────────────────────────────────────

# Scanlines — only built when needed (skipped in _LOW_PERF mode)
def _make_scanlines(w, h, alpha=28, step=4):
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(0, h, step):
        pygame.draw.line(s, (0, 0, 0, alpha), (0, y), (w, y))
    return s

_SCAN_FULL  = None if _LOW_PERF else _make_scanlines(SW, SH)
_SCAN_LANES = None if _LOW_PERF else _make_scanlines(SW, LANE_BOT - LANE_TOP)

# Pre-baked starfields (static positions, only twinkle varies — skipped in LOW_PERF)
def _make_star_positions(n, w, y0, y1, seed):
    rng = random.Random(seed)
    return [(rng.randint(0, w), rng.randint(y0, y1)) for _ in range(n)]

_STARS_MENU    = [] if _LOW_PERF else _make_star_positions(120, SW, 0,        SH,       7)
_STARS_LANES   = [] if _LOW_PERF else _make_star_positions(60,  SW, LANE_TOP, LANE_BOT, 13)
_STARS_SEL     = [] if _LOW_PERF else _make_star_positions(100, SW, 0,        SH,       42)
_STARS_RESULTS = _make_star_positions(40, SW, 0, SH, 99)   # results always uses pre-baked list

# Pre-rendered arrow surfaces per lane (static color)
_ARROW_SURFS = [F_ARROW.render(a, True, LANE_C[i]) for i, a in enumerate(["←","↓","↑","→"])]

# Pre-baked note body surfaces — full-width (SW=1080) note. For split-screen
# (480px ctx) the note_w differs, so we bake per note width on demand.
# A note body = fill rounded-rect + bright outline + centered arrow. Baking it
# once turns 2 draw.rect + 1 blit per note per frame into a single blit.
_NOTE_BODY_CACHE: dict = {}   # (kind, lane, note_w) -> Surface

def _bake_note_body(kind: str, lane: int, nw: int) -> pygame.Surface:
    """kind: 'classical' | 'collapsed'. Returns a baked NOTE_W x NOTE_H surface."""
    key = (kind, lane, nw)
    cached = _NOTE_BODY_CACHE.get(key)
    if cached is not None:
        return cached
    if kind == "collapsed":
        r, g, b = Q_PURPLE
        arrow = _ARROW_SURFS[lane]
    else:
        r, g, b = LANE_C[lane]
        arrow = _ARROW_SURFS[lane]
    surf = pygame.Surface((nw, NOTE_H), pygame.SRCALPHA)
    rect = pygame.Rect(0, 0, nw, NOTE_H)
    pygame.draw.rect(surf, (r // 4, g // 4, b // 4), rect, border_radius=9)
    pygame.draw.rect(surf, (r, g, b),               rect, 3, border_radius=9)
    surf.blit(arrow, (nw // 2 - arrow.get_width() // 2,
                      (NOTE_H - arrow.get_height()) // 2))
    _NOTE_BODY_CACHE[key] = surf
    return surf

# Pre-baked animated border strips (30-frame cycle, plain surfaces — fast blit)
_BORDER_COLS_TOP = [(255,60,180),(255,160,0),(80,255,80),(0,200,255),(200,80,255)]
_BORDER_COLS_BOT = [(0,200,255),(200,80,255),(255,60,180),(255,160,0),(80,255,80)]
_TOP_BORDER_FRAMES: list = []
_BOT_BORDER_FRAMES: list = []
for _phase in range(30):
    _pulse = 0.6 + 0.4 * math.sin(_phase * math.tau / 30)
    _st = pygame.Surface((SW, 6))
    _sb = pygame.Surface((SW, 6))
    for _i, (_ct, _cb) in enumerate(zip(_BORDER_COLS_TOP, _BORDER_COLS_BOT)):
        _ct2 = tuple(min(255, int(v * _pulse * 0.9)) for v in _ct)
        _cb2 = tuple(min(255, int(v * _pulse * 0.9)) for v in _cb)
        pygame.draw.line(_st, _ct2, (0, _i), (SW, _i))
        pygame.draw.line(_sb, _cb2, (0, _i), (SW, _i))
    _TOP_BORDER_FRAMES.append(_st)
    _BOT_BORDER_FRAMES.append(_sb)

# Pre-baked song-select active row glow (built on first use)
_ROW_GLOW: pygame.Surface = None

def _get_row_glow(w, h):
    global _ROW_GLOW
    if _ROW_GLOW is None:
        s = pygame.Surface((w + 16, h + 16), pygame.SRCALPHA)
        pygame.draw.rect(s, (*Q_PURPLE, 20), (0, 0, w + 16, h + 16), border_radius=12)
        _ROW_GLOW = s
    return _ROW_GLOW

# Pre-baked menu button glows — keyed by base color tuple
_BTN_GLOWS: dict = {}

def _get_btn_glow(w, h, color):
    if color not in _BTN_GLOWS:
        s = pygame.Surface((w + 36, h + 36), pygame.SRCALPHA)
        pygame.draw.rect(s, (*color, 25), (0, 0, w + 36, h + 36), border_radius=14)
        _BTN_GLOWS[color] = s
    return _BTN_GLOWS[color]

# Cache for rainbow title characters: (char, r, g, b, font_id) → Surface
_RAINBOW_CACHE: dict = {}

def _rainbow_char(ch: str, r: int, g: int, b: int, font) -> pygame.Surface:
    key = (ch, r, g, b, id(font))
    if key not in _RAINBOW_CACHE:
        _RAINBOW_CACHE[key] = font.render(ch, True, (r, g, b))
    return _RAINBOW_CACHE[key]

# Cache for text surfaces that only change when value changes
_text_cache: dict = {}

def _tcache(key, text, font, color):
    if key not in _text_cache or _text_cache[key][0] != text:
        _text_cache[key] = (text, font.render(text, True, color))
    return _text_cache[key][1]


# ─────────────────────────────────────────────────────────────────────────────
# RenderCtx — per-surface layout (scales for split-screen 480px halves)
# ─────────────────────────────────────────────────────────────────────────────
from dataclasses import dataclass

@dataclass
class RenderCtx:
    sw       : int
    lane_w   : int
    lane_gap : int
    lx0      : int
    note_w   : int

def make_ctx(surf_w: int) -> RenderCtx:
    scale    = surf_w / SW
    lw       = max(60, int(LANE_W  * scale))
    lg       = max(4,  int(LANE_GAP * scale))
    total    = N_LANES * lw + (N_LANES - 1) * lg
    lx0      = (surf_w - total) // 2
    nw       = max(40, lw - int(14 * scale))
    return RenderCtx(sw=surf_w, lane_w=lw, lane_gap=lg, lx0=lx0, note_w=nw)

def _lx(lane: int, ctx: RenderCtx) -> int:
    return ctx.lx0 + lane * (ctx.lane_w + ctx.lane_gap)

def _lcx(lane: int, ctx: RenderCtx) -> int:
    return _lx(lane, ctx) + ctx.lane_w // 2

# Display-mode globals (set in start_game)
two_screen_mode = False   # Option A: two SDL2 windows on separate monitors
split_mode      = False   # Option B: one window split 50/50
ctx1: RenderCtx = None    # P1 render context
ctx2: RenderCtx = None    # P2 render context


def _get_monitor_x_positions() -> list:
    """
    Return a list of X offsets for all connected monitors, sorted ascending.
    P1 always gets positions[0] (leftmost), P2 gets positions[1] (rightmost).
    This makes plug order irrelevant — whichever screen is on the left is P1.

    Tries in order:
    1. wlr-randr  (Wayland/labwc — Raspberry Pi Trixie)
    2. xrandr     (X11 Linux)
    3. pygame     (macOS / Windows fallback)
    """
    import subprocess, re

    # ── wlr-randr (Wayland) ──────────────────────────────────────────────────
    try:
        out = subprocess.check_output(["wlr-randr"],
                                      stderr=subprocess.DEVNULL).decode()
        positions = sorted(set(
            int(m.group(1))
            for m in re.finditer(r'Position:\s*(\d+),\d+', out)
        ))
        if len(positions) >= 1:
            return positions
    except Exception:
        pass

    # ── xrandr (X11) ─────────────────────────────────────────────────────────
    try:
        out = subprocess.check_output(["xrandr", "--query"],
                                      stderr=subprocess.DEVNULL).decode()
        pattern = re.compile(r'^\S+ connected \d+x\d+\+(\d+)\+\d+', re.MULTILINE)
        positions = sorted(int(m.group(1)) for m in pattern.finditer(out))
        if len(positions) >= 1:
            return positions
    except Exception:
        pass

    # ── pygame fallback (macOS / Windows) ────────────────────────────────────
    try:
        n = pygame.display.get_num_displays()
        if n >= 2:
            sizes = pygame.display.get_desktop_sizes()
            return [0, sizes[0][0]]
    except Exception:
        pass

    return []


# ─────────────────────────────────────────────────────────────────────────────
# BPM timing helpers
# ─────────────────────────────────────────────────────────────────────────────
def _bpm_fall_speed() -> float:
    """px/second for a note to travel FALL_DISTANCE in _active_beats_fall beats."""
    seconds = _active_beats_fall * 60.0 / SONG_BPM
    return FALL_DISTANCE / seconds   # px/sec — frame-rate independent

def _bpm_collapse_y() -> int:
    """Collapse 1 beat before the note reaches TARGET_Y."""
    px_per_beat = (FALL_DISTANCE / (_active_beats_fall * 60.0 / SONG_BPM)) * (60.0 / SONG_BPM)
    return int(TARGET_Y - px_per_beat * COLLAPSE_THRESHOLD)


# ─────────────────────────────────────────────────────────────────────────────
# Slider widget
# ─────────────────────────────────────────────────────────────────────────────
class Slider:
    TW = 12
    HR = 13

    def __init__(self, cx, y_top, height,
                 min_val, max_val, init_val,
                 title, value_fmt, color, desc=()):
        self.cx      = cx
        self.y_top   = y_top
        self.height  = height
        self.min_val = float(min_val)
        self.max_val = float(max_val)
        self.val     = float(init_val)
        self.title   = title
        self.fmt     = value_fmt
        self.color   = color
        self.desc    = desc
        self.dragging = False

    def _hy(self):
        t = (self.val - self.min_val) / (self.max_val - self.min_val)
        return int(self.y_top + (1.0 - t) * self.height)

    def _y_to_val(self, sy):
        rel = max(0.0, min(float(self.height), sy - self.y_top))
        t   = 1.0 - rel / self.height
        return self.min_val + t * (self.max_val - self.min_val)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            hy  = self._hy()
            hit = pygame.Rect(self.cx - self.HR - 5, hy - self.HR - 5,
                              (self.HR + 5) * 2, (self.HR + 5) * 2)
            if hit.collidepoint(event.pos):
                self.dragging = True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.val = max(self.min_val,
                          min(self.max_val, self._y_to_val(event.pos[1])))

    def draw(self, surf):
        r, g, b = self.color
        hy  = self._hy()
        tx  = self.cx - self.TW // 2
        y_b = self.y_top + self.height

        pygame.draw.rect(surf, (22, 18, 42),
                         (tx, self.y_top, self.TW, self.height), border_radius=6)
        fill_h = y_b - hy
        if fill_h > 0:
            pygame.draw.rect(surf, (r // 3, g // 3, b // 3),
                             (tx, hy, self.TW, fill_h), border_radius=6)
        pygame.draw.rect(surf, (r // 2, g // 2, b // 2),
                         (tx, self.y_top, self.TW, self.height), 2, border_radius=6)

        pygame.draw.circle(surf, (r // 5, g // 5, b // 5), (self.cx, hy), self.HR + 7)
        pygame.draw.circle(surf, self.color, (self.cx, hy), self.HR)
        pygame.draw.circle(surf, WHITE, (self.cx, hy), max(1, self.HR - 7))

        t = F_SM.render(self.title, True, self.color)
        surf.blit(t, (self.cx - t.get_width() // 2, self.y_top - 22))
        mx_t = F_XSM.render("▲ MAX", True, (r // 2, g // 2, b // 2))
        surf.blit(mx_t, (self.cx - mx_t.get_width() // 2, self.y_top - 36))
        mn_t = F_XSM.render("▼ MIN", True, (r // 2, g // 2, b // 2))
        surf.blit(mn_t, (self.cx - mn_t.get_width() // 2, y_b + 4))

        val_str = self.fmt.format(self.val)
        vt = F_MED.render(val_str, True, self.color)
        surf.blit(vt, (self.cx - vt.get_width() // 2, y_b + 18))
        for i, line in enumerate(self.desc):
            dt = F_XSM.render(line, True, DIM)
            surf.blit(dt, (self.cx - dt.get_width() // 2, y_b + 36 + i * 13))


# ─────────────────────────────────────────────────────────────────────────────
# Slider instances
# ─────────────────────────────────────────────────────────────────────────────
_SL_Y = TOP_H + 70
_SL_H = LANE_BOT - _SL_Y - 80

_CX_SPAWN    = LX0 // 2
_CX_SPEED    = RP_X + RP_W * 1 // 4
_CX_COLLAPSE = RP_X + RP_W * 2 // 4
_CX_BIAS     = RP_X + RP_W * 3 // 4

spawn_slider = Slider(
    cx=_CX_SPAWN, y_top=_SL_Y, height=_SL_H,
    min_val=1.0, max_val=10.0, init_val=4.5,
    title="SPAWN", value_fmt="{:.1f}", color=SL_SPAWN_C,
    desc=("notes / sec", "↑ more notes", "↓ fewer notes"),
)
speed_slider = Slider(
    cx=_CX_SPEED, y_top=_SL_Y, height=_SL_H,
    min_val=1.5, max_val=9.0, init_val=3.9,
    title="SPEED", value_fmt="{:.1f}", color=SL_SPEED_C,
    desc=("fall speed", "px / frame"),
)
collapse_slider = Slider(
    cx=_CX_COLLAPSE, y_top=_SL_Y, height=_SL_H,
    min_val=40, max_val=430, init_val=195,
    title="COLLAPSE", value_fmt="{:.0f}px", color=SL_COLLAPSE_C,
    desc=("above hit zone", "↑ more time", "↓ surprise!"),
)
bias_slider = Slider(
    cx=_CX_BIAS, y_top=_SL_Y, height=_SL_H,
    min_val=0, max_val=100, init_val=50,
    title="BIAS", value_fmt="{:.0f}%", color=SL_BIAS_C,
    desc=("collapse bias", "↑ favors lane 1", "↓ favors lane 2"),
)

# In BPM mode SPEED and COLLAPSE sliders are hidden; SPAWN and BIAS remain
SLIDERS_FREE = [spawn_slider, speed_slider, collapse_slider, bias_slider]
SLIDERS_BPM  = [spawn_slider, bias_slider]


def get_collapse_y() -> int:
    return _bpm_collapse_y() if SONG_FILE else int(TARGET_Y - collapse_slider.val)

def get_fall_speed() -> float:
    return _bpm_fall_speed() if SONG_FILE else speed_slider.val

def get_spawn_interval() -> int:
    return max(25, int(215 - spawn_slider.val * 19.5))

def get_collapse_bias() -> float:
    return bias_slider.val / 100.0

def active_sliders():
    return SLIDERS_BPM if SONG_FILE else SLIDERS_FREE


# ─────────────────────────────────────────────────────────────────────────────
# Note
# ─────────────────────────────────────────────────────────────────────────────
class Note:
    _nid = 0

    def __init__(self, lane: int, quantum: bool = False, lane2: int = None,
                 nid: int = None, wave_phase: float = None):
        if nid is None:
            Note._nid += 1
            nid = Note._nid
        self.nid          = nid
        self.lane         = lane
        self.lane2        = lane2
        self.quantum      = quantum
        self.collapsed    = False
        self.final_lane   = lane
        self.dropped_lane = None
        self.y            = float(LANE_TOP - NOTE_H - 8)
        self.speed        = get_fall_speed() + random.uniform(-8.0, 8.0)  # px/sec
        self.alive        = True
        self.hit          = False
        self.missed       = False
        self.just_collapsed = False
        self.just_missed    = False
        self.wave_phase   = wave_phase if wave_phase is not None else random.uniform(0, math.tau)

    def cy(self):
        return self.y + NOTE_H / 2

    def in_hit_zone(self):
        d = abs(self.cy() - TARGET_Y)
        if d <= HIT_PERFECT: return "PERFECT"
        if d <= HIT_GOOD:    return "GOOD"
        return None

    def update(self, collapsed_outcomes: dict, player_idx: int, dt: float,
               collapse_y: int):
        """
        collapsed_outcomes: shared dict  nid → (p1_lane, p2_lane)
        player_idx: 0 = P1, 1 = P2  |  dt: seconds since last frame
        collapse_y: pre-computed collapse line (passed in, not recomputed here)
        """
        self.just_collapsed = False
        self.just_missed    = False
        self.y += self.speed * dt

        if self.quantum and not self.collapsed and self.y >= collapse_y:
            self.collapsed      = True
            self.just_collapsed = True
            # First note to collapse (could be P1 or P2) sets the shared outcome
            if self.nid not in collapsed_outcomes:
                a = self.lane if random.random() < get_collapse_bias() else self.lane2
                b = self.lane2 if a == self.lane else self.lane
                collapsed_outcomes[self.nid] = (a, b)
            self.final_lane   = collapsed_outcomes[self.nid][player_idx]
            self.dropped_lane = (self.lane2 if self.final_lane == self.lane
                                 else self.lane)
            self.lane = self.final_lane

        if (not self.hit and not self.missed
                and self.y > TARGET_Y + HIT_ZONE_H + 18):
            self.missed      = True
            self.just_missed = True
            self.alive       = False


# ─────────────────────────────────────────────────────────────────────────────
# Particle / FloatText  (surface-aware versions)
# ─────────────────────────────────────────────────────────────────────────────
# Lightweight particle tuning — kept cheap for Raspberry Pi:
#  - integer math only, plain draw.circle (no per-particle surfaces/alpha)
#  - hard cap on how many can exist per player at once
#  - smaller bursts in _LOW_PERF mode
_PARTICLE_MAX   = 40                     # hard cap per player
_BURST_HIT      = 4 if _LOW_PERF else 10
_BURST_MISS     = 3 if _LOW_PERF else 6
_BURST_COLLAPSE = 5 if _LOW_PERF else 12

class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "color", "size")

    def __init__(self, x, y, color, speed_scale=1.0):
        a  = random.uniform(0, math.tau)
        sp = random.uniform(1.5, 5.0) * speed_scale
        self.x, self.y   = float(x), float(y)
        self.vx, self.vy = math.cos(a) * sp, math.sin(a) * sp - 1.5
        self.life  = random.randint(14, 28)
        self.color = color
        self.size  = random.randint(2, 4)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.22          # gravity
        self.life -= 1

    def draw(self, surf):
        # No alpha fade — just shrink the dot as it dies (cheaper than blending)
        r = self.size if self.life > 6 else 1
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), r)

def _spawn_burst(plist, x, y, color, count, speed_scale=1.0):
    """Add up to `count` particles, respecting the per-player hard cap."""
    room = _PARTICLE_MAX - len(plist)
    for _ in range(min(count, max(0, room))):
        plist.append(Particle(x, y, color, speed_scale))


class FloatText:
    def __init__(self, text, x, y, color, font=None):
        # Convert to a per-pixel-alpha surface ONCE so we can set_alpha on it
        # directly each frame instead of copying it every draw call.
        self.surf     = (font or F_MED).render(text, True, color).convert_alpha()
        self.x        = float(x - self.surf.get_width() // 2)
        self.y        = float(y)
        self.life     = 52
        self.max_life = 52

    def update(self):
        self.y -= 1.3;  self.life -= 1

    def draw(self, surf):
        if self.life <= 0: return
        self.surf.set_alpha(int(255 * self.life / self.max_life))
        surf.blit(self.surf, (int(self.x), int(self.y)))


# ─────────────────────────────────────────────────────────────────────────────
# Per-player state container
# ─────────────────────────────────────────────────────────────────────────────
class PlayerState:
    def __init__(self, player_idx: int, keys: list, ctx: "RenderCtx" = None):
        self.idx       = player_idx
        self.keys      = keys
        self.ctx       = ctx  # layout context; set after make_ctx()
        self.notes     : list[Note]      = []
        self.particles : list[Particle]  = []
        self.floats    : list[FloatText] = []
        self.score     = 0
        self.combo     = 0
        self.max_combo = 0
        self.key_flash = [0] * N_LANES
        self.perfect_count  = 0
        self.good_count     = 0
        self.miss_count     = 0
        self.total_notes    = 0
        self.last_milestone = 0
        self.milestone_timer = 0
        self.milestone_text  = ""
        self.flash_timer     = 0

    def handle_key(self, key_idx: int):
        lane = key_idx
        self.key_flash[lane] = 14
        scx = _lcx(lane, self.ctx) if self.ctx else lcx(lane)

        best, best_d = None, 9999
        for note in self.notes:
            if not note.alive or note.hit: continue
            if note.quantum and not note.collapsed:
                in_lane = lane in (note.lane, note.lane2)
            else:
                in_lane = lane == note.lane
            if not in_lane: continue
            d = abs(note.cy() - TARGET_Y)
            if d < best_d: best_d, best = d, note

        if best is None or best_d > HIT_GOOD:
            self.combo = 0
            self.last_milestone = 0
            self.miss_count += 1
            self.floats.append(FloatText("MISS", scx, TARGET_Y - 42, RED))
            _spawn_burst(self.particles, scx, TARGET_Y, RED, _BURST_MISS)
            _play(SFX_MISS)
            return

        quality = best.in_hit_zone()
        if quality:
            best.hit = True; best.alive = False
            self.combo += 1
            if quality == "PERFECT":
                self.score += 300 * max(1, self.combo // 5)
                self.perfect_count += 1
                self.floats.append(FloatText("PERFECT!", scx, TARGET_Y - 42, GOLD, F_MED))
                _spawn_burst(self.particles, scx, TARGET_Y, LANE_C[lane], _BURST_HIT)
            else:
                self.score += 100 * max(1, self.combo // 10)
                self.good_count += 1
                self.floats.append(FloatText("GOOD", scx, TARGET_Y - 42, WHITE))
                _spawn_burst(self.particles, scx, TARGET_Y, LANE_C[lane], _BURST_MISS)
            for m in COMBO_MILESTONES:
                if self.combo >= m and self.last_milestone < m:
                    self.last_milestone  = m
                    self.milestone_text  = f"COMBO  ×{m}!"
                    self.milestone_timer = 90
                    self.flash_timer     = 8
                    _spawn_burst(self.particles, scx, TARGET_Y, GOLD, _BURST_COLLAPSE)
                    _play(SFX_MILESTONE)
        else:
            self.combo = 0
            self.last_milestone = 0
            self.miss_count += 1
            self.floats.append(FloatText("EARLY", scx, TARGET_Y - 42, (255, 180, 0)))
            _spawn_burst(self.particles, scx, TARGET_Y, (255, 180, 0), _BURST_MISS)
            _play(SFX_MISS)

    def update(self, collapsed_outcomes: dict, dt: float):
        collapse_y = get_collapse_y()   # computed once for all this player's notes
        for note in self.notes:
            note.update(collapsed_outcomes, self.idx, dt, collapse_y)
            if note.just_collapsed:
                cx = (_lcx(note.dropped_lane, self.ctx) if self.ctx
                      else lcx(note.dropped_lane))
                ny = int(note.y) + NOTE_H // 2
                self.floats.append(FloatText(
                    "COLLAPSED!", cx,
                    TARGET_Y - 42 + int(note.y - TARGET_Y) + NOTE_H // 2,
                    Q_PURPLE, F_SM))
                _spawn_burst(self.particles, cx, ny, Q_WAVE, _BURST_COLLAPSE, 1.2)
                _play(SFX_COLLAPSE)
            if note.just_missed:
                self.combo = 0
                self.last_milestone = 0
                self.miss_count += 1
                miss_cx = (_lcx(note.lane, self.ctx) if self.ctx else lcx(note.lane))
                self.floats.append(FloatText("MISS", miss_cx, TARGET_Y - 42, RED))
                _spawn_burst(self.particles, miss_cx, TARGET_Y, RED, _BURST_MISS)

        self.notes[:]  = [n for n in self.notes  if n.alive]
        self.max_combo = max(self.max_combo, self.combo)
        for p in self.particles: p.update()
        self.particles[:] = [p for p in self.particles if p.life > 0]
        for f in self.floats: f.update()
        self.floats[:]    = [f for f in self.floats    if f.life > 0]
        for i in range(N_LANES):
            if self.key_flash[i] > 0: self.key_flash[i] -= 1
        if self.milestone_timer > 0: self.milestone_timer -= 1
        if self.flash_timer     > 0: self.flash_timer     -= 1


# ─────────────────────────────────────────────────────────────────────────────
# Global game counters (shared across players)
# ─────────────────────────────────────────────────────────────────────────────
q_collapsed        = 0
q_total            = 0
tick               = 0
spawn_timer        = 0.9   # seconds until first note spawn
collapsed_outcomes : dict = {}   # nid → (p1_lane, p2_lane)
last_beat          = -1
_game_elapsed      = 0.0   # seconds since game started (fallback timer)
END_GRACE_S        = 2.0   # seconds to wait after the song ends before RESULTS
_end_timer         = -1.0  # counts up once the song is done (-1 = not started)

p1 : PlayerState = None
p2 : PlayerState = None


# ─────────────────────────────────────────────────────────────────────────────
# Spawner
# ─────────────────────────────────────────────────────────────────────────────
def _m(lane: int) -> int:
    """Mirror a lane index for P2: 0↔3, 1↔2."""
    return _P2_KEY_MAP[lane]


def spawn_note():
    global q_total
    if random.random() < 0.38:
        a, b = random.sample(range(N_LANES), 2)
        wp   = random.uniform(0, math.tau)
        Note._nid += 1
        nid = Note._nid
        p1.notes.append(Note(a, quantum=True, lane2=b, nid=nid, wave_phase=wp))
        p1.total_notes += 1
        if n_players == 2:
            p2.notes.append(Note(a, quantum=True, lane2=b, nid=nid, wave_phase=wp))
            p2.total_notes += 1
        q_total += 1
    else:
        lane = random.randint(0, N_LANES - 1)
        Note._nid += 1
        nid = Note._nid
        p1.notes.append(Note(lane, nid=nid))
        p1.total_notes += 1
        if n_players == 2:
            p2.notes.append(Note(_m(lane), nid=nid))
            p2.total_notes += 1


# ─────────────────────────────────────────────────────────────────────────────
# Draw helpers (surface-aware)
# ─────────────────────────────────────────────────────────────────────────────
def draw_panels(surf):
    pygame.draw.rect(surf, PANEL_BG, (0, LANE_TOP, LX0, LANE_BOT - LANE_TOP))
    pygame.draw.line(surf, (40, 32, 72), (LX0, LANE_TOP), (LX0, LANE_BOT), 1)
    pygame.draw.rect(surf, PANEL_BG, (RP_X, LANE_TOP, RP_W, LANE_BOT - LANE_TOP))
    pygame.draw.line(surf, (40, 32, 72), (RP_X, LANE_TOP), (RP_X, LANE_BOT), 1)
    lp_lbl = F_XSM.render("SPAWN RATE", True, (60, 55, 90))
    surf.blit(lp_lbl, (LX0 // 2 - lp_lbl.get_width() // 2, LANE_TOP + 8))
    rp_lbl = F_XSM.render("NOTE CONTROLS", True, (60, 55, 90))
    surf.blit(rp_lbl, (RP_X + RP_W // 2 - rp_lbl.get_width() // 2, LANE_TOP + 8))


def draw_lanes(surf, key_flash, ctx: RenderCtx, cy: int):
    # Starfield — skipped in LOW_PERF mode
    if not _LOW_PERF:
        for j, (sx, sy) in enumerate(_STARS_LANES):
            twinkle = 0.4 + 0.6 * math.sin(tick * 0.04 + j * 0.53)
            br = max(0, min(240, int(55 * twinkle)))
            pygame.draw.circle(surf, (br, br, min(255, br + 15)), (sx, sy), 1)

    for i in range(N_LANES):
        x    = _lx(i, ctx)
        rect = pygame.Rect(x, LANE_TOP, ctx.lane_w, LANE_BOT - LANE_TOP)
        pygame.draw.rect(surf, (6, 4, 18), rect)
        r, g, b = LANE_C[i]
        pygame.draw.line(surf, (r//3, g//3, b//3), (x, LANE_TOP), (x, LANE_BOT), 2)
        pygame.draw.line(surf, (r//3, g//3, b//3), (x + ctx.lane_w - 1, LANE_TOP),
                         (x + ctx.lane_w - 1, LANE_BOT), 2)
        if key_flash[i] > 0:
            pygame.draw.rect(surf, (r//3, g//3, b//3),
                             (x, LANE_TOP, ctx.lane_w, LANE_BOT - LANE_TOP))

    if not _LOW_PERF and _SCAN_LANES:
        surf.blit(_SCAN_LANES, (0, LANE_TOP))

    # Collapse zone (cy is computed once per frame by the caller)
    col_pulse = int(120 + 80 * math.sin(tick * 0.08))
    for i in range(N_LANES):
        x = _lx(i, ctx)
        pygame.draw.line(surf, (col_pulse, 20, col_pulse),
                         (x + 4, cy), (x + ctx.lane_w - 4, cy), 2)
    cl = _tcache(('czlbl', col_pulse // 20), "◆ COLLAPSE ZONE ◆", F_XSM, (col_pulse, 40, col_pulse))
    surf.blit(cl, (_lcx(0, ctx) - cl.get_width() // 2, cy - 15))


def draw_hit_zone(surf, ctx: RenderCtx):
    pulse = 0.7 + 0.3 * math.sin(tick * 0.10)
    for i in range(N_LANES):
        x       = _lx(i, ctx)
        scx     = _lcx(i, ctx)
        r, g, b = LANE_C[i]
        pr, pg, pb = int(r*pulse), int(g*pulse), int(b*pulse)
        hz = pygame.Rect(x + 4, TARGET_Y - HIT_ZONE_H // 2,
                         ctx.lane_w - 8, HIT_ZONE_H)
        pygame.draw.rect(surf, (r//6, g//6, b//6), hz, border_radius=10)
        pygame.draw.rect(surf, (pr, pg, pb),        hz, 3, border_radius=10)
        pygame.draw.line(surf, (pr, pg, pb),
                         (x + 6, TARGET_Y), (x + ctx.lane_w - 6, TARGET_Y), 3)
        ar = _ARROW_SURFS[i]
        surf.blit(ar, (scx - ar.get_width() // 2,
                       TARGET_Y + HIT_ZONE_H // 2 + 4))


def draw_classical(surf, note: Note, ctx: RenderCtx):
    # Single blit of a pre-baked body instead of 2 draw.rect + arrow blit.
    scx  = _lcx(note.lane, ctx)
    nw   = ctx.note_w
    body = _bake_note_body("classical", note.lane, nw)
    surf.blit(body, (scx - nw // 2, int(note.y)))


_Q_MARK_SURF = F_ARROW.render("?", True, Q_PURPLE)
_SUPER_SURF  = F_XSM.render("superposition", True, (180, 30, 220))

def draw_quantum(surf, note: Note, ctx: RenderCtx, cy_collapse: int):
    nw = ctx.note_w
    if note.collapsed:
        cx   = _lcx(note.lane, ctx)
        body = _bake_note_body("collapsed", note.lane, nw)
        surf.blit(body, (cx - nw // 2, int(note.y)))
        return

    dist    = max(0.0, cy_collapse - note.y)
    urgency = 1.0 - min(dist / 200.0, 1.0)
    pulse   = 0.55 + 0.45 * math.sin(tick * 0.14 + note.wave_phase)
    af      = 0.35 + 0.45 * pulse + 0.20 * urgency

    for gl in (note.lane, note.lane2):
        r, g, b = Q_PURPLE
        ri, gi, bi = int(r * af), int(g * af * 0.35), int(b * af)
        cx   = _lcx(gl, ctx)
        rect = pygame.Rect(cx - nw // 2, int(note.y), nw, NOTE_H)
        pygame.draw.rect(surf, (ri // 3, gi // 3, bi // 3), rect, border_radius=9)
        pygame.draw.rect(surf, (ri, gi, bi), rect, 2, border_radius=9)
        surf.blit(_Q_MARK_SURF, (cx - _Q_MARK_SURF.get_width() // 2,
                                  int(note.y) + (NOTE_H - _Q_MARK_SURF.get_height()) // 2))

    # Connecting line — 8 sample points instead of per-pixel loop
    xa, xb = _lcx(note.lane, ctx), _lcx(note.lane2, ctx)
    wy = int(note.y) + NOTE_H // 2
    x0, x1 = min(xa, xb), max(xa, xb)
    step = max(1, (x1 - x0) // 8)
    pts = []
    for xp in range(x0, x1 + 1, step):
        yp = wy + math.sin((xp - x0) * 0.22 + tick * 0.18 + note.wave_phase) \
             * (5 + 5 * urgency)
        pts.append((xp, int(yp)))
    if len(pts) >= 2:
        wr, wg, wb = Q_WAVE
        pygame.draw.lines(surf, (int(wr * af), int(wg * af * 0.5), int(wb * af)),
                          False, pts, 2)

    if dist > 60:
        mx = (xa + xb) // 2
        surf.blit(_SUPER_SURF, (mx - _SUPER_SURF.get_width() // 2, int(note.y) - 17))


def draw_top(surf, ps: PlayerState, ctx: RenderCtx, label: str = ""):
    sw = ctx.sw
    pygame.draw.rect(surf, (4, 2, 14), (0, 0, sw, TOP_H))
    # Pre-baked animated border (30-frame cycle, plain surface blit)
    surf.blit(_TOP_BORDER_FRAMES[tick % 30], (0, TOP_H - 6))

    # Rainbow cycling title — cached per character/color combo
    title_str = "QUANTUM DANCE" + (f"  —  {label}" if label else "")
    tx = sw // 2 - sum(F_TITLE.size(ch)[0] for ch in title_str) // 2
    for i, ch in enumerate(title_str):
        hue = (tick * 2 + i * 20) % 360
        h = hue / 60.0
        xv = int(255 * (1 - abs(h % 2 - 1)))
        if   h < 1: r2,g2,b2 = 255, xv,  0
        elif h < 2: r2,g2,b2 =  xv,255,  0
        elif h < 3: r2,g2,b2 =   0,255, xv
        elif h < 4: r2,g2,b2 =   0, xv,255
        elif h < 5: r2,g2,b2 =  xv,  0,255
        else:       r2,g2,b2 = 255,  0, xv
        cs = _rainbow_char(ch, r2, g2, b2, F_TITLE)
        surf.blit(cs, (tx, 6))
        tx += cs.get_width()

    sc = _tcache(('score', id(ps)), f"SCORE  {ps.score:07d}", F_MED, GOLD)
    surf.blit(sc, (10, 48))

    combo_col = GOLD if ps.combo >= 10 else WHITE
    cb = _tcache(('combo', id(ps)), f"×{ps.combo}  COMBO", F_MED, combo_col)
    surf.blit(cb, (sw - cb.get_width() - 10, 48))

    qc = _tcache('collapses', f"collapses  {q_collapsed}/{q_total}", F_XSM, (170, 70, 230))
    surf.blit(qc, (sw // 2 - qc.get_width() // 2, 52))


def draw_bottom(surf, ctx: RenderCtx):
    sw = ctx.sw
    y0 = SH - BOT_H
    pygame.draw.rect(surf, (4, 2, 14), (0, y0, sw, BOT_H))
    # Pre-baked animated border
    surf.blit(_BOT_BORDER_FRAMES[tick % 30], (0, y0))

    pct = int(bias_slider.val)
    bias_txt = f"⬡  Quantum — 2 lanes  |  {pct}% lane 1 / {100-pct}% lane 2"
    surf.blit(_tcache('cl_txt', "■  Classical — stays in its lane", F_XSM, (180, 220, 255)),
              (14, y0 + 14))
    surf.blit(_tcache('bias_txt', bias_txt, F_XSM, (200, 100, 255)),
              (14, y0 + 32))

    if n_players == 2:
        hint = _tcache('2p_hint', "2P: entangled collapse — opposite lanes", F_XSM, (170, 70, 230))
        surf.blit(hint, (sw - hint.get_width() - 14, y0 + 14))
        ctrl = _tcache('2p_ctrl', "P2: A ↔  S ↓  W ↑  D →", F_XSM, DIM)
        surf.blit(ctrl, (sw - ctrl.get_width() - 14, y0 + 32))
    else:
        for i, (k, line) in enumerate([
            ('q_line1', "Quantum: particle exists in multiple"),
            ('q_line2', "states until MEASURED  ⬡"),
        ]):
            t = _tcache(k, line, F_XSM, DIM)
            surf.blit(t, (sw - t.get_width() - 14, y0 + 14 + i * 17))


# ─────────────────────────────────────────────────────────────────────────────
# Arcade retro menu
# ─────────────────────────────────────────────────────────────────────────────
_menu_tick = 0   # animated frame counter

def draw_menu():
    global _menu_tick
    _menu_tick += 1
    t = _menu_tick

    screen.fill((4, 2, 14))

    # ── Starfield — skipped in LOW_PERF ──────────────────────────────────────
    if not _LOW_PERF:
        for j, (sx, sy) in enumerate(_STARS_MENU):
            twinkle = 0.5 + 0.5 * math.sin(t * 0.05 + j * 0.41)
            br = max(0, min(235, int(80 * twinkle)))
            pygame.draw.circle(screen, (br, br, min(255, br + 20)), (sx, sy), 1)
        if _SCAN_FULL:
            screen.blit(_SCAN_FULL, (0, 0))

    # ── Marquee border (pre-baked frame cycle) ────────────────────────────────
    screen.blit(_TOP_BORDER_FRAMES[t % 30], (0, 0))
    screen.blit(_TOP_BORDER_FRAMES[t % 30], (0, SH - 6))

    # ── Blinking "INSERT COIN" ────────────────────────────────────────────────
    if (t // 22) % 2 == 0:
        coin = _tcache('insert_coin', "► INSERT COIN ◄", F_MENUSM, (255, 230, 0))
        screen.blit(coin, (SW // 2 - coin.get_width() // 2, 28))

    # ── Rainbow cycling title — cached chars ─────────────────────────────────
    title_str = "QUANTUM  DANCE"
    total_w = sum(F_BIG.size(ch)[0] for ch in title_str)
    tx = SW // 2 - total_w // 2
    ty = SH // 2 - 200 + int(6 * math.sin(t * 0.06))
    for i, ch in enumerate(title_str):
        hue = (t * 2 + i * 18) % 360
        h = hue / 60.0
        xv = int(255 * (1 - abs(h % 2 - 1)))
        if   h < 1: r,g,b = 255, xv,  0
        elif h < 2: r,g,b =  xv,255,  0
        elif h < 3: r,g,b =   0,255, xv
        elif h < 4: r,g,b =   0, xv,255
        elif h < 5: r,g,b =  xv,  0,255
        else:       r,g,b = 255,  0, xv
        cs = _rainbow_char(ch, r, g, b, F_BIG)
        screen.blit(cs, (tx, ty))
        tx += cs.get_width()

    # ── Subtitle — quantized color to reduce re-renders ──────────────────────
    sub_bucket = (t // 8) % 45
    sub_col = (max(0, min(255, int(160 + 60 * math.sin(sub_bucket * 0.14)))),
               max(0, min(255, int(100 + 60 * math.sin(sub_bucket * 0.14 + 1)))),
               max(0, min(255, int(200 + 55 * math.sin(sub_bucket * 0.14 + 2)))))
    sub = _tcache(('menu_sub', sub_bucket), "CLASSICAL  vs  QUANTUM  COMPUTING",
                  F_MENUSM, sub_col)
    screen.blit(sub, (SW // 2 - sub.get_width() // 2, SH // 2 - 130))

    # ── Buttons — highlight selected player count ─────────────────────────────
    btn_w, btn_h = 300, 64
    gap  = 22
    bx   = SW // 2 - btn_w // 2
    by1  = SH // 2 - 30
    by2  = by1 + btn_h + gap
    mx, my = pygame.mouse.get_pos()
    pulse = 0.7 + 0.3 * math.sin(t * 0.10)

    for idx, (by, label, key_hint, base_col) in enumerate([
        (by1, "1  PLAYER",  "PRESS  1", (0, 180, 255)),
        (by2, "2  PLAYERS", "PRESS  2", (255, 80, 200)),
    ]):
        rect     = pygame.Rect(bx, by, btn_w, btn_h)
        hover    = rect.collidepoint(mx, my)
        selected = (idx + 1) == n_players   # highlight currently selected mode
        active   = selected or hover
        r, g, b  = base_col
        bcol     = (int(r * pulse), int(g * pulse), int(b * pulse))

        glow = _get_btn_glow(btn_w, btn_h, base_col)
        glow.set_alpha(int(240 * pulse) if active else int(60 * pulse))
        screen.blit(glow, (bx - 18, by - 18))

        fill = (int(r*0.35), int(g*0.35), int(b*0.35)) if selected else (int(r*0.12), int(g*0.12), int(b*0.12))
        border_w = 3 if selected else 2
        pygame.draw.rect(screen, fill, rect, border_radius=8)
        pygame.draw.rect(screen, bcol, rect, border_w, border_radius=8)

        # Arrow indicator on selected row
        if selected:
            arrow = _tcache(('menu_sel_arrow', idx), "►", F_MENU, WHITE)
            screen.blit(arrow, (bx - arrow.get_width() - 10,
                                rect.centery - arrow.get_height() // 2))

        lbl  = _tcache(('btn_lbl', label, active), label, F_MENU, WHITE if active else bcol)
        hint = _tcache(('btn_hint', key_hint), key_hint, F_XSM, (120, 110, 160))
        screen.blit(lbl,  (rect.centerx - lbl.get_width() // 2,
                           rect.centery - lbl.get_height() // 2))
        screen.blit(hint, (rect.right + 12, rect.centery - hint.get_height() // 2))

    # ── Arrow decoration — use pre-baked arrow surfaces ───────────────────────
    arrow_y = SH // 2 + 110
    for i, ar in enumerate(_ARROW_SURFS):
        bounce = int(5 * math.sin(t * 0.12 + i * 0.8))
        ax = SW // 2 - 90 + i * 60
        screen.blit(ar, (ax - ar.get_width() // 2, arrow_y + bounce))

    # ── Bottom hint ───────────────────────────────────────────────────────────
    ctrl = _tcache('menu_ctrl', "P1: ← ↓ ↑ →     2P adds: A S W D",
                   F_XSM, (70, 60, 100))
    screen.blit(ctrl, (SW // 2 - ctrl.get_width() // 2, SH - 28))

    pygame.display.flip()
    return (pygame.Rect(bx, by1, btn_w, btn_h),
            pygame.Rect(bx, by2, btn_w, btn_h))


# ─────────────────────────────────────────────────────────────────────────────
# Song select screen
# ─────────────────────────────────────────────────────────────────────────────
def draw_song_select(cursor: int, num_players: int) -> list:
    """Draw song list; returns list of row rects for click detection."""
    t = _menu_tick
    screen.fill((4, 2, 14))

    # Starfield — skipped in LOW_PERF
    if not _LOW_PERF:
        for j, (sx, sy) in enumerate(_STARS_SEL):
            twinkle = 0.4 + 0.6 * math.sin(t * 0.04 + j * 0.47)
            br = max(0, min(240, int(50 * twinkle)))
            pygame.draw.circle(screen, (br, br, min(255, br + 15)), (sx, sy), 1)
        if _SCAN_FULL:
            screen.blit(_SCAN_FULL, (0, 0))

    # Marquee border — pre-baked
    screen.blit(_TOP_BORDER_FRAMES[t % 30], (0, 0))
    screen.blit(_TOP_BORDER_FRAMES[t % 30], (0, SH - 6))

    # Rainbow title — use cache
    title_str = "SELECT  SONG"
    tx = SW // 2 - sum(F_TITLE.size(ch)[0] for ch in title_str) // 2
    for i, ch in enumerate(title_str):
        hue = (t * 2 + i * 22) % 360
        h = hue / 60.0
        x2 = int(255 * (1 - abs(h % 2 - 1)))
        if   h < 1: rc,gc,bc = 255, x2,  0
        elif h < 2: rc,gc,bc =  x2,255,  0
        elif h < 3: rc,gc,bc =   0,255, x2
        elif h < 4: rc,gc,bc =   0, x2,255
        elif h < 5: rc,gc,bc =  x2,  0,255
        else:       rc,gc,bc = 255,  0, x2
        cs = _rainbow_char(ch, rc, gc, bc, F_TITLE)
        screen.blit(cs, (tx, 26)); tx += cs.get_width()

    mode_key = '1p_mode' if num_players == 1 else '2p_mode'
    mode_lbl = _tcache(mode_key,
        f"{'1 PLAYER' if num_players == 1 else '2 PLAYERS'}  —  choose a track",
        F_MENUSM, (140, 100, 200))
    screen.blit(mode_lbl, (SW // 2 - mode_lbl.get_width() // 2, 72))

    mx, my = pygame.mouse.get_pos()
    row_h  = 72
    row_w  = 720
    rx0    = (SW - row_w) // 2
    ry0    = 118
    rects  = []

    for i, song in enumerate(SONGS):
        ry     = ry0 + i * row_h
        rect   = pygame.Rect(rx0, ry, row_w, row_h - 6)
        hover  = rect.collidepoint(mx, my)
        active = i == cursor

        if active:
            ap = 0.7 + 0.3 * math.sin(t * 0.10)
            fill   = (int(50*ap), int(15*ap), int(90*ap))
            border = tuple(min(255, int(v*ap)) for v in Q_PURPLE)
        else:
            fill   = (22, 12, 44) if hover else (12, 8, 28)
            border = (120, 60, 180) if hover else (40, 28, 70)

        # Glow on active — pre-baked surface
        if active:
            glow = _get_row_glow(row_w, row_h - 6)
            glow.set_alpha(int(180 * (0.7 + 0.3 * math.sin(t * 0.10))))
            screen.blit(glow, (rx0 - 8, ry - 8))

        pygame.draw.rect(screen, fill,   rect, border_radius=10)
        pygame.draw.rect(screen, border, rect, 2 if active else 1, border_radius=10)
        rects.append(rect)

        nc = WHITE if active else (180, 100, 255)
        num_s = _tcache(('snum', i, active), f"{i + 1}", F_MED, nc)
        screen.blit(num_s, (rx0 + 18, ry + (row_h - 6 - num_s.get_height()) // 2))

        tc = WHITE if active else (200, 180, 240)
        title_s  = _tcache(('stitle', i, active), song["title"],  F_MED, tc)
        artist_s = _tcache(('sartist', i),         song["artist"], F_SM,  (120, 100, 180))
        screen.blit(title_s,  (rx0 + 50, ry + 8))
        screen.blit(artist_s, (rx0 + 50, ry + 8 + title_s.get_height()))

        bpm_s = _tcache(('sbpm', i), f"{song['bpm']} BPM", F_SM, (80, 180, 255))
        screen.blit(bpm_s, (rx0 + row_w - 210, ry + (row_h - 6 - bpm_s.get_height()) // 2))

        diff   = song["difficulty"]
        dc     = DIFF_COLOR[diff]
        diff_s = F_SM.render(diff, True, dc)
        bw, bh = diff_s.get_width() + 16, diff_s.get_height() + 6
        bx_    = rx0 + row_w - bw - 12
        by_    = ry + (row_h - 6 - bh) // 2
        pygame.draw.rect(screen, (dc[0]//6, dc[1]//6, dc[2]//6),
                         (bx_, by_, bw, bh), border_radius=6)
        pygame.draw.rect(screen, dc, (bx_, by_, bw, bh), 1, border_radius=6)
        screen.blit(diff_s, (bx_ + 8, by_ + 3))

    hint = _tcache('sel_hint',
                   "↑↓ navigate   START play   ←→ high scores   SELECT back",
                   F_XSM, (70, 55, 100))
    screen.blit(hint, (SW // 2 - hint.get_width() // 2, ry0 + len(SONGS) * row_h + 8))

    pygame.display.flip()
    return rects


# ─────────────────────────────────────────────────────────────────────────────
# Results helpers — kid-friendly star rating
# ─────────────────────────────────────────────────────────────────────────────
def _stars(accuracy: float) -> int:
    if accuracy >= 0.90: return 5
    if accuracy >= 0.70: return 4
    if accuracy >= 0.50: return 3
    if accuracy >= 0.30: return 2
    return 1

def _star_message(n: int) -> tuple:
    return [
        ("Keep trying!",   (200, 180, 100)),
        ("Nice try!",      (200, 180, 100)),
        ("Good job!",      (100, 220, 255)),
        ("Great!",         (100, 255, 150)),
        ("AMAZING!",       GOLD),
        ("PERFECT!!",      GOLD),
    ][n]

def _draw_star(surf, cx, cy, r, filled, col):
    pts = []
    for i in range(10):
        angle = math.pi / 2 + i * math.tau / 10
        radius = r if i % 2 == 0 else r * 0.42
        pts.append((cx + math.cos(angle) * radius,
                    cy - math.sin(angle) * radius))
    if filled:
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, (255, 255, 200), pts, 1)
    else:
        pygame.draw.polygon(surf, (60, 50, 90), pts)
        pygame.draw.polygon(surf, (80, 70, 110), pts, 1)

def _draw_results_panel(surf, ps: PlayerState, cx: int, cy: int, title: str):
    total = max(1, ps.total_notes)
    hits  = ps.perfect_count + ps.good_count
    acc   = hits / total
    n_st  = _stars(acc)
    msg, mcol = _star_message(n_st)

    if title:
        lbl = F_MED.render(title, True, Q_PURPLE)
        surf.blit(lbl, (cx - lbl.get_width() // 2, cy - 190))

    # Stars
    star_r = 28
    star_gap = 70
    star_y = cy - 130
    for i in range(5):
        sx = cx + (i - 2) * star_gap
        filled = i < n_st
        col = GOLD if filled else (50, 40, 70)
        _draw_star(surf, sx, star_y, star_r, filled, col)

    # Message
    msg_surf = F_TITLE.render(msg, True, mcol)
    surf.blit(msg_surf, (cx - msg_surf.get_width() // 2, cy - 78))

    # Score (big)
    sc_surf = F_TITLE.render(f"{ps.score:,}", True, GOLD)
    surf.blit(sc_surf, (cx - sc_surf.get_width() // 2, cy - 30))
    sc_lbl = F_SM.render("SCORE", True, DIM)
    surf.blit(sc_lbl, (cx - sc_lbl.get_width() // 2, cy + 14))

    # Stats row
    for i, (icon, val, col) in enumerate([
        ("★ PERFECT", str(ps.perfect_count), (100, 255, 150)),
        ("◆ GOOD",    str(ps.good_count),    (80, 200, 255)),
        ("✕ MISS",    str(ps.miss_count),    (180, 80, 80)),
        ("⚡ COMBO",  f"×{ps.max_combo}",    GOLD),
    ]):
        bx = cx - 140 + i * 72
        by = cy + 46
        pygame.draw.rect(surf, (20, 15, 40), (bx, by, 64, 42), border_radius=6)
        pygame.draw.rect(surf, (50, 40, 80), (bx, by, 64, 42), 1, border_radius=6)
        v = F_MED.render(val, True, col)
        k = F_XSM.render(icon, True, DIM)
        surf.blit(v, (bx + 32 - v.get_width() // 2, by + 4))
        surf.blit(k, (bx + 32 - k.get_width() // 2, by + 26))


def draw_results():
    screen.fill(BG)

    # Subtle star field behind results
    # Pre-baked starfield positions (no random.Random each frame)
    for sx, sy in _STARS_RESULTS:
        pygame.draw.circle(screen, (40, 35, 65), (sx, sy), 1)

    title = _tcache('res_title', "✦  GREAT GAME!  ✦", F_TITLE, Q_PURPLE)
    screen.blit(title, (SW // 2 - title.get_width() // 2, 22))

    if last_song:
        song_lbl = _tcache('res_song',
            f"{last_song['title']}  —  {last_song['artist']}", F_MED, DIM)
        screen.blit(song_lbl, (SW // 2 - song_lbl.get_width() // 2, 62))

    if n_players == 2 and p2:
        _draw_results_panel(screen, p1, SW // 4,     SH // 2 + 20, "PLAYER 1")
        _draw_results_panel(screen, p2, SW * 3 // 4, SH // 2 + 20, "PLAYER 2")
        pygame.draw.line(screen, (50, 40, 80), (SW // 2, 95), (SW // 2, SH - 55), 1)
    else:
        _draw_results_panel(screen, p1, SW // 2, SH // 2 + 20, "")

    # Top-5 leaderboard for this song, along the bottom
    if last_song:
        _draw_board_list(screen, last_song["title"], SW // 2, SH - 200, compact=True)

    hint = _tcache('res_hint', "START / R  play again     SELECT / ESC  menu",
                   F_SM, (80, 70, 120))
    screen.blit(hint, (SW // 2 - hint.get_width() // 2, SH - 40))
    pygame.display.flip()


def _draw_board_list(surf, song_title: str, cx: int, top_y: int,
                     compact: bool = False, highlight: str = None):
    """Draw a song's top-5 list centered at cx, starting at top_y."""
    board = _board_for(song_title)
    hdr = _tcache(('board_hdr', song_title[:6]), "TOP 5", F_MED, GOLD)
    surf.blit(hdr, (cx - hdr.get_width() // 2, top_y))
    row_h = 26 if compact else 34
    y = top_y + 32
    if not board:
        empty = _tcache('board_empty', "no scores yet — be the first!", F_SM, DIM)
        surf.blit(empty, (cx - empty.get_width() // 2, y))
        return
    for i, e in enumerate(board):
        is_hi = (highlight is not None and e["name"] == highlight)
        col = GOLD if is_hi else (200, 190, 230) if i == 0 else (150, 140, 190)
        rank = f"{i+1}."
        line = f"{rank}  {e['name']:<10}  {e['score']:>7,}"
        # Use a monospace-ish render via the regular font (names padded)
        surf_line = (F_MED if not compact else F_SM).render(line, True, col)
        surf.blit(surf_line, (cx - surf_line.get_width() // 2, y + i * row_h))


def draw_name_entry():
    """Arcade 3-initial entry screen (also accepts keyboard typing)."""
    screen.fill(BG)
    for sx, sy in _STARS_RESULTS:
        pygame.draw.circle(screen, (40, 35, 65), (sx, sy), 1)

    t = _tcache('ne_title', "NEW HIGH SCORE!", F_TITLE, GOLD)
    screen.blit(t, (SW // 2 - t.get_width() // 2, SH // 4 - 40))

    if _entry_label:
        pl = _tcache(('ne_label', _entry_label), _entry_label, F_MENU, Q_PURPLE)
        screen.blit(pl, (SW // 2 - pl.get_width() // 2, SH // 4 + 10))

    sc = _tcache(('ne_score', _entry_score), f"{_entry_score:,}", F_BIG, WHITE)
    screen.blit(sc, (SW // 2 - sc.get_width() // 2, SH // 4 + 56))

    # If the player has typed a keyboard name, show that; else show the 3 reels
    cy = SH // 2 + 70
    if _entry_typed:
        name_s = _entry_typed.upper() + ("_" if (pygame.time.get_ticks() // 400) % 2 else " ")
        ns = F_BIG.render(name_s, True, GOLD)
        screen.blit(ns, (SW // 2 - ns.get_width() // 2, cy))
        hint = "type name   ENTER confirm   BACKSPACE delete"
    else:
        slot_w = 90
        x0 = SW // 2 - slot_w * 3 // 2
        for i in range(3):
            ch = _entry_initials[i]
            box = pygame.Rect(x0 + i * slot_w + 10, cy - 10, slot_w - 20, 84)
            active = (i == _entry_pos)
            pygame.draw.rect(screen, (30, 20, 55) if active else (18, 12, 34),
                             box, border_radius=8)
            pygame.draw.rect(screen, GOLD if active else (80, 70, 110),
                             box, 3 if active else 1, border_radius=8)
            cs = F_BIG.render(ch if ch != " " else "_", True,
                              WHITE if active else (170, 160, 200))
            screen.blit(cs, (box.centerx - cs.get_width() // 2,
                             box.centery - cs.get_height() // 2))
            if active:
                up = F_SM.render("▲", True, GOLD); dn = F_SM.render("▼", True, GOLD)
                screen.blit(up, (box.centerx - up.get_width() // 2, box.top - 24))
                screen.blit(dn, (box.centerx - dn.get_width() // 2, box.bottom + 4))
        hint = "▲▼ change letter    START / → next    SELECT confirm"

    hs = _tcache(('ne_hint', _entry_typed != ""), hint, F_SM, (110, 100, 150))
    screen.blit(hs, (SW // 2 - hs.get_width() // 2, SH - 60))
    pygame.display.flip()


def draw_leaderboard():
    """Full-screen leaderboard for the highlighted song (from song select)."""
    screen.fill(BG)
    for sx, sy in _STARS_RESULTS:
        pygame.draw.circle(screen, (40, 35, 65), (sx, sy), 1)
    song = SONGS[_leader_view_idx]
    t = _tcache(('lb_title', _leader_view_idx), "HIGH SCORES", F_TITLE, Q_PURPLE)
    screen.blit(t, (SW // 2 - t.get_width() // 2, 40))
    sub = _tcache(('lb_song', _leader_view_idx),
                  f"{song['title']} — {song['artist']}", F_MENUSM, DIM)
    screen.blit(sub, (SW // 2 - sub.get_width() // 2, 92))
    _draw_board_list(screen, song["title"], SW // 2, SH // 2 - 80)
    hint = _tcache('lb_hint', "SELECT / ESC  back", F_SM, (110, 100, 150))
    screen.blit(hint, (SW // 2 - hint.get_width() // 2, SH - 50))
    pygame.display.flip()


# ─────────────────────────────────────────────────────────────────────────────
# Game init / reset
# ─────────────────────────────────────────────────────────────────────────────
def start_game(num_players: int, song: dict):
    global n_players, game_state, p1, p2, last_song
    global q_collapsed, q_total, tick, spawn_timer, collapsed_outcomes, last_beat, _game_elapsed
    global win2, ren2, surf2
    global SONG_FILE, SONG_BPM, SONG_OFFSET, SONG_DURATION, _active_beats_fall
    global two_screen_mode, split_mode, ctx1, ctx2, _end_timer
    last_song = song

    n_players  = num_players
    game_state = GameState.PLAYING

    # Apply song settings
    SONG_FILE          = song["file"]
    SONG_BPM           = float(song["bpm"])
    SONG_OFFSET        = float(song["offset"])
    SONG_DURATION      = float(song.get("duration", 120))
    speed_mult         = DIFF_SPEED[song["difficulty"]]
    _active_beats_fall = max(2.0, BEATS_TO_FALL / speed_mult)

    # Stop menu music (channel 14 reserved; stop all non-music channels)
    pygame.mixer.stop()   # stops all channels so menu jingle doesn't overlap song

    q_collapsed    = 0
    q_total        = 0
    tick           = 0
    spawn_timer    = 0.9   # seconds
    collapsed_outcomes = {}
    last_beat      = -1
    _game_elapsed  = 0.0
    _end_timer     = -1.0   # reset end-of-song grace timer
    Note._nid      = 0

    # Don't destroy win2 here — we reuse the logo window as P2 window for 2P
    win2 = ren2 = surf2 = None
    two_screen_mode = False
    split_mode      = False

    if num_players == 2:
        if _win_logo and _ren_logo and _surf_logo:
            # Reuse the permanent logo window as the P2 gameplay window
            two_screen_mode = True
            split_mode      = False
            win2  = _win_logo
            ren2  = _ren_logo
            surf2 = _surf_logo
            ctx1  = make_ctx(SW)
            ctx2  = make_ctx(SW)
        else:
            # No second monitor — split 50/50
            split_mode = True
            ctx1 = make_ctx(SW // 2)
            ctx2 = make_ctx(SW // 2)
    else:
        ctx1 = make_ctx(SW)
        ctx2 = None

    p1 = PlayerState(0, KEYS_P1, ctx1)
    p2 = PlayerState(1, KEYS_P2, ctx2) if num_players == 2 else None

    # Music
    if SONG_FILE:
        try:
            pygame.mixer.music.set_volume(1.0)
            pygame.mixer.music.load(SONG_FILE)
            pygame.mixer.music.play()
            try:
                with open('/tmp/audio_debug.txt', 'a') as _dbg:
                    _dbg.write(f"music_load={SONG_FILE}\n")
                    _dbg.write(f"music_busy={pygame.mixer.music.get_busy()}\n")
            except Exception:
                pass
        except Exception as e:
            print(f"[WARNING] Could not load music: {e}")
            try:
                with open('/tmp/audio_debug.txt', 'a') as _dbg:
                    _dbg.write(f"music_error={e}\n")
            except Exception:
                pass


def stop_game():
    global game_state, win2, ren2, surf2, SONG_FILE
    global two_screen_mode, split_mode, ctx1, ctx2
    game_state = GameState.MENU
    try: pygame.mixer.music.stop()
    except Exception: pass
    SONG_FILE = None
    # Don't destroy win2 — it's the permanent logo window (_win_logo).
    # Just clear the gameplay references so the logo resumes showing.
    win2 = ren2 = surf2 = None
    two_screen_mode = False
    split_mode      = False
    ctx1 = ctx2 = None


# ─────────────────────────────────────────────────────────────────────────────
# Per-frame update
# ─────────────────────────────────────────────────────────────────────────────
def update(dt: float, music_pos_ms: int = -1):
    global spawn_timer, q_collapsed, tick, last_beat, _game_elapsed

    tick += 1
    _game_elapsed += dt   # actual elapsed seconds, not fixed 1/FPS

    # Spawning
    if music_pos_ms >= 0:
        # Beat-synced spawning while the song is playing
        beat_time = max(0.0, music_pos_ms / 1000.0 - SONG_OFFSET)
        cur_beat  = int(beat_time * SONG_BPM / 60.0)
        # Catch up on any beats missed during a slow frame
        for b in range(last_beat + 1, cur_beat + 1):
            if b % BEATS_PER_NOTE == 0:
                spawn_note()
        if cur_beat > last_beat:
            last_beat = cur_beat
    elif SONG_FILE is None:
        # Free-play mode (no song loaded) — timer-based spawning.
        # NOTE: when a SONG_FILE exists but the music has stopped, we
        # intentionally spawn nothing so the lanes drain and RESULTS shows.
        spawn_timer -= dt
        if spawn_timer <= 0:
            spawn_note()
            base_sec    = get_spawn_interval() / 60.0   # frames→seconds
            spawn_timer = random.uniform(base_sec * 0.78, base_sec * 1.35)

    p1.update(collapsed_outcomes, dt)
    if p2: p2.update(collapsed_outcomes, dt)


def _render_player(surf, ps: PlayerState, ctx: RenderCtx, label: str = ""):
    sw = ctx.sw
    cy_collapse = get_collapse_y()   # computed ONCE per player per frame
    surf.fill((4, 2, 14))
    draw_lanes(surf, ps.key_flash, ctx, cy_collapse)
    draw_hit_zone(surf, ctx)

    for note in ps.notes:
        if note.quantum:
            draw_quantum(surf, note, ctx, cy_collapse)
        else:
            draw_classical(surf, note, ctx)

    for p in ps.particles: p.draw(surf)
    for f in ps.floats:    f.draw(surf)

    draw_top(surf, ps, ctx, label)
    draw_bottom(surf, ctx)

    # Milestone banner
    if ps.milestone_timer > 0:
        alpha = int(255 * ps.milestone_timer / 90)
        bsurf = _tcache(('milestone', id(ps)), ps.milestone_text, F_TITLE, Q_PURPLE).copy()
        bsurf.set_alpha(alpha)
        surf.blit(bsurf, (sw // 2 - bsurf.get_width() // 2, SH // 2 - 30))

    # Screen flash on milestone — plain surface with set_alpha (no SRCALPHA)
    if ps.flash_timer > 0:
        fsurf = pygame.Surface((sw, SH))
        fsurf.fill((255, 255, 255))
        fsurf.set_alpha(int(60 * ps.flash_timer / 8))
        surf.blit(fsurf, (0, 0))



# ─────────────────────────────────────────────────────────────────────────────
# Collapse counting (shared, tracked by P1 note just_collapsed events)
# ─────────────────────────────────────────────────────────────────────────────
# We count in the main loop after p1.update() using a seen-nids set.
_seen_collapsed_nids: set = set()


# ─────────────────────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────────────────────
def main():
    global game_state, q_collapsed, _seen_collapsed_nids
    global n_players, song_cursor, last_song, _end_timer
    global _entry_pos, _entry_typed, _entry_initials, _leader_view_idx
    btn1_rect = btn2_rect = None
    song_rects: list = []

    # Open logo window on second monitor immediately at startup
    _open_logo_window()

    _menu_music_ch = None   # channel playing menu music loop

    while True:
        dt = min(clk.tick(30 if _LOW_PERF else FPS) / 1000.0, 0.05)

        # ── MENU ──────────────────────────────────────────────────────────────
        if game_state == GameState.MENU:
            # Start menu music loop if not already playing
            if _sfx_ok and SFX_MENU_MUSIC and (
                    _menu_music_ch is None or not _menu_music_ch.get_busy()):
                _menu_music_ch = SFX_MENU_MUSIC.play(-1)  # -1 = loop forever
            btn1_rect, btn2_rect = draw_menu()
            _present_logo()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        pygame.quit(); sys.exit()
                    elif event.key in (pygame.K_UP, pygame.K_DOWN,
                                       pygame.K_LEFT, pygame.K_RIGHT):
                        n_players = 2 if n_players == 1 else 1
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        song_cursor = 0
                        game_state  = GameState.SONG_SELECT
                    elif event.key == pygame.K_1:
                        n_players   = 1
                        song_cursor = 0
                        game_state  = GameState.SONG_SELECT
                    elif event.key == pygame.K_2:
                        n_players   = 2
                        song_cursor = 0
                        game_state  = GameState.SONG_SELECT
                    elif (event.key == pygame.K_DELETE
                          and (pygame.key.get_mods() & pygame.KMOD_SHIFT)):
                        # Shift+Delete on the menu = wipe all leaderboards
                        _leaderboard.clear()
                        _save_leaderboard()
                        print("[INFO] Leaderboards cleared")
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if btn1_rect and btn1_rect.collidepoint(event.pos):
                        n_players   = 1
                        song_cursor = 0
                        game_state  = GameState.SONG_SELECT
                    elif btn2_rect and btn2_rect.collidepoint(event.pos):
                        n_players   = 2
                        song_cursor = 0
                        game_state  = GameState.SONG_SELECT
                elif event.type == pygame.JOYBUTTONDOWN:
                    if event.button in (MAT_UP, MAT_DOWN, MAT_LEFT, MAT_RIGHT):
                        n_players = 2 if n_players == 1 else 1
                        _play(SFX_NAV)
                    elif event.button == MAT_START:
                        _play(SFX_CONFIRM)
                        if _menu_music_ch: _menu_music_ch.stop()
                        song_cursor = 0
                        game_state  = GameState.SONG_SELECT
            continue

        # ── SONG SELECT ───────────────────────────────────────────────────────
        if game_state == GameState.SONG_SELECT:
            # Preview the highlighted song (loops back if the fragment ends)
            if _menu_music_ch:
                _menu_music_ch.stop()        # silence the menu jingle while previewing
            if _preview_idx != song_cursor or not pygame.mixer.music.get_busy():
                _start_preview(SONGS[song_cursor], song_cursor)

            song_rects = draw_song_select(song_cursor, n_players)
            _present_logo()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        _stop_preview()
                        game_state = GameState.MENU
                    elif event.key == pygame.K_UP:
                        song_cursor = (song_cursor + 1) % len(SONGS)
                    elif event.key == pygame.K_DOWN:
                        song_cursor = (song_cursor - 1) % len(SONGS)
                    elif event.key == pygame.K_RETURN:
                        _stop_preview()
                        start_game(n_players, SONGS[song_cursor])
                    elif event.key == pygame.K_TAB:           # view scores
                        _stop_preview()
                        _leader_view_idx = song_cursor
                        game_state = GameState.LEADERBOARD
                    else:
                        for idx in range(len(SONGS)):
                            if event.key == getattr(pygame, f"K_{idx + 1}", None):
                                song_cursor = idx
                                _stop_preview()
                                start_game(n_players, SONGS[song_cursor])
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for idx, rect in enumerate(song_rects):
                        if rect.collidepoint(event.pos):
                            song_cursor = idx
                            _stop_preview()
                            start_game(n_players, SONGS[song_cursor])
                elif event.type == pygame.JOYBUTTONDOWN:
                    if event.button == MAT_UP:
                        song_cursor = (song_cursor + 1) % len(SONGS)
                        _play(SFX_NAV)
                    elif event.button == MAT_DOWN:
                        song_cursor = (song_cursor - 1) % len(SONGS)
                        _play(SFX_NAV)
                    elif event.button == MAT_START:
                        _play(SFX_CONFIRM)
                        _stop_preview()
                        start_game(n_players, SONGS[song_cursor])
                    elif event.button in (MAT_LEFT, MAT_RIGHT):   # view scores
                        _play(SFX_NAV)
                        _stop_preview()
                        _leader_view_idx = song_cursor
                        game_state = GameState.LEADERBOARD
                    elif event.button == MAT_SELECT:
                        _play(SFX_NAV)
                        _stop_preview()
                        game_state = GameState.MENU
            continue

        # ── NAME ENTRY (new high score) ───────────────────────────────────────
        if game_state == GameState.NAME_ENTRY:
            draw_name_entry()
            _present_logo()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        _commit_name_entry()
                    elif event.key == pygame.K_BACKSPACE:
                        _entry_typed = _entry_typed[:-1]
                    elif event.key == pygame.K_ESCAPE:
                        _commit_name_entry()   # skip = accept current
                    elif event.unicode and event.unicode.isprintable() \
                            and len(_entry_typed) < 10:
                        _entry_typed += event.unicode
                elif event.type == pygame.JOYBUTTONDOWN:
                    # Arcade reel input (only when not keyboard-typing)
                    idx = _NAME_CHARS.find(_entry_initials[_entry_pos])
                    if event.button == MAT_UP:
                        _entry_initials[_entry_pos] = _NAME_CHARS[(idx + 1) % len(_NAME_CHARS)]
                        _play(SFX_NAV)
                    elif event.button == MAT_DOWN:
                        _entry_initials[_entry_pos] = _NAME_CHARS[(idx - 1) % len(_NAME_CHARS)]
                        _play(SFX_NAV)
                    elif event.button in (MAT_RIGHT, MAT_START):
                        if _entry_pos < 2:
                            _entry_pos += 1
                            _play(SFX_NAV)
                        else:
                            _play(SFX_CONFIRM)
                            _commit_name_entry()
                    elif event.button == MAT_LEFT:
                        if _entry_pos > 0:
                            _entry_pos -= 1
                            _play(SFX_NAV)
                    elif event.button == MAT_SELECT:
                        _play(SFX_CONFIRM)
                        _commit_name_entry()
            continue

        # ── LEADERBOARD (viewing a song's board from song select) ─────────────
        if game_state == GameState.LEADERBOARD:
            draw_leaderboard()
            _present_logo()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    game_state = GameState.SONG_SELECT
                elif event.type == pygame.JOYBUTTONDOWN and event.button == MAT_SELECT:
                    game_state = GameState.SONG_SELECT
            continue

        # ── RESULTS ───────────────────────────────────────────────────────────
        if game_state == GameState.RESULTS:
            draw_results()
            _present_logo()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        stop_game()
                    elif event.key == pygame.K_r and last_song:
                        start_game(n_players, last_song)
                elif event.type == pygame.JOYBUTTONDOWN:
                    if event.button == MAT_START and last_song:
                        start_game(n_players, last_song)   # START = play again
                    elif event.button == MAT_SELECT:
                        stop_game()                         # SELECT = back to menu
            continue

        # ── PLAYING ───────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    stop_game()
                    continue
                elif event.key == pygame.K_LEFTBRACKET:
                    bias_slider.val = max(0.0,   bias_slider.val - 5.0)
                elif event.key == pygame.K_RIGHTBRACKET:
                    bias_slider.val = min(100.0, bias_slider.val + 5.0)
                elif event.key == pygame.K_BACKSLASH:
                    bias_slider.val = 50.0

                for i, k in enumerate(KEYS_P1):
                    if event.key == k:
                        p1.handle_key(i)

                if p2:
                    for i, k in enumerate(KEYS_P2):
                        if event.key == k:
                            p2.handle_key(i)

            elif event.type == pygame.JOYBUTTONDOWN:
                # SELECT exits game back to menu from any player's mat
                if event.button == MAT_SELECT:
                    stop_game()
                    break
                key = (event.joy, event.button)
                if tick - _mat_last.get(key, -_MAT_DEBOUNCE) >= _MAT_DEBOUNCE:
                    _mat_last[key] = tick
                    lane = _mat_lane(event.button)
                    if lane is not None:
                        if event.joy == 0:
                            p1.handle_key(lane)
                        elif p2 and event.joy == 1:
                            p2.handle_key(lane)

        music_playing  = SONG_FILE and pygame.mixer.music.get_busy()
        music_pos_ms   = pygame.mixer.music.get_pos() if music_playing else -1

        update(dt, music_pos_ms)
        for nid in collapsed_outcomes:
            if nid not in _seen_collapsed_nids:
                _seen_collapsed_nids.add(nid)
                q_collapsed += 1

        # ── Duration-based fade & auto-end ───────────────────────────────────
        if music_playing:
            elapsed_sec = max(0.0, music_pos_ms / 1000.0 - SONG_OFFSET)
            time_left   = SONG_DURATION - elapsed_sec
            if time_left <= 0:
                try: pygame.mixer.music.stop()
                except Exception: pass
            elif time_left <= FADE_START:
                vol = max(0.0, time_left / FADE_START)
                try: pygame.mixer.music.set_volume(vol)
                except Exception: pass

        # ── Transition to RESULTS (after a short grace period) ────────────────
        if music_playing:
            song_done = not pygame.mixer.music.get_busy()
        else:
            song_done = SONG_FILE is not None and _game_elapsed >= SONG_DURATION

        # Once the song is done AND all notes have drained, start a 2s countdown
        notes_drained = not p1.notes and (p2 is None or not p2.notes)
        if song_done and notes_drained:
            if _end_timer < 0:
                _end_timer = 0.0               # begin grace period
                try: pygame.mixer.music.set_volume(1.0)
                except Exception: pass
            else:
                _end_timer += dt
                if _end_timer >= END_GRACE_S:
                    # Build the name-entry queue for players who made the top-5
                    title = last_song["title"] if last_song else ""
                    queue = []
                    if _qualifies(title, p1.score):
                        queue.append((p1, "PLAYER 1" if n_players == 2 else ""))
                    if p2 and _qualifies(title, p2.score):
                        queue.append((p2, "PLAYER 2"))
                    if queue:
                        _begin_name_entry(queue)   # -> NAME_ENTRY
                    else:
                        game_state = GameState.RESULTS

        # ── Render ────────────────────────────────────────────────────────────
        if split_mode and n_players == 2 and p2 and ctx1 and ctx2:
            # Option B: side-by-side subsurfaces on one window
            screen.fill(BG)
            left  = screen.subsurface(pygame.Rect(0,        0, SW // 2, SH))
            right = screen.subsurface(pygame.Rect(SW // 2,  0, SW // 2, SH))
            _render_player(left,  p1, ctx1, "P1")
            _render_player(right, p2, ctx2, "P2")
            pygame.draw.line(screen, (60, 50, 100), (SW // 2, 0), (SW // 2, SH), 1)
            pygame.display.flip()

        elif two_screen_mode and n_players == 2 and p2 and surf2 and ren2 and ctx1 and ctx2:
            # Option A: 2P two-monitor — P1 on main, P2 on win2 (logo window replaced)
            _render_player(screen, p1, ctx1, "PLAYER 1")
            pygame.display.flip()
            try:
                from pygame._sdl2.video import Texture
                _render_player(surf2, p2, ctx2, "PLAYER 2")
                tex = Texture.from_surface(ren2, surf2)
                ren2.clear()
                tex.draw()
                ren2.present()
                tex.destroy()
            except Exception:
                pass

        else:
            # 1P — render game on main screen, show logo on second screen
            lbl = "PLAYER 1" if n_players == 2 else ""
            _render_player(screen, p1, ctx1 or make_ctx(SW), lbl)
            pygame.display.flip()
            _present_logo()


if __name__ == "__main__":
    main()