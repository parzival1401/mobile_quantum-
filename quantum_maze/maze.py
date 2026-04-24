"""
Wilson's loop-erased random walk maze generation.

Maze stored as np.ndarray shape (ROWS, COLS), dtype int32.
Each cell is a bitmask of OPEN walls: N=1, S=2, E=4, W=8.
"""

import random
import numpy as np
from settings import N, S, E, W, ROWS, COLS, EXIT_CELL


def generate(seed: int) -> np.ndarray:
    rng = random.Random(seed)
    maze = np.zeros((ROWS, COLS), dtype=np.int32)

    in_maze = {EXIT_CELL}
    not_in  = {(r, c) for r in range(ROWS) for c in range(COLS)} - in_maze

    def _neighbors(r, c):
        out = []
        if r > 0:        out.append((r-1, c))
        if r < ROWS - 1: out.append((r+1, c))
        if c > 0:        out.append((r, c-1))
        if c < COLS - 1: out.append((r, c+1))
        return out

    def _carve(r0, c0, r1, c1):
        dr, dc = r1 - r0, c1 - c0
        if   dr == -1: maze[r0, c0] |= N; maze[r1, c1] |= S
        elif dr ==  1: maze[r0, c0] |= S; maze[r1, c1] |= N
        elif dc ==  1: maze[r0, c0] |= E; maze[r1, c1] |= W
        elif dc == -1: maze[r0, c0] |= W; maze[r1, c1] |= E

    while not_in:
        start   = rng.choice(list(not_in))
        path    = [start]
        pos_map = {start: 0}      # cell → index in path (for loop erasure)
        current = start

        while current not in in_maze:
            nbrs = _neighbors(*current)
            nxt  = rng.choice(nbrs)

            if nxt in in_maze:
                path.append(nxt)
                break
            elif nxt in pos_map:
                # Erase the loop back to nxt
                idx = pos_map[nxt]
                for erased in path[idx + 1:]:
                    del pos_map[erased]
                path    = path[:idx + 1]
                current = path[-1]
            else:
                pos_map[nxt] = len(path)
                path.append(nxt)
                current = nxt

        # Carve the walk into the maze
        for i in range(len(path) - 1):
            r0, c0 = path[i]
            r1, c1 = path[i + 1]
            _carve(r0, c0, r1, c1)
            in_maze.add((r0, c0))
            not_in.discard((r0, c0))

    return maze


def is_open(maze: np.ndarray, r: int, c: int, direction: int) -> bool:
    return bool(maze[r, c] & direction)


def get_neighbors(maze: np.ndarray, r: int, c: int) -> list:
    out = []
    if r > 0           and is_open(maze, r, c, N): out.append((r-1, c))
    if r < ROWS - 1    and is_open(maze, r, c, S): out.append((r+1, c))
    if c < COLS - 1    and is_open(maze, r, c, E): out.append((r, c+1))
    if c > 0           and is_open(maze, r, c, W): out.append((r, c-1))
    return out
