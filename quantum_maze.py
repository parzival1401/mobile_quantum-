"""
quantum_maze.py  —  Quantum Maze
==================================
Quantum Exhibition  |  Superposition Demo

Architecture
------------
The maze is stored as an adjacency matrix  adj[r][c] = set of open direction
indices.  This is built once at generation time so every per-cell lookup is O(1)
— no searching through a passages set each frame.

The maze surface is pre-rendered to a pygame.Surface and blitted each frame
(~1 draw call instead of 1700+).  The visited-cell overlay is only rebuilt
when the character reaches a new cell.

Quantum mechanics
-----------------
  • Character rotates, sweeping a FOV cone.
  • Every open path inside the cone is in SUPERPOSITION (glowing purple).
  • Dim green ghost lines show what lies beyond each visible path (preview).
  • SPACE collapses: one path is chosen at random; character moves there.

Sliders
-------
  SPEED (left panel)  —  rotation speed  0.3 – 4.5 °/frame
  FOV   (right panel) —  cone width      25° – 180°

Controls
--------
  SPACE  —  collapse & move
  R      —  new maze
  ESC    —  quit
"""

import pygame
import sys
import random
import math

pygame.init()

# ─────────────────────────────────────────────────────────────────────────────
# Screen
# ─────────────────────────────────────────────────────────────────────────────
SW, SH = 960, 760
FPS    = 60
screen = pygame.display.set_mode((SW, SH))
pygame.display.set_caption("Quantum Maze  |  Quantum Exhibition")
clk    = pygame.time.Clock()

# ─────────────────────────────────────────────────────────────────────────────
# Colours
# ─────────────────────────────────────────────────────────────────────────────
BG         = (8,   6,  20)
WALL_C     = (55,  75, 145)
FLOOR_C    = (13,  11,  30)
FLOOR_VIS  = (20,  24,  55)
FOV_C      = (255, 220,  60)
SUPER_C    = (160,  60, 255)
PREVIEW_C  = ( 55, 195, 130)
CHAR_C     = ( 80, 220, 255)
COLLAPSE_C = (255, 200,  50)
VISITED_C  = ( 30, 155,  85)
Q_PURPLE   = (210,  70, 255)
DIM        = ( 70,  65, 110)
WHITE      = (240, 240, 255)
PANEL_BG   = (10,   8,  26)
WARN_C     = (255, 100,  60)
SL_SPEED_C = (255, 140,  50)
SL_FOV_C   = (255, 220,  60)

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
COLS   = 21        # maze columns  — 21 × 21 gives a dense complex maze
ROWS   = 21
CELL   = 28        # pixels per cell

MAZE_W = COLS * CELL    # 588
MAZE_H = ROWS * CELL    # 588
TOP_H  = 80
BOT_H  = 80
MX0    = (SW - MAZE_W) // 2    # 186 — maze left edge  (also = left panel width)
MY0    = TOP_H                 # maze top edge

# Direction table  (row_delta, col_delta, angle_deg, label)
# Angle: E=0°  S=90°  W=180°  N=270°   (pygame y-down convention)
DIRS = [
    ( 0,  1,   0, "E"),   # 0
    ( 1,  0,  90, "S"),   # 1
    ( 0, -1, 180, "W"),   # 2
    (-1,  0, 270, "N"),   # 3
]

FOV_RADIUS = int(CELL * 2.2)   # visual length of drawn FOV cone

