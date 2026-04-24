"""
Ray casting + fog-of-war overlay.

Fog surface is a full-screen SRCALPHA surface filled black at alpha=FOG_ALPHA
each frame. Holes are punched using BLEND_RGBA_SUB:
  • ambient circle  — radial gradient around player
  • lit cells along the ray — partial transparency
"""

import math
import numpy as np
import pygame
from settings import (
    N, S, E, W,
    ROWS, COLS, CELL, MAZE_X0, MAZE_Y0,
    FOG_C, FOG_ALPHA, AMBIENT_RADIUS,
    RAY_STEP, RAY_MAX_DIST,
    RAY_C, RAY_GLOW_C,
    SW, GAME_H,
)
from maze import is_open


# ── Pre-compute ambient gradient surface (done once at import time) ───────────
def _build_ambient(radius: int) -> pygame.Surface:
    size = radius * 2
    # Use numpy for fast per-pixel alpha computation
    yi, xi = np.ogrid[:size, :size]
    dist = np.sqrt((xi - radius) ** 2 + (yi - radius) ** 2).astype(np.float32)
    alpha = np.clip(FOG_ALPHA * (1.0 - dist / radius), 0, 255).astype(np.uint8)

    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    # surfarray pixels_alpha is indexed (x, y) = (col, row) — transpose
    pygame.surfarray.pixels_alpha(surf)[:, :] = alpha.T
    return surf


def make_ambient(radius: int) -> pygame.Surface:
    return _build_ambient(radius)


# ── Ray casting ───────────────────────────────────────────────────────────────
def cast_ray(player_px: tuple, angle_rad: float, maze: np.ndarray):
    """
    Step along angle_rad from player_px, stopping at the first wall.
    Returns (lit_cells: list[tuple], endpoint_px: tuple).
    """
    ox, oy  = player_px
    cos_a   = math.cos(angle_rad)
    sin_a   = math.sin(angle_rad)

    pr = int((oy - MAZE_Y0) / CELL)
    pc = int((ox - MAZE_X0) / CELL)
    pr = max(0, min(ROWS - 1, pr))
    pc = max(0, min(COLS - 1, pc))

    lit     = {(pr, pc)}
    prev_r  = pr
    prev_c  = pc
    endpoint = (int(ox), int(oy))

    for d in range(RAY_STEP, RAY_MAX_DIST + RAY_STEP, RAY_STEP):
        x = ox + cos_a * d
        y = oy + sin_a * d

        r = int((y - MAZE_Y0) / CELL)
        c = int((x - MAZE_X0) / CELL)

        # Out of maze bounds → stop
        if not (0 <= r < ROWS and 0 <= c < COLS):
            break

        # Crossed a cell boundary → check wall
        if r != prev_r or c != prev_c:
            if _wall_blocks(maze, prev_r, prev_c, r - prev_r, c - prev_c):
                break
            prev_r, prev_c = r, c

        lit.add((r, c))
        endpoint = (int(x), int(y))

    return list(lit), endpoint


def _wall_blocks(maze, r, c, dr, dc) -> bool:
    if   dr == -1 and dc ==  0: return not is_open(maze, r, c, N)
    elif dr ==  1 and dc ==  0: return not is_open(maze, r, c, S)
    elif dr ==  0 and dc ==  1: return not is_open(maze, r, c, E)
    elif dr ==  0 and dc == -1: return not is_open(maze, r, c, W)
    elif abs(dr) == 1 and abs(dc) == 1:
        bv = not is_open(maze, r, c, N if dr == -1 else S)
        bh = not is_open(maze, r, c, E if dc ==  1 else W)
        return bv and bh
    return True


# ── Fog rendering ─────────────────────────────────────────────────────────────
def render(screen, fog_surf, ray_surf, ambient_surf,
           player_px, angle_rad, maze, lit_cells):
    """Composite fog + ray onto screen. Call after drawing maze/player."""
    px, py = player_px

    # 1. Reset fog to uniform darkness
    fog_surf.fill((*FOG_C, FOG_ALPHA))

    # 2. Punch ambient hole around player
    ax = px - AMBIENT_RADIUS
    ay = py - AMBIENT_RADIUS
    fog_surf.blit(ambient_surf, (ax, ay), special_flags=pygame.BLEND_RGBA_SUB)

    # 3. Partially reveal cells along the ray (outside ambient radius)
    for (r, c) in lit_cells:
        ccx = MAZE_X0 + c * CELL + CELL // 2
        ccy = MAZE_Y0 + r * CELL + CELL // 2
        if (ccx - px) ** 2 + (ccy - py) ** 2 > AMBIENT_RADIUS ** 2:
            fog_surf.fill(
                (0, 0, 0, 150),
                (MAZE_X0 + c * CELL, MAZE_Y0 + r * CELL, CELL, CELL),
                special_flags=pygame.BLEND_RGBA_SUB,
            )

    # 4. Blit fog
    screen.blit(fog_surf, (0, 0))

    # 5. Draw ray on top of fog (glow + line on the pre-allocated ray_surf)
    _, endpoint = cast_ray(player_px, angle_rad, maze)
    if endpoint != player_px:
        ray_surf.fill((0, 0, 0, 0))
        pygame.draw.line(ray_surf, (*RAY_GLOW_C, 35), (px, py), endpoint, 7)
        pygame.draw.line(ray_surf, (*RAY_C, 180),     (px, py), endpoint, 1)
        screen.blit(ray_surf, (0, 0))

    return endpoint
