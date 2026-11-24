"""Watch AI: replay one stored agent trace with beliefs, log, proofs and rules."""

from __future__ import annotations

import pygame

from shifting_manor.kb.facts import Fact
from shifting_manor.kb.rules import RULES
from shifting_manor.trace import (
    Belief,
    LogRow,
    ProofNode,
    StepTrace,
    TraceStore,
    firing_cells,
    format_firing,
    format_item,
)
from shifting_manor.ui import fx, strings, theme

# Dedicated Thought Banner above the board (y=68..120) so row 5 is NEVER covered!
THOUGHT_BAR = pygame.Rect(48, 66, 576, 52)
BOARD = pygame.Rect(48, 126, 576, 576)
SIDE = pygame.Rect(648, 66, 600, 636)
CONTENT = pygame.Rect(648, 112, 600, 444)
FOOTER = pygame.Rect(648, 564, 600, 138)
TABS = (
    pygame.Rect(648, 66, 190, 38),
    pygame.Rect(842, 66, 224, 38),
    pygame.Rect(1070, 66, 178, 38),
)


def _smooth(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _fit(value: str, size: int, width: int, *, bold: bool = False) -> str:
    font = theme.font(size, bold)
    if font.size(value)[0] <= width:
        return value
    out = value
    while out and font.size(out + "...")[0] > width:
        out = out[:-1]
    return out + "..."


def _dashed_rect(surface, color, rect: pygame.Rect, *, width: int = 2, dash: int = 8) -> None:
    for x in range(rect.left, rect.right, dash * 2):
        pygame.draw.line(
            surface, color, (x, rect.top), (min(x + dash, rect.right), rect.top), width
        )
        pygame.draw.line(
            surface, color, (x, rect.bottom), (min(x + dash, rect.right), rect.bottom), width
        )
    for y in range(rect.top, rect.bottom, dash * 2):
        pygame.draw.line(
            surface, color, (rect.left, y), (rect.left, min(y + dash, rect.bottom)), width
        )
        pygame.draw.line(
            surface, color, (rect.right, y), (rect.right, min(y + dash, rect.bottom)), width
        )


class WatchView:
    """All Watch AI state and drawing. The App only forwards events."""

    def __init__(
        self,
        store: TraceStore,
        *,
        to_logical,
        on_exit,
        on_fire=None,
        seed: str = "",
        show_coords: bool = True,
    ) -> None:
        self.store = store
        self.to_logical = to_logical
        self.on_exit = on_exit
        self.on_fire = on_fire
        self.seed = seed or store.seed
        self.show_coords = show_coords
        self.index = 0
        self.elapsed = 0.0
        self.playing = True
        self.speed = 1.0
        self.tab = 0
        self.overlay = True
        self.overlay_alpha = 1.0
        self.log_new_only = True
        self.log_scroll = 0
        self.log_auto = True
        self.kb_scroll = 0
        self.selected_rule: str | None = None
        self.selected_cells: tuple = ()
        self.hover_cell = None
        self.proof: ProofNode | None = None
        self.proof_step = 0
        self.proof_scroll = 0
        self.proof_message = ""
        self.expanded: set[int] = set()
        self._proof_stack: list[ProofNode] = []
        self._buttons: dict[str, pygame.Rect] = {}
        self._log_hits: list[tuple[pygame.Rect, LogRow]] = []
        self._kb_hits: list[tuple[pygame.Rect, str]] = []
        self._proof_hits: list[tuple[pygame.Rect, ProofNode]] = []
        self._last_visible_new = 0
        self.rows_new: dict[int, list[LogRow]] = {step.index: [] for step in store.steps}
        self.rows_all: dict[int, list[LogRow]] = {step.index: [] for step in store.steps}
        for row in store.log_rows():
            self.rows_all[row.step_index].append(row)
            if row.new:
                self.rows_new[row.step_index].append(row)
        self._t = 0.0

    # -- step / playback --------------------------------------------------
    @property
    def step(self) -> StepTrace:
        return self.store.steps[self.index]

    def duration(self, step: StepTrace | None = None) -> float:
        step = step or self.step
        base = max(0.65, min(2.0, len(step.firings) * 0.12))
        return base / max(0.5, self.speed)

    def visible_new(self) -> int:
        n = len(self.step.firings)
        if self.elapsed >= self.duration():
            return n
        interval = 0.12 / max(0.5, self.speed)
        return min(n, int(self.elapsed / interval) + 1)

    def set_step(self, index: int, *, playing: bool = False) -> None:
        self.index = max(0, min(index, len(self.store.steps) - 1))
        self.elapsed = self.duration()
        self.playing = playing
        self.proof = None
        self.proof_message = ""
        self.selected_cells = ()
        self.log_auto = True
        self._last_visible_new = len(self.step.firings)

    def advance(self) -> None:
        if self.index < len(self.store.steps) - 1:
            self.index += 1
            self.elapsed = 0.0
            self._last_visible_new = 0
            self.log_auto = True
        else:
            self.elapsed = self.duration()
            self.playing = False

    def step_back(self) -> None:
        if self.index > 0:
            self.set_step(self.index - 1, playing=False)
        else:
            self.set_step(0, playing=False)

    def finished(self) -> bool:
        return (
            self.index == len(self.store.steps) - 1
            and self.elapsed >= self.duration()
            and not self.playing
        )

    def restart(self) -> None:
        self.index = 0
        self.elapsed = 0.0
        self.playing = True
        self.log_auto = True
        self.proof = None
        self.proof_message = ""
        self.selected_cells = ()
        self._last_visible_new = 0

    def update(self, dt: float) -> None:
        self._t += dt
        target = 1.0 if self.overlay else 0.0
        if self.overlay_alpha < target:
            self.overlay_alpha = min(1.0, self.overlay_alpha + dt * 5.0)
        elif self.overlay_alpha > target:
            self.overlay_alpha = max(0.0, self.overlay_alpha - dt * 5.0)
        if not self.playing or self.proof is not None:
            return
        self.elapsed += dt
        visible = self.visible_new()
        changed = visible > self._last_visible_new
        self._last_visible_new = visible
        if changed and self.on_fire is not None:
            self.on_fire()
        if self.elapsed >= self.duration():
            if self.index < len(self.store.steps) - 1:
                self.advance()
            else:
                self.playing = False

    # -- input ------------------------------------------------------------
    def handle(self, event) -> None:
        if event.type == pygame.KEYDOWN:
            self._key(event.key)
            return
        if event.type == pygame.MOUSEMOTION:
            logical = self.to_logical(event.pos)
            self.hover_cell = self._cell_at(logical)
            return
        if event.type == pygame.MOUSEWHEEL:
            self._wheel(event.y)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._click(self.to_logical(event.pos))

    def _cycle_speed(self, direction: int) -> None:
        speeds = (0.5, 1.0, 2.0, 4.0)
        i = min(range(len(speeds)), key=lambda k: abs(speeds[k] - self.speed))
        self.speed = speeds[(i + direction) % len(speeds)]

    def _key(self, key: int) -> None:
        if key == pygame.K_ESCAPE:
            if self.proof is not None or self.proof_message:
                self.proof = None
                self.proof_message = ""
            else:
                self.on_exit()
            return
        if key == pygame.K_SPACE:
            if self.index == len(self.store.steps) - 1 and self.elapsed >= self.duration():
                self.restart()
            else:
                self.playing = not self.playing
            return
        if key == pygame.K_LEFT:
            self.step_back()
            return
        if key == pygame.K_RIGHT:
            if self.elapsed < self.duration() - 1e-6:
                self.elapsed = self.duration()
            else:
                self.advance()
            return
        if key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self._cycle_speed(1)
            return
        if key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self._cycle_speed(-1)
            return
        if key == pygame.K_r:
            self.restart()
            return
        if key == pygame.K_b:
            self.overlay = not self.overlay
            return
        if key == pygame.K_TAB:
            self.tab = (self.tab + 1) % 3
            return
        if key == pygame.K_l:
            self.tab = 1
            return
        if key == pygame.K_k:
            self.tab = 2
            return
        if key == pygame.K_f and self.tab == 1:
            self.log_new_only = not self.log_new_only
            self.log_auto = True
            return
        if key == pygame.K_w:
            self._open_room_proof(self.hover_cell)
            return
        self.elapsed = self.duration()

    def _wheel(self, amount: int) -> None:
        if self.proof is not None:
            self.proof_scroll = max(0, self.proof_scroll - amount * 34)
            return
        if self.tab == 1:
            self.log_scroll = max(0, self.log_scroll - amount * 34)
            self.log_auto = self.log_scroll >= getattr(self, "_log_max_scroll", 0)
        elif self.tab == 2:
            self.kb_scroll = max(0, self.kb_scroll - amount * 34)

    def _click(self, pos: tuple[int, int]) -> None:
        for i, rect in enumerate(TABS):
            if rect.collidepoint(pos):
                self.tab = i
                return
        if self.proof is not None or self.proof_message:
            close = self._buttons.get("close")
            if close is not None and close.collidepoint(pos):
                self.proof = None
                self.proof_message = ""
                return
            for rect, node in self._proof_hits:
                if rect.collidepoint(pos):
                    if node.id in self.expanded:
                        self.expanded.discard(node.id)
                    elif node.children:
                        self.expanded.add(node.id)
                    return
            return
        for name, rect in self._buttons.items():
            if not rect.collidepoint(pos):
                continue
            if name == "play":
                self._key(pygame.K_SPACE)
            elif name == "back_step":
                self.step_back()
            elif name == "fwd_step":
                self._key(pygame.K_RIGHT)
            elif name == "speed":
                self._cycle_speed(1)
            elif name == "overlay":
                self.overlay = not self.overlay
            elif name == "why":
                self._open_room_proof(self.hover_cell or self.step.position)
            elif name == "log_filter":
                self.log_new_only = not self.log_new_only
                self.log_auto = True
            elif name == "menu":
                self.on_exit()
            return
        if self.tab == 1:
            for rect, row in self._log_hits:
                if rect.collidepoint(pos):
                    self.proof = self.store.proof(row.step_index, row.firing)
                    self.proof_step = row.step_index
                    self.proof_scroll = 0
                    self.proof_message = ""
                    self.expanded = set()
                    self.playing = False
                    return
        if self.tab == 2:
            for rect, rule_id in self._kb_hits:
                if rect.collidepoint(pos):
                    self.selected_rule = rule_id
                    _, last = self.store.rule_stats(self.index)
                    firing = last.get(rule_id)
                    self.selected_cells = firing_cells(firing) if firing else ()
                    return
        cell = self._cell_at(pos)
        if cell is not None:
            self._open_room_proof(cell)

    def _open_room_proof(self, cell) -> None:
        if cell is None:
            return
        labels = {b.cell: b for b in self.step.beliefs}
        belief = labels.get(cell)
        if belief is None:
            return
        priority = ("Safe", "Pit", "Ghost", "NoPit", "NoGhost", "NoTreasure", "Visited")
        fact = next(
            (f for name in priority for f in self.step.facts if f.name == name and f.cell == cell),
            None,
        )
        if fact is None:
            self.proof = None
            self.proof_message = strings.WATCH_WHY_EMPTY
            self.proof_step = self.index
            self.proof_scroll = 0
            self.playing = False
            return
        self.proof = self.store.proof(self.index, fact)
        self.proof_step = self.index
        self.proof_scroll = 0
        self.proof_message = ""
        self.expanded = set()
        self.playing = False

    # -- geometry ---------------------------------------------------------
    def _cell_px(self) -> int:
        return BOARD.width // self.store.size

    def _cell_rect(self, cell) -> pygame.Rect:
        size = self.store.size
        cpx = self._cell_px()
        return pygame.Rect(BOARD.x + cell[0] * cpx, BOARD.y + (size - 1 - cell[1]) * cpx, cpx, cpx)

    def _cell_at(self, pos) -> tuple[int, int] | None:
        if not BOARD.collidepoint(pos):
            return None
        cpx = self._cell_px()
        x = (pos[0] - BOARD.x) // cpx
        y = self.store.size - 1 - (pos[1] - BOARD.y) // cpx
        cell = (int(x), int(y))
        return cell if 0 <= cell[0] < self.store.size and 0 <= cell[1] < self.store.size else None

    # -- drawing ----------------------------------------------------------
    def draw(self, canvas: pygame.Surface) -> None:
        self.canvas = canvas
        canvas.fill(theme.BG)
        self._buttons = {}
        self._log_hits = []
        self._kb_hits = []
        self._proof_hits = []
        self._draw_header()
        self._draw_thought()
        self._draw_board()
        self._draw_tabs()
        if self.tab == 0:
            self._draw_trace()
        elif self.tab == 1:
            self._draw_log()
        else:
            self._draw_kb()
        self._draw_footer()
        self._draw_hover_tooltip()
        if self.proof is not None or self.proof_message:
            self._draw_proof()

    def _draw_header(self) -> None:
        title_rect = theme.text(
            self.canvas, strings.WATCH_TITLE, 28, theme.GOLD, (48, 18), bold=True
        )
        theme.badge(
            self.canvas,
            f"{self.store.agent.upper()} · {self.store.mode.upper()} · {self.seed}",
            (title_rect.right + 16, title_rect.centery),
            color=theme.CYAN,
            anchor="midleft",
            size=15,
        )
        theme.badge(
            self.canvas,
            strings.WATCH_STEP.format(step=self.index + 1, total=len(self.store.steps)),
            (1110, 22),
            color=theme.GOLD,
            anchor="topright",
            size=16,
        )
        menu = pygame.Rect(1134, 16, 114, 34)
        theme.button(
            self.canvas, menu, "MENU [Esc]", hover=menu.collidepoint(self._mouse()), size=15
        )
        self._buttons["menu"] = menu

    def _draw_thought(self) -> None:
        text = self.step.thought or "..."
        theme.panel(
            self.canvas,
            THOUGHT_BAR,
            color=theme.BG_PANEL_LIGHT,
            border=theme.GOLD,
            radius=8,
        )
        theme.badge(
            self.canvas,
            strings.WATCH_THOUGHT,
            (THOUGHT_BAR.x + 10, THOUGHT_BAR.centery),
            color=theme.GOLD,
            size=13,
            anchor="midleft",
        )
        lines = theme.wrap(text, 16, THOUGHT_BAR.width - 156)
        if len(lines) == 1:
            theme.text(
                self.canvas,
                lines[0],
                16,
                theme.INK_BRIGHT,
                (THOUGHT_BAR.x + 146, THOUGHT_BAR.centery),
                anchor="midleft",
            )
        else:
            for i, line in enumerate(lines[:2]):
                theme.text(
                    self.canvas,
                    line,
                    15,
                    theme.INK_BRIGHT,
                    (THOUGHT_BAR.x + 146, THOUGHT_BAR.y + 8 + i * 19),
                )

    def _draw_board(self) -> None:
        size = self.store.size
        cpx = self._cell_px()
        step = self.step
        board = pygame.Surface(BOARD.size)
        board.fill(theme.FLOOR)
        visited = step.visited
        for x in range(size):
            for y in range(size):
                cell = (x, y)
                rect = pygame.Rect(x * cpx, (size - 1 - y) * cpx, cpx, cpx)
                fx.draw_stone_tile(
                    board,
                    rect,
                    cell,
                    visited=cell in visited,
                    is_entrance=cell == self.store.entrance,
                    show_coords=self.show_coords,
                )
        if size == 6:
            k = 3 * cpx
            for p in range(24, board.get_height(), 48):
                pygame.draw.circle(board, (112, 92, 134), (k, p), 2)
                pygame.draw.circle(board, (112, 92, 134), (p, k), 2)
            pygame.draw.line(board, (96, 78, 118), (k, 4), (k, board.get_height() - 4), 2)
            pygame.draw.line(board, (96, 78, 118), (4, k), (board.get_width() - 4, k), 2)
        pygame.draw.rect(board, theme.WALL_LIGHT, board.get_rect(), 2)

        if self.overlay_alpha > 0.01:
            layer = pygame.Surface(BOARD.size, pygame.SRCALPHA)
            for belief in step.beliefs:
                self._draw_belief(layer, belief)
            board.blit(layer, (0, 0))
        if step.shift is not None:
            self._draw_shift(board, step.shift)
        self._draw_highlights(board)
        self._draw_agent(board)
        self.canvas.blit(board, BOARD.topleft)

    def _draw_belief(self, layer, belief: Belief) -> None:
        cpx = self._cell_px()
        rect = pygame.Rect(
            belief.cell[0] * cpx,
            (self.store.size - 1 - belief.cell[1]) * cpx,
            cpx,
            cpx,
        )
        alpha = int(255 * self.overlay_alpha)
        if belief.label in ("safe", "pit", "ghost"):
            theme.mark(layer, rect, belief.label, alpha)
        elif belief.risk > 0.01 or belief.label in ("no-pit", "no-ghost", "no-treasure"):
            color = self._risk_color(belief.risk)
            fill = pygame.Surface(rect.size, pygame.SRCALPHA)
            fill.fill((*color, int(58 * self.overlay_alpha)))
            layer.blit(fill, rect.topleft)
            theme.mark(layer, rect, "?", int(120 * self.overlay_alpha))
            theme.text(
                layer,
                f"{100 * belief.risk:.0f}%",
                14,
                (*color, int(220 * self.overlay_alpha)),
                (rect.centerx, rect.bottom - 8),
                anchor="midbottom",
                bold=True,
            )
        elif belief.label == "unknown":
            theme.mark(layer, rect, "?", int(45 * self.overlay_alpha))
        if belief.stale:
            dashed = pygame.Surface(rect.size, pygame.SRCALPHA)
            _dashed_rect(
                dashed,
                (*theme.GOLD, int(220 * self.overlay_alpha)),
                dashed.get_rect().inflate(-10, -10),
                width=2,
                dash=7,
            )
            layer.blit(dashed, rect.topleft)

    @staticmethod
    def _risk_color(risk: float) -> tuple[int, int, int]:
        if risk < 0.1:
            return theme.TEAL
        if risk < 0.3:
            return theme.GOLD
        if risk < 0.6:
            return theme.ORANGE
        return theme.RED

    def _draw_shift(self, board, shift) -> None:
        if self.elapsed > 1.5:
            return
        alpha = int(210 * (1 - self.elapsed / 1.5))
        wing = {new for _, new in shift.mapping}
        if not wing:
            return
        cpx = self._cell_px()
        xs = [c[0] for c in wing]
        ys = [c[1] for c in wing]
        size = self.store.size
        rect = pygame.Rect(
            min(xs) * cpx,
            (size - 1 - max(ys)) * cpx,
            (max(xs) - min(xs) + 1) * cpx,
            (max(ys) - min(ys) + 1) * cpx,
        )
        _dashed_rect(board, (*theme.GOLD, alpha), rect.inflate(-4, -4), width=3, dash=10)
        label = strings.WATCH_SHIFT.format(
            n=shift.shift_index,
            wing=("FOYER", "SE", "NW", "NE")[shift.wing] if shift.wing < 4 else shift.wing,
            direction=shift.direction.upper(),
        )
        theme.text(
            board, label, 18, theme.GOLD, (rect.centerx, rect.y + 8), anchor="midtop", bold=True
        )
        import random

        rng = random.Random(f"{self.seed}:{shift.shift_index}")
        for _ in range(22):
            dx = rng.randrange(rect.left + 8, rect.right - 8)
            dy = rng.randrange(rect.top + 24, rect.bottom - 8)
            r = 2 + rng.randrange(3)
            pygame.draw.circle(board, (210, 190, 160, alpha), (dx, dy), r)

    def _draw_highlights(self, board) -> None:
        cpx = self._cell_px()
        cells: set[tuple[int, int]] = set()
        if self.tab == 0:
            visible = self.step.firings[: self.visible_new()]
            if visible:
                cells.update(firing_cells(visible[-1]))
            if self.step.gamble_candidates:
                cells.update(c.cell for c in self.step.gamble_candidates)
        if self.tab == 2:
            cells.update(self.selected_cells)
        for cell in cells:
            rect = pygame.Rect(
                cell[0] * cpx,
                (self.store.size - 1 - cell[1]) * cpx,
                cpx,
                cpx,
            )
            pygame.draw.rect(board, theme.GOLD, rect.inflate(-6, -6), 3, border_radius=4)
        if self.hover_cell is not None:
            hrect = pygame.Rect(
                self.hover_cell[0] * cpx,
                (self.store.size - 1 - self.hover_cell[1]) * cpx,
                cpx,
                cpx,
            )
            pygame.draw.rect(board, theme.CYAN, hrect.inflate(-3, -3), 2, border_radius=4)
        if self.tab == 0 and self.step.gamble_candidates:
            for candidate in self.step.gamble_candidates[:6]:
                rect = pygame.Rect(
                    candidate.cell[0] * cpx,
                    (self.store.size - 1 - candidate.cell[1]) * cpx,
                    cpx,
                    cpx,
                )
                theme.text(
                    board,
                    f"{100 * candidate.risk:.0f}%",
                    16,
                    theme.ORANGE,
                    (rect.centerx, rect.centery + 20),
                    anchor="center",
                    bold=True,
                )

    def _draw_agent(self, board) -> None:
        step = self.step
        local = self._cell_rect(step.position).move(-BOARD.x, -BOARD.y)
        after = self._cell_rect(step.after_position).move(-BOARD.x, -BOARD.y)
        duration = self.duration()
        if step.after_position != step.position and self.elapsed > duration * 0.55:
            t = _smooth((self.elapsed - duration * 0.55) / max(0.01, duration * 0.35))
            center = (
                int(local.centerx + (after.centerx - local.centerx) * t),
                int(local.centery + (after.centery - local.centery) * t),
            )
        else:
            center = after.center if self.elapsed >= duration else local.center
        direction = getattr(step.action, "dir", None) or "S"
        fx.draw_caretaker(board, center, direction, self._t, ai_mode=True)

    def _draw_hover_tooltip(self) -> None:
        if self.hover_cell is None or self.proof is not None:
            return
        belief = self.step.belief_by_cell.get(self.hover_cell)
        if belief is None:
            return
        lines = [
            (
                f"Belief: {belief.label.upper()}",
                theme.TEAL if belief.label == "safe" else theme.GOLD,
            ),
            (
                strings.WATCH_RISK.format(
                    risk=100 * belief.risk,
                    pit=100 * belief.pit_risk,
                    ghost=100 * belief.ghost_risk,
                ),
                self._risk_color(belief.risk),
            ),
            ("Click room to open Why? proof tree", theme.MUTED),
        ]
        if belief.stale:
            lines.insert(1, ("Transported by R16 wing shift", theme.GOLD))
        theme.draw_tooltip(
            self.canvas,
            self._mouse(),
            f"Room ({self.hover_cell[0]}, {self.hover_cell[1]})",
            lines,
        )

    def _draw_tabs(self) -> None:
        labels = ("TRACE", "INFERENCE LOG", "RULES (24)")
        for i, (rect, label) in enumerate(zip(TABS, labels)):
            theme.button(self.canvas, rect, label, selected=i == self.tab, size=16)

    def _draw_trace(self) -> None:
        theme.panel(self.canvas, CONTENT)
        x = CONTENT.x + 14
        y = CONTENT.y + 10
        theme.text(
            self.canvas,
            strings.WATCH_STEP.format(step=self.index + 1, total=len(self.store.steps)),
            18,
            theme.GOLD,
            (x, y),
            bold=True,
        )
        theme.text(
            self.canvas,
            f"pos {self.step.position} · oil {self.step.oil} · action {self.step.action}",
            15,
            theme.MUTED,
            (CONTENT.right - 14, y + 2),
            anchor="topright",
        )
        y += 28
        theme.text(self.canvas, strings.WATCH_PERCEPTS, 14, theme.MUTED, (x, y))
        self._draw_percept_icons(x, y + 18)
        y += 64
        theme.text(self.canvas, "FIRINGS · NEW THIS TURN", 14, theme.MUTED, (x, y))
        y += 20
        visible = self.step.firings[: self.visible_new()]
        gy = CONTENT.bottom - 96
        newest = len(visible) - 1
        drawn_firings = 0
        used_lines = 0
        max_lines = max(1, (gy - 4 - y) // 18)
        for i, firing in enumerate(visible):
            flines = theme.wrap(format_firing(firing), 15, CONTENT.width - 34)
            if (
                used_lines + len(flines) > max_lines - (1 if i < len(visible) - 1 else 0)
                and drawn_firings > 0
            ):
                break
            color = theme.INK_BRIGHT if i == newest else theme.MUTED
            for line in flines:
                theme.text(self.canvas, line, 15, color, (x, y + used_lines * 18))
                used_lines += 1
            drawn_firings += 1
        if drawn_firings < len(visible):
            theme.text(
                self.canvas,
                f"... {len(visible) - drawn_firings} more (see Inference Log tab)",
                14,
                theme.MUTED,
                (x, y + used_lines * 18),
            )
        if not visible:
            theme.text(self.canvas, "No new conclusions this turn.", 15, theme.MUTED, (x, y))
        theme.text(self.canvas, strings.WATCH_GAMBLES, 14, theme.MUTED, (x, gy))
        if self.step.gamble_candidates:
            for i, candidate in enumerate(self.step.gamble_candidates[:4]):
                line = (
                    f"{format_item(Fact('Cell', candidate.cell))}  "
                    f"risk {100 * candidate.risk:.0f}%  utility {candidate.utility:.1f}"
                )
                theme.text(
                    self.canvas,
                    _fit(line, 15, CONTENT.width - 34),
                    15,
                    theme.INK,
                    (x, gy + 20 + i * 18),
                )
        else:
            theme.text(self.canvas, strings.WATCH_NO_GAMBLE, 15, theme.MUTED, (x, gy + 20))

    def _draw_percept_icons(self, x: int, y: int) -> None:
        p = self.step.percepts
        items = [
            ("breeze", p.breeze, theme.CYAN),
            ("chill", p.chill, theme.GREEN),
            ("glimmer", p.glimmer, theme.GOLD),
            ("rumble", p.rumble is not None, theme.ORANGE),
            ("scream", p.scream, theme.VIOLET),
            (
                "quiet",
                not any((p.breeze, p.chill, p.glimmer, p.rumble, p.scream, p.bump)),
                theme.TEAL,
            ),
        ]
        for i, (name, active, color) in enumerate(items):
            box = pygame.Rect(x + i * 94, y, 82, 30)
            pygame.draw.rect(
                self.canvas,
                theme.BG_PANEL_LIGHT if active else theme.BG_PANEL,
                box,
                border_radius=6,
            )
            pygame.draw.rect(self.canvas, color if active else theme.WALL, box, 2, border_radius=6)
            self._percept_icon(box, name, color if active else (74, 66, 86))
            theme.text(
                self.canvas,
                name,
                12,
                color if active else (85, 78, 96),
                (box.centerx, box.bottom + 3),
                anchor="midtop",
                bold=active,
            )

    def _percept_icon(self, box, name: str, color) -> None:
        c = box.center
        if name == "breeze":
            for k in range(2):
                pygame.draw.arc(
                    self.canvas,
                    color,
                    (c[0] - 20 + k * 5, c[1] - 7, 24, 15),
                    0.2,
                    2.7,
                    2,
                )
        elif name == "chill":
            pygame.draw.circle(self.canvas, color, (c[0], c[1] - 2), 8, 2)
            for dx in (-8, 0, 8):
                pygame.draw.line(
                    self.canvas, color, (c[0] + dx, c[1] + 6), (c[0] + dx, c[1] + 11), 2
                )
        elif name == "glimmer":
            points = [(c[0], c[1] - 10), (c[0] + 10, c[1]), (c[0], c[1] + 10), (c[0] - 10, c[1])]
            pygame.draw.polygon(self.canvas, color, points, 2)
        elif name == "rumble":
            for r in (5, 9, 13):
                pygame.draw.circle(self.canvas, color, c, r, 1)
        elif name == "scream":
            pygame.draw.polygon(
                self.canvas,
                color,
                [(c[0] - 10, c[1] + 8), (c[0], c[1] - 10), (c[0] + 10, c[1] + 8)],
                1,
            )
        else:
            pygame.draw.circle(self.canvas, color, c, 5, 1)

    def _draw_log(self) -> None:
        theme.panel(self.canvas, CONTENT)
        x = CONTENT.x + 14
        y = CONTENT.y + 10
        theme.text(self.canvas, strings.WATCH_LOG_TAB, 18, theme.GOLD, (x, y), bold=True)
        filt = pygame.Rect(CONTENT.right - 144, y - 2, 130, 26)
        theme.button(
            self.canvas,
            filt,
            strings.WATCH_LOG_NEW if self.log_new_only else strings.WATCH_LOG_ALL,
            selected=not self.log_new_only,
            hover=filt.collidepoint(self._mouse()),
            size=13,
        )
        self._buttons["log_filter"] = filt
        y += 32
        view = pygame.Rect(x, y, CONTENT.width - 28, CONTENT.bottom - y - 12)
        rows = self._visible_log()
        if not rows:
            theme.text(self.canvas, strings.WATCH_LOG_EMPTY, 16, theme.MUTED, (x, y + 4))
            self._log_max_scroll = 0
            return
        laid: list[tuple[str, object, int, tuple[str, ...] | None]] = []
        cursor = 0
        last_step = -1
        for step_index, row in rows:
            if step_index != last_step:
                laid.append(("head", step_index, cursor, None))
                cursor += 22
                last_step = step_index
            prefix = "" if row.new else "· "
            lines = tuple(theme.wrap(prefix + row.text, 15, view.width - 8))
            laid.append(("row", row, cursor, lines))
            cursor += 18 * len(lines)
        total = cursor
        self._log_max_scroll = max(0, total - view.height)
        if self.log_auto:
            self.log_scroll = self._log_max_scroll
        self.log_scroll = max(0, min(self.log_scroll, self._log_max_scroll))
        base_y = view.y - self.log_scroll
        for kind, item, offset, lines in laid:
            yy = base_y + offset
            height = 22 if kind == "head" else 18 * len(lines)
            if yy + height < view.y or yy > view.bottom:
                continue
            if kind == "head":
                theme.text(self.canvas, f"TURN {item + 1}", 15, theme.GOLD, (x, yy), bold=True)
                pygame.draw.line(self.canvas, theme.WALL, (x + 78, yy + 8), (view.right, yy + 8), 1)
            else:
                row: LogRow = item  # type: ignore[assignment]
                color = theme.INK if row.new else theme.MUTED
                rect = pygame.Rect(x, yy, view.width, height - 1)
                if rect.collidepoint(self._mouse()):
                    pygame.draw.rect(self.canvas, theme.BG_PANEL_LIGHT, rect, border_radius=3)
                for j, line in enumerate(lines):
                    theme.text(self.canvas, line, 15, color, (x + 2, yy + j * 18))
                self._log_hits.append((rect, row))

    def _visible_log(self) -> list[tuple[int, LogRow]]:
        out: list[tuple[int, LogRow]] = []
        source = self.rows_new if self.log_new_only else self.rows_all
        for step in self.store.steps[: self.index + 1]:
            rows = source[step.index]
            if step.index == self.index and self.log_new_only:
                rows = rows[: self.visible_new()]
            out.extend((step.index, row) for row in rows)
        return out

    def _draw_kb(self) -> None:
        theme.panel(self.canvas, CONTENT)
        x = CONTENT.x + 14
        y = CONTENT.y + 10
        theme.text(self.canvas, strings.WATCH_KB_TAB, 18, theme.GOLD, (x, y), bold=True)
        theme.text(
            self.canvas,
            strings.WATCH_KB_HINT,
            14,
            theme.MUTED,
            (CONTENT.right - 14, y + 2),
            anchor="topright",
        )
        y += 28
        view = pygame.Rect(x, y, CONTENT.width - 28, CONTENT.bottom - y - 10)
        counts, last = self.store.rule_stats(self.index)
        max_count = max(counts.values(), default=1)
        cursor = -self.kb_scroll
        for rule in RULES:
            rect = pygame.Rect(x, y + cursor, view.width, 24)
            if rect.bottom >= view.y and rect.top <= view.bottom:
                count = counts.get(rule.id, 0)
                if rule.id == self.selected_rule:
                    pygame.draw.rect(self.canvas, theme.BG_PANEL_HIGHLIGHT, rect, border_radius=4)
                # Visual heat bar behind the count column
                bar_bg = pygame.Rect(rect.right - 154, rect.y + 5, 72, 13)
                pygame.draw.rect(self.canvas, theme.BG_DEEP, bar_bg, border_radius=4)
                if count > 0:
                    fill_w = max(4, int(bar_bg.width * (count / max_count)))
                    bar_col = theme.GOLD if rule.id == "R16" else theme.TEAL
                    pygame.draw.rect(
                        self.canvas,
                        bar_col,
                        (bar_bg.x, bar_bg.y, fill_w, bar_bg.height),
                        border_radius=4,
                    )
                theme.text(
                    self.canvas, rule.id, 15, theme.GOLD, (rect.x + 4, rect.y + 3), bold=True
                )
                theme.text(
                    self.canvas,
                    _fit(rule.description, 13, 336),
                    13,
                    theme.INK if count > 0 or rule.id == self.selected_rule else theme.DIM,
                    (rect.x + 48, rect.y + 4),
                )
                theme.text(
                    self.canvas,
                    f"{count}x",
                    13,
                    theme.INK if count > 0 else theme.DIM,
                    (rect.right - 46, rect.y + 4),
                    anchor="topright",
                )
                theme.text(
                    self.canvas,
                    f"T{last[rule.id].turn + 1}" if rule.id in last else "-",
                    12,
                    theme.MUTED,
                    (rect.right - 6, rect.y + 5),
                    anchor="topright",
                )
                self._kb_hits.append((rect, rule.id))
            cursor += 24
        self._kb_max_scroll = max(0, len(RULES) * 24 - view.height)
        self.kb_scroll = max(0, min(self.kb_scroll, self._kb_max_scroll))

    def _draw_footer(self) -> None:
        theme.panel(self.canvas, FOOTER)
        x = FOOTER.x + 14
        y = FOOTER.y + 12
        mouse = self._mouse()

        back_btn = pygame.Rect(x, y, 42, 32)
        theme.button(self.canvas, back_btn, "<", hover=back_btn.collidepoint(mouse), size=18)
        self._buttons["back_step"] = back_btn

        play = pygame.Rect(x + 48, y, 90, 32)
        theme.button(
            self.canvas,
            play,
            "PAUSE" if self.playing else "PLAY",
            selected=self.playing,
            hover=play.collidepoint(mouse),
            size=16,
        )
        self._buttons["play"] = play

        fwd_btn = pygame.Rect(x + 144, y, 42, 32)
        theme.button(self.canvas, fwd_btn, ">", hover=fwd_btn.collidepoint(mouse), size=18)
        self._buttons["fwd_step"] = fwd_btn

        speed = pygame.Rect(x + 194, y, 108, 32)
        theme.button(
            self.canvas,
            speed,
            f"{self.speed:g}x",
            hover=speed.collidepoint(mouse),
            size=16,
        )
        self._buttons["speed"] = speed

        overlay = pygame.Rect(x + 310, y, 152, 32)
        theme.button(
            self.canvas,
            overlay,
            strings.WATCH_OVERLAY_ON if self.overlay else strings.WATCH_OVERLAY_OFF,
            selected=self.overlay,
            hover=overlay.collidepoint(mouse),
            size=15,
        )
        self._buttons["overlay"] = overlay

        why = pygame.Rect(x + 470, y, 102, 32)
        theme.button(
            self.canvas,
            why,
            "WHY? [W]",
            hover=why.collidepoint(mouse),
            accent=theme.CYAN,
            size=15,
        )
        self._buttons["why"] = why

        # Timeline scrub bar
        bar = pygame.Rect(x, y + 44, FOOTER.width - 28, 10)
        pygame.draw.rect(self.canvas, theme.BG_DEEP, bar, border_radius=5)
        total = max(1, len(self.store.steps) - 1)
        prog = self.index / total
        pygame.draw.rect(
            self.canvas,
            theme.GOLD,
            (bar.x, bar.y, max(8, int(bar.width * prog)), bar.height),
            border_radius=5,
        )

        theme.text(self.canvas, strings.WATCH_TRACE_HINT, 14, theme.MUTED, (x, y + 64))
        end = (
            strings.WATCH_END
            if self.index == len(self.store.steps) - 1 and self.elapsed >= self.duration()
            else strings.WATCH_SELECT
        )
        theme.text(self.canvas, end, 14, theme.GOLD, (x, y + 92))
        theme.text(
            self.canvas,
            f"outcome: {self.store.outcome} · score {self.store.score}",
            14,
            theme.CYAN,
            (FOOTER.right - 14, y + 92),
            anchor="topright",
        )

    def _draw_proof(self) -> None:
        shade = pygame.Surface((1280, 720), pygame.SRCALPHA)
        shade.fill((8, 6, 12, 226))
        self.canvas.blit(shade, (0, 0))
        rect = pygame.Rect(70, 70, 1140, 588)
        theme.panel(self.canvas, rect, color=theme.BG_PANEL_LIGHT, accent_top=theme.CYAN)
        theme.text(
            self.canvas,
            strings.WATCH_WHY_TITLE,
            24,
            theme.GOLD,
            (rect.x + 20, rect.y + 14),
            bold=True,
        )
        theme.text(
            self.canvas,
            strings.WATCH_WHY_HINT,
            15,
            theme.MUTED,
            (rect.right - 66, rect.y + 20),
            anchor="topright",
        )
        close = pygame.Rect(rect.right - 46, rect.y + 12, 30, 30)
        theme.button(self.canvas, close, "X", size=17)
        self._buttons["close"] = close
        if self.proof is None:
            theme.text(
                self.canvas,
                self.proof_message or strings.WATCH_WHY_EMPTY,
                20,
                theme.INK,
                (rect.centerx, rect.centery),
                anchor="center",
            )
            return
        view = pygame.Rect(rect.x + 20, rect.y + 58, rect.width - 40, rect.height - 78)
        rows = self._proof_rows(self.proof)
        cursor = -self.proof_scroll
        for kind, node, depth in rows:
            h = 38 if kind == "node" else 26
            row_rect = pygame.Rect(view.x, view.y + cursor, view.width, h)
            if row_rect.bottom >= view.y and row_rect.top <= view.bottom:
                if kind == "expand":
                    theme.button(
                        self.canvas,
                        row_rect.inflate(-6, -2),
                        "+ expand hidden premises",
                        size=15,
                    )
                    self._proof_hits.append((row_rect, node))
                else:
                    indent = min(depth, 12) * 18
                    if self._point_in(row_rect):
                        pygame.draw.rect(self.canvas, theme.BG_PANEL, row_rect, border_radius=4)
                    theme.text(
                        self.canvas,
                        _fit(node.label, 17, view.width - indent - 24),
                        17,
                        theme.INK_BRIGHT if depth == 0 else theme.GOLD,
                        (view.x + indent + 4, view.y + cursor + 1),
                        bold=depth == 0,
                    )
                    theme.text(
                        self.canvas,
                        _fit(node.detail, 13, view.width - indent - 24),
                        13,
                        theme.MUTED,
                        (view.x + indent + 4, view.y + cursor + 20),
                    )
                    self._proof_hits.append((row_rect, node))
            cursor += h
        self._proof_max_scroll = max(0, cursor - view.height)
        self.proof_scroll = max(0, min(self.proof_scroll, self._proof_max_scroll))

    def _proof_rows(self, root: ProofNode) -> list[tuple[str, ProofNode, int]]:
        rows: list[tuple[str, ProofNode, int]] = []

        def walk(node: ProofNode, depth: int) -> None:
            if depth >= 6 and node.children and node.id not in self.expanded:
                rows.append(("node", node, depth))
                rows.append(("expand", node, depth))
                return
            rows.append(("node", node, depth))
            for child in node.children:
                walk(child, depth + 1)

        walk(root, 0)
        return rows

    def _point_in(self, rect) -> bool:
        return rect.collidepoint(self._mouse())

    def _mouse(self) -> tuple[int, int]:
        return self.to_logical(pygame.mouse.get_pos())
