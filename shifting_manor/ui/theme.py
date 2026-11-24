"""Palette, typography, logical geometry and rich drawing helpers for the UI."""

from __future__ import annotations

from math import cos, pi, sin
from pathlib import Path

import pygame

LOGICAL_SIZE = (1280, 720)
BOARD_PX = 576
CELL = 96

# Gothic warm-lantern vs cold-shadow palette (colour-blind safe)
BG = (14, 11, 20)
BG_DEEP = (9, 7, 14)
BG_PANEL = (23, 18, 34)
BG_PANEL_LIGHT = (35, 28, 50)
BG_PANEL_HIGHLIGHT = (46, 37, 66)
INK = (238, 224, 192)
INK_BRIGHT = (252, 244, 224)
MUTED = (148, 140, 166)
DIM = (96, 88, 114)
GOLD = (236, 188, 92)
GOLD_SOFT = (182, 140, 68)
AMBER = (255, 174, 76)
TEAL = (72, 214, 194)
ORANGE = (244, 118, 72)
CYAN = (148, 228, 244)
VIOLET = (176, 142, 242)
RED = (226, 84, 88)
GREEN = (118, 208, 134)
FLOOR = (42, 34, 54)
FLOOR_DARK = (28, 22, 38)
FLOOR_VISITED = (64, 51, 80)
WALL = (86, 69, 104)
WALL_LIGHT = (120, 98, 144)
FOG = (6, 4, 11)

_FONTS: dict[tuple[int, bool, bool], pygame.font.Font] = {}
_FONT_PATH: str | None = None
_FONT_BOLD_PATH: str | None = None
_MONO_PATH: str | None = None
_FONT_INITIALIZED = False
_HIGH_CONTRAST = False
_FONT_SCALE = 1.0


def set_accessibility(*, high_contrast: bool = False, font_scale: float = 1.0) -> None:
    """Update global visual accessibility modifiers."""
    global _HIGH_CONTRAST, _FONT_SCALE
    changed = _FONT_SCALE != font_scale
    _HIGH_CONTRAST = high_contrast
    _FONT_SCALE = max(0.85, min(1.35, font_scale))
    if changed:
        _FONTS.clear()


def is_high_contrast() -> bool:
    return _HIGH_CONTRAST


def _bundled_font(filename: str) -> str | None:
    """Locate bundled TTF fonts for both desktop and WebAssembly (pygbag) builds."""
    candidates = (
        Path(__file__).resolve().parent.parent.parent / "assets" / "fonts" / filename,
        Path("assets") / "fonts" / filename,
    )
    for path in candidates:
        if path.is_file():
            return str(path)
    return None


def _resolve_fonts() -> None:
    global _FONT_PATH, _FONT_BOLD_PATH, _MONO_PATH, _FONT_INITIALIZED
    if _FONT_INITIALIZED:
        return
    _FONT_INITIALIZED = True
    if not pygame.font.get_init():
        pygame.font.init()

    _FONT_PATH = _bundled_font("DejaVuSans.ttf")
    _FONT_BOLD_PATH = _bundled_font("DejaVuSans-Bold.ttf")
    _MONO_PATH = _bundled_font("DejaVuSansMono.ttf")

    if _FONT_PATH is None:
        for name in ("dejavusans", "liberationsans", "ubuntusans", "freesans", "arial"):
            path = pygame.font.match_font(name)
            if path:
                _FONT_PATH = path
                break
    if _MONO_PATH is None:
        for name in ("dejavusansmono", "liberationmono", "ubuntumono", "freemono", "consolas"):
            path = pygame.font.match_font(name)
            if path:
                _MONO_PATH = path
                break


