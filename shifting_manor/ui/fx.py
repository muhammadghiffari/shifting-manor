"""Visual effects: particles, beams, floating text, screen shake, gothic sprites."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame

from shifting_manor.ui import theme


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    radius: float
    color: tuple[int, int, int]
    kind: str = "dot"


@dataclass
class FloatingText:
    x: float
    y: float
    text: str
    color: tuple[int, int, int]
    life: float
    max_life: float
    size: int = 20


@dataclass
class CharmBeam:
    start: tuple[float, float]
    end: tuple[float, float]
    life: float
    max_life: float = 0.42


class FXManager:
    """Self-contained particles, floating popups, charm beams and screen shake."""

    def __init__(self) -> None:
        self.particles: list[Particle] = []
        self.popups: list[FloatingText] = []
        self.beams: list[CharmBeam] = []
        self.shake_timer = 0.0
        self.shake_intensity = 0.0
        self.toast_text = ""
        self.toast_color = theme.GOLD
        self.toast_timer = 0.0
        self._rng = random.Random(42)

    def clear(self) -> None:
        self.particles.clear()
        self.popups.clear()
        self.beams.clear()
        self.shake_timer = 0.0
        self.shake_intensity = 0.0

    def trigger_shake(self, intensity: float = 6.0, duration: float = 0.25) -> None:
        self.shake_intensity = max(self.shake_intensity, intensity)
        self.shake_timer = max(self.shake_timer, duration)

    def toast(self, message: str, color: tuple[int, int, int] = theme.GOLD, duration: float = 2.6):
        self.toast_text = message
        self.toast_color = color
        self.toast_timer = duration

    def add_popup(
        self,
        pos: tuple[float, float],
        message: str,
        color: tuple[int, int, int] = theme.GOLD,
        *,
        size: int = 20,
        duration: float = 1.3,
    ) -> None:
        self.popups.append(FloatingText(pos[0], pos[1], message, color, duration, duration, size))

    def add_beam(self, start: tuple[float, float], end: tuple[float, float]) -> None:
        self.beams.append(CharmBeam(start, end, 0.45, 0.45))

    def emit_percepts(
        self,
        rect: pygame.Rect,
        *,
        breeze: bool = False,
        chill: bool = False,
        glimmer: bool = False,
        dt: float = 0.016,
    ) -> None:
        if len(self.particles) > 180:
            return
        if breeze and self._rng.random() < min(0.5, dt * 14.0):
            y = rect.y + self._rng.uniform(10, rect.height - 10)
            self.particles.append(
                Particle(
                    rect.x + 6,
                    y,
                    self._rng.uniform(65, 115),
                    self._rng.uniform(-10, 10),
                    0.65,
                    0.65,
                    2.5,
                    theme.CYAN,
                    "wind",
                )
            )
        if chill and self._rng.random() < min(0.45, dt * 11.0):
            x = rect.x + self._rng.uniform(14, rect.width - 14)
            y = rect.bottom - self._rng.uniform(8, 26)
            self.particles.append(
                Particle(
                    x,
                    y,
                    self._rng.uniform(-14, 14),
                    self._rng.uniform(-42, -20),
                    0.9,
                    0.9,
                    5.0,
                    theme.GREEN,
                    "wisp",
                )
            )
        if glimmer and self._rng.random() < min(0.55, dt * 15.0):
            x = rect.x + self._rng.uniform(12, rect.width - 12)
            y = rect.y + self._rng.uniform(12, rect.height - 12)
            self.particles.append(
                Particle(
                    x,
                    y,
                    self._rng.uniform(-12, 12),
                    self._rng.uniform(-24, -6),
                    0.75,
                    0.75,
                    3.5,
                    theme.GOLD,
                    "sparkle",
                )
            )

    def burst(
        self,
        center: tuple[float, float],
        color: tuple[int, int, int],
        *,
        count: int = 20,
        speed: float = 95.0,
        kind: str = "sparkle",
    ) -> None:
        for _ in range(count):
            ang = self._rng.uniform(0, math.tau)
            spd = self._rng.uniform(speed * 0.35, speed)
            life = self._rng.uniform(0.35, 0.85)
            self.particles.append(
                Particle(
                    center[0],
                    center[1],
                    math.cos(ang) * spd,
                    math.sin(ang) * spd,
                    life,
                    life,
                    self._rng.uniform(2.5, 5.0),
                    color,
                    kind,
                )
            )

    def update(self, dt: float) -> None:
        if self.shake_timer > 0.0:
            self.shake_timer = max(0.0, self.shake_timer - dt)
            if self.shake_timer == 0.0:
                self.shake_intensity = 0.0
        if self.toast_timer > 0.0:
            self.toast_timer = max(0.0, self.toast_timer - dt)

        alive_p: list[Particle] = []
        for p in self.particles:
            p.life -= dt
            if p.life <= 0.0:
                continue
            p.x += p.vx * dt
            p.y += p.vy * dt
            alive_p.append(p)
        self.particles = alive_p

        alive_t: list[FloatingText] = []
        for item in self.popups:
            item.life -= dt
            if item.life <= 0.0:
                continue
            item.y -= 28.0 * dt
            alive_t.append(item)
        self.popups = alive_t

        alive_b: list[CharmBeam] = []
        for beam in self.beams:
            beam.life -= dt
            if beam.life > 0.0:
                alive_b.append(beam)
        self.beams = alive_b

    def shake_offset(self, *, reduce_motion: bool = False) -> tuple[int, int]:
        if reduce_motion or self.shake_timer <= 0.0 or self.shake_intensity <= 0.0:
            return (0, 0)
        mag = self.shake_intensity * min(1.0, self.shake_timer * 4.0)
        return (
            int(self._rng.uniform(-mag, mag)),
            int(self._rng.uniform(-mag, mag)),
        )

    def draw(self, surface: pygame.Surface) -> None:
        if self.particles or self.beams:
            layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            for beam in self.beams:
                t = max(0.0, min(1.0, beam.life / beam.max_life))
                alpha = int(235 * t)
                pygame.draw.line(
                    layer,
                    (*theme.VIOLET, alpha),
                    beam.start,
                    beam.end,
                    max(2, int(10 * t)),
                )
                pygame.draw.line(
                    layer,
                    (*theme.CYAN, alpha),
                    beam.start,
                    beam.end,
                    max(1, int(4 * t)),
                )
                # Animated sigil head traveling along beam
                prog = 1.0 - t
                hx = beam.start[0] + (beam.end[0] - beam.start[0]) * prog
                hy = beam.start[1] + (beam.end[1] - beam.start[1]) * prog
                pygame.draw.circle(layer, (*theme.INK_BRIGHT, alpha), (int(hx), int(hy)), 7)
                pygame.draw.circle(layer, (*theme.CYAN, alpha), (int(hx), int(hy)), 12, 2)
            for p in self.particles:
                ratio = max(0.0, min(1.0, p.life / p.max_life))
                alpha = int(220 * ratio)
                ix, iy = int(p.x), int(p.y)
                if p.kind == "wind":
                    pygame.draw.line(
                        layer,
                        (*p.color, alpha),
                        (ix - 10, iy),
                        (ix + 10, iy),
                        2,
                    )
                elif p.kind == "sparkle":
                    r = max(2, int(p.radius * (0.6 + 0.6 * ratio)))
                    pygame.draw.line(layer, (*p.color, alpha), (ix - r, iy), (ix + r, iy), 2)
                    pygame.draw.line(layer, (*p.color, alpha), (ix, iy - r), (ix, iy + r), 2)
                else:
                    pygame.draw.circle(
                        layer, (*p.color, alpha), (ix, iy), max(1, int(p.radius * ratio))
                    )
            surface.blit(layer, (0, 0))

        for item in self.popups:
            ratio = max(0.0, min(1.0, item.life / item.max_life))
            alpha = int(255 * min(1.0, ratio * 2.2))
            theme.text(
                surface,
                item.text,
                item.size,
                (*item.color, alpha),
                (int(item.x), int(item.y)),
                anchor="center",
                bold=True,
                shadow=True,
            )

        if self.toast_timer > 0.0 and self.toast_text:
            alpha = int(242 * min(1.0, self.toast_timer * 2.0))
            f = theme.font(16, bold=True)
            tw, th = f.size(self.toast_text)
            rect = pygame.Rect(0, 0, tw + 28, th + 12)
            rect.midbottom = (theme.LOGICAL_SIZE[0] // 2, theme.LOGICAL_SIZE[1] - 6)
            pill = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(pill, (16, 12, 26, alpha), pill.get_rect(), border_radius=10)
            pygame.draw.rect(pill, (*self.toast_color, alpha), pill.get_rect(), 2, border_radius=10)
            surface.blit(pill, rect.topleft)
            theme.text(
                surface,
                self.toast_text,
                16,
                (*self.toast_color, alpha),
                rect.center,
                anchor="center",
                bold=True,
            )


# -- Procedural gothic sprites (zero external asset dependency) ---------------
def draw_caretaker(
    surface: pygame.Surface,
    center: tuple[int, int],
    facing: str,
    t: float,
    *,
    carrying_treasure: bool = False,
    ai_mode: bool = False,
) -> None:
    """Draw the hooded Caretaker with a softly swinging warm lantern."""
    bob = round(math.sin(t * 4.5) * 2.0)
    cx, cy = center[0], center[1] + bob

    # Soft ground shadow
    shadow = pygame.Surface((46, 18), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 110), (0, 0, 46, 18))
    surface.blit(shadow, (cx - 23, center[1] + 15))

    # Cloak body
    cloak_col = (56, 78, 114) if ai_mode else (74, 52, 92)
    cloak_edge = theme.CYAN if ai_mode else theme.GOLD
    body = [
        (cx, cy - 18),
        (cx + 18, cy + 14),
        (cx + 8, cy + 20),
        (cx - 8, cy + 20),
        (cx - 18, cy + 14),
    ]
    pygame.draw.polygon(surface, cloak_col, body)
    pygame.draw.polygon(surface, cloak_edge, body, 2)

    # Hood & warm lit face
    pygame.draw.circle(surface, (42, 32, 54), (cx, cy - 12), 12)
    pygame.draw.circle(surface, cloak_edge, (cx, cy - 12), 12, 2)
    # Eyes looking toward facing direction
    offsets = {"N": (0, -4), "S": (0, 2), "E": (4, -1), "W": (-4, -1)}
    ox, oy = offsets.get(facing, (0, 2))
    eye_col = theme.CYAN if ai_mode else theme.AMBER
    pygame.draw.circle(surface, eye_col, (cx - 4 + ox // 2, cy - 12 + oy // 2), 2)
    pygame.draw.circle(surface, eye_col, (cx + 4 + ox // 2, cy - 12 + oy // 2), 2)

    # Swinging warm lantern held in front/side
    lan_off = {"N": (14, -6), "S": (14, 6), "E": (16, 2), "W": (-16, 2)}.get(facing, (14, 4))
    swing = round(math.sin(t * 5.2) * 2.0)
    lx, ly = cx + lan_off[0] + swing, cy + lan_off[1]
    glow = pygame.Surface((32, 32), pygame.SRCALPHA)
    pygame.draw.circle(glow, (255, 186, 86, 75), (16, 16), 14)
    pygame.draw.circle(glow, (255, 220, 130, 145), (16, 16), 7)
    surface.blit(glow, (lx - 16, ly - 16))
    pygame.draw.rect(surface, theme.GOLD, (lx - 4, ly - 5, 8, 10), border_radius=2)
    pygame.draw.rect(surface, theme.INK_BRIGHT, (lx - 2, ly - 3, 4, 6), border_radius=1)

    # Facing direction chevron on edge
    dir_vec = {"N": (0, -25), "S": (0, 25), "E": (25, 0), "W": (-25, 0)}.get(facing, (0, 25))
    tx, ty = cx + dir_vec[0], cy + dir_vec[1]
    px, py = -dir_vec[1] * 0.22, dir_vec[0] * 0.22
    bx, by = cx + dir_vec[0] * 0.72, cy + dir_vec[1] * 0.72
    pygame.draw.polygon(
        surface,
        theme.GOLD if not ai_mode else theme.CYAN,
        [(tx, ty), (bx + px, by + py), (bx - px, by - py)],
    )

    # Tiny golden heirloom badge on shoulder if carried
    if carrying_treasure:
        hx, hy = cx - 14, cy - 16
        pts = [(hx, hy - 7), (hx + 6, hy), (hx, hy + 7), (hx - 6, hy)]
        pygame.draw.polygon(surface, theme.GOLD, pts)
        pygame.draw.polygon(surface, theme.INK_BRIGHT, pts, 1)


def draw_heirloom(surface: pygame.Surface, rect: pygame.Rect, t: float = 0.0) -> None:
    """Draw a gleaming heirloom diamond/locket with animated pulse."""
    cx, cy = rect.center
    pulse = 1.0 + 0.08 * math.sin(t * 5.0)
    r = int(18 * pulse)
    aura = pygame.Surface((64, 64), pygame.SRCALPHA)
    pygame.draw.circle(aura, (242, 193, 78, 55), (32, 32), 28)
    pygame.draw.circle(aura, (255, 224, 130, 80), (32, 32), 18)
    surface.blit(aura, (cx - 32, cy - 32))
    pts = [(cx, cy - r), (cx + int(r * 0.85), cy), (cx, cy + r), (cx - int(r * 0.85), cy)]
    pygame.draw.polygon(surface, theme.GOLD, pts)
    pygame.draw.polygon(surface, theme.INK_BRIGHT, pts, 2)
    inner = [
        (cx, cy - r // 2),
        (cx + r // 3, cy),
        (cx, cy + r // 2),
        (cx - r // 3, cy),
    ]
    pygame.draw.polygon(surface, (255, 236, 170), inner)


def draw_pit_reveal(surface: pygame.Surface, rect: pygame.Rect) -> None:
    """Draw a crumbling bottomless pit chasm (revealed board / tutorial)."""
    c = rect.center
    pygame.draw.circle(surface, (18, 10, 14), c, 26)
    pygame.draw.circle(surface, (8, 4, 8), c, 19)
    pygame.draw.circle(surface, theme.ORANGE, c, 26, 3)
    pygame.draw.circle(surface, (130, 58, 38), c, 21, 1)
    pygame.draw.line(surface, theme.ORANGE, (c[0] - 9, c[1] - 9), (c[0] + 9, c[1] + 9), 3)
    pygame.draw.line(surface, theme.ORANGE, (c[0] + 9, c[1] - 9), (c[0] - 9, c[1] + 9), 3)


def draw_ghost_reveal(surface: pygame.Surface, rect: pygame.Rect, t: float = 0.0) -> None:
    """Draw a cosy-creepy floating spectral ghost (revealed board / tutorial)."""
    bob = round(math.sin(t * 4.0) * 3.0)
    cx, cy = rect.centerx, rect.centery + bob
    aura = pygame.Surface((68, 68), pygame.SRCALPHA)
    pygame.draw.circle(aura, (148, 228, 244, 52), (34, 34), 28)
    surface.blit(aura, (cx - 34, cy - 34))
    pygame.draw.circle(surface, (164, 234, 248), (cx, cy - 6), 16)
    pygame.draw.rect(surface, (164, 234, 248), (cx - 16, cy - 6, 32, 18))
    for i in range(4):
        tx = cx - 12 + i * 8
        pygame.draw.circle(surface, (164, 234, 248), (tx, cy + 12), 5)
    pygame.draw.circle(surface, (24, 36, 52), (cx - 6, cy - 7), 3)
    pygame.draw.circle(surface, (24, 36, 52), (cx + 6, cy - 7), 3)
    pygame.draw.ellipse(surface, (24, 36, 52), (cx - 4, cy, 8, 5))


def draw_stone_tile(
    surface: pygame.Surface,
    rect: pygame.Rect,
    cell: tuple[int, int],
    *,
    visited: bool,
    is_entrance: bool,
    has_treasure_badge: bool = False,
    show_coords: bool = False,
) -> None:
    """Draw a detailed gothic stone room tile with subtle masonry texture."""
    fill = theme.FLOOR_VISITED if visited else theme.FLOOR_DARK
    inner = rect.inflate(-4, -4)
    pygame.draw.rect(surface, fill, inner, border_radius=4)
    # Subtle bevel highlight & shadow
    border = (78, 63, 98) if visited else (48, 39, 60)
    pygame.draw.rect(surface, border, rect, 1)
    # Subtle stone brick seam deterministic from cell coords
    if (cell[0] + cell[1]) % 2 == 0:
        pygame.draw.line(
            surface,
            (54, 44, 68) if visited else (35, 28, 46),
            (inner.x + 12, inner.y + 30),
            (inner.right - 16, inner.y + 30),
            1,
        )
    else:
        pygame.draw.line(
            surface,
            (54, 44, 68) if visited else (35, 28, 46),
            (inner.x + 34, inner.y + 16),
            (inner.x + 34, inner.bottom - 18),
            1,
        )
    if visited:
        # Soft footprints
        for dx, dy in ((-14, 14), (8, 22)):
            pygame.draw.ellipse(
                surface,
                (102, 84, 120),
                (rect.centerx + dx - 5, rect.centery + dy - 3, 10, 6),
                1,
            )
    if is_entrance:
        # Golden arched manor doorway along the bottom edge
        door = pygame.Rect(rect.centerx - 24, rect.bottom - 16, 48, 12)
        pygame.draw.rect(surface, theme.GOLD, door, border_radius=4)
        pygame.draw.rect(surface, (124, 86, 36), door, 2, border_radius=4)
        if has_treasure_badge:
            theme.text(
                surface,
                "EXIT [E]",
                13,
                theme.GOLD,
                (rect.centerx, rect.top + 8),
                anchor="midtop",
                bold=True,
                shadow=True,
            )
        else:
            theme.text(
                surface,
                "DOOR",
                12,
                theme.GOLD_SOFT,
                (rect.centerx, rect.bottom - 20),
                anchor="midbottom",
                bold=True,
            )
    if show_coords:
        theme.text(
            surface,
            f"{cell[0]},{cell[1]}",
            12,
            (116, 106, 134) if visited else (74, 66, 88),
            (rect.x + 6, rect.y + 5),
            mono=True,
        )
