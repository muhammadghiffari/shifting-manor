"""Visual Field Guide / How-To-Play reference overlay (accessible anytime via [H])."""

from __future__ import annotations

import pygame

from shifting_manor.ui import fx, strings, theme

TABS = (
    "1. GOAL & FLOW",
    "2. SENSES & MARKS",
    "3. THE SHIFT TWIST",
    "4. CONTROLS & AI AGENTS",
)


class GuideOverlay:
    """Clean, visual, 4-tab How-To-Play field guide with live vector illustrations."""

    def __init__(self, *, on_close, on_start_tutorial=None, on_start_auto=None) -> None:
        self.on_close = on_close
        self.on_start_tutorial = on_start_tutorial
        self.on_start_auto = on_start_auto
        self.tab = 0
        self.t = 0.0
        self._hits: list[tuple[pygame.Rect, str, object]] = []

    def update(self, dt: float) -> None:
        self.t += dt

    def handle(self, event, pos: tuple[int, int] | None = None) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_h):
                self.on_close()
                return True
            if event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_TAB):
                self.tab = (self.tab + 1) % len(TABS)
                return True
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.tab = (self.tab - 1) % len(TABS)
                return True
            if event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                self.tab = event.key - pygame.K_1
                return True
            if event.key == pygame.K_t and self.on_start_tutorial is not None:
                self.on_start_tutorial()
                return True
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and pos is not None:
            for rect, action, payload in self._hits:
                if rect.collidepoint(pos):
                    if action == "close":
                        self.on_close()
                    elif action == "tab":
                        self.tab = int(payload)  # type: ignore[arg-type]
                    elif action == "tutorial" and self.on_start_tutorial is not None:
                        self.on_start_tutorial()
                    elif action == "auto" and self.on_start_auto is not None:
                        self.on_start_auto()
                    return True
            if not self._rect().collidepoint(pos):
                self.on_close()
            return True
        return False

    @staticmethod
    def _rect() -> pygame.Rect:
        return pygame.Rect(90, 46, 1100, 628)

    def draw(self, canvas: pygame.Surface, mouse: tuple[int, int]) -> None:
        self._hits = []
        shade = pygame.Surface(theme.LOGICAL_SIZE, pygame.SRCALPHA)
        shade.fill((8, 6, 14, 224))
        canvas.blit(shade, (0, 0))

        rect = self._rect()
        theme.panel(canvas, rect, color=theme.BG_PANEL_LIGHT, accent_top=theme.GOLD)
        theme.text(
            canvas,
            strings.GUIDE_TITLE,
            30,
            theme.GOLD,
            (rect.x + 26, rect.y + 18),
            bold=True,
        )
        theme.text(canvas, strings.GUIDE_HINT, 15, theme.MUTED, (rect.x + 26, rect.y + 52))

        close = pygame.Rect(rect.right - 118, rect.y + 18, 94, 34)
        theme.button(
            canvas, close, "CLOSE", selected=True, hover=close.collidepoint(mouse), size=17
        )
        self._hits.append((close, "close", None))

        # Tab strip
        tab_w = (rect.width - 52 - 3 * 10) // 4
        for i, lbl in enumerate(TABS):
            tr = pygame.Rect(rect.x + 26 + i * (tab_w + 10), rect.y + 82, tab_w, 38)
            theme.button(
                canvas,
                tr,
                lbl,
                selected=i == self.tab,
                hover=tr.collidepoint(mouse),
                size=16,
            )
            self._hits.append((tr, "tab", i))

        body = pygame.Rect(rect.x + 26, rect.y + 132, rect.width - 52, 412)
        theme.panel(canvas, body, color=theme.BG_PANEL, radius=8)

        if self.tab == 0:
            self._draw_goal(canvas, body)
        elif self.tab == 1:
            self._draw_senses(canvas, body)
        elif self.tab == 2:
            self._draw_shift(canvas, body)
        else:
            self._draw_controls_ai(canvas, body)

        # Footer interactive CTA buttons
        fy = rect.bottom - 66
        if self.on_start_tutorial is not None:
            tb = pygame.Rect(rect.x + 26, fy, 330, 44)
            theme.button(
                canvas,
                tb,
                "PLAY 4-LESSON INTERACTIVE TUTORIAL [T]",
                selected=True,
                hover=tb.collidepoint(mouse),
                accent=theme.TEAL,
                size=16,
            )
            self._hits.append((tb, "tutorial", None))
        if self.on_start_auto is not None:
            ab = pygame.Rect(rect.x + 372, fy, 320, 44)
            theme.button(
                canvas,
                ab,
                "WATCH REAL AI PLAY AUTONOMOUSLY",
                hover=ab.collidepoint(mouse),
                accent=theme.CYAN,
                size=16,
            )
            self._hits.append((ab, "auto", None))
        theme.text(
            canvas,
            f"Page {self.tab + 1} / {len(TABS)}  ·  Use Left/Right arrows or click tabs",
            15,
            theme.MUTED,
            (rect.right - 26, fy + 14),
            anchor="topright",
        )

    def _draw_goal(self, canvas: pygame.Surface, body: pygame.Rect) -> None:
        cards = [
            (
                "1. EXPLORE",
                theme.TEAL,
                "Start at Entrance (0,0) with your flickering lantern. Every Move or Charm spends 1 Oil.",
                "caretaker",
            ),
            (
                "2. DEDUCE",
                theme.CYAN,
                "Hidden Pits & 1 Ghost kill on contact. Read Senses in your room to prove safe paths!",
                "hazards",
            ),
            (
                "3. GRAB HEIRLOOM",
                theme.GOLD,
                "Feel a golden GLIMMER when the Heirloom is adjacent. Walk onto its room to pick it up!",
                "heirloom",
            ),
            (
                "4. ESCAPE AT (0,0)",
                theme.ORANGE,
                "Return safely to the golden Entrance door at (0,0) and press [E] or click LEAVE MANOR!",
                "exit",
            ),
        ]
        cw = (body.width - 48 - 36) // 4
        for i, (head, col, desc, icon) in enumerate(cards):
            cr = pygame.Rect(body.x + 24 + i * (cw + 12), body.y + 22, cw, 240)
            theme.panel(canvas, cr, color=theme.BG_PANEL_LIGHT, border=col, radius=8)
            theme.text(canvas, head, 18, col, (cr.centerx, cr.y + 16), anchor="midtop", bold=True)
            art = pygame.Rect(cr.centerx - 48, cr.y + 48, 96, 86)
            if icon == "caretaker":
                fx.draw_caretaker(canvas, art.center, "E", self.t)
            elif icon == "hazards":
                fx.draw_pit_reveal(canvas, pygame.Rect(art.x - 10, art.y, 64, 86))
                fx.draw_ghost_reveal(canvas, pygame.Rect(art.x + 42, art.y, 64, 86), self.t)
            elif icon == "heirloom":
                fx.draw_heirloom(canvas, art, self.t)
            else:
                fx.draw_stone_tile(
                    canvas,
                    pygame.Rect(art.centerx - 40, art.centery - 38, 80, 76),
                    (0, 0),
                    visited=True,
                    is_entrance=True,
                    has_treasure_badge=True,
                )
            for j, line in enumerate(theme.wrap(desc, 15, cr.width - 20)):
                theme.text(
                    canvas,
                    line,
                    15,
                    theme.INK,
                    (cr.centerx, cr.y + 146 + j * 19),
                    anchor="midtop",
                )

        # Scoring & Stars summary strip
        strip = pygame.Rect(body.x + 24, body.y + 282, body.width - 48, 108)
        theme.panel(canvas, strip, color=theme.BG_PANEL_LIGHT, radius=8)
        theme.text(
            canvas,
            "SCORING & STAR RATING",
            17,
            theme.GOLD,
            (strip.x + 16, strip.y + 12),
            bold=True,
        )
        theme.text(
            canvas,
            "+1000 Escape with Heirloom   ·   +200 Ghost Banished   ·   -10 Charm Cast   ·   -1 per Action   ·   -1000 Death",
            16,
            theme.INK,
            (strip.x + 16, strip.y + 40),
        )
        theme.text(
            canvas,
            "3 Stars: Escape with Heirloom within Oracle Par + 15 moves   ·   2 Stars: Slower win   ·   1 Star: Empty escape",
            15,
            theme.MUTED,
            (strip.x + 16, strip.y + 68),
        )

    def _draw_senses(self, canvas: pygame.Surface, body: pygame.Rect) -> None:
        left = pygame.Rect(body.x + 20, body.y + 18, 560, body.height - 36)
        right = pygame.Rect(
            left.right + 18, body.y + 18, body.right - left.right - 38, body.height - 36
        )
        theme.panel(canvas, left, color=theme.BG_PANEL_LIGHT, radius=8)
        theme.panel(canvas, right, color=theme.BG_PANEL_LIGHT, radius=8)

        theme.text(
            canvas,
            "READING YOUR SENSES (4-NEIGHBOURS ONLY)",
            17,
            theme.GOLD,
            (left.x + 16, left.y + 14),
            bold=True,
        )
        senses = [
            (
                "QUIET ROOM",
                theme.TEAL,
                "No Breeze & no Chill -> ALL 4 orthogonal neighbours are 100% SAFE!",
            ),
            ("BREEZE", theme.CYAN, "At least ONE 4-neighbour (N/E/S/W) contains a bottomless Pit."),
            (
                "CHILL",
                theme.GREEN,
                "The living Ghost is in one of your 4-neighbours. Never diagonal!",
            ),
            ("GLIMMER", theme.GOLD, "The Heirloom is in THIS room or one of your 4-neighbours."),
            ("RUMBLE", theme.ORANGE, "A wing will rotate 90° in 2 moves! Check the Shift Clock."),
            ("SCREAM", theme.VIOLET, "Your Charm hit and banished the Ghost permanently (+200)."),
        ]
        for i, (name, col, desc) in enumerate(senses):
            sy = left.y + 48 + i * 52
            theme.badge(canvas, name, (left.x + 16, sy), color=col, size=14)
            for j, line in enumerate(theme.wrap(desc, 15, left.width - 150)):
                theme.text(canvas, line, 15, theme.INK, (left.x + 142, sy + j * 18))

        theme.text(
            canvas,
            "SHARED MARK & AI BELIEF ICONS",
            17,
            theme.GOLD,
            (right.x + 16, right.y + 14),
            bold=True,
        )
        marks = [
            ("safe", "SAFE [4]", theme.TEAL, "Proven free of pits & ghost."),
            ("pit", "PIT [2]", theme.ORANGE, "Deadly pit room — never enter."),
            ("ghost", "GHOST [3]", theme.CYAN, "Ghost room — aim Charm [C] to banish!"),
            ("?", "SUSPECT [1]", theme.VIOLET, "Possible danger; needs another clue."),
        ]
        for i, (kind, lbl, col, desc) in enumerate(marks):
            my = right.y + 52 + i * 68
            box = pygame.Rect(right.x + 16, my, 52, 52)
            pygame.draw.rect(canvas, theme.FLOOR_DARK, box, border_radius=6)
            theme.mark(canvas, box, kind)
            theme.text(canvas, lbl, 16, col, (box.right + 12, my + 4), bold=True)
            for j, line in enumerate(theme.wrap(desc, 14, right.width - 96)):
                theme.text(canvas, line, 14, theme.MUTED, (box.right + 12, my + 26 + j * 17))
        theme.text(
            canvas,
            "Tip: Right-click any room on the board to cycle marks!",
            15,
            theme.GOLD,
            (right.x + 16, right.bottom - 32),
            bold=True,
        )

    def _draw_shift(self, canvas: pygame.Surface, body: pygame.Rect) -> None:
        # Mini 6x6 wing diagram on the left
        diag = pygame.Rect(body.x + 36, body.y + 44, 312, 312)
        half = 156
        wings = [
            (
                pygame.Rect(diag.x, diag.y, half, half),
                "WING NW",
                "ROTATES 90°",
                theme.VIOLET,
                "ccw",
            ),
            (
                pygame.Rect(diag.x + half, diag.y, half, half),
                "WING NE",
                "ROTATES 90°",
                theme.CYAN,
                "cw",
            ),
            (
                pygame.Rect(diag.x, diag.y + half, half, half),
                "FOYER (SW)",
                "NEVER ROTATES",
                theme.TEAL,
                None,
            ),
            (
                pygame.Rect(diag.x + half, diag.y + half, half, half),
                "WING SE",
                "ROTATES 90°",
                theme.GOLD,
                "cw",
            ),
        ]
        for r, name, sub, col, rot in wings:
            pygame.draw.rect(canvas, theme.BG_PANEL_LIGHT, r.inflate(-4, -4), border_radius=6)
            pygame.draw.rect(canvas, col, r.inflate(-4, -4), 2, border_radius=6)
            theme.text(canvas, name, 17, col, (r.centerx, r.y + 22), anchor="center", bold=True)
            theme.text(canvas, sub, 13, theme.MUTED, (r.centerx, r.y + 44), anchor="center")
            if rot:
                theme.draw_rotation_arrow(canvas, (r.centerx, r.centery + 18), 26, rot, col, 3)
            else:
                theme.text(
                    canvas,
                    "Entrance (0,0)",
                    13,
                    theme.GOLD,
                    (r.centerx, r.bottom - 24),
                    anchor="center",
                )

        # Explanation on the right
        rx = diag.right + 36
        rw = body.right - rx - 24
        y = body.y + 28
        theme.text(canvas, "HOW THE SHIFTING MANOR WORKS", 20, theme.GOLD, (rx, y), bold=True)
        y += 36
        bullets = [
            (
                "Every K moves",
                "In Explorer (every 8 moves) & Haunted (every 5 moves), one 3×3 wing rotates 90° CW or CCW.",
            ),
            (
                "2-Move Telegraph",
                "Two moves before a shift, you feel a RUMBLE and see the glowing target wing & arrow on the Shift Clock.",
            ),
            (
                "What Moves",
                "ONLY hidden Pits and the Ghost rotate around the wing's centre. Rooms, walls, Entrance, and Heirloom stay fixed!",
            ),
            (
                "Marks Rotate Too!",
                "Your placed notes inside that wing rotate automatically so your bookkeeping stays truthful.",
            ),
            (
                "Tactical Hold",
                "If YOU stand inside the target wing when the timer hits 0, the manor holds its breath and the shift is SKIPPED!",
            ),
            (
                "Why Caretaker AI Wins",
                "Caretaker AI (B3) applies Rule R16 to transport all its logical facts & constraints by the exact rotation — beating Shift-Blind (B2) by +16.5% in Haunted!",
            ),
        ]
        for head, desc in bullets:
            theme.text(canvas, f"• {head}:", 16, theme.TEAL, (rx, y), bold=True)
            wrapped = theme.wrap(desc, 15, rw - 16)
            y += 20
            for line in wrapped:
                theme.text(canvas, line, 15, theme.INK, (rx + 14, y))
                y += 18
            y += 6

    def _draw_controls_ai(self, canvas: pygame.Surface, body: pygame.Rect) -> None:
        left = pygame.Rect(body.x + 20, body.y + 18, 480, body.height - 36)
        right = pygame.Rect(
            left.right + 18, body.y + 18, body.right - left.right - 38, body.height - 36
        )
        theme.panel(canvas, left, color=theme.BG_PANEL_LIGHT, radius=8)
        theme.panel(canvas, right, color=theme.BG_PANEL_LIGHT, radius=8)

        theme.text(
            canvas,
            "KEYBOARD & MOUSE CONTROLS",
            17,
            theme.GOLD,
            (left.x + 16, left.y + 14),
            bold=True,
        )
        ctrls = [
            ("WASD / Arrows / Click", "Move to adjacent room"),
            ("E or Click Entrance", "Leave Manor at (0,0)"),
            ("C + Direction", "Cast 1-use Charm along line"),
            ("Right-click / 1-4 / 0", "Cycle or set room marks"),
            ("T", "Toggle LIVE Autonomous AI Takeover!"),
            ("I", "Request Smart AI Hint (zero cheating)"),
            ("B", "Toggle Live AI Belief & Risk Overlay"),
            ("Space / Right / +/-", "Pause, Step, Speed in AI Play"),
            ("H / O / F1 / F2", "Guide / Settings / Presenter / SimLab"),
            ("R / N / F11 / Esc", "Restart / New Seed / Fullscreen / Pause"),
        ]
        for i, (k, v) in enumerate(ctrls):
            cy = left.y + 48 + i * 32
            theme.badge(canvas, k, (left.x + 16, cy), color=theme.GOLD, size=13)
            theme.text(canvas, v, 15, theme.INK, (left.x + 216, cy + 4))

        theme.text(
            canvas,
            "AUTONOMOUS AI MODES & AGENTS",
            17,
            theme.CYAN,
            (right.x + 16, right.y + 14),
            bold=True,
        )
        items = [
            (
                "LIVE AI AUTO-PLAY",
                theme.CYAN,
                "Watch ANY real agent (B3, B5, B2b, B2, B1, B0, B4) play a live Game turn-by-turn with full fog, animations, live rule log & instant manual takeover [T]!",
            ),
            (
                "DUEL vs AI",
                theme.GOLD,
                "Play a seed manually first, then watch Caretaker B3 tackle the exact same seed and compare scores side by side.",
            ),
            (
                "TRACE INSPECTOR [V]",
                theme.VIOLET,
                "Step forward/backward through a frozen trace and click ANY room to inspect its complete forward-chaining Why? proof tree.",
            ),
            (
                "SIMULATION LAB [F2]",
                theme.TEAL,
                "Explore 200-seed statistical win rates, 95% Wilson CIs, and run a live benchmark right in the app.",
            ),
        ]
        y = right.y + 50
        for head, col, desc in items:
            theme.text(canvas, head, 16, col, (right.x + 16, y), bold=True)
            y += 22
            for line in theme.wrap(desc, 15, right.width - 32):
                theme.text(canvas, line, 15, theme.INK, (right.x + 16, y))
                y += 19
            y += 10