def font(size: int, bold: bool = False, *, mono: bool = False) -> pygame.font.Font:
    scaled = max(10, round(size * _FONT_SCALE * 0.78))
    key = (scaled, bold, mono)
    if key not in _FONTS:
        if not pygame.font.get_init():
            pygame.font.init()
        _resolve_fonts()
        use_bold_file = bold and not mono and _FONT_BOLD_PATH is not None
        path = _MONO_PATH if mono else (_FONT_BOLD_PATH if use_bold_file else _FONT_PATH)
        try:
            f = pygame.font.Font(path, scaled)
        except (OSError, pygame.error, RuntimeError):
            f = pygame.font.Font(None, max(12, round(size * _FONT_SCALE)))
            use_bold_file = False
        if bold and not use_bold_file:
            f.set_bold(True)
        _FONTS[key] = f
    return _FONTS[key]


def reset_fonts() -> None:
    """Drop cached Font objects after pygame.quit()/font re-init."""
    global _FONT_INITIALIZED
    _FONTS.clear()
    _FONT_INITIALIZED = False


def text(
    surface: pygame.Surface,
    value: str,
    size: int,
    color: tuple[int, int, int] | tuple[int, int, int, int] = INK,
    pos: tuple[int, int] = (0, 0),
    *,
    anchor: str = "topleft",
    bold: bool = False,
    mono: bool = False,
    shadow: bool = False,
) -> pygame.Rect:
    rgb = color[:3]
    alpha = color[3] if len(color) > 3 else 255
    if _HIGH_CONTRAST and rgb == MUTED:
        rgb = INK
    f = font(size, bold, mono=mono)
    image = f.render(value, True, rgb)
    if alpha < 255:
        image.set_alpha(alpha)
    rect = image.get_rect()
    setattr(rect, anchor, pos)
    if shadow:
        sh = f.render(value, True, (6, 4, 10))
        if alpha < 255:
            sh.set_alpha(alpha)
        surface.blit(sh, rect.move(1, 2))
    surface.blit(image, rect)
    return rect


def panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    *,
    color: tuple[int, int, int] = BG_PANEL,
    border: tuple[int, int, int] | None = None,
    radius: int = 10,
    accent_top: tuple[int, int, int] | None = None,
) -> None:
    edge = border or (WALL_LIGHT if _HIGH_CONTRAST else WALL)
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    if accent_top is not None:
        bar = pygame.Rect(rect.x + radius, rect.y + 1, max(1, rect.width - 2 * radius), 2)
        pygame.draw.rect(surface, accent_top, bar)
    pygame.draw.rect(surface, edge, rect, 2, border_radius=radius)