# ─────────────────────────────────────────────────────────────────────────────
# Vertical Slider
# ─────────────────────────────────────────────────────────────────────────────
class Slider:
    TW = 12
    HR = 13

    def __init__(self, cx, y_top, height, min_val, max_val, init_val,
                 title, value_fmt, color, desc=()):
        self.cx, self.y_top, self.height = cx, y_top, height
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
        return self.min_val + (1.0 - rel / self.height) * (self.max_val - self.min_val)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            hy = self._hy()
            if pygame.Rect(self.cx - self.HR - 5, hy - self.HR - 5,
                           (self.HR + 5) * 2, (self.HR + 5) * 2).collidepoint(event.pos):
                self.dragging = True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.val = max(self.min_val, min(self.max_val, self._y_to_val(event.pos[1])))

    def draw(self):
        r, g, b = self.color
        hy  = self._hy()
        tx  = self.cx - self.TW // 2
        y_b = self.y_top + self.height

        pygame.draw.rect(screen, (22, 18, 42), (tx, self.y_top, self.TW, self.height), border_radius=6)
        fill_h = y_b - hy
        if fill_h > 0:
            pygame.draw.rect(screen, (r // 3, g // 3, b // 3), (tx, hy, self.TW, fill_h), border_radius=6)
        pygame.draw.rect(screen, (r // 2, g // 2, b // 2), (tx, self.y_top, self.TW, self.height), 2, border_radius=6)
        pygame.draw.circle(screen, (r // 5, g // 5, b // 5), (self.cx, hy), self.HR + 7)
        pygame.draw.circle(screen, self.color, (self.cx, hy), self.HR)
        pygame.draw.circle(screen, WHITE, (self.cx, hy), max(1, self.HR - 7))

        screen.blit(F_SM.render(self.title, True, self.color),
                    (self.cx - F_SM.size(self.title)[0] // 2, self.y_top - 22))
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
_SL_Y  = MY0 + 58
_SL_H  = MAZE_H - 148
_CX_SP = MX0 // 2                               # 93  — left panel centre
_CX_FV = MX0 + MAZE_W + (SW - MX0 - MAZE_W) // 2  # 867 — right panel centre

speed_slider = Slider(_CX_SP, _SL_Y, _SL_H, 0.3, 4.5, 1.4,
                      "SPEED", "{:.1f}", SL_SPEED_C,
                      ("°/frame", "↑ faster", "↓ slower"))
fov_slider   = Slider(_CX_FV, _SL_Y, _SL_H, 25,  180, 100,
                      "FOV",   "{:.0f}°", SL_FOV_C,
                      ("field of view", "↑ wider", "↓ narrower"))
ALL_SLIDERS  = [speed_slider, fov_slider]

def get_rotate_speed(): return speed_slider.val
def get_fov_deg():      return fov_slider.val

# ─────────────────────────────────────────────────────────────────────────────
# Maze generation — iterative backtracker → adjacency matrix
# ─────────────────────────────────────────────────────────────────────────────
def generate_adj(rows, cols, sr, sc):
    """
    Iterative recursive-backtracker.
    Returns adj[r][c] = set of open direction indices.
    Using a stack avoids Python recursion-limit issues on large grids.
    """
    visited = [[False] * cols for _ in range(rows)]
    adj     = [[set() for _ in range(cols)] for _ in range(rows)]

    stack = [(sr, sc)]
    visited[sr][sc] = True

    while stack:
        r, c = stack[-1]
        # Collect unvisited neighbours in random order
        nbrs = []
        for d in range(4):
            dr, dc, _, _ = DIRS[d]
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and not visited[nr][nc]:
                nbrs.append((d, nr, nc))
        if nbrs:
            d, nr, nc = random.choice(nbrs)
            adj[r][c].add(d)
            adj[nr][nc].add((d + 2) % 4)
            visited[nr][nc] = True
            stack.append((nr, nc))
        else:
            stack.pop()

    return adj


def add_loops(adj, rows, cols, ratio=0.12):
    """Open a fraction of closed internal walls to create alternative routes."""
    candidates = []
    for r in range(rows):
        for c in range(cols):
            for d in (0, 1):          # E and S only — avoids double-counting
                if d not in adj[r][c]:
                    dr, dc, _, _ = DIRS[d]
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        candidates.append((r, c, d, nr, nc))
    random.shuffle(candidates)
    for r, c, d, nr, nc in candidates[:max(3, int(len(candidates) * ratio))]:
        adj[r][c].add(d)
        adj[nr][nc].add((d + 2) % 4)
    return adj

# ─────────────────────────────────────────────────────────────────────────────
# Pre-rendered surfaces
# ─────────────────────────────────────────────────────────────────────────────
def build_maze_surface(adj, rows, cols, cell):
    """
    Render all walls into a Surface once.
    Strategy: draw N and W walls for every cell, then the outer S and E borders.
    Each shared internal wall is drawn exactly once.
    """
    surf = pygame.Surface((MAZE_W, MAZE_H))
    surf.fill(FLOOR_C)

    for r in range(rows):
        for c in range(cols):
            ox = c * cell
            oy = r * cell
            # North wall (top edge of this cell)
            if 3 not in adj[r][c]:
                pygame.draw.line(surf, WALL_C, (ox, oy), (ox + cell, oy), 2)
            # West wall (left edge of this cell)
            if 2 not in adj[r][c]:
                pygame.draw.line(surf, WALL_C, (ox, oy), (ox, oy + cell), 2)

    # Bottom border
    for c in range(cols):
        ox = c * cell
        oy = rows * cell
        if 1 not in adj[rows - 1][c]:
            pygame.draw.line(surf, WALL_C, (ox, oy), (ox + cell, oy), 2)

    # Right border
    for r in range(rows):
        ox = cols * cell
        oy = r * cell
        if 0 not in adj[r][cols - 1]:
            pygame.draw.line(surf, WALL_C, (ox, oy), (ox, oy + cell), 2)

    return surf


def build_visited_surface(visited_cells):
    """Rebuild the visited-cell overlay. Called only when the set changes."""
    surf = pygame.Surface((MAZE_W, MAZE_H), pygame.SRCALPHA)
    for (r, c) in visited_cells:
        ox = c * CELL + 3
        oy = r * CELL + 3
        pygame.draw.rect(surf, (*VISITED_C, 26), (ox, oy, CELL - 6, CELL - 6), border_radius=3)
    return surf

# ─────────────────────────────────────────────────────────────────────────────
# Game state
# ─────────────────────────────────────────────────────────────────────────────
STATE_ROTATING   = "ROTATING"
STATE_COLLAPSING = "COLLAPSING"
STATE_MOVING     = "MOVING"

adj            = [[set()]]   # replaced in reset()
maze_surf      = None
visited_surf   = None

char_r         = ROWS // 2
char_c         = COLS // 2
char_angle     = 0.0
visited_cells  = set()

state          = STATE_ROTATING
collapse_timer = 0
COLLAPSE_FRAMES = 35

move_progress  = 0.0
MOVE_FRAMES    = 24
move_target    = None
chosen_dir     = None
visible_paths  = []
no_paths_flash = 0
tick           = 0


def reset():
    global adj, maze_surf, visited_surf
    global char_r, char_c, char_angle, visited_cells
    global state, collapse_timer, move_progress, move_target
    global chosen_dir, visible_paths, no_paths_flash

    a = generate_adj(ROWS, COLS, ROWS // 2, COLS // 2)
    adj = add_loops(a, ROWS, COLS)

    maze_surf  = build_maze_surface(adj, ROWS, COLS, CELL)

    char_r, char_c = ROWS // 2, COLS // 2
    char_angle     = 0.0
    visited_cells  = {(char_r, char_c)}
    visited_surf   = build_visited_surface(visited_cells)

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
    """O(4) lookup: iterate adj[r][c] only (max 4 directions)."""
    return [d for d in adj[r][c] if angle_in_fov(DIRS[d][2], view_angle, fov)]

# ─────────────────────────────────────────────────────────────────────────────
# Draw — panels
# ─────────────────────────────────────────────────────────────────────────────
def draw_panels():
    pygame.draw.rect(screen, PANEL_BG, (0, MY0, MX0, MAZE_H))
    pygame.draw.line(screen, (40, 32, 72), (MX0, MY0), (MX0, MY0 + MAZE_H), 1)
    t = F_XSM.render("ROTATION SPEED", True, (60, 55, 90))
    screen.blit(t, (MX0 // 2 - t.get_width() // 2, MY0 + 8))

    rp_x = MX0 + MAZE_W
    rp_w = SW - rp_x
    pygame.draw.rect(screen, PANEL_BG, (rp_x, MY0, rp_w, MAZE_H))
    pygame.draw.line(screen, (40, 32, 72), (rp_x, MY0), (rp_x, MY0 + MAZE_H), 1)
    t2 = F_XSM.render("FIELD OF VIEW", True, (60, 55, 90))
    screen.blit(t2, (rp_x + rp_w // 2 - t2.get_width() // 2, MY0 + 8))

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
    pygame.draw.polygon(surf, (*FOV_C, 24), pts)
    for edge in (start_a, end_a):
        pygame.draw.line(surf, (*FOV_C, 65),
                         (cx, cy),
                         (cx + int(math.cos(edge) * radius),
                          cy + int(math.sin(edge) * radius)), 1)
    screen.blit(surf, (0, 0))

# ─────────────────────────────────────────────────────────────────────────────
# Draw — path preview (dim ghost of onward passages beyond each visible path)
# ─────────────────────────────────────────────────────────────────────────────
def draw_path_preview(r, c, paths, t):
    pulse = 0.35 + 0.25 * math.sin(t * 0.09)
    surf  = pygame.Surface((SW, SH), pygame.SRCALPHA)
    pr, pg, pb = PREVIEW_C

    for d in paths:
        dr, dc, _, _ = DIRS[d]
        nr, nc = r + dr, c + dc
        ncx, ncy = cell_cx(nc), cell_cy(nr)

        # Subtle cell frame at the destination
        rx = MX0 + nc * CELL + 4
        ry = MY0 + nr * CELL + 4
        pygame.draw.rect(surf, (pr // 3, pg // 3, pb // 3, int(32 * pulse)),
                         (rx, ry, CELL - 8, CELL - 8), border_radius=3)
        pygame.draw.rect(surf, (pr // 2, pg // 2, pb // 2, int(50 * pulse)),
                         (rx, ry, CELL - 8, CELL - 8), 1, border_radius=3)

        # Ghost lines for every open passage from the neighbour (except way back)
        back = (d + 2) % 4
        for nd in adj[nr][nc]:
            if nd == back:
                continue
            ndr, ndc, _, _ = DIRS[nd]
            nnr, nnc = nr + ndr, nc + ndc
            if 0 <= nnr < ROWS and 0 <= nnc < COLS:
                alpha = int(75 * pulse)
                pygame.draw.line(surf, (pr, pg, pb, alpha),
                                 (ncx, ncy), (cell_cx(nnc), cell_cy(nnr)), 4)
                pygame.draw.line(surf, (200, 255, 220, alpha // 2),
                                 (ncx, ncy), (cell_cx(nnc), cell_cy(nnr)), 1)

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
        at = int(140 * pulse)
        # Outer glow
        pygame.draw.line(surf, (sr // 2, sg // 2, sb // 2, at // 2),
                         (cx, cy), (nx, ny), 20)
        # Bright core
        pygame.draw.line(surf, (sr, sg, sb, at), (cx, cy), (nx, ny), 8)
        pygame.draw.line(surf, (255, 200, 255, int(min(255, 200 * pulse))),
                         (cx, cy), (nx, ny), 2)
        # "?" at midpoint
        mx_, my_ = (cx + nx) // 2, (cy + ny) // 2
        v   = int(180 * pulse)
        lbl = F_SM.render("?", True, (v, v // 3, v))
        surf.blit(lbl, (mx_ - lbl.get_width() // 2, my_ - lbl.get_height() // 2))

    screen.blit(surf, (0, 0))

# ─────────────────────────────────────────────────────────────────────────────
# Draw — collapse flash
# ─────────────────────────────────────────────────────────────────────────────
def draw_collapse_flash(r, c, chosen, timer):
    cx, cy       = cell_cx(c), cell_cy(r)
    dr, dc, _, _ = DIRS[chosen]
    nx, ny       = cell_cx(c + dc), cell_cy(r + dr)
    t            = timer / COLLAPSE_FRAMES
    surf         = pygame.Surface((SW, SH), pygame.SRCALPHA)
    pygame.draw.line(surf, (*COLLAPSE_C, int(255 * t)),
                     (cx, cy), (nx, ny), max(2, int(18 * t)))
    pygame.draw.line(surf, (255, 255, 255, int(190 * t)),
                     (cx, cy), (nx, ny), 2)
    mx_, my_ = (cx + nx) // 2, (cy + ny) // 2
    lbl = F_SM.render("COLLAPSED!", True, COLLAPSE_C)
    lbl.set_alpha(int(255 * t))
    surf.blit(lbl, (mx_ - lbl.get_width() // 2, my_ - 22))
    screen.blit(surf, (0, 0))

# ─────────────────────────────────────────────────────────────────────────────
# Draw — character
# ─────────────────────────────────────────────────────────────────────────────
def draw_character(px, py, angle_deg):
    pygame.draw.circle(screen, (18, 55, 105), (px, py), 18)
    pygame.draw.circle(screen, CHAR_C, (px, py), 11)
    pygame.draw.circle(screen, BG, (px, py), 4)
    rad = math.radians(angle_deg)
    ax  = px + math.cos(rad) * 18
    ay  = py + math.sin(rad) * 18
    pygame.draw.line(screen, (255, 255, 100), (px, py), (int(ax), int(ay)), 2)
    pygame.draw.circle(screen, (255, 240, 80), (int(ax), int(ay)), 3)

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
            msg, col = "Rotating — no paths in view yet", DIM
        elif n_visible == 1:
            msg, col = "1 path visible in superposition — SPACE to collapse", SUPER_C
        else:
            msg, col = f"{n_visible} paths visible in superposition — SPACE to collapse", SUPER_C
    elif state == STATE_COLLAPSING:
        msg, col = "Collapsing quantum state  →  one path chosen...", COLLAPSE_C
    else:
        msg, col = "Moving to next junction...", (80, 200, 255)

    screen.blit(F_SM.render(msg, True, col),
                (SW // 2 - F_SM.size(msg)[0] // 2, 52))


def draw_bottom(n_visited):
    y0 = MY0 + MAZE_H
    pygame.draw.rect(screen, PANEL_BG, (0, y0, SW, BOT_H))
    pygame.draw.line(screen, (55, 45, 100), (0, y0), (SW, y0))
    lines = [
        ("■ purple = superposition paths   ■ green ghost = preview beyond   ■ SPACE = collapse   ■ R = new maze", DIM),
        ("Quantum: a particle exists in ALL states at once — it only picks one when MEASURED", (110, 55, 170)),
    ]
    for i, (txt, col) in enumerate(lines):
        t = F_XSM.render(txt, True, col)
        screen.blit(t, (SW // 2 - t.get_width() // 2, y0 + 11 + i * 19))
    vc = F_SM.render(f"Visited: {n_visited}/{ROWS * COLS}", True, VISITED_C)
    screen.blit(vc, (SW - vc.get_width() - 14, y0 + 10))


def draw_no_path_warning(flash):
    if flash <= 0:
        return
    lbl = F_MED.render("No paths in view — keep rotating!", True, WARN_C)
    lbl.set_alpha(int(255 * min(1.0, flash / 20)))
    screen.blit(lbl, (SW // 2 - lbl.get_width() // 2, MY0 + MAZE_H // 2 - 10))

# ─────────────────────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────────────────────
def main():
    global char_r, char_c, char_angle, state, collapse_timer
    global move_progress, move_target, chosen_dir, visible_paths
    global no_paths_flash, tick, visited_cells, visited_surf

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
                    paths = get_visible_paths(char_r, char_c, char_angle, get_fov_deg())
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
            visible_paths = get_visible_paths(char_r, char_c, char_angle, get_fov_deg())
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
                if (char_r, char_c) not in visited_cells:
                    visited_cells.add((char_r, char_c))
                    visited_surf = build_visited_surface(visited_cells)   # rebuild only on change
                move_target    = None
                move_progress  = 0.0
                state          = STATE_ROTATING
                visible_paths  = []

        # ── Render ────────────────────────────────────────────────────────
        screen.fill(BG)
        draw_panels()

        # Pre-rendered maze + visited overlay (single blit each)
        screen.blit(maze_surf,    (MX0, MY0))
        screen.blit(visited_surf, (MX0, MY0))

        # Interpolated character position while moving
        px = cell_cx(char_c)
        py = cell_cy(char_r)
        if state == STATE_MOVING and move_target:
            tr, tc = move_target
            te = move_progress ** 2 * (3 - 2 * move_progress)   # ease-in-out
            px = int(px + (cell_cx(tc) - px) * te)
            py = int(py + (cell_cy(tr) - py) * te)

        draw_fov_cone(cell_cx(char_c), cell_cy(char_r),
                      char_angle, get_fov_deg(), FOV_RADIUS)

        if state == STATE_ROTATING and visible_paths:
            draw_path_preview(char_r, char_c, visible_paths, tick)
            draw_superposition_paths(char_r, char_c, visible_paths, tick)
        elif state == STATE_COLLAPSING and chosen_dir is not None:
            draw_collapse_flash(char_r, char_c, chosen_dir, collapse_timer)

        draw_character(px, py, char_angle)

        for sl in ALL_SLIDERS:
            sl.draw()

        draw_no_path_warning(no_paths_flash)
        draw_top(len(visible_paths) if state == STATE_ROTATING else 0)
        draw_bottom(len(visited_cells))
        pygame.display.flip()


if __name__ == "__main__":
    main()