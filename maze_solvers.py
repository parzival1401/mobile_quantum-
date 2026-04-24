"""
maze_solvers.py  —  Random Maze + 5 Solver Algorithm Animations
================================================================
Quantum Exhibition  |  Pathfinding Visualization

Algorithms
----------
1. BFS    Breadth-First Search    — uniform frontier, always optimal
2. DFS    Depth-First Search      — deep backtracking, not optimal
3. A*     A* Search               — heuristic + distance, optimal & fast
4. Greedy Greedy Best-First       — heuristic only, fastest, non-optimal
5. BiDir  Bidirectional BFS       — two frontiers meeting in the middle

Controls
--------
  SPACE   — skip animation to result / advance to next algorithm
  R       — regenerate maze and restart from algorithm 1
  ESC     — quit
"""

import pygame
import sys
import random
from collections import deque
import heapq

pygame.init()

# ─── Screen ───────────────────────────────────────────────────────────────────
SW, SH = 880, 700
FPS    = 60
screen = pygame.display.set_mode((SW, SH))
pygame.display.set_caption("Maze Solvers  |  Pathfinding Visualization")
clk    = pygame.time.Clock()

# ─── Colours ──────────────────────────────────────────────────────────────────
BG       = (8,   6,  20)
PANEL_BG = (12,  10, 28)
WALL_C   = (55,  75, 145)
FLOOR_C  = (18,  15, 38)
WHITE    = (240, 240, 255)
DIM      = (70,  65, 110)
SUBDIM   = (40,  38, 65)
START_C  = (60,  220, 120)
GOAL_C   = (220,  60, 120)
PATH_C   = (255, 220,  60)

# Per-algorithm: (short, long, fg_colour, visited_blend, description lines)
ALGORITHMS = [
    ("BFS",    "Breadth-First Search",
     (60,  180, 255), (28,  50,  90),
     ["Explores all reachable cells", "layer by layer (uniform cost).",
      "Guarantees the shortest path."]),
    ("DFS",    "Depth-First Search",
     (255, 120,  50), (60,  28,  14),
     ["Dives as deep as possible,", "then backtracks.",
      "Fast but path is non-optimal."]),
    ("A*",     "A* Search",
     (200,  80, 255), (48,  20,  65),
     ["Combines path cost + Manhattan", "distance heuristic.",
      "Optimal and highly efficient."]),
    ("Greedy", "Greedy Best-First",
     (60,  230, 170), (15,  58,  44),
     ["Uses only the heuristic,", "ignores path cost.",
      "Fastest, but non-optimal."]),
    ("BiDir",  "Bidirectional BFS",
     (255,  80, 160), (65,  20,  42),
     ["Two BFS frontiers expand", "from start and goal.",
      "They meet in the middle."]),
]
N_ALGS = len(ALGORITHMS)

BIDIR_FG_B  = (80, 255, 110)   # second frontier colour (BiDir)
BIDIR_VIS_B = (15,  58,  22)   # second visited colour  (BiDir)

# ─── Fonts ────────────────────────────────────────────────────────────────────
def _f(sz, bold=True):
    for name in ("Segoe UI", "Arial", "DejaVu Sans"):
        try:
            return pygame.font.SysFont(name, sz, bold=bold)
        except Exception:
            pass
    return pygame.font.Font(None, sz)

F_BIG  = _f(22)
F_MED  = _f(16)
F_SM   = _f(13)
F_XSM  = _f(11, bold=False)

# ─── Layout ───────────────────────────────────────────────────────────────────
ROWS, COLS = 25, 25
CELL       = 16
WALL_T     = 2
TOP_H      = 62
BOT_H      = 50
MX0        = 20
MY0        = TOP_H
MAZE_PX    = COLS * CELL     # 400
MAZE_PY    = ROWS * CELL     # 400
RP_X       = MX0 + MAZE_PX + 18    # right panel left
RP_W       = SW - RP_X - 8         # right panel width

START = (0, 0)
GOAL  = (ROWS - 1, COLS - 1)

STEPS_PER_FRAME = 6    # algorithm steps per frame
RESULT_PAUSE_MS = 3000  # ms to display solution before auto-advancing

