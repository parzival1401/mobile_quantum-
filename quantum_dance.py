"""
quantum_dance.py  —  Quantum Dance
====================================
Quantum Exhibition  |  Classical vs Quantum Computing

A Dance-Dance-Revolution-style game that shows the difference between
classical and quantum behaviour:

  CLASSICAL notes  — solid, always in ONE lane.  You know exactly where
                     they are the moment they appear.

  QUANTUM notes    — appear as ghosts in TWO lanes simultaneously
                     (superposition), connected by a glowing wave.
                     As they approach the hit zone they COLLAPSE to ONE
                     lane at random (50 / 50).  Only then do you know
                     which key to press.

Controls
--------
  ←  Left lane       ↓  Centre-left lane
  ↑  Centre-right    →  Right lane
  Drag sliders with the mouse to change game parameters
  ESC  quit
"""

import pygame
import sys
import random
import math

pygame.init()

# ─────────────────────────────────────────────────────────────────────────────
# Screen & timing
# ─────────────────────────────────────────────────────────────────────────────
SW, SH = 960, 720
FPS    = 60
screen = pygame.display.set_mode((SW, SH))
pygame.display.set_caption("Quantum Dance  |  Quantum Exhibition")
clk    = pygame.time.Clock()

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

# Slider accent colours
SL_SPAWN_C    = ( 80, 200, 255)   # cyan-blue
SL_SPEED_C    = ( 80, 255, 160)   # mint-green
SL_COLLAPSE_C = (210,  70, 255)   # purple (matches quantum)

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

F_TITLE = _f(34)
F_MED   = _f(18)
F_SM    = _f(14)
F_XSM   = _f(11, bold=False)
F_ARROW = _f(26)

# ─────────────────────────────────────────────────────────────────────────────
# Layout constants
# ─────────────────────────────────────────────────────────────────────────────
N_LANES  = 4
LANE_W   = 108
LANE_GAP = 20
TOTAL_W  = N_LANES * LANE_W + (N_LANES - 1) * LANE_GAP   # 512
LX0      = (SW - TOTAL_W) // 2                            # 224 — left edge lane 0

TOP_H    = 82
BOT_H    = 88
LANE_TOP = TOP_H
LANE_BOT = SH - BOT_H                    # 632

TARGET_Y  = LANE_BOT - 28                # hit-zone centre y
HIT_ZONE_H = 56
NOTE_W    = LANE_W - 10
NOTE_H    = 52

HIT_PERFECT = 22
HIT_GOOD    = 48

KEYS   = [pygame.K_LEFT, pygame.K_DOWN, pygame.K_UP, pygame.K_RIGHT]
ARROWS = ["←", "↓", "↑", "→"]

# Right-panel x boundaries
RP_X = LX0 + TOTAL_W       # 736 — right panel starts here
RP_W = SW - RP_X            # 224 — right panel width


def lx(lane):  return LX0 + lane * (LANE_W + LANE_GAP)
def lcx(lane): return lx(lane) + LANE_W // 2


