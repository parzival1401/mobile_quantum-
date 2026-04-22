"""
quantum_maze.py  —  Quantum Maze
==================================
Quantum Exhibition  |  Superposition Demo

The character stands at a junction and ROTATES, sweeping its field of view.
Every open path that falls inside the FOV is in SUPERPOSITION — all possible
routes exist simultaneously, shown as glowing purple corridors.

Press SPACE to COLLAPSE the superposition:
  • Only paths currently visible in the FOV are candidates.
  • One path is chosen at random (weighted by nothing — pure chance).
  • The character moves to the next junction and the process repeats.

This mirrors how a quantum particle exists in multiple states
simultaneously until it is MEASURED — at which point it picks one.

Controls
--------
  SPACE  —  collapse the superposition and move
  R      —  generate a new maze and reset
  ESC    —  quit

Hardware note
-------------
  Any device that sends SPACE keystrokes (button via Arduino HID)
  can trigger collapse, making this exhibit touchable.
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
FOV_C      = (255, 220,  60)   # gold FOV cone tint
SUPER_C    = (160,  60, 255)   # superposition path (purple)
CHAR_C     = ( 80, 220, 255)   # character body (cyan)
COLLAPSE_C = (255, 200,  50)   # collapse flash (gold)
VISITED_C  = ( 30, 160,  90)   # visited trail (green)
Q_PURPLE   = (210,  70, 255)
DIM        = ( 75,  70, 115)
WHITE      = (240, 240, 255)
PANEL_BG   = (10,   8,  26)
WARN_C     = (255, 100,  60)

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
# Maze layout
# ─────────────────────────────────────────────────────────────────────────────
COLS   = 9
ROWS   = 9
CELL   = 56           # pixels per cell
TOP_H  = 82
BOT_H  = 86

MAZE_W = COLS * CELL
MAZE_H = ROWS * CELL
MX0    = (SW - MAZE_W) // 2    # maze left edge
MY0    = TOP_H                 # maze top edge

# Direction table: index → (row_delta, col_delta, angle_deg, label)
# Angles follow pygame coords: E=0°, S=90°, W=180°, N=270°
DIRS = [
    ( 0,  1,   0, "E"),   # 0 East
    ( 1,  0,  90, "S"),   # 1 South
    ( 0, -1, 180, "W"),   # 2 West
    (-1,  0, 270, "N"),   # 3 North
]

# ─────────────────────────────────────────────────────────────────────────────
# FOV parameters
# ─────────────────────────────────────────────────────────────────────────────
ROTATE_SPEED = 1.4     # degrees per frame (viewer rotation)
FOV_DEG      = 100.0   # cone width in degrees
FOV_RADIUS   = int(CELL * 1.9)   # visual radius of drawn cone

# ─────────────────────────────────────────────────────────────────────────────
# Maze generation — recursive backtracker
# ─────────────────────────────────────────────────────────────────────────────
def generate_maze(rows, cols, sr, sc):
    """Return a set of (r, c, dir_idx) open-passage tuples."""
    visited = [[False] * cols for _ in range(rows)]
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
                passages.add((nr, nc, (d + 2) % 4))  # opposite direction
                carve(nr, nc)

    carve(sr, sc)
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
char_angle    = 0.0     # current view direction in degrees
visited_cells = set()

state          = STATE_ROTATING
collapse_timer = 0
COLLAPSE_FRAMES = 38

move_progress  = 0.0
MOVE_FRAMES    = 28
move_target    = None   # (tr, tc)
chosen_dir     = None
visible_paths  = []     # direction indices in FOV right now
no_paths_flash = 0      # frames to show "no paths visible" warning


def reset():
    global passages, char_r, char_c, char_angle, visited_cells
    global state, collapse_timer, move_progress, move_target
    global chosen_dir, visible_paths, no_paths_flash
    passages       = generate_maze(ROWS, COLS, ROWS // 2, COLS // 2)
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
tick = 0

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def cell_cx(c):  return MX0 + c * CELL + CELL // 2
def cell_cy(r):  return MY0 + r * CELL + CELL // 2


def angle_in_fov(dir_angle, view_angle, fov):
    """True if dir_angle lies within ±fov/2 of view_angle."""
    diff = (dir_angle - view_angle + 180) % 360 - 180
    return abs(diff) <= fov / 2


def get_visible_paths(r, c, view_angle, fov):
    """Return list of direction indices that are open AND inside the FOV."""
    result = []
    for d, (dr, dc, ang, _) in enumerate(DIRS):
        if (r, c, d) in passages and angle_in_fov(ang, view_angle, fov):
            result.append(d)
    return result

# ─────────────────────────────────────────────────────────────────────────────
# Drawing helpers
# ─────────────────────────────────────────────────────────────────────────────
def draw_maze():
    for r in range(ROWS):
        for c in range(COLS):
            x = MX0 + c * CELL
            y = MY0 + r * CELL
            col = FLOOR_VIS if (r, c) in visited_cells else FLOOR_C
            pygame.draw.rect(screen, col, (x, y, CELL, CELL))

    for r in range(ROWS):
        for c in range(COLS):
            x = MX0 + c * CELL
            y = MY0 + r * CELL
            # Draw a wall on every edge that has no passage
            if (r, c, 3) not in passages:  # North
                pygame.draw.line(screen, WALL_C, (x, y), (x + CELL, y), 3)
            if (r, c, 1) not in passages:  # South
                pygame.draw.line(screen, WALL_C, (x, y + CELL), (x + CELL, y + CELL), 3)
            if (r, c, 2) not in passages:  # West
                pygame.draw.line(screen, WALL_C, (x, y), (x, y + CELL), 3)
            if (r, c, 0) not in passages:  # East
                pygame.draw.line(screen, WALL_C, (x + CELL, y), (x + CELL, y + CELL), 3)


def draw_visited_glow():
    surf = pygame.Surface((SW, SH), pygame.SRCALPHA)
    for (r, c) in visited_cells:
        x = MX0 + c * CELL + 3
        y = MY0 + r * CELL + 3
        pygame.draw.rect(surf, (*VISITED_C, 22), (x, y, CELL - 6, CELL - 6), border_radius=4)
    screen.blit(surf, (0, 0))


def draw_fov_cone(cx, cy, angle_deg, fov_deg, radius):
    surf = pygame.Surface((SW, SH), pygame.SRCALPHA)
    start_a = math.radians(angle_deg - fov_deg / 2)
    end_a   = math.radians(angle_deg + fov_deg / 2)
    steps = 24
    pts = [(cx, cy)]
    for i in range(steps + 1):
        a = start_a + (end_a - start_a) * i / steps
        pts.append((cx + math.cos(a) * radius,
                    cy + math.sin(a) * radius))
    pygame.draw.polygon(surf, (*FOV_C, 28), pts)
    # Cone outline
    pygame.draw.arc(surf, (*FOV_C, 80),
                    (cx - radius, cy - radius, radius * 2, radius * 2),
                    -math.radians(angle_deg + fov_deg / 2),
                    -math.radians(angle_deg - fov_deg / 2), 1)
    screen.blit(surf, (0, 0))


def draw_superposition_paths(r, c, paths, t):
    cx, cy = cell_cx(c), cell_cy(r)
    pulse  = 0.5 + 0.5 * math.sin(t * 0.13)
    surf   = pygame.Surface((SW, SH), pygame.SRCALPHA)
    sr, sg, sb = SUPER_C
    for d in paths:
        dr, dc, _, _ = DIRS[d]
        nx, ny = cell_cx(c + dc), cell_cy(r + dr)
        alpha_thick = int(140 * pulse)
        alpha_thin  = int(min(255, 200 * pulse))
        # Glow halo
        pygame.draw.line(surf, (sr // 2, sg // 2, sb // 2, alpha_thick // 2),
                         (cx, cy), (nx, ny), 22)
        # Bright centre line
        pygame.draw.line(surf, (sr, sg, sb, alpha_thick),
                         (cx, cy), (nx, ny), 10)
        pygame.draw.line(surf, (255, 200, 255, alpha_thin),
                         (cx, cy), (nx, ny), 3)
        # "?" marker at midpoint
        mx, my = (cx + nx) // 2, (cy + ny) // 2
        v = int(180 * pulse)
        lbl = F_SM.render("?", True, (v, v // 3, v))
        surf.blit(lbl, (mx - lbl.get_width() // 2, my - lbl.get_height() // 2))
    screen.blit(surf, (0, 0))


def draw_collapse_flash(r, c, chosen, timer):
    cx, cy = cell_cx(c), cell_cy(r)
    dr, dc, _, _ = DIRS[chosen]
    nx, ny = cell_cx(c + dc), cell_cy(r + dr)
    t    = timer / COLLAPSE_FRAMES
    surf = pygame.Surface((SW, SH), pygame.SRCALPHA)
    pygame.draw.line(surf, (*COLLAPSE_C, int(255 * t)), (cx, cy), (nx, ny),
                     max(2, int(20 * t)))
    pygame.draw.line(surf, (255, 255, 255, int(200 * t)), (cx, cy), (nx, ny), 3)
    # "COLLAPSED!" label
    mx, my = (cx + nx) // 2, (cy + ny) // 2
    lbl = F_SM.render("COLLAPSED!", True, COLLAPSE_C)
    lbl.set_alpha(int(255 * t))
    surf.blit(lbl, (mx - lbl.get_width() // 2, my - 24))
    screen.blit(surf, (0, 0))


def draw_character(px, py, angle_deg):
    # Outer glow
    pygame.draw.circle(screen, (20, 60, 110), (px, py), 20)
    # Body
    pygame.draw.circle(screen, CHAR_C, (px, py), 13)
    pygame.draw.circle(screen, BG, (px, py), 5)
    # Direction arrow
    rad = math.radians(angle_deg)
    ax  = px + math.cos(rad) * 21
    ay  = py + math.sin(rad) * 21
    pygame.draw.line(screen, (255, 255, 100), (px, py), (int(ax), int(ay)), 3)
    pygame.draw.circle(screen, (255, 240, 80), (int(ax), int(ay)), 4)


def draw_top(n_visible):
    pygame.draw.rect(screen, PANEL_BG, (0, 0, SW, TOP_H))
    pygame.draw.line(screen, (55, 45, 100), (0, TOP_H - 1), (SW, TOP_H - 1))

    title = F_TITLE.render("✦  QUANTUM MAZE  ✦", True, Q_PURPLE)
    screen.blit(title, (SW // 2 - title.get_width() // 2, 8))

    if state == STATE_ROTATING:
        if n_visible == 0:
            msg = "Rotating... no paths in view yet — keep watching"
            col = DIM
        elif n_visible == 1:
            msg = f"1 path in superposition visible — SPACE to collapse"
            col = SUPER_C
        else:
            msg = f"{n_visible} paths in superposition — SPACE to collapse one"
            col = SUPER_C
    elif state == STATE_COLLAPSING:
        msg = "Quantum state COLLAPSING  →  one path chosen..."
        col = COLLAPSE_C
    else:
        msg = "Moving to new position..."
        col = (80, 200, 255)

    st = F_SM.render(msg, True, col)
    screen.blit(st, (SW // 2 - st.get_width() // 2, 52))


def draw_bottom(n_visited):
    y0 = MY0 + MAZE_H
    pygame.draw.rect(screen, PANEL_BG, (0, y0, SW, BOT_H))
    pygame.draw.line(screen, (55, 45, 100), (0, y0), (SW, y0))

    lines = [
        ("FOV sweeps all paths at once (superposition)  —  SPACE collapses to one  —  R = new maze  —  ESC = quit",
         DIM),
        ("Quantum: a particle exists in ALL states simultaneously until measured — just like these paths",
         (120, 60, 180)),
    ]
    for i, (txt, col) in enumerate(lines):
        t = F_XSM.render(txt, True, col)
        screen.blit(t, (SW // 2 - t.get_width() // 2, y0 + 12 + i * 19))

    vc = F_SM.render(f"Cells visited: {n_visited}", True, VISITED_C)
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
                    reset()
                    tick = 0

                elif event.key == pygame.K_SPACE and state == STATE_ROTATING:
                    paths = get_visible_paths(char_r, char_c, char_angle, FOV_DEG)
                    if paths:
                        chosen_dir     = random.choice(paths)
                        visible_paths  = paths
                        state          = STATE_COLLAPSING
                        collapse_timer = COLLAPSE_FRAMES
                    else:
                        no_paths_flash = 55  # show warning

        # ── Update ────────────────────────────────────────────────────────
        if state == STATE_ROTATING:
            char_angle    = (char_angle + ROTATE_SPEED) % 360
            visible_paths = get_visible_paths(char_r, char_c, char_angle, FOV_DEG)
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
        draw_visited_glow()
        draw_maze()

        # Compute character screen position (interpolate while moving)
        px = cell_cx(char_c)
        py = cell_cy(char_r)
        if state == STATE_MOVING and move_target:
            tr, tc = move_target
            tx, ty = cell_cx(tc), cell_cy(tr)
            t      = move_progress
            # Ease-in-out
            t_ease = t * t * (3 - 2 * t)
            px = int(px + (tx - px) * t_ease)
            py = int(py + (ty - py) * t_ease)

        # FOV cone (always shown at character's current cell, even while moving)
        draw_fov_cone(cell_cx(char_c), cell_cy(char_r),
                      char_angle, FOV_DEG, FOV_RADIUS)

        # Superposition paths or collapse flash
        if state == STATE_ROTATING and visible_paths:
            draw_superposition_paths(char_r, char_c, visible_paths, tick)
        elif state == STATE_COLLAPSING and chosen_dir is not None:
            draw_collapse_flash(char_r, char_c, chosen_dir, collapse_timer)

        # Character
        draw_character(px, py, char_angle)

        draw_no_path_warning(no_paths_flash)
        draw_top(len(visible_paths) if state == STATE_ROTATING else 0)
        draw_bottom(len(visited_cells))
        pygame.display.flip()


if __name__ == "__main__":
    main()