# ─── Direction helpers ────────────────────────────────────────────────────────
DIRS4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]

def _inb(r, c):
    return 0 <= r < ROWS and 0 <= c < COLS

# ─── Maze generation: iterative DFS backtracker ───────────────────────────────
def generate_maze():
    """Returns passages[r][c] = set of (dr, dc) open directions."""
    passages = [[set() for _ in range(COLS)] for _ in range(ROWS)]
    visited  = [[False] * COLS for _ in range(ROWS)]
    stack    = [(0, 0)]
    visited[0][0] = True

    while stack:
        r, c = stack[-1]
        nbrs = [(r+dr, c+dc, dr, dc)
                for dr, dc in DIRS4
                if _inb(r+dr, c+dc) and not visited[r+dr][c+dc]]
        if nbrs:
            nr, nc, dr, dc = random.choice(nbrs)
            passages[r][c].add((dr, dc))
            passages[nr][nc].add((-dr, -dc))
            visited[nr][nc] = True
            stack.append((nr, nc))
        else:
            stack.pop()

    return passages

# ─── Path reconstruction ──────────────────────────────────────────────────────
def _recon(came_from, node):
    path, cur = [], node
    while cur is not None:
        path.append(cur)
        cur = came_from.get(cur)
    path.reverse()
    return path

# ─── State dict helper ────────────────────────────────────────────────────────
def _s(visited, frontier, path, done, steps, **kw):
    return dict(visited=visited, frontier=frontier,
                path=path, done=done, steps=steps, **kw)

# ─────────────────────────────────────────────────────────────────────────────
# Algorithm 1 — BFS
# ─────────────────────────────────────────────────────────────────────────────
def bfs_gen(passages):
    q         = deque([START])
    came_from = {START: None}
    visited   = set()
    steps     = 0

    while q:
        r, c = q.popleft()
        if (r, c) in visited:
            continue
        visited.add((r, c))
        steps += 1

        if (r, c) == GOAL:
            yield _s(frozenset(visited), frozenset(q),
                     _recon(came_from, GOAL), True, steps)
            return

        for dr, dc in passages[r][c]:
            nb = (r+dr, c+dc)
            if nb not in came_from:
                came_from[nb] = (r, c)
                q.append(nb)

        yield _s(frozenset(visited), frozenset(q), None, False, steps)

    yield _s(frozenset(visited), frozenset(), [], True, steps)

# ─────────────────────────────────────────────────────────────────────────────
# Algorithm 2 — DFS
# ─────────────────────────────────────────────────────────────────────────────
def dfs_gen(passages):
    stack     = [START]
    came_from = {START: None}
    visited   = set()
    steps     = 0

    while stack:
        r, c = stack.pop()
        if (r, c) in visited:
            continue
        visited.add((r, c))
        steps += 1

        if (r, c) == GOAL:
            yield _s(frozenset(visited), frozenset(stack),
                     _recon(came_from, GOAL), True, steps)
            return

        for dr, dc in passages[r][c]:
            nb = (r+dr, c+dc)
            if nb not in visited:
                if nb not in came_from:
                    came_from[nb] = (r, c)
                stack.append(nb)

        yield _s(frozenset(visited), frozenset(stack), None, False, steps)

    yield _s(frozenset(visited), frozenset(), [], True, steps)

# ─────────────────────────────────────────────────────────────────────────────
# Algorithm 3 — A*
# ─────────────────────────────────────────────────────────────────────────────
def _h(r, c):
    return abs(r - GOAL[0]) + abs(c - GOAL[1])

