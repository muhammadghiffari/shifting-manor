"""Interactive 4-lesson playable tutorial for first-time players."""

from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from shifting_manor.engine.game import Game
from shifting_manor.engine.grid import DIRS, in_bounds, manhattan, rotation_mapping, wing_cells
from shifting_manor.engine.types import CastCharm, Cell, Dir, Leave, Move, ShiftApplied
from shifting_manor.ui import fx, theme

BOARD_RECT = pygame.Rect(48, 108, 576, 576)
MARK_ORDER = (None, "?", "pit", "ghost", "safe")


@dataclass(frozen=True)
class LessonSpec:
    number: int
    title: str
    subtitle: str
    size: int
    mode: str
    pits: frozenset[Cell]
    ghost: Cell | None
    treasure: Cell
    oil: int
    goal_text: str
    steps: tuple[str, ...]
    highlight_cells: tuple[Cell, ...]
    forced_shift_at: int | None = None
    forced_shift_wing: int = 1
    forced_shift_dir: str = "cw"


LESSONS: tuple[LessonSpec, ...] = (
    LessonSpec(
        number=1,
        title="LESSON 1 · LANTERN & BREEZE",
        subtitle="Move safely, read Senses, and mark a suspected Pit.",
        size=4,
        mode="apprentice",
        pits=frozenset({(2, 0), (3, 3)}),
        ghost=None,
        treasure=(1, 2),
        oil=30,
        goal_text="Feel the Breeze at (1,0), right-click (2,0) to mark a Pit, then grab the Heirloom at (1,2)!",
        steps=(
            "1. Start at (0,0). Notice Senses says QUIET — that proves (1,0) and (0,1) are SAFE.",
            "2. Move RIGHT to (1,0) using D / Right Arrow / clicking (1,0). You will feel a BREEZE!",
            "3. A Breeze means a Pit is in an adjacent room. Right-click (2,0) twice to mark it as PIT (X).",
            "4. Move UP to (1,1) then (1,2) to collect the gleaming Heirloom!",
        ),
        highlight_cells=((1, 0), (1, 2)),
    ),
    LessonSpec(
        number=2,
        title="LESSON 2 · DEDUCE & ESCAPE",
        subtitle="Triangulate a Pit from two clues, grab the Heirloom, and Leave at (0,0).",
        size=4,
        mode="apprentice",
        pits=frozenset({(1, 1), (3, 2)}),
        ghost=None,
        treasure=(0, 2),
        oil=30,
        goal_text="Avoid the Pit at (1,1), collect the Heirloom at (0,2), return to (0,0) and press E to ESCAPE!",
        steps=(
            "1. Move UP to (0,1) — you feel a BREEZE (Pit at (1,1) or (0,2)?).",
            "2. Wait! Also check (1,0) — it feels a BREEZE too! Both overlap on (1,1), so (1,1) is the PIT!",
            "3. Move UP from (0,1) to (0,2) safely to grab the Heirloom (you'll feel GLIMMER nearby).",
            "4. Walk back to the golden Entrance (0,0) and press E (or click LEAVE MANOR) to WIN!",
        ),
        highlight_cells=((0, 2), (0, 0)),
    ),
    LessonSpec(
        number=3,
        title="LESSON 3 · BANISH THE GHOST",
        subtitle="Sense Chill, aim your 1-use Charm [C], and hear the Ghost scream!",
        size=4,
        mode="apprentice",
        pits=frozenset({(3, 3)}),
        ghost=(2, 1),
        treasure=(2, 1),
        oil=30,
        goal_text="Stand at (1,1) or (0,1), press C then RIGHT to banish the Ghost at (2,1), then grab the Heirloom!",
        steps=(
            "1. Move UP to (0,1) then RIGHT to (1,1). You feel a green CHILL — the Ghost is adjacent!",
            "2. You have ONE Charm per game. It fires in a straight line all the way to the wall.",
            "3. Press C (or click CHARM), then press RIGHT (D / Right Arrow) to shoot East at (2,1)!",
            "4. Hear the SCREAM (+200 score)! Now step into (2,1) safely to grab the Heirloom!",
        ),
        highlight_cells=((1, 1), (2, 1)),
    ),
    LessonSpec(
        number=4,
        title="LESSON 4 · THE SHIFTING MANOR",
        subtitle="Wings rotate 90° every few moves — and your marks rotate with them!",
        size=6,
        mode="explorer",
        pits=frozenset({(3, 0), (5, 5), (0, 5), (5, 2)}),
        ghost=(4, 5),
        treasure=(3, 1),
        oil=50,
        goal_text="Right-click (3,0) to mark the Pit, make 3 moves to trigger a SE wing rotation, then collect (3,1)!",
        steps=(
            "1. On 6×6 maps, FOYER (bottom-left) NEVER rotates. SE, NW, NE rotate 90° every K moves!",
            "2. Right-click (3,0) in wing SE to place a PIT mark. Notice the golden dashed wing border.",
            "3. Walk to (1,0) -> (2,0) -> (2,1). On move 3, Wing SE rotates 90° CW — watch your mark move to (3,2)!",
            "4. Because the Pit moved away from (3,0) and (3,1) is now safe, step into (3,1) to finish training!",
        ),
        highlight_cells=((3, 0), (3, 1)),
        forced_shift_at=3,
        forced_shift_wing=1,
        forced_shift_dir="cw",
    ),
)


