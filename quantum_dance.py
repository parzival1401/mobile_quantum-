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
BG          = (8,   6,  20)
LANE_BG     = (16,  13,  36)
LANE_LINE   = (45,  38,  80)
NEON        = (57, 255,  20)
GOLD        = (255, 200,   0)
WHITE       = (240, 240, 255)
RED         = (255,  55,  55)
DIM         = (90,  80, 130)
Q_PURPLE    = (210,  70, 255)
Q_WAVE      = (255,  90, 210)

# One accent colour per lane
LANE_C = [
    ( 50, 130, 255),   # 0  ←  blue
    ( 40, 220, 120),   # 1  ↓  teal
    (255, 160,  45),   # 2  ↑  orange
    (200,  70, 255),   # 3  →  purple
]

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
# Layout
# ─────────────────────────────────────────────────────────────────────────────
N_LANES    = 4
LANE_W     = 108
LANE_GAP   = 20
TOTAL_W    = N_LANES * LANE_W + (N_LANES - 1) * LANE_GAP   # 512
LX0        = (SW - TOTAL_W) // 2                            # left edge lane 0

TOP_H      = 82
BOT_H      = 88
LANE_TOP   = TOP_H
LANE_BOT   = SH - BOT_H

TARGET_Y   = LANE_BOT - 28          # centre of the hit zone
HIT_ZONE_H = 56                      # full height of hit zone rect
NOTE_W     = LANE_W - 10
NOTE_H     = 52

COLLAPSE_Y    = TARGET_Y - 195       # quantum notes collapse here
HIT_PERFECT   = 22                   # px tolerance for PERFECT
HIT_GOOD      = 48                   # px tolerance for GOOD
NOTE_SPEED    = 3.9                  # pixels / frame

KEYS   = [pygame.K_LEFT, pygame.K_DOWN, pygame.K_UP, pygame.K_RIGHT]
ARROWS = ["←", "↓", "↑", "→"]


def lx(lane):   return LX0 + lane * (LANE_W + LANE_GAP)   # left edge
def lcx(lane):  return lx(lane) + LANE_W // 2             # centre x


# ─────────────────────────────────────────────────────────────────────────────
# Note
# ─────────────────────────────────────────────────────────────────────────────
class Note:
    _nid = 0

    def __init__(self, lane: int, quantum: bool = False, lane2: int = None):
        Note._nid += 1
        self.nid         = Note._nid
        self.lane        = lane
        self.lane2       = lane2            # second ghost lane (quantum only)
        self.quantum     = quantum
        self.collapsed   = False
        self.final_lane  = lane
        self.dropped_lane = None            # lane that vanished on collapse
        self.y           = float(LANE_TOP - NOTE_H - 8)
        self.speed       = NOTE_SPEED + random.uniform(-0.25, 0.25)
        self.alive       = True
        self.hit         = False
        self.missed      = False
        self.just_collapsed = False         # true for one frame
        self.just_missed    = False         # true for one frame
        self.wave_phase  = random.uniform(0, math.tau)

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

        # Quantum collapse
        if self.quantum and not self.collapsed and self.y >= COLLAPSE_Y:
            self.collapsed      = True
            self.just_collapsed = True
            self.final_lane     = random.choice([self.lane, self.lane2])
            self.dropped_lane   = self.lane2 if self.final_lane == self.lane else self.lane
            self.lane           = self.final_lane

        # Miss: slipped past hit zone
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
        self.x  += self.vx
        self.y  += self.vy
        self.vy += 0.18
        self.life -= 1

    def draw(self):
        if self.life <= 0: return
        r, g, b = self.color
        pygame.draw.circle(screen, (r, g, b),
                           (int(self.x), int(self.y)), max(1, self.size))


