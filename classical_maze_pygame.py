"""
classical_maze_pygame.py  —  Classical Computer: The Maze Runner
=================================================================
Quantum Exhibition  |  Classical vs Quantum Computing

ZONE 1  (top 1/4 )  : 8-bit switch panel  — one bit flips & glows red per move
ZONE 2  (bottom 3/4): Clock panel (left) + Circuit-board maze (right)

Clock rule: the player can ONLY move during the TICK (GO!) phase of the clock.
            Trying to move during TOCK (WAIT) shows a warning and blocks the move.
            This mirrors how a real CPU can only execute one instruction per clock cycle.

Controls: Arrow keys   R = new maze   ESC = quit
"""

import pygame
import sys
import random
import math
from collections import deque

# ─────────────────────────────────────────────────────────────────────────────
# Display
# ─────────────────────────────────────────────────────────────────────────────
WIDTH, HEIGHT  = 1060, 680
ZONE1_H        = 165           # top bit-status panel  (≈ 1/4)
ZONE2_H        = HEIGHT - ZONE1_H
CLOCK_PANEL_W  = 185           # left clock column inside Zone 2
FPS            = 60

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Classical Computer: The Maze Runner  |  Quantum Exhibit")
clock = pygame.time.Clock()

# ─────────────────────────────────────────────────────────────────────────────
# Colors
# ─────────────────────────────────────────────────────────────────────────────
BG          = (8,  14,  8)
PCB_DARK    = (10, 28, 10)
PCB_MID     = (22, 60, 22)
PCB_TRACE   = (40, 118, 40)
PCB_VIA     = (58, 168, 58)
FLOOR       = (5,  12,  5)
NEON_GREEN  = (57, 255, 20)
BRIGHT_GRN  = (0,  222, 72)
PATH_RED    = (225, 38, 38)
GOLD        = (255, 205,  0)
WHITE       = (238, 245, 238)
BIT_OFF     = (22,  44, 22)
BIT_ON      = (175, 22, 22)
BIT_GLOW    = (255, 82, 82)
DIM         = (40,  85, 40)
AMBER       = (255, 160,  0)
AMBER_DIM   = (100, 62,  0)
GO_GREEN    = (30, 220, 80)
GO_DIM      = (12,  80, 30)

# ─────────────────────────────────────────────────────────────────────────────
# Fonts
# ─────────────────────────────────────────────────────────────────────────────
def _font(size, bold=True):
    for name in ("Courier New", "Courier", "monospace"):
        try:
            return pygame.font.SysFont(name, size, bold=bold)
        except Exception:
            pass
    return pygame.font.Font(None, size)

F_TITLE  = _font(21)
F_MED    = _font(15)
F_SM     = _font(12)
F_LARGE  = _font(30)
F_XSM    = _font(10)
F_CLOCK  = _font(28)        # big GO! / WAIT label
F_CLKSUB = _font(11)

# ─────────────────────────────────────────────────────────────────────────────
# Clock constants
# ─────────────────────────────────────────────────────────────────────────────
CLOCK_PERIOD     = 120        # frames per full cycle  (2 s at 60 fps)
CLOCK_TICK_FRAMES = 70        # frames the clock is HIGH  ("TICK / GO!")
#                               remaining 50 frames = LOW  ("TOCK / WAIT")

WAVE_W           = CLOCK_PANEL_W - 20   # pixels wide for the waveform
WAVE_SAMPLES     = WAVE_W               # one sample per pixel column
WAVE_SAMPLE_EVERY = 2                   # sample clock state every N frames

# ─────────────────────────────────────────────────────────────────────────────
# Maze parameters
# ─────────────────────────────────────────────────────────────────────────────
MAZE_COLS, MAZE_ROWS = 17, 10
GRID_W = 2 * MAZE_COLS + 1
GRID_H = 2 * MAZE_ROWS + 1

