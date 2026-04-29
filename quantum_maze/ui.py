"""Slider widget, toggle switch, quantum jump button, HUD strip, win overlay."""

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


# ── Toggle switch ─────────────────────────────────────────────────────────────
class Toggle:
    def __init__(self, x: int, y: int, label: str, init: bool = True):
        self._x     = x
        self._y     = y
        self._label = label
        self.on     = init
        # clickable area: pill (36 wide) + some padding
        self._rect  = pygame.Rect(x, y - 8, 36, 18)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._rect.collidepoint(event.pos):
                self.on = not self.on

    def draw(self, surface):
        _init_fonts()
        x, y = self._x, self._y
        w, h = 36, 16
        r    = h // 2

        bg_col  = (0, 140, 80) if self.on else (60, 30, 30)
        pygame.draw.rect(surface, bg_col,    (x, y - r, w, h), border_radius=r)
        pygame.draw.rect(surface, (80, 80, 120), (x, y - r, w, h), 1, border_radius=r)

        # Knob
        knob_x = x + w - r - 2 if self.on else x + r + 2
        pygame.draw.circle(surface, (220, 240, 255), (knob_x, y), r - 3)

        lbl = _F_LABEL.render(self._label, True, SLIDER_LABEL_C)
        surface.blit(lbl, (x + w + 6, y - lbl.get_height() // 2))

        state_txt = _F_LABEL.render("ON" if self.on else "OFF", True,
                                    (0, 200, 120) if self.on else (160, 60, 60))
        surface.blit(state_txt, (x - state_txt.get_width() - 4,
                                 y - state_txt.get_height() // 2))


# ── Slider ────────────────────────────────────────────────────────────────────
class Slider:
    def __init__(self, x, y, width):
        self._rect   = pygame.Rect(x, y - 10, width, 20)
        self._track  = pygame.Rect(x, y - 3,  width, 6)
        self.value   = 0          # 0 … 100
        self._drag   = False
        self.changed = False

        self._collapse_risk  = 0.0
        self._force_collapse = False

    # ── Depth mapping — 1–50 ─────────────────────────────────────────────────
    @property
    def depth(self) -> int:
        """BFS depth limit 1–50 mapped from slider value 0–100."""
        return max(1, round(self.value / 100 * 50))

    # ── Collapse risk ─────────────────────────────────────────────────────────
    @property
    def force_collapse(self) -> bool:
        return self._force_collapse

    def update(self, dt: float, collapse_enabled: bool, collapse_rate: float):
        """
        collapse_enabled: if False, risk never accumulates.
        collapse_rate: multiplier from the speed slider (0.25 – 4.0).
        """
        self._force_collapse = False
        if not collapse_enabled:
            self._collapse_risk = 0.0
            return
        brightness = self.value / 100.0
        rate = brightness ** 2 * 2.0 * collapse_rate
        self._collapse_risk = min(1.0, self._collapse_risk + dt * rate)
        if self._collapse_risk >= 1.0:
            self._collapse_risk  = 0.0
            self._force_collapse = True
        if self.value == 0:
            self._collapse_risk = max(0.0, self._collapse_risk - dt * 0.5)

    # ── Events ────────────────────────────────────────────────────────────────
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

    def draw(self, surface, collapse_enabled: bool = True):
        _init_fonts()
        depth_val = self.depth
        lbl = _F_LABEL.render(f"RAY DEPTH  {depth_val:2d} / 50", True, SLIDER_LABEL_C)
        surface.blit(lbl, (self._rect.x, self._rect.y - 16))

        pygame.draw.rect(surface, SLIDER_TRACK_C, self._track, border_radius=3)
        fill_w = int(self.value / 100 * self._track.width)
        if fill_w > 0:
            track_col = (180, 60, 30) if self.value > 60 else (0, 100, 140)
            pygame.draw.rect(surface, track_col,
                             (self._track.x, self._track.y, fill_w, self._track.height),
                             border_radius=3)

        # Collapse risk bar (only shown when collapse is enabled)
        if collapse_enabled and self._collapse_risk > 0:
            risk_w = int(self._collapse_risk * self._track.width)
            risk_y = self._track.bottom + 3
            pygame.draw.rect(surface, (180, 30, 30),
                             (self._track.x, risk_y, risk_w, 3))
            if self._collapse_risk > 0.3:
                intensity = int(255 * self._collapse_risk)
                warn = _F_LABEL.render("! COLLAPSE RISK", True, (intensity, 30, 30))
                surface.blit(warn, (self._track.right - warn.get_width(), risk_y + 5))

        hx = self._val_to_x(self.value)
        cy = self._track.centery
        handle_col = (130, 50, 20) if self.value > 60 else (0, 70, 110)
        pygame.draw.circle(surface, handle_col,       (hx, cy), 13)
        pygame.draw.circle(surface, SLIDER_HANDLE_C,  (hx, cy), 9)
        pygame.draw.circle(surface, (200, 245, 255),  (hx, cy), 3)


# ── Collapse speed slider ─────────────────────────────────────────────────────
class CollapseSpeedSlider:
    """Controls how fast collapse risk accumulates. Range 0.25× – 4.0×."""

    _MIN = 0.25
    _MAX = 4.0

    def __init__(self, x, y, width):
        self._rect  = pygame.Rect(x, y - 10, width, 20)
        self._track = pygame.Rect(x, y - 3,  width, 6)
        self.value  = 50     # 0–100 maps to _MIN–_MAX
        self._drag  = False

    @property
    def rate(self) -> float:
        """Returns multiplier in range [_MIN, _MAX]."""
        t = self.value / 100.0
        return self._MIN + t * (self._MAX - self._MIN)

    def _val_to_x(self, v):
        return self._rect.x + int(v / 100 * self._rect.width)

    def _x_to_val(self, x):
        rel = (x - self._rect.x) / max(1, self._rect.width)
        return int(max(0, min(100, rel * 100)))

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            hx = self._val_to_x(self.value)
            hr = pygame.Rect(hx - 10, self._rect.centery - 10, 20, 20)
            if hr.collidepoint(event.pos) or self._track.collidepoint(event.pos):
                self._drag = True
                self.value = self._x_to_val(event.pos[0])
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._drag = False
        elif event.type == pygame.MOUSEMOTION and self._drag:
            self.value = self._x_to_val(event.pos[0])

    def draw(self, surface, enabled: bool = True):
        _init_fonts()
        rate_val = self.rate
        col = SLIDER_LABEL_C if enabled else (60, 60, 90)
        lbl = _F_LABEL.render(f"COLLAPSE SPEED  {rate_val:.2f}x", True, col)
        surface.blit(lbl, (self._rect.x, self._rect.y - 16))

        track_col = SLIDER_TRACK_C if enabled else (20, 20, 35)
        pygame.draw.rect(surface, track_col, self._track, border_radius=3)
        fill_w = int(self.value / 100 * self._track.width)
        if fill_w > 0 and enabled:
            orange = (180, 100, 20)
            pygame.draw.rect(surface, orange,
                             (self._track.x, self._track.y, fill_w, self._track.height),
                             border_radius=3)

        hx = self._val_to_x(self.value)
        cy = self._track.centery
        knob_outer = (100, 60, 10) if enabled else (40, 40, 60)
        knob_inner = (220, 160, 60) if enabled else (80, 80, 100)
        pygame.draw.circle(surface, knob_outer, (hx, cy), 13)
        pygame.draw.circle(surface, knob_inner, (hx, cy), 9)
        pygame.draw.circle(surface, (255, 220, 150) if enabled else (100, 100, 120),
                           (hx, cy), 3)


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

    def draw(self, surface, cooldown_frac: float, can_jump: bool):
        _init_fonts()
        col_border = BUTTON_FG if can_jump else (30, 60, 80)
        pygame.draw.rect(surface, BUTTON_BG, self.rect, border_radius=6)

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
