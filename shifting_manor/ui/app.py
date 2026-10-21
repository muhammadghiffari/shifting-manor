"""Pygame launcher. Milestone M0: a window with the title placeholder.

M4 replaces the placeholder scene stack with the playable UI. The engine and
agents stay importable without pygame; only this package imports it.
"""

from __future__ import annotations

import os

LOGICAL_SIZE = (1280, 720)


def _dummy_video_if_headless() -> None:
    if os.environ.get("SDL_VIDEODRIVER") == "dummy":
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


class App:
    """Minimal app loop; scenes arrive in M4."""

    def __init__(
        self, *, audio: bool = True, windowed: bool = True, seed: str = "HAUNT-4F2A"
    ) -> None:
        _dummy_video_if_headless()
        import pygame

        self.pygame = pygame
        self.audio = audio
        self.windowed = windowed
        self.seed = seed
        pygame.display.init()
        pygame.font.init()
        if audio:
            pygame.mixer.init()
        flags = 0
        if not windowed:
            flags |= pygame.FULLSCREEN
        self.screen = pygame.display.set_mode(LOGICAL_SIZE, flags)
        pygame.display.set_caption("Shifting Manor")
        self.clock = pygame.time.Clock()
        self.running = True

    def handle(self, event) -> None:
        pygame = self.pygame
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_q):
                self.running = False
            elif event.key == pygame.K_F11:
                self.windowed = not self.windowed
                flags = 0 if self.windowed else pygame.FULLSCREEN
                self.screen = pygame.display.set_mode(LOGICAL_SIZE, flags)

    def draw(self) -> None:
        pygame = self.pygame
        self.screen.fill((14, 11, 20))
        font = pygame.font.Font(None, 64)
        line = font.render("SHIFTING MANOR", True, (232, 217, 181))
        rect = line.get_rect(center=(LOGICAL_SIZE[0] // 2, LOGICAL_SIZE[1] // 2))
        self.screen.blit(line, rect)
        hint = pygame.font.Font(None, 28).render(
            "M0 scaffolding - press Esc to quit", True, (138, 130, 153)
        )
        self.screen.blit(
            hint, hint.get_rect(center=(LOGICAL_SIZE[0] // 2, LOGICAL_SIZE[1] // 2 + 60))
        )
        pygame.display.flip()

    def run(self, max_frames: int | None = None) -> None:
        pygame = self.pygame
        frames = 0
        while self.running:
            for event in pygame.event.get():
                self.handle(event)
            self.draw()
            self.clock.tick(60)
            frames += 1
            if max_frames is not None and frames >= max_frames:
                break
        pygame.quit()


def main(*, audio: bool = True, windowed: bool = True, seed: str = "HAUNT-4F2A") -> None:
    App(audio=audio, windowed=windowed, seed=seed).run()