# ─────────────────────────────────────────────────────────────────────────────
# Vertical Slider widget
# ─────────────────────────────────────────────────────────────────────────────
class Slider:
    """
    Draggable vertical slider.
    Convention: handle at TOP  →  maximum value
                handle at BOTTOM →  minimum value
    """
    TW = 12    # track width  (px)
    HR = 13    # handle radius (px)

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
        self.fmt     = value_fmt   # e.g. "{:.1f}"  or  "{:.0f} px"
        self.color   = color
        self.desc    = desc        # short description lines shown below value
        self.dragging = False

    # ── value ↔ screen-y mapping ─────────────────────────────────────────
    def _hy(self):
        """Handle y: high value → top (small y), low value → bottom (large y)."""
        t = (self.val - self.min_val) / (self.max_val - self.min_val)
        return int(self.y_top + (1.0 - t) * self.height)

    def _y_to_val(self, sy):
        rel = max(0.0, min(float(self.height), sy - self.y_top))
        t   = 1.0 - rel / self.height
        return self.min_val + t * (self.max_val - self.min_val)

    # ── events ───────────────────────────────────────────────────────────
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

    # ── draw ─────────────────────────────────────────────────────────────
    def draw(self):
        r, g, b = self.color
        hy  = self._hy()
        tx  = self.cx - self.TW // 2
        y_b = self.y_top + self.height          # bottom of track

        # Track
        pygame.draw.rect(screen, (22, 18, 42),
                         (tx, self.y_top, self.TW, self.height), border_radius=6)

        # Filled part (handle → bottom) — shows "remaining" level
        fill_h = y_b - hy
        if fill_h > 0:
            pygame.draw.rect(screen, (r // 3, g // 3, b // 3),
                             (tx, hy, self.TW, fill_h), border_radius=6)

        pygame.draw.rect(screen, (r // 2, g // 2, b // 2),
                         (tx, self.y_top, self.TW, self.height), 2, border_radius=6)

        # Handle glow ring
        pygame.draw.circle(screen, (r // 5, g // 5, b // 5),
                           (self.cx, hy), self.HR + 7)
        # Handle
        pygame.draw.circle(screen, self.color, (self.cx, hy), self.HR)
        # Inner white dot
        pygame.draw.circle(screen, WHITE, (self.cx, hy), max(1, self.HR - 7))

        # Title above track
        t = F_SM.render(self.title, True, self.color)
        screen.blit(t, (self.cx - t.get_width() // 2, self.y_top - 22))

        # MAX label (top of track)
        mx_t = F_XSM.render("▲ MAX", True, (r // 2, g // 2, b // 2))
        screen.blit(mx_t, (self.cx - mx_t.get_width() // 2, self.y_top - 36))

        # MIN label (bottom of track)
        mn_t = F_XSM.render("▼ MIN", True, (r // 2, g // 2, b // 2))
        screen.blit(mn_t, (self.cx - mn_t.get_width() // 2, y_b + 4))

        # Current value
        val_str = self.fmt.format(self.val)
        vt = F_MED.render(val_str, True, self.color)
        screen.blit(vt, (self.cx - vt.get_width() // 2, y_b + 18))

        # Description lines
        for i, line in enumerate(self.desc):
            dt = F_XSM.render(line, True, DIM)
            screen.blit(dt, (self.cx - dt.get_width() // 2,
                             y_b + 36 + i * 13))


# ─────────────────────────────────────────────────────────────────────────────
# Slider instances
# ─────────────────────────────────────────────────────────────────────────────
_SL_Y   = TOP_H + 70       # track top y
_SL_H   = LANE_BOT - _SL_Y - 80  # track height  (≈ 482 px)

# Left panel  — one slider centred in 224 px
_CX_SPAWN    = LX0 // 2                         # ≈ 112

# Right panel — two sliders side by side inside 224 px
_CX_SPEED    = RP_X + RP_W * 1 // 3            # ≈ 811
_CX_COLLAPSE = RP_X + RP_W * 2 // 3            # ≈ 885

spawn_slider = Slider(
    cx=_CX_SPAWN, y_top=_SL_Y, height=_SL_H,
    min_val=1.0, max_val=10.0, init_val=4.5,
    title="SPAWN",
    value_fmt="{:.1f}",
    color=SL_SPAWN_C,
    desc=("notes / sec",
          "↑ more notes",
          "↓ fewer notes"),
)

speed_slider = Slider(
    cx=_CX_SPEED, y_top=_SL_Y, height=_SL_H,
    min_val=1.5, max_val=9.0, init_val=3.9,
    title="SPEED",
    value_fmt="{:.1f}",
    color=SL_SPEED_C,
    desc=("fall speed",
          "px / frame"),
)

collapse_slider = Slider(
    cx=_CX_COLLAPSE, y_top=_SL_Y, height=_SL_H,
    min_val=40, max_val=430, init_val=195,
    title="COLLAPSE",
    value_fmt="{:.0f}px",
    color=SL_COLLAPSE_C,
    desc=("above hit zone",
          "↑ more time",
          "↓ surprise!"),
)

ALL_SLIDERS = [spawn_slider, speed_slider, collapse_slider]


# ─────────────────────────────────────────────────────────────────────────────
# Dynamic game-parameter accessors  (read slider values at runtime)
# ─────────────────────────────────────────────────────────────────────────────
def get_collapse_y() -> int:
    """Y position where quantum notes collapse (above hit zone)."""
    return int(TARGET_Y - collapse_slider.val)


def get_fall_speed() -> float:
    """Note fall speed in pixels/frame."""
    return speed_slider.val


def get_spawn_interval() -> int:
    """Base frame interval between note spawns (fewer frames = faster)."""
    # spawn_slider.val 1→10 maps to interval 210→25 frames
    return max(25, int(215 - spawn_slider.val * 19.5))


# ─────────────────────────────────────────────────────────────────────────────
# Note
# ─────────────────────────────────────────────────────────────────────────────
class Note:
    _nid = 0

    def __init__(self, lane: int, quantum: bool = False, lane2: int = None):
        Note._nid += 1
        self.nid          = Note._nid
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
        self.wave_phase   = random.uniform(0, math.tau)

    def cy(self):
        return self.y + NOTE_H / 2

    def in_hit_zone(self):
        d = abs(self.cy() - TARGET_Y)
        if d <= HIT_PERFECT: return "PERFECT"
        if d <= HIT_GOOD:    return "GOOD"
        return None

    def update(self):
        self.just_collapsed = False
        self.just_missed    = False
        self.y += self.speed

        # Quantum collapse — check against dynamic threshold
        if self.quantum and not self.collapsed and self.y >= get_collapse_y():
            self.collapsed      = True
            self.just_collapsed = True
            self.final_lane     = random.choice([self.lane, self.lane2])
            self.dropped_lane   = (self.lane2 if self.final_lane == self.lane
                                   else self.lane)
            self.lane = self.final_lane

        # Miss
        if (not self.hit and not self.missed
                and self.y > TARGET_Y + HIT_ZONE_H + 18):
            self.missed      = True
            self.just_missed = True
            self.alive       = False


# ─────────────────────────────────────────────────────────────────────────────
# Particle
# ─────────────────────────────────────────────────────────────────────────────
class Particle:
    def __init__(self, x, y, color, speed_scale=1.0):
        a  = random.uniform(0, math.tau)
        sp = random.uniform(1.5, 6.0) * speed_scale
        self.x, self.y   = float(x), float(y)
        self.vx, self.vy = math.cos(a) * sp, math.sin(a) * sp - 1.5
        self.life = random.randint(22, 48)
        self.max_life = self.life
        self.color = color
        self.size  = random.randint(2, 5)

    def update(self):
        self.x += self.vx;  self.y += self.vy
        self.vy += 0.18;    self.life -= 1

    def draw(self):
        if self.life <= 0: return
        pygame.draw.circle(screen, self.color,
                           (int(self.x), int(self.y)), max(1, self.size))


# ─────────────────────────────────────────────────────────────────────────────
# Floating feedback text
# ─────────────────────────────────────────────────────────────────────────────
class FloatText:
    def __init__(self, text, x, y, color, font=None):
        self.surf  = (font or F_MED).render(text, True, color)
        self.x     = float(x - self.surf.get_width() // 2)
        self.y     = float(y)
        self.life  = 52
        self.max_life = 52

    def update(self):
        self.y -= 1.3;  self.life -= 1

    def draw(self):
        if self.life <= 0: return
        tmp = self.surf.copy()
        tmp.set_alpha(int(255 * self.life / self.max_life))
        screen.blit(tmp, (int(self.x), int(self.y)))


# ─────────────────────────────────────────────────────────────────────────────
# Game state
# ─────────────────────────────────────────────────────────────────────────────
notes     : list[Note]      = []
particles : list[Particle]  = []
floats    : list[FloatText] = []

score       = 0
combo       = 0
max_combo   = 0
q_collapsed = 0
q_total     = 0
tick        = 0
spawn_timer = 55
key_flash   = [0] * N_LANES


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def burst(x, y, color, n=14, speed=1.0):
    for _ in range(n):
        particles.append(Particle(x, y, color, speed))


def pop(text, lane, y_offset=0, color=WHITE, font=None):
    floats.append(FloatText(text, lcx(lane), TARGET_Y - 42 + y_offset, color, font))


# ─────────────────────────────────────────────────────────────────────────────
# Spawner
# ─────────────────────────────────────────────────────────────────────────────
def spawn_note():
    global q_total
    if random.random() < 0.38:
        a, b = random.sample(range(N_LANES), 2)
        notes.append(Note(a, quantum=True, lane2=b))
        q_total += 1
    else:
        notes.append(Note(random.randint(0, N_LANES - 1)))


# ─────────────────────────────────────────────────────────────────────────────
# Input
# ─────────────────────────────────────────────────────────────────────────────
def handle_key(lane: int):
    global combo, score
    key_flash[lane] = 14

    best, best_d = None, 9999
    for note in notes:
        if not note.alive or note.hit: continue
        if note.quantum and not note.collapsed:
            in_lane = lane in (note.lane, note.lane2)
        else:
            in_lane = lane == note.lane
        if not in_lane: continue
        d = abs(note.cy() - TARGET_Y)
        if d < best_d: best_d, best = d, note

    if best is None or best_d > HIT_GOOD:
        combo = 0
        pop("MISS", lane, color=RED)
        return

    quality = best.in_hit_zone()
    if quality:
        best.hit = best.alive = False; best.alive = False
        best.hit = True
        combo += 1
        if quality == "PERFECT":
            score += 300 * max(1, combo // 5)
            pop("PERFECT!", lane, color=GOLD, font=F_MED)
            burst(lcx(lane), TARGET_Y, LANE_C[lane], 20)
        else:
            score += 100 * max(1, combo // 10)
            pop("GOOD", lane, color=WHITE)
            burst(lcx(lane), TARGET_Y, LANE_C[lane], 9)
    else:
        combo = 0
        pop("EARLY", lane, color=(255, 180, 0))


# ─────────────────────────────────────────────────────────────────────────────
# Update
# ─────────────────────────────────────────────────────────────────────────────
def update():
    global spawn_timer, q_collapsed, tick, combo, max_combo

    tick += 1
    spawn_timer -= 1
    if spawn_timer <= 0:
        spawn_note()
        base = get_spawn_interval()
        spawn_timer = random.randint(int(base * 0.78), int(base * 1.35))

    for note in notes:
        note.update()
        if note.just_collapsed:
            q_collapsed += 1
            burst(lcx(note.dropped_lane), note.y + NOTE_H // 2, Q_WAVE, 16, 0.9)
            pop("COLLAPSED!", note.dropped_lane,
                y_offset=int(note.y - TARGET_Y) + NOTE_H // 2,
                color=Q_PURPLE, font=F_SM)
        if note.just_missed:
            combo = 0
            floats.append(FloatText("MISS", lcx(note.lane), TARGET_Y - 42, RED))

    notes[:] = [n for n in notes if n.alive]
    max_combo = max(max_combo, combo)

    for p in particles: p.update()
    particles[:] = [p for p in particles if p.life > 0]
    for f in floats:    f.update()
    floats[:]    = [f for f in floats    if f.life > 0]

    for i in range(N_LANES):
        if key_flash[i] > 0: key_flash[i] -= 1


# ─────────────────────────────────────────────────────────────────────────────
# Draw — side panels (slider backgrounds)
# ─────────────────────────────────────────────────────────────────────────────
def draw_panels():
    # Left panel
    pygame.draw.rect(screen, PANEL_BG, (0, LANE_TOP, LX0, LANE_BOT - LANE_TOP))
    pygame.draw.line(screen, (40, 32, 72), (LX0, LANE_TOP), (LX0, LANE_BOT), 1)

    # Right panel
    pygame.draw.rect(screen, PANEL_BG, (RP_X, LANE_TOP, RP_W, LANE_BOT - LANE_TOP))
    pygame.draw.line(screen, (40, 32, 72), (RP_X, LANE_TOP), (RP_X, LANE_BOT), 1)

    # Panel labels at top
    lp_lbl = F_XSM.render("SPAWN RATE", True, (60, 55, 90))
    screen.blit(lp_lbl, (LX0 // 2 - lp_lbl.get_width() // 2, LANE_TOP + 8))

    rp_lbl = F_XSM.render("NOTE CONTROLS", True, (60, 55, 90))
    screen.blit(rp_lbl, (RP_X + RP_W // 2 - rp_lbl.get_width() // 2, LANE_TOP + 8))


# ─────────────────────────────────────────────────────────────────────────────
# Draw — lanes
# ─────────────────────────────────────────────────────────────────────────────
def draw_lanes():
    for i in range(N_LANES):
        x    = lx(i)
        rect = pygame.Rect(x, LANE_TOP, LANE_W, LANE_BOT - LANE_TOP)
        pygame.draw.rect(screen, LANE_BG, rect)
        pygame.draw.rect(screen, LANE_LINE, rect, 1)

        if key_flash[i] > 0:
            r, g, b = LANE_C[i]
            s = pygame.Surface((LANE_W, LANE_BOT - LANE_TOP), pygame.SRCALPHA)
            s.fill((r, g, b, int(90 * key_flash[i] / 14)))
            screen.blit(s, (x, LANE_TOP))

    # Dynamic collapse-zone line
    cy = get_collapse_y()
    for i in range(N_LANES):
        x = lx(i)
        pygame.draw.line(screen, (80, 35, 105),
                         (x + 4, cy), (x + LANE_W - 4, cy), 1)

    cl = F_XSM.render("◀ collapse zone", True, (100, 45, 130))
    screen.blit(cl, (lx(N_LANES - 1) + LANE_W + 4, cy - 7))


# ─────────────────────────────────────────────────────────────────────────────
# Draw — hit zone
# ─────────────────────────────────────────────────────────────────────────────
def draw_hit_zone():
    for i in range(N_LANES):
        x       = lx(i)
        r, g, b = LANE_C[i]
        hz      = pygame.Rect(x + 4, TARGET_Y - HIT_ZONE_H // 2,
                              LANE_W - 8, HIT_ZONE_H)
        pygame.draw.rect(screen, (r // 5, g // 5, b // 5), hz, border_radius=10)
        pygame.draw.rect(screen, (r // 2, g // 2, b // 2), hz, 2, border_radius=10)
        pygame.draw.line(screen, (r, g, b),
                         (x + 6, TARGET_Y), (x + LANE_W - 6, TARGET_Y), 2)
        lbl = F_ARROW.render(ARROWS[i], True, (r, g, b))
        screen.blit(lbl, (lcx(i) - lbl.get_width() // 2,
                          TARGET_Y + HIT_ZONE_H // 2 + 5))


# ─────────────────────────────────────────────────────────────────────────────
# Draw — notes
# ─────────────────────────────────────────────────────────────────────────────
def draw_classical(note: Note):
    r, g, b = LANE_C[note.lane]
    cx      = lcx(note.lane)
    rect    = pygame.Rect(cx - NOTE_W // 2, int(note.y), NOTE_W, NOTE_H)
    pygame.draw.rect(screen, (r // 3, g // 3, b // 3), rect, border_radius=9)
    pygame.draw.rect(screen, (r, g, b), rect, 3, border_radius=9)
    ar = F_ARROW.render(ARROWS[note.lane], True, (r, g, b))
    screen.blit(ar, (cx - ar.get_width() // 2,
                     int(note.y) + (NOTE_H - ar.get_height()) // 2))


def draw_quantum(note: Note):
    if note.collapsed:
        r, g, b = Q_PURPLE
        cx   = lcx(note.lane)
        rect = pygame.Rect(cx - NOTE_W // 2, int(note.y), NOTE_W, NOTE_H)
        pygame.draw.rect(screen, (r // 3, g // 3, b // 3), rect, border_radius=9)
        pygame.draw.rect(screen, (r, g, b), rect, 3, border_radius=9)
        ar = F_ARROW.render(ARROWS[note.lane], True, (r, g, b))
        screen.blit(ar, (cx - ar.get_width() // 2,
                         int(note.y) + (NOTE_H - ar.get_height()) // 2))
        return

    # Superposition: two ghosts + sine wave
    cy_collapse = get_collapse_y()
    dist  = max(0.0, cy_collapse - note.y)
    urgency = 1.0 - min(dist / 200.0, 1.0)
    pulse   = 0.55 + 0.45 * math.sin(tick * 0.14 + note.wave_phase)
    af      = 0.35 + 0.45 * pulse + 0.20 * urgency

    for gl in (note.lane, note.lane2):
        r, g, b = Q_PURPLE
        ri, gi, bi = int(r * af), int(g * af * 0.35), int(b * af)
        cx   = lcx(gl)
        rect = pygame.Rect(cx - NOTE_W // 2, int(note.y), NOTE_W, NOTE_H)
        pygame.draw.rect(screen, (ri // 3, gi // 3, bi // 3), rect, border_radius=9)
        pygame.draw.rect(screen, (ri, gi, bi), rect, 2, border_radius=9)
        qm = F_ARROW.render("?", True, (ri, gi, bi))
        screen.blit(qm, (cx - qm.get_width() // 2,
                         int(note.y) + (NOTE_H - qm.get_height()) // 2))

    xa, xb = lcx(note.lane), lcx(note.lane2)
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
        pygame.draw.lines(screen, (int(wr * af), int(wg * af * 0.5), int(wb * af)),
                          False, pts, 2)

    if dist > 60:
        mx  = (xa + xb) // 2
        slb = F_XSM.render("superposition", True,
                            (int(180 * af), 30, int(220 * af)))
        screen.blit(slb, (mx - slb.get_width() // 2, int(note.y) - 17))


# ─────────────────────────────────────────────────────────────────────────────
# Draw — top & bottom bars
# ─────────────────────────────────────────────────────────────────────────────
def draw_top():
    pygame.draw.rect(screen, (10, 8, 26), (0, 0, SW, TOP_H))
    pygame.draw.line(screen, (55, 45, 100), (0, TOP_H - 1), (SW, TOP_H - 1))

    title = F_TITLE.render("✦  QUANTUM DANCE  ✦", True, Q_PURPLE)
    screen.blit(title, (SW // 2 - title.get_width() // 2, 8))

    sc = F_MED.render(f"SCORE  {score:07d}", True, GOLD)
    screen.blit(sc, (18, 10))

    cb = F_MED.render(f"COMBO  ×{combo}", True, GOLD if combo >= 10 else WHITE)
    screen.blit(cb, (SW - cb.get_width() - 18, 10))
    mc = F_SM.render(f"best ×{max_combo}", True, DIM)
    screen.blit(mc, (SW - mc.get_width() - 18, 32))
    qc = F_SM.render(f"collapses: {q_collapsed}/{q_total}", True, (170, 70, 230))
    screen.blit(qc, (18, 34))

    sub = F_XSM.render(
        "Classical notes: ONE lane.   "
        "Quantum notes: TWO lanes — collapse to one before the hit zone.",
        True, DIM)
    screen.blit(sub, (SW // 2 - sub.get_width() // 2, 57))


def draw_bottom():
    y0 = SH - BOT_H
    pygame.draw.rect(screen, (10, 8, 26), (0, y0, SW, BOT_H))
    pygame.draw.line(screen, (55, 45, 100), (0, y0), (SW, y0))

    for i, (txt, col) in enumerate([
        ("■  Classical — stays in its lane", WHITE),
        ("⬡  Quantum  — 2 lanes, collapses 50/50", Q_PURPLE),
    ]):
        screen.blit(F_SM.render(txt, True, col), (18, y0 + 12 + i * 22))

    lines = ["In quantum mechanics a particle can be",
             "in multiple states until it is MEASURED."]
    for i, line in enumerate(lines):
        t = F_XSM.render(line, True, DIM)
        screen.blit(t, (SW - t.get_width() - 18, y0 + 14 + i * 17))


# ─────────────────────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────────────────────
def main():
    while True:
        clk.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                for i, k in enumerate(KEYS):
                    if event.key == k:
                        handle_key(i)

            # Pass all mouse events to sliders
            for sl in ALL_SLIDERS:
                sl.handle_event(event)

        update()

        # ── Render ────────────────────────────────────────────────────────
        screen.fill(BG)
        draw_panels()          # side panel backgrounds
        draw_lanes()           # lane columns + collapse line
        draw_hit_zone()        # hit targets

        for note in notes:
            (draw_quantum if note.quantum else draw_classical)(note)

        for p in particles: p.draw()
        for f in floats:    f.draw()

        # Draw sliders on top of panels
        for sl in ALL_SLIDERS:
            sl.draw()

        draw_top()
        draw_bottom()
        pygame.display.flip()


if __name__ == "__main__":
    main()