MAZE_AREA_W = WIDTH - CLOCK_PANEL_W
CELL        = min((ZONE2_H - 60) // GRID_H, (MAZE_AREA_W - 30) // GRID_W)
MAZE_PX_W   = GRID_W * CELL
MAZE_PX_H   = GRID_H * CELL
MAZE_OX     = CLOCK_PANEL_W + (MAZE_AREA_W - MAZE_PX_W) // 2
MAZE_OY     = ZONE1_H + 30

PLAYER_START = [1, 1]
GOAL_POS     = [GRID_H - 2, GRID_W - 2]


# ─────────────────────────────────────────────────────────────────────────────
# Maze generation
# ─────────────────────────────────────────────────────────────────────────────
def generate_maze(cols, rows):
    gw, gh = 2 * cols + 1, 2 * rows + 1
    grid = [[True] * gw for _ in range(gh)]
    vis  = [[False] * cols for _ in range(rows)]

    def carve(r, c):
        vis[r][c] = True
        grid[2 * r + 1][2 * c + 1] = False
        ds = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        random.shuffle(ds)
        for dr, dc in ds:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and not vis[nr][nc]:
                grid[2 * r + 1 + dr][2 * c + 1 + dc] = False
                carve(nr, nc)

    old = sys.getrecursionlimit()
    sys.setrecursionlimit(cols * rows * 12)
    carve(0, 0)
    sys.setrecursionlimit(old)
    return grid


def build_wall_decor(maze):
    decor = {}
    for r in range(GRID_H):
        for c in range(GRID_W):
            if maze[r][c]:
                rng = random.Random(r * 1009 + c * 37)
                items = []
                for _ in range(rng.randint(1, 3)):
                    if rng.random() < 0.5:
                        items.append(('h', rng.randint(2, CELL - 3)))
                    else:
                        items.append(('v', rng.randint(2, CELL - 3)))
                if rng.random() < 0.55:
                    items.append(('dot', rng.randint(3, CELL - 4), rng.randint(3, CELL - 4)))
                decor[(r, c)] = items
    return decor


def build_maze_surface(maze, decor):
    surf = pygame.Surface((MAZE_PX_W, MAZE_PX_H))
    surf.fill(FLOOR)
    for r in range(GRID_H):
        for c in range(GRID_W):
            x, y = c * CELL, r * CELL
            if maze[r][c]:
                pygame.draw.rect(surf, PCB_DARK, (x, y, CELL, CELL))
                pygame.draw.rect(surf, PCB_MID,  (x, y, CELL, CELL), 1)
                for d in decor.get((r, c), []):
                    if d[0] == 'h':
                        pygame.draw.line(surf, PCB_TRACE,
                                         (x + 1, y + d[1]), (x + CELL - 2, y + d[1]), 1)
                    elif d[0] == 'v':
                        pygame.draw.line(surf, PCB_TRACE,
                                         (x + d[1], y + 1), (x + d[1], y + CELL - 2), 1)
                    elif d[0] == 'dot':
                        pygame.draw.circle(surf, PCB_VIA, (x + d[1], y + d[2]), 2)
    return surf


# ─────────────────────────────────────────────────────────────────────────────
# Game state
# ─────────────────────────────────────────────────────────────────────────────
maze       = generate_maze(MAZE_COLS, MAZE_ROWS)
wall_decor = build_wall_decor(maze)
maze_surf  = build_maze_surface(maze, wall_decor)

player     = list(PLAYER_START)
path       = [tuple(PLAYER_START)]
move_count = 0
won        = False

bits       = [0] * 8
active_bit = -1
bit_flash  = 0
wall_flash = 0
tick       = 0

# Clock state
clock_phase   = 0          # frame index within current period (0 … CLOCK_PERIOD-1)
clk_history   = deque([0] * WAVE_SAMPLES, maxlen=WAVE_SAMPLES)  # 0=LOW, 1=HIGH
clk_blocked   = 0          # frames to show "wait for tick!" warning


def clock_is_high():
    return clock_phase < CLOCK_TICK_FRAMES


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def cell_center(row, col):
    return (MAZE_OX + col * CELL + CELL // 2,
            MAZE_OY + row * CELL + CELL // 2)


# ─────────────────────────────────────────────────────────────────────────────
# Drawing — Zone 1: bit panel
# ─────────────────────────────────────────────────────────────────────────────
def draw_bit_panel():
    pygame.draw.rect(screen, PCB_DARK, (0, 0, WIDTH, ZONE1_H))
    pygame.draw.rect(screen, PCB_TRACE, (0, 0, WIDTH, ZONE1_H), 2)
    for x in range(0, WIDTH, 55):
        pygame.draw.line(screen, PCB_MID, (x, 0), (x, ZONE1_H))

    t = F_TITLE.render("CLASSICAL COMPUTER:  THE MAZE RUNNER", True, NEON_GREEN)
    screen.blit(t, ((WIDTH - t.get_width()) // 2, 7))

    BW, BH = 48, 48
    GAP    = 10
    TW     = 8 * BW + 7 * GAP
    bx     = (WIDTH - TW) // 2
    by     = 35

    for i in range(8):
        rx   = bx + i * (BW + GAP)
        rect = pygame.Rect(rx, by, BW, BH)
        active = (i == active_bit and bit_flash > 0)

        if active:
            glow = rect.inflate(10, 10)
            pygame.draw.rect(screen, (110, 0, 0), glow, border_radius=7)
            pygame.draw.rect(screen, BIT_GLOW, rect, border_radius=5)
            vc = (0, 0, 0)
        else:
            bg = BIT_ON if bits[i] else BIT_OFF
            pygame.draw.rect(screen, bg, rect, border_radius=5)
            pygame.draw.rect(screen, PCB_TRACE, rect, 2, border_radius=5)
            vc = WHITE if bits[i] else DIM

        v = F_MED.render(str(bits[i]), True, vc)
        screen.blit(v, (rect.centerx - v.get_width() // 2,
                        rect.centery - v.get_height() // 2))

    bin_str = "".join(str(b) for b in bits)
    dec_val = int(bin_str, 2)
    bs = F_MED.render(bin_str, True, BRIGHT_GRN)
    screen.blit(bs, ((WIDTH - bs.get_width()) // 2, by + BH + 7))
    dv = F_XSM.render(
        f"0b {bin_str}   =   0x{dec_val:02X}   =   {dec_val:3d}", True, DIM)
    screen.blit(dv, ((WIDTH - dv.get_width()) // 2, by + BH + 26))
    sc = F_XSM.render(f"STEPS: {move_count}", True, DIM)
    screen.blit(sc, (12, ZONE1_H - 18))


# ─────────────────────────────────────────────────────────────────────────────
# Drawing — Clock panel  (left side of Zone 2)
# ─────────────────────────────────────────────────────────────────────────────
def draw_clock_panel():
    px, py = 0, ZONE1_H
    pw, ph = CLOCK_PANEL_W, ZONE2_H

    # Background
    pygame.draw.rect(screen, PCB_DARK, (px, py, pw, ph))
    pygame.draw.rect(screen, PCB_TRACE, (px, py, pw, ph), 2)

    is_high = clock_is_high()
    y = py + 12

    # ── Title ────────────────────────────────────────────────────────────
    title = F_CLKSUB.render("⚡  CPU  CLOCK  ⚡", True, NEON_GREEN)
    screen.blit(title, (px + (pw - title.get_width()) // 2, y))
    y += 20

    # ── Square wave ──────────────────────────────────────────────────────
    wave_x  = px + 10
    wave_y  = y
    wave_h  = 72
    high_y  = wave_y + 8           # y for HIGH level line
    low_y   = wave_y + wave_h - 8  # y for LOW level line

    # Wave background box
    pygame.draw.rect(screen, (5, 18, 5), (wave_x, wave_y, WAVE_W, wave_h))
    pygame.draw.rect(screen, PCB_MID,   (wave_x, wave_y, WAVE_W, wave_h), 1)

    # Reference lines (dim)
    pygame.draw.line(screen, (15, 40, 15), (wave_x, high_y), (wave_x + WAVE_W, high_y), 1)
    pygame.draw.line(screen, (15, 40, 15), (wave_x, low_y),  (wave_x + WAVE_W, low_y),  1)

    # Draw waveform as a polyline
    hist = list(clk_history)
    pts  = []
    for i, s in enumerate(hist):
        xp = wave_x + i
        yp = high_y if s else low_y
        # Insert vertical segment on transitions
        if i > 0 and hist[i] != hist[i - 1]:
            pts.append((xp, high_y if hist[i - 1] else low_y))
        pts.append((xp, yp))

    if len(pts) >= 2:
        wave_color = GO_GREEN if is_high else AMBER
        pygame.draw.lines(screen, wave_color, False, pts, 2)

    # Cursor — bright vertical line at rightmost sample
    cursor_x = wave_x + WAVE_W - 1
    pygame.draw.line(screen, WHITE, (cursor_x, wave_y + 2), (cursor_x, wave_y + wave_h - 2), 1)

    # Labels "1" / "0" on the side
    lbl1 = F_XSM.render("1", True, DIM)
    lbl0 = F_XSM.render("0", True, DIM)
    screen.blit(lbl1, (wave_x - 8, high_y - 5))
    screen.blit(lbl0, (wave_x - 8, low_y  - 5))

    y += wave_h + 14

    # ── Big state indicator ───────────────────────────────────────────────
    ind_w, ind_h = pw - 20, 58
    ind_x = px + 10
    ind_y = y

    if is_high:
        bg_col   = (12, 80, 28)
        border_c = GO_GREEN
        label    = "GO!"
        sub      = "(TICK)"
        txt_col  = GO_GREEN
    else:
        bg_col   = (70, 42, 0)
        border_c = AMBER
        label    = "WAIT"
        sub      = "(TOCK)"
        txt_col  = AMBER

    # Glow behind box when GO
    if is_high:
        pulse = 0.6 + 0.4 * math.sin(tick * 0.15)
        glow_surf = pygame.Surface((ind_w + 12, ind_h + 12), pygame.SRCALPHA)
        glow_surf.fill((0, int(180 * pulse), 40, 50))
        screen.blit(glow_surf, (ind_x - 6, ind_y - 6))

    pygame.draw.rect(screen, bg_col,   (ind_x, ind_y, ind_w, ind_h), border_radius=6)
    pygame.draw.rect(screen, border_c, (ind_x, ind_y, ind_w, ind_h), 2, border_radius=6)

    lbl  = F_CLOCK.render(label, True, txt_col)
    slbl = F_CLKSUB.render(sub,  True, border_c)
    screen.blit(lbl,  (ind_x + (ind_w - lbl.get_width())  // 2, ind_y + 6))
    screen.blit(slbl, (ind_x + (ind_w - slbl.get_width()) // 2, ind_y + ind_h - 18))

    y += ind_h + 10

    # ── Progress bar for current phase ───────────────────────────────────
    bar_w   = pw - 20
    bar_h   = 14
    bar_x   = px + 10
    bar_y   = y

    if is_high:
        phase_progress = clock_phase / CLOCK_TICK_FRAMES
        bar_color = GO_GREEN
    else:
        phase_progress = (clock_phase - CLOCK_TICK_FRAMES) / (CLOCK_PERIOD - CLOCK_TICK_FRAMES)
        bar_color = AMBER

    filled = int(bar_w * phase_progress)
    pygame.draw.rect(screen, (15, 30, 15), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
    if filled > 0:
        pygame.draw.rect(screen, bar_color, (bar_x, bar_y, filled, bar_h), border_radius=3)
    pygame.draw.rect(screen, PCB_MID, (bar_x, bar_y, bar_w, bar_h), 1, border_radius=3)

    y += bar_h + 6

    # Countdown text
    if is_high:
        frames_left = CLOCK_TICK_FRAMES - clock_phase
    else:
        frames_left = CLOCK_PERIOD - clock_phase
    secs_left = frames_left / FPS
    cdlbl = "MOVE NOW!" if is_high else f"next TICK in {secs_left:.1f}s"
    cd = F_XSM.render(cdlbl, True, bar_color)
    screen.blit(cd, (px + (pw - cd.get_width()) // 2, y))
    y += 18

    # ── Blocked warning ───────────────────────────────────────────────────
    if clk_blocked > 0:
        alpha   = int(255 * min(clk_blocked / 20, 1.0))
        blink   = (tick // 6) % 2 == 0
        if blink:
            wt = F_SM.render("⛔ WAIT FOR TICK!", True, (255, alpha // 2, 0))
            screen.blit(wt, (px + (pw - wt.get_width()) // 2, y))
    y += 22

    # ── Divider ───────────────────────────────────────────────────────────
    pygame.draw.line(screen, PCB_MID, (px + 10, y), (px + pw - 10, y))
    y += 10

    # ── Non-technical explanation ─────────────────────────────────────────
    lines = [
        "Think of the clock",
        "as a heartbeat.",
        "",
        "The computer can",
        "only act on each",
        "TICK — one step",
        "at a time.",
        "",
        "No TICK = no move.",
    ]
    for line in lines:
        t = F_XSM.render(line, True, DIM)
        screen.blit(t, (px + (pw - t.get_width()) // 2, y))
        y += 13


# ─────────────────────────────────────────────────────────────────────────────
# Drawing — Zone 2: maze elements
# ─────────────────────────────────────────────────────────────────────────────
def draw_path_trail():
    if len(path) < 2:
        return
    pts = [cell_center(r, c) for (r, c) in path]
    pygame.draw.lines(screen, PATH_RED, False, pts, 3)


def draw_goal():
    gr, gc = GOAL_POS
    gx = MAZE_OX + gc * CELL
    gy = MAZE_OY + gr * CELL

    pulse = 0.5 + 0.5 * math.sin(tick * 0.07)
    fill  = (int(15 + 200 * pulse), int(70 + 140 * pulse), int(15 + 40 * pulse))
    pygame.draw.rect(screen, fill, (gx, gy, CELL, CELL))
    pygame.draw.rect(screen, BRIGHT_GRN, (gx, gy, CELL, CELL), 2)

    et = F_XSM.render("EXIT", True, BRIGHT_GRN)
    screen.blit(et, (gx + (CELL - et.get_width()) // 2,
                     gy + (CELL - et.get_height()) // 2))

    alpha = int(90 + 160 * abs(math.sin(tick * 0.035)))
    glow  = (0, min(255, alpha), 38)
    t1 = F_XSM.render("ONE PATH.", True, glow)
    t2 = F_XSM.render("ONE PATH AT A TIME.", True, glow)
    tx = gx - t2.get_width() - 6
    screen.blit(t1, (tx + (t2.get_width() - t1.get_width()), gy + 1))
    screen.blit(t2, (tx, gy + 13))


def draw_wall_flash():
    alpha = int(200 * wall_flash / 20)
    fs    = pygame.Surface((MAZE_PX_W, MAZE_PX_H), pygame.SRCALPHA)
    fs.fill((255, 38, 38, alpha))
    screen.blit(fs, (MAZE_OX, MAZE_OY))


def draw_clock_blocked_overlay():
    """Amber tint on maze when player tries to move during TOCK."""
    alpha = int(120 * clk_blocked / 25)
    fs    = pygame.Surface((MAZE_PX_W, MAZE_PX_H), pygame.SRCALPHA)
    fs.fill((200, 120, 0, alpha))
    screen.blit(fs, (MAZE_OX, MAZE_OY))


def draw_turtle(row, col):
    cx, cy = cell_center(row, col)
    r = max(CELL // 2 - 2, 8)

    leg_c = (28, 130, 48)
    leg_r = max(3, r // 4)
    for dx, dy in [(r - 4, -(r - 4)), (r - 4, r - 4),
                   (-(r - 4), -(r - 4)), (-(r - 4), r - 4)]:
        pygame.draw.circle(screen, leg_c, (cx + dx, cy + dy), leg_r)

    shell_rect = pygame.Rect(cx - r + 2, cy - r + 2, 2 * r - 4, 2 * r - 4)
    pygame.draw.ellipse(screen, (24, 95, 34), shell_rect)

    inner = max(2, r // 3)
    pygame.draw.circle(screen, (16, 65, 22), (cx,          cy),          inner)
    pygame.draw.circle(screen, (16, 65, 22), (cx - r // 3, cy - r // 3), inner - 1)
    pygame.draw.circle(screen, (16, 65, 22), (cx + r // 3, cy - r // 3), inner - 1)
    pygame.draw.circle(screen, (16, 65, 22), (cx,          cy + r // 3), inner - 1)
    pygame.draw.ellipse(screen, (42, 155, 55), shell_rect, 2)

    hx = cx + r - 2
    pygame.draw.circle(screen, (50, 175, 68), (hx, cy), max(4, r // 3))

    hw    = max(10, r // 2 + 5)
    hh    = max(5,  r // 4 + 2)
    hat_y = cy - r // 3 - hh - 1
    pygame.draw.rect(screen, (220, 180, 0),
                     (hx - hw // 2, hat_y, hw, hh), border_radius=2)
    pygame.draw.rect(screen, (200, 150, 0),
                     (hx - hw // 2 - 3, hat_y + hh - 3, hw + 6, 3), border_radius=1)


def draw_win():
    ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 175))
    screen.blit(ov, (0, 0))

    t1 = F_LARGE.render("PATH COMPLETE!", True, GOLD)
    t2 = F_MED.render("One path.  One solution.  Sequential.", True, BRIGHT_GRN)
    t3 = F_SM.render(f"Total moves: {move_count}         Press R to play again", True, DIM)

    cy = HEIGHT // 2 - 44
    screen.blit(t1, ((WIDTH - t1.get_width()) // 2, cy))
    screen.blit(t2, ((WIDTH - t2.get_width()) // 2, cy + 44))
    screen.blit(t3, ((WIDTH - t3.get_width()) // 2, cy + 78))


# ─────────────────────────────────────────────────────────────────────────────
# Game logic
# ─────────────────────────────────────────────────────────────────────────────
def attempt_move(dr, dc):
    global move_count, active_bit, bit_flash, wall_flash, won, clk_blocked

    if won:
        return

    # ── Clock gate: only allow movement during TICK (HIGH) phase ──────────
    if not clock_is_high():
        clk_blocked = 30   # show warning for 30 frames
        return

    nr, nc = player[0] + dr, player[1] + dc

    if (0 <= nr < GRID_H and 0 <= nc < GRID_W and not maze[nr][nc]):
        player[0], player[1] = nr, nc
        path.append((nr, nc))
        move_count += 1

        bi = move_count % 8
        bits[bi] ^= 1
        active_bit = bi
        bit_flash  = 38

        if [nr, nc] == GOAL_POS:
            won = True
    else:
        wall_flash = 20


def reset_game():
    global maze, wall_decor, maze_surf
    global player, path, move_count, won
    global bits, active_bit, bit_flash, wall_flash, tick
    global clock_phase, clk_history, clk_blocked

    maze       = generate_maze(MAZE_COLS, MAZE_ROWS)
    wall_decor = build_wall_decor(maze)
    maze_surf  = build_maze_surface(maze, wall_decor)

    player     = list(PLAYER_START)
    path       = [tuple(PLAYER_START)]
    move_count = 0
    won        = False
    bits       = [0] * 8
    active_bit = -1
    bit_flash  = 0
    wall_flash = 0
    tick       = 0
    clock_phase  = 0
    clk_history  = deque([0] * WAVE_SAMPLES, maxlen=WAVE_SAMPLES)
    clk_blocked  = 0


# ─────────────────────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────────────────────
def main():
    global bit_flash, wall_flash, tick, clock_phase, clk_blocked

    while True:
        clock.tick(FPS)
        tick       += 1
        clock_phase = tick % CLOCK_PERIOD

        # Sample waveform history every N frames
        if tick % WAVE_SAMPLE_EVERY == 0:
            clk_history.append(1 if clock_is_high() else 0)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            elif event.type == pygame.KEYDOWN:
                if   event.key == pygame.K_ESCAPE: pygame.quit(); sys.exit()
                elif event.key == pygame.K_r:       reset_game()
                elif event.key == pygame.K_UP:      attempt_move(-1,  0)
                elif event.key == pygame.K_DOWN:    attempt_move( 1,  0)
                elif event.key == pygame.K_LEFT:    attempt_move( 0, -1)
                elif event.key == pygame.K_RIGHT:   attempt_move( 0,  1)

        if bit_flash    > 0: bit_flash    -= 1
        if wall_flash   > 0: wall_flash   -= 1
        if clk_blocked  > 0: clk_blocked  -= 1

        # ── Render ────────────────────────────────────────────────────────
        screen.fill(BG)
        draw_bit_panel()                              # Zone 1 — top
        draw_clock_panel()                            # Zone 2 left — clock
        screen.blit(maze_surf, (MAZE_OX, MAZE_OY))   # Zone 2 right — maze walls
        draw_path_trail()                             # red trail
        draw_goal()                                   # pulsing exit
        draw_turtle(player[0], player[1])             # avatar

        if wall_flash  > 0: draw_wall_flash()
        if clk_blocked > 0: draw_clock_blocked_overlay()
        if won:             draw_win()

        pygame.display.flip()


if __name__ == "__main__":
    main()
