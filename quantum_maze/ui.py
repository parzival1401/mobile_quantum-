"""Slider widget, quantum jump button, HUD strip, win overlay."""

import pygame
from settings import (
    SW, SH, GAME_H, HUD_H,
    SLIDER_TRACK_C, SLIDER_HANDLE_C, SLIDER_LABEL_C,
    BUTTON_FG, BUTTON_TEXT_C, BUTTON_BG,
    HUD_BG, TEXT_C, WIN_TEXT_C,
    COLLAPSE_PENALTY, JUMP_COOLDOWN,
)

# Module-level fonts (initialised lazily after pygame.init)
_F_LABEL = _F_BTN = _F_HUD = _F_BIG = _F_MED = _F_SM = None


def _init_fonts():
    global _F_LABEL, _F_BTN, _F_HUD, _F_BIG, _F_MED, _F_SM
    if _F_LABEL:
        return
    _F_LABEL = pygame.font.SysFont('monospace', 11)
    _F_BTN   = pygame.font.SysFont('monospace', 13, bold=True)
    _F_HUD   = pygame.font.SysFont('monospace', 13)
    _F_BIG   = pygame.font.SysFont('monospace', 38, bold=True)
    _F_MED   = pygame.font.SysFont('monospace', 20)
    _F_SM    = pygame.font.SysFont('monospace', 15)


# ── Slider ────────────────────────────────────────────────────────────────────
class Slider:
    def __init__(self, x, y, width):
        self._rect  = pygame.Rect(x, y - 10, width, 20)
        self._track = pygame.Rect(x, y - 3, width, 6)
        self.value  = 0          # 0 … 100
        self._drag  = False
        self.changed = False     # True for exactly the frame a change occurs

    def _val_to_x(self, v):
        return self._rect.x + int(v / 100 * self._rect.width)

    def _x_to_val(self, x):
        rel = (x - self._rect.x) / max(1, self._rect.width)
        return int(max(0, min(100, rel * 100)))

    def handle_event(self, event):
        self.changed = False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            hx = self._val_to_x(self.value)
            hr = pygame.Rect(hx - 10, self._rect.centery - 10, 20, 20)
            if hr.collidepoint(event.pos) or self._track.collidepoint(event.pos):
                self._drag = True
                prev = self.value
                self.value = self._x_to_val(event.pos[0])
                self.changed = self.value != prev
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._drag:
                self._drag   = False
                self.changed = True
        elif event.type == pygame.MOUSEMOTION and self._drag:
            prev = self.value
            self.value = self._x_to_val(event.pos[0])
            self.changed = self.value != prev

    def draw(self, surface):
        _init_fonts()
        lbl = _F_LABEL.render("OBSERVATION LEVEL", True, SLIDER_LABEL_C)
        surface.blit(lbl, (self._rect.x, self._rect.y - 16))

        # Track
        pygame.draw.rect(surface, SLIDER_TRACK_C, self._track, border_radius=3)
        fill_w = int(self.value / 100 * self._track.width)
        if fill_w > 0:
            pygame.draw.rect(surface, (0, 100, 140),
                             (self._track.x, self._track.y, fill_w, self._track.height),
                             border_radius=3)

        # Handle
        hx = self._val_to_x(self.value)
        cy = self._track.centery
        pygame.draw.circle(surface, (0, 70, 110), (hx, cy), 13)
        pygame.draw.circle(surface, SLIDER_HANDLE_C,  (hx, cy), 9)
        pygame.draw.circle(surface, (200, 245, 255),  (hx, cy), 3)


# ── Quantum Jump Button ───────────────────────────────────────────────────────
class QuantumJumpButton:
    def __init__(self, x, y, width, height):
        self.rect    = pygame.Rect(x, y, width, height)
        self.pressed = False

    def handle_event(self, event, can_jump: bool):
        self.pressed = False
        if not can_jump:
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.pressed = True
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            self.pressed = True

    def draw(self, surface, cooldown_frac: float, can_jump: bool):
        _init_fonts()
        col_border = BUTTON_FG if can_jump else (30, 60, 80)
        pygame.draw.rect(surface, BUTTON_BG, self.rect, border_radius=6)

        # Cooldown fill bar
        if cooldown_frac < 1.0:
            fw = int(self.rect.width * cooldown_frac)
            pygame.draw.rect(surface, (0, 45, 80),
                             (self.rect.x, self.rect.y, fw, self.rect.height),
                             border_radius=6)

        pygame.draw.rect(surface, col_border, self.rect, 1, border_radius=6)
        tc = BUTTON_TEXT_C if can_jump else (70, 90, 110)
        t  = _F_BTN.render("QUANTUM JUMP [SPACE]", True, tc)
        surface.blit(t, (self.rect.centerx - t.get_width() // 2,
                         self.rect.centery - t.get_height() // 2))


# ── HUD strip ─────────────────────────────────────────────────────────────────
def draw_hud(surface, collapse_count: int, elapsed: float):
    _init_fonts()
    y0 = GAME_H
    pygame.draw.rect(surface, HUD_BG, (0, y0, SW, HUD_H))
    pygame.draw.line(surface, (40, 40, 80), (0, y0), (SW, y0), 1)

    cx = SW // 2
    m  = int(elapsed) // 60
    s  = int(elapsed) % 60

    for i, (txt, col) in enumerate([
        (f"COLLAPSES: {collapse_count}", TEXT_C),
        (f"TIME  {m:02d}:{s:02d}", TEXT_C),
        (f"SCORE: {int(elapsed + collapse_count * COLLAPSE_PENALTY)}s", (200, 200, 100)),
    ]):
        t = _F_HUD.render(txt, True, col)
        surface.blit(t, (cx - t.get_width() // 2, y0 + 8 + i * 20))


# ── Win overlay ───────────────────────────────────────────────────────────────
def draw_win_overlay(surface, collapse_count: int, elapsed: float):
    _init_fonts()
    ov = pygame.Surface((SW, SH), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 185))
    surface.blit(ov, (0, 0))

    cx, cy = SW // 2, SH // 2
    penalty = collapse_count * COLLAPSE_PENALTY
    score   = int(elapsed + penalty)

    for i, (txt, font, col) in enumerate([
        ("MAZE  SOLVED",                _F_BIG, WIN_TEXT_C),
        (f"Time:      {elapsed:.1f}s",  _F_MED, TEXT_C),
        (f"Collapses: {collapse_count}  (+{int(penalty)}s)", _F_MED, TEXT_C),
        (f"SCORE:     {score}s",        _F_MED, WIN_TEXT_C),
        ("",                            _F_SM,  TEXT_C),
        ("Press  R  to restart",        _F_SM,  (140, 140, 200)),
    ]):
        if not txt:
            continue
        t = font.render(txt, True, col)
        surface.blit(t, (cx - t.get_width() // 2, cy - 90 + i * 36))