def astar_gen(passages):
    open_heap = [(_h(*START), 0, START)]
    came_from = {START: None}
    g_cost    = {START: 0}
    closed    = set()
    steps     = 0

    while open_heap:
        _, g, (r, c) = heapq.heappop(open_heap)
        if (r, c) in closed:
            continue
        closed.add((r, c))
        steps += 1

        if (r, c) == GOAL:
            yield _s(frozenset(closed),
                     frozenset(cell for _, _, cell in open_heap),
                     _recon(came_from, GOAL), True, steps)
            return

        for dr, dc in passages[r][c]:
            nb = (r+dr, c+dc)
            if nb in closed:
                continue
            ng = g + 1
            if ng < g_cost.get(nb, 10**9):
                g_cost[nb]    = ng
                came_from[nb] = (r, c)
                heapq.heappush(open_heap, (ng + _h(*nb), ng, nb))

        yield _s(frozenset(closed),
                 frozenset(cell for _, _, cell in open_heap),
                 None, False, steps)

    yield _s(frozenset(closed), frozenset(), [], True, steps)

# ─────────────────────────────────────────────────────────────────────────────
# Algorithm 4 — Greedy Best-First Search
# ─────────────────────────────────────────────────────────────────────────────
def greedy_gen(passages):
    open_heap = [(_h(*START), START)]
    came_from = {START: None}
    visited   = set()
    steps     = 0

    while open_heap:
        _, (r, c) = heapq.heappop(open_heap)
        if (r, c) in visited:
            continue
        visited.add((r, c))
        steps += 1

        if (r, c) == GOAL:
            yield _s(frozenset(visited),
                     frozenset(cell for _, cell in open_heap),
                     _recon(came_from, GOAL), True, steps)
            return

        for dr, dc in passages[r][c]:
            nb = (r+dr, c+dc)
            if nb not in visited and nb not in came_from:
                came_from[nb] = (r, c)
                heapq.heappush(open_heap, (_h(*nb), nb))

        yield _s(frozenset(visited),
                 frozenset(cell for _, cell in open_heap),
                 None, False, steps)

    yield _s(frozenset(visited), frozenset(), [], True, steps)

# ─────────────────────────────────────────────────────────────────────────────
# Algorithm 5 — Bidirectional BFS
# ─────────────────────────────────────────────────────────────────────────────
def bidir_bfs_gen(passages):
    front_a = deque([START])
    front_b = deque([GOAL])
    came_a  = {START: None}
    came_b  = {GOAL:  None}
    vis_a   = set()
    vis_b   = set()
    steps   = 0
    meeting = None

    def _step(q, came, vis):
        while q:
            r, c = q.popleft()
            if (r, c) in vis:
                continue
            vis.add((r, c))
            for dr, dc in passages[r][c]:
                nb = (r+dr, c+dc)
                if nb not in came:
                    came[nb] = (r, c)
                    q.append(nb)
            return (r, c)
        return None

    while front_a or front_b:
        ca = _step(front_a, came_a, vis_a)
        if ca and ca in vis_b:
            meeting = ca
            break

        cb = _step(front_b, came_b, vis_b)
        if cb and cb in vis_a:
            meeting = cb
            break

        steps += 1
        yield _s(frozenset(vis_a), frozenset(front_a), None, False, steps,
                 vis_b=frozenset(vis_b), front_b=frozenset(front_b))

    if meeting is None:
        common  = vis_a & vis_b
        meeting = next(iter(common)) if common else GOAL

    path_a = _recon(came_a, meeting)
    path_b = _recon(came_b, meeting)[::-1]   # [meeting,…,GOAL] after reverse
    path   = path_a + path_b[1:]             # skip duplicate meeting point

    yield _s(frozenset(vis_a), frozenset(), path, True, steps,
             vis_b=frozenset(vis_b), front_b=frozenset())

# ─── Wire generators into ALGORITHMS ─────────────────────────────────────────
_GEN_FNS = [bfs_gen, dfs_gen, astar_gen, greedy_gen, bidir_bfs_gen]

