"""
main.py — game loop, event handling, state machine.
Run with:  python main.py   (from inside quantum_maze/)
"""

import sys
import math
import pygame
from enum import Enum, auto

import maze as maze_mod
import lighting
import effects as fx
import ui
from player import Player
from ray_solver import RaySolver, SolveResult, draw_ray
from settings import (
    SW, SH, GAME_H, HUD_H, FPS, WINDOW_TITLE,
    BG, WALL_C, FLOOR_C, EXIT_C,
    MAZE_X0, MAZE_Y0, MAZE_W, MAZE_H, ROWS, COLS, CELL,
    N, W,
    EXIT_CELL, START_CELL,
    EXIT_BASE_RADIUS, EXIT_PULSE_RANGE, EXIT_PULSE_FREQ,
    AMBIENT_RADIUS,
    FLASH_DURATION, JUMP_COOLDOWN,
    DEFAULT_SEED,
)


class State(Enum):
    PLAYING    = auto()
    COLLAPSING = auto()
    JUMPING    = auto()
    WIN        = auto()


# ── Maze surface builder ──────────────────────────────────────────────────────
def _build_maze_surf(mz) -> pygame.Surface:
    surf = pygame.Surface((MAZE_W + 2, MAZE_H + 2))
    surf.fill(FLOOR_C)
    for r in range(ROWS):
        for c in range(COLS):
            ox, oy = c * CELL, r * CELL
            if not maze_mod.is_open(mz, r, c, N):
                pygame.draw.line(surf, WALL_C, (ox, oy), (ox + CELL, oy), 2)
            if not maze_mod.is_open(mz, r, c, W):
                pygame.draw.line(surf, WALL_C, (ox, oy), (ox, oy + CELL), 2)
    # South + east borders
    for c in range(COLS):
        oy = ROWS * CELL
        pygame.draw.line(surf, WALL_C, (c*CELL, oy), (c*CELL + CELL, oy), 2)
    for r in range(ROWS):
        ox = COLS * CELL
        pygame.draw.line(surf, WALL_C, (ox, r*CELL), (ox, r*CELL + CELL), 2)
    return surf


