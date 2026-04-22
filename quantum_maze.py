"""
quantum_maze.py  —  Quantum Maze
==================================
Quantum Exhibition  |  Superposition Demo

The character stands at a junction and ROTATES, sweeping its field of view.
Every open path inside the FOV is in SUPERPOSITION — shown as glowing purple
corridors.  When a path is visible you also see a DIM PREVIEW of where it
leads (the paths branching from the next cell).

Press SPACE to COLLAPSE the superposition:
  • Only paths currently visible in the FOV are candidates.
  • One path is chosen at random — pure quantum chance.
  • The character moves to the next junction and the process repeats.

Sliders
-------
  SPEED slider (left panel)  —  how fast the FOV rotates
  FOV   slider (right panel) —  how wide the cone of view is

Controls
--------
  SPACE  —  collapse and move
  R      —  new maze
  ESC    —  quit
"""

import pygame
import sys
import random
import math

pygame.init()

SW, SH = 900, 720
FPS    = 60
screen = pygame.display.set_mode((SW, SH))
pygame.display.set_caption("Quantum Maze  |  Quantum Exhibition")
clk    = pygame.time.Clock()

# ─────────────────────────────────────────────────────────────────────────────
# Colours
# ─────────────────────────────────────────────────────────────────────────────
BG         = (8,   6,  20)
WALL_C     = (45,  60, 120)
FLOOR_C    = (14,  12,  32)
FLOOR_VIS  = (18,  22,  50)
FOV_C      = (255, 220,  60)
SUPER_C    = (160,  60, 255)
PREVIEW_C  = ( 60, 200, 140)   # ghost preview of onward paths
CHAR_C     = ( 80, 220, 255)
COLLAPSE_C = (255, 200,  50)
VISITED_C  = ( 30, 160,  90)
Q_PURPLE   = (210,  70, 255)
DIM        = ( 75,  70, 115)
WHITE      = (240, 240, 255)
PANEL_BG   = (10,   8,  26)
WARN_C     = (255, 100,  60)

SL_SPEED_C = (255, 140,  50)   # orange — rotation speed slider
SL_FOV_C   = (255, 220,  60)   # gold   — FOV width slider

# ─────────────────────────────────────────────────────────────────────────────
# Fonts
# ─────────────────────────────────────────────────────────────────────────────
def _f(sz, bold=True):
    for n in ("Segoe UI", "Arial", "DejaVu Sans"):
        try:
            return pygame.font.SysFont(n, sz, bold=bold)
        except Exception:
            pass
    return pygame.font.Font(None, sz)

F_TITLE = _f(32)
F_MED   = _f(18)
F_SM    = _f(14)
F_XSM   = _f(11, bold=False)

# ─────────────────────────────────────────────────────────────────────────────
# Layout
# ─────────────────────────────────────────────────────────────────────────────
COLS   = 9
ROWS   = 9
CELL   = 56
TOP_H  = 82
BOT_H  = 86

MAZE_W = COLS * CELL       # 504
MAZE_H = ROWS * CELL       # 504
MX0    = (SW - MAZE_W) // 2   # 198 — left edge of maze
MY0    = TOP_H                # 82  — top edge of maze

# Direction table: (row_delta, col_delta, angle_deg, label)
# Angles: E=0°, S=90°, W=180°, N=270°  (pygame y-down)
DIRS = [
    ( 0,  1,   0, "E"),
    ( 1,  0,  90, "S"),
    ( 0, -1, 180, "W"),
    (-1,  0, 270, "N"),
]

FOV_RADIUS = int(CELL * 1.9)   # visual radius of the drawn cone

