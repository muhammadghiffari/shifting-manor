"""End-to-end interactive UI for Shifting Manor.

Supports Manual Play, Real Autonomous Live AI Play (all agents B0-B5),
Human vs AI Duel mode, Watch AI Trace Inspector, Interactive 4-Lesson Tutorial,
Visual How-To-Play Field Guide, Simulation Lab, Settings & Accessibility,
procedural gothic audio, lantern fog-of-war, particles, and Run Card export.

Only this package imports pygame. Engine/KB/agents/sim stay strictly headless.
"""

from __future__ import annotations

import asyncio
import base64
import io
import math
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from shifting_manor.engine.game import Game
from shifting_manor.engine.grid import DIRS, in_bounds, manhattan, wing_cells, wing_of
from shifting_manor.engine.modes import MODES
from shifting_manor.engine.types import (
    Bumped,
    CastCharm,
    Cell,
    Dir,
    GhostBanished,
    Leave,
    Move,
    OilLow,
    Percepts,
    PickedUp,
    ShiftApplied,
    ShiftSkipped,
    ShiftTelegraph,
)
from shifting_manor.kb.rules import RULES
from shifting_manor.trace import WATCH_AGENTS, ProofNode
from shifting_manor.ui import fx, strings, theme
from shifting_manor.ui.audio import AudioManager
from shifting_manor.ui.guide import GuideOverlay
from shifting_manor.ui.live_ai import (
    LIVE_AGENTS,
    HintInfo,
    LiveAIController,
    compute_human_hint,
)
from shifting_manor.ui.settings import Settings, SettingsOverlay
from shifting_manor.ui.simlab import SimLabScene
from shifting_manor.ui.tutorial import TutorialScene

if TYPE_CHECKING:
    import pygame


LOGICAL_SIZE = theme.LOGICAL_SIZE
BOARD_PX = theme.BOARD_PX
CELL = theme.CELL
IS_WEB = sys.platform == "emscripten"

WING_NAMES = {0: "FOYER", 1: "SE", 2: "NW", 3: "NE"}
MARK_ORDER = (None, "?", "pit", "ghost", "safe")
DEMO_SEEDS = ("HAUNT-4F2A", "HAUNT-7C1D", "HAUNT-5D7C")


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


def _dashed_rect(surface, color, rect, *, width: int = 2, dash: int = 8) -> None:
    import pygame

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


@dataclass
class ShiftAnimation:
    wing: int
    direction: str
    mapping: dict[Cell, Cell]
    elapsed: float
    duration: float
    marks: dict[Cell, str]
    dust: list[tuple[int, int]]


@dataclass
class RunSummary:
    who: str
    outcome: str
    score: int
    stars: int
    par: int
    actions: int
    oil_left: int
    charms: int
    marks_or_rules: int
    path: tuple[Cell, ...]
    reveal: dict[str, Any]
    ghost_banished: bool = False
    has_treasure: bool = False


