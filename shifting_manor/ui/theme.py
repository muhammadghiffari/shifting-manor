"""Palette, logical geometry and small drawing helpers for the UI."""

from __future__ import annotations

import pygame

LOGICAL_SIZE = (1280, 720)
BOARD_PX = 576
CELL = 96

BG = (14, 11, 20)
BG_PANEL = (24, 19, 33)
BG_PANEL_LIGHT = (34, 27, 46)
INK = (232, 217, 181)
MUTED = (138, 130, 153)
GOLD = (224, 176, 92)
TEAL = (84, 210, 190)
ORANGE = (238, 122, 72)
CYAN = (150, 226, 236)
VIOLET = (178, 146, 232)
RED = (214, 82, 84)
GREEN = (116, 202, 132)
FLOOR = (43, 35, 54)
FLOOR_VISITED = (62, 50, 74)
WALL = (82, 65, 96)
FOG = (5, 3, 9)

_FONTS: dict[tuple[int, bool], pygame.font.Font] = {}


def font(size: int, bold: bool = False) -> pygame.font.Font:
    key = (size, bold)
    if key not in _FONTS:
        f = pygame.font.Font(None, size)
        f.set_bold(bold)
        _FONTS[key] = f
    return _FONTS[key]


def reset_fonts() -> None:
    """Drop cached Font objects after pygame.quit()/font re-init."""
    _FONTS.clear()


def text(
    surface: pygame.Surface,
    value: str,
    size: int,
    color: tuple[int, int, int] = INK,
    pos: tuple[int, int] = (0, 0),
    *,
    anchor: str = "topleft",
    bold: bool = False,
) -> pygame.Rect:
    image = font(size, bold).render(value, True, color)
    rect = image.get_rect()
    setattr(rect, anchor, pos)
    surface.blit(image, rect)
    return rect


def panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    *,
    color: tuple[int, int, int] = BG_PANEL,
    border: tuple[int, int, int] = WALL,
    radius: int = 8,
) -> None:
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    pygame.draw.rect(surface, border, rect, 2, border_radius=radius)


def button(
    surface: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    *,
    selected: bool = False,
    hover: bool = False,
    size: int = 30,
) -> None:
    fill = BG_PANEL_LIGHT if selected or hover else BG_PANEL
    edge = GOLD if selected else (GOLD if hover else WALL)
    pygame.draw.rect(surface, fill, rect, border_radius=8)
    pygame.draw.rect(surface, edge, rect, 2, border_radius=8)
    text(surface, label, size, INK if selected else MUTED, rect.center, anchor="center")


def mark(surface: pygame.Surface, rect: pygame.Rect, kind: str, alpha: int = 255) -> None:
    """One icon vocabulary for human marks and the Watch AI belief overlay."""
    target = surface
    box = rect
    if alpha < 255:
        target = pygame.Surface(rect.size, pygame.SRCALPHA)
        box = pygame.Rect(0, 0, rect.width, rect.height)
    c = box.center
    if kind == "safe":
        pygame.draw.lines(
            target,
            TEAL,
            False,
            [(c[0] - 16, c[1]), (c[0] - 4, c[1] + 12), (c[0] + 18, c[1] - 14)],
            5,
        )
    elif kind == "pit":
        pygame.draw.circle(target, ORANGE, c, 19, 3)
        pygame.draw.line(target, ORANGE, (c[0] - 11, c[1] - 11), (c[0] + 11, c[1] + 11), 5)
        pygame.draw.line(target, ORANGE, (c[0] + 11, c[1] - 11), (c[0] - 11, c[1] + 11), 5)
    elif kind == "ghost":
        pygame.draw.circle(target, CYAN, (c[0], c[1] - 5), 15, 3)
        pygame.draw.line(target, CYAN, (c[0] - 15, c[1] + 8), (c[0] - 15, c[1] + 18), 3)
        pygame.draw.line(target, CYAN, (c[0], c[1] + 10), (c[0], c[1] + 20), 3)
        pygame.draw.line(target, CYAN, (c[0] + 15, c[1] + 8), (c[0] + 15, c[1] + 18), 3)
    elif kind == "?":
        text(target, "?", 42, VIOLET, c, anchor="center", bold=True)
    if target is not surface:
        target.set_alpha(alpha)
        surface.blit(target, rect.topleft)


def wrap(value: str, size: int, width: int, *, bold: bool = False) -> list[str]:
    font_obj = font(size, bold)
    words = value.split()
    lines: list[str] = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if line and font_obj.size(candidate)[0] > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines or [""]