def badge(
    surface: pygame.Surface,
    label: str,
    pos: tuple[int, int],
    *,
    color: tuple[int, int, int] = GOLD,
    bg: tuple[int, int, int] = BG_PANEL_LIGHT,
    size: int = 15,
    anchor: str = "topleft",
    pad_x: int = 10,
    pad_y: int = 4,
) -> pygame.Rect:
    f = font(size, bold=True)
    tw, th = f.size(label)
    rect = pygame.Rect(0, 0, tw + pad_x * 2, th + pad_y * 2)
    setattr(rect, anchor, pos)
    pygame.draw.rect(surface, bg, rect, border_radius=rect.height // 2)
    pygame.draw.rect(surface, color, rect, 1, border_radius=rect.height // 2)
    text(surface, label, size, color, rect.center, anchor="center", bold=True)
    return rect


def button(
    surface: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    *,
    selected: bool = False,
    hover: bool = False,
    disabled: bool = False,
    accent: tuple[int, int, int] = GOLD,
    size: int = 24,
    sublabel: str = "",
) -> None:
    if disabled:
        fill = (20, 16, 28)
        edge = (54, 46, 66)
        fg = DIM
    elif selected and hover:
        fill = BG_PANEL_HIGHLIGHT
        edge = INK_BRIGHT
        fg = INK_BRIGHT
    elif selected:
        fill = BG_PANEL_LIGHT
        edge = accent
        fg = INK_BRIGHT
    elif hover:
        fill = BG_PANEL_LIGHT
        edge = accent
        fg = INK
    else:
        fill = BG_PANEL
        edge = WALL_LIGHT if _HIGH_CONTRAST else WALL
        fg = INK if _HIGH_CONTRAST else MUTED

    pygame.draw.rect(surface, fill, rect, border_radius=9)
    if (selected or hover) and not disabled:
        inner = rect.inflate(-4, -4)
        pygame.draw.rect(surface, (*edge[:3],), inner, 1, border_radius=7)
    pygame.draw.rect(surface, edge, rect, 2, border_radius=9)
    if label:
        if sublabel:
            text(
                surface,
                label,
                size,
                fg,
                (rect.centerx, rect.centery - 9),
                anchor="center",
                bold=selected or hover,
            )
            text(
                surface,
                sublabel,
                max(13, size - 9),
                accent if selected else MUTED,
                (rect.centerx, rect.centery + 12),
                anchor="center",
            )
        else:
            text(surface, label, size, fg, rect.center, anchor="center", bold=selected or hover)


def mark(surface: pygame.Surface, rect: pygame.Rect, kind: str, alpha: int = 255) -> None:
    """One icon vocabulary for human marks and the Watch/Live AI belief overlay."""
    target = surface
    box = rect
    if alpha < 255:
        target = pygame.Surface(rect.size, pygame.SRCALPHA)
        box = pygame.Rect(0, 0, rect.width, rect.height)
    c = box.center
    scale = min(box.width, box.height) / 96.0
    if kind == "safe":
        r = max(10, int(19 * scale))
        pts = [
            (c[0] - int(15 * scale), c[1] + int(1 * scale)),
            (c[0] - int(4 * scale), c[1] + int(12 * scale)),
            (c[0] + int(17 * scale), c[1] - int(13 * scale)),
        ]
        pygame.draw.circle(target, (22, 54, 52), c, r)
        pygame.draw.circle(target, TEAL, c, r, max(2, int(2 * scale)))
        pygame.draw.lines(target, TEAL, False, pts, max(2, int(4 * scale)))
    elif kind == "pit":
        r = max(10, int(19 * scale))
        d = max(5, int(10 * scale))
        pygame.draw.circle(target, (64, 24, 18), c, r)
        pygame.draw.circle(target, ORANGE, c, r, max(2, int(3 * scale)))
        pygame.draw.line(
            target, ORANGE, (c[0] - d, c[1] - d), (c[0] + d, c[1] + d), max(2, int(4 * scale))
        )
        pygame.draw.line(
            target, ORANGE, (c[0] + d, c[1] - d), (c[0] - d, c[1] + d), max(2, int(4 * scale))
        )
    elif kind == "ghost":
        r = max(8, int(14 * scale))
        head = (c[0], c[1] - int(5 * scale))
        pygame.draw.circle(target, (26, 54, 66), head, r)
        pygame.draw.circle(target, CYAN, head, r, max(2, int(3 * scale)))
        eye_r = max(1, int(2.5 * scale))
        pygame.draw.circle(target, CYAN, (head[0] - int(4 * scale), head[1] - 1), eye_r)
        pygame.draw.circle(target, CYAN, (head[0] + int(4 * scale), head[1] - 1), eye_r)
        for dx, dy in ((-r + 2, 12), (0, 15), (r - 2, 12)):
            pygame.draw.line(
                target,
                CYAN,
                (c[0] + dx, c[1] + int(5 * scale)),
                (c[0] + dx, c[1] + int(dy * scale)),
                max(2, int(3 * scale)),
            )
    elif kind == "?":
        sz = max(18, int(40 * scale))
        text(target, "?", sz, VIOLET, c, anchor="center", bold=True)
    if target is not surface:
        target.set_alpha(alpha)
        surface.blit(target, rect.topleft)


def draw_star(
    surface: pygame.Surface,
    center: tuple[int, int],
    radius: int,
    *,
    filled: bool,
) -> None:
    points = [
        (
            center[0] + cos(-pi / 2 + i * pi / 5) * (radius if i % 2 == 0 else radius * 0.45),
            center[1] + sin(-pi / 2 + i * pi / 5) * (radius if i % 2 == 0 else radius * 0.45),
        )
        for i in range(10)
    ]
    if filled:
        pygame.draw.polygon(surface, GOLD, points)
        pygame.draw.polygon(surface, (120, 84, 42), points, 2)
    else:
        pygame.draw.polygon(surface, (92, 80, 104), points, 2)


def draw_rotation_arrow(
    surface: pygame.Surface,
    center: tuple[int, int],
    radius: int,
    direction: str,
    color: tuple[int, int, int] = GOLD,
    width: int = 3,
) -> None:
    """Draw a clean vector CW or CCW curved arrow (never relies on Unicode glyphs)."""
    box = pygame.Rect(center[0] - radius, center[1] - radius, radius * 2, radius * 2)
    if direction == "cw":
        pygame.draw.arc(surface, color, box, -0.3, 4.1, width)
        tip = (center[0] + int(radius * cos(-0.3)), center[1] - int(radius * sin(-0.3)))
        head = [
            tip,
            (tip[0] - 9, tip[1] - 4),
            (tip[0] + 4, tip[1] - 9),
        ]
    else:
        pygame.draw.arc(surface, color, box, -1.0, 3.4, width)
        tip = (center[0] + int(radius * cos(3.4)), center[1] - int(radius * sin(3.4)))
        head = [
            tip,
            (tip[0] + 9, tip[1] - 4),
            (tip[0] - 4, tip[1] - 9),
        ]
    pygame.draw.polygon(surface, color, head)


def draw_tooltip(
    surface: pygame.Surface,
    anchor_pos: tuple[int, int],
    title: str,
    lines: list[tuple[str, tuple[int, int, int]]],
    *,
    max_width: int = 290,
) -> None:
    """Draw a floating dark-parchment tooltip clamped inside the 1280x720 canvas."""
    rendered: list[tuple[str, tuple[int, int, int]]] = []
    for line, col in lines:
        for wrapped in wrap(line, 15, max_width - 20):
            rendered.append((wrapped, col))
    f_title = font(16, bold=True)
    f_body = font(15)
    w = max(
        f_title.size(title)[0] + 22,
        max((f_body.size(line)[0] + 22 for line, _ in rendered), default=120),
    )
    w = min(max_width, max(150, w))
    h = 30 + len(rendered) * 18 + 8
    x = anchor_pos[0] + 18
    y = anchor_pos[1] - h - 10
    if x + w > LOGICAL_SIZE[0] - 12:
        x = anchor_pos[0] - w - 18
    if y < 12:
        y = anchor_pos[1] + 22
    x = max(12, min(x, LOGICAL_SIZE[0] - w - 12))
    y = max(12, min(y, LOGICAL_SIZE[1] - h - 12))
    rect = pygame.Rect(x, y, w, h)
    box = pygame.Surface(rect.size, pygame.SRCALPHA)
    box.fill((16, 12, 26, 240))
    surface.blit(box, rect.topleft)
    pygame.draw.rect(surface, GOLD, rect, 1, border_radius=8)
    text(surface, title, 16, GOLD, (rect.x + 11, rect.y + 7), bold=True)
    for i, (line, col) in enumerate(rendered):
        text(surface, line, 15, col, (rect.x + 11, rect.y + 28 + i * 18))


def wrap(value: str, size: int, width: int, *, bold: bool = False) -> list[str]:
    """Word-wrap ``value`` so every returned line fits ``width``; never truncates.

    Words that are longer than the whole width (e.g. long ``PIT{(0,3),...}``
    constraint tokens) are hard-broken instead of overflowing.
    """
    font_obj = font(size, bold)
    lines: list[str] = []
    line = ""
    for chunk in _chunks(value, font_obj, width):
        candidate = f"{line} {chunk}".strip()
        if line and font_obj.size(candidate)[0] > width:
            lines.append(line)
            line = chunk
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines or [""]


def _chunks(value: str, font_obj, width: int):
    """Split on spaces, then hard-break any token that alone exceeds ``width``."""
    for word in value.split():
        start = 0
        while start < len(word):
            end = len(word)
            while end > start + 1 and font_obj.size(word[start:end])[0] > width:
                end -= 1
            if font_obj.size(word[start:end])[0] > width:  # one glyph still too wide
                end = start + 1
            yield word[start:end]
            start = end