# ── Exit portal drawing ───────────────────────────────────────────────────────
def _draw_exit(screen, t: float, glow_surf):
    r, c  = EXIT_CELL
    cx    = MAZE_X0 + c * CELL + CELL // 2
    cy    = MAZE_Y0 + r * CELL + CELL // 2
    rad   = EXIT_BASE_RADIUS + int(EXIT_PULSE_RANGE * math.sin(2 * math.pi * EXIT_PULSE_FREQ * t))
    # Soft glow
    gr = rad * 3
    glow_surf.fill((0, 0, 0, 0))
    pygame.draw.circle(glow_surf, (*EXIT_C, 35), (gr, gr), gr)
    screen.blit(glow_surf, (cx - gr, cy - gr))
    # Portal circles
    pygame.draw.circle(screen, EXIT_C,           (cx, cy), rad)
    pygame.draw.circle(screen, (210, 175, 255),  (cx, cy), max(2, rad - 4))


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    pygame.init()
    screen = pygame.display.set_mode((SW, SH))
    pygame.display.set_caption(WINDOW_TITLE)
    clock  = pygame.time.Clock()

    # Pre-allocated surfaces
    fog_surf     = pygame.Surface((SW, GAME_H), pygame.SRCALPHA)
    ray_surf     = pygame.Surface((SW, GAME_H), pygame.SRCALPHA)
    ambient_surf = lighting.make_ambient(AMBIENT_RADIUS)
    gr           = EXIT_BASE_RADIUS * 3
    exit_glow    = pygame.Surface((gr * 2, gr * 2), pygame.SRCALPHA)

    # Game objects
    mz         = maze_mod.generate(DEFAULT_SEED)
    maze_surf  = _build_maze_surf(mz)
    solver     = RaySolver(mz)
    player     = Player()
    particles  = fx.ParticleSystem()
    flash      = fx.ScreenFlash()
    scanlines  = fx.ScanlineStatic()

    # HUD widgets — vertically centred inside HUD strip
    hud_cy = GAME_H + HUD_H // 2
    slider  = ui.Slider(x=24, y=hud_cy, width=260)
    btn     = ui.QuantumJumpButton(x=SW - 244, y=hud_cy - 20, width=236, height=40)

    # State
    state          = State.PLAYING
    collapse_count = 0
    elapsed        = 0.0
    next_seed      = DEFAULT_SEED + 1
    collapse_timer = 0.0
    lit_cells: list    = []
    solve_result: SolveResult | None = None

    while True:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)

        # ── Mouse ray angle (for fog-of-war only) ────────────────────────────
        mx, my    = pygame.mouse.get_pos()
        angle_rad = math.atan2(my - player.py, mx - player.px)

        # ── BFS ray solve (every frame) ───────────────────────────────────────
        solve_result = solver.solve(
            (player.row, player.col), EXIT_CELL, slider.depth)

        # ── Fog cast ray (for ambient reveal, unchanged) ──────────────────────
        if state in (State.PLAYING, State.COLLAPSING, State.JUMPING):
            lit_cells, _ = lighting.cast_ray(
                (player.px, player.py), angle_rad, mz)

        # ── Events ────────────────────────────────────────────────────────────
        can_jump = (state == State.PLAYING and
                    player.jump_cooldown <= 0.0 and
                    not player.is_moving() and
                    not player.is_jumping)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                if event.key == pygame.K_r:
                    # Full restart
                    mz = maze_mod.generate(DEFAULT_SEED)
                    maze_surf = _build_maze_surf(mz)
                    solver    = RaySolver(mz)
                    player    = Player()
                    particles.clear()
                    state          = State.PLAYING
                    collapse_count = 0
                    elapsed        = 0.0
                    next_seed      = DEFAULT_SEED + 1

            slider.handle_event(event)
            btn.handle_event(event, can_jump)

        # ── Slider risk accumulation ──────────────────────────────────────────
        slider.update(dt)

        # ── Trigger collapse (risk-based) ─────────────────────────────────────
        def _do_collapse():
            nonlocal mz, maze_surf, solver, next_seed, collapse_count
            nonlocal state, collapse_timer
            mz = maze_mod.generate(next_seed)
            maze_surf = _build_maze_surf(mz)
            solver    = RaySolver(mz)
            next_seed += 1
            collapse_count += 1
            player.snap_to_cell(player.row, player.col)
            flash.trigger()
            scanlines.trigger()
            state          = State.COLLAPSING
            collapse_timer = FLASH_DURATION

        if slider.force_collapse and state == State.PLAYING:
            _do_collapse()

        # ── Trigger quantum jump ──────────────────────────────────────────────
        if btn.pressed and can_jump and solve_result and solve_result.path:
            player.start_jump(solve_result.path[-1])
            state = State.JUMPING

        # ── Update ────────────────────────────────────────────────────────────
        if state != State.WIN:
            elapsed += dt

        player.update(dt)
        particles.update(dt)
        flash.update(dt)
        scanlines.update(dt)

        # Held-key movement (smooth continuous movement while key held)
        if state == State.PLAYING and not player.is_moving() and not player.is_jumping:
            keys = pygame.key.get_pressed()
            if   keys[pygame.K_w] or keys[pygame.K_UP]:    player.try_move(mz, -1,  0)
            elif keys[pygame.K_s] or keys[pygame.K_DOWN]:  player.try_move(mz,  1,  0)
            elif keys[pygame.K_a] or keys[pygame.K_LEFT]:  player.try_move(mz,  0, -1)
            elif keys[pygame.K_d] or keys[pygame.K_RIGHT]: player.try_move(mz,  0,  1)

        # State transitions
        if state == State.COLLAPSING:
            collapse_timer -= dt
            if collapse_timer <= 0:
                state = State.PLAYING

        if state == State.JUMPING and not player.is_jumping:
            particles.burst(player.px, player.py)
            state = State.PLAYING
            if player.at_exit():
                state = State.WIN

        if state == State.PLAYING and player.at_exit() and not player.is_moving():
            state = State.WIN

        # ── Render ────────────────────────────────────────────────────────────
        t_now = pygame.time.get_ticks() / 1000.0

        screen.fill(BG)

        # Maze + exit portal
        screen.blit(maze_surf, (MAZE_X0, MAZE_Y0))
        _draw_exit(screen, t_now, exit_glow)

        # Particles (below fog)
        particles.draw(screen)

        # Fog (ambient hole + geometric fog reveal)
        lighting.render(screen, fog_surf, ray_surf, ambient_surf,
                        (player.px, player.py), angle_rad, mz, lit_cells)

        # BFS ray — on top of fog, below player
        if solve_result:
            draw_ray(screen, solve_result, CELL)

        # Player — on top of everything
        player.draw(screen)

        # Screen effects (flash, scanlines)
        flash.draw(screen)
        scanlines.draw(screen)

        # HUD
        ui.draw_hud(screen, collapse_count, elapsed)
        cooldown_frac = 1.0 - player.jump_cooldown / JUMP_COOLDOWN
        slider.draw(screen)
        btn.draw(screen, cooldown_frac, can_jump)

        # Win overlay
        if state == State.WIN:
            ui.draw_win_overlay(screen, collapse_count, elapsed)

        pygame.display.flip()


if __name__ == '__main__':
    main()
