"""The game state machine. Pure Python: no pygame imports anywhere in engine/."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from shifting_manor.engine.generator import GeneratedMap, generate
from shifting_manor.engine.grid import (
    FOYER_WING,
    ROTATING_WINGS,
    in_bounds,
    line_cells,
    neighbours,
    step,
    wing_map,
    wing_of,
)
from shifting_manor.engine.modes import Mode, get_mode
from shifting_manor.engine.shift import ShiftPlan, plan_request, request_shift
from shifting_manor.engine.types import (
    Action,
    Bumped,
    CastCharm,
    Cell,
    CharmCast,
    Died,
    Escaped,
    Event,
    GameInfo,
    GhostBanished,
    InvalidAction,
    Leave,
    Move,
    Moved,
    OilLow,
    OilOut,
    Percepts,
    PickedUp,
    ShiftApplied,
    ShiftSkipped,
    ShiftTelegraph,
    ShiftWarning,
    StepResult,
)


@dataclass
class GameState:
    size: int
    pits: frozenset[Cell]
    ghost: Cell | None
    treasure: Cell
    entrance: Cell
    agent: Cell
    oil: int
    start_oil: int
    has_treasure: bool = False
    charm_available: bool = True
    action_count: int = 0
    actions_taken: int = 0
    charms_cast: int = 0
    ghost_banished: bool = False
    done: bool = False
    outcome: str | None = None
    event_log: list[tuple[int, tuple[Event, ...]]] = field(default_factory=list)

    @property
    def ghost_alive(self) -> bool:
        return self.ghost is not None


class Game:
    def __init__(self, mode: Mode | str, seed: str, layout: GeneratedMap | None = None) -> None:
        self.mode = get_mode(mode)
        self.seed = seed
        generated = layout or generate(self.mode, seed)
        self.state = GameState(
            size=self.mode.size,
            pits=frozenset(generated.pits),
            ghost=generated.ghost,
            treasure=generated.treasure,
            entrance=(0, 0),
            agent=(0, 0),
            oil=self.mode.oil,
            start_oil=self.mode.oil,
        )
        self._shift_rng = random.Random(f"{seed}:shift")
        self._pending: ShiftPlan | None = None
        self._pending_due: int | None = None
        self._bump = False
        self._scream = False
        self._oil_low_announced = False

    @classmethod
    def from_map(
        cls,
        mode: Mode | str,
        seed: str,
        *,
        pits: set[Cell] | frozenset[Cell],
        ghost: Cell | None,
        treasure: Cell,
        oil: int | None = None,
    ) -> Game:
        """Deterministic test/demo board without rejection sampling."""
        game = cls(mode, seed, GeneratedMap(frozenset(pits), ghost, treasure))
        if oil is not None:
            game.state.oil = oil
            game.state.start_oil = oil
        return game

    # -- public interface -------------------------------------------------
    def info(self) -> GameInfo:
        return GameInfo(
            size=self.state.size,
            pit_total=self.mode.pits,
            entrance=self.state.entrance,
            shift_every=self.mode.shift_every,
            oil=self.state.start_oil,
            wings=wing_map(self.state.size),
            foyer_wing=FOYER_WING,
            rotating_wings=ROTATING_WINGS if self.state.size == 6 else (),
            seed=self.seed,
            mode=self.mode.name,
        )

    def observe(self) -> Percepts:
        st = self.state
        breeze = any(n in st.pits for n in neighbours(st.agent, st.size))
        chill = st.ghost is not None and st.ghost in neighbours(st.agent, st.size)
        glimmer = st.treasure == st.agent or st.treasure in neighbours(st.agent, st.size)
        rumble = None
        if self._pending is not None and self._pending_due is not None:
            remaining = self._pending_due - st.action_count
            if remaining > 0:
                rumble = ShiftWarning(
                    self._pending.wing, self._pending.direction, in_actions=remaining
                )
        return Percepts(
            breeze=breeze,
            chill=chill,
            glimmer=glimmer,
            bump=self._bump,
            scream=self._scream,
            rumble=rumble,
        )

    def step(self, action: Action) -> StepResult:
        if self.state.done:
            return StepResult(self.observe(), [], True)
        self._bump = False
        self._scream = False
        events: list[Event] = []
        result = self._apply(action, events)
        if result is not None:
            self._log(events)
            return result
        if not self.state.done:
            self._maybe_oil_low(events)
            if not self.state.done:
                self._advance_shift(events)
        self._log(events)
        return StepResult(self.observe(), events, self.state.done)

    def score(self) -> int:
        st = self.state
        score = -st.actions_taken - 10 * st.charms_cast
        if st.ghost_banished:
            score += 200
        if st.outcome == "escaped_treasure":
            score += 1000
        if st.outcome in ("died_pit", "died_ghost"):
            score -= 1000
        return score

    def stars(self) -> int:
        if not (self.state.outcome or "").startswith("escaped"):
            return 0
        score = self.score()
        if score >= 900:
            return 3
        if score >= 850:
            return 2
        return 1

    def reveal(self) -> dict[str, object]:
        """Full board for the result screen / oracle, never for a live human."""
        return {
            "pits": sorted(self.state.pits),
            "ghost": self.state.ghost,
            "treasure": self.state.treasure,
            "entrance": self.state.entrance,
        }

    def shift_status(self) -> tuple[int, str, int] | None:
        """(wing, direction, actions_left) for the telegraphed shift, else None."""
        if self._pending is None or self._pending_due is None:
            return None
        left = max(0, self._pending_due - self.state.action_count)
        return (self._pending.wing, self._pending.direction, left)

    # -- internals --------------------------------------------------------
    def _apply(self, action: Action, events: list[Event]) -> StepResult | None:
        st = self.state
        if isinstance(action, Move):
            target = step(st.agent, action.dir)
            if not in_bounds(target, st.size):
                self._bump = True
                events.append(Bumped(action.dir))
                return StepResult(self.observe(), events, st.done)
            st.oil -= 1
            st.action_count += 1
            st.actions_taken += 1
            st.agent = target
            events.append(Moved(target))
            if target in st.pits:
                self._finish("died_pit", events)
                return StepResult(self.observe(), events, True)
            if st.ghost is not None and target == st.ghost:
                self._finish("died_ghost", events)
                return StepResult(self.observe(), events, True)
            if target == st.treasure and not st.has_treasure:
                st.has_treasure = True
                events.append(PickedUp(target))
            return None
        if isinstance(action, CastCharm):
            if not st.charm_available:
                events.append(InvalidAction("charm already used"))
                return StepResult(self.observe(), events, st.done)
            st.oil -= 1
            st.action_count += 1
            st.actions_taken += 1
            st.charm_available = False
            st.charms_cast += 1
            events.append(CharmCast(action.dir))
            if st.ghost is not None and st.ghost in line_cells(st.agent, action.dir, st.size):
                events.append(GhostBanished(st.ghost))
                st.ghost = None
                st.ghost_banished = True
                self._scream = True
            return None
        if isinstance(action, Leave):
            if st.agent != st.entrance:
                events.append(InvalidAction("leave only at the entrance"))
                return StepResult(self.observe(), events, st.done)
            self._finish("escaped_treasure" if st.has_treasure else "escaped_empty", events)
            return StepResult(self.observe(), events, True)
        events.append(InvalidAction(f"unknown action {action!r}"))
        return StepResult(self.observe(), events, st.done)

    def _finish(self, outcome: str, events: list[Event]) -> None:
        st = self.state
        st.outcome = outcome
        st.done = True
        if outcome == "died_pit":
            events.append(Died("pit"))
        elif outcome == "died_ghost":
            events.append(Died("ghost"))
        elif outcome.startswith("escaped"):
            events.append(Escaped(st.has_treasure))

    def _maybe_oil_low(self, events: list[Event]) -> None:
        st = self.state
        if st.oil <= max(1, st.start_oil // 4) and not self._oil_low_announced:
            self._oil_low_announced = True
            events.append(OilLow(st.oil))
        if st.oil <= 0:
            st.oil = 0
            self._finish("oil_out", events)
            events.append(OilOut())

    def _advance_shift(self, events: list[Event]) -> None:
        st = self.state
        if self.mode.shift_every is None:
            return
        k = self.mode.shift_every
        if (
            self._pending is not None
            and self._pending_due is not None
            and st.action_count >= self._pending_due
        ):
            plan = self._pending
            if wing_of(st.agent, st.size) == plan.wing:
                events.append(ShiftSkipped(plan.wing, "agent inside wing"))
            else:
                st.pits, st.ghost = (
                    frozenset(plan.mapping.get(p, p) for p in st.pits),
                    None if st.ghost is None else plan.mapping.get(st.ghost, st.ghost),
                )
                events.append(ShiftApplied(plan.wing, plan.direction, dict(plan.mapping)))
            self._pending = None
            self._pending_due = None
        if self._pending is None and st.action_count % k == (k - 2) % k:
            due = ((st.action_count // k) + 1) * k
            request = request_shift(self._shift_rng, st.size)
            if request is not None:
                plan = plan_request(
                    request,
                    size=st.size,
                    pits=st.pits,
                    ghost=st.ghost,
                    treasure=st.treasure,
                    entrance=st.entrance,
                    agent=st.agent,
                    has_treasure=st.has_treasure,
                )
                if plan is None:
                    events.append(ShiftSkipped(request.wing, "no valid rotation"))
                else:
                    self._pending = plan
                    self._pending_due = due
                    events.append(ShiftTelegraph(plan.wing, plan.direction, 2))

    def _log(self, events: list[Event]) -> None:
        self.state.event_log.append((self.state.action_count, tuple(events)))