class TutorialScene:
    """Hands-on 4-lesson interactive tutorial with real Game rules & live feedback."""

    def __init__(self, *, on_exit, on_play_real, audio=None) -> None:
        self.on_exit = on_exit
        self.on_play_real = on_play_real
        self.audio = audio
        self.lesson_index = 0
        self.game: Game | None = None
        self.visited: set[Cell] = set()
        self.marks: dict[Cell, str] = {}
        self.percepts = None
        self.facing: Dir = "E"
        self.charm_aim = False
        self.completed = False
        self.failed_msg = ""
        self.shift_done = False
        self.shift_anim_timer = 0.0
        self.shift_anim_marks: dict[Cell, str] = {}
        self.t = 0.0
        self.fx = fx.FXManager()
        self._buttons: dict[str, pygame.Rect] = {}
        self.hover: Cell | None = None
        self.load_lesson(0)

    @property
    def spec(self) -> LessonSpec:
        return LESSONS[self.lesson_index]

    def load_lesson(self, index: int) -> None:
        self.lesson_index = max(0, min(index, len(LESSONS) - 1))
        spec = self.spec
        self.game = Game.from_map(
            spec.mode,
            f"TUTORIAL-{spec.number}",
            pits=spec.pits,
            ghost=spec.ghost,
            treasure=spec.treasure,
            oil=spec.oil,
        )
        self.percepts = self.game.observe()
        self.visited = {self.game.state.agent}
        self.marks = {}
        self.facing = "E"
        self.charm_aim = False
        self.completed = False
        self.failed_msg = ""
        self.shift_done = False
        self.shift_anim_timer = 0.0
        self.shift_anim_marks = {}
        self.fx.clear()
        if spec.number == 4:
            self.marks[(3, 0)] = "?"

    def _cell_size(self) -> int:
        return BOARD_RECT.width // self.spec.size

    def _cell_rect(self, cell: Cell) -> pygame.Rect:
        sz = self._cell_size()
        return pygame.Rect(
            BOARD_RECT.x + cell[0] * sz,
            BOARD_RECT.y + (self.spec.size - 1 - cell[1]) * sz,
            sz,
            sz,
        )

    def _cell_at(self, pos: tuple[int, int]) -> Cell | None:
        if not BOARD_RECT.collidepoint(pos):
            return None
        sz = self._cell_size()
        x = (pos[0] - BOARD_RECT.x) // sz
        y = self.spec.size - 1 - (pos[1] - BOARD_RECT.y) // sz
        cell = (int(x), int(y))
        return cell if in_bounds(cell, self.spec.size) else None

    def handle(self, event, logical_pos: tuple[int, int] | None = None) -> None:
        if event.type == pygame.MOUSEMOTION and logical_pos is not None:
            self.hover = self._cell_at(logical_pos)
            return
        if event.type == pygame.KEYDOWN:
            key = event.key
            if key == pygame.K_ESCAPE:
                self.on_exit()
                return
            if key == pygame.K_r:
                self.load_lesson(self.lesson_index)
                return
            if self.completed and key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                if self.lesson_index < len(LESSONS) - 1:
                    self.load_lesson(self.lesson_index + 1)
                else:
                    self.on_play_real()
                return
            if self.failed_msg:
                if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r):
                    self.load_lesson(self.lesson_index)
                return
            if key == pygame.K_c and self.game and self.game.state.charm_available:
                self.charm_aim = not self.charm_aim
                if self.audio:
                    self.audio.play("ui_click")
                return
            if key == pygame.K_e:
                self._try_leave()
                return
            dir_map: dict[int, Dir] = {
                pygame.K_UP: "N",
                pygame.K_w: "N",
                pygame.K_RIGHT: "E",
                pygame.K_d: "E",
                pygame.K_DOWN: "S",
                pygame.K_s: "S",
                pygame.K_LEFT: "W",
                pygame.K_a: "W",
            }
            if key in dir_map:
                self._act(dir_map[key], charm=self.charm_aim)
                self.charm_aim = False
            elif key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                assert self.game is not None
                target = self.hover or self.game.state.agent
                mark = (None, "?", "pit", "ghost", "safe")[key - pygame.K_0]
                if mark is not None:
                    self.marks[target] = mark
                    if self.audio:
                        self.audio.play("mark")
            return

        if event.type == pygame.MOUSEBUTTONDOWN and logical_pos is not None:
            if event.button == 1:
                for name, rect in self._buttons.items():
                    if rect.collidepoint(logical_pos):
                        self._on_button(name)
                        return
                if self.failed_msg:
                    self.load_lesson(self.lesson_index)
                    return
                cell = self._cell_at(logical_pos)
                if cell is None or self.game is None:
                    return
                if self.charm_aim:
                    d = self._dir_to(self.game.state.agent, cell)
                    if d is not None:
                        self._act(d, charm=True)
                    self.charm_aim = False
                elif cell == self.game.state.entrance and self.game.state.agent == cell:
                    self._try_leave()
                elif manhattan(self.game.state.agent, cell) == 1:
                    d = self._dir_to(self.game.state.agent, cell)
                    if d is not None:
                        self._act(d, charm=False)
            elif event.button == 3:
                cell = self._cell_at(logical_pos)
                if cell is not None:
                    cur = self.marks.get(cell)
                    idx = MARK_ORDER.index(cur) if cur in MARK_ORDER else 0
                    nxt = MARK_ORDER[(idx + 1) % len(MARK_ORDER)]
                    if nxt is None:
                        self.marks.pop(cell, None)
                    else:
                        self.marks[cell] = nxt
                    if self.audio:
                        self.audio.play("mark")

    def _on_button(self, name: str) -> None:
        if self.audio:
            self.audio.play("ui_click")
        if name == "back":
            self.on_exit()
        elif name == "reset":
            self.load_lesson(self.lesson_index)
        elif name == "prev":
            self.load_lesson(self.lesson_index - 1)
        elif name == "next":
            if self.lesson_index < len(LESSONS) - 1:
                self.load_lesson(self.lesson_index + 1)
            else:
                self.on_play_real()
        elif name == "leave":
            self._try_leave()
        elif name == "charm" and self.game and self.game.state.charm_available:
            self.charm_aim = not self.charm_aim
        elif name == "play_now":
            self.on_play_real()
        elif name.startswith("lesson_"):
            self.load_lesson(int(name.split("_")[1]))

    @staticmethod
    def _dir_to(start: Cell, target: Cell) -> Dir | None:
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

    def _try_leave(self) -> None:
        assert self.game is not None
        if self.game.state.agent != self.game.state.entrance:
            self.fx.toast("Walk to Entrance (0,0) first to Leave Manor!", theme.ORANGE, 2.0)
            return
        res = self.game.step(Leave())
        self.percepts = res.percepts
        if self.game.state.outcome == "escaped_treasure":
            self.completed = True
            self.fx.toast("ESCAPED WITH THE HEIRLOOM! Lesson complete!", theme.GOLD, 3.0)
            if self.audio:
                self.audio.play("win")
        else:
            self.failed_msg = (
                "You left empty-handed! Grab the Heirloom first, then return to (0,0) and press E."
            )

    def _act(self, direction: Dir, *, charm: bool) -> None:
        assert self.game is not None
        self.facing = direction
        if charm:
            start = self._cell_rect(self.game.state.agent).center
            dx, dy = DIRS[direction]
            sz = self._cell_size()
            end = (start[0] + dx * sz * self.spec.size, start[1] - dy * sz * self.spec.size)
            self.fx.add_beam(start, end)
            if self.audio:
                self.audio.play("charm_cast")
            res = self.game.step(CastCharm(direction))
        else:
            res = self.game.step(Move(direction))
            if self.audio:
                self.audio.play("step")
        self.percepts = res.percepts
        self.visited.add(self.game.state.agent)

        for ev in res.events:
            name = type(ev).__name__
            if name == "GhostBanished":
                pos = self._cell_rect(ev.cell).center
                self.fx.burst(pos, theme.CYAN, count=24, speed=110.0)
                self.fx.add_popup(pos, "GHOST BANISHED! +200", theme.CYAN, size=22)
                self.fx.trigger_shake(7.0, 0.28)
                if self.audio:
                    self.audio.play("ghost_banish")
            elif name == "PickedUp":
                pos = self._cell_rect(ev.cell).center
                self.fx.burst(pos, theme.GOLD, count=26, speed=105.0)
                self.fx.add_popup(pos, "HEIRLOOM FOUND!", theme.GOLD, size=22)
                if self.audio:
                    self.audio.play("pickup")
            elif name == "ShiftApplied":
                self._apply_mark_rotation(ev)

        # Deterministic lesson-4 scripted shift so the student always experiences rotation clearly
        spec = self.spec
        if (
            spec.forced_shift_at is not None
            and not self.shift_done
            and self.game.state.actions_taken >= spec.forced_shift_at
            and not self.game.state.done
        ):
            mapping = rotation_mapping(spec.forced_shift_wing, spec.forced_shift_dir, 6)
            self.game.state.pits = frozenset(mapping.get(p, p) for p in self.game.state.pits)
            if self.game.state.ghost is not None:
                self.game.state.ghost = mapping.get(self.game.state.ghost, self.game.state.ghost)
            ev = ShiftApplied(spec.forced_shift_wing, spec.forced_shift_dir, mapping)
            self._apply_mark_rotation(ev)
            self.percepts = self.game.observe()
            self.shift_done = True

        if self.game.state.done and self.game.state.outcome in (
            "died_pit",
            "died_ghost",
            "oil_out",
        ):
            cause = {
                "died_pit": "You fell into a Pit! Watch the Breeze clues and try again.",
                "died_ghost": "The Ghost caught you! Sense Chill and press C + direction to banish it.",
                "oil_out": "Your lantern ran out of oil! Press R to retry.",
            }[self.game.state.outcome]
            self.failed_msg = cause
            self.fx.trigger_shake(8.0, 0.3)
            if self.audio:
                self.audio.play("lose")
            return

        # Check lesson win conditions
        if spec.number in (1, 3) and self.game.state.has_treasure:
            self.completed = True
            self.fx.toast("LESSON COMPLETE! Click NEXT LESSON or press Enter.", theme.TEAL, 4.0)
            if self.audio:
                self.audio.play("win")
        elif spec.number == 4 and self.game.state.has_treasure and self.shift_done:
            self.completed = True
            self.fx.toast(
                "TRAINING COMPLETE! You are ready for the Shifting Manor!", theme.GOLD, 4.0
            )
            if self.audio:
                self.audio.play("win")

    def _apply_mark_rotation(self, event: ShiftApplied) -> None:
        self.shift_anim_marks = {c: self.marks[c] for c in event.mapping if c in self.marks}
        self.marks = {event.mapping.get(c, c): m for c, m in self.marks.items()}
        self.shift_anim_timer = 1.0
        self.fx.trigger_shake(7.0, 0.35)
        self.fx.toast("WING SE ROTATED 90° CW — YOUR MARKS ROTATED WITH IT!", theme.GOLD, 3.5)
        if self.audio:
            self.audio.play("shift")

    def update(self, dt: float) -> None:
        self.t += dt
        if self.shift_anim_timer > 0.0:
            self.shift_anim_timer = max(0.0, self.shift_anim_timer - dt)
        if self.game is not None and self.percepts is not None:
            rect = self._cell_rect(self.game.state.agent)
            self.fx.emit_percepts(
                rect,
                breeze=self.percepts.breeze,
                chill=self.percepts.chill,
                glimmer=self.percepts.glimmer,
                dt=dt,
            )
        self.fx.update(dt)

    def draw(self, canvas: pygame.Surface, mouse: tuple[int, int]) -> None:
        assert self.game is not None and self.percepts is not None
        self._buttons = {}
        canvas.fill(theme.BG)

        # Header
        theme.text(canvas, self.spec.title, 30, theme.GOLD, (48, 22), bold=True)
        theme.text(canvas, self.spec.subtitle, 17, theme.MUTED, (48, 58))

        # Step indicator pills top right (clickable to jump to any lesson)
        for i in range(len(LESSONS)):
            pill = pygame.Rect(834 + i * 72, 22, 64, 32)
            active = i == self.lesson_index
            done = i < self.lesson_index or (active and self.completed)
            theme.button(
                canvas,
                pill,
                f"{i + 1}/4",
                selected=active,
                hover=pill.collidepoint(mouse),
                accent=theme.TEAL if done else theme.GOLD,
                size=16,
            )
            self._buttons[f"lesson_{i}"] = pill
        back = pygame.Rect(1148, 22, 100, 32)
        theme.button(canvas, back, "EXIT [Esc]", hover=back.collidepoint(mouse), size=16)
        self._buttons["back"] = back

        # Board
        self._draw_board(canvas)

        # Right panel: Objective, Steps, Senses, Quick Controls
        side = pygame.Rect(648, 108, 600, 576)
        theme.panel(canvas, side, accent_top=theme.TEAL if self.completed else theme.GOLD)

        # Objective callout
        obj_rect = pygame.Rect(side.x + 18, side.y + 18, side.width - 36, 84)
        theme.panel(
            canvas,
            obj_rect,
            color=theme.BG_PANEL_LIGHT,
            border=theme.TEAL if self.completed else theme.GOLD,
            radius=8,
        )
        theme.badge(
            canvas,
            "COMPLETE!" if self.completed else "OBJECTIVE",
            (obj_rect.x + 12, obj_rect.y + 10),
            color=theme.TEAL if self.completed else theme.GOLD,
            size=14,
        )
        lines = theme.wrap(self.spec.goal_text, 17, obj_rect.width - 28)
        for i, line in enumerate(lines[:2]):
            theme.text(
                canvas, line, 17, theme.INK_BRIGHT, (obj_rect.x + 14, obj_rect.y + 38 + i * 21)
            )

        # Step-by-step instructions
        y = obj_rect.bottom + 16
        theme.text(canvas, "STEP-BY-STEP GUIDE", 16, theme.GOLD, (side.x + 20, y), bold=True)
        y += 26
        for step_text in self.spec.steps:
            wrapped = theme.wrap(step_text, 16, side.width - 48)
            for j, line in enumerate(wrapped):
                theme.text(
                    canvas,
                    line,
                    16,
                    theme.INK if j == 0 else theme.MUTED,
                    (side.x + 24, y),
                )
                y += 20
            y += 6

        # Live Senses card inside tutorial
        s_rect = pygame.Rect(side.x + 18, side.bottom - 208, side.width - 36, 118)
        theme.panel(canvas, s_rect, color=theme.BG_PANEL_LIGHT, radius=8)
        theme.text(
            canvas,
            f"LIVE SENSES AT {self.game.state.agent}   ·   OIL {self.game.state.oil}",
            16,
            theme.GOLD,
            (s_rect.x + 14, s_rect.y + 10),
            bold=True,
        )
        p = self.percepts
        sense_items: list[tuple[str, tuple[int, int, int]]] = []
        if p.breeze:
            sense_items.append(("BREEZE — A Pit is in a 4-neighbour room!", theme.CYAN))
        if p.chill:
            sense_items.append(("CHILL — The Ghost is in a 4-neighbour room!", theme.GREEN))
        if p.glimmer:
            sense_items.append(("GLIMMER — The Heirloom is here or adjacent!", theme.GOLD))
        if p.scream:
            sense_items.append(("SCREAM — Ghost banished! Way is clear!", theme.VIOLET))
        if self.spec.number == 4 and not self.shift_done:
            left = max(0, (self.spec.forced_shift_at or 3) - self.game.state.actions_taken)
            sense_items.append(
                (f"RUMBLE — Wing SE rotates 90° CW in {left} move(s)!", theme.ORANGE)
            )
        if not sense_items:
            sense_items.append(("QUIET — No Pit or Ghost in any adjacent room!", theme.TEAL))
        for i, (txt, col) in enumerate(sense_items[:3]):
            sy = s_rect.y + 38 + i * 24
            pygame.draw.circle(canvas, col, (s_rect.x + 22, sy + 8), 5)
            theme.text(canvas, txt, 16, col, (s_rect.x + 36, sy))

        # Action bar at bottom of right panel
        by = side.bottom - 72
        charm_btn = pygame.Rect(side.x + 18, by, 128, 46)
        theme.button(
            canvas,
            charm_btn,
            "AIMING..." if self.charm_aim else "CHARM [C]",
            selected=self.charm_aim,
            disabled=not self.game.state.charm_available,
            hover=charm_btn.collidepoint(mouse),
            accent=theme.VIOLET,
            size=16,
        )
        self._buttons["charm"] = charm_btn

        leave_btn = pygame.Rect(side.x + 154, by, 140, 46)
        at_exit = self.game.state.agent == self.game.state.entrance
        theme.button(
            canvas,
            leave_btn,
            "LEAVE [E]",
            selected=at_exit and self.game.state.has_treasure,
            disabled=not at_exit,
            hover=leave_btn.collidepoint(mouse),
            accent=theme.GOLD,
            size=16,
        )
        self._buttons["leave"] = leave_btn

        reset_btn = pygame.Rect(side.x + 302, by, 108, 46)
        theme.button(canvas, reset_btn, "RETRY [R]", hover=reset_btn.collidepoint(mouse), size=16)
        self._buttons["reset"] = reset_btn

        next_btn = pygame.Rect(side.x + 418, by, 164, 46)
        next_lbl = "START GAME!" if self.lesson_index == len(LESSONS) - 1 else "NEXT LESSON ->"
        theme.button(
            canvas,
            next_btn,
            next_lbl,
            selected=self.completed,
            hover=next_btn.collidepoint(mouse),
            accent=theme.TEAL if self.completed else theme.GOLD,
            size=16,
        )
        self._buttons["next"] = next_btn

        # Failure banner overlay if player walked into hazard
        if self.failed_msg:
            banner = pygame.Rect(
                BOARD_RECT.x + 24, BOARD_RECT.centery - 58, BOARD_RECT.width - 48, 116
            )
            theme.panel(canvas, banner, color=(42, 18, 28), border=theme.RED, radius=12)
            theme.text(
                canvas,
                "TRY AGAIN!",
                26,
                theme.RED,
                (banner.centerx, banner.y + 24),
                anchor="center",
                bold=True,
            )
            for i, line in enumerate(theme.wrap(self.failed_msg, 17, banner.width - 32)[:2]):
                theme.text(
                    canvas,
                    line,
                    17,
                    theme.INK,
                    (banner.centerx, banner.y + 56 + i * 22),
                    anchor="center",
                )
            theme.text(
                canvas,
                "Press R or click anywhere on the board to retry.",
                14,
                theme.MUTED,
                (banner.centerx, banner.bottom - 14),
                anchor="center",
            )

        self.fx.draw(canvas)

    def _draw_board(self, canvas: pygame.Surface) -> None:
        assert self.game is not None
        sz = self._cell_size()
        size = self.spec.size
        ox, oy = self.fx.shake_offset()
        board = pygame.Surface(BOARD_RECT.size)
        board.fill(theme.FLOOR)

        for x in range(size):
            for y in range(size):
                cell = (x, y)
                rect = pygame.Rect(x * sz, (size - 1 - y) * sz, sz, sz)
                fx.draw_stone_tile(
                    board,
                    rect,
                    cell,
                    visited=cell in self.visited,
                    is_entrance=cell == self.game.state.entrance,
                    has_treasure_badge=self.game.state.has_treasure
                    and cell == self.game.state.entrance,
                    show_coords=True,
                )
                # Highlight clickable adjacent rooms
                if manhattan(self.game.state.agent, cell) == 1 and not self.completed:
                    hl = pygame.Surface(rect.size, pygame.SRCALPHA)
                    alpha = 65 if cell == self.hover else 28
                    pygame.draw.rect(
                        hl, (*theme.TEAL, alpha), hl.get_rect().inflate(-8, -8), border_radius=6
                    )
                    board.blit(hl, rect.topleft)

                # Pulsing tutorial target highlights
                if cell in self.spec.highlight_cells and not self.completed:
                    pulse = int(120 + 95 * math.sin(self.t * 4.5))
                    ring = pygame.Surface(rect.size, pygame.SRCALPHA)
                    pygame.draw.rect(
                        ring,
                        (*theme.GOLD, pulse),
                        ring.get_rect().inflate(-8, -8),
                        3,
                        border_radius=8,
                    )
                    board.blit(ring, rect.topleft)

                # Reveal heirloom once glimmer felt or lesson 1/2/3/4 target cell
                if (
                    cell == self.game.state.treasure
                    and not self.game.state.has_treasure
                    and (
                        cell in self.visited
                        or manhattan(self.game.state.agent, cell) <= 1
                        or self.spec.number == 4
                    )
                ):
                    fx.draw_heirloom(board, rect, self.t)

                # Lesson 4 wing SE dashed highlight
                if size == 6 and cell in wing_cells(1, 6):
                    pygame.draw.rect(board, (130, 98, 56), rect.inflate(-3, -3), 1)

        if size == 6:
            k = 3 * sz
            pygame.draw.line(board, theme.GOLD_SOFT, (k, 4), (k, BOARD_RECT.height - 4), 2)
            pygame.draw.line(board, theme.GOLD_SOFT, (4, k), (BOARD_RECT.width - 4, k), 2)
            theme.badge(
                board, "FOYER (FIXED)", (10, BOARD_RECT.height - 28), color=theme.MUTED, size=13
            )
            theme.badge(
                board,
                "WING SE (ROTATES CW)",
                (k + 10, BOARD_RECT.height - 28),
                color=theme.GOLD,
                size=13,
            )

        for cell, mk in self.marks.items():
            if in_bounds(cell, size):
                rect = pygame.Rect(cell[0] * sz, (size - 1 - cell[1]) * sz, sz, sz)
                theme.mark(board, rect, mk)

        # Draw Caretaker
        agent_rect = pygame.Rect(
            self.game.state.agent[0] * sz,
            (size - 1 - self.game.state.agent[1]) * sz,
            sz,
            sz,
        )
        fx.draw_caretaker(
            board,
            agent_rect.center,
            self.facing,
            self.t,
            carrying_treasure=self.game.state.has_treasure,
        )

        # Charm aim lines
        if self.charm_aim:
            c = agent_rect.center
            for dx, dy in DIRS.values():
                for n in range(1, 9, 2):
                    s = (c[0] + dx * 28 * n, c[1] - dy * 28 * n)
                    e = (c[0] + dx * 28 * (n + 1), c[1] - dy * 28 * (n + 1))
                    pygame.draw.line(board, theme.CYAN, s, e, 3)

        # Lesson 4 wing rotation visual tween
        if self.shift_anim_timer > 0.0 and size == 6:
            prog = 1.0 - self.shift_anim_timer
            angle = -90.0 * (prog * prog * (3 - 2 * prog))
            w_surf = pygame.Surface((3 * sz, 3 * sz), pygame.SRCALPHA)
            w_surf.fill((*theme.FLOOR_VISITED, 215))
            pygame.draw.rect(w_surf, (*theme.GOLD, 220), w_surf.get_rect(), 3)
            for cell, mk in self.shift_anim_marks.items():
                lr = pygame.Rect((cell[0] - 3) * sz, (2 - cell[1]) * sz, sz, sz)
                theme.mark(w_surf, lr, mk)
            rot = pygame.transform.rotate(w_surf, angle)
            center = (int(4.5 * sz), int(4.5 * sz))
            board.blit(rot, rot.get_rect(center=center))

        pygame.draw.rect(board, theme.GOLD_SOFT, board.get_rect(), 2)
        canvas.blit(board, (BOARD_RECT.x + ox, BOARD_RECT.y + oy))