# ─── Pre-rendered maze surface ────────────────────────────────────────────────
def build_maze_surf(passages):
    """Walls drawn on transparent surface — blitted on top of cell colours."""
    surf = pygame.Surface((MAZE_PX + WALL_T, MAZE_PY + WALL_T), pygame.SRCALPHA)
    for r in range(ROWS):
        for c in range(COLS):
            ox, oy = c * CELL, r * CELL
            if (-1, 0) not in passages[r][c]:   # north wall
                pygame.draw.line(surf, WALL_C, (ox, oy), (ox + CELL, oy), WALL_T)
            if (0, -1) not in passages[r][c]:   # west wall
                pygame.draw.line(surf, WALL_C, (ox, oy), (ox, oy + CELL), WALL_T)
    # south border
    for c in range(COLS):
        ox, oy = c * CELL, ROWS * CELL
        if (1, 0) not in passages[ROWS-1][c]:
            pygame.draw.line(surf, WALL_C, (ox, oy), (ox + CELL, oy), WALL_T)
    # east border
    for r in range(ROWS):
        ox, oy = COLS * CELL, r * CELL
        if (0, 1) not in passages[r][COLS-1]:
            pygame.draw.line(surf, WALL_C, (ox, oy), (ox, oy + CELL), WALL_T)
    return surf

# ─── Rendering helpers ────────────────────────────────────────────────────────
def draw_floor():
    pygame.draw.rect(screen, FLOOR_C, (MX0, MY0, MAZE_PX, MAZE_PY))


def draw_cells(state, alg_idx):
    visited  = state['visited']
    frontier = state['frontier']
    path     = state.get('path')
    vis_b    = state.get('vis_b', frozenset())
    front_b  = state.get('front_b', frozenset())

    _, _, fg, vis_col, _ = ALGORITHMS[alg_idx]
    path_set = frozenset(path) if path else frozenset()

    for r in range(ROWS):
        for c in range(COLS):
            cell = (r, c)
            ox   = MX0 + c * CELL + 1
            oy   = MY0 + r * CELL + 1
            w    = CELL - 1

            if cell in path_set:
                col = PATH_C
            elif cell in frontier:
                col = fg
            elif cell in front_b:
                col = BIDIR_FG_B
            elif cell in visited:
                col = vis_col
            elif cell in vis_b:
                col = BIDIR_VIS_B
            else:
                col = FLOOR_C

            pygame.draw.rect(screen, col, (ox, oy, w, w))


def draw_start_goal():
    for (r, c), col in ((START, START_C), (GOAL, GOAL_C)):
        ox = MX0 + c * CELL + 3
        oy = MY0 + r * CELL + 3
        s  = CELL - 6
        pygame.draw.rect(screen, col, (ox, oy, s, s), border_radius=2)
    # Labels
    for (r, c), lbl, col in ((START, "S", START_C), (GOAL, "G", GOAL_C)):
        t  = F_XSM.render(lbl, True, BG)
        ox = MX0 + c * CELL + CELL // 2 - t.get_width() // 2
        oy = MY0 + r * CELL + CELL // 2 - t.get_height() // 2
        screen.blit(t, (ox, oy))


def _legend_row(y, colour, label):
    pygame.draw.rect(screen, colour, (RP_X + 8, y + 2, 12, 12), border_radius=2)
    screen.blit(F_XSM.render(label, True, DIM), (RP_X + 26, y))


