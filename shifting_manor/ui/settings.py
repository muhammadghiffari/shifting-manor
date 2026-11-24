"""Settings & accessibility configuration and interactive overlay."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from shifting_manor.ui import strings, theme


@dataclass
class Settings:
    master_volume: float = 0.8
    music_volume: float = 0.45
    sfx_volume: float = 0.75
    reduce_motion: bool = False
    high_contrast: bool = False
    show_hints: bool = True
    show_coords: bool = True
    fog_enabled: bool = True
    font_scale: float = 1.0
    default_ai_speed: float = 1.0


class SettingsOverlay:
    """Modal settings drawer accessible from Title, Mode Select, or Pause."""

    def __init__(self, settings: Settings, *, on_apply, on_close) -> None:
        self.settings = settings
        self.on_apply = on_apply
        self.on_close = on_close
        self._hits: list[tuple[pygame.Rect, str, object]] = []

    def handle(self, event, pos: tuple[int, int] | None = None) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_o):
                self.on_close()
                return True
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and pos is not None:
            for rect, action, payload in self._hits:
                if rect.collidepoint(pos):
                    self._activate(action, payload)
                    return True
            panel = self._rect()
            if not panel.collidepoint(pos):
                self.on_close()
            return True
        return False

    def _activate(self, action: str, payload: object) -> None:
        s = self.settings
        if action == "close":
            self.on_close()
            return
        if action == "master":
            s.master_volume = float(payload)  # type: ignore[arg-type]
        elif action == "music":
            s.music_volume = float(payload)  # type: ignore[arg-type]
        elif action == "sfx":
            s.sfx_volume = float(payload)  # type: ignore[arg-type]
        elif action == "reduce_motion":
            s.reduce_motion = not s.reduce_motion
        elif action == "high_contrast":
            s.high_contrast = not s.high_contrast
        elif action == "show_hints":
            s.show_hints = not s.show_hints
        elif action == "show_coords":
            s.show_coords = not s.show_coords
        elif action == "fog_enabled":
            s.fog_enabled = not s.fog_enabled
        elif action == "font_scale":
            s.font_scale = float(payload)  # type: ignore[arg-type]
        elif action == "ai_speed":
            s.default_ai_speed = float(payload)  # type: ignore[arg-type]
        self.on_apply()

    @staticmethod
    def _rect() -> pygame.Rect:
        return pygame.Rect(240, 80, 800, 560)

    def draw(self, canvas: pygame.Surface, mouse: tuple[int, int]) -> None:
        self._hits = []
        shade = pygame.Surface(theme.LOGICAL_SIZE, pygame.SRCALPHA)
        shade.fill((8, 6, 14, 218))
        canvas.blit(shade, (0, 0))

        rect = self._rect()
        theme.panel(canvas, rect, color=theme.BG_PANEL_LIGHT, accent_top=theme.GOLD)
        theme.text(
            canvas,
            strings.SETTINGS_TITLE,
            30,
            theme.GOLD,
            (rect.x + 28, rect.y + 20),
            bold=True,
        )
        theme.text(
            canvas,
            strings.SETTINGS_HINT,
            16,
            theme.MUTED,
            (rect.x + 28, rect.y + 56),
        )
        close = pygame.Rect(rect.right - 110, rect.y + 20, 86, 34)
        theme.button(canvas, close, "DONE", selected=True, hover=close.collidepoint(mouse), size=18)
        self._hits.append((close, "close", None))

        s = self.settings
        y = rect.y + 100

        # Volume step bars
        for key, label, val in (
            ("master", "Master Volume", s.master_volume),
            ("music", "Ambient Music", s.music_volume),
            ("sfx", "Sound Effects", s.sfx_volume),
        ):
            theme.text(canvas, label, 20, theme.INK, (rect.x + 32, y + 6))
            steps = (0.0, 0.25, 0.5, 0.75, 1.0)
            for i, lvl in enumerate(steps):
                btn = pygame.Rect(rect.x + 330 + i * 82, y, 74, 32)
                active = abs(val - lvl) < 0.12
                theme.button(
                    canvas,
                    btn,
                    "MUTE" if lvl == 0 else f"{int(lvl * 100)}%",
                    selected=active,
                    hover=btn.collidepoint(mouse),
                    size=16,
                )
                self._hits.append((btn, key, lvl))
            y += 46

        y += 8
        pygame.draw.line(canvas, theme.WALL, (rect.x + 28, y), (rect.right - 28, y), 1)
        y += 18

        # Toggles in 2 columns
        toggles = [
            ("show_hints", "Live Coaching Hints", s.show_hints, "Contextual tips while playing"),
            (
                "show_coords",
                "Room Coordinates (x,y)",
                s.show_coords,
                "Show grid coordinates on tiles",
            ),
            ("fog_enabled", "Lantern Fog of War", s.fog_enabled, "Atmospheric lantern darkness"),
            (
                "reduce_motion",
                "Reduce Motion",
                s.reduce_motion,
                "Disable screen shake & spin tween",
            ),
            ("high_contrast", "High Contrast UI", s.high_contrast, "Brighter borders & text"),
        ]
        for idx, (key, label, value, desc) in enumerate(toggles):
            col = idx % 2
            row = idx // 2
            bx = rect.x + 32 + col * 376
            by = y + row * 64
            box = pygame.Rect(bx, by, 356, 52)
            theme.panel(
                canvas,
                box,
                color=theme.BG_PANEL_HIGHLIGHT if value else theme.BG_PANEL,
                border=theme.TEAL if value else theme.WALL,
                radius=8,
            )
            theme.text(canvas, label, 18, theme.INK, (box.x + 14, box.y + 8), bold=True)
            theme.text(canvas, desc, 14, theme.MUTED, (box.x + 14, box.y + 30))
            theme.badge(
                canvas,
                "ON" if value else "OFF",
                (box.right - 12, box.centery),
                color=theme.TEAL if value else theme.MUTED,
                anchor="midright",
                size=15,
            )
            self._hits.append((box, key, None))

        y += 206
        # Font scale + Default AI Speed
        theme.text(canvas, "Font Scale", 18, theme.INK, (rect.x + 32, y + 6))
        for i, (sc, lbl) in enumerate(((1.0, "100%"), (1.12, "112%"), (1.25, "125%"))):
            btn = pygame.Rect(rect.x + 160 + i * 74, y, 66, 32)
            theme.button(
                canvas,
                btn,
                lbl,
                selected=abs(s.font_scale - sc) < 0.05,
                hover=btn.collidepoint(mouse),
                size=16,
            )
            self._hits.append((btn, "font_scale", sc))

        theme.text(canvas, "AI Speed", 18, theme.INK, (rect.x + 420, y + 6))
        for i, spd in enumerate((0.5, 1.0, 2.0, 4.0)):
            btn = pygame.Rect(rect.x + 516 + i * 64, y, 56, 32)
            theme.button(
                canvas,
                btn,
                f"{spd:g}x",
                selected=abs(s.default_ai_speed - spd) < 0.1,
                hover=btn.collidepoint(mouse),
                size=16,
            )
            self._hits.append((btn, "ai_speed", spd))
