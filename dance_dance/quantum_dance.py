"""
quantum_dance.py  —  Quantum Dance
====================================
Quantum Exhibition  |  Classical vs Quantum Computing

MENU → SONG SELECT → PLAYING

Controls (in-game)
------------------
  ←↓↑→        P1 lanes 0-3
  A S W D      P2 lanes 0-3  (2P only)
  [  /  ]      Nudge BIAS slider ±5%
  \\            Reset BIAS to 50%
  ESC          Return to menu

Hardware
--------
  See SERIAL PORT HOOK comment block to wire a potentiometer via USB serial.
"""

# ─────────────────────────────────────────────────────────────────────────────
# FIXED TIMING CONSTANTS  (overridden at runtime by song selection)
# ─────────────────────────────────────────────────────────────────────────────
BEATS_PER_NOTE = 1    # spawn one note every N beats
BEATS_TO_FALL  = 4    # base beats from spawn to hit zone (scaled by difficulty)

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

import pygame
import sys
import random
import math
import numpy as np
from enum import Enum, auto

pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)


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

try:
    SFX_PERFECT   = _make_tone(880,  70)
    SFX_GOOD      = _make_tone(660,  70)
    SFX_MISS      = _make_tone(150, 110)
    SFX_COLLAPSE  = _make_tone(440, 140)
    SFX_MILESTONE = _make_tone(1047, 180)
    _sfx_ok = True
except Exception:
    _sfx_ok = False

def _play(sfx):
    if _sfx_ok:
        try: sfx.play()
        except Exception: pass

# ─────────────────────────────────────────────────────────────────────────────
# Screen & timing
# ─────────────────────────────────────────────────────────────────────────────
SW, SH = 960, 720
FPS    = 60
screen = pygame.display.set_mode((SW, SH))
pygame.display.set_caption("Quantum Dance  |  Quantum Exhibition")
clk    = pygame.time.Clock()

# ─────────────────────────────────────────────────────────────────────────────
# Game state enum
# ─────────────────────────────────────────────────────────────────────────────
class GameState(Enum):
    MENU        = auto()
    SONG_SELECT = auto()
    PLAYING     = auto()
    RESULTS     = auto()

game_state    = GameState.MENU
n_players     = 1
song_cursor   = 0      # highlighted row in song select screen
last_song     = None   # dict of the last played song (for retry)

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

F_TITLE  = _f(34)
F_MENU   = _f(28)
F_MENUSM = _f(18)
F_MED    = _f(18)
F_SM     = _f(14)
F_XSM    = _f(11, bold=False)
F_ARROW  = _f(26)

# ─────────────────────────────────────────────────────────────────────────────
# Song catalogue  (sourced from music/ddr_songs.txt)
# ─────────────────────────────────────────────────────────────────────────────
SONGS = [
    {"title": "Faded",                  "artist": "Alan Walker",
     "file": "music/Alan Walker - Faded.mp3",
     "bpm": 90,  "offset": 0.0, "difficulty": "Easy",    "duration": 120},
    {"title": "Alone",                  "artist": "Alan Walker",
     "file": "music/Alan Walker - Alone.mp3",
     "bpm": 150, "offset": 3.0, "difficulty": "Hard",    "duration":  90},
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
     "bpm": 130, "offset": 0.0, "difficulty": "Extreme", "duration":  90},
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
LANE_W   = 200
LANE_GAP = 16
TOTAL_W  = N_LANES * LANE_W + (N_LANES - 1) * LANE_GAP   # 848
LX0      = (SW - TOTAL_W) // 2                            #  56 — small side margins

TOP_H    = 82
BOT_H    = 88
LANE_TOP = TOP_H
LANE_BOT = SH - BOT_H        # 632

TARGET_Y   = LANE_BOT - 28
HIT_ZONE_H = 56
NOTE_W     = LANE_W - 14
NOTE_H     = 52

HIT_PERFECT = 22
HIT_GOOD    = 48

KEYS_P1 = [pygame.K_LEFT, pygame.K_DOWN, pygame.K_UP, pygame.K_RIGHT]
KEYS_P2 = [pygame.K_a,    pygame.K_s,    pygame.K_w,  pygame.K_d]
ARROWS  = ["←", "↓", "↑", "→"]

RP_X = LX0 + TOTAL_W   # 736
RP_W = SW - RP_X        # 224

FALL_DISTANCE = TARGET_Y - LANE_TOP   # ~522 px


def lx(lane):  return LX0 + lane * (LANE_W + LANE_GAP)
def lcx(lane): return lx(lane) + LANE_W // 2

