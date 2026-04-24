"""Particle burst, screen flash, scanline static, tween helper."""

import math
import random
import pygame
from settings import (
    SW, SH,
    FLASH_C, FLASH_DURATION,
    SCANLINE_DURATION,
    PARTICLE_C_START, PARTICLE_C_END,
    PARTICLE_LIFETIME, PARTICLE_SPEED_MIN, PARTICLE_SPEED_MAX,
    PARTICLE_RADIUS, N_PARTICLES,
)

# ── Tween helper ──────────────────────────────────────────────────────────────
try:
    import pytweening as _pt
    ease_in_out_quad = _pt.easeInOutQuad
except ImportError:
    def ease_in_out_quad(t: float) -> float:
        """Fallback cubic ease-in-out."""
        t *= 2
        if t < 1:
            return 0.5 * t * t
        t -= 1
        return -0.5 * (t * (t - 2) - 1)


# ── Particles ─────────────────────────────────────────────────────────────────
class _Particle:
    __slots__ = ('x', 'y', 'vx', 'vy', 'age')

    def __init__(self, px: float, py: float):
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(PARTICLE_SPEED_MIN, PARTICLE_SPEED_MAX)
        self.x   = px
        self.y   = py
        self.vx  = math.cos(angle) * speed
        self.vy  = math.sin(angle) * speed
        self.age = 0.0

    def update(self, dt: float):
        self.vx *= 0.93
        self.vy *= 0.93
        self.x  += self.vx * dt
        self.y  += self.vy * dt
        self.age += dt

    @property
    def alive(self) -> bool:
        return self.age < PARTICLE_LIFETIME

    def _color(self):
        t  = self.age / PARTICLE_LIFETIME
        r  = int(PARTICLE_C_START[0] + (PARTICLE_C_END[0] - PARTICLE_C_START[0]) * t)
        g  = int(PARTICLE_C_START[1] + (PARTICLE_C_END[1] - PARTICLE_C_START[1]) * t)
        b  = int(PARTICLE_C_START[2] + (PARTICLE_C_END[2] - PARTICLE_C_START[2]) * t)
        a  = int(255 * (1.0 - t))
        return r, g, b, a

    def draw(self, surf, temp):
        r, g, b, a = self._color()
        d = PARTICLE_RADIUS * 2 + 2
        temp.fill((0, 0, 0, 0))
        pygame.draw.circle(temp, (r, g, b, a),
                           (PARTICLE_RADIUS + 1, PARTICLE_RADIUS + 1),
                           PARTICLE_RADIUS)
        surf.blit(temp, (int(self.x) - PARTICLE_RADIUS - 1,
                         int(self.y) - PARTICLE_RADIUS - 1))


class ParticleSystem:
    def __init__(self):
        self._particles: list[_Particle] = []
        d = PARTICLE_RADIUS * 2 + 2
        self._temp = pygame.Surface((d, d), pygame.SRCALPHA)

    def burst(self, px: float, py: float, n: int = N_PARTICLES):
        for _ in range(n):
            self._particles.append(_Particle(px, py))

    def update(self, dt: float):
        self._particles = [p for p in self._particles if p.alive]
        for p in self._particles:
            p.update(dt)

    def draw(self, surface):
        for p in self._particles:
            p.draw(surface, self._temp)

    def clear(self):
        self._particles.clear()


# ── Screen flash ──────────────────────────────────────────────────────────────
class ScreenFlash:
    def __init__(self):
        self._alpha = 0.0
        self._surf  = pygame.Surface((SW, SH), pygame.SRCALPHA)

    def trigger(self):
        self._alpha = 180.0

    def update(self, dt: float):
        if self._alpha > 0:
            self._alpha = max(0.0, self._alpha - (180.0 / FLASH_DURATION) * dt)

    def draw(self, surface):
        if self._alpha <= 0:
            return
        self._surf.fill((*FLASH_C, int(self._alpha)))
        surface.blit(self._surf, (0, 0))

    @property
    def active(self) -> bool:
        return self._alpha > 0


# ── Scanline static ───────────────────────────────────────────────────────────
class ScanlineStatic:
    def __init__(self):
        self._timer = 0.0
        self._surf  = pygame.Surface((SW, SH))
        self._surf.set_colorkey((0, 0, 0))
        for y in range(0, SH, 2):
            self._surf.fill((255, 255, 255), (0, y, SW, 1))

    def trigger(self):
        self._timer = SCANLINE_DURATION

    def update(self, dt: float):
        self._timer = max(0.0, self._timer - dt)

    def draw(self, surface):
        if self._timer <= 0:
            return
        self._surf.set_alpha(int(90 * self._timer / SCANLINE_DURATION))
        surface.blit(self._surf, (0, 0))

    @property
    def active(self) -> bool:
        return self._timer > 0
