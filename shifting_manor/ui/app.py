"""Playable M4 UI: title, mode select, board with fog, HUD, marks and result.

Only this package imports pygame. Engine/KB/agents/sim stay headless.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass
from math import cos, pi, sin
from typing import TYPE_CHECKING

from shifting_manor.engine.game import Game
from shifting_manor.engine.grid import DIRS, in_bounds, manhattan, wing_cells
from shifting_manor.engine.modes import MODES
from shifting_manor.engine.types import (
    CastCharm,
    Cell,
    Dir,
    Move,
    Percepts,
    ShiftApplied,
)
from shifting_manor.ui import strings, theme

if TYPE_CHECKING:
    import pygame


LOGICAL_SIZE = theme.LOGICAL_SIZE
BOARD_PX = theme.BOARD_PX
CELL = theme.CELL

WING_NAMES = {0: "FOYER", 1: "SE", 2: "NW", 3: "NE"}
MARK_ORDER = (None, "?", "pit", "ghost", "safe")


def _dummy_video_if_headless() -> None:
    if os.environ.get("SDL_VIDEODRIVER") == "dummy":
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def _smooth(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def _direction_to(start: Cell, target: Cell) -> Dir | None:
    dx, dy = target[0] - start[0], target[1] - start[1]
    if dx == 0 and dy > 0:
        return "N"
    if dx == 0 and dy < 0:
        return "S"
    if dy == 0 and dx > 0:
        return "E"
    if dy == 0 and dx < 0:
        return "W"
    return None


@dataclass
class ShiftAnimation:
    wing: int
    direction: str
    mapping: dict[Cell, Cell]
    elapsed: float
    duration: float
    marks: dict[Cell, str]
    dust: list[tuple[int, int]]


class App:
    """One window, four scenes, all input and drawing in one place."""

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
        theme.reset_fonts()
        if audio:
            pygame.mixer.init()
        pygame.key.set_repeat(220, 110)
        self.screen = None
        self.view_rect = pygame.Rect(0, 0, *LOGICAL_SIZE)
        self._set_window()
        self.canvas = pygame.Surface(LOGICAL_SIZE)
        pygame.display.set_caption(strings.TITLE)
        self.clock = pygame.time.Clock()
        self.running = True

        self.scene = "title"
        self.mode_names = list(MODES)
        self.mode_index = 1
        self.game: Game | None = None
        self.percepts = Percepts()
        self.events: list = []
        self.marks: dict[Cell, str] = {}
        self.visited: set[Cell] = set()
        self.charm_aim = False
        self.facing: Dir = "S"
        self.paused = False
        self.shift_anim: ShiftAnimation | None = None
        self.hover: Cell | None = None
        self.result: dict | None = None
        self._glow = self._make_glow()
        self._last_buttons: dict[str, pygame.Rect] = {}

    # -- window -----------------------------------------------------------
    def _set_window(self) -> None:
        pygame = self.pygame
        if self.windowed:
            self.screen = pygame.display.set_mode(LOGICAL_SIZE)
            self.view_rect = pygame.Rect(0, 0, *LOGICAL_SIZE)
        else:
            info = pygame.display.Info()
            width, height = info.current_w, info.current_h
            self.screen = pygame.display.set_mode((width, height), pygame.FULLSCREEN)
            scale = min(width / LOGICAL_SIZE[0], height / LOGICAL_SIZE[1])
            size = (int(LOGICAL_SIZE[0] * scale), int(LOGICAL_SIZE[1] * scale))
            self.view_rect = pygame.Rect(
                (width - size[0]) // 2, (height - size[1]) // 2, size[0], size[1]
            )

    def _to_logical(self, pos: tuple[int, int]) -> tuple[int, int]:
        x = (pos[0] - self.view_rect.x) * LOGICAL_SIZE[0] / self.view_rect.width
        y = (pos[1] - self.view_rect.y) * LOGICAL_SIZE[1] / self.view_rect.height
        return int(x), int(y)

    def _present(self) -> None:
        pygame = self.pygame
        if self.view_rect.size == LOGICAL_SIZE:
            self.screen.blit(self.canvas, (0, 0))
        else:
            scaled = pygame.transform.scale(self.canvas, self.view_rect.size)
            self.screen.fill((0, 0, 0))
            self.screen.blit(scaled, self.view_rect.topleft)
        pygame.display.flip()

    # -- game lifecycle ---------------------------------------------------
    def start_game(self, mode: str | None = None, seed: str | None = None) -> None:
        mode = mode or self.mode_names[self.mode_index]
        self.seed = seed or self.seed
        self.game = Game(mode, self.seed)
        self.percepts = self.game.observe()
        self.events = []
        self.marks = {}
        self.visited = {self.game.state.agent}
        self.charm_aim = False
        self.facing = "S"
        self.paused = False
        self.shift_anim = None
        self.hover = None
        self.result = None
        self.scene = "play"

    def new_seed(self) -> str:
        self.seed = f"HAUNT-{random.randrange(16**4):04X}"
        return self.seed

    def restart(self, *, same_seed: bool = True) -> None:
        if self.game is None:
            self.start_game()
            return
        mode = self.game.mode.name
        if not same_seed:
            self.new_seed()
        self.start_game(mode, self.seed)

    def _finish(self) -> None:
        assert self.game is not None
        from shifting_manor.sim.runner import run_game

        par = run_game(self.game.mode.name, self.seed, "b4").actions
        self.result = {
            "outcome": self.game.state.outcome or "stalled",
            "score": self.game.score(),
            "stars": self.game.stars(par),
        }
        self.paused = False
        self.shift_anim = None
        self.scene = "result"

    # -- input ------------------------------------------------------------
    def handle(self, event) -> None:
        pygame = self.pygame
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
            self.windowed = not self.windowed
            self._set_window()
            return
        if event.type == pygame.MOUSEMOTION:
            logical = self._to_logical(event.pos)
            self.hover = self._cell_at(logical) if self.scene == "play" else None
            return
        if self.scene == "title":
            self._handle_title(event)
        elif self.scene == "modes":
            self._handle_modes(event)
        elif self.scene == "play":
            self._handle_play(event)
        elif self.scene == "result":
            self._handle_result(event)

    def _key(self, event) -> int | None:
        pygame = self.pygame
        return event.key if event.type == pygame.KEYDOWN else None

    def _handle_title(self, event) -> None:
        pygame = self.pygame
        key = self._key(event)
        if key in (pygame.K_ESCAPE, pygame.K_q):
            self.running = False
        elif (
            key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER)
            or event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
        ):
            self.scene = "modes"

    def _handle_modes(self, event) -> None:
        pygame = self.pygame
        key = self._key(event)
        if key in (pygame.K_ESCAPE, pygame.K_q):
            self.scene = "title"
            if key == pygame.K_q:
                self.running = False
            return
        if key in (pygame.K_UP, pygame.K_w, pygame.K_a):
            self.mode_index = (self.mode_index - 1) % len(self.mode_names)
        elif key in (pygame.K_DOWN, pygame.K_s, pygame.K_d):
            self.mode_index = (self.mode_index + 1) % len(self.mode_names)
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3):
            self.mode_index = key - pygame.K_1
        elif key == pygame.K_n:
            self.new_seed()
        elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
            self.start_game(self.mode_names[self.mode_index], self.seed)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self._to_logical(event.pos)
            for i, rect in enumerate(self._mode_rects()):
                if rect.collidepoint(pos):
                    self.mode_index = i
                    return
            if self._last_buttons.get("begin", self._begin_rect()).collidepoint(pos):
                self.start_game(self.mode_names[self.mode_index], self.seed)

    def _handle_play(self, event) -> None:
        pygame = self.pygame
        key = self._key(event)
        if self.shift_anim is not None and event.type in (
            pygame.KEYDOWN,
            pygame.MOUSEBUTTONDOWN,
        ):
            self.shift_anim = None
            return
        if self.paused:
            if key == pygame.K_ESCAPE:
                self.paused = False
            elif key in (pygame.K_r,):
                self.restart()
            elif key in (pygame.K_m,):
                self.scene = "title"
            elif key in (pygame.K_q,):
                self.running = False
            return
        if key in (pygame.K_ESCAPE,):
            self.paused = True
            return
        if key == pygame.K_q:
            self.running = False
            return
        if key == pygame.K_F11:
            return
        if key == pygame.K_r:
            self.restart()
            return
        if key == pygame.K_n:
            self.restart(same_seed=False)
            return
        if key == pygame.K_c:
            if self.game and self.game.state.charm_available:
                self.charm_aim = not self.charm_aim
            return
        if key in (pygame.K_UP, pygame.K_w):
            self._move_or_charm("N")
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self._move_or_charm("E")
        elif key in (pygame.K_DOWN, pygame.K_s):
            self._move_or_charm("S")
        elif key in (pygame.K_LEFT, pygame.K_a):
            self._move_or_charm("W")
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
            mark = (None, "?", "pit", "ghost", "safe")[key - pygame.K_0]
            if mark is not None:
                self.marks[self.game.state.agent] = mark  # type: ignore[union-attr]
        elif key == pygame.K_0:
            self.marks.pop(self.game.state.agent, None)  # type: ignore[union-attr]

        if event.type == pygame.MOUSEBUTTONDOWN:
            pos = self._to_logical(event.pos)
            cell = self._cell_at(pos)
            if cell is None:
                return
            if event.button == 3:
                current = self.marks.get(cell)
                index = MARK_ORDER.index(current) if current in MARK_ORDER else 0
                nxt = MARK_ORDER[(index + 1) % len(MARK_ORDER)]
                if nxt is None:
                    self.marks.pop(cell, None)
                else:
                    self.marks[cell] = nxt
                return
            if event.button != 1:
                return
            assert self.game is not None
            if self.charm_aim:
                direction = _direction_to(self.game.state.agent, cell)
                if direction is not None:
                    self._act(direction, charm=True)
                else:
                    self.charm_aim = False
                return
            if manhattan(self.game.state.agent, cell) == 1:
                direction = _direction_to(self.game.state.agent, cell)
                if direction is not None:
                    self._act(direction)

    def _handle_result(self, event) -> None:
        pygame = self.pygame
        key = self._key(event)
        if key in (pygame.K_r, pygame.K_RETURN, pygame.K_KP_ENTER):
            self.restart()
        elif key == pygame.K_n:
            self.restart(same_seed=False)
        elif key in (pygame.K_m, pygame.K_ESCAPE):
            self.scene = "title"
        elif key == pygame.K_q:
            self.running = False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self._to_logical(event.pos)
            if self._last_buttons.get("replay", self._result_buttons()[0]).collidepoint(pos):
                self.restart()
            elif self._last_buttons.get("new", self._result_buttons()[1]).collidepoint(pos):
                self.restart(same_seed=False)
            elif self._last_buttons.get("menu", self._result_buttons()[2]).collidepoint(pos):
                self.scene = "title"

    def _move_or_charm(self, direction: Dir) -> None:
        if self.charm_aim:
            self._act(direction, charm=True)
            self.charm_aim = False
        else:
            self._act(direction)

    def _act(self, direction: Dir, *, charm: bool = False) -> None:
        assert self.game is not None
        if self.game.state.done:
            return
        self.facing = direction
        if charm:
            self._after_step(self.game.step(CastCharm(direction)))
            self.charm_aim = False
            return
        self._after_step(self.game.step(Move(direction)))

    def _after_step(self, step_result) -> None:
        assert self.game is not None
        self.percepts = step_result.percepts
        self.events = list(step_result.events)
        self.visited.add(self.game.state.agent)
        for event in step_result.events:
            if isinstance(event, ShiftApplied):
                pre = {c: self.marks[c] for c in event.mapping if c in self.marks}
                self.marks = {event.mapping.get(c, c): mark for c, mark in self.marks.items()}
                rng = random.Random(f"{self.seed}:{event.wing}:{event.direction}")
                dust = [
                    (rng.randrange(6, 3 * CELL - 6), rng.randrange(6, 3 * CELL - 6))
                    for _ in range(24)
                ]
                self.shift_anim = ShiftAnimation(
                    event.wing,
                    event.direction,
                    dict(event.mapping),
                    0.0,
                    0.85,
                    pre,
                    dust,
                )
        if step_result.done or self.game.state.done:
            self._finish()

    # -- update -----------------------------------------------------------
    def update(self, dt: float) -> None:
        if self.shift_anim is not None:
            self.shift_anim.elapsed += dt
            if self.shift_anim.elapsed >= self.shift_anim.duration:
                self.shift_anim = None

    # -- geometry ---------------------------------------------------------
    def _board_rect(self) -> pygame.Rect:
        pygame = self.pygame
        size = self.game.info().size if self.game else 6
        px = size * CELL
        return pygame.Rect(48 + (BOARD_PX - px) // 2, 96 + (BOARD_PX - px) // 2, px, px)

    def _cell_rect(self, cell: Cell) -> pygame.Rect:
        assert self.game is not None
        size = self.game.info().size
        board = self._board_rect()
        x, y = cell
        return self.pygame.Rect(board.x + x * CELL, board.y + (size - 1 - y) * CELL, CELL, CELL)

    def _cell_at(self, pos: tuple[int, int]) -> Cell | None:
        assert self.game is not None
        size = self.game.info().size
        board = self._board_rect()
        if not board.collidepoint(pos):
            return None
        x = (pos[0] - board.x) // CELL
        y = size - 1 - (pos[1] - board.y) // CELL
        cell = (int(x), int(y))
        return cell if in_bounds(cell, size) else None

    def _mode_rects(self) -> list[pygame.Rect]:
        pygame = self.pygame
        width, gap = 330, 30
        x0 = (LOGICAL_SIZE[0] - (3 * width + 2 * gap)) // 2
        return [pygame.Rect(x0 + i * (width + gap), 190, width, 300) for i in range(3)]

    def _begin_rect(self) -> pygame.Rect:
        return self.pygame.Rect(540, 550, 200, 56)

    def _result_panel_rect(self) -> pygame.Rect:
        return self.pygame.Rect(560, 170, 672, 478)

    def _result_board_rect(self) -> pygame.Rect:
        return self.pygame.Rect(48, 172, 480, 480)

    def _result_buttons(self) -> list[pygame.Rect]:
        pygame = self.pygame
        panel = self._result_panel_rect()
        width, gap = 190, 24
        x0 = panel.centerx - (3 * width + 2 * gap) // 2
        return [pygame.Rect(x0 + i * (width + gap), panel.bottom - 70, width, 52) for i in range(3)]

    # -- drawing ----------------------------------------------------------
    def draw(self) -> None:
        self.canvas.fill(theme.BG)
        if self.scene == "title":
            self._draw_title()
        elif self.scene == "modes":
            self._draw_modes()
        elif self.scene == "play":
            self._draw_play()
        elif self.scene == "result":
            self._draw_result()

    def run(self, max_frames: int | None = None, screenshot: str | None = None) -> None:
        pygame = self.pygame
        frames = 0
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            for event in pygame.event.get():
                self.handle(event)
            self.update(dt)
            self.draw()
            self._present()
            frames += 1
            if max_frames is not None and frames >= max_frames:
                break
        if screenshot:
            self.draw()
            pygame.image.save(self.canvas, screenshot)
        pygame.quit()

    # -- backgrounds ------------------------------------------------------
    def _draw_vignette(self) -> None:
        pygame = self.pygame
        for i in range(8):
            alpha = 12 + i * 3
            pygame.draw.rect(
                self.canvas,
                (8, 6, 12),
                (i * 24, i * 14, LOGICAL_SIZE[0] - i * 48, LOGICAL_SIZE[1] - i * 28),
                24,
                border_radius=26,
            )  # type: ignore[arg-type]
            del alpha
        # faint floor-plan silhouette
        for x in range(0, LOGICAL_SIZE[0], 120):
            for y in range(0, LOGICAL_SIZE[1], 120):
                if (x // 120 + y // 120) % 2:
                    pygame.draw.rect(self.canvas, (20, 16, 27), (x + 10, y + 10, 100, 100), 1)

    # -- title ------------------------------------------------------------
    def _draw_title(self) -> None:
        pygame = self.pygame
        self._draw_vignette()
        cx = LOGICAL_SIZE[0] // 2
        theme.text(
            self.canvas, strings.TITLE, 104, theme.GOLD, (cx, 190), anchor="center", bold=True
        )
        theme.text(self.canvas, strings.TAGLINE, 28, theme.MUTED, (cx, 265), anchor="center")
        # a tiny lit manor plan
        board = pygame.Rect(cx - 192, 320, 384, 192)
        for x in range(4):
            for y in range(2):
                rect = pygame.Rect(board.x + x * 96, board.y + y * 96, 96, 96)
                pygame.draw.rect(
                    self.canvas,
                    theme.FLOOR_VISITED if (x, y) == (1, 0) else theme.FLOOR,
                    rect,
                    border_radius=2,
                )
                pygame.draw.rect(self.canvas, theme.WALL, rect, 1)
        spot = (board.x + 96 + 48, board.y + 48)
        glow = pygame.transform.scale(self._glow, (150, 150))
        self.canvas.blit(glow, glow.get_rect(center=spot))
        pygame.draw.circle(self.canvas, theme.ORANGE, spot, 20)
        pygame.draw.circle(self.canvas, theme.INK, spot, 20, 2)
        theme.text(self.canvas, strings.PRESS_ENTER, 34, theme.INK, (cx, 570), anchor="center")
        theme.text(self.canvas, strings.TITLE_HINT, 22, theme.MUTED, (cx, 630), anchor="center")
        theme.text(
            self.canvas, "M4 · playable build", 18, (90, 82, 104), (cx, 690), anchor="center"
        )

    # -- mode select ------------------------------------------------------
    def _draw_modes(self) -> None:
        pygame = self.pygame
        self._draw_vignette()
        theme.text(self.canvas, strings.MODE_TITLE, 54, theme.GOLD, (80, 80), bold=True)
        theme.text(self.canvas, strings.MODE_HINT, 22, theme.MUTED, (82, 138))
        mouse = self._to_logical(pygame.mouse.get_pos())
        for i, rect in enumerate(self._mode_rects()):
            name = self.mode_names[i]
            selected = i == self.mode_index
            hover = rect.collidepoint(mouse)
            theme.button(self.canvas, rect, "", selected=selected, hover=hover)
            theme.text(
                self.canvas,
                name.upper(),
                40,
                theme.GOLD if selected else theme.INK,
                (rect.centerx, rect.y + 52),
                anchor="center",
                bold=True,
            )
            mode = MODES[name]
            facts = f"{mode.size}x{mode.size} · {mode.pits} pits\n{mode.oil} oil\n" + (
                "no shifts" if mode.shift_every is None else f"shift every {mode.shift_every}"
            )
            for j, line in enumerate(facts.split("\n")):
                theme.text(
                    self.canvas,
                    line,
                    24,
                    theme.INK if selected else theme.MUTED,
                    (rect.centerx, rect.y + 118 + j * 30),
                    anchor="center",
                )
            for j, line in enumerate(strings.MODE_BLURB[name].split("\n")[1:]):
                theme.text(
                    self.canvas,
                    line,
                    20,
                    theme.MUTED,
                    (rect.centerx, rect.y + 230 + j * 24),
                    anchor="center",
                )
        theme.text(
            self.canvas,
            f"{strings.HUD_SEED}: {self.seed}",
            26,
            theme.INK,
            (80, 512),
        )
        begin = self._begin_rect()
        theme.button(
            self.canvas, begin, strings.MODE_BEGIN, selected=True, hover=begin.collidepoint(mouse)
        )
        self._last_buttons["begin"] = begin

    # -- play -------------------------------------------------------------
    def _draw_play(self) -> None:
        assert self.game is not None
        self._draw_vignette()
        self._draw_board()
        self._draw_hud()
        self._draw_senses()
        self._draw_legend()
        if self.charm_aim:
            self._draw_charm_aim()
        if self.shift_anim is not None:
            self._draw_shift_anim(self.shift_anim)
        if self.shift_anim is not None:
            theme.text(
                self.canvas,
                "THE MANOR SHIFTS",
                30,
                theme.GOLD,
                (self._board_rect().centerx, 60),
                anchor="center",
                bold=True,
            )
        if self.paused:
            self._draw_pause()

    def _draw_board(self, reveal: dict | None = None, dest=None) -> None:
        pygame = self.pygame
        assert self.game is not None
        board_rect = self._board_rect()
        size = self.game.info().size
        board = pygame.Surface(board_rect.size)
        board.fill(theme.FLOOR)
        pits = set(reveal.get("pits", ())) if reveal else set()
        ghost = reveal.get("ghost") if reveal else None
        treasure = reveal.get("treasure") if reveal else None

        for x in range(size):
            for y in range(size):
                cell = (x, y)
                rect = pygame.Rect(x * CELL, (size - 1 - y) * CELL, CELL, CELL)
                visited = cell in self.visited
                pygame.draw.rect(
                    board,
                    theme.FLOOR_VISITED if visited else (31, 25, 40),
                    rect.inflate(-4, -4),
                    border_radius=3,
                )
                pygame.draw.rect(board, (58, 46, 68), rect, 1)
                if visited:
                    for dx, dy in ((-12, 4), (10, 14)):
                        pygame.draw.ellipse(
                            board,
                            (90, 74, 104),
                            (rect.centerx + dx - 5, rect.centery + dy - 3, 10, 6),
                            1,
                        )
                if cell == self.game.state.entrance:
                    door = pygame.Rect(rect.centerx - 22, rect.bottom - 14, 44, 10)
                    pygame.draw.rect(board, theme.GOLD, door, border_radius=2)
                    pygame.draw.rect(board, (120, 84, 42), door, 1, border_radius=2)
                if cell in pits:
                    self._draw_mark_on(board, rect, "pit")
                if cell == ghost:
                    self._draw_mark_on(board, rect, "ghost")
                if cell == treasure:
                    self._draw_treasure(board, rect)

        # wing rune borders run after the fog so the plan stays legible in the dark
        if size == 6:
            k = 3 * CELL
            for p in range(24, board_rect.height, 48):
                pygame.draw.circle(board, (94, 76, 112), (k, p), 2)
                pygame.draw.circle(board, (94, 76, 112), (p, k), 2)
            pygame.draw.line(board, (88, 70, 104), (k, 4), (k, board_rect.height - 4), 2)
            pygame.draw.line(board, (88, 70, 104), (4, k), (board_rect.width - 4, k), 2)
        pygame.draw.rect(board, (76, 60, 90), board.get_rect(), 2)
        for cell, mark in self.marks.items():
            if in_bounds(cell, size):
                self._draw_mark_on(board, self._local_rect(cell), mark)
        self._draw_player(board)
        target = pygame.Rect(dest) if dest is not None else board_rect
        if target.size != board_rect.size:
            board = pygame.transform.smoothscale(board, target.size)
        self.canvas.blit(board, target.topleft)

    def _local_rect(self, cell: Cell) -> pygame.Rect:
        assert self.game is not None
        size = self.game.info().size
        return self.pygame.Rect(cell[0] * CELL, (size - 1 - cell[1]) * CELL, CELL, CELL)

    def _draw_fog(self, board) -> None:
        pygame = self.pygame
        assert self.game is not None
        size = self.game.info().size
        player = self.game.state.agent
        mask = pygame.Surface(board.get_size(), pygame.SRCALPHA)
        for x in range(size):
            for y in range(size):
                cell = (x, y)
                visited = cell in self.visited
                alpha = 112 if visited else 238
                distance = manhattan(player, cell)
                light = max(0.0, 1.0 - distance / 2.6)
                alpha = max(0, int(alpha - 255 * light))
                rect = pygame.Rect(x * CELL, (size - 1 - y) * CELL, CELL, CELL)
                pygame.draw.rect(mask, (*theme.FOG, alpha), rect)
        board.blit(mask, (0, 0))
        glow = pygame.transform.scale(self._glow, (300, 300))
        local = self._local_rect(player)
        board.blit(glow, glow.get_rect(center=local.center), special_flags=pygame.BLEND_RGBA_ADD)

    def _draw_player(self, board) -> None:
        pygame = self.pygame
        assert self.game is not None
        local = self._local_rect(self.game.state.agent)
        center = local.center
        pygame.draw.circle(board, (255, 176, 96), center, 22)
        pygame.draw.circle(board, (46, 30, 20), center, 22, 3)
        offsets = {"N": (0, -12), "S": (0, 12), "E": (12, 0), "W": (-12, 0)}
        ox, oy = offsets[self.facing]
        pygame.draw.polygon(
            board,
            theme.INK,
            [
                (center[0] + ox, center[1] + oy),
                (center[0] + ox * 0.35 - oy * 0.35, center[1] + oy * 0.35 + ox * 0.35),
                (center[0] + ox * 0.35 + oy * 0.35, center[1] + oy * 0.35 - ox * 0.35),
            ],
        )

    def _draw_mark_on(self, surface, rect, mark: str) -> None:
        pygame = self.pygame
        c = rect.center
        if mark == "safe":
            pygame.draw.lines(
                surface,
                theme.TEAL,
                False,
                [(c[0] - 16, c[1]), (c[0] - 4, c[1] + 12), (c[0] + 18, c[1] - 14)],
                5,
            )
        elif mark == "pit":
            pygame.draw.circle(surface, theme.ORANGE, c, 19, 3)
            pygame.draw.line(
                surface, theme.ORANGE, (c[0] - 11, c[1] - 11), (c[0] + 11, c[1] + 11), 5
            )
            pygame.draw.line(
                surface, theme.ORANGE, (c[0] + 11, c[1] - 11), (c[0] - 11, c[1] + 11), 5
            )
        elif mark == "ghost":
            pygame.draw.circle(surface, theme.CYAN, (c[0], c[1] - 5), 15, 3)
            pygame.draw.line(surface, theme.CYAN, (c[0] - 15, c[1] + 8), (c[0] - 15, c[1] + 18), 3)
            pygame.draw.line(surface, theme.CYAN, (c[0], c[1] + 10), (c[0], c[1] + 20), 3)
            pygame.draw.line(surface, theme.CYAN, (c[0] + 15, c[1] + 8), (c[0] + 15, c[1] + 18), 3)
        elif mark == "?":
            theme.text(surface, "?", 42, theme.VIOLET, c, anchor="center", bold=True)

    def _draw_treasure(self, surface, rect) -> None:
        pygame = self.pygame
        c = rect.center
        points = [(c[0], c[1] - 18), (c[0] + 16, c[1]), (c[0], c[1] + 18), (c[0] - 16, c[1])]
        pygame.draw.polygon(surface, theme.GOLD, points)
        pygame.draw.polygon(surface, (120, 84, 42), points, 2)

    def _draw_charm_aim(self) -> None:
        pygame = self.pygame
        assert self.game is not None
        center = self._cell_rect(self.game.state.agent).center
        for dx, dy in DIRS.values():
            step_px = 24
            for n in range(1, 8, 2):
                start = (center[0] + dx * step_px * n, center[1] - dy * step_px * n)
                end = (
                    center[0] + dx * step_px * (n + 1),
                    center[1] - dy * step_px * (n + 1),
                )
                pygame.draw.line(self.canvas, (196, 160, 96), start, end, 2)
        theme.text(
            self.canvas,
            "Aim the charm: arrow key or click a direction",
            22,
            theme.GOLD,
            (self._board_rect().centerx, self._board_rect().bottom + 14),
            anchor="midtop",
        )

    def _draw_shift_anim(self, anim: ShiftAnimation) -> None:
        pygame = self.pygame
        assert self.game is not None
        cells = wing_cells(anim.wing, 6)
        if not cells:
            return
        origin_x = min(c[0] for c in cells) * CELL
        origin_y = min(6 - 1 - c[1] for c in cells) * CELL
        surface = pygame.Surface((3 * CELL, 3 * CELL), pygame.SRCALPHA)
        surface.fill((*theme.FLOOR_VISITED, 225))
        for i in (1, 2):
            pygame.draw.line(surface, (156, 124, 80, 120), (i * CELL, 0), (i * CELL, 3 * CELL), 2)
            pygame.draw.line(surface, (156, 124, 80, 120), (0, i * CELL), (3 * CELL, i * CELL), 2)
        pygame.draw.rect(surface, (196, 160, 96, 170), surface.get_rect(), 2)
        for cell, mark in anim.marks.items():
            local = pygame.Rect(
                (cell[0] - origin_x // CELL) * CELL,
                (6 - 1 - cell[1] - origin_y // CELL) * CELL,
                CELL,
                CELL,
            )
            self._draw_mark_on(surface, local, mark)
        for dx, dy in anim.dust:
            pygame.draw.circle(surface, (210, 190, 160), (dx, dy), 2)
        progress = _smooth(anim.elapsed / anim.duration)
        angle = (90 if anim.direction == "ccw" else -90) * progress
        rotated = pygame.transform.rotate(surface, angle)
        board = self._board_rect()
        center = (board.x + origin_x + 1.5 * CELL, board.y + origin_y + 1.5 * CELL)
        self.canvas.blit(rotated, rotated.get_rect(center=center))
        wing_rect = pygame.Rect(board.x + origin_x, board.y + origin_y, 3 * CELL, 3 * CELL)
        pygame.draw.rect(self.canvas, theme.GOLD, wing_rect, 3, border_radius=4)

    # -- HUD / sidebar ----------------------------------------------------
    def _draw_hud(self) -> None:
        pygame = self.pygame
        assert self.game is not None
        rect = pygame.Rect(648, 38, 600, 190)
        theme.panel(self.canvas, rect)
        st = self.game.state
        theme.text(self.canvas, strings.HUD_OIL, 20, theme.MUTED, (rect.x + 20, rect.y + 16))
        bar = pygame.Rect(rect.x + 78, rect.y + 18, 220, 18)
        pygame.draw.rect(self.canvas, (16, 12, 22), bar, border_radius=9)
        ratio = st.oil / max(1, st.start_oil)
        color = theme.GREEN if ratio > 0.5 else theme.GOLD if ratio > 0.25 else theme.RED
        pygame.draw.rect(
            self.canvas,
            color,
            (bar.x, bar.y, int(bar.width * max(0.0, ratio)), bar.height),
            border_radius=9,
        )
        theme.text(
            self.canvas, f"{st.oil}/{st.start_oil}", 20, theme.INK, (bar.right + 12, bar.y - 1)
        )
        theme.text(
            self.canvas,
            f"{strings.HUD_SCORE}: {self.game.score()}",
            26,
            theme.GOLD,
            (rect.right - 20, rect.y + 12),
            anchor="topright",
            bold=True,
        )
        charm = strings.HUD_CHARM_READY if st.charm_available else strings.HUD_CHARM_SPENT
        theme.text(
            self.canvas,
            f"{strings.HUD_CHARM}: {charm}",
            22,
            theme.TEAL if st.charm_available else theme.MUTED,
            (rect.x + 20, rect.y + 54),
        )
        held = strings.HUD_HEIRLOOM_HELD if st.has_treasure else strings.HUD_HEIRLOOM_LOST
        theme.text(
            self.canvas,
            f"{strings.HUD_HEIRLOOM}: {held}",
            22,
            theme.GOLD if st.has_treasure else theme.MUTED,
            (rect.x + 20, rect.y + 84),
        )
        theme.text(
            self.canvas,
            f"{strings.HUD_SEED}: {self.seed}",
            20,
            theme.MUTED,
            (rect.x + 20, rect.y + 118),
        )
        theme.text(
            self.canvas,
            f"{strings.HUD_POSITION.format(x=st.agent[0], y=st.agent[1])}",
            20,
            theme.MUTED,
            (rect.x + 20, rect.y + 146),
        )

        clock_x = rect.right - 100
        clock_y = rect.y + 104
        pygame.draw.circle(self.canvas, (16, 12, 22), (clock_x, clock_y), 52)
        pygame.draw.circle(self.canvas, theme.WALL, (clock_x, clock_y), 52, 2)
        status = self.game.shift_status()
        if status is None:
            theme.text(
                self.canvas,
                strings.HUD_SHIFT_STEADY,
                18,
                theme.MUTED,
                (clock_x, clock_y - 8),
                anchor="center",
            )
            k = self.game.mode.shift_every
            if k:
                theme.text(
                    self.canvas,
                    strings.HUD_SHIFT_EVERY.format(k=k),
                    15,
                    (100, 92, 116),
                    (clock_x, clock_y + 16),
                    anchor="center",
                )
        else:
            wing, direction, left = status
            theme.text(
                self.canvas,
                WING_NAMES.get(wing, str(wing)),
                22,
                theme.GOLD,
                (clock_x, clock_y - 18),
                anchor="center",
                bold=True,
            )
            theme.text(
                self.canvas,
                "CW" if direction == "cw" else "CCW",
                18,
                theme.ORANGE,
                (clock_x, clock_y + 4),
                anchor="center",
            )
            theme.text(
                self.canvas,
                strings.HUD_SHIFT_SOON.format(n=left),
                16,
                theme.INK,
                (clock_x, clock_y + 26),
                anchor="center",
            )
        theme.text(
            self.canvas,
            strings.HUD_SHIFT,
            16,
            theme.MUTED,
            (clock_x, rect.y + 166),
            anchor="midtop",
        )

    def _draw_senses(self) -> None:
        pygame = self.pygame
        rect = pygame.Rect(648, 244, 600, 178)
        theme.panel(self.canvas, rect)
        theme.text(
            self.canvas, strings.SENSES_TITLE, 24, theme.GOLD, (rect.x + 20, rect.y + 14), bold=True
        )
        lines: list[tuple[str, tuple[int, int, int]]] = []
        p = self.percepts
        if p.breeze:
            lines.append((strings.SENSE_BREEZE, theme.CYAN))
        if p.chill:
            lines.append((strings.SENSE_CHILL, theme.GREEN))
        if p.glimmer:
            lines.append((strings.SENSE_GLIMMER, theme.GOLD))
        if p.rumble is not None:
            lines.append((strings.SENSE_RUMBLE.format(n=p.rumble.in_actions), theme.ORANGE))
        if p.scream:
            lines.append((strings.SENSE_SCREAM, theme.VIOLET))
        if p.bump:
            lines.append((strings.SENSE_BUMP, theme.MUTED))
        if not lines:
            lines.append((strings.SENSE_QUIET, theme.MUTED))
        for i, (line, color) in enumerate(lines[:4]):
            y = rect.y + 54 + i * 29
            pygame.draw.circle(self.canvas, color, (rect.x + 28, y + 9), 6)
            theme.text(self.canvas, line, 22, theme.INK, (rect.x + 44, y))

    def _draw_legend(self) -> None:
        pygame = self.pygame
        rect = pygame.Rect(648, 438, 600, 244)
        theme.panel(self.canvas, rect)
        theme.text(
            self.canvas, strings.LEGEND_TITLE, 20, theme.GOLD, (rect.x + 20, rect.y + 12), bold=True
        )
        items = (
            ("safe", strings.LEGEND_SAFE),
            ("pit", strings.LEGEND_PIT),
            ("ghost", strings.LEGEND_GHOST),
            ("?", strings.LEGEND_UNKNOWN),
        )
        for i, (mark, label) in enumerate(items):
            box = pygame.Rect(rect.x + 22 + i * 138, rect.y + 44, 40, 40)
            self._draw_mark_on(self.canvas, box, mark)
            theme.text(self.canvas, label, 18, theme.MUTED, (box.right + 6, box.y + 10))
        for i, line in enumerate(strings.CONTROLS):
            theme.text(self.canvas, line, 18, theme.MUTED, (rect.x + 20, rect.y + 98 + i * 24))

    def _draw_pause(self) -> None:
        pygame = self.pygame
        overlay = pygame.Surface(LOGICAL_SIZE, pygame.SRCALPHA)
        overlay.fill((8, 6, 12, 210))
        self.canvas.blit(overlay, (0, 0))
        rect = pygame.Rect(440, 250, 400, 220)
        theme.panel(self.canvas, rect, color=theme.BG_PANEL_LIGHT)
        theme.text(
            self.canvas,
            strings.PAUSED,
            64,
            theme.GOLD,
            (rect.centerx, rect.y + 50),
            anchor="center",
            bold=True,
        )
        theme.text(
            self.canvas,
            strings.PAUSE_HINT,
            22,
            theme.INK,
            (rect.centerx, rect.y + 130),
            anchor="center",
        )

    # -- result -----------------------------------------------------------
    def _draw_result(self) -> None:
        pygame = self.pygame
        assert self.game is not None and self.result is not None
        self._draw_vignette()
        theme.text(
            self.canvas,
            strings.RESULT_TITLE,
            40,
            theme.MUTED,
            (LOGICAL_SIZE[0] // 2, 52),
            anchor="center",
        )
        outcome = self.result["outcome"]
        color = theme.GOLD if outcome.startswith("escaped") else theme.RED
        theme.text(
            self.canvas,
            strings.RESULT_OUTCOME.get(outcome, outcome.upper()),
            46,
            color,
            (LOGICAL_SIZE[0] // 2, 108),
            anchor="center",
            bold=True,
        )
        self._draw_board(reveal=self.game.reveal(), dest=self._result_board_rect())
        panel = self._result_panel_rect()
        theme.panel(self.canvas, panel)
        stars = self.result["stars"]
        for i in range(3):
            self._draw_star(
                self.canvas,
                (panel.centerx + (i - 1) * 64, panel.y + 48),
                24,
                filled=i < stars,
            )
        theme.text(
            self.canvas,
            f"{strings.RESULT_SCORE}: {self.result['score']}",
            40,
            theme.INK,
            (panel.centerx, panel.y + 84),
            anchor="center",
            bold=True,
        )
        stats = [
            (strings.RESULT_ACTIONS, self.game.state.actions_taken),
            (strings.RESULT_OIL, self.game.state.oil),
            (strings.RESULT_CHARMS, self.game.state.charms_cast),
            (strings.RESULT_RULES, len(self.marks)),
            (strings.RESULT_STARS, stars),
        ]
        for i, (label, value) in enumerate(stats):
            y = panel.y + 130 + i * 30
            theme.text(self.canvas, label, 22, theme.MUTED, (panel.x + 30, y))
            theme.text(
                self.canvas, str(value), 22, theme.INK, (panel.right - 30, y), anchor="topright"
            )
        theme.text(
            self.canvas,
            f"{strings.RESULT_SEED}: {self.seed}",
            22,
            theme.MUTED,
            (panel.x + 30, panel.y + 310),
        )
        theme.text(
            self.canvas,
            f"{strings.RESULT_MODE}: {self.game.mode.name}",
            22,
            theme.MUTED,
            (panel.x + 30, panel.y + 340),
        )
        theme.text(
            self.canvas,
            strings.RESULT_HINT,
            18,
            (100, 92, 116),
            (panel.centerx, panel.y + 386),
            anchor="center",
        )
        buttons = self._result_buttons()
        labels = (strings.RESULT_REPLAY, strings.RESULT_NEW, strings.RESULT_MENU)
        mouse = self._to_logical(pygame.mouse.get_pos())
        for i, (rect, label) in enumerate(zip(buttons, labels)):
            theme.button(self.canvas, rect, label, hover=rect.collidepoint(mouse))
            self._last_buttons[("replay", "new", "menu")[i]] = rect

    def _draw_star(self, surface, center: tuple[int, int], radius: int, *, filled: bool) -> None:
        pygame = self.pygame
        points = [
            (
                center[0] + cos(-pi / 2 + i * pi / 5) * (radius if i % 2 == 0 else radius * 0.45),
                center[1] + sin(-pi / 2 + i * pi / 5) * (radius if i % 2 == 0 else radius * 0.45),
            )
            for i in range(10)
        ]
        if filled:
            pygame.draw.polygon(surface, theme.GOLD, points)
            pygame.draw.polygon(surface, (120, 84, 42), points, 2)
        else:
            pygame.draw.polygon(surface, (92, 80, 104), points, 2)

    # -- utility ----------------------------------------------------------
    def _make_glow(self) -> pygame.Surface:
        pygame = self.pygame
        size = 320
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        center = (size // 2, size // 2)
        for radius in range(size // 2, 0, -2):
            alpha = int(34 * (1.0 - radius / (size / 2)) ** 2)
            if alpha:
                pygame.draw.circle(surface, (255, 176, 96, alpha), center, radius)
        return surface


def main(
    *,
    audio: bool = True,
    windowed: bool = True,
    seed: str = "HAUNT-4F2A",
    mode: str | None = None,
    frames: int | None = None,
    screenshot: str | None = None,
) -> None:
    """Real entry point used by ``python -m shifting_manor``."""
    app = App(audio=audio, windowed=windowed, seed=seed)
    if mode:
        app.start_game(mode, seed)
    if screenshot and frames is None:
        frames = 1
    app.run(max_frames=frames, screenshot=screenshot)