# P2 key mirror map: physical key index → logical lane
# Lane 0(←)↔3(→), Lane 1(↓)↔2(↑)
_P2_KEY_MAP = [3, 2, 1, 0]


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


# ─────────────────────────────────────────────────────────────────────────────
# BPM timing helpers
# ─────────────────────────────────────────────────────────────────────────────
def _bpm_fall_speed() -> float:
    """px/frame for a note to travel FALL_DISTANCE in _active_beats_fall beats."""
    seconds = _active_beats_fall * 60.0 / SONG_BPM
    return (FALL_DISTANCE / seconds) / FPS

def _bpm_collapse_y() -> int:
    """Collapse 1 beat before the note reaches TARGET_Y."""
    px_per_beat = (FALL_DISTANCE / (_active_beats_fall * 60.0 / SONG_BPM)) * (60.0 / SONG_BPM)
    return int(TARGET_Y - px_per_beat)


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
        self.speed        = get_fall_speed() + random.uniform(-0.2, 0.2)
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

    def update(self, collapsed_outcomes: dict, player_idx: int):
        """
        collapsed_outcomes: shared dict  nid → (p1_lane, p2_lane)
        player_idx: 0 = P1, 1 = P2
        In 1P mode player_idx is always 0.
        """
        self.just_collapsed = False
        self.just_missed    = False
        self.y += self.speed

        if self.quantum and not self.collapsed and self.y >= get_collapse_y():
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
class Particle:
    def __init__(self, x, y, color, speed_scale=1.0):
        a  = random.uniform(0, math.tau)
        sp = random.uniform(1.5, 6.0) * speed_scale
        self.x, self.y   = float(x), float(y)
        self.vx, self.vy = math.cos(a) * sp, math.sin(a) * sp - 1.5
        self.life     = random.randint(22, 48)
        self.max_life = self.life
        self.color    = color
        self.size     = random.randint(2, 5)

    def update(self):
        self.x += self.vx;  self.y += self.vy
        self.vy += 0.18;    self.life -= 1

    def draw(self, surf):
        if self.life <= 0: return
        pygame.draw.circle(surf, self.color,
                           (int(self.x), int(self.y)), max(1, self.size))


