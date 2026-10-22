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
from shifting_manor.ui import strings, theme

BOARD = pygame.Rect(48, 96, 576, 576)
SIDE = pygame.Rect(648, 88, 600, 608)
CONTENT = pygame.Rect(648, 134, 600, 428)
FOOTER = pygame.Rect(648, 570, 600, 126)
TABS = (
    pygame.Rect(648, 88, 190, 38),
    pygame.Rect(842, 88, 224, 38),
    pygame.Rect(1070, 88, 178, 38),
)


def _smooth(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _fit(value: str, size: int, width: int, *, bold: bool = False) -> str:
    font = theme.font(size, bold)
    if font.size(value)[0] <= width:
        return value
    out = value
    while out and font.size(out + "…")[0] > width:
        out = out[:-1]
    return out + "…"


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
    ) -> None:
        self.store = store
        self.to_logical = to_logical
        self.on_exit = on_exit
        self.on_fire = on_fire
        self.seed = seed or store.seed
        self.index = 0
        self.elapsed = 0.0
        self.playing = True
        self.speed = 1.0
        self.tab = 0
        self.overlay = True
        self.overlay_alpha = 1.0
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
        self.rows_new = {step.index: [] for step in store.steps}
        for row in store.log_rows():
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
        speeds = (1.0, 2.0, 4.0)
        i = min(range(len(speeds)), key=lambda k: abs(speeds[k] - self.speed))
        self.speed = speeds[(i + direction) % len(speeds)]

    def _key(self, key: int) -> None:
        if key == pygame.K_ESCAPE:
            if self.proof is not None:
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
        if key == pygame.K_w:
            self._open_room_proof(self.hover_cell)
            return
        # Any other key skips the rest of this step's firing animation.
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
        if self.proof is not None:
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
            elif name == "speed":
                self._cycle_speed(1)
            elif name == "overlay":
                self.overlay = not self.overlay
            elif name == "why":
                self._open_room_proof(self.hover_cell)
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
    def _cell_rect(self, cell) -> pygame.Rect:
        size = self.store.size
        return pygame.Rect(BOARD.x + cell[0] * 96, BOARD.y + (size - 1 - cell[1]) * 96, 96, 96)

    def _cell_at(self, pos) -> tuple[int, int] | None:
        if not BOARD.collidepoint(pos):
            return None
        x = (pos[0] - BOARD.x) // 96
        y = self.store.size - 1 - (pos[1] - BOARD.y) // 96
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
        self._draw_board()
        self._draw_tabs()
        if self.tab == 0:
            self._draw_trace()
        elif self.tab == 1:
            self._draw_log()
        else:
            self._draw_kb()
        self._draw_footer()
        if self.proof is not None or self.proof_message:
            self._draw_proof()

    def _draw_header(self) -> None:
        theme.text(self.canvas, strings.WATCH_TITLE, 34, theme.GOLD, (48, 24), bold=True)
        theme.text(
            self.canvas,
            f"{self.store.agent.upper()} · {self.store.mode.upper()} · {self.seed}",
            20,
            theme.MUTED,
            (206, 34),
        )
        theme.text(
            self.canvas,
            strings.WATCH_REPLAY,
            20,
            theme.INK,
            (1232, 34),
            anchor="topright",
        )
        theme.text(
            self.canvas,
            strings.WATCH_STEP.format(step=self.index + 1, total=len(self.store.steps)),
            18,
            theme.GOLD,
            (BOARD.centerx, 82),
            anchor="midbottom",
        )

    def _draw_board(self) -> None:
        size = self.store.size
        step = self.step
        board = pygame.Surface(BOARD.size)
        board.fill(theme.FLOOR)
        visited = step.visited
        for x in range(size):
            for y in range(size):
                cell = (x, y)
                rect = pygame.Rect(x * 96, (size - 1 - y) * 96, 96, 96)
                pygame.draw.rect(
                    board,
                    theme.FLOOR_VISITED if cell in visited else (31, 25, 40),
                    rect.inflate(-4, -4),
                    border_radius=3,
                )
                pygame.draw.rect(board, (58, 46, 68), rect, 1)
                if cell == self.store.entrance:
                    door = pygame.Rect(rect.centerx - 22, rect.bottom - 14, 44, 10)
                    pygame.draw.rect(board, theme.GOLD, door, border_radius=2)
        if size == 6:
            k = 3 * 96
            for p in range(24, board.get_height(), 48):
                pygame.draw.circle(board, (94, 76, 112), (k, p), 2)
                pygame.draw.circle(board, (94, 76, 112), (p, k), 2)
            pygame.draw.line(board, (88, 70, 104), (k, 4), (k, board.get_height() - 4), 2)
            pygame.draw.line(board, (88, 70, 104), (4, k), (board.get_width() - 4, k), 2)
        pygame.draw.rect(board, (76, 60, 90), board.get_rect(), 2)

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
        self._draw_thought()

    def _draw_belief(self, layer, belief: Belief) -> None:
        rect = pygame.Rect(
            belief.cell[0] * 96,
            (self.store.size - 1 - belief.cell[1]) * 96,
            96,
            96,
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
                13,
                (*color, int(210 * self.overlay_alpha)),
                (rect.centerx, rect.bottom - 11),
                anchor="midbottom",
            )
        elif belief.label == "unknown":
            # Unknown rooms get a faint question mark; certainty stays visually quiet.
            theme.mark(layer, rect, "?", int(45 * self.overlay_alpha))
        if belief.stale:
            dashed = pygame.Surface(rect.size, pygame.SRCALPHA)
            _dashed_rect(
                dashed,
                (*theme.GOLD, int(220 * self.overlay_alpha)),
                dashed.get_rect().inflate(-12, -12),
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
        xs = [c[0] for c in wing]
        ys = [c[1] for c in wing]
        size = self.store.size
        rect = pygame.Rect(
            min(xs) * 96,
            (size - 1 - max(ys)) * 96,
            (max(xs) - min(xs) + 1) * 96,
            (max(ys) - min(ys) + 1) * 96,
        )
        _dashed_rect(board, (*theme.GOLD, alpha), rect.inflate(-4, -4), width=3, dash=10)
        label = strings.WATCH_SHIFT.format(
            n=shift.shift_index,
            wing=("FOYER", "SE", "NW", "NE")[shift.wing] if shift.wing < 4 else shift.wing,
            direction=shift.direction.upper(),
        )
        theme.text(
            board, label, 20, theme.GOLD, (rect.centerx, rect.y + 8), anchor="midtop", bold=True
        )
        # deterministic dust from the stored shift, not a re-simulation
        import random

        rng = random.Random(f"{self.seed}:{shift.shift_index}")
        for _ in range(22):
            dx = rng.randrange(rect.left + 8, rect.right - 8)
            dy = rng.randrange(rect.top + 24, rect.bottom - 8)
            r = 2 + rng.randrange(3)
            pygame.draw.circle(board, (210, 190, 160, alpha), (dx, dy), r)

    def _draw_highlights(self, board) -> None:
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
                cell[0] * 96,
                (self.store.size - 1 - cell[1]) * 96,
                96,
                96,
            )
            pygame.draw.rect(board, theme.GOLD, rect.inflate(-6, -6), 3, border_radius=3)
        # R22 candidate risk labels are part of the trace, so they may be shown.
        if self.tab == 0 and self.step.gamble_candidates:
            for candidate in self.step.gamble_candidates[:6]:
                rect = pygame.Rect(
                    candidate.cell[0] * 96,
                    (self.store.size - 1 - candidate.cell[1]) * 96,
                    96,
                    96,
                )
                theme.text(
                    board,
                    f"{100 * candidate.risk:.0f}%",
                    17,
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
        pygame.draw.circle(board, (255, 176, 96), center, 22)
        pygame.draw.circle(board, (46, 30, 20), center, 22, 3)
        direction = getattr(step.action, "dir", None) or "S"
        offsets = {"N": (0, -12), "S": (0, 12), "E": (12, 0), "W": (-12, 0)}
        ox, oy = offsets[direction]
        pygame.draw.polygon(
            board,
            theme.INK,
            [
                (center[0] + ox, center[1] + oy),
                (center[0] + ox * 0.35 - oy * 0.35, center[1] + oy * 0.35 + ox * 0.35),
                (center[0] + ox * 0.35 + oy * 0.35, center[1] + oy * 0.35 - ox * 0.35),
            ],
        )

    def _draw_thought(self) -> None:
        text = self.step.thought or "…"
        rect = pygame.Rect(58, 104, 556, 58)
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel.fill((*theme.BG_PANEL_LIGHT, 226))
        self.canvas.blit(panel, rect.topleft)
        pygame.draw.rect(self.canvas, theme.GOLD, rect, 2, border_radius=8)
        theme.text(self.canvas, strings.WATCH_THOUGHT, 14, theme.MUTED, (rect.x + 12, rect.y + 6))
        lines = theme.wrap(text, 18, rect.width - 24)
        for i, line in enumerate(lines[:2]):
            theme.text(self.canvas, line, 18, theme.INK, (rect.x + 12, rect.y + 24 + i * 18))

    def _draw_tabs(self) -> None:
        labels = ("TRACE", "INFERENCE LOG", "RULES")
        for i, (rect, label) in enumerate(zip(TABS, labels)):
            theme.button(self.canvas, rect, label, selected=i == self.tab, size=17)

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
            f"pos {self.step.position} · oil {self.step.oil}",
            16,
            theme.MUTED,
            (CONTENT.right - 14, y),
            anchor="topright",
        )
        y += 26
        theme.text(self.canvas, strings.WATCH_PERCEPTS, 14, theme.MUTED, (x, y))
        self._draw_percept_icons(x, y + 18)
        y += 62
        theme.text(self.canvas, "FIRINGS · NEW THIS TURN", 14, theme.MUTED, (x, y))
        y += 20
        visible = self.step.firings[: self.visible_new()]
        for i, firing in enumerate(visible[:13]):
            line = _fit(format_firing(firing), 15, CONTENT.width - 34)
            color = theme.INK if i == len(visible) - 1 else theme.MUTED
            theme.text(self.canvas, line, 15, color, (x, y + i * 18))
        if len(visible) > 13:
            theme.text(
                self.canvas,
                f"… {len(visible) - 13} more",
                14,
                theme.MUTED,
                (x, y + 13 * 18),
            )
        if not visible:
            theme.text(self.canvas, "…", 16, theme.MUTED, (x, y))
        gy = CONTENT.bottom - 96
        theme.text(self.canvas, strings.WATCH_GAMBLES, 14, theme.MUTED, (x, gy))
        if self.step.gamble_candidates:
            for i, candidate in enumerate(self.step.gamble_candidates[:4]):
                line = (
                    f"{format_item(Fact('Cell', candidate.cell))}  "
                    f"risk {100 * candidate.risk:.0f}%  utility {candidate.utility:.1f}"
                )
                theme.text(
                    self.canvas,
                    _fit(line, 16, CONTENT.width - 34),
                    16,
                    theme.INK,
                    (x, gy + 20 + i * 18),
                )
        else:
            theme.text(self.canvas, strings.WATCH_NO_GAMBLE, 16, theme.MUTED, (x, gy + 20))

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
                theme.MUTED,
            ),
        ]
        for i, (name, active, color) in enumerate(items):
            box = pygame.Rect(x + i * 90, y, 74, 30)
            pygame.draw.rect(
                self.canvas,
                theme.BG_PANEL_LIGHT if active else theme.BG_PANEL,
                box,
                border_radius=5,
            )
            pygame.draw.rect(self.canvas, color if active else theme.WALL, box, 2, border_radius=5)
            self._percept_icon(box, name, color if active else (74, 66, 86))
            theme.text(
                self.canvas,
                name,
                12,
                color if active else (85, 78, 96),
                (box.centerx, box.bottom + 2),
                anchor="midtop",
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
        theme.text(
            self.canvas,
            "new firings only",
            14,
            theme.MUTED,
            (CONTENT.right - 14, y + 2),
            anchor="topright",
        )
        y += 32
        view = pygame.Rect(x, y, CONTENT.width - 28, CONTENT.bottom - y - 12)
        rows = self._visible_log()
        if not rows:
            theme.text(self.canvas, strings.WATCH_LOG_EMPTY, 16, theme.MUTED, (x, y + 4))
            self._log_max_scroll = 0
            return
        # Lay out headings and rows, then draw the visible slice.
        laid: list[tuple[str, object, int]] = []
        cursor = 0
        last_step = -1
        for step_index, row in rows:
            if step_index != last_step:
                laid.append(("head", step_index, cursor))
                cursor += 22
                last_step = step_index
            laid.append(("row", row, cursor))
            cursor += 18
        total = cursor
        self._log_max_scroll = max(0, total - view.height)
        if self.log_auto:
            self.log_scroll = self._log_max_scroll
        self.log_scroll = max(0, min(self.log_scroll, self._log_max_scroll))
        base_y = view.y - self.log_scroll
        for kind, item, offset in laid:
            yy = base_y + offset
            if yy + 18 < view.y or yy > view.bottom:
                continue
            if kind == "head":
                theme.text(self.canvas, f"TURN {item + 1}", 15, theme.GOLD, (x, yy), bold=True)
                pygame.draw.line(self.canvas, theme.WALL, (x + 78, yy + 8), (view.right, yy + 8), 1)
            else:
                row: LogRow = item  # type: ignore[assignment]
                color = theme.INK if row.new else theme.MUTED
                prefix = "" if row.new else "· "
                text = _fit(prefix + row.text, 15, view.width - 8)
                rect = pygame.Rect(x, yy, view.width, 17)
                if rect.collidepoint(self._mouse()):
                    pygame.draw.rect(self.canvas, theme.BG_PANEL_LIGHT, rect)
                theme.text(self.canvas, text, 15, color, (x + 2, yy))
                self._log_hits.append((rect, row))

    def _visible_log(self) -> list[tuple[int, LogRow]]:
        out: list[tuple[int, LogRow]] = []
        for step in self.store.steps[: self.index + 1]:
            rows = self.rows_new[step.index]
            if step.index == self.index:
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
        cursor = -self.kb_scroll
        for rule in RULES:
            rect = pygame.Rect(x, y + cursor, view.width, 23)
            if rect.bottom >= view.y and rect.top <= view.bottom:
                if rule.id == self.selected_rule:
                    pygame.draw.rect(self.canvas, theme.BG_PANEL_LIGHT, rect, border_radius=3)
                theme.text(
                    self.canvas, rule.id, 15, theme.GOLD, (rect.x + 4, rect.y + 3), bold=True
                )
                theme.text(
                    self.canvas,
                    _fit(rule.description, 13, 330),
                    13,
                    theme.INK if rule.id == self.selected_rule else theme.MUTED,
                    (rect.x + 46, rect.y + 4),
                )
                count = counts.get(rule.id, 0)
                theme.text(
                    self.canvas,
                    f"{count}×",
                    13,
                    theme.INK,
                    (rect.right - 108, rect.y + 4),
                    anchor="topright",
                )
                theme.text(
                    self.canvas,
                    f"T{last[rule.id].turn + 1}" if rule.id in last else "—",
                    12,
                    theme.MUTED,
                    (rect.right - 8, rect.y + 4),
                    anchor="topright",
                )
                self._kb_hits.append((rect, rule.id))
            cursor += 23
        del view

    def _draw_footer(self) -> None:
        theme.panel(self.canvas, FOOTER)
        x = FOOTER.x + 14
        y = FOOTER.y + 10
        play = pygame.Rect(x, y, 96, 30)
        theme.button(
            self.canvas, play, "PAUSE" if self.playing else "PLAY", selected=self.playing, size=17
        )
        self._buttons["play"] = play
        speed = pygame.Rect(x + 106, y, 128, 30)
        theme.button(self.canvas, speed, strings.WATCH_SPEED.format(speed=self.speed), size=17)
        self._buttons["speed"] = speed
        overlay = pygame.Rect(x + 244, y, 200, 30)
        theme.button(
            self.canvas,
            overlay,
            strings.WATCH_OVERLAY_ON if self.overlay else strings.WATCH_OVERLAY_OFF,
            selected=self.overlay,
            size=17,
        )
        self._buttons["overlay"] = overlay
        why = pygame.Rect(x + 454, y, 118, 30)
        theme.button(self.canvas, why, strings.WATCH_WHY_TITLE.split(" ·")[0], size=17)
        self._buttons["why"] = why
        theme.text(self.canvas, strings.WATCH_TRACE_HINT, 15, theme.MUTED, (x, y + 42))
        end = (
            strings.WATCH_END
            if self.index == len(self.store.steps) - 1 and self.elapsed >= self.duration()
            else strings.WATCH_SELECT
        )
        theme.text(self.canvas, end, 14, theme.GOLD, (x, y + 70))
        theme.text(
            self.canvas,
            f"outcome: {self.store.outcome} · score {self.store.score}",
            14,
            theme.MUTED,
            (FOOTER.right - 14, y + 70),
            anchor="topright",
        )

    def _draw_proof(self) -> None:
        shade = pygame.Surface((1280, 720), pygame.SRCALPHA)
        shade.fill((8, 6, 12, 226))
        self.canvas.blit(shade, (0, 0))
        rect = pygame.Rect(70, 76, 1140, 584)
        theme.panel(self.canvas, rect, color=theme.BG_PANEL_LIGHT)
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
            (rect.right - 62, rect.y + 20),
            anchor="topright",
        )
        close = pygame.Rect(rect.right - 42, rect.y + 12, 26, 26)
        theme.button(self.canvas, close, "×", size=18)
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
            h = 38 if kind == "node" else 24
            row_rect = pygame.Rect(view.x, view.y + cursor, view.width, h)
            if row_rect.bottom >= view.y and row_rect.top <= view.bottom:
                if kind == "expand":
                    theme.button(
                        self.canvas, row_rect.inflate(-6, -2), "▸ expand hidden premises", size=15
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
                        theme.INK if depth == 0 else theme.GOLD,
                        (view.x + indent + 2, view.y + cursor + 1),
                        bold=depth == 0,
                    )
                    theme.text(
                        self.canvas,
                        _fit(node.detail, 13, view.width - indent - 24),
                        13,
                        theme.MUTED,
                        (view.x + indent + 2, view.y + cursor + 20),
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
