"""
ray_solver.py — BFS-based maze ray solver + visual renderer.

The "ray" is the shortest BFS path from the player toward the exit,
limited to depth_limit cells. Multiple BFS branches are resolved by
picking the frontier cell with the lowest Manhattan distance to exit.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from collections import deque

import pygame
from settings import ROWS, COLS, CELL, MAZE_X0, MAZE_Y0
from maze import get_neighbors

# Pre-allocated bloom surface (lazy-init, reused every frame)
_bloom_surf: pygame.Surface | None = None


# ── Result dataclass ──────────────────────────────────────────────────────────
@dataclass
class SolveResult:
    path:          list   # ordered cells start → best-frontier or exit
    reached_exit:  bool   # True only when exit is within depth_limit
    depth_used:    int    # len(path) - 1
    frontier:      list   # leaf cells at the depth boundary


# ── Solver ────────────────────────────────────────────────────────────────────
class RaySolver:
    def __init__(self, maze, max_possible_depth: int = 20):
        self._maze = maze

    def update_maze(self, maze):
        """Call after maze collapse to swap the underlying grid."""
        self._maze = maze

    def solve(self, start: tuple, exit_cell: tuple,
              depth_limit: int) -> SolveResult:
        """
        BFS from start, expanding up to depth_limit cells.
        Returns a single-chain path to the best frontier cell
        (or exit if reachable within the limit).
        """
        depth_limit = max(1, depth_limit)

        parent:   dict[tuple, tuple | None] = {start: None}
        depth_map: dict[tuple, int]          = {start: 0}
        queue     = deque([start])
        frontier: list[tuple]                = []

        while queue:
            cell = queue.popleft()
            d    = depth_map[cell]

            # ── Reached exit ─────────────────────────────────────────────────
            if cell == exit_cell:
                path = _trace(parent, cell)
                return SolveResult(
                    path=path,
                    reached_exit=True,
                    depth_used=len(path) - 1,
                    frontier=[cell],
                )

            # ── At depth limit → leaf / frontier ─────────────────────────────
            if d >= depth_limit:
                frontier.append(cell)
                continue       # do not expand further

            # ── Normal expansion ──────────────────────────────────────────────
            for nb in get_neighbors(self._maze, *cell):
                if nb not in parent:
                    parent[nb]    = cell
                    depth_map[nb] = d + 1
                    queue.append(nb)

        # BFS exhausted before reaching depth_limit (tiny maze / large limit)
        if not frontier:
            # All reachable cells visited; treat the deepest ones as frontier
            max_d = max(depth_map.values()) if depth_map else 0
            frontier = [c for c, d in depth_map.items() if d == max_d]
            if not frontier:
                frontier = [start]

        # Pick frontier cell closest to exit by Manhattan distance
        er, ec = exit_cell
        best   = min(frontier, key=lambda c: abs(c[0] - er) + abs(c[1] - ec))
        path   = _trace(parent, best)

        return SolveResult(
            path=path,
            reached_exit=False,
            depth_used=len(path) - 1,
            frontier=frontier,
        )


# ── Path trace helper ─────────────────────────────────────────────────────────
def _trace(parent: dict, cell: tuple) -> list:
    path, cur = [], cell
    while cur is not None:
        path.append(cur)
        cur = parent[cur]
    path.reverse()
    return path


# ── Pixel helper ──────────────────────────────────────────────────────────────
def _cell_px(r: int, c: int) -> tuple:
    return (MAZE_X0 + c * CELL + CELL // 2,
            MAZE_Y0 + r * CELL + CELL // 2)


# ── Renderer ──────────────────────────────────────────────────────────────────
def draw_ray(surface: pygame.Surface, result: SolveResult, cell_size: int):
    """
    Draw the BFS ray path onto surface.
    Draw order: bloom (glow) → core line → frontier dots.
    Caller is responsible for correct layer order (above fog, below player).
    """
    global _bloom_surf

    path = result.path
    if len(path) < 2:
        return

    pts = [_cell_px(*cell) for cell in path]

    # ── Bloom pass (7 px, alpha 40, separate SRCALPHA surface) ───────────────
    size = surface.get_size()
    if _bloom_surf is None or _bloom_surf.get_size() != size:
        _bloom_surf = pygame.Surface(size, pygame.SRCALPHA)
    _bloom_surf.fill((0, 0, 0, 0))

    for i in range(len(pts) - 1):
        pygame.draw.line(_bloom_surf, (255, 248, 220, 40), pts[i], pts[i + 1], 7)
    surface.blit(_bloom_surf, (0, 0))

    # ── Core line (3 px, warm white) ─────────────────────────────────────────
    for i in range(len(pts) - 1):
        pygame.draw.line(surface, (255, 248, 220), pts[i], pts[i + 1], 3)

    # ── Frontier dots ────────────────────────────────────────────────────────
    dot_col = (139, 92, 246) if result.reached_exit else (0, 229, 255)
    dot_r   = max(2, int(cell_size * 0.25))
    for cell in result.frontier:
        pygame.draw.circle(surface, dot_col, _cell_px(*cell), dot_r)