# ─────────────────────────────────────────────────────────────────────────────
# Floating feedback text
# ─────────────────────────────────────────────────────────────────────────────
class FloatText:
    def __init__(self, text, x, y, color, font=None):
        self.surf = (font or F_MED).render(text, True, color)
        self.x, self.y = float(x - self.surf.get_width() // 2), float(y)
        self.life = 52
        self.max_life = 52

    def update(self):
        self.y    -= 1.3
        self.life -= 1

    def draw(self):
        if self.life <= 0: return
        alpha = int(255 * self.life / self.max_life)
        tmp   = self.surf.copy()
        tmp.set_alpha(alpha)
        screen.blit(tmp, (int(self.x), int(self.y)))


# ─────────────────────────────────────────────────────────────────────────────
# Game state
# ─────────────────────────────────────────────────────────────────────────────
notes      : list[Note]      = []
particles  : list[Particle]  = []
floats     : list[FloatText] = []

score        = 0
combo        = 0
max_combo    = 0
q_collapsed  = 0       # quantum collapse counter
q_total      = 0       # total quantum notes spawned
tick         = 0
spawn_timer  = 55      # first note in ~1 s
key_flash    = [0] * N_LANES


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

    # Find the closest note that belongs to this lane
    best, best_d = None, 9999
    for note in notes:
        if not note.alive or note.hit:
            continue
        # Quantum in superposition: either ghost lane counts
        if note.quantum and not note.collapsed:
            in_lane = lane in (note.lane, note.lane2)
        else:
            in_lane = lane == note.lane
        if not in_lane:
            continue
        d = abs(note.cy() - TARGET_Y)
        if d < best_d:
            best_d, best = d, note

    if best is None or best_d > HIT_GOOD:
        combo = 0
        pop("MISS", lane, color=RED)
        return

    quality = best.in_hit_zone()
    if quality:
        best.hit   = True
        best.alive = False
        combo += 1
        if quality == "PERFECT":
            pts = 300 * max(1, combo // 5)
            score += pts
            pop("PERFECT!", lane, color=GOLD, font=F_MED)
            burst(lcx(lane), TARGET_Y, LANE_C[lane], 20)
        else:
            pts = 100 * max(1, combo // 10)
            score += pts
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
        spawn_timer = random.randint(72, 145)

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
            floats.append(FloatText("MISS", lcx(note.lane),
                                    TARGET_Y - 42, RED))

    notes[:] = [n for n in notes if n.alive]

    max_combo = max(max_combo, combo)

    for p in particles: p.update()
    particles[:] = [p for p in particles if p.life > 0]
    for f in floats:    f.update()
    floats[:]    = [f for f in floats    if f.life > 0]

    for i in range(N_LANES):
        if key_flash[i] > 0: key_flash[i] -= 1


# ─────────────────────────────────────────────────────────────────────────────
# Draw — lanes background
# ─────────────────────────────────────────────────────────────────────────────
def draw_lanes():
    for i in range(N_LANES):
        x    = lx(i)
        rect = pygame.Rect(x, LANE_TOP, LANE_W, LANE_BOT - LANE_TOP)
        pygame.draw.rect(screen, LANE_BG, rect)
        pygame.draw.rect(screen, LANE_LINE, rect, 1)

        if key_flash[i] > 0:
            r, g, b = LANE_C[i]
            a = int(90 * key_flash[i] / 14)
            s = pygame.Surface((LANE_W, LANE_BOT - LANE_TOP), pygame.SRCALPHA)
            s.fill((r, g, b, a))
            screen.blit(s, (x, LANE_TOP))

    # Collapse threshold line (subtle dashed)
    for i in range(N_LANES):
        x = lx(i)
        pygame.draw.line(screen, (60, 30, 80),
                         (x + 4, int(COLLAPSE_Y)), (x + LANE_W - 4, int(COLLAPSE_Y)), 1)

    cl = F_XSM.render("◀ collapse zone", True, (70, 35, 90))
    screen.blit(cl, (lx(N_LANES - 1) + LANE_W + 6, int(COLLAPSE_Y) - 7))


# ─────────────────────────────────────────────────────────────────────────────
# Draw — hit zone
# ─────────────────────────────────────────────────────────────────────────────
def draw_hit_zone():
    for i in range(N_LANES):
        x      = lx(i)
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
# Draw — classical note
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


# ─────────────────────────────────────────────────────────────────────────────
# Draw — quantum note  (superposition + collapse)
# ─────────────────────────────────────────────────────────────────────────────
def draw_quantum(note: Note):
    if note.collapsed:
        # Solid note in final lane  (same shape as classical, quantum colour)
        r, g, b = Q_PURPLE
        cx   = lcx(note.lane)
        rect = pygame.Rect(cx - NOTE_W // 2, int(note.y), NOTE_W, NOTE_H)
        pygame.draw.rect(screen, (r // 3, g // 3, b // 3), rect, border_radius=9)
        pygame.draw.rect(screen, (r, g, b), rect, 3, border_radius=9)
        ar = F_ARROW.render(ARROWS[note.lane], True, (r, g, b))
        screen.blit(ar, (cx - ar.get_width() // 2,
                         int(note.y) + (NOTE_H - ar.get_height()) // 2))
        return

    # ── Superposition: ghost in two lanes + wave ──────────────────────────
    dist_to_collapse = max(0.0, COLLAPSE_Y - note.y)
    urgency  = 1.0 - min(dist_to_collapse / 200.0, 1.0)   # 0 far, 1 at collapse
    pulse    = 0.55 + 0.45 * math.sin(tick * 0.14 + note.wave_phase)
    af       = 0.35 + 0.45 * pulse + 0.20 * urgency        # alpha factor 0.35–1.0

    for ghost_lane in (note.lane, note.lane2):
        r, g, b = Q_PURPLE
        ri, gi, bi = int(r * af), int(g * af * 0.35), int(b * af)
        cx   = lcx(ghost_lane)
        rect = pygame.Rect(cx - NOTE_W // 2, int(note.y), NOTE_W, NOTE_H)
        pygame.draw.rect(screen, (ri // 3, gi // 3, bi // 3), rect, border_radius=9)
        pygame.draw.rect(screen, (ri, gi, bi), rect, 2, border_radius=9)
        qm = F_ARROW.render("?", True, (ri, gi, bi))
        screen.blit(qm, (cx - qm.get_width() // 2,
                         int(note.y) + (NOTE_H - qm.get_height()) // 2))

    # Sine wave between the two ghosts
    xa = lcx(note.lane)
    xb = lcx(note.lane2)
    x0, x1 = min(xa, xb), max(xa, xb)
    wy  = int(note.y) + NOTE_H // 2
    pts = []
    steps = max(2, x1 - x0)
    for i in range(steps + 1):
        xp = x0 + i
        yp = wy + math.sin(i * math.pi * 0.14 + tick * 0.18 + note.wave_phase) \
             * (5 + 5 * urgency)
        pts.append((xp, int(yp)))
    if len(pts) >= 2:
        wr, wg, wb = Q_WAVE
        wc = (int(wr * af), int(wg * af * 0.5), int(wb * af))
        pygame.draw.lines(screen, wc, False, pts, 2)

    # "superposition" label above (fade when near collapse)
    if dist_to_collapse > 60:
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

    cb_color = GOLD if combo >= 10 else WHITE
    cb = F_MED.render(f"COMBO  ×{combo}", True, cb_color)
    screen.blit(cb, (SW - cb.get_width() - 18, 10))

    mc = F_SM.render(f"best ×{max_combo}", True, DIM)
    screen.blit(mc, (SW - mc.get_width() - 18, 32))

    qc = F_SM.render(f"collapses: {q_collapsed} / {q_total}", True, (170, 70, 230))
    screen.blit(qc, (18, 34))

    sub = F_XSM.render(
        "Classical notes: always ONE lane.   "
        "Quantum notes: TWO lanes at once — collapse to one before the hit zone.",
        True, DIM,
    )
    screen.blit(sub, (SW // 2 - sub.get_width() // 2, 57))


def draw_bottom():
    y0 = SH - BOT_H
    pygame.draw.rect(screen, (10, 8, 26), (0, y0, SW, BOT_H))
    pygame.draw.line(screen, (55, 45, 100), (0, y0), (SW, y0))

    # Legend left
    for i, (txt, col) in enumerate([
        ("■  Classical note — stays in its lane", WHITE),
        ("⬡  Quantum note  — in 2 lanes until collapse  (50 / 50)", Q_PURPLE),
    ]):
        t = F_SM.render(txt, True, col)
        screen.blit(t, (18, y0 + 12 + i * 22))

    # Explanation right
    lines = [
        "In quantum mechanics a particle can be in",
        "multiple states at once — until it is MEASURED.",
        "That measurement forces a definite outcome.",
    ]
    rx = SW - 18
    for i, line in enumerate(lines):
        t = F_XSM.render(line, True, DIM)
        screen.blit(t, (rx - t.get_width(), y0 + 10 + i * 17))


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

        update()

        # ── Render ────────────────────────────────────────────────────────
        screen.fill(BG)
        draw_lanes()
        draw_hit_zone()

        for note in notes:
            if note.quantum:
                draw_quantum(note)
            else:
                draw_classical(note)

        for p in particles: p.draw()
        for f in floats:    f.draw()

        draw_top()
        draw_bottom()
        pygame.display.flip()


if __name__ == "__main__":
    main()