class FloatText:
    def __init__(self, text, x, y, color, font=None):
        self.surf     = (font or F_MED).render(text, True, color)
        self.x        = float(x - self.surf.get_width() // 2)
        self.y        = float(y)
        self.life     = 52
        self.max_life = 52

    def update(self):
        self.y -= 1.3;  self.life -= 1

    def draw(self, surf):
        if self.life <= 0: return
        tmp = self.surf.copy()
        tmp.set_alpha(int(255 * self.life / self.max_life))
        surf.blit(tmp, (int(self.x), int(self.y)))


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
                for _ in range(20): self.particles.append(Particle(scx, TARGET_Y, LANE_C[lane]))
                _play(SFX_PERFECT)
            else:
                self.score += 100 * max(1, self.combo // 10)
                self.good_count += 1
                self.floats.append(FloatText("GOOD", scx, TARGET_Y - 42, WHITE))
                for _ in range(9): self.particles.append(Particle(scx, TARGET_Y, LANE_C[lane]))
                _play(SFX_GOOD)
            for m in COMBO_MILESTONES:
                if self.combo >= m and self.last_milestone < m:
                    self.last_milestone  = m
                    self.milestone_text  = f"COMBO  ×{m}!"
                    self.milestone_timer = 90
                    self.flash_timer     = 8
                    _play(SFX_MILESTONE)
        else:
            self.combo = 0
            self.last_milestone = 0
            self.miss_count += 1
            self.floats.append(FloatText("EARLY", scx, TARGET_Y - 42, (255, 180, 0)))
            _play(SFX_MISS)

    def update(self, collapsed_outcomes: dict):
        for note in self.notes:
            note.update(collapsed_outcomes, self.idx)
            if note.just_collapsed:
                cx = (_lcx(note.dropped_lane, self.ctx) if self.ctx
                      else lcx(note.dropped_lane))
                ny = note.y + NOTE_H // 2
                for _ in range(16): self.particles.append(Particle(cx, ny, Q_WAVE, 0.9))
                self.floats.append(FloatText(
                    "COLLAPSED!", cx,
                    TARGET_Y - 42 + int(note.y - TARGET_Y) + NOTE_H // 2,
                    Q_PURPLE, F_SM))
                _play(SFX_COLLAPSE)
            if note.just_missed:
                self.combo = 0
                self.last_milestone = 0
                self.miss_count += 1
                miss_cx = (_lcx(note.lane, self.ctx) if self.ctx else lcx(note.lane))
                self.floats.append(FloatText("MISS", miss_cx, TARGET_Y - 42, RED))

        self.notes[:]     = [n for n in self.notes     if n.alive]
        self.max_combo    = max(self.max_combo, self.combo)
        for p in self.particles: p.update()
        self.particles[:] = [p for p in self.particles if p.life > 0]
        for f in self.floats:    f.update()
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
spawn_timer        = 55
collapsed_outcomes : dict = {}   # nid → (p1_lane, p2_lane)
last_beat          = -1

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


def draw_lanes(surf, key_flash, ctx: RenderCtx):
    for i in range(N_LANES):
        x    = _lx(i, ctx)
        rect = pygame.Rect(x, LANE_TOP, ctx.lane_w, LANE_BOT - LANE_TOP)
        pygame.draw.rect(surf, LANE_BG, rect)
        pygame.draw.rect(surf, LANE_LINE, rect, 1)
        if key_flash[i] > 0:
            r, g, b = LANE_C[i]
            s = pygame.Surface((ctx.lane_w, LANE_BOT - LANE_TOP), pygame.SRCALPHA)
            s.fill((r, g, b, int(90 * key_flash[i] / 14)))
            surf.blit(s, (x, LANE_TOP))

    cy = get_collapse_y()
    for i in range(N_LANES):
        x = _lx(i, ctx)
        pygame.draw.line(surf, (80, 35, 105), (x + 4, cy), (x + ctx.lane_w - 4, cy), 1)
    cl = F_XSM.render("collapse zone", True, (100, 45, 130))
    surf.blit(cl, (_lcx(0, ctx) - cl.get_width() // 2, cy - 14))


def draw_hit_zone(surf, ctx: RenderCtx):
    for i in range(N_LANES):
        x       = _lx(i, ctx)
        scx     = _lcx(i, ctx)
        r, g, b = LANE_C[i]
        hz      = pygame.Rect(x + 4, TARGET_Y - HIT_ZONE_H // 2,
                              ctx.lane_w - 8, HIT_ZONE_H)
        pygame.draw.rect(surf, (r // 5, g // 5, b // 5), hz, border_radius=10)
        pygame.draw.rect(surf, (r // 2, g // 2, b // 2), hz, 2, border_radius=10)
        pygame.draw.line(surf, (r, g, b),
                         (x + 6, TARGET_Y), (x + ctx.lane_w - 6, TARGET_Y), 2)
        lbl = F_ARROW.render(ARROWS[i], True, (r, g, b))
        surf.blit(lbl, (scx - lbl.get_width() // 2,
                        TARGET_Y + HIT_ZONE_H // 2 + 5))


def draw_classical(surf, note: Note, ctx: RenderCtx):
    r, g, b = LANE_C[note.lane]
    scx     = _lcx(note.lane, ctx)
    nw      = ctx.note_w
    rect    = pygame.Rect(scx - nw // 2, int(note.y), nw, NOTE_H)
    pygame.draw.rect(surf, (r // 3, g // 3, b // 3), rect, border_radius=9)
    pygame.draw.rect(surf, (r, g, b), rect, 3, border_radius=9)
    ar = F_ARROW.render(ARROWS[note.lane], True, (r, g, b))
    surf.blit(ar, (scx - ar.get_width() // 2,
                   int(note.y) + (NOTE_H - ar.get_height()) // 2))


def draw_quantum(surf, note: Note, ctx: RenderCtx):
    nw = ctx.note_w
    if note.collapsed:
        r, g, b = Q_PURPLE
        cx   = _lcx(note.lane, ctx)
        rect = pygame.Rect(cx - nw // 2, int(note.y), nw, NOTE_H)
        pygame.draw.rect(surf, (r // 3, g // 3, b // 3), rect, border_radius=9)
        pygame.draw.rect(surf, (r, g, b), rect, 3, border_radius=9)
        ar = F_ARROW.render(ARROWS[note.lane], True, (r, g, b))
        surf.blit(ar, (cx - ar.get_width() // 2,
                       int(note.y) + (NOTE_H - ar.get_height()) // 2))
        return

    cy_collapse = get_collapse_y()
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
        qm = F_ARROW.render("?", True, (ri, gi, bi))
        surf.blit(qm, (cx - qm.get_width() // 2,
                       int(note.y) + (NOTE_H - qm.get_height()) // 2))

    xa, xb = _lcx(note.lane, ctx), _lcx(note.lane2, ctx)
    x0, x1 = min(xa, xb), max(xa, xb)
    wy = int(note.y) + NOTE_H // 2
    pts = []
    for i in range(x1 - x0 + 1):
        xp = x0 + i
        yp = wy + math.sin(i * math.pi * 0.14 + tick * 0.18 + note.wave_phase) \
             * (5 + 5 * urgency)
        pts.append((xp, int(yp)))
    if len(pts) >= 2:
        wr, wg, wb = Q_WAVE
        pygame.draw.lines(surf, (int(wr * af), int(wg * af * 0.5), int(wb * af)),
                          False, pts, 2)

    if dist > 60:
        mx  = (xa + xb) // 2
        slb = F_XSM.render("superposition", True, (int(180 * af), 30, int(220 * af)))
        surf.blit(slb, (mx - slb.get_width() // 2, int(note.y) - 17))


def draw_top(surf, ps: PlayerState, ctx: RenderCtx, label: str = ""):
    sw = ctx.sw
    pygame.draw.rect(surf, (10, 8, 26), (0, 0, sw, TOP_H))
    pygame.draw.line(surf, (55, 45, 100), (0, TOP_H - 1), (sw, TOP_H - 1))

    title_str = "✦  QUANTUM DANCE  ✦" + (f"  —  {label}" if label else "")
    title = F_TITLE.render(title_str, True, Q_PURPLE)
    surf.blit(title, (sw // 2 - title.get_width() // 2, 8))

    sc = F_MED.render(f"SCORE  {ps.score:07d}", True, GOLD)
    surf.blit(sc, (18, 10))

    cb = F_MED.render(f"COMBO  ×{ps.combo}", True, GOLD if ps.combo >= 10 else WHITE)
    surf.blit(cb, (sw - cb.get_width() - 18, 10))
    mc = F_SM.render(f"best ×{ps.max_combo}", True, DIM)
    surf.blit(mc, (sw - mc.get_width() - 18, 32))
    qc = F_SM.render(f"collapses: {q_collapsed}/{q_total}", True, (170, 70, 230))
    surf.blit(qc, (18, 34))

    sub = F_XSM.render(
        "Classical notes: ONE lane.   "
        "Quantum notes: TWO lanes — collapse to one before the hit zone.",
        True, DIM)
    surf.blit(sub, (sw // 2 - sub.get_width() // 2, 65))


def draw_bottom(surf, ctx: RenderCtx):
    sw = ctx.sw
    y0 = SH - BOT_H
    pygame.draw.rect(surf, (10, 8, 26), (0, y0, sw, BOT_H))
    pygame.draw.line(surf, (55, 45, 100), (0, y0), (sw, y0))

    pct = int(bias_slider.val)
    bias_txt = f"⬡  Quantum — 2 lanes, collapses {pct}% lane 1 / {100 - pct}% lane 2"
    for i, (txt, col) in enumerate([
        ("■  Classical — stays in its lane", WHITE),
        (bias_txt, SL_BIAS_C),
    ]):
        surf.blit(F_SM.render(txt, True, col), (18, y0 + 12 + i * 22))

    if n_players == 2:
        hint = F_XSM.render("2P: entangled collapse — P1 & P2 get opposite lanes", True, (170, 70, 230))
        surf.blit(hint, (sw - hint.get_width() - 18, y0 + 14))
        ctrl = F_XSM.render("P2 keys: A ↔  S ↓  W ↑  D →", True, DIM)
        surf.blit(ctrl, (sw - ctrl.get_width() - 18, y0 + 31))
    else:
        lines = ["In quantum mechanics a particle can be",
                 "in multiple states until it is MEASURED."]
        for i, line in enumerate(lines):
            t = F_XSM.render(line, True, DIM)
            surf.blit(t, (sw - t.get_width() - 18, y0 + 14 + i * 17))


# ─────────────────────────────────────────────────────────────────────────────
# Arcade retro menu
# ─────────────────────────────────────────────────────────────────────────────
_menu_tick = 0   # animated frame counter

def draw_menu():
    global _menu_tick
    _menu_tick += 1
    t = _menu_tick

    screen.fill((4, 2, 14))

    # ── Starfield ────────────────────────────────────────────────────────────
    rng = random.Random(7)
    for _ in range(120):
        sx = rng.randint(0, SW)
        sy = rng.randint(0, SH)
        twinkle = 0.5 + 0.5 * math.sin(t * 0.05 + rng.random() * math.tau)
        br = int(80 * twinkle)
        pygame.draw.circle(screen, (br, br, br + 20), (sx, sy), rng.randint(1, 2))

    # ── Horizontal scan lines (retro CRT feel) ────────────────────────────────
    scan = pygame.Surface((SW, SH), pygame.SRCALPHA)
    for y in range(0, SH, 4):
        pygame.draw.line(scan, (0, 0, 0, 35), (0, y), (SW, y))
    screen.blit(scan, (0, 0))

    # ── Marquee border ────────────────────────────────────────────────────────
    cols = [(255,60,180),(255,160,0),(80,255,80),(0,200,255),(200,80,255)]
    for i, col in enumerate(cols):
        alpha = int(180 + 75 * math.sin(t * 0.07 + i * 1.2))
        c = tuple(min(255, int(v * alpha / 255)) for v in col)
        pygame.draw.rect(screen, c, (i*3, i*3, SW - i*6, SH - i*6), 2)

    # ── Blinking "INSERT COIN" at top ─────────────────────────────────────────
    if (t // 22) % 2 == 0:
        coin = F_MENUSM.render("► INSERT COIN ◄", True, (255, 230, 0))
        screen.blit(coin, (SW // 2 - coin.get_width() // 2, 28))

    # ── Rainbow cycling title ─────────────────────────────────────────────────
    title_str = "QUANTUM  DANCE"
    char_surfs = []
    total_w = 0
    F_BIG = _f(56)
    for i, ch in enumerate(title_str):
        hue = (t * 2 + i * 18) % 360
        # HSV → RGB
        h = hue / 60.0
        x = int(255 * (1 - abs(h % 2 - 1)))
        if   h < 1: r,g,b = 255,  x,  0
        elif h < 2: r,g,b =   x,255,  0
        elif h < 3: r,g,b =   0,255,  x
        elif h < 4: r,g,b =   0,  x,255
        elif h < 5: r,g,b =   x,  0,255
        else:       r,g,b = 255,  0,  x
        cs = F_BIG.render(ch, True, (r, g, b))
        char_surfs.append(cs)
        total_w += cs.get_width()

    tx = SW // 2 - total_w // 2
    ty = SH // 2 - 200 + int(6 * math.sin(t * 0.06))
    for cs in char_surfs:
        screen.blit(cs, (tx, ty))
        tx += cs.get_width()

    # ── Subtitle ─────────────────────────────────────────────────────────────
    sub_col = (int(160 + 60 * math.sin(t * 0.04)),
               int(100 + 60 * math.sin(t * 0.04 + 1)),
               int(200 + 55 * math.sin(t * 0.04 + 2)))
    sub = F_MENUSM.render("CLASSICAL  vs  QUANTUM  COMPUTING", True, sub_col)
    screen.blit(sub, (SW // 2 - sub.get_width() // 2, SH // 2 - 130))

    # ── Buttons ───────────────────────────────────────────────────────────────
    btn_w, btn_h = 300, 64
    gap  = 22
    bx   = SW // 2 - btn_w // 2
    by1  = SH // 2 - 30
    by2  = by1 + btn_h + gap
    mx, my = pygame.mouse.get_pos()

    for by, label, key_hint, base_col in [
        (by1, "1  PLAYER",  "PRESS  1", (0, 180, 255)),
        (by2, "2  PLAYERS", "PRESS  2", (255, 80, 200)),
    ]:
        rect  = pygame.Rect(bx, by, btn_w, btn_h)
        hover = rect.collidepoint(mx, my)
        pulse = 0.7 + 0.3 * math.sin(t * 0.10)
        r, g, b = base_col
        bcol  = (int(r * pulse), int(g * pulse), int(b * pulse))

        # Glow
        for gw in (18, 10, 4):
            gs = pygame.Surface((btn_w + gw*2, btn_h + gw*2), pygame.SRCALPHA)
            alpha = int(40 * (1 - gw / 20)) if hover else int(18 * (1 - gw / 20))
            pygame.draw.rect(gs, (*bcol, alpha),
                             (0, 0, btn_w + gw*2, btn_h + gw*2), border_radius=10)
            screen.blit(gs, (bx - gw, by - gw))

        fill = (int(r*0.18), int(g*0.18), int(b*0.18))
        pygame.draw.rect(screen, fill,   rect, border_radius=8)
        pygame.draw.rect(screen, bcol,   rect, 2, border_radius=8)

        lbl = F_MENU.render(label, True, WHITE if hover else bcol)
        screen.blit(lbl, (rect.centerx - lbl.get_width() // 2,
                          rect.centery - lbl.get_height() // 2))
        hint = F_XSM.render(key_hint, True, (120, 110, 160))
        screen.blit(hint, (rect.right + 12, rect.centery - hint.get_height() // 2))

    # ── Arrow decoration ──────────────────────────────────────────────────────
    arrow_y = SH // 2 + 110
    for i, (arrow, col) in enumerate(zip(
        ["←", "↓", "↑", "→"], LANE_C
    )):
        bounce = int(5 * math.sin(t * 0.12 + i * 0.8))
        as_ = F_TITLE.render(arrow, True, col)
        ax  = SW // 2 - 90 + i * 60
        screen.blit(as_, (ax - as_.get_width() // 2, arrow_y + bounce))

    # ── Bottom hint ───────────────────────────────────────────────────────────
    ctrl = F_XSM.render("P1: ← ↓ ↑ →     2P adds: A S W D",
                         True, (70, 60, 100))
    screen.blit(ctrl, (SW // 2 - ctrl.get_width() // 2, SH - 28))

    pygame.display.flip()
    return (pygame.Rect(bx, by1, btn_w, btn_h),
            pygame.Rect(bx, by2, btn_w, btn_h))


# ─────────────────────────────────────────────────────────────────────────────
# Song select screen
# ─────────────────────────────────────────────────────────────────────────────
def draw_song_select(cursor: int, num_players: int) -> list:
    """Draw song list; returns list of row rects for click detection."""
    screen.fill(BG)

    title = F_TITLE.render("✦  SELECT SONG  ✦", True, Q_PURPLE)
    screen.blit(title, (SW // 2 - title.get_width() // 2, 40))

    mode_lbl = F_MENUSM.render(
        f"{'1 PLAYER' if num_players == 1 else '2 PLAYERS'}  —  choose a track",
        True, DIM)
    screen.blit(mode_lbl, (SW // 2 - mode_lbl.get_width() // 2, 86))

    mx, my = pygame.mouse.get_pos()
    row_h  = 72
    row_w  = 720
    rx0    = (SW - row_w) // 2
    ry0    = 140
    rects  = []

    for i, song in enumerate(SONGS):
        ry     = ry0 + i * row_h
        rect   = pygame.Rect(rx0, ry, row_w, row_h - 6)
        hover  = rect.collidepoint(mx, my)
        active = i == cursor

        fill   = (50, 25, 90) if active else ((30, 15, 60) if hover else (16, 10, 38))
        border = Q_PURPLE     if active else ((160, 80, 200) if hover else (50, 35, 80))
        pygame.draw.rect(screen, fill,   rect, border_radius=10)
        pygame.draw.rect(screen, border, rect, 2 if active else 1, border_radius=10)
        rects.append(rect)

        # Number
        num_s = F_MED.render(f"{i + 1}", True, (120, 80, 180) if not active else WHITE)
        screen.blit(num_s, (rx0 + 18, ry + (row_h - 6 - num_s.get_height()) // 2))

        # Title + artist
        title_s  = F_MED.render(song["title"],  True, WHITE if active else (200, 190, 230))
        artist_s = F_SM.render(song["artist"],  True, DIM)
        screen.blit(title_s,  (rx0 + 50, ry + 8))
        screen.blit(artist_s, (rx0 + 50, ry + 8 + title_s.get_height()))

        # BPM
        bpm_s = F_SM.render(f"{song['bpm']} BPM", True, (140, 200, 255))
        screen.blit(bpm_s, (rx0 + row_w - 210, ry + (row_h - 6 - bpm_s.get_height()) // 2))

        # Difficulty badge
        diff   = song["difficulty"]
        dc     = DIFF_COLOR[diff]
        diff_s = F_SM.render(diff, True, dc)
        bw, bh = diff_s.get_width() + 16, diff_s.get_height() + 6
        bx     = rx0 + row_w - bw - 12
        by_    = ry + (row_h - 6 - bh) // 2
        pygame.draw.rect(screen, (dc[0] // 5, dc[1] // 5, dc[2] // 5),
                         (bx, by_, bw, bh), border_radius=6)
        pygame.draw.rect(screen, dc, (bx, by_, bw, bh), 1, border_radius=6)
        screen.blit(diff_s, (bx + 8, by_ + 3))

    hint = F_XSM.render("↑↓ navigate     Enter / click to select     ESC back",
                         True, (70, 60, 100))
    screen.blit(hint, (SW // 2 - hint.get_width() // 2, ry0 + len(SONGS) * row_h + 10))

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
    rng = random.Random(99)
    for _ in range(60):
        sx = rng.randint(0, SW)
        sy = rng.randint(0, SH)
        pygame.draw.circle(screen, (40, 35, 65), (sx, sy), rng.randint(1, 2))

    title = F_TITLE.render("✦  GREAT GAME!  ✦", True, Q_PURPLE)
    screen.blit(title, (SW // 2 - title.get_width() // 2, 22))

    if last_song:
        song_lbl = F_MED.render(
            f"{last_song['title']}  —  {last_song['artist']}", True, DIM)
        screen.blit(song_lbl, (SW // 2 - song_lbl.get_width() // 2, 62))

    if n_players == 2 and p2:
        _draw_results_panel(screen, p1, SW // 4,     SH // 2 + 20, "PLAYER 1")
        _draw_results_panel(screen, p2, SW * 3 // 4, SH // 2 + 20, "PLAYER 2")
        pygame.draw.line(screen, (50, 40, 80), (SW // 2, 95), (SW // 2, SH - 55), 1)
    else:
        _draw_results_panel(screen, p1, SW // 2, SH // 2 + 20, "")

    hint = F_SM.render("R  play again     ESC  menu", True, (80, 70, 120))
    screen.blit(hint, (SW // 2 - hint.get_width() // 2, SH - 40))
    pygame.display.flip()


# ─────────────────────────────────────────────────────────────────────────────
# Game init / reset
# ─────────────────────────────────────────────────────────────────────────────
def start_game(num_players: int, song: dict):
    global n_players, game_state, p1, p2, last_song
    global q_collapsed, q_total, tick, spawn_timer, collapsed_outcomes, last_beat
    global win2, ren2, surf2
    global SONG_FILE, SONG_BPM, SONG_OFFSET, SONG_DURATION, _active_beats_fall
    global two_screen_mode, split_mode, ctx1, ctx2
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

    q_collapsed = 0
    q_total     = 0
    tick        = 0
    spawn_timer = 55
    collapsed_outcomes = {}
    last_beat   = -1
    Note._nid   = 0

    # Tear down any existing second window
    if win2 is not None:
        try: win2.destroy()
        except Exception: pass
    win2 = ren2 = surf2 = None
    two_screen_mode = False
    split_mode      = False

    if num_players == 2:
        try:
            n_displays = pygame.display.get_num_displays()
        except Exception:
            n_displays = 1

        if n_displays >= 2:
            # Option A — two physical monitors
            try:
                from pygame._sdl2.video import Window, Renderer
                two_screen_mode = True
                split_mode      = False
                # Place P2 window at x = width of display 0 so it lands on display 1
                sizes = pygame.display.get_desktop_sizes()
                d0_w  = sizes[0][0] if sizes else SW
                win2  = Window("Quantum Dance — Player 2", size=(SW, SH))
                win2.position = (d0_w, 0)
                ren2  = Renderer(win2)
                surf2 = pygame.Surface((SW, SH))
                ctx1  = make_ctx(SW)
                ctx2  = make_ctx(SW)
            except Exception as e:
                print(f"[WARNING] Second monitor init failed, falling back to split: {e}")
                two_screen_mode = False
                win2 = ren2 = surf2 = None
                split_mode = True
                ctx1 = make_ctx(SW // 2)
                ctx2 = make_ctx(SW // 2)
        else:
            # Option B — split-screen on one monitor
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
        except Exception as e:
            print(f"[WARNING] Could not load music: {e}")


def stop_game():
    global game_state, win2, ren2, surf2, SONG_FILE
    global two_screen_mode, split_mode, ctx1, ctx2
    game_state = GameState.MENU
    try: pygame.mixer.music.stop()
    except Exception: pass
    SONG_FILE = None
    if win2 is not None:
        try: win2.destroy()
        except Exception: pass
    win2 = ren2 = surf2 = None
    two_screen_mode = False
    split_mode      = False
    ctx1 = ctx2 = None


# ─────────────────────────────────────────────────────────────────────────────
# Per-frame update
# ─────────────────────────────────────────────────────────────────────────────
def update():
    global spawn_timer, q_collapsed, tick, last_beat

    tick += 1

    # Spawning
    if SONG_FILE and pygame.mixer.music.get_busy():
        pos_ms     = pygame.mixer.music.get_pos()
        beat_time  = max(0.0, pos_ms / 1000.0 - SONG_OFFSET)
        beat_num   = beat_time * SONG_BPM / 60.0
        cur_beat   = int(beat_num)
        if cur_beat > last_beat and cur_beat % BEATS_PER_NOTE == 0:
            spawn_note()
            last_beat = cur_beat
    else:
        spawn_timer -= 1
        if spawn_timer <= 0:
            spawn_note()
            base = get_spawn_interval()
            spawn_timer = random.randint(int(base * 0.78), int(base * 1.35))

    p1.update(collapsed_outcomes)
    if p2: p2.update(collapsed_outcomes)


def _render_player(surf, ps: PlayerState, ctx: RenderCtx, label: str = ""):
    sw = ctx.sw
    surf.fill(BG)
    draw_lanes(surf, ps.key_flash, ctx)
    draw_hit_zone(surf, ctx)

    for note in ps.notes:
        if note.quantum:
            draw_quantum(surf, note, ctx)
        else:
            draw_classical(surf, note, ctx)

    for p in ps.particles: p.draw(surf)
    for f in ps.floats:    f.draw(surf)

    draw_top(surf, ps, ctx, label)
    draw_bottom(surf, ctx)

    # Milestone banner
    if ps.milestone_timer > 0:
        alpha = int(255 * ps.milestone_timer / 90)
        bsurf = F_TITLE.render(ps.milestone_text, True, Q_PURPLE)
        bsurf.set_alpha(alpha)
        surf.blit(bsurf, (sw // 2 - bsurf.get_width() // 2, SH // 2 - 30))

    # Screen flash on milestone
    if ps.flash_timer > 0:
        fsurf = pygame.Surface((sw, SH), pygame.SRCALPHA)
        fsurf.fill((255, 255, 255, int(60 * ps.flash_timer / 8)))
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
    global n_players, song_cursor, last_song
    btn1_rect = btn2_rect = None
    song_rects: list = []

    while True:
        clk.tick(FPS)

        # ── MENU ──────────────────────────────────────────────────────────────
        if game_state == GameState.MENU:
            btn1_rect, btn2_rect = draw_menu()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        pygame.quit(); sys.exit()
                    elif event.key == pygame.K_1:
                        n_players   = 1
                        song_cursor = 0
                        game_state  = GameState.SONG_SELECT
                    elif event.key == pygame.K_2:
                        n_players   = 2
                        song_cursor = 0
                        game_state  = GameState.SONG_SELECT
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if btn1_rect and btn1_rect.collidepoint(event.pos):
                        n_players   = 1
                        song_cursor = 0
                        game_state  = GameState.SONG_SELECT
                    elif btn2_rect and btn2_rect.collidepoint(event.pos):
                        n_players   = 2
                        song_cursor = 0
                        game_state  = GameState.SONG_SELECT
            continue

        # ── SONG SELECT ───────────────────────────────────────────────────────
        if game_state == GameState.SONG_SELECT:
            song_rects = draw_song_select(song_cursor, n_players)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        game_state = GameState.MENU
                    elif event.key == pygame.K_UP:
                        song_cursor = (song_cursor - 1) % len(SONGS)
                    elif event.key == pygame.K_DOWN:
                        song_cursor = (song_cursor + 1) % len(SONGS)
                    elif event.key == pygame.K_RETURN:
                        start_game(n_players, SONGS[song_cursor])
                    else:
                        # Number keys 1–6
                        for idx in range(len(SONGS)):
                            if event.key == getattr(pygame, f"K_{idx + 1}", None):
                                song_cursor = idx
                                start_game(n_players, SONGS[song_cursor])
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for idx, rect in enumerate(song_rects):
                        if rect.collidepoint(event.pos):
                            song_cursor = idx
                            start_game(n_players, SONGS[song_cursor])
            continue

        # ── RESULTS ───────────────────────────────────────────────────────────
        if game_state == GameState.RESULTS:
            draw_results()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        stop_game()
                    elif event.key == pygame.K_r and last_song:
                        start_game(n_players, last_song)
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

        update()
        for nid in collapsed_outcomes:
            if nid not in _seen_collapsed_nids:
                _seen_collapsed_nids.add(nid)
                q_collapsed += 1

        # ── Duration-based fade & auto-end ───────────────────────────────────
        if SONG_FILE and pygame.mixer.music.get_busy():
            elapsed_ms  = pygame.mixer.music.get_pos()
            elapsed_sec = max(0.0, elapsed_ms / 1000.0 - SONG_OFFSET)
            time_left   = SONG_DURATION - elapsed_sec
            if time_left <= 0:
                # Time's up — stop music and let notes drain
                try: pygame.mixer.music.stop()
                except Exception: pass
            elif time_left <= FADE_START:
                # Smooth fade: volume 1.0 → 0.0 over FADE_START seconds
                vol = max(0.0, time_left / FADE_START)
                try: pygame.mixer.music.set_volume(vol)
                except Exception: pass

        # ── Transition to RESULTS ─────────────────────────────────────────────
        song_done = SONG_FILE and not pygame.mixer.music.get_busy()
        if song_done and not p1.notes and (p2 is None or not p2.notes):
            try: pygame.mixer.music.set_volume(1.0)
            except Exception: pass
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
            # Option A: separate SDL2 windows on two monitors
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
            # 1P or fallback
            lbl = "PLAYER 1" if n_players == 2 else ""
            _render_player(screen, p1, ctx1 or make_ctx(SW), lbl)
            pygame.display.flip()


if __name__ == "__main__":
    main()