def draw_info_panel(alg_idx, state, game_state, completed):
    pygame.draw.rect(screen, PANEL_BG, (RP_X - 6, MY0, RP_W + 6, MAZE_PY))
    pygame.draw.line(screen, (40, 32, 72), (RP_X - 6, MY0), (RP_X - 6, MY0 + MAZE_PY), 1)

    y = MY0 + 10

    # ── Algorithm list ────────────────────────────────────────────────────────
    hdr = F_XSM.render("ALGORITHMS", True, (55, 50, 85))
    screen.blit(hdr, (RP_X + 8, y))
    y += 16

    for i, (short, long, fg, _, _) in enumerate(ALGORITHMS):
        if i < len(completed):
            sym = "✓"
            col = (60, 160, 60)
        elif i == alg_idx:
            sym = "▶"
            col = fg
        else:
            sym = "○"
            col = SUBDIM

        sx = RP_X + 8
        screen.blit(F_SM.render(sym, True, col), (sx, y))
        name_col = fg if i == alg_idx else (col if i < len(completed) else DIM)
        screen.blit(F_SM.render(f"  {short}  {long}", True, name_col), (sx + 10, y))
        y += 17

    y += 6
    pygame.draw.line(screen, (40, 32, 72), (RP_X + 4, y), (SW - 8, y), 1)
    y += 8

    # ── Current algorithm detail ──────────────────────────────────────────────
    if alg_idx < N_ALGS:
        short, long, fg, _, desc_lines = ALGORITHMS[alg_idx]
        t = F_BIG.render(short, True, fg)
        screen.blit(t, (RP_X + 8, y))
        y += t.get_height() + 2

        lt = F_XSM.render(long, True, DIM)
        screen.blit(lt, (RP_X + 8, y))
        y += lt.get_height() + 8

        for line in desc_lines:
            dl = F_XSM.render(line, True, (140, 130, 180))
            screen.blit(dl, (RP_X + 8, y))
            y += dl.get_height() + 2

    y += 8
    pygame.draw.line(screen, (40, 32, 72), (RP_X + 4, y), (SW - 8, y), 1)
    y += 8

    # ── Stats ─────────────────────────────────────────────────────────────────
    if state:
        steps    = state.get('steps', 0)
        path     = state.get('path')
        explored = len(state['visited']) + len(state.get('vis_b', frozenset()))

        screen.blit(F_XSM.render(f"Cells explored : {explored}", True, DIM), (RP_X + 8, y))
        y += 15
        screen.blit(F_XSM.render(f"Steps taken    : {steps}", True, DIM), (RP_X + 8, y))
        y += 15
        if path:
            screen.blit(F_XSM.render(f"Path length    : {len(path)}", True, PATH_C), (RP_X + 8, y))
        else:
            screen.blit(F_XSM.render("Path length    : —", True, DIM), (RP_X + 8, y))
        y += 15

        if game_state == 'paused' and path:
            is_bfs = alg_idx == 0
            is_bidir = alg_idx == 4
            note = ("optimal" if alg_idx in (0, 2) else
                    "may not be optimal" if alg_idx in (1, 3, 4) else "")
            if note:
                nc = (80, 200, 80) if "optimal" == note else (200, 160, 60)
                screen.blit(F_XSM.render(f"→ {note}", True, nc), (RP_X + 8, y))
                y += 15

    y += 4
    pygame.draw.line(screen, (40, 32, 72), (RP_X + 4, y), (SW - 8, y), 1)
    y += 8

    # ── Legend ────────────────────────────────────────────────────────────────
    screen.blit(F_XSM.render("LEGEND", True, (55, 50, 85)), (RP_X + 8, y))
    y += 15

    if alg_idx < N_ALGS:
        _, _, fg, _, _ = ALGORITHMS[alg_idx]
        _legend_row(y, START_C, "Start");        y += 15
        _legend_row(y, GOAL_C,  "Goal");         y += 15
        _legend_row(y, fg,      "Frontier A");   y += 15
        if alg_idx == 4:
            _legend_row(y, BIDIR_FG_B, "Frontier B");  y += 15
        _legend_row(y, PATH_C,  "Solution path"); y += 15

    # ── Controls ──────────────────────────────────────────────────────────────
    ctrl_y = MY0 + MAZE_PY - 44
    pygame.draw.line(screen, (40, 32, 72), (RP_X + 4, ctrl_y), (SW - 8, ctrl_y), 1)
    ctrl_y += 6
    for txt, col in (("SPACE  skip / next algorithm", DIM),
                     ("R       regenerate maze",       DIM)):
        screen.blit(F_XSM.render(txt, True, col), (RP_X + 8, ctrl_y))
        ctrl_y += 14


