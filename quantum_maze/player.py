"""Player movement, grid-snap animation, quantum jump tween."""

import pygame
from effects import ease_in_out_quad
from settings import (
    N, S, E, W,
    ROWS, COLS, CELL, MAZE_X0, MAZE_Y0,
    START_CELL, EXIT_CELL,
    PLAYER_C, PLAYER_CENTER_C, PLAYER_RADIUS,
    PLAYER_MOVE_TIME, JUMP_DURATION, JUMP_COOLDOWN,
)
from maze import is_open


def _cell_center(r: int, c: int) -> tuple:
    return (MAZE_X0 + c * CELL + CELL // 2,
            MAZE_Y0 + r * CELL + CELL // 2)


class Player:
    def __init__(self):
        self.row, self.col = START_CELL
        cx, cy = _cell_center(self.row, self.col)
        self._px = float(cx)
        self._py = float(cy)

        # Grid-slide tween
        self._slide_from = (self._px, self._py)
        self._slide_to   = (self._px, self._py)
        self._slide_t    = 1.0       # 1.0 = finished

        # Quantum jump tween
        self._jump_from  = (self._px, self._py)
        self._jump_to    = (self._px, self._py)
        self._jump_t     = 1.0
        self.is_jumping  = False
        self.jump_cooldown = 0.0

    # ── Public pixel position ─────────────────────────────────────────────────
    @property
    def px(self) -> int: return int(self._px)
    @property
    def py(self) -> int: return int(self._py)

    def is_moving(self) -> bool:
        return self._slide_t < 1.0

    def at_exit(self) -> bool:
        return (self.row, self.col) == EXIT_CELL

    # ── Grid movement ─────────────────────────────────────────────────────────
    def try_move(self, maze, dr: int, dc: int) -> bool:
        if self.is_moving() or self.is_jumping:
            return False
        nr, nc = self.row + dr, self.col + dc
        if not (0 <= nr < ROWS and 0 <= nc < COLS):
            return False
        direction = {(-1,0): N, (1,0): S, (0,1): E, (0,-1): W}.get((dr, dc))
        if direction and is_open(maze, self.row, self.col, direction):
            self.row, self.col = nr, nc
            self._slide_from = (self._px, self._py)
            self._slide_to   = tuple(float(v) for v in _cell_center(nr, nc))
            self._slide_t    = 0.0
            return True
        return False

    # ── Quantum jump ─────────────────────────────────────────────────────────
    def start_jump(self, endpoint_px: tuple):
        tx = max(MAZE_X0, min(MAZE_X0 + COLS * CELL - 1, endpoint_px[0]))
        ty = max(MAZE_Y0, min(MAZE_Y0 + ROWS * CELL - 1, endpoint_px[1]))
        self.row = (ty - MAZE_Y0) // CELL
        self.col = (tx - MAZE_X0) // CELL
        self._jump_from = (self._px, self._py)
        self._jump_to   = (float(tx), float(ty))
        self._jump_t    = 0.0
        self.is_jumping = True

    def snap_to_cell(self, r: int, c: int):
        self.row, self.col = r, c
        cx, cy = _cell_center(r, c)
        self._px, self._py = float(cx), float(cy)
        self._slide_t = 1.0
        self._jump_t  = 1.0
        self.is_jumping = False

    # ── Update ────────────────────────────────────────────────────────────────
    def update(self, dt: float):
        # Grid slide (linear)
        if self._slide_t < 1.0:
            self._slide_t = min(1.0, self._slide_t + dt / PLAYER_MOVE_TIME)
            t = self._slide_t
            self._px = self._slide_from[0] + (self._slide_to[0] - self._slide_from[0]) * t
            self._py = self._slide_from[1] + (self._slide_to[1] - self._slide_from[1]) * t

        # Quantum jump (ease-in-out)
        if self.is_jumping:
            self._jump_t = min(1.0, self._jump_t + dt / JUMP_DURATION)
            e = ease_in_out_quad(self._jump_t)
            self._px = self._jump_from[0] + (self._jump_to[0] - self._jump_from[0]) * e
            self._py = self._jump_from[1] + (self._jump_to[1] - self._jump_from[1]) * e
            if self._jump_t >= 1.0:
                self.is_jumping   = False
                self.jump_cooldown = JUMP_COOLDOWN

        # Cooldown countdown
        if self.jump_cooldown > 0:
            self.jump_cooldown = max(0.0, self.jump_cooldown - dt)

    # ── Draw ──────────────────────────────────────────────────────────────────
    def draw(self, surface):
        px, py = self.px, self.py
        pygame.draw.circle(surface, (0, 60,  90), (px, py), PLAYER_RADIUS + 6)
        pygame.draw.circle(surface, PLAYER_C,        (px, py), PLAYER_RADIUS)
        pygame.draw.circle(surface, PLAYER_CENTER_C, (px, py), max(2, PLAYER_RADIUS - 4))