class App:
    """One window, complete scene suite, manual + live autonomous AI + Duel + Lab."""

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
        self.settings = Settings()
        self.sfx = AudioManager(enabled=audio)
        self.sfx.start_ambient()
        pygame.key.set_repeat(220, 110)
        self.screen = None
        self.view_rect = pygame.Rect(0, 0, *LOGICAL_SIZE)
        self._set_window()
        self.canvas = pygame.Surface(LOGICAL_SIZE)
        pygame.display.set_caption(strings.TITLE)
        self.clock = pygame.time.Clock()
        self.running = True
        self._t = 0.0

        # Navigation & scenes
        self.scene = "title"
        self.mode_names = list(MODES)
        self.mode_index = 1  # explorer default
        self.agent_names = list(LIVE_AGENTS)
        self.agent_index = 0  # b3 default
        self.seed_editing = False
        self.presenter_overlay = False

        # Sub-views & overlays
        self.watch = None
        self.tutorial: TutorialScene | None = None
        self.simlab: SimLabScene | None = None
        self.guide: GuideOverlay | None = None
        self.settings_overlay: SettingsOverlay | None = None

        # Demo loop state
        self.demo = False
        self.demo_mode = "explorer"
        self.demo_seeds: list[str] = []
        self.demo_index = 0
        self.demo_pause = 0.0

        # Active gameplay state (shared by Manual, Live AI, and Duel)
        self.game: Game | None = None
        self.percepts = Percepts()
        self.events: list[Any] = []
        self.marks: dict[Cell, str] = {}
        self.visited: set[Cell] = set()
        self.room_senses: dict[Cell, set[str]] = {}
        self.path: list[Cell] = []
        self.history: list[tuple[Percepts, list[Any], Cell, int]] = []
        self.charm_aim = False
        self.facing: Dir = "S"
        self.paused = False
        self.shift_anim: ShiftAnimation | None = None
        self.hover: Cell | None = None
        self.result: dict[str, Any] | None = None
        self.sidebar_tab = 0  # 0: Marks/Controls, 1: Live AI Log, 2: KB Rules (24)
        self.log_scroll = 0
        self.kb_scroll = 0
        self._log_hits: list[tuple[pygame.Rect, Any]] = []
        self._proof: ProofNode | None = None
        self._proof_msg = ""
        self._proof_scroll = 0
        self._proof_expanded: set[int] = set()
        self._proof_hits: list[tuple[pygame.Rect, ProofNode]] = []

        # Live autonomous AI & hint state
        self.auto_play = False
        self.auto_paused = False
        self.auto_speed = 1.0
        self.auto_timer = 0.0
        self.live_ai: LiveAIController | None = None
        self.live_ai_agent = "b3"
        self._ai_pending_events: list[Any] = []
        self.belief_overlay = False
        self.active_hint: HintInfo | None = None
        self._hint_ctrl: LiveAIController | None = None

        # Duel state
        self.duel_active = False
        self.duel_phase = ""  # "human" | "halftime" | "ai" | "done"
        self.duel_human: RunSummary | None = None
        self.duel_ai: RunSummary | None = None
        self.duel_path_filter = "both"  # "both" | "human" | "ai"

        # Movement easing & visual FX
        self._move_from: Cell = (0, 0)
        self._move_t = 1.0
        self.fx = fx.FXManager()
        self._glow = self._make_glow()
        self._last_buttons: dict[str, pygame.Rect] = {}
        self._title_stars = [
            (
                random.Random(101 + i).randrange(20, LOGICAL_SIZE[0] - 20),
                random.Random(201 + i).randrange(18, 340),
                random.Random(301 + i).uniform(0.0, math.tau),
                1 + (i % 2),
            )
            for i in range(44)
        ]

    # -- window -----------------------------------------------------------
    def _set_window(self) -> None:
        pygame = self.pygame
        if self.windowed or IS_WEB:
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

    def _apply_settings(self) -> None:
        s = self.settings
        self.sfx.set_volumes(master=s.master_volume, music=s.music_volume, sfx=s.sfx_volume)
        theme.set_accessibility(high_contrast=s.high_contrast, font_scale=s.font_scale)
        self.auto_speed = s.default_ai_speed

    # -- overlays ---------------------------------------------------------
    def open_guide(self) -> None:
        self.guide = GuideOverlay(
            on_close=self._close_guide,
            on_start_tutorial=self._guide_to_tutorial,
            on_start_auto=self._guide_to_auto,
        )
        self.sfx.play("ui_click")

    def _close_guide(self) -> None:
        self.guide = None
        self.sfx.play("ui_back")

    def _guide_to_tutorial(self) -> None:
        self.guide = None
        self.start_tutorial()

    def _guide_to_auto(self) -> None:
        self.guide = None
        self.start_live_ai(
            self.mode_names[self.mode_index], self.seed, self.agent_names[self.agent_index]
        )

    def open_settings(self) -> None:
        self.settings_overlay = SettingsOverlay(
            self.settings,
            on_apply=self._apply_settings,
            on_close=self._close_settings,
        )
        self.sfx.play("ui_click")

    def _close_settings(self) -> None:
        self.settings_overlay = None
        self.sfx.play("ui_back")

    # -- game lifecycle ---------------------------------------------------
    def _init_play_state(
        self,
        mode: str,
        seed: str,
        *,
        autonomous: bool = False,
        agent: str = "b3",
        duel: bool = False,
        duel_phase: str = "",
    ) -> None:
        self.seed = seed
        self.game = Game(mode, self.seed)
        self.percepts = self.game.observe()
        self.events = []
        self.marks = {}
        self.visited = {self.game.state.agent}
        self.room_senses = {}
        self._record_room_sense(self.game.state.agent, self.percepts)
        self.path = [self.game.state.agent]
        self.history = [(self.percepts, [], self.game.state.agent, self.game.state.oil)]
        self.charm_aim = False
        self.facing = "S"
        self.paused = False
        self.shift_anim = None
        self.fx.clear()
        self.fx.toast_timer = 0.0
        self.hover = None
        self.result = None
        self.seed_editing = False
        self._move_from = self.game.state.agent
        self._move_t = 1.0
        self.fx.clear()
        self.active_hint = None
        self._hint_ctrl = None
        self._proof = None
        self._proof_msg = ""
        self.log_scroll = 0
        self.kb_scroll = 0

        self.duel_active = duel
        self.duel_phase = duel_phase
        self.live_ai_agent = agent
        self.auto_play = autonomous
        self.auto_paused = False
        self.auto_speed = self.settings.default_ai_speed
        self.auto_timer = 0.28
        self._ai_pending_events = []

        if autonomous:
            self.live_ai = LiveAIController(self.game.info(), agent)
            self.belief_overlay = True
            self.sidebar_tab = 1
            self.fx.toast(
                f"LIVE AUTONOMOUS AI ({agent.upper()}) STARTED!",
                theme.CYAN,
                2.6,
            )
        else:
            self.live_ai = None
            self.belief_overlay = False
            self.sidebar_tab = 0
        self.scene = "play"
        self._update_audio_tension()

    def start_game(self, mode: str | None = None, seed: str | None = None) -> None:
        """Start a standard manual Play session."""
        mode = mode or self.mode_names[self.mode_index]
        self._init_play_state(mode, seed or self.seed, autonomous=False, duel=False)

    def start_live_ai(
        self,
        mode: str | None = None,
        seed: str | None = None,
        agent: str | None = None,
    ) -> None:
        """Start a REAL autonomous agent playing live turn-by-turn on the board."""
        mode = mode or self.mode_names[self.mode_index]
        agent = agent or self.agent_names[self.agent_index]
        self._init_play_state(mode, seed or self.seed, autonomous=True, agent=agent, duel=False)

    def start_duel(self, mode: str | None = None, seed: str | None = None) -> None:
        """Start Duel mode: human plays first, then Caretaker B3 plays the exact same seed."""
        mode = mode or self.mode_names[self.mode_index]
        self.duel_human = None
        self.duel_ai = None
        self.duel_path_filter = "both"
        self._init_play_state(
            mode,
            seed or self.seed,
            autonomous=False,
            agent="b3",
            duel=True,
            duel_phase="human",
        )
        self.fx.toast("DUEL PHASE 1: YOUR TURN — Beat Caretaker B3 on this seed!", theme.GOLD, 3.0)

    def start_duel_ai_phase(self, *, fast: bool = False) -> None:
        """Run Phase 2 of Duel: Caretaker B3 plays the exact same seed."""
        assert self.game is not None
        mode = self.game.mode.name
        self._init_play_state(
            mode,
            self.seed,
            autonomous=True,
            agent="b3",
            duel=True,
            duel_phase="ai",
        )
        if fast:
            self._fast_finish_live_ai()

    def start_tutorial(self) -> None:
        self.tutorial = TutorialScene(
            on_exit=self._exit_to_modes,
            on_play_real=lambda: self.start_game("apprentice", self.seed),
            audio=self.sfx,
        )
        self.scene = "tutorial"

    def start_simlab(self) -> None:
        self.simlab = SimLabScene(on_exit=self._exit_to_modes, audio=self.sfx)
        self.scene = "simlab"

    def start_watch(
        self, mode: str | None = None, seed: str | None = None, agent: str | None = None
    ) -> None:
        mode = mode or self.mode_names[self.mode_index]
        self.seed = seed or self.seed
        chosen = agent or self.agent_names[self.agent_index]
        if chosen not in WATCH_AGENTS:
            chosen = "b3"
        from shifting_manor.trace import build_trace
        from shifting_manor.ui.watch import WatchView

        store = build_trace(mode, self.seed, chosen)
        self.watch = WatchView(
            store,
            to_logical=self._to_logical,
            on_exit=self._exit_watch,
            on_fire=lambda: self.sfx.play("rule_fire", cooldown=0.125),
            seed=self.seed,
            show_coords=self.settings.show_coords,
        )
        self.watch.speed = self.settings.default_ai_speed
        self.scene = "watch"

    def start_demo(self, seed: str | None = None, mode: str | None = None) -> None:
        self.demo = True
        self.demo_mode = mode or "explorer"
        first = seed or self.seed
        self.demo_seeds = [first] + [s for s in ("HAUNT-7C1D", "HAUNT-5D7C") if s != first]
        self.demo_index = 0
        self.demo_pause = 0.0
        self.start_watch(self.demo_mode, self.demo_seeds[0], "b3")

    def _exit_watch(self) -> None:
        self.demo = False
        self.scene = "modes"

    def _exit_to_modes(self) -> None:
        self.scene = "modes"

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
        if self.duel_active:
            self.start_duel(mode, self.seed)
        elif self.auto_play:
            self.start_live_ai(mode, self.seed, self.live_ai_agent)
        else:
            self.start_game(mode, self.seed)

    def toggle_auto_play(self) -> None:
        """Seamlessly hand over control to a real synced AI agent, or take back control."""
        if self.game is None or self.game.state.done:
            return
        if self.duel_active and self.duel_phase == "human":
            self.fx.toast(
                "Auto-Play is disabled during your Duel turn — try AI Hint [I]!", theme.ORANGE
            )
            return
        if self.auto_play:
            self.auto_play = False
            self.auto_paused = False
            self.fx.toast("MANUAL CONTROL RESTORED — You are at the lantern!", theme.GOLD, 2.2)
            self.sfx.play("ui_click")
            return
        agent_name = self.agent_names[self.agent_index]
        self.live_ai_agent = agent_name
        ctrl = LiveAIController(self.game.info(), agent_name)
        if len(self.history) > 1:
            ctrl.replay_prefix(self.history[:-1])
        self._ai_pending_events = list(self.history[-1][1]) if self.history else []
        self.live_ai = ctrl
        self.auto_play = True
        self.auto_paused = False
        self.auto_timer = 0.18
        self.belief_overlay = True
        self.sidebar_tab = 1
        self.active_hint = None
        self.fx.toast(
            f"AI TAKEOVER: Real {agent_name.upper()} agent now playing live!", theme.CYAN, 2.6
        )
        self.sfx.play("ui_click")

    def request_hint(self) -> None:
        """Ask a fair, zero-cheating B3 Caretaker synced to your history for a hint."""
        if self.game is None or self.game.state.done:
            return
        hint, ctrl = compute_human_hint(self.game.info(), self.history)
        self.active_hint = hint
        self._hint_ctrl = ctrl
        self.fx.toast(hint.summary, theme.TEAL, 3.4)
        self.sfx.play("glimmer", gain=0.7)

    def _step_live_ai(self) -> None:
        """Execute ONE real live decision from the active autonomous agent."""
        if self.game is None or self.live_ai is None or self.game.state.done:
            return
        action = self.live_ai.decide_next(
            self.percepts,
            self._ai_pending_events,
            position=self.game.state.agent,
            oil=self.game.state.oil,
        )
        self._ai_pending_events = []
        if self.live_ai.log:
            self.sfx.play("rule_fire", cooldown=0.125, gain=0.7)
        self._execute_action(action)

    def _fast_finish_live_ai(self) -> None:
        """Instantly finish the remaining turns of a Live AI / Duel AI run."""
        if self.game is None or self.live_ai is None:
            return
        guard = 0
        while not self.game.state.done and guard < 400:
            self._step_live_ai()
            guard += 1
        self.shift_anim = None

    def _build_summary(self, who: str, par: int) -> RunSummary:
        assert self.game is not None
        st = self.game.state
        count = self.live_ai.total_firings if (self.auto_play and self.live_ai) else len(self.marks)
        return RunSummary(
            who=who,
            outcome=st.outcome or "stalled",
            score=self.game.score(),
            stars=self.game.stars(par),
            par=par,
            actions=st.actions_taken,
            oil_left=st.oil,
            charms=st.charms_cast,
            marks_or_rules=count,
            path=tuple(self.path),
            reveal=self.game.reveal(),
            ghost_banished=st.ghost_banished,
            has_treasure=st.has_treasure,
        )

    def _finish(self) -> None:
        assert self.game is not None
        from shifting_manor.sim.runner import run_game

        par = run_game(self.game.mode.name, self.seed, "b4").actions
        outcome = self.game.state.outcome or "stalled"
        if outcome == "escaped_treasure":
            self.sfx.play("win")
        elif outcome == "escaped_empty":
            self.sfx.play("escape_empty")
        else:
            self.sfx.play("lose")
        self.sfx.set_tension(0.0)

        self.result = {
            "outcome": outcome,
            "score": self.game.score(),
            "stars": self.game.stars(par),
            "par": par,
            "autonomous": self.auto_play,
            "agent": self.live_ai_agent if self.auto_play else "human",
            "rules_fired": self.live_ai.total_firings if self.live_ai else 0,
        }
        self.paused = False
        self.shift_anim = None
        self.fx.clear()
        self.fx.toast_timer = 0.0

        if self.duel_active and self.duel_phase == "human":
            self.duel_human = self._build_summary("YOU (HUMAN)", par)
            self.duel_phase = "halftime"
            self.scene = "duel_halftime"
            return
        if self.duel_active and self.duel_phase == "ai":
            self.duel_ai = self._build_summary("CARETAKER AI (B3)", par)
            self.duel_phase = "done"
            self.scene = "duel_result"
            return
        self.scene = "result"

    def _request_quit(self) -> None:
        if IS_WEB:
            self.paused = False
            self.scene = "title"
            self.fx.toast("Returned to Title (close browser tab to exit).", theme.GOLD, 2.2)
        else:
            self.running = False

    def save_run_card(self) -> Path:
        mode = self.game.mode.name if self.game else "manor"
        tag = f"{self.seed}_{mode}".replace("/", "_")
        filename = f"runcard_{tag}.png"
        self.draw()
        if IS_WEB:
            try:
                import platform

                buf = io.BytesIO()
                self.pygame.image.save(self.canvas, buf, filename)
                b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                doc = platform.window.document
                link = doc.createElement("a")
                link.href = f"data:image/png;base64,{b64}"
                link.download = filename
                doc.body.appendChild(link)
                link.click()
                doc.body.removeChild(link)
                self.fx.toast(f"Downloading Run Card: {filename}", theme.TEAL, 3.0)
                self.sfx.play("ui_click")
                return Path(filename)
            except (ImportError, AttributeError, OSError, RuntimeError):
                self.fx.toast("Run Card captured in browser memory.", theme.TEAL, 2.5)
                return Path(filename)
        out_dir = Path.cwd() / "runcards"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / filename
        self.pygame.image.save(self.canvas, str(path))
        self.fx.toast(f"Saved Run Card: runcards/{path.name}", theme.TEAL, 3.0)
        self.sfx.play("ui_click")
        return path

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
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F1:
            self.presenter_overlay = not self.presenter_overlay
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F2 and not self.seed_editing:
            if self.scene == "simlab":
                self.scene = "modes"
            else:
                self.start_simlab()
            return

        logical = self._to_logical(event.pos) if hasattr(event, "pos") else None

        # Active modal overlays take priority
        if self.settings_overlay is not None:
            self.settings_overlay.handle(event, logical)
            return
        if self.guide is not None:
            self.guide.handle(event, logical)
            return

        if self.scene == "watch" and self.watch is not None:
            self.watch.handle(event)
            return
        if self.scene == "tutorial" and self.tutorial is not None:
            self.tutorial.handle(event, logical)
            return
        if self.scene == "simlab" and self.simlab is not None:
            self.simlab.handle(event, logical)
            return

        if event.type == pygame.MOUSEMOTION and logical is not None:
            self.hover = self._cell_at(logical) if self.scene == "play" else None
            return

        if self.scene == "title":
            self._handle_title(event)
        elif self.scene == "modes":
            self._handle_modes(event)
        elif self.scene == "play":
            self._handle_play(event)
        elif self.scene == "duel_halftime":
            self._handle_duel_halftime(event)
        elif self.scene == "duel_result":
            self._handle_duel_result(event)
        elif self.scene == "result":
            self._handle_result(event)

    def _key(self, event) -> int | None:
        pygame = self.pygame
        return event.key if event.type == pygame.KEYDOWN else None

    def _handle_title(self, event) -> None:
        pygame = self.pygame
        key = self._key(event)
        if key in (pygame.K_ESCAPE, pygame.K_q):
            self._request_quit()
            return
        if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
            self.sfx.play("ui_click")
            self.scene = "modes"
            return
        if key == pygame.K_a:
            self.sfx.play("ui_click")
            self.start_live_ai(self.mode_names[self.mode_index], self.seed, "b3")
            return
        if key == pygame.K_d:
            self.sfx.play("ui_click")
            self.start_duel(self.mode_names[self.mode_index], self.seed)
            return
        if key == pygame.K_h:
            self.open_guide()
            return
        if key == pygame.K_t:
            self.start_tutorial()
            return
        if key == pygame.K_v:
            self.start_watch(self.mode_names[self.mode_index], self.seed, "b3")
            return
        if key == pygame.K_o:
            self.open_settings()
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self._to_logical(event.pos)
            self.sfx.play("ui_click")
            for name, rect in self._last_buttons.items():
                if not rect.collidepoint(pos):
                    continue
                if name == "title_play":
                    self.scene = "modes"
                elif name == "title_auto":
                    self.start_live_ai(self.mode_names[self.mode_index], self.seed, "b3")
                elif name == "title_duel":
                    self.start_duel(self.mode_names[self.mode_index], self.seed)
                elif name == "title_tutorial":
                    self.start_tutorial()
                elif name == "title_guide":
                    self.open_guide()
                elif name == "title_watch":
                    self.start_watch(self.mode_names[self.mode_index], self.seed, "b3")
                elif name == "title_simlab":
                    self.start_simlab()
                elif name == "title_settings":
                    self.open_settings()
                return
            # Clicking anywhere else on Title enters Mode Select
            self.scene = "modes"

    def _handle_modes(self, event) -> None:
        pygame = self.pygame
        key = self._key(event)

        if self.seed_editing and event.type == pygame.KEYDOWN:
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
                self.seed_editing = False
                if not self.seed.strip():
                    self.seed = "HAUNT-4F2A"
                return
            if key == pygame.K_BACKSPACE:
                self.seed = self.seed[:-1]
                return
            ch = getattr(event, "unicode", "")
            if ch and (ch.isalnum() or ch in "-_") and len(self.seed) < 18:
                self.seed += ch.upper()
            return

        if key in (pygame.K_ESCAPE, pygame.K_q):
            self.sfx.play("ui_back")
            if key == pygame.K_q:
                self._request_quit()
            else:
                self.scene = "title"
            return
        if key in (pygame.K_UP, pygame.K_LEFT, pygame.K_w):
            self.mode_index = (self.mode_index - 1) % len(self.mode_names)
            self.sfx.play("ui_hover")
        elif key in (pygame.K_DOWN, pygame.K_RIGHT, pygame.K_s):
            self.mode_index = (self.mode_index + 1) % len(self.mode_names)
            self.sfx.play("ui_hover")
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3):
            self.mode_index = key - pygame.K_1
            self.sfx.play("ui_click")
        elif key == pygame.K_a:
            self.agent_index = (self.agent_index + 1) % len(self.agent_names)
            self.sfx.play("ui_click")
        elif key == pygame.K_n:
            self.new_seed()
            self.sfx.play("ui_click")
        elif key == pygame.K_h:
            self.open_guide()
        elif key == pygame.K_t:
            self.start_tutorial()
        elif key == pygame.K_o:
            self.open_settings()
        elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
            self.sfx.play("ui_click")
            self.start_game(self.mode_names[self.mode_index], self.seed)
        elif key == pygame.K_l:
            self.sfx.play("ui_click")
            self.start_live_ai(
                self.mode_names[self.mode_index],
                self.seed,
                self.agent_names[self.agent_index],
            )
        elif key == pygame.K_d:
            self.sfx.play("ui_click")
            self.start_duel(self.mode_names[self.mode_index], self.seed)
        elif key == pygame.K_v:
            self.sfx.play("ui_click")
            self.start_watch(self.mode_names[self.mode_index], self.seed)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self._to_logical(event.pos)
            self.seed_editing = False
            for i, rect in enumerate(self._mode_rects()):
                if rect.collidepoint(pos):
                    self.mode_index = i
                    self.sfx.play("ui_click")
                    return
            for name, rect in self._last_buttons.items():
                if not rect.collidepoint(pos):
                    continue
                self.sfx.play("ui_click")
                if name == "seed_box":
                    self.seed_editing = True
                elif name == "seed_rand":
                    self.new_seed()
                elif name.startswith("preset_"):
                    self.seed = name.split("preset_", 1)[1]
                elif name == "agent":
                    self.agent_index = (self.agent_index + 1) % len(self.agent_names)
                elif name == "begin":
                    self.start_game(self.mode_names[self.mode_index], self.seed)
                elif name == "live_ai":
                    self.start_live_ai(
                        self.mode_names[self.mode_index],
                        self.seed,
                        self.agent_names[self.agent_index],
                    )
                elif name == "duel":
                    self.start_duel(self.mode_names[self.mode_index], self.seed)
                elif name == "watch":
                    self.start_watch(self.mode_names[self.mode_index], self.seed)
                elif name == "tutorial":
                    self.start_tutorial()
                elif name == "guide":
                    self.open_guide()
                elif name == "simlab":
                    self.start_simlab()
                elif name == "settings":
                    self.open_settings()
                elif name == "back":
                    self.scene = "title"
                return

    def _handle_play(self, event) -> None:
        pygame = self.pygame
        key = self._key(event)

        # Proof tree modal inside Live AI Play
        if self._proof is not None or self._proof_msg:
            if key == pygame.K_ESCAPE:
                self._proof = None
                self._proof_msg = ""
                return
            if event.type == pygame.MOUSEWHEEL:
                self._proof_scroll = max(0, self._proof_scroll - event.y * 34)
                return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = self._to_logical(event.pos)
                close = self._last_buttons.get("proof_close")
                if close and close.collidepoint(pos):
                    self._proof = None
                    self._proof_msg = ""
                    return
                for rect, node in self._proof_hits:
                    if rect.collidepoint(pos):
                        if node.id in self._proof_expanded:
                            self._proof_expanded.discard(node.id)
                        elif node.children:
                            self._proof_expanded.add(node.id)
                        return
            return

        if self.shift_anim is not None and event.type in (
            pygame.KEYDOWN,
            pygame.MOUSEBUTTONDOWN,
        ):
            self.shift_anim = None
            return

        if self.paused:
            if key == pygame.K_ESCAPE:
                self.paused = False
            elif key == pygame.K_h:
                self.paused = False
                self.open_guide()
            elif key == pygame.K_o:
                self.paused = False
                self.open_settings()
            elif key == pygame.K_r:
                self.restart()
            elif key == pygame.K_m:
                self.scene = "title"
            elif key == pygame.K_q:
                self._request_quit()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = self._to_logical(event.pos)
                for name, rect in self._last_buttons.items():
                    if not rect.collidepoint(pos):
                        continue
                    if name == "pause_resume":
                        self.paused = False
                    elif name == "pause_guide":
                        self.paused = False
                        self.open_guide()
                    elif name == "pause_settings":
                        self.paused = False
                        self.open_settings()
                    elif name == "pause_restart":
                        self.restart()
                    elif name == "pause_menu":
                        self.scene = "title"
                    return
            return

        if event.type == pygame.MOUSEWHEEL:
            if self.sidebar_tab == 1:
                self.log_scroll = max(0, self.log_scroll - event.y * 32)
            elif self.sidebar_tab == 2:
                self.kb_scroll = max(0, self.kb_scroll - event.y * 32)
            return

        if key == pygame.K_ESCAPE:
            self.paused = True
            return
        if key == pygame.K_q:
            self._request_quit()
            return
        if key == pygame.K_h:
            self.open_guide()
            return
        if key == pygame.K_o:
            self.open_settings()
            return
        if key == pygame.K_r:
            self.restart()
            return
        if key == pygame.K_n:
            self.restart(same_seed=False)
            return
        if key == pygame.K_t:
            self.toggle_auto_play()
            return
        if key == pygame.K_b:
            self.belief_overlay = not self.belief_overlay
            if self.belief_overlay and self.live_ai is None and self._hint_ctrl is None:
                self.request_hint()
            self.sfx.play("ui_click")
            return
        if key == pygame.K_TAB:
            self.sidebar_tab = (self.sidebar_tab + 1) % 3
            return
        if key == pygame.K_i and not self.auto_play:
            self.request_hint()
            return
        if key == pygame.K_w:
            self._open_live_proof(self.hover or (self.game.state.agent if self.game else None))
            return

        # Live AI playback controls
        if self.auto_play:
            if key == pygame.K_SPACE:
                self.auto_paused = not self.auto_paused
                self.sfx.play("ui_click")
                return
            if key in (pygame.K_RIGHT, pygame.K_PERIOD):
                self.auto_paused = True
                self._step_live_ai()
                return
            if key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                self._cycle_auto_speed(1)
                return
            if key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self._cycle_auto_speed(-1)
                return
            if key == pygame.K_f:
                self._fast_finish_live_ai()
                return
        else:
            # Manual player controls
            if key == pygame.K_e:
                self._try_leave()
                return
            if key == pygame.K_c:
                if self.game and self.game.state.charm_available:
                    self.charm_aim = not self.charm_aim
                    self.sfx.play("ui_click")
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
                if mark is not None and self.game is not None:
                    self.marks[self.game.state.agent] = mark
                    self.sfx.play("mark")
            elif key == pygame.K_0 and self.game is not None:
                self.marks.pop(self.game.state.agent, None)
                self.sfx.play("mark")

        if event.type == pygame.MOUSEBUTTONDOWN:
            pos = self._to_logical(event.pos)
            if event.button == 1:
                if self._handle_play_ui_click(pos):
                    return
                cell = self._cell_at(pos)
                if cell is None or self.game is None:
                    return
                if self.auto_play:
                    self._open_live_proof(cell)
                    return
                if self.charm_aim:
                    direction = _direction_to(self.game.state.agent, cell)
                    if direction is not None:
                        self._act(direction, charm=True)
                    else:
                        self.charm_aim = False
                    return
                if cell == self.game.state.entrance and self.game.state.agent == cell:
                    self._try_leave()
                    return
                if manhattan(self.game.state.agent, cell) == 1:
                    direction = _direction_to(self.game.state.agent, cell)
                    if direction is not None:
                        self._act(direction)
            elif event.button == 3 and not self.auto_play:
                cell = self._cell_at(pos)
                if cell is None:
                    return
                current = self.marks.get(cell)
                index = MARK_ORDER.index(current) if current in MARK_ORDER else 0
                nxt = MARK_ORDER[(index + 1) % len(MARK_ORDER)]
                if nxt is None:
                    self.marks.pop(cell, None)
                else:
                    self.marks[cell] = nxt
                self.sfx.play("mark")

    def _handle_play_ui_click(self, pos: tuple[int, int]) -> bool:
        for name, rect in self._last_buttons.items():
            if not rect.collidepoint(pos):
                continue
            if name == "leave":
                self._try_leave()
            elif (
                name == "charm"
                and self.game
                and self.game.state.charm_available
                and not self.auto_play
            ):
                self.charm_aim = not self.charm_aim
                self.sfx.play("ui_click")
            elif name == "toggle_auto":
                self.toggle_auto_play()
            elif name == "hint" and not self.auto_play:
                self.request_hint()
            elif name == "ai_pause":
                self.auto_paused = not self.auto_paused
                self.sfx.play("ui_click")
            elif name == "ai_step":
                self.auto_paused = True
                self._step_live_ai()
            elif name == "ai_speed":
                self._cycle_auto_speed(1)
            elif name == "ai_fast":
                self._fast_finish_live_ai()
            elif name == "beliefs":
                self.belief_overlay = not self.belief_overlay
                if self.belief_overlay and self.live_ai is None and self._hint_ctrl is None:
                    self.request_hint()
                self.sfx.play("ui_click")
            elif name == "guide":
                self.open_guide()
            elif name == "settings":
                self.open_settings()
            elif name.startswith("tab_"):
                self.sidebar_tab = int(name.split("_")[1])
                self.sfx.play("ui_click")
            elif name.startswith("mark_") and self.game is not None and not self.auto_play:
                val = name.split("_", 1)[1]
                target = self.game.state.agent
                if val == "clear":
                    self.marks.pop(target, None)
                else:
                    self.marks[target] = val
                self.sfx.play("mark")
            return True

        if self.sidebar_tab == 1:
            for rect, firing in self._log_hits:
                if rect.collidepoint(pos):
                    ctrl = self.live_ai or self._hint_ctrl
                    if ctrl is not None:
                        self._proof = ctrl.proof_for_firing(firing)
                        self._proof_msg = ""
                        self._proof_scroll = 0
                        self._proof_expanded = set()
                        self.auto_paused = True
                    return True
        return False

    def _open_live_proof(self, cell: Cell | None) -> None:
        if cell is None:
            return
        ctrl = self.live_ai or self._hint_ctrl
        if ctrl is None:
            self.fx.toast(
                "Toggle Beliefs [B] or Live AI [T] to inspect Why? proof trees.", theme.MUTED
            )
            return
        node = ctrl.proof_for_cell(cell)
        if node is None:
            self._proof = None
            self._proof_msg = strings.WATCH_WHY_EMPTY
        else:
            self._proof = node
            self._proof_msg = ""
        self._proof_scroll = 0
        self._proof_expanded = set()
        self.auto_paused = True

    def _cycle_auto_speed(self, delta: int) -> None:
        speeds = (0.5, 1.0, 2.0, 4.0)
        idx = min(range(len(speeds)), key=lambda i: abs(speeds[i] - self.auto_speed))
        self.auto_speed = speeds[(idx + delta) % len(speeds)]
        self.sfx.play("ui_click")

    def _handle_duel_halftime(self, event) -> None:
        pygame = self.pygame
        key = self._key(event)
        if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
            self.start_duel_ai_phase(fast=False)
        elif key == pygame.K_f:
            self.start_duel_ai_phase(fast=True)
        elif key == pygame.K_ESCAPE:
            self.duel_active = False
            self.scene = "modes"
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self._to_logical(event.pos)
            for name, rect in self._last_buttons.items():
                if not rect.collidepoint(pos):
                    continue
                if name == "duel_watch_ai":
                    self.start_duel_ai_phase(fast=False)
                elif name == "duel_fast_ai":
                    self.start_duel_ai_phase(fast=True)
                elif name == "duel_menu":
                    self.duel_active = False
                    self.scene = "modes"
                return

    def _handle_duel_result(self, event) -> None:
        pygame = self.pygame
        key = self._key(event)
        if key in (pygame.K_r, pygame.K_RETURN, pygame.K_KP_ENTER):
            self.start_duel(self.game.mode.name if self.game else "explorer", self.seed)
        elif key == pygame.K_n:
            self.new_seed()
            self.start_duel(self.game.mode.name if self.game else "explorer", self.seed)
        elif key == pygame.K_s:
            self.save_run_card()
        elif key in (pygame.K_m, pygame.K_ESCAPE):
            self.duel_active = False
            self.scene = "modes"
        elif key == pygame.K_q:
            self._request_quit()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self._to_logical(event.pos)
            for name, rect in self._last_buttons.items():
                if not rect.collidepoint(pos):
                    continue
                if name == "duel_rematch":
                    self.start_duel(self.game.mode.name if self.game else "explorer", self.seed)
                elif name == "duel_new":
                    self.new_seed()
                    self.start_duel(self.game.mode.name if self.game else "explorer", self.seed)
                elif name == "duel_card":
                    self.save_run_card()
                elif name == "duel_menu":
                    self.duel_active = False
                    self.scene = "modes"
                elif name.startswith("path_"):
                    self.duel_path_filter = name.split("_", 1)[1]
                return

    def _handle_result(self, event) -> None:
        pygame = self.pygame
        key = self._key(event)
        if key in (pygame.K_r, pygame.K_RETURN, pygame.K_KP_ENTER):
            self.restart()
        elif key == pygame.K_n:
            self.restart(same_seed=False)
        elif key == pygame.K_l:
            mode = self.game.mode.name if self.game else "explorer"
            self.start_live_ai(mode, self.seed, self.agent_names[self.agent_index])
        elif key == pygame.K_v:
            mode = self.game.mode.name if self.game else "explorer"
            self.start_watch(mode, self.seed, "b3")
        elif key == pygame.K_s:
            self.save_run_card()
        elif key in (pygame.K_m, pygame.K_ESCAPE):
            self.scene = "title"
        elif key == pygame.K_q:
            self._request_quit()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self._to_logical(event.pos)
            if self._last_buttons.get("replay", self._result_buttons()[0]).collidepoint(pos):
                self.restart()
            elif self._last_buttons.get("new", self._result_buttons()[1]).collidepoint(pos):
                self.restart(same_seed=False)
            elif self._last_buttons.get("menu", self._result_buttons()[2]).collidepoint(pos):
                self.scene = "title"
            elif self._last_buttons.get("live_ai") and self._last_buttons["live_ai"].collidepoint(
                pos
            ):
                mode = self.game.mode.name if self.game else "explorer"
                self.start_live_ai(mode, self.seed, self.agent_names[self.agent_index])
            elif self._last_buttons.get("watch") and self._last_buttons["watch"].collidepoint(pos):
                mode = self.game.mode.name if self.game else "explorer"
                self.start_watch(mode, self.seed, "b3")
            elif self._last_buttons.get("save_card") and self._last_buttons[
                "save_card"
            ].collidepoint(pos):
                self.save_run_card()

    def _try_leave(self) -> None:
        if self.game is None or self.game.state.done:
            return
        if self.game.state.agent != self.game.state.entrance:
            self.fx.toast(
                "Walk to the golden Entrance (0,0) first to Leave Manor!", theme.ORANGE, 2.2
            )
            return
        self._execute_action(Leave())

    def _move_or_charm(self, direction: Dir) -> None:
        if self.charm_aim:
            self._act(direction, charm=True)
            self.charm_aim = False
        else:
            self._act(direction)

    def _act(self, direction: Dir, *, charm: bool = False) -> None:
        if charm:
            self._execute_action(CastCharm(direction))
            self.charm_aim = False
        else:
            self._execute_action(Move(direction))

    def _execute_action(self, action) -> None:
        assert self.game is not None
        if self.game.state.done:
            return
        prev_pos = self.game.state.agent
        if isinstance(action, (Move, CastCharm)):
            self.facing = action.dir
        if isinstance(action, CastCharm) and self.game.state.charm_available:
            start = self._cell_rect(prev_pos).center
            dx, dy = DIRS[action.dir]
            end = (
                start[0] + dx * CELL * self.game.info().size,
                start[1] - dy * CELL * self.game.info().size,
            )
            self.fx.add_beam(start, end)
            self.sfx.play("charm_cast")
        step_result = self.game.step(action)
        if self.game.state.agent != prev_pos:
            self._move_from = prev_pos
            self._move_t = 1.0 if self.settings.reduce_motion else 0.0
            self.path.append(self.game.state.agent)
            self.sfx.play("step")
        self._after_step(step_result)

    def _record_room_sense(self, cell: Cell, p: Percepts) -> None:
        tags = self.room_senses.setdefault(cell, set())
        if p.breeze:
            tags.add("B")
        if p.chill:
            tags.add("C")
        if p.glimmer:
            tags.add("G")

    def _after_step(self, step_result) -> None:
        assert self.game is not None
        self.percepts = step_result.percepts
        self.events = list(step_result.events)
        self.visited.add(self.game.state.agent)
        self._record_room_sense(self.game.state.agent, self.percepts)
        self.history.append(
            (self.percepts, list(step_result.events), self.game.state.agent, self.game.state.oil)
        )
        if self.auto_play:
            self._ai_pending_events = list(step_result.events)
        else:
            self.active_hint = None
            if self.belief_overlay:
                _, ctrl = compute_human_hint(self.game.info(), self.history)
                self._hint_ctrl = ctrl

        agent_pos_px = self._cell_rect(self.game.state.agent).center
        for event in step_result.events:
            if isinstance(event, Bumped):
                self.fx.trigger_shake(4.0, 0.16)
                self.fx.add_popup(agent_pos_px, "WALL!", theme.MUTED, size=18)
                self.sfx.play("bump")
            elif isinstance(event, PickedUp):
                self.fx.burst(agent_pos_px, theme.GOLD, count=30, speed=115.0)
                self.fx.add_popup(agent_pos_px, "HEIRLOOM FOUND!", theme.GOLD, size=22)
                self.fx.toast(
                    "HEIRLOOM COLLECTED! Return to Entrance (0,0) & press [E]!", theme.GOLD, 3.2
                )
                self.sfx.play("pickup")
            elif isinstance(event, GhostBanished):
                gpx = self._cell_rect(event.cell).center
                self.fx.burst(gpx, theme.CYAN, count=32, speed=125.0)
                self.fx.add_popup(gpx, "GHOST BANISHED! +200", theme.CYAN, size=22)
                self.fx.trigger_shake(7.0, 0.3)
                self.sfx.play("ghost_banish")
            elif isinstance(event, OilLow):
                self.fx.toast(f"LANTERN OIL LOW ({event.oil} left)!", theme.RED, 2.5)
                self.sfx.play("oil_low")
            elif isinstance(event, ShiftTelegraph):
                wname = WING_NAMES.get(event.wing, str(event.wing))
                self.fx.trigger_shake(4.0, 0.2)
                self.fx.toast(
                    f"RUMBLE! Wing {wname} rotates {event.direction.upper()} in {event.in_actions} moves!",
                    theme.ORANGE,
                    2.6,
                )
                self.sfx.play("rumble")
            elif isinstance(event, ShiftSkipped):
                wname = WING_NAMES.get(event.wing, str(event.wing))
                self.fx.toast(f"Wing {wname} shift skipped ({event.reason})!", theme.TEAL, 2.2)
            elif isinstance(event, ShiftApplied):
                pre = {c: self.marks[c] for c in event.mapping if c in self.marks}
                self.marks = {event.mapping.get(c, c): mark for c, mark in self.marks.items()}
                # Clear stale sense memory inside the rotated wing
                for c in event.mapping:
                    self.room_senses.pop(c, None)
                rng = random.Random(f"{self.seed}:{event.wing}:{event.direction}")
                dust = [
                    (rng.randrange(6, 3 * CELL - 6), rng.randrange(6, 3 * CELL - 6))
                    for _ in range(28)
                ]
                if not self.settings.reduce_motion:
                    self.shift_anim = ShiftAnimation(
                        event.wing,
                        event.direction,
                        dict(event.mapping),
                        0.0,
                        0.85,
                        pre,
                        dust,
                    )
                    self.fx.trigger_shake(7.0, 0.4)
                wname = WING_NAMES.get(event.wing, str(event.wing))
                self.fx.toast(
                    f"WING {wname} ROTATED {event.direction.upper()} — MARKS TRANSPORTED!",
                    theme.GOLD,
                    2.6,
                )
                self.sfx.play("shift")

        # Subtle sense cues on entering a room
        if self.percepts.glimmer and not self.game.state.has_treasure:
            self.sfx.play("glimmer", cooldown=0.5, gain=0.55)
        elif self.percepts.chill:
            self.sfx.play("chill", cooldown=0.6, gain=0.45)
        elif self.percepts.breeze:
            self.sfx.play("breeze", cooldown=0.6, gain=0.35)

        self._update_audio_tension()
        if step_result.done or self.game.state.done:
            self._finish()

    def _update_audio_tension(self) -> None:
        if self.game is None:
            self.sfx.set_tension(0.0)
            return
        st = self.game.state
        oil_ratio = st.oil / max(1, st.start_oil)
        tension = 0.0
        if self.percepts.breeze:
            tension += 0.25
        if self.percepts.chill:
            tension += 0.45
        if self.percepts.rumble is not None:
            tension += 0.35
        if oil_ratio <= 0.25:
            tension += 0.45
        self.sfx.set_tension(min(1.0, tension))

    # -- update -----------------------------------------------------------
    def update(self, dt: float) -> None:
        self._t += dt
        if self.guide is not None:
            self.guide.update(dt)
        if self.scene == "tutorial" and self.tutorial is not None:
            self.tutorial.update(dt)
            return
        if self.scene == "simlab" and self.simlab is not None:
            self.simlab.update(dt)
            return
        if self.scene == "watch" and self.watch is not None:
            self.watch.update(dt)
            if self.demo and self.watch.finished():
                self.demo_pause += dt
                if self.demo_pause >= 3.0:
                    self.demo_pause = 0.0
                    self.demo_index = (self.demo_index + 1) % len(self.demo_seeds)
                    self.start_watch(self.demo_mode, self.demo_seeds[self.demo_index], "b3")
            elif self.demo:
                self.demo_pause = 0.0
            return

        if self._move_t < 1.0:
            self._move_t = min(1.0, self._move_t + dt / 0.14)

        if self.shift_anim is not None:
            self.shift_anim.elapsed += dt
            if self.shift_anim.elapsed >= self.shift_anim.duration:
                self.shift_anim = None

        if self.scene == "play" and self.game is not None and not self.paused:
            # Ambient percept particles in current room
            rect = self._cell_rect(self.game.state.agent)
            self.fx.emit_percepts(
                rect,
                breeze=self.percepts.breeze,
                chill=self.percepts.chill,
                glimmer=self.percepts.glimmer and not self.game.state.has_treasure,
                dt=dt,
            )
            # Live Autonomous AI heartbeat
            if (
                self.auto_play
                and not self.auto_paused
                and self.shift_anim is None
                and self._proof is None
                and self.guide is None
                and self.settings_overlay is None
                and not self.game.state.done
            ):
                self.auto_timer -= dt * max(0.25, self.auto_speed)
                if self.auto_timer <= 0.0:
                    self._step_live_ai()
                    self.auto_timer = 0.55

        self.fx.update(dt)

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
        width, gap = 360, 26
        x0 = (LOGICAL_SIZE[0] - (3 * width + 2 * gap)) // 2
        return [pygame.Rect(x0 + i * (width + gap), 132, width, 242) for i in range(3)]

    def _begin_rect(self) -> pygame.Rect:
        return self.pygame.Rect(74, 594, 270, 56)

    def _watch_rect(self) -> pygame.Rect:
        return self.pygame.Rect(934, 594, 270, 56)

    def _agent_rect(self) -> pygame.Rect:
        return self.pygame.Rect(74, 486, 1130, 52)

    def _result_panel_rect(self) -> pygame.Rect:
        return self.pygame.Rect(560, 152, 672, 514)

    def _result_board_rect(self) -> pygame.Rect:
        return self.pygame.Rect(48, 166, 480, 480)

    def _result_buttons(self) -> list[pygame.Rect]:
        pygame = self.pygame
        panel = self._result_panel_rect()
        width, gap = 190, 24
        x0 = panel.centerx - (3 * width + 2 * gap) // 2
        return [pygame.Rect(x0 + i * (width + gap), panel.bottom - 66, width, 50) for i in range(3)]

    # -- drawing ----------------------------------------------------------
    def draw(self) -> None:
        self.canvas.fill(theme.BG)
        mouse = self._to_logical(self.pygame.mouse.get_pos())
        if self.scene == "title":
            self._draw_title(mouse)
        elif self.scene == "modes":
            self._draw_modes(mouse)
        elif self.scene == "play":
            self._draw_play(mouse)
        elif self.scene == "duel_halftime":
            self._draw_duel_halftime(mouse)
        elif self.scene == "duel_result":
            self._draw_duel_result(mouse)
        elif self.scene == "result":
            self._draw_result(mouse)
        elif self.scene == "watch" and self.watch is not None:
            self.watch.draw(self.canvas)
        elif self.scene == "tutorial" and self.tutorial is not None:
            self.tutorial.draw(self.canvas, mouse)
        elif self.scene == "simlab" and self.simlab is not None:
            self.simlab.draw(self.canvas, mouse)

        if self.presenter_overlay:
            self._draw_presenter_overlay()
        if self.guide is not None:
            self.guide.draw(self.canvas, mouse)
        if self.settings_overlay is not None:
            self.settings_overlay.draw(self.canvas, mouse)

    def run(self, max_frames: int | None = None, screenshot: str | None = None) -> None:
        pygame = self.pygame
        frames = 0
        while self.running:
            dt = min(0.05, self.clock.tick(60) / 1000.0)
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

    async def run_async(self, max_frames: int | None = None, screenshot: str | None = None) -> None:
        """Async frame loop required by WebAssembly / pygbag browsers."""
        pygame = self.pygame
        frames = 0
        while self.running:
            dt = min(0.05, self.clock.tick(60) / 1000.0)
            for event in pygame.event.get():
                self.handle(event)
            self.update(dt)
            self.draw()
            self._present()
            await asyncio.sleep(0)
            frames += 1
            if max_frames is not None and frames >= max_frames:
                break
        if screenshot:
            self.draw()
            pygame.image.save(self.canvas, screenshot)
        if not IS_WEB:
            pygame.quit()

    # -- atmospheric background -------------------------------------------
    def _draw_vignette(self) -> None:
        pygame = self.pygame
        # Subtle gothic stone floor-plan backdrop
        for x in range(0, LOGICAL_SIZE[0], 128):
            for y in range(0, LOGICAL_SIZE[1], 128):
                if (x // 128 + y // 128) % 2:
                    pygame.draw.rect(self.canvas, (20, 15, 29), (x + 12, y + 12, 104, 104), 1)
        pygame.draw.rect(self.canvas, (9, 7, 15), (0, 0, *LOGICAL_SIZE), 14)

    # -- title ------------------------------------------------------------
    def _draw_title(self, mouse: tuple[int, int]) -> None:
        pygame = self.pygame
        self._last_buttons = {}
        self._draw_vignette()
        cx = LOGICAL_SIZE[0] // 2

        # Twinkling night stars
        for sx, sy, phase, r in self._title_stars:
            tw = max(0.15, min(1.0, 0.58 + 0.42 * math.sin(self._t * 2.1 + phase)))
            col = (int(150 * tw), int(140 * tw), int(195 * tw))
            pygame.draw.circle(self.canvas, col, (sx, sy), r)

        # Ambient warm lantern halo behind logo
        halo = pygame.transform.scale(self._glow, (520, 260))
        self.canvas.blit(halo, halo.get_rect(center=(cx, 125)), special_flags=pygame.BLEND_RGB_ADD)

        theme.text(
            self.canvas,
            strings.TITLE,
            92,
            theme.GOLD,
            (cx, 106),
            anchor="center",
            bold=True,
            shadow=True,
        )
        theme.text(self.canvas, strings.TAGLINE, 22, theme.INK, (cx, 168), anchor="center")

        # Interactive animated manor preview centerpiece (3x3 rotating wing + Caretaker!)
        preview = pygame.Rect(cx - 210, 206, 420, 198)
        theme.panel(self.canvas, preview, color=(19, 15, 30), border=theme.GOLD_SOFT, radius=12)
        # Left half: Foyer with Caretaker & flickering lantern
        for gx in range(2):
            for gy in range(2):
                tr = pygame.Rect(preview.x + 26 + gx * 82, preview.y + 18 + gy * 82, 80, 80)
                fx.draw_stone_tile(
                    self.canvas,
                    tr,
                    (gx, 1 - gy),
                    visited=(gx, gy) == (0, 1),
                    is_entrance=(gx, gy) == (0, 1),
                )
        spot = (preview.x + 26 + 40, preview.y + 18 + 82 + 40)
        mini_glow = pygame.transform.scale(self._glow, (180, 180))
        self.canvas.blit(
            mini_glow, mini_glow.get_rect(center=spot), special_flags=pygame.BLEND_RGB_ADD
        )
        fx.draw_caretaker(self.canvas, spot, "E", self._t)

        # Right half: gently oscillating rotating wing preview with marks
        wing_center = (preview.x + 312, preview.centery)
        w_surf = pygame.Surface((128, 128), pygame.SRCALPHA)
        pygame.draw.rect(w_surf, (*theme.FLOOR_VISITED, 235), (0, 0, 128, 128), border_radius=8)
        pygame.draw.rect(w_surf, theme.GOLD, (0, 0, 128, 128), 2, border_radius=8)
        pygame.draw.line(w_surf, theme.WALL_LIGHT, (64, 4), (64, 124), 1)
        pygame.draw.line(w_surf, theme.WALL_LIGHT, (4, 64), (124, 64), 1)
        theme.mark(w_surf, pygame.Rect(0, 0, 64, 64), "safe")
        theme.mark(w_surf, pygame.Rect(64, 0, 64, 64), "pit")
        theme.mark(w_surf, pygame.Rect(0, 64, 64, 64), "ghost")
        fx.draw_heirloom(w_surf, pygame.Rect(64, 64, 64, 64), self._t)
        ang = math.sin(self._t * 0.9) * 18.0
        rot = pygame.transform.rotate(w_surf, ang)
        self.canvas.blit(rot, rot.get_rect(center=wing_center))
        theme.draw_rotation_arrow(
            self.canvas, (preview.right - 26, preview.y + 26), 14, "cw", theme.GOLD, 2
        )

        # 4 Primary Interactive Action Cards
        cards = [
            ("title_play", strings.TITLE_BTN_PLAY, strings.TITLE_BTN_PLAY_SUB, theme.GOLD, True),
            ("title_auto", strings.TITLE_BTN_AUTO, strings.TITLE_BTN_AUTO_SUB, theme.CYAN, True),
            ("title_duel", strings.TITLE_BTN_DUEL, strings.TITLE_BTN_DUEL_SUB, theme.TEAL, False),
            (
                "title_tutorial",
                strings.TITLE_BTN_TUTORIAL,
                strings.TITLE_BTN_TUTORIAL_SUB,
                theme.VIOLET,
                False,
            ),
        ]
        cw, gap = 264, 18
        x0 = cx - (4 * cw + 3 * gap) // 2
        for i, (key_name, lbl, sub, accent, sel) in enumerate(cards):
            rect = pygame.Rect(x0 + i * (cw + gap), 438, cw, 84)
            theme.button(
                self.canvas,
                rect,
                lbl,
                sublabel=sub,
                selected=sel,
                hover=rect.collidepoint(mouse),
                accent=accent,
                size=21,
            )
            self._last_buttons[key_name] = rect

        # Secondary utility bar
        utils = [
            ("title_watch", strings.TITLE_BTN_WATCH, theme.GOLD),
            ("title_simlab", strings.TITLE_BTN_SIMLAB, theme.TEAL),
            ("title_guide", "FIELD GUIDE [H]", theme.INK),
            ("title_settings", strings.TITLE_BTN_SETTINGS, theme.MUTED),
        ]
        uw, ugap = 220, 16
        ux0 = cx - (len(utils) * uw + (len(utils) - 1) * ugap) // 2
        for i, (key_name, lbl, accent) in enumerate(utils):
            rect = pygame.Rect(ux0 + i * (uw + ugap), 544, uw, 44)
            theme.button(
                self.canvas,
                rect,
                lbl,
                hover=rect.collidepoint(mouse),
                accent=accent,
                size=16,
            )
            self._last_buttons[key_name] = rect

        theme.text(self.canvas, strings.TITLE_HINT, 18, theme.MUTED, (cx, 622), anchor="center")
        theme.text(self.canvas, strings.TITLE_BUILD, 15, theme.DIM, (cx, 682), anchor="center")

    # -- mode select ------------------------------------------------------
    def _draw_modes(self, mouse: tuple[int, int]) -> None:
        pygame = self.pygame
        self._last_buttons = {}
        self._draw_vignette()

        theme.text(self.canvas, strings.MODE_TITLE, 42, theme.GOLD, (74, 30), bold=True)
        theme.text(self.canvas, strings.MODE_HINT, 16, theme.MUTED, (76, 82))

        # Top-right quick utility buttons
        top_btns = [
            ("tutorial", "TUTORIAL [T]", theme.TEAL),
            ("guide", "HOW TO PLAY [H]", theme.GOLD),
            ("simlab", "SIM LAB [F2]", theme.CYAN),
            ("settings", "SETTINGS [O]", theme.MUTED),
            ("back", "BACK [Esc]", theme.MUTED),
        ]
        rx = 1204
        for key_name, lbl, col in reversed(top_btns):
            w = max(108, theme.font(15, bold=True).size(lbl)[0] + 24)
            rect = pygame.Rect(rx - w, 34, w, 36)
            theme.button(
                self.canvas, rect, lbl, hover=rect.collidepoint(mouse), accent=col, size=15
            )
            self._last_buttons[key_name] = rect
            rx -= w + 10

        # 3 Difficulty cards
        for i, rect in enumerate(self._mode_rects()):
            name = self.mode_names[i]
            selected = i == self.mode_index
            hover = rect.collidepoint(mouse)
            theme.button(self.canvas, rect, "", selected=selected, hover=hover, accent=theme.GOLD)
            theme.badge(
                self.canvas,
                f"DIFFICULTY {i + 1}",
                (rect.centerx, rect.y + 22),
                color=theme.GOLD if selected else theme.MUTED,
                anchor="center",
                size=13,
            )
            theme.text(
                self.canvas,
                name.upper(),
                34,
                theme.GOLD if selected else theme.INK,
                (rect.centerx, rect.y + 62),
                anchor="center",
                bold=True,
            )
            mode = MODES[name]
            shift_txt = (
                "No shifts" if mode.shift_every is None else f"Shift every {mode.shift_every}"
            )
            stats_line = f"{mode.size}x{mode.size} · {mode.pits} pits · {mode.oil} oil"
            theme.text(
                self.canvas,
                stats_line,
                19,
                theme.INK_BRIGHT if selected else theme.INK,
                (rect.centerx, rect.y + 108),
                anchor="center",
            )
            theme.badge(
                self.canvas,
                shift_txt.upper(),
                (rect.centerx, rect.y + 144),
                color=theme.TEAL if mode.shift_every is None else theme.ORANGE,
                anchor="center",
                size=14,
            )
            blurb = strings.MODE_BLURB[name].split("\n")[-1]
            for j, line in enumerate(theme.wrap(blurb, 16, rect.width - 34)):
                theme.text(
                    self.canvas,
                    line,
                    16,
                    theme.MUTED,
                    (rect.centerx, rect.y + 178 + j * 21),
                    anchor="center",
                )

        # Seed input bar + Demo preset chips
        seed_row = pygame.Rect(74, 396, 1130, 70)
        theme.panel(self.canvas, seed_row, color=theme.BG_PANEL, radius=10)
        theme.text(
            self.canvas, "MAP SEED", 16, theme.GOLD, (seed_row.x + 18, seed_row.y + 10), bold=True
        )
        seed_box = pygame.Rect(seed_row.x + 18, seed_row.y + 32, 240, 28)
        pygame.draw.rect(
            self.canvas,
            theme.BG_PANEL_HIGHLIGHT if self.seed_editing else theme.BG_DEEP,
            seed_box,
            border_radius=6,
        )
        pygame.draw.rect(
            self.canvas,
            theme.CYAN if self.seed_editing else theme.WALL_LIGHT,
            seed_box,
            2,
            border_radius=6,
        )
        cursor_ch = "_" if (self.seed_editing and int(self._t * 2.5) % 2 == 0) else ""
        theme.text(
            self.canvas,
            self.seed + cursor_ch,
            18,
            theme.INK_BRIGHT,
            (seed_box.x + 10, seed_box.centery),
            anchor="midleft",
            mono=True,
            bold=True,
        )
        self._last_buttons["seed_box"] = seed_box

        rand_btn = pygame.Rect(seed_box.right + 12, seed_row.y + 26, 140, 34)
        theme.button(
            self.canvas, rand_btn, "RANDOM [N]", hover=rand_btn.collidepoint(mouse), size=15
        )
        self._last_buttons["seed_rand"] = rand_btn

        theme.text(
            self.canvas,
            "FEATURED DEMO SEEDS:",
            14,
            theme.MUTED,
            (rand_btn.right + 28, seed_row.y + 10),
        )
        px = rand_btn.right + 28
        for preset in DEMO_SEEDS:
            pr = pygame.Rect(px, seed_row.y + 30, 138, 30)
            theme.button(
                self.canvas,
                pr,
                preset,
                selected=self.seed == preset,
                hover=pr.collidepoint(mouse),
                accent=theme.GOLD,
                size=14,
            )
            self._last_buttons[f"preset_{preset}"] = pr
            px += 148

        # Agent selector bar
        agent_rect = self._agent_rect()
        cur_agent = self.agent_names[self.agent_index]
        agent_desc = strings.AGENT_LABELS.get(cur_agent, cur_agent.upper())
        theme.button(
            self.canvas,
            agent_rect,
            f"AUTONOMOUS AI AGENT [A]:   {agent_desc}   (click to switch)",
            selected=True,
            hover=agent_rect.collidepoint(mouse),
            accent=theme.CYAN,
            size=18,
        )
        self._last_buttons["agent"] = agent_rect
        theme.text(
            self.canvas,
            strings.MODE_AGENT_HINT,
            15,
            theme.MUTED,
            (agent_rect.centerx, agent_rect.bottom + 14),
            anchor="center",
        )

        # 4 Launch action buttons
        launch_specs = [
            ("begin", strings.MODE_BEGIN, "You explore manually", theme.GOLD, True),
            ("live_ai", strings.MODE_LIVE_AI, "Real AI plays live!", theme.CYAN, True),
            ("duel", strings.MODE_DUEL, "You vs Caretaker B3", theme.TEAL, False),
            ("watch", strings.MODE_WATCH, "Proof-tree replay", theme.VIOLET, False),
        ]
        bw, bgap = 270, 16
        bx0 = 74
        for i, (key_name, lbl, sub, col, sel) in enumerate(launch_specs):
            r = pygame.Rect(bx0 + i * (bw + bgap), 590, bw, 76)
            theme.button(
                self.canvas,
                r,
                lbl,
                sublabel=sub,
                selected=sel,
                hover=r.collidepoint(mouse),
                accent=col,
                size=19,
            )
            self._last_buttons[key_name] = r

    # -- play -------------------------------------------------------------
    def _draw_play(self, mouse: tuple[int, int]) -> None:
        assert self.game is not None
        self._last_buttons = {}
        self._log_hits = []
        self._proof_hits = []
        self._draw_vignette()
        self._draw_percept_edge_glow()
        self._draw_play_top_strip()
        self._draw_board()
        self._draw_hud(mouse)
        self._draw_toolbar(mouse)
        self._draw_senses()
        self._draw_sidebar_bottom(mouse)
        if self.charm_aim:
            self._draw_charm_aim()
        if self.shift_anim is not None:
            self._draw_shift_anim(self.shift_anim)
            theme.badge(
                self.canvas,
                "THE MANOR SHIFTS — PRESS ANY KEY TO SKIP",
                (self._board_rect().centerx, 22),
                color=theme.GOLD,
                anchor="midtop",
                size=17,
            )
        self.fx.draw(self.canvas)
        self._draw_hover_tooltip(mouse)
        if self._proof is not None or self._proof_msg:
            self._draw_live_proof(mouse)
        if self.paused:
            self._draw_pause(mouse)

    def _draw_percept_edge_glow(self) -> None:
        pygame = self.pygame
        edge_color = None
        if self.percepts.chill:
            edge_color = theme.GREEN
        elif self.percepts.breeze:
            edge_color = theme.CYAN
        elif self.percepts.glimmer and self.game and not self.game.state.has_treasure:
            edge_color = theme.GOLD
        if edge_color is None:
            return
        pulse = int(28 + 16 * math.sin(self._t * 3.5))
        border = pygame.Surface(LOGICAL_SIZE, pygame.SRCALPHA)
        pygame.draw.rect(border, (*edge_color, pulse), (0, 0, *LOGICAL_SIZE), 16)
        self.canvas.blit(border, (0, 0))

    def _coach_message(self) -> tuple[str, tuple[int, int, int]]:
        assert self.game is not None
        st = self.game.state
        if self.auto_play and self.live_ai is not None:
            tag = f"LIVE AI ({self.live_ai_agent.upper()})"
            if self.auto_paused:
                tag += " [PAUSED]"
            return (f"{tag}: {self.live_ai.thought}", theme.CYAN)
        if self.active_hint is not None:
            return (f"AI HINT: {self.active_hint.summary} ({self.active_hint.detail})", theme.TEAL)
        if st.has_treasure and st.agent == st.entrance:
            return (strings.COACH_AT_EXIT, theme.GOLD)
        if st.has_treasure:
            return (strings.COACH_CARRYING, theme.GOLD)
        if st.oil <= max(2, st.start_oil // 4):
            return (strings.COACH_OIL_LOW.format(oil=st.oil), theme.RED)
        if self.percepts.rumble is not None:
            r = self.percepts.rumble
            return (
                strings.COACH_RUMBLE.format(
                    wing=WING_NAMES.get(r.wing, str(r.wing)),
                    dir=r.direction.upper(),
                    n=r.in_actions,
                ),
                theme.ORANGE,
            )
        if self.percepts.glimmer:
            return (strings.COACH_GLIMMER, theme.GOLD)
        if self.percepts.chill:
            return (strings.COACH_CHILL, theme.GREEN)
        if self.percepts.breeze:
            return (strings.COACH_BREEZE, theme.CYAN)
        return (strings.COACH_START, theme.TEAL)

    def _draw_play_top_strip(self) -> None:
        assert self.game is not None
        bar = self.pygame.Rect(48, 34, 576, 52)
        if not self.auto_play and not self.settings.show_hints and self.active_hint is None:
            # Show clean compact header if user turned off hints
            title = f"{self.game.mode.name.upper()} · {self.seed}"
            theme.text(self.canvas, title, 22, theme.GOLD, (48, 50), bold=True)
            return
        msg, col = self._coach_message()
        theme.panel(
            self.canvas,
            bar,
            color=theme.BG_PANEL_LIGHT if self.auto_play else theme.BG_PANEL,
            border=col,
            radius=8,
        )
        # Live indicator dot
        dot_r = 6 if (not self.auto_play or int(self._t * 3) % 2 == 0) else 4
        self.pygame.draw.circle(self.canvas, col, (bar.x + 18, bar.centery), dot_r)
        lines = theme.wrap(msg, 15, bar.width - 40)
        if len(lines) == 1:
            theme.text(
                self.canvas,
                lines[0],
                15,
                theme.INK_BRIGHT,
                (bar.x + 32, bar.centery),
                anchor="midleft",
            )
        else:
            for i, line in enumerate(lines[:2]):
                theme.text(
                    self.canvas, line, 14, theme.INK_BRIGHT, (bar.x + 32, bar.y + 8 + i * 18)
                )

    def _draw_board(self, reveal: dict | None = None, dest=None, path_overlay=None) -> None:
        pygame = self.pygame
        assert self.game is not None
        board_rect = self._board_rect()
        size = self.game.info().size
        board = pygame.Surface(board_rect.size)
        board.fill(theme.FLOOR)
        pits = set(reveal.get("pits", ())) if reveal else set()
        ghost = reveal.get("ghost") if reveal else None
        treasure = reveal.get("treasure") if reveal else None
        status = self.game.shift_status() if reveal is None else None
        tele_wing = status[0] if status is not None else None

        for x in range(size):
            for y in range(size):
                cell = (x, y)
                rect = pygame.Rect(x * CELL, (size - 1 - y) * CELL, CELL, CELL)
                visited = cell in self.visited or reveal is not None
                fx.draw_stone_tile(
                    board,
                    rect,
                    cell,
                    visited=visited,
                    is_entrance=cell == self.game.state.entrance,
                    has_treasure_badge=(
                        reveal is None
                        and self.game.state.has_treasure
                        and cell == self.game.state.entrance
                    ),
                    show_coords=self.settings.show_coords,
                )
                # Subtle adjacent movement highlight for manual players
                if (
                    reveal is None
                    and not self.auto_play
                    and manhattan(self.game.state.agent, cell) == 1
                ):
                    hl = pygame.Surface(rect.size, pygame.SRCALPHA)
                    alpha = 68 if cell == self.hover else 22
                    pygame.draw.rect(
                        hl, (*theme.TEAL, alpha), hl.get_rect().inflate(-8, -8), border_radius=6
                    )
                    board.blit(hl, rect.topleft)

                # Remembered senses corner badges on visited rooms (human play aid)
                if reveal is None and cell in self.room_senses and cell != self.game.state.agent:
                    senses = self.room_senses[cell]
                    sx = rect.right - 14
                    for code, col in (("B", theme.CYAN), ("C", theme.GREEN), ("G", theme.GOLD)):
                        if code in senses:
                            pygame.draw.circle(board, (18, 14, 28), (sx, rect.y + 13), 8)
                            pygame.draw.circle(board, col, (sx, rect.y + 13), 8, 1)
                            theme.text(
                                board, code, 11, col, (sx, rect.y + 13), anchor="center", bold=True
                            )
                            sx -= 18

                if cell in pits:
                    fx.draw_pit_reveal(board, rect)
                if cell == ghost:
                    fx.draw_ghost_reveal(board, rect, self._t)
                if cell == treasure:
                    fx.draw_heirloom(board, rect, self._t)

        # Apply atmospheric Lantern Fog-of-War during live gameplay!
        if reveal is None and self.settings.fog_enabled:
            self._draw_fog(board)

        # Wing rune borders drawn AFTER fog so the manor layout stays legible
        if size == 6:
            k = 3 * CELL
            for p in range(24, board_rect.height, 48):
                pygame.draw.circle(board, (118, 96, 144), (k, p), 2)
                pygame.draw.circle(board, (118, 96, 144), (p, k), 2)
            pygame.draw.line(board, (104, 84, 128), (k, 4), (k, board_rect.height - 4), 2)
            pygame.draw.line(board, (104, 84, 128), (4, k), (board_rect.width - 4, k), 2)
            # Subtle wing corner labels
            for lbl, pos in (
                ("NW", (8, 8)),
                ("NE", (k + 8, 8)),
                ("FOYER", (8, k + 8)),
                ("SE", (k + 8, k + 8)),
            ):
                theme.text(board, lbl, 12, (124, 108, 148), pos, bold=True)

        # Telegraphed rotating wing pulsing aura + CW/CCW vector arrow!
        if tele_wing is not None and size == 6:
            cells = wing_cells(tele_wing, 6)
            if cells:
                wx = min(c[0] for c in cells) * CELL
                wy = min(6 - 1 - c[1] for c in cells) * CELL
                wrect = pygame.Rect(wx, wy, 3 * CELL, 3 * CELL)
                pulse = int(130 + 95 * math.sin(self._t * 6.0))
                _dashed_rect(board, (*theme.ORANGE, pulse), wrect.inflate(-6, -6), width=3, dash=10)
                theme.draw_rotation_arrow(
                    board,
                    (wrect.right - 26, wrect.y + 26),
                    14,
                    status[1],
                    theme.ORANGE,
                    3,
                )

        # AI Belief Overlay (Live AI mode or optional player toggle [B])
        if reveal is None and self.belief_overlay:
            self._draw_live_belief_overlay(board)

        # Planned AI route stepping stones (Live AI or Active Hint)
        if reveal is None:
            self._draw_route_preview(board)

        # Path overlay on Result / Duel Result boards
        if path_overlay:
            self._draw_path_trail(board, path_overlay)

        # Player marks
        if reveal is None:
            for cell, mark in self.marks.items():
                if in_bounds(cell, size):
                    self._draw_mark_on(board, self._local_rect(cell), mark)

        # Hover outline
        if reveal is None and self.hover is not None and in_bounds(self.hover, size):
            hrect = self._local_rect(self.hover)
            pygame.draw.rect(board, theme.GOLD, hrect.inflate(-4, -4), 2, border_radius=5)

        self._draw_player(board, revealed=reveal is not None)
        pygame.draw.rect(board, theme.WALL_LIGHT, board.get_rect(), 2)

        target = pygame.Rect(dest) if dest is not None else board_rect
        if target.size != board_rect.size:
            board = pygame.transform.smoothscale(board, target.size)
        ox, oy = (
            self.fx.shake_offset(reduce_motion=self.settings.reduce_motion)
            if reveal is None
            else (0, 0)
        )
        self.canvas.blit(board, (target.x + ox, target.y + oy))

    def _draw_live_belief_overlay(self, board) -> None:
        pygame = self.pygame
        ctrl = self.live_ai or self._hint_ctrl
        if ctrl is None or not ctrl.beliefs:
            return
        layer = pygame.Surface(board.get_size(), pygame.SRCALPHA)
        for cell, belief in ctrl.beliefs.items():
            rect = self._local_rect(cell)
            if belief.label in ("safe", "pit", "ghost"):
                theme.mark(layer, rect, belief.label, 215)
            elif belief.risk > 0.01:
                col = (
                    theme.TEAL
                    if belief.risk < 0.1
                    else theme.GOLD
                    if belief.risk < 0.3
                    else theme.ORANGE
                    if belief.risk < 0.6
                    else theme.RED
                )
                tint = pygame.Surface(rect.size, pygame.SRCALPHA)
                tint.fill((*col, 52))
                layer.blit(tint, rect.topleft)
                theme.mark(layer, rect, "?", 115)
                theme.text(
                    layer,
                    f"{100 * belief.risk:.0f}%",
                    14,
                    (*col, 225),
                    (rect.centerx, rect.bottom - 8),
                    anchor="midbottom",
                    bold=True,
                )
            if belief.stale:
                _dashed_rect(layer, (*theme.GOLD, 210), rect.inflate(-10, -10), width=2, dash=6)
        board.blit(layer, (0, 0))

    def _draw_route_preview(self, board) -> None:
        pygame = self.pygame
        route: tuple[Cell, ...] = ()
        color = theme.CYAN
        if self.auto_play and self.live_ai is not None:
            route = self.live_ai.route
        elif self.active_hint is not None and self.active_hint.target_cell is not None:
            assert self.game is not None
            route = (self.game.state.agent, self.active_hint.target_cell)
            color = theme.TEAL
        if len(route) < 2:
            return
        pts = [self._local_rect(c).center for c in route]
        layer = pygame.Surface(board.get_size(), pygame.SRCALPHA)
        pygame.draw.lines(layer, (*color, 130), False, pts, 3)
        for p in pts[1:]:
            pygame.draw.circle(layer, (*color, 190), p, 6)
        # Pulse target ring on final destination
        end_rect = self._local_rect(route[-1])
        pulse = int(120 + 90 * math.sin(self._t * 6.0))
        pygame.draw.rect(layer, (*color, pulse), end_rect.inflate(-12, -12), 3, border_radius=8)
        board.blit(layer, (0, 0))

    def _draw_path_trail(
        self, board, trails: list[tuple[tuple[Cell, ...], tuple[int, int, int]]]
    ) -> None:
        pygame = self.pygame
        layer = pygame.Surface(board.get_size(), pygame.SRCALPHA)
        for idx, (cells, col) in enumerate(trails):
            if len(cells) < 2:
                continue
            off = -4 if idx == 0 and len(trails) > 1 else (4 if idx == 1 else 0)
            pts = [
                (self._local_rect(c).centerx + off, self._local_rect(c).centery + off)
                for c in cells
            ]
            pygame.draw.lines(layer, (*col, 210), False, pts, 4)
            pygame.draw.circle(layer, (*col, 240), pts[-1], 8, 2)
        board.blit(layer, (0, 0))

    def _local_rect(self, cell: Cell) -> pygame.Rect:
        assert self.game is not None
        size = self.game.info().size
        return self.pygame.Rect(cell[0] * CELL, (size - 1 - cell[1]) * CELL, CELL, CELL)

    def _player_local_center(self) -> tuple[int, int]:
        assert self.game is not None
        dst = self._local_rect(self.game.state.agent).center
        if self._move_t >= 1.0:
            return dst
        src = self._local_rect(self._move_from).center
        t = _smooth(self._move_t)
        return (int(src[0] + (dst[0] - src[0]) * t), int(src[1] + (dst[1] - src[1]) * t))

    def _draw_fog(self, board) -> None:
        pygame = self.pygame
        assert self.game is not None
        size = self.game.info().size
        st = self.game.state
        player = st.agent
        oil_ratio = st.oil / max(1, st.start_oil)
        flicker = 0.06 * math.sin(self._t * 7.3) + 0.04 * math.sin(self._t * 13.7)
        reach = (2.15 if oil_ratio <= 0.25 else 2.85) + flicker
        mask = pygame.Surface(board.get_size(), pygame.SRCALPHA)
        for x in range(size):
            for y in range(size):
                cell = (x, y)
                visited = cell in self.visited
                # Keep unvisited rooms mysterious but never pitch-black in Live AI mode
                base_alpha = 88 if visited else (175 if self.auto_play else 218)
                distance = manhattan(player, cell)
                light = max(0.0, 1.0 - distance / reach)
                alpha = max(0, int(base_alpha - 240 * light))
                rect = pygame.Rect(x * CELL, (size - 1 - y) * CELL, CELL, CELL)
                pygame.draw.rect(mask, (*theme.FOG, alpha), rect)
        board.blit(mask, (0, 0))
        glow_px = int((280 if oil_ratio <= 0.25 else 360) * (1.0 + flicker * 0.6))
        glow = pygame.transform.scale(self._glow, (glow_px, glow_px))
        center = self._player_local_center()
        board.blit(glow, glow.get_rect(center=center), special_flags=pygame.BLEND_RGB_ADD)

    def _draw_player(self, board, *, revealed: bool = False) -> None:
        assert self.game is not None
        center = (
            self._local_rect(self.game.state.agent).center
            if revealed
            else self._player_local_center()
        )
        fx.draw_caretaker(
            board,
            center,
            self.facing,
            self._t,
            carrying_treasure=self.game.state.has_treasure,
            ai_mode=self.auto_play,
        )

    def _draw_mark_on(self, surface, rect, mark: str) -> None:
        theme.mark(surface, rect, mark)

    def _draw_charm_aim(self) -> None:
        pygame = self.pygame
        assert self.game is not None
        center = self._cell_rect(self.game.state.agent).center
        for dx, dy in DIRS.values():
            step_px = 24
            for n in range(1, 9, 2):
                start = (center[0] + dx * step_px * n, center[1] - dy * step_px * n)
                end = (center[0] + dx * step_px * (n + 1), center[1] - dy * step_px * (n + 1))
                pygame.draw.line(self.canvas, theme.CYAN, start, end, 3)
        theme.badge(
            self.canvas,
            "AIM CHARM: PRESS ARROW / WASD OR CLICK A DIRECTION (C CANCELS)",
            (self._board_rect().centerx, self._board_rect().bottom + 10),
            color=theme.CYAN,
            anchor="midtop",
            size=15,
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
        surface.fill((*theme.FLOOR_VISITED, 232))
        for i in (1, 2):
            pygame.draw.line(surface, (186, 148, 86, 145), (i * CELL, 0), (i * CELL, 3 * CELL), 2)
            pygame.draw.line(surface, (186, 148, 86, 145), (0, i * CELL), (3 * CELL, i * CELL), 2)
        pygame.draw.rect(surface, (*theme.GOLD, 210), surface.get_rect(), 3)
        for cell, mark in anim.marks.items():
            local = pygame.Rect(
                (cell[0] - origin_x // CELL) * CELL,
                (6 - 1 - cell[1] - origin_y // CELL) * CELL,
                CELL,
                CELL,
            )
            self._draw_mark_on(surface, local, mark)
        for dx, dy in anim.dust:
            pygame.draw.circle(surface, (236, 214, 176), (dx, dy), 2)
        progress = _smooth(anim.elapsed / max(0.01, anim.duration))
        angle = (90 if anim.direction == "ccw" else -90) * progress
        rotated = pygame.transform.rotate(surface, angle)
        board = self._board_rect()
        center = (board.x + origin_x + 1.5 * CELL, board.y + origin_y + 1.5 * CELL)
        self.canvas.blit(rotated, rotated.get_rect(center=center))
        wing_rect = pygame.Rect(board.x + origin_x, board.y + origin_y, 3 * CELL, 3 * CELL)
        pygame.draw.rect(self.canvas, theme.GOLD, wing_rect, 3, border_radius=5)

    # -- HUD / sidebar ----------------------------------------------------
    def _draw_hud(self, mouse: tuple[int, int]) -> None:
        pygame = self.pygame
        assert self.game is not None
        rect = pygame.Rect(648, 34, 600, 182)
        theme.panel(
            self.canvas,
            rect,
            accent_top=theme.CYAN if self.auto_play else theme.GOLD,
        )
        st = self.game.state

        # Top row: Oil gauge + Score
        theme.text(
            self.canvas, strings.HUD_OIL, 16, theme.MUTED, (rect.x + 18, rect.y + 14), bold=True
        )
        bar = pygame.Rect(rect.x + 132, rect.y + 14, 198, 18)
        pygame.draw.rect(self.canvas, theme.BG_DEEP, bar, border_radius=9)
        ratio = st.oil / max(1, st.start_oil)
        color = theme.GREEN if ratio > 0.5 else theme.GOLD if ratio > 0.25 else theme.RED
        pygame.draw.rect(
            self.canvas,
            color,
            (bar.x, bar.y, max(6, int(bar.width * max(0.0, ratio))), bar.height),
            border_radius=9,
        )
        theme.text(
            self.canvas,
            f"{st.oil}/{st.start_oil}",
            17,
            theme.INK_BRIGHT if ratio <= 0.25 else theme.INK,
            (bar.right + 10, bar.y - 1),
            bold=ratio <= 0.25,
        )
        theme.text(
            self.canvas,
            f"{strings.HUD_SCORE}: {self.game.score()}",
            24,
            theme.GOLD,
            (rect.right - 18, rect.y + 10),
            anchor="topright",
            bold=True,
        )

        # Heirloom badge & Duel/Mode badge
        held = strings.HUD_HEIRLOOM_HELD if st.has_treasure else strings.HUD_HEIRLOOM_LOST
        theme.badge(
            self.canvas,
            f"HEIRLOOM: {held}",
            (rect.x + 18, rect.y + 44),
            color=theme.GOLD if st.has_treasure else theme.MUTED,
            size=14,
        )

        # Clickable Charm & Leave Manor buttons right in HUD!
        charm_btn = pygame.Rect(rect.x + 18, rect.y + 78, 152, 36)
        charm_lbl = (
            "AIMING..."
            if self.charm_aim
            else (strings.HUD_CHARM_READY if st.charm_available else "CHARM SPENT")
        )
        theme.button(
            self.canvas,
            charm_btn,
            charm_lbl,
            selected=self.charm_aim,
            disabled=(not st.charm_available) or self.auto_play,
            hover=charm_btn.collidepoint(mouse),
            accent=theme.VIOLET,
            size=15,
        )
        self._last_buttons["charm"] = charm_btn

        leave_btn = pygame.Rect(rect.x + 180, rect.y + 78, 178, 36)
        at_exit = st.agent == st.entrance
        theme.button(
            self.canvas,
            leave_btn,
            strings.PLAY_LEAVE_BTN,
            selected=at_exit and st.has_treasure,
            disabled=(not at_exit) or self.auto_play,
            hover=leave_btn.collidepoint(mouse),
            accent=theme.GOLD if st.has_treasure else theme.TEAL,
            size=15,
        )
        self._last_buttons["leave"] = leave_btn

        # Info strip: Seed, Room, Wing, Moves
        wname = WING_NAMES.get(wing_of(st.agent, st.size), "FOYER")
        mode_tag = (
            f"DUEL ({self.duel_phase.upper()})"
            if self.duel_active
            else (
                f"LIVE {self.live_ai_agent.upper()}"
                if self.auto_play
                else self.game.mode.name.upper()
            )
        )
        theme.text(
            self.canvas,
            f"{mode_tag} · SEED {self.seed}",
            15,
            theme.CYAN if self.auto_play else theme.MUTED,
            (rect.x + 18, rect.y + 126),
            bold=self.auto_play,
        )
        theme.text(
            self.canvas,
            f"Room ({st.agent[0]}, {st.agent[1]}) · Wing {wname} · Actions {st.actions_taken}",
            15,
            theme.MUTED,
            (rect.x + 18, rect.y + 150),
        )

        # Shift Clock Dial on right side of HUD
        clock_x = rect.right - 92
        clock_y = rect.y + 102
        status = self.game.shift_status()
        dial_edge = theme.ORANGE if status is not None else theme.WALL_LIGHT
        pygame.draw.circle(self.canvas, theme.BG_DEEP, (clock_x, clock_y), 48)
        pygame.draw.circle(self.canvas, dial_edge, (clock_x, clock_y), 48, 2)

        # Progress arc showing moves until next shift
        k = self.game.mode.shift_every
        if k:
            rem = k - (st.action_count % k) if st.action_count % k else k
            frac = 1.0 - (rem / k)
            if frac > 0.02:
                arc_rect = pygame.Rect(clock_x - 42, clock_y - 42, 84, 84)
                pygame.draw.arc(
                    self.canvas,
                    theme.ORANGE if status else theme.GOLD_SOFT,
                    arc_rect,
                    math.pi / 2 - math.tau * frac,
                    math.pi / 2,
                    4,
                )

        if status is None:
            theme.text(
                self.canvas,
                strings.HUD_SHIFT_STEADY,
                15,
                theme.MUTED,
                (clock_x, clock_y - 9),
                anchor="center",
                bold=True,
            )
            if k:
                rem = k - (st.action_count % k)
                theme.text(
                    self.canvas,
                    f"next in {rem}",
                    14,
                    theme.GOLD_SOFT,
                    (clock_x, clock_y + 12),
                    anchor="center",
                )
            else:
                theme.text(
                    self.canvas,
                    "no shifts",
                    13,
                    theme.DIM,
                    (clock_x, clock_y + 12),
                    anchor="center",
                )
        else:
            wing, direction, left = status
            theme.text(
                self.canvas,
                WING_NAMES.get(wing, str(wing)),
                18,
                theme.GOLD,
                (clock_x, clock_y - 18),
                anchor="center",
                bold=True,
            )
            theme.text(
                self.canvas,
                direction.upper(),
                15,
                theme.ORANGE,
                (clock_x, clock_y + 2),
                anchor="center",
                bold=True,
            )
            theme.text(
                self.canvas,
                f"in {left}",
                14,
                theme.INK_BRIGHT,
                (clock_x, clock_y + 22),
                anchor="center",
            )
        theme.text(
            self.canvas,
            strings.HUD_SHIFT,
            13,
            theme.MUTED,
            (clock_x, rect.y + 156),
            anchor="midtop",
        )

    def _draw_toolbar(self, mouse: tuple[int, int]) -> None:
        pygame = self.pygame
        y = 224
        x = 648
        if self.auto_play:
            # Live AI transport controls!
            btns = [
                ("toggle_auto", strings.PLAY_TAKE_OVER, 146, theme.GOLD, False),
                (
                    "ai_pause",
                    "PLAY" if self.auto_paused else "PAUSE",
                    76,
                    theme.CYAN,
                    not self.auto_paused,
                ),
                ("ai_step", "STEP", 64, theme.INK, False),
                ("ai_speed", f"{self.auto_speed:g}x", 56, theme.GOLD, False),
                ("ai_fast", "FINISH [F]", 92, theme.TEAL, False),
                ("beliefs", "BELIEFS", 82, theme.VIOLET, self.belief_overlay),
                ("guide", "GUIDE", 64, theme.MUTED, False),
            ]
        else:
            btns = [
                ("toggle_auto", strings.PLAY_AUTO_OFF, 156, theme.CYAN, False),
                ("hint", strings.PLAY_HINT_BTN, 114, theme.TEAL, self.active_hint is not None),
                (
                    "beliefs",
                    strings.PLAY_BELIEF_ON if self.belief_overlay else strings.PLAY_BELIEF_OFF,
                    134,
                    theme.VIOLET,
                    self.belief_overlay,
                ),
                ("guide", strings.PLAY_GUIDE_BTN, 92, theme.GOLD, False),
                ("settings", "OPT [O]", 80, theme.MUTED, False),
            ]
        cur_x = x
        for key_name, lbl, w, col, sel in btns:
            r = pygame.Rect(cur_x, y, w, 34)
            theme.button(
                self.canvas, r, lbl, selected=sel, hover=r.collidepoint(mouse), accent=col, size=14
            )
            self._last_buttons[key_name] = r
            cur_x += w + 4

    def _draw_senses(self) -> None:
        pygame = self.pygame
        rect = pygame.Rect(648, 266, 600, 146)
        theme.panel(self.canvas, rect)
        theme.text(
            self.canvas, strings.SENSES_TITLE, 18, theme.GOLD, (rect.x + 18, rect.y + 10), bold=True
        )
        p = self.percepts
        lines: list[tuple[str, tuple[int, int, int]]] = []
        if p.breeze:
            lines.append((strings.SENSE_BREEZE, theme.CYAN))
        if p.chill:
            lines.append((strings.SENSE_CHILL, theme.GREEN))
        if p.glimmer:
            lines.append((strings.SENSE_GLIMMER, theme.GOLD))
        if p.rumble is not None:
            wname = WING_NAMES.get(p.rumble.wing, str(p.rumble.wing))
            lines.append(
                (
                    strings.SENSE_RUMBLE.format(
                        wing=wname, dir=p.rumble.direction.upper(), n=p.rumble.in_actions
                    ),
                    theme.ORANGE,
                )
            )
        if p.scream:
            lines.append((strings.SENSE_SCREAM, theme.VIOLET))
        if p.bump:
            lines.append((strings.SENSE_BUMP, theme.MUTED))
        if not lines:
            lines.append((strings.SENSE_QUIET, theme.TEAL))
        for i, (line, color) in enumerate(lines[:4]):
            y = rect.y + 40 + i * 24
            pygame.draw.circle(self.canvas, color, (rect.x + 26, y + 9), 5)
            theme.text(self.canvas, line, 17, color if i == 0 else theme.INK, (rect.x + 40, y))

    def _draw_sidebar_bottom(self, mouse: tuple[int, int]) -> None:
        pygame = self.pygame
        tab_labels = ("MARKS & CONTROLS", "LIVE AI LOG", "KB RULES (24)")
        tw = 196
        for i, lbl in enumerate(tab_labels):
            tr = pygame.Rect(648 + i * (tw + 6), 420, tw, 32)
            theme.button(
                self.canvas,
                tr,
                lbl,
                selected=i == self.sidebar_tab,
                hover=tr.collidepoint(mouse),
                accent=theme.CYAN if i > 0 else theme.GOLD,
                size=14,
            )
            self._last_buttons[f"tab_{i}"] = tr

        panel = pygame.Rect(648, 456, 600, 234)
        theme.panel(self.canvas, panel)
        if self.sidebar_tab == 0:
            self._draw_legend_tab(panel, mouse)
        elif self.sidebar_tab == 1:
            self._draw_live_log_tab(panel, mouse)
        else:
            self._draw_live_kb_tab(panel)

    def _draw_legend_tab(self, rect, mouse: tuple[int, int]) -> None:
        pygame = self.pygame
        items = (
            ("safe", "SAFE [4]", "safe"),
            ("pit", "PIT [2]", "pit"),
            ("ghost", "GHOST [3]", "ghost"),
            ("?", "MARK ? [1]", "?"),
        )
        for i, (mk, label, key) in enumerate(items):
            box = pygame.Rect(rect.x + 14 + i * 120, rect.y + 12, 114, 44)
            theme.panel(
                self.canvas,
                box,
                color=theme.BG_PANEL_LIGHT if box.collidepoint(mouse) else theme.BG_DEEP,
                border=theme.GOLD if box.collidepoint(mouse) else theme.WALL,
                radius=6,
            )
            self._draw_mark_on(self.canvas, pygame.Rect(box.x + 4, box.y + 5, 34, 34), mk)
            theme.text(self.canvas, label, 12, theme.INK, (box.x + 41, box.y + 15), bold=True)
            self._last_buttons[f"mark_{key}"] = box

        clr = pygame.Rect(rect.right - 98, rect.y + 12, 84, 44)
        theme.button(self.canvas, clr, "CLR [0]", hover=clr.collidepoint(mouse), size=13)
        self._last_buttons["mark_clear"] = clr

        for i, line in enumerate(strings.CONTROLS):
            theme.text(self.canvas, line, 15, theme.MUTED, (rect.x + 18, rect.y + 72 + i * 27))

    def _draw_live_log_tab(self, rect, mouse: tuple[int, int]) -> None:
        pygame = self.pygame
        ctrl = self.live_ai or self._hint_ctrl
        if ctrl is None or not ctrl.log:
            theme.text(
                self.canvas,
                "Press [T] for Live Autonomous AI Play or [I] for an AI Hint to stream live rule firings here!",
                16,
                theme.MUTED,
                (rect.x + 20, rect.y + 24),
            )
            return
        theme.text(
            self.canvas,
            f"LIVE FORWARD CHAINING · {ctrl.total_firings} FIRINGS (click any line for Why?)",
            14,
            theme.CYAN,
            (rect.x + 14, rect.y + 10),
            bold=True,
        )
        view = pygame.Rect(rect.x + 14, rect.y + 32, rect.width - 28, rect.height - 42)
        entries = ctrl.log[-24:]
        laid: list[tuple[Any, int, list[str]]] = []
        cursor = 0
        for entry in entries:
            lines = theme.wrap(f"T{entry.turn + 1} {entry.text}", 14, view.width - 6)
            laid.append((entry, cursor, lines))
            cursor += 17 * len(lines) + 2
        max_scroll = max(0, cursor - view.height)
        scroll = max_scroll if self.log_scroll == 0 else min(self.log_scroll, max_scroll)
        base_y = view.y - scroll
        for entry, off, lines in laid:
            yy = base_y + off
            h = 17 * len(lines)
            if yy + h < view.y or yy > view.bottom:
                continue
            r = pygame.Rect(view.x, yy, view.width, h)
            if r.collidepoint(mouse):
                pygame.draw.rect(self.canvas, theme.BG_PANEL_LIGHT, r, border_radius=3)
            for j, line in enumerate(lines):
                col = theme.GOLD if entry.firing.rule_id == "R16" else theme.INK
                theme.text(self.canvas, line, 14, col, (view.x + 2, yy + j * 17))
            self._log_hits.append((r, entry.firing))

    def _draw_live_kb_tab(self, rect) -> None:
        pygame = self.pygame
        ctrl = self.live_ai or self._hint_ctrl
        counts = ctrl.rule_counts if ctrl is not None else {}
        max_c = max(counts.values(), default=1)
        theme.text(
            self.canvas,
            "24 IF-THEN RULES (R01-R24) · Scroll with mouse wheel",
            14,
            theme.GOLD,
            (rect.x + 14, rect.y + 10),
            bold=True,
        )
        view = pygame.Rect(rect.x + 14, rect.y + 32, rect.width - 28, rect.height - 40)
        cursor = -self.kb_scroll
        for rule in RULES:
            rr = pygame.Rect(view.x, view.y + cursor, view.width, 22)
            if rr.bottom >= view.y and rr.top <= view.bottom:
                c = counts.get(rule.id, 0)
                bar_bg = pygame.Rect(rr.right - 110, rr.y + 4, 62, 12)
                pygame.draw.rect(self.canvas, theme.BG_DEEP, bar_bg, border_radius=4)
                if c > 0:
                    fw = max(4, int(bar_bg.width * (c / max_c)))
                    pygame.draw.rect(
                        self.canvas,
                        theme.GOLD if rule.id == "R16" else theme.TEAL,
                        (bar_bg.x, bar_bg.y, fw, bar_bg.height),
                        border_radius=4,
                    )
                theme.text(self.canvas, rule.id, 14, theme.GOLD, (rr.x + 2, rr.y + 2), bold=True)
                theme.text(
                    self.canvas,
                    rule.description[:52],
                    13,
                    theme.INK if c > 0 else theme.DIM,
                    (rr.x + 42, rr.y + 3),
                )
                theme.text(
                    self.canvas,
                    f"{c}x",
                    13,
                    theme.INK if c > 0 else theme.DIM,
                    (rr.right - 4, rr.y + 3),
                    anchor="topright",
                )
            cursor += 22
        max_sc = max(0, len(RULES) * 22 - view.height)
        self.kb_scroll = max(0, min(self.kb_scroll, max_sc))

    def _draw_hover_tooltip(self, mouse: tuple[int, int]) -> None:
        if self.hover is None or self.game is None or self.paused or self._proof is not None:
            return
        cell = self.hover
        wname = WING_NAMES.get(wing_of(cell, self.game.info().size), "FOYER")
        lines: list[tuple[str, tuple[int, int, int]]] = [
            (
                f"Wing: {wname}  ·  {'Visited' if cell in self.visited else 'Unvisited'}",
                theme.MUTED,
            ),
        ]
        if cell in self.room_senses:
            tags = ", ".join(
                {"B": "Breeze", "C": "Chill", "G": "Glimmer"}[k]
                for k in sorted(self.room_senses[cell])
            )
            lines.append((f"Sensed here: {tags}", theme.CYAN))
        if cell in self.marks:
            lines.append((f"Your mark: {self.marks[cell].upper()}", theme.GOLD))
        ctrl = self.live_ai or self._hint_ctrl
        if self.belief_overlay and ctrl is not None and cell in ctrl.beliefs:
            b = ctrl.beliefs[cell]
            lines.append(
                (
                    f"AI Belief: {b.label.upper()} (risk {100 * b.risk:.0f}%)",
                    theme.TEAL if b.risk < 0.05 else theme.ORANGE,
                )
            )
            lines.append(("Click or press W for Why? proof", theme.MUTED))
        elif not self.auto_play and manhattan(self.game.state.agent, cell) == 1:
            lines.append(("Left-click to move · Right-click to mark", theme.TEAL))
        elif not self.auto_play:
            lines.append(("Right-click to place / cycle note mark", theme.MUTED))
        theme.draw_tooltip(self.canvas, mouse, f"Room ({cell[0]}, {cell[1]})", lines)

    def _draw_live_proof(self, mouse: tuple[int, int]) -> None:
        pygame = self.pygame
        shade = pygame.Surface(LOGICAL_SIZE, pygame.SRCALPHA)
        shade.fill((8, 6, 12, 224))
        self.canvas.blit(shade, (0, 0))
        rect = pygame.Rect(90, 76, 1100, 568)
        theme.panel(self.canvas, rect, color=theme.BG_PANEL_LIGHT, accent_top=theme.CYAN)
        theme.text(
            self.canvas,
            strings.WATCH_WHY_TITLE,
            24,
            theme.GOLD,
            (rect.x + 22, rect.y + 14),
            bold=True,
        )
        close = pygame.Rect(rect.right - 96, rect.y + 12, 76, 30)
        theme.button(self.canvas, close, "CLOSE", hover=close.collidepoint(mouse), size=15)
        self._last_buttons["proof_close"] = close
        if self._proof is None:
            theme.text(
                self.canvas,
                self._proof_msg or strings.WATCH_WHY_EMPTY,
                19,
                theme.INK,
                rect.center,
                anchor="center",
            )
            return
        view = pygame.Rect(rect.x + 22, rect.y + 56, rect.width - 44, rect.height - 74)
        rows: list[tuple[str, ProofNode, int]] = []

        def walk(node: ProofNode, depth: int) -> None:
            if depth >= 6 and node.children and node.id not in self._proof_expanded:
                rows.append(("node", node, depth))
                rows.append(("expand", node, depth))
                return
            rows.append(("node", node, depth))
            for ch in node.children:
                walk(ch, depth + 1)

        walk(self._proof, 0)
        cursor = -self._proof_scroll
        for kind, node, depth in rows:
            h = 38 if kind == "node" else 26
            rr = pygame.Rect(view.x, view.y + cursor, view.width, h)
            if rr.bottom >= view.y and rr.top <= view.bottom:
                if kind == "expand":
                    theme.button(self.canvas, rr.inflate(-6, -2), "+ expand premises", size=14)
                    self._proof_hits.append((rr, node))
                else:
                    ind = min(depth, 10) * 18
                    theme.text(
                        self.canvas,
                        node.label[:95],
                        16,
                        theme.INK_BRIGHT if depth == 0 else theme.GOLD,
                        (view.x + ind, view.y + cursor + 1),
                        bold=depth == 0,
                    )
                    theme.text(
                        self.canvas,
                        node.detail[:110],
                        13,
                        theme.MUTED,
                        (view.x + ind, view.y + cursor + 19),
                    )
                    self._proof_hits.append((rr, node))
            cursor += h

    def _draw_pause(self, mouse: tuple[int, int]) -> None:
        pygame = self.pygame
        overlay = pygame.Surface(LOGICAL_SIZE, pygame.SRCALPHA)
        overlay.fill((8, 6, 12, 214))
        self.canvas.blit(overlay, (0, 0))
        rect = pygame.Rect(420, 176, 440, 368)
        theme.panel(self.canvas, rect, color=theme.BG_PANEL_LIGHT, accent_top=theme.GOLD)
        theme.text(
            self.canvas,
            strings.PAUSED,
            52,
            theme.GOLD,
            (rect.centerx, rect.y + 44),
            anchor="center",
            bold=True,
        )
        btns = [
            ("pause_resume", "RESUME [Esc]", theme.GOLD, True),
            ("pause_guide", "HOW TO PLAY GUIDE [H]", theme.TEAL, False),
            ("pause_settings", "SETTINGS [O]", theme.CYAN, False),
            ("pause_restart", "RESTART SEED [R]", theme.INK, False),
            ("pause_menu", "MAIN MENU [M]", theme.MUTED, False),
        ]
        for i, (key_name, lbl, col, sel) in enumerate(btns):
            br = pygame.Rect(rect.x + 48, rect.y + 92 + i * 48, rect.width - 96, 40)
            theme.button(
                self.canvas,
                br,
                lbl,
                selected=sel,
                hover=br.collidepoint(mouse),
                accent=col,
                size=18,
            )
            self._last_buttons[key_name] = br
        theme.text(
            self.canvas,
            strings.PAUSE_HINT,
            14,
            theme.MUTED,
            (rect.centerx, rect.bottom - 18),
            anchor="center",
        )

    def _draw_presenter_overlay(self) -> None:
        pygame = self.pygame
        pill = pygame.Rect(16, LOGICAL_SIZE[1] - 42, 760, 32)
        bg = pygame.Surface(pill.size, pygame.SRCALPHA)
        pygame.draw.rect(bg, (14, 11, 22, 230), bg.get_rect(), border_radius=8)
        pygame.draw.rect(bg, theme.GOLD, bg.get_rect(), 1, border_radius=8)
        self.canvas.blit(bg, pill.topleft)
        mode = (
            self.game.mode.name.upper() if self.game else self.mode_names[self.mode_index].upper()
        )
        turn = self.game.state.actions_taken if self.game else 0
        oil = self.game.state.oil if self.game else 0
        last_rule = (
            self.live_ai.log[-1].firing.rule_id if (self.live_ai and self.live_ai.log) else "—"
        )
        txt = f"PRESENTER [F1] · {mode} · SEED {self.seed} · TURN {turn} · OIL {oil} · LAST RULE {last_rule}"
        theme.text(
            self.canvas,
            txt,
            15,
            theme.GOLD,
            (pill.x + 12, pill.centery),
            anchor="midleft",
            bold=True,
        )

    # -- duel halftime & result -------------------------------------------
    def _draw_duel_halftime(self, mouse: tuple[int, int]) -> None:
        pygame = self.pygame
        self._last_buttons = {}
        self._draw_vignette()
        h = self.duel_human
        assert h is not None
        card = pygame.Rect(270, 120, 740, 480)
        theme.panel(self.canvas, card, color=theme.BG_PANEL_LIGHT, accent_top=theme.GOLD)
        theme.badge(
            self.canvas,
            "DUEL PHASE 1 COMPLETE",
            (card.centerx, card.y + 34),
            color=theme.GOLD,
            anchor="center",
            size=16,
        )
        theme.text(
            self.canvas,
            strings.RESULT_OUTCOME.get(h.outcome, h.outcome.upper()),
            34,
            theme.TEAL if h.outcome == "escaped_treasure" else theme.ORANGE,
            (card.centerx, card.y + 84),
            anchor="center",
            bold=True,
        )
        for i in range(3):
            theme.draw_star(
                self.canvas, (card.centerx + (i - 1) * 58, card.y + 142), 22, filled=i < h.stars
            )
        theme.text(
            self.canvas,
            f"YOUR SCORE: {h.score}   ·   {h.actions} actions (Oracle par {h.par})   ·   {h.oil_left} oil left",
            20,
            theme.INK_BRIGHT,
            (card.centerx, card.y + 196),
            anchor="center",
            bold=True,
        )
        theme.text(
            self.canvas,
            f"Now watch the REAL Caretaker AI (B3) play the EXACT same seed ({self.seed}) autonomously!",
            18,
            theme.CYAN,
            (card.centerx, card.y + 260),
            anchor="center",
        )
        watch_btn = pygame.Rect(card.centerx - 250, card.y + 324, 240, 56)
        theme.button(
            self.canvas,
            watch_btn,
            strings.DUEL_NEXT_AI,
            selected=True,
            hover=watch_btn.collidepoint(mouse),
            accent=theme.CYAN,
            size=18,
        )
        self._last_buttons["duel_watch_ai"] = watch_btn
        fast_btn = pygame.Rect(card.centerx + 10, card.y + 324, 240, 56)
        theme.button(
            self.canvas,
            fast_btn,
            strings.DUEL_SKIP_AI,
            hover=fast_btn.collidepoint(mouse),
            accent=theme.GOLD,
            size=18,
        )
        self._last_buttons["duel_fast_ai"] = fast_btn
        back_btn = pygame.Rect(card.centerx - 110, card.y + 402, 220, 42)
        theme.button(
            self.canvas, back_btn, "CANCEL DUEL [Esc]", hover=back_btn.collidepoint(mouse), size=16
        )
        self._last_buttons["duel_menu"] = back_btn

    def _draw_duel_result(self, mouse: tuple[int, int]) -> None:
        pygame = self.pygame
        self._last_buttons = {}
        self._draw_vignette()
        h, a = self.duel_human, self.duel_ai
        assert h is not None and a is not None and self.game is not None

        if h.score > a.score:
            banner, col = strings.DUEL_WIN_HUMAN, theme.TEAL
        elif a.score > h.score:
            banner, col = strings.DUEL_WIN_AI, theme.CYAN
        else:
            banner, col = strings.DUEL_TIE, theme.GOLD

        theme.text(self.canvas, strings.DUEL_TITLE, 24, theme.MUTED, (640, 32), anchor="center")
        theme.text(self.canvas, banner, 38, col, (640, 76), anchor="center", bold=True)

        trails = []
        if self.duel_path_filter in ("both", "human"):
            trails.append((h.path, theme.GOLD))
        if self.duel_path_filter in ("both", "ai"):
            trails.append((a.path, theme.CYAN))
        self._draw_board(reveal=a.reveal, dest=pygame.Rect(48, 126, 480, 480), path_overlay=trails)

        # Path filter toggles beneath revealed board
        for i, (key_name, lbl, pcol) in enumerate(
            (
                ("both", "BOTH PATHS", theme.INK),
                ("human", "YOUR PATH", theme.GOLD),
                ("ai", "AI PATH", theme.CYAN),
            )
        ):
            r = pygame.Rect(48 + i * 164, 622, 152, 34)
            theme.button(
                self.canvas,
                r,
                lbl,
                selected=self.duel_path_filter == key_name,
                hover=r.collidepoint(mouse),
                accent=pcol,
                size=14,
            )
            self._last_buttons[f"path_{key_name}"] = r

        # Side-by-side comparison cards
        for idx, (summary, accent) in enumerate(((h, theme.GOLD), (a, theme.CYAN))):
            card = pygame.Rect(556 + idx * 344, 126, 330, 444)
            theme.panel(self.canvas, card, color=theme.BG_PANEL_LIGHT, accent_top=accent)
            theme.text(
                self.canvas,
                summary.who,
                22,
                accent,
                (card.centerx, card.y + 24),
                anchor="center",
                bold=True,
            )
            for s_i in range(3):
                theme.draw_star(
                    self.canvas,
                    (card.centerx + (s_i - 1) * 48, card.y + 72),
                    18,
                    filled=s_i < summary.stars,
                )
            theme.text(
                self.canvas,
                f"{summary.score}",
                42,
                theme.INK_BRIGHT,
                (card.centerx, card.y + 126),
                anchor="center",
                bold=True,
            )
            theme.text(
                self.canvas,
                strings.RESULT_OUTCOME.get(summary.outcome, summary.outcome),
                15,
                theme.TEAL if summary.outcome == "escaped_treasure" else theme.RED,
                (card.centerx, card.y + 168),
                anchor="center",
                bold=True,
            )
            rows = [
                ("Actions", f"{summary.actions} (par {summary.par})"),
                ("Oil Left", str(summary.oil_left)),
                ("Charms Cast", str(summary.charms)),
                ("Ghost Banished", "Yes (+200)" if summary.ghost_banished else "No"),
                ("Marks / Rules", str(summary.marks_or_rules)),
            ]
            for r_i, (k, v) in enumerate(rows):
                ry = card.y + 210 + r_i * 38
                theme.text(self.canvas, k, 16, theme.MUTED, (card.x + 20, ry))
                theme.text(
                    self.canvas,
                    v,
                    16,
                    theme.INK,
                    (card.right - 20, ry),
                    anchor="topright",
                    bold=True,
                )

        # Bottom action buttons
        btns = [
            ("duel_rematch", "REMATCH SEED [R]", theme.GOLD),
            ("duel_new", "NEW DUEL SEED [N]", theme.TEAL),
            ("duel_card", "SAVE CARD [S]", theme.CYAN),
            ("duel_menu", "MENU [M]", theme.MUTED),
        ]
        for i, (key_name, lbl, bcol) in enumerate(btns):
            r = pygame.Rect(556 + i * 172, 594, 162, 50)
            theme.button(self.canvas, r, lbl, hover=r.collidepoint(mouse), accent=bcol, size=15)
            self._last_buttons[key_name] = r
        self.fx.draw(self.canvas)

    # -- result -----------------------------------------------------------
    def _draw_result(self, mouse: tuple[int, int]) -> None:
        pygame = self.pygame
        assert self.game is not None and self.result is not None
        self._last_buttons = {}
        self._draw_vignette()

        mode_who = (
            f"AUTONOMOUS AGENT ({self.result.get('agent', 'b3').upper()})"
            if self.result.get("autonomous")
            else "MANUAL CARETAKER RUN"
        )
        theme.text(
            self.canvas,
            f"{strings.RESULT_TITLE}  ·  {mode_who}",
            26,
            theme.MUTED,
            (LOGICAL_SIZE[0] // 2, 40),
            anchor="center",
        )
        outcome = self.result["outcome"]
        color = (
            theme.GOLD
            if outcome == "escaped_treasure"
            else (theme.TEAL if outcome.startswith("escaped") else theme.RED)
        )
        theme.text(
            self.canvas,
            strings.RESULT_OUTCOME.get(outcome, outcome.upper()),
            44,
            color,
            (LOGICAL_SIZE[0] // 2, 92),
            anchor="center",
            bold=True,
            shadow=True,
        )

        trail_color = theme.CYAN if self.result.get("autonomous") else theme.GOLD
        self._draw_board(
            reveal=self.game.reveal(),
            dest=self._result_board_rect(),
            path_overlay=[(tuple(self.path), trail_color)],
        )
        theme.text(
            self.canvas,
            "Full map revealed · Path trail shown",
            15,
            theme.MUTED,
            (self._result_board_rect().centerx, self._result_board_rect().bottom + 14),
            anchor="center",
        )

        panel = self._result_panel_rect()
        theme.panel(self.canvas, panel, accent_top=color)
        stars = self.result["stars"]
        for i in range(3):
            theme.draw_star(
                self.canvas,
                (panel.centerx + (i - 1) * 64, panel.y + 44),
                23,
                filled=i < stars,
            )
        theme.text(
            self.canvas,
            f"{strings.RESULT_SCORE}: {self.result['score']}",
            38,
            theme.INK_BRIGHT,
            (panel.centerx, panel.y + 92),
            anchor="center",
            bold=True,
        )
        st = self.game.state
        par = self.result.get("par", 0)
        stats = [
            (strings.RESULT_ACTIONS, f"{st.actions_taken}  (Oracle par: {par})"),
            (strings.RESULT_OIL, f"{st.oil} / {st.start_oil}"),
            (
                strings.RESULT_CHARMS,
                f"{st.charms_cast}  ({'Ghost banished +200' if st.ghost_banished else '—'})",
            ),
            (
                "Rules fired" if self.result.get("autonomous") else "Marks placed",
                str(
                    self.result.get("rules_fired", 0)
                    if self.result.get("autonomous")
                    else len(self.marks)
                ),
            ),
            (strings.RESULT_STARS, f"{stars} / 3"),
            (
                f"{strings.RESULT_SEED} / {strings.RESULT_MODE}",
                f"{self.seed}  ·  {self.game.mode.name}",
            ),
        ]
        for i, (label, value) in enumerate(stats):
            y = panel.y + 132 + i * 31
            theme.text(self.canvas, label, 18, theme.MUTED, (panel.x + 28, y))
            theme.text(
                self.canvas,
                str(value),
                18,
                theme.INK,
                (panel.right - 28, y),
                anchor="topright",
                bold=True,
            )

        # Secondary actions inside panel directly above primary buttons
        sec_y = panel.bottom - 126
        sec_w, sec_gap = 190, 24
        sec_x0 = panel.centerx - (3 * sec_w + 2 * sec_gap) // 2
        for i, (key_name, lbl, col) in enumerate(
            (
                ("live_ai", strings.RESULT_WATCH_AI, theme.CYAN),
                ("watch", "TRACE PROOF [V]", theme.VIOLET),
                ("save_card", strings.RESULT_SAVE_CARD, theme.TEAL),
            )
        ):
            sr = pygame.Rect(sec_x0 + i * (sec_w + sec_gap), sec_y, sec_w, 40)
            theme.button(self.canvas, sr, lbl, hover=sr.collidepoint(mouse), accent=col, size=15)
            self._last_buttons[key_name] = sr

        buttons = self._result_buttons()
        labels = (strings.RESULT_REPLAY, strings.RESULT_NEW, strings.RESULT_MENU)
        for i, (rect, label) in enumerate(zip(buttons, labels)):
            theme.button(
                self.canvas,
                rect,
                label,
                selected=i == 0,
                hover=rect.collidepoint(mouse),
                size=18,
            )
            self._last_buttons[("replay", "new", "menu")[i]] = rect
        self.fx.draw(self.canvas)

    # -- utility ----------------------------------------------------------
    def _make_glow(self) -> pygame.Surface:
        pygame = self.pygame
        size = 320
        surface = pygame.Surface((size, size))
        surface.fill((0, 0, 0))
        center = (size // 2, size // 2)
        half = size / 2.0
        for radius in range(size // 2, 0, -2):
            falloff = (1.0 - radius / half) ** 2.2
            col = (
                int(105 * falloff),
                int(68 * falloff),
                int(24 * falloff),
            )
            pygame.draw.circle(surface, col, center, radius)
        return surface


def main(
    *,
    audio: bool = True,
    windowed: bool = True,
    seed: str = "HAUNT-4F2A",
    mode: str | None = None,
    agent: str = "b3",
    auto: bool = False,
    duel: bool = False,
    tutorial: bool = False,
    simlab: bool = False,
    frames: int | None = None,
    screenshot: str | None = None,
    demo: bool = False,
) -> None:
    """Real entry point used by ``python -m shifting_manor``."""
    app = App(audio=audio, windowed=windowed, seed=seed)
    if agent in app.agent_names:
        app.agent_index = app.agent_names.index(agent)
    if demo:
        app.start_demo(seed, mode or "explorer")
    elif tutorial:
        app.start_tutorial()
    elif simlab:
        app.start_simlab()
    elif duel:
        app.start_duel(mode or "explorer", seed)
    elif auto:
        app.start_live_ai(mode or "explorer", seed, agent)
    elif mode:
        app.start_game(mode, seed)
    if screenshot and frames is None:
        frames = 1
    app.run(max_frames=frames, screenshot=screenshot)
