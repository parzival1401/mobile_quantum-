"""
classical_maze_pygame.py  —  Classical Computer: The Maze Runner
=================================================================
Quantum Exhibition  |  Classical vs Quantum Computing

ZONE 1  (top 1/4 )  : 8-bit switch panel — one bit flips & glows red each move
ZONE 2  (bottom 3/4): Circuit-board maze with animated turtle-in-hard-hat avatar

Controls: Arrow keys   R = new maze   ESC = quit
"""

import pygame
import sys
import random
import math

# ─────────────────────────────────────────────────────────────────────────────
# Display
# ─────────────────────────────────────────────────────────────────────────────
WIDTH, HEIGHT = 980, 680
ZONE1_H = 165          # bit-status panel  (≈ 1/4)
ZONE2_H = HEIGHT - ZONE1_H
FPS = 60

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
DARK_GRN    = (15,  45, 15)

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

F_TITLE = _font(21)
F_MED   = _font(15)
F_SM    = _font(12)
F_LARGE = _font(30)
F_XSM   = _font(10)

# ─────────────────────────────────────────────────────────────────────────────
# Maze parameters & generation
# ─────────────────────────────────────────────────────────────────────────────
MAZE_COLS, MAZE_ROWS = 17, 10   # logical cells  (larger = more complex path)
GRID_W = 2 * MAZE_COLS + 1
GRID_H = 2 * MAZE_ROWS + 1

CELL = min((ZONE2_H - 60) // GRID_H, (WIDTH - 40) // GRID_W)
MAZE_PX_W = GRID_W * CELL
MAZE_PX_H = GRID_H * CELL
MAZE_OX   = (WIDTH - MAZE_PX_W) // 2
MAZE_OY   = ZONE1_H + 30

PLAYER_START = [1, 1]
GOAL_POS     = [GRID_H - 2, GRID_W - 2]


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
    """Pre-generate deterministic circuit-board decorations per wall cell."""
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
                pygame.draw.rect(surf, PCB_DARK,  (x, y, CELL, CELL))
                pygame.draw.rect(surf, PCB_MID,   (x, y, CELL, CELL), 1)
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
# Game state (mutable, reset-able)
# ─────────────────────────────────────────────────────────────────────────────
maze      = generate_maze(MAZE_COLS, MAZE_ROWS)
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

    # Subtle vertical lines (PCB feel)
    for x in range(0, WIDTH, 55):
        pygame.draw.line(screen, PCB_MID, (x, 0), (x, ZONE1_H))

    # Title
    t = F_TITLE.render("CLASSICAL COMPUTER:  THE MAZE RUNNER", True, NEON_GREEN)
    screen.blit(t, ((WIDTH - t.get_width()) // 2, 7))

    # 8 bit switches
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

    # Binary string + decoded value
    bin_str = "".join(str(b) for b in bits)
    dec_val = int(bin_str, 2)

    bs = F_MED.render(bin_str, True, BRIGHT_GRN)
    screen.blit(bs, ((WIDTH - bs.get_width()) // 2, by + BH + 7))

    dv = F_XSM.render(
        f"0b {bin_str}   =   0x{dec_val:02X}   =   {dec_val:3d}",
        True, DIM,
    )
    screen.blit(dv, ((WIDTH - dv.get_width()) // 2, by + BH + 26))

    # Step counter
    sc = F_XSM.render(f"STEPS: {move_count}", True, DIM)
    screen.blit(sc, (12, ZONE1_H - 18))


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

    # "ONE PATH AT A TIME." glowing text — positioned left of exit
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


def draw_turtle(row, col):
    cx, cy = cell_center(row, col)
    r = max(CELL // 2 - 2, 8)

    # Legs (4 rounded bumps)
    leg_c = (28, 130, 48)
    leg_r = max(3, r // 4)
    for dx, dy in [(r - 4, -(r - 4)), (r - 4, r - 4),
                   (-(r - 4), -(r - 4)), (-(r - 4), r - 4)]:
        pygame.draw.circle(screen, leg_c, (cx + dx, cy + dy), leg_r)

    # Shell body
    shell_rect = pygame.Rect(cx - r + 2, cy - r + 2, 2 * r - 4, 2 * r - 4)
    pygame.draw.ellipse(screen, (24, 95, 34), shell_rect)

    # Shell hex pattern
    inner = max(2, r // 3)
    pygame.draw.circle(screen, (16, 65, 22), (cx,           cy),           inner)
    pygame.draw.circle(screen, (16, 65, 22), (cx - r // 3,  cy - r // 3), inner - 1)
    pygame.draw.circle(screen, (16, 65, 22), (cx + r // 3,  cy - r // 3), inner - 1)
    pygame.draw.circle(screen, (16, 65, 22), (cx,           cy + r // 3), inner - 1)
    pygame.draw.ellipse(screen, (42, 155, 55), shell_rect, 2)

    # Head (right side, moving direction)
    hx = cx + r - 2
    pygame.draw.circle(screen, (50, 175, 68), (hx, cy), max(4, r // 3))

    # Hard hat (yellow)
    hw    = max(10, r // 2 + 5)
    hh    = max(5,  r // 4 + 2)
    hat_y = cy - r // 3 - hh - 1
    pygame.draw.rect(screen, (220, 180, 0),
                     (hx - hw // 2, hat_y, hw, hh), border_radius=2)
    pygame.draw.rect(screen, (200, 150, 0),
                     (hx - hw // 2 - 3, hat_y + hh - 3, hw + 6, 3),
                     border_radius=1)


def draw_win():
    ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 175))
    screen.blit(ov, (0, 0))

    pulse = 0.5 + 0.5 * math.sin(tick * 0.08)
    gc    = (int(200 * pulse), int(200 + 55 * pulse), 0)

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
    global move_count, active_bit, bit_flash, wall_flash, won

    if won:
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


# ─────────────────────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────────────────────

def main():
    global bit_flash, wall_flash, tick

    while True:
        clock.tick(FPS)
        tick += 1

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if   event.key == pygame.K_ESCAPE:  pygame.quit(); sys.exit()
                elif event.key == pygame.K_r:        reset_game()
                elif event.key == pygame.K_UP:       attempt_move(-1,  0)
                elif event.key == pygame.K_DOWN:     attempt_move( 1,  0)
                elif event.key == pygame.K_LEFT:     attempt_move( 0, -1)
                elif event.key == pygame.K_RIGHT:    attempt_move( 0,  1)

        if bit_flash  > 0: bit_flash  -= 1
        if wall_flash > 0: wall_flash -= 1

        # ── Render ────────────────────────────────────────────────────────
        screen.fill(BG)

        draw_bit_panel()                               # Zone 1

        screen.blit(maze_surf, (MAZE_OX, MAZE_OY))    # Zone 2: circuit walls
        draw_path_trail()                              # red trail
        draw_goal()                                    # pulsing exit + text
        draw_turtle(player[0], player[1])              # avatar

        if wall_flash > 0:
            draw_wall_flash()                          # red flash on collision

        if won:
            draw_win()                                 # victory overlay

        pygame.display.flip()


if __name__ == "__main__":
    main()