def draw_top(alg_idx, game_state):
    pygame.draw.rect(screen, PANEL_BG, (0, 0, SW, TOP_H))
    pygame.draw.line(screen, (40, 32, 72), (0, TOP_H - 1), (SW, TOP_H - 1), 1)

    title = F_BIG.render("✦  MAZE SOLVERS  ✦", True, (210, 70, 255))
    screen.blit(title, (SW // 2 - title.get_width() // 2, 8))

    if game_state == 'done':
        msg, col = "All algorithms complete — press R to regenerate", (80, 200, 80)
    elif game_state == 'paused':
        msg, col = "Solution found — press SPACE for next algorithm", PATH_C
    elif alg_idx < N_ALGS:
        _, long, fg, _, _ = ALGORITHMS[alg_idx]
        msg, col = f"Running  {long}  ({alg_idx + 1} / {N_ALGS})", fg
    else:
        msg, col = "", WHITE

    t = F_XSM.render(msg, True, col)
    screen.blit(t, (SW // 2 - t.get_width() // 2, TOP_H - 18))


def draw_bottom():
    y0 = MY0 + MAZE_PY
    pygame.draw.rect(screen, PANEL_BG, (0, y0, SW, BOT_H))
    pygame.draw.line(screen, (40, 32, 72), (0, y0), (SW, y0), 1)
    lines = [
        ("■ frontier = cells about to be explored   ■ visited = already explored   ■ yellow = final path", DIM),
        ("Algorithms differ in HOW they prioritise which cell to explore next — that changes speed & optimality.", (80, 70, 120)),
    ]
    for i, (txt, col) in enumerate(lines):
        t = F_XSM.render(txt, True, col)
        screen.blit(t, (SW // 2 - t.get_width() // 2, y0 + 8 + i * 16))


# ─── Main loop ───────────────────────────────────────────────────────────────
def main():
    passages   = generate_maze()
    maze_surf  = build_maze_surf(passages)

    alg_idx     = 0
    cur_gen     = _GEN_FNS[0](passages)
    cur_state   = None
    game_state  = 'solving'   # 'solving' | 'paused' | 'done'
    pause_start = 0
    completed   = []          # list of final states per algorithm

    while True:
        clk.tick(FPS)

        # ── Events ────────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()

                elif event.key == pygame.K_r:
                    passages    = generate_maze()
                    maze_surf   = build_maze_surf(passages)
                    alg_idx     = 0
                    completed   = []
                    cur_gen     = _GEN_FNS[0](passages)
                    cur_state   = None
                    game_state  = 'solving'

                elif event.key == pygame.K_SPACE:
                    if game_state == 'solving':
                        # Drain generator — jump to final state
                        for s in cur_gen:
                            cur_state = s
                            if s['done']:
                                break
                        if cur_state is None:
                            cur_state = _s(frozenset(), frozenset(), [], True, 0)
                        if not completed or completed[-1] is not cur_state:
                            completed.append(cur_state)
                        game_state  = 'paused'
                        pause_start = pygame.time.get_ticks()

                    elif game_state == 'paused':
                        alg_idx += 1
                        if alg_idx >= N_ALGS:
                            game_state = 'done'
                        else:
                            cur_gen    = _GEN_FNS[alg_idx](passages)
                            cur_state  = None
                            game_state = 'solving'

        # ── Update ────────────────────────────────────────────────────────────
        if game_state == 'solving':
            for _ in range(STEPS_PER_FRAME):
                try:
                    s = next(cur_gen)
                    cur_state = s
                    if s['done']:
                        completed.append(s)
                        game_state  = 'paused'
                        pause_start = pygame.time.get_ticks()
                        break
                except StopIteration:
                    game_state  = 'paused'
                    pause_start = pygame.time.get_ticks()
                    break

        elif game_state == 'paused':
            if pygame.time.get_ticks() - pause_start >= RESULT_PAUSE_MS:
                alg_idx += 1
                if alg_idx >= N_ALGS:
                    game_state = 'done'
                else:
                    cur_gen    = _GEN_FNS[alg_idx](passages)
                    cur_state  = None
                    game_state = 'solving'

        # ── Render ────────────────────────────────────────────────────────────
        screen.fill(BG)

        if cur_state:
            draw_cells(cur_state, alg_idx if alg_idx < N_ALGS else N_ALGS - 1)
        else:
            draw_floor()

        screen.blit(maze_surf, (MX0, MY0))
        draw_start_goal()
        draw_info_panel(alg_idx if alg_idx < N_ALGS else N_ALGS,
                        cur_state, game_state, completed)
        draw_top(alg_idx, game_state)
        draw_bottom()

        pygame.display.flip()


if __name__ == "__main__":
    main()