# ─────────────────────────────────────────────────────────────────────────────
# Vertical Slider widget
# ─────────────────────────────────────────────────────────────────────────────
class Slider:
    TW = 12   # track width px
    HR = 13   # handle radius px

    def __init__(self, cx, y_top, height, min_val, max_val, init_val,
                 title, value_fmt, color, desc=()):
        self.cx       = cx
        self.y_top    = y_top
        self.height   = height
        self.min_val  = float(min_val)
        self.max_val  = float(max_val)
        self.val      = float(init_val)
        self.title    = title
        self.fmt      = value_fmt
        self.color    = color
        self.desc     = desc
        self.dragging = False

    def _hy(self):
        t = (self.val - self.min_val) / (self.max_val - self.min_val)
        return int(self.y_top + (1.0 - t) * self.height)

    def _y_to_val(self, sy):
        rel = max(0.0, min(float(self.height), sy - self.y_top))
        return self.min_val + (1.0 - rel / self.height) * (self.max_val - self.min_val)

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

    def draw(self):
        r, g, b = self.color
        hy  = self._hy()
        tx  = self.cx - self.TW // 2
        y_b = self.y_top + self.height

        pygame.draw.rect(screen, (22, 18, 42),
                         (tx, self.y_top, self.TW, self.height), border_radius=6)
        fill_h = y_b - hy
        if fill_h > 0:
            pygame.draw.rect(screen, (r // 3, g // 3, b // 3),
                             (tx, hy, self.TW, fill_h), border_radius=6)
        pygame.draw.rect(screen, (r // 2, g // 2, b // 2),
                         (tx, self.y_top, self.TW, self.height), 2, border_radius=6)

        pygame.draw.circle(screen, (r // 5, g // 5, b // 5), (self.cx, hy), self.HR + 7)
        pygame.draw.circle(screen, self.color, (self.cx, hy), self.HR)
        pygame.draw.circle(screen, WHITE, (self.cx, hy), max(1, self.HR - 7))

        t = F_SM.render(self.title, True, self.color)
        screen.blit(t, (self.cx - t.get_width() // 2, self.y_top - 22))

        mx_t = F_XSM.render("▲ MAX", True, (r // 2, g // 2, b // 2))
        screen.blit(mx_t, (self.cx - mx_t.get_width() // 2, self.y_top - 36))

        mn_t = F_XSM.render("▼ MIN", True, (r // 2, g // 2, b // 2))
        screen.blit(mn_t, (self.cx - mn_t.get_width() // 2, y_b + 4))

        vt = F_MED.render(self.fmt.format(self.val), True, self.color)
        screen.blit(vt, (self.cx - vt.get_width() // 2, y_b + 18))

        for i, line in enumerate(self.desc):
            dt = F_XSM.render(line, True, DIM)
            screen.blit(dt, (self.cx - dt.get_width() // 2, y_b + 36 + i * 13))


# ─────────────────────────────────────────────────────────────────────────────
# Slider instances
# ─────────────────────────────────────────────────────────────────────────────
_SL_Y = MY0 + 58           # track top y
_SL_H = MAZE_H - 148       # track height

_CX_SPEED = MX0 // 2                        # 99  — centre of left panel
_CX_FOV   = MX0 + MAZE_W + (SW - MX0 - MAZE_W) // 2   # 801 — centre of right panel

speed_slider = Slider(
    cx=_CX_SPEED, y_top=_SL_Y, height=_SL_H,
    min_val=0.3, max_val=4.5, init_val=1.4,
    title="SPEED",
    value_fmt="{:.1f}",
    color=SL_SPEED_C,
    desc=("°/frame", "↑ faster spin", "↓ slower spin"),
)

fov_slider = Slider(
    cx=_CX_FOV, y_top=_SL_Y, height=_SL_H,
    min_val=25, max_val=180, init_val=100,
    title="FOV",
    value_fmt="{:.0f}°",
    color=SL_FOV_C,
    desc=("field of view", "↑ wider cone", "↓ narrower"),
)

ALL_SLIDERS = [speed_slider, fov_slider]


def get_rotate_speed() -> float:
    return speed_slider.val

def get_fov_deg() -> float:
    return fov_slider.val

# ─────────────────────────────────────────────────────────────────────────────
# Maze generation
# ─────────────────────────────────────────────────────────────────────────────
def generate_maze(rows, cols, sr, sc):
    """Recursive-backtracker spanning tree — one path between any two cells."""
    visited  = [[False] * cols for _ in range(rows)]
    passages = set()

    def carve(r, c):
        visited[r][c] = True
        order = list(range(4))
        random.shuffle(order)
        for d in order:
            dr, dc, _, _ = DIRS[d]
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and not visited[nr][nc]:
                passages.add((r, c, d))
                passages.add((nr, nc, (d + 2) % 4))
                carve(nr, nc)

    carve(sr, sc)
    return passages


def add_loops(passages, rows, cols, ratio=0.28):
    """Open a fraction of closed internal walls to create multiple paths."""
    candidates = []
    for r in range(rows):
        for c in range(cols):
            for d in (0, 1):   # East and South only — avoids double-counting
                if (r, c, d) not in passages:
                    dr, dc, _, _ = DIRS[d]
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        candidates.append((r, c, d, nr, nc))
    random.shuffle(candidates)
    n = max(3, int(len(candidates) * ratio))
    for r, c, d, nr, nc in candidates[:n]:
        passages.add((r, c, d))
        passages.add((nr, nc, (d + 2) % 4))
    return passages

# ─────────────────────────────────────────────────────────────────────────────
# Game state
# ─────────────────────────────────────────────────────────────────────────────
STATE_ROTATING   = "ROTATING"
STATE_COLLAPSING = "COLLAPSING"
STATE_MOVING     = "MOVING"

passages      = set()
char_r        = ROWS // 2
char_c        = COLS // 2
char_angle    = 0.0
visited_cells = set()

state          = STATE_ROTATING
collapse_timer = 0
COLLAPSE_FRAMES = 38

move_progress = 0.0
MOVE_FRAMES   = 28
move_target   = None
chosen_dir    = None
visible_paths = []
no_paths_flash = 0
tick           = 0


def reset():
    global passages, char_r, char_c, char_angle, visited_cells
    global state, collapse_timer, move_progress, move_target
    global chosen_dir, visible_paths, no_paths_flash
    p = generate_maze(ROWS, COLS, ROWS // 2, COLS // 2)
    passages       = add_loops(p, ROWS, COLS)
    char_r         = ROWS // 2
    char_c         = COLS // 2
    char_angle     = 0.0
    visited_cells  = {(char_r, char_c)}
    state          = STATE_ROTATING
    collapse_timer = 0
    move_progress  = 0.0
    move_target    = None
    chosen_dir     = None
    visible_paths  = []
    no_paths_flash = 0


reset()

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def cell_cx(c): return MX0 + c * CELL + CELL // 2
def cell_cy(r): return MY0 + r * CELL + CELL // 2


def angle_in_fov(dir_angle, view_angle, fov):
    diff = (dir_angle - view_angle + 180) % 360 - 180
    return abs(diff) <= fov / 2


def get_visible_paths(r, c, view_angle, fov):
    result = []
    for d, (dr, dc, ang, _) in enumerate(DIRS):
        if (r, c, d) in passages and angle_in_fov(ang, view_angle, fov):
            result.append(d)
    return result

# ─────────────────────────────────────────────────────────────────────────────
# Draw — panels
# ─────────────────────────────────────────────────────────────────────────────
def draw_panels():
    # Left panel
    pygame.draw.rect(screen, PANEL_BG, (0, MY0, MX0, MAZE_H))
    pygame.draw.line(screen, (40, 32, 72), (MX0, MY0), (MX0, MY0 + MAZE_H), 1)
    lbl = F_XSM.render("ROTATION SPEED", True, (60, 55, 90))
    screen.blit(lbl, (MX0 // 2 - lbl.get_width() // 2, MY0 + 8))

    # Right panel
    rp_x = MX0 + MAZE_W
    rp_w = SW - rp_x
    pygame.draw.rect(screen, PANEL_BG, (rp_x, MY0, rp_w, MAZE_H))
    pygame.draw.line(screen, (40, 32, 72), (rp_x, MY0), (rp_x, MY0 + MAZE_H), 1)
    lbl2 = F_XSM.render("FIELD OF VIEW", True, (60, 55, 90))
    screen.blit(lbl2, (rp_x + rp_w // 2 - lbl2.get_width() // 2, MY0 + 8))

# ─────────────────────────────────────────────────────────────────────────────
# Draw — maze
# ─────────────────────────────────────────────────────────────────────────────
def draw_maze():
    for r in range(ROWS):
        for c in range(COLS):
            x   = MX0 + c * CELL
            y   = MY0 + r * CELL
            col = FLOOR_VIS if (r, c) in visited_cells else FLOOR_C
            pygame.draw.rect(screen, col, (x, y, CELL, CELL))

    for r in range(ROWS):
        for c in range(COLS):
            x = MX0 + c * CELL
            y = MY0 + r * CELL
            if (r, c, 3) not in passages:  # North wall
                pygame.draw.line(screen, WALL_C, (x, y), (x + CELL, y), 3)
            if (r, c, 1) not in passages:  # South wall
                pygame.draw.line(screen, WALL_C, (x, y + CELL), (x + CELL, y + CELL), 3)
            if (r, c, 2) not in passages:  # West wall
                pygame.draw.line(screen, WALL_C, (x, y), (x, y + CELL), 3)
            if (r, c, 0) not in passages:  # East wall
                pygame.draw.line(screen, WALL_C, (x + CELL, y), (x + CELL, y + CELL), 3)


def draw_visited_glow():
    surf = pygame.Surface((SW, SH), pygame.SRCALPHA)
    for (r, c) in visited_cells:
        x = MX0 + c * CELL + 3
        y = MY0 + r * CELL + 3
        pygame.draw.rect(surf, (*VISITED_C, 22), (x, y, CELL - 6, CELL - 6), border_radius=4)
    screen.blit(surf, (0, 0))

# ─────────────────────────────────────────────────────────────────────────────
# Draw — FOV cone
# ─────────────────────────────────────────────────────────────────────────────
def draw_fov_cone(cx, cy, angle_deg, fov_deg, radius):
    surf    = pygame.Surface((SW, SH), pygame.SRCALPHA)
    start_a = math.radians(angle_deg - fov_deg / 2)
    end_a   = math.radians(angle_deg + fov_deg / 2)
    steps   = 28
    pts = [(cx, cy)]
    for i in range(steps + 1):
        a = start_a + (end_a - start_a) * i / steps
        pts.append((cx + math.cos(a) * radius, cy + math.sin(a) * radius))
    pygame.draw.polygon(surf, (*FOV_C, 26), pts)
    # Edge lines of the cone
    edge_a1 = math.radians(angle_deg - fov_deg / 2)
    edge_a2 = math.radians(angle_deg + fov_deg / 2)
    pygame.draw.line(surf, (*FOV_C, 70),
                     (cx, cy),
                     (cx + int(math.cos(edge_a1) * radius),
                      cy + int(math.sin(edge_a1) * radius)), 1)
    pygame.draw.line(surf, (*FOV_C, 70),
                     (cx, cy),
                     (cx + int(math.cos(edge_a2) * radius),
                      cy + int(math.sin(edge_a2) * radius)), 1)
    screen.blit(surf, (0, 0))

# ─────────────────────────────────────────────────────────────────────────────
# Draw — path preview  (dim ghost of what's beyond each visible path)
# ─────────────────────────────────────────────────────────────────────────────
def draw_path_preview(r, c, paths, t):
    """For every path in FOV, show dim ghost lines for passages beyond it."""
    pulse = 0.35 + 0.25 * math.sin(t * 0.09)
    surf  = pygame.Surface((SW, SH), pygame.SRCALPHA)
    pr, pg, pb = PREVIEW_C

    for d in paths:
        dr, dc, _, _ = DIRS[d]
        nr, nc = r + dr, c + dc
        ncx, ncy = cell_cx(nc), cell_cy(nr)

        # Subtle cell highlight for the peek-destination
        rx = MX0 + nc * CELL + 5
        ry = MY0 + nr * CELL + 5
        pygame.draw.rect(surf, (pr // 3, pg // 3, pb // 3, int(35 * pulse)),
                         (rx, ry, CELL - 10, CELL - 10), border_radius=4)
        pygame.draw.rect(surf, (pr // 2, pg // 2, pb // 2, int(55 * pulse)),
                         (rx, ry, CELL - 10, CELL - 10), 1, border_radius=4)

        # Ghost lines for every passage that continues from the neighbor
        back = (d + 2) % 4
        for nd in range(4):
            if nd == back:
                continue   # don't echo the path we came from
            if (nr, nc, nd) in passages:
                ndr, ndc, _, _ = DIRS[nd]
                nnr, nnc = nr + ndr, nc + ndc
                if 0 <= nnr < ROWS and 0 <= nnc < COLS:
                    nnx = cell_cx(nnc)
                    nny = cell_cy(nnr)
                    alpha = int(80 * pulse)
                    pygame.draw.line(surf,
                                     (pr, pg, pb, alpha),
                                     (ncx, ncy), (nnx, nny), 5)
                    pygame.draw.line(surf,
                                     (200, 255, 220, alpha // 2),
                                     (ncx, ncy), (nnx, nny), 1)

    screen.blit(surf, (0, 0))

# ─────────────────────────────────────────────────────────────────────────────
# Draw — superposition paths
# ─────────────────────────────────────────────────────────────────────────────
def draw_superposition_paths(r, c, paths, t):
    cx, cy = cell_cx(c), cell_cy(r)
    pulse  = 0.5 + 0.5 * math.sin(t * 0.13)
    surf   = pygame.Surface((SW, SH), pygame.SRCALPHA)
    sr, sg, sb = SUPER_C

    for d in paths:
        dr, dc, _, _ = DIRS[d]
        nx, ny = cell_cx(c + dc), cell_cy(r + dr)
        a_thick = int(140 * pulse)
        a_thin  = int(min(255, 200 * pulse))
        pygame.draw.line(surf, (sr // 2, sg // 2, sb // 2, a_thick // 2),
                         (cx, cy), (nx, ny), 22)
        pygame.draw.line(surf, (sr, sg, sb, a_thick),
                         (cx, cy), (nx, ny), 10)
        pygame.draw.line(surf, (255, 200, 255, a_thin),
                         (cx, cy), (nx, ny), 3)
        mx, my = (cx + nx) // 2, (cy + ny) // 2
        v   = int(180 * pulse)
        lbl = F_SM.render("?", True, (v, v // 3, v))
        surf.blit(lbl, (mx - lbl.get_width() // 2, my - lbl.get_height() // 2))

    screen.blit(surf, (0, 0))

# ─────────────────────────────────────────────────────────────────────────────
# Draw — collapse flash
# ─────────────────────────────────────────────────────────────────────────────
def draw_collapse_flash(r, c, chosen, timer):
    cx, cy   = cell_cx(c), cell_cy(r)
    dr, dc, _, _ = DIRS[chosen]
    nx, ny   = cell_cx(c + dc), cell_cy(r + dr)
    t        = timer / COLLAPSE_FRAMES
    surf     = pygame.Surface((SW, SH), pygame.SRCALPHA)
    pygame.draw.line(surf, (*COLLAPSE_C, int(255 * t)),
                     (cx, cy), (nx, ny), max(2, int(20 * t)))
    pygame.draw.line(surf, (255, 255, 255, int(200 * t)),
                     (cx, cy), (nx, ny), 3)
    mx, my = (cx + nx) // 2, (cy + ny) // 2
    lbl = F_SM.render("COLLAPSED!", True, COLLAPSE_C)
    lbl.set_alpha(int(255 * t))
    surf.blit(lbl, (mx - lbl.get_width() // 2, my - 24))
    screen.blit(surf, (0, 0))

# ─────────────────────────────────────────────────────────────────────────────
# Draw — character
# ─────────────────────────────────────────────────────────────────────────────
def draw_character(px, py, angle_deg):
    pygame.draw.circle(screen, (20, 60, 110), (px, py), 20)
    pygame.draw.circle(screen, CHAR_C, (px, py), 13)
    pygame.draw.circle(screen, BG, (px, py), 5)
    rad = math.radians(angle_deg)
    ax  = px + math.cos(rad) * 21
    ay  = py + math.sin(rad) * 21
    pygame.draw.line(screen, (255, 255, 100), (px, py), (int(ax), int(ay)), 3)
    pygame.draw.circle(screen, (255, 240, 80), (int(ax), int(ay)), 4)

# ─────────────────────────────────────────────────────────────────────────────
# Draw — HUD
# ─────────────────────────────────────────────────────────────────────────────
def draw_top(n_visible):
    pygame.draw.rect(screen, PANEL_BG, (0, 0, SW, TOP_H))
    pygame.draw.line(screen, (55, 45, 100), (0, TOP_H - 1), (SW, TOP_H - 1))

    title = F_TITLE.render("✦  QUANTUM MAZE  ✦", True, Q_PURPLE)
    screen.blit(title, (SW // 2 - title.get_width() // 2, 8))

    if state == STATE_ROTATING:
        if n_visible == 0:
            msg, col = "Rotating... no paths in view yet", DIM
        elif n_visible == 1:
            msg, col = "1 path in superposition — SPACE to collapse", SUPER_C
        else:
            msg, col = f"{n_visible} paths in superposition — SPACE to collapse", SUPER_C
    elif state == STATE_COLLAPSING:
        msg, col = "Quantum state COLLAPSING  →  one path chosen...", COLLAPSE_C
    else:
        msg, col = "Moving to new position...", (80, 200, 255)

    st = F_SM.render(msg, True, col)
    screen.blit(st, (SW // 2 - st.get_width() // 2, 52))


def draw_bottom(n_visited):
    y0 = MY0 + MAZE_H
    pygame.draw.rect(screen, PANEL_BG, (0, y0, SW, BOT_H))
    pygame.draw.line(screen, (55, 45, 100), (0, y0), (SW, y0))

    lines = [
        ("■ purple = superposition paths   ■ green ghost = preview of what's beyond   ■ SPACE = collapse",
         DIM),
        ("Quantum: a particle exists in ALL states simultaneously until it is MEASURED",
         (120, 60, 180)),
    ]
    for i, (txt, col) in enumerate(lines):
        t = F_XSM.render(txt, True, col)
        screen.blit(t, (SW // 2 - t.get_width() // 2, y0 + 11 + i * 19))

    vc = F_SM.render(f"Visited: {n_visited} / {ROWS * COLS}", True, VISITED_C)
    screen.blit(vc, (SW - vc.get_width() - 14, y0 + 10))


def draw_no_path_warning(flash):
    if flash <= 0:
        return
    alpha = int(255 * min(1.0, flash / 20))
    lbl   = F_MED.render("No paths in view — keep rotating!", True, WARN_C)
    lbl.set_alpha(alpha)
    screen.blit(lbl, (SW // 2 - lbl.get_width() // 2, MY0 + MAZE_H // 2 - 12))

# ─────────────────────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────────────────────
def main():
    global char_r, char_c, char_angle, state, collapse_timer
    global move_progress, move_target, chosen_dir, visible_paths
    global no_paths_flash, tick

    while True:
        clk.tick(FPS)
        tick += 1

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                elif event.key == pygame.K_r:
                    reset(); tick = 0
                elif event.key == pygame.K_SPACE and state == STATE_ROTATING:
                    paths = get_visible_paths(char_r, char_c,
                                              char_angle, get_fov_deg())
                    if paths:
                        chosen_dir     = random.choice(paths)
                        visible_paths  = paths
                        state          = STATE_COLLAPSING
                        collapse_timer = COLLAPSE_FRAMES
                    else:
                        no_paths_flash = 55

            for sl in ALL_SLIDERS:
                sl.handle_event(event)

        # ── Update ────────────────────────────────────────────────────────
        if state == STATE_ROTATING:
            char_angle    = (char_angle + get_rotate_speed()) % 360
            visible_paths = get_visible_paths(char_r, char_c,
                                              char_angle, get_fov_deg())
            if no_paths_flash > 0:
                no_paths_flash -= 1

        elif state == STATE_COLLAPSING:
            collapse_timer -= 1
            if collapse_timer <= 0:
                dr, dc, _, _ = DIRS[chosen_dir]
                move_target   = (char_r + dr, char_c + dc)
                move_progress = 0.0
                state         = STATE_MOVING

        elif state == STATE_MOVING:
            move_progress += 1.0 / MOVE_FRAMES
            if move_progress >= 1.0:
                char_r, char_c = move_target
                visited_cells.add((char_r, char_c))
                move_target    = None
                move_progress  = 0.0
                state          = STATE_ROTATING
                visible_paths  = []

        # ── Render ────────────────────────────────────────────────────────
        screen.fill(BG)
        draw_panels()
        draw_visited_glow()
        draw_maze()

        # Interpolated character position while moving
        px = cell_cx(char_c)
        py = cell_cy(char_r)
        if state == STATE_MOVING and move_target:
            tr, tc = move_target
            tx, ty = cell_cx(tc), cell_cy(tr)
            te     = move_progress ** 2 * (3 - 2 * move_progress)  # ease-in-out
            px     = int(px + (tx - px) * te)
            py     = int(py + (ty - py) * te)

        # FOV cone (anchored to current cell grid position)
        draw_fov_cone(cell_cx(char_c), cell_cy(char_r),
                      char_angle, get_fov_deg(), FOV_RADIUS)

        # Path preview (ghost of what's beyond each visible path)
        if state == STATE_ROTATING and visible_paths:
            draw_path_preview(char_r, char_c, visible_paths, tick)

        # Superposition paths or collapse flash
        if state == STATE_ROTATING and visible_paths:
            draw_superposition_paths(char_r, char_c, visible_paths, tick)
        elif state == STATE_COLLAPSING and chosen_dir is not None:
            draw_collapse_flash(char_r, char_c, chosen_dir, collapse_timer)

        draw_character(px, py, char_angle)

        # Sliders on top of side panels
        for sl in ALL_SLIDERS:
            sl.draw()

        draw_no_path_warning(no_paths_flash)
        draw_top(len(visible_paths) if state == STATE_ROTATING else 0)
        draw_bottom(len(visited_cells))
        pygame.display.flip()


if __name__ == "__main__":
    main()