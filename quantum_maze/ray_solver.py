"""
ray_solver.py — BFS-based maze ray solver + visual renderer.

BFS expands from the player up to depth_limit cells. Every leaf node
(frontier cell) gets its own traced path back to start. All branches are
drawn and each frontier cell has equal probability for quantum jump.
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
    path:          list         # path to the closest-to-exit frontier cell (for compat)
    reached_exit:  bool         # True only when exit is within depth_limit
    depth_used:    int          # max depth reached
    frontier:      list         # all leaf cells at the depth boundary
    all_paths:     list = field(default_factory=list)  # one path per frontier cell


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
        Returns all branch paths — one per frontier cell — so every
        frontier cell can be drawn and targeted for quantum jump.
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
                    all_paths=[path],
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
            max_d = max(depth_map.values()) if depth_map else 0
            frontier = [c for c, d in depth_map.items() if d == max_d]
            if not frontier:
                frontier = [start]

        # Trace a path for every frontier cell
        all_paths = [_trace(parent, f) for f in frontier]

        # Keep a single "best" path for backward compatibility
        er, ec = exit_cell
        best_idx = min(range(len(frontier)),
                       key=lambda i: abs(frontier[i][0] - er) + abs(frontier[i][1] - ec))
        best_path = all_paths[best_idx]

        return SolveResult(
            path=best_path,
            reached_exit=False,
            depth_used=len(best_path) - 1,
            frontier=frontier,
            all_paths=all_paths,
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
    Draw all BFS branch paths onto surface.
    Draw order: bloom (glow) → core lines → frontier dots.
    Caller is responsible for correct layer order (above fog, below player).
    """
    global _bloom_surf

    paths = result.all_paths if result.all_paths else ([result.path] if result.path else [])
    paths = [p for p in paths if len(p) >= 2]
    if not paths:
        return

    size = surface.get_size()
    if _bloom_surf is None or _bloom_surf.get_size() != size:
        _bloom_surf = pygame.Surface(size, pygame.SRCALPHA)
    _bloom_surf.fill((0, 0, 0, 0))

    # ── Bloom pass (all branches) ─────────────────────────────────────────────
    for path in paths:
        pts = [_cell_px(*cell) for cell in path]
        for i in range(len(pts) - 1):
            pygame.draw.line(_bloom_surf, (255, 248, 220, 40), pts[i], pts[i + 1], 7)
    surface.blit(_bloom_surf, (0, 0))

    # ── Core lines (all branches, 3 px warm white) ────────────────────────────
    for path in paths:
        pts = [_cell_px(*cell) for cell in path]
        for i in range(len(pts) - 1):
            pygame.draw.line(surface, (255, 248, 220), pts[i], pts[i + 1], 3)

    # ── Frontier dots (equal probability → equal visual weight) ───────────────
    dot_col = (139, 92, 246) if result.reached_exit else (0, 229, 255)
    dot_r   = max(2, int(cell_size * 0.25))
    for cell in result.frontier:
        pygame.draw.circle(surface, dot_col, _cell_px(*cell), dot_r)
