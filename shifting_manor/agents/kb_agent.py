"""The knowledge-based Caretaker agent. One class, three variants (B2, B2b, B3)."""

from __future__ import annotations

import random
from collections.abc import Iterable

from shifting_manor.agents.planner import Route, cautious_route, safe_route
from shifting_manor.engine.grid import DIRS, in_bounds, manhattan, step
from shifting_manor.engine.types import (
    Action,
    CastCharm,
    Cell,
    Dir,
    Event,
    GameInfo,
    Leave,
    Move,
    Percepts,
)
from shifting_manor.kb.base import KnowledgeBase
from shifting_manor.kb.facts import Explanation, Firing


def direction_between(a: Cell, b: Cell) -> Dir | None:
    dx, dy = b[0] - a[0], b[1] - a[1]
    if (dx, dy) == (0, 1):
        return "N"
    if (dx, dy) == (1, 0):
        return "E"
    if (dx, dy) == (0, -1):
        return "S"
    if (dx, dy) == (-1, 0):
        return "W"
    return None


class KBAgent:
    """Forward chaining over R01-R24, then a plan from the derived goals.

    variant: b3 = full (R16 transport), b2 = shift-blind, b2b = forgetful.
    """

    def __init__(self, variant: str = "b3") -> None:
        self.variant = variant
        self.name = variant
        self.info: GameInfo | None = None
        self.kb: KnowledgeBase | None = None
        self.pos: Cell = (0, 0)
        self.oil = 0
        self.actions = 0
        self.has_treasure = False
        self.charm_available = True
        self.rng = random.Random(0)
        self.last = Explanation()
        self.last_firings: list[Firing] = []
        self.last_action: Action | None = None

    def reset(self, info: GameInfo) -> None:
        self.info = info
        self.kb = KnowledgeBase(info, variant=self.variant)
        self.pos = info.entrance
        self.oil = info.oil
        self.actions = 0
        self.has_treasure = False
        self.charm_available = True
        self.rng = random.Random(f"{info.seed}:agent:{self.variant}")
        self.last = Explanation()
        self.last_firings = []
        self.last_action = None

    def act(self, percepts: Percepts, events: Iterable[Event]) -> Action:
        if self.info is None or self.kb is None:
            raise RuntimeError("reset() before act()")
        events = list(events)
        self.kb.on_events(events)
        self._absorb(events)
        self._sync_globals()
        self.kb.observe(percepts)
        self._sync_globals()
        action = self._decide()
        self.last_action = action
        self.last_firings = list(self.kb.firings)
        self.last = Explanation(
            thought=self._thought(action),
            firings=self.last_firings,
            beliefs=self.kb.belief_labels(),
        )
        return action

    def explain(self) -> Explanation:
        return self.last

    # -- event bookkeeping ------------------------------------------------
    def _absorb(self, events: list[Event]) -> None:
        for event in events:
            name = type(event).__name__
            if name == "Moved":
                self.pos = event.cell  # type: ignore[attr-defined]
                self.oil -= 1
                self.actions += 1
            elif name == "CharmCast":
                self.oil -= 1
                self.actions += 1
                self.charm_available = False
            elif name == "PickedUp":
                self.has_treasure = True

    def _sync_globals(self) -> None:
        assert self.kb is not None
        self.kb.set_global("Oil", max(0, self.oil))
        self.kb.set_global("ActionCount", self.actions)
        self.kb.set_global("HasTreasure", self.has_treasure)
        self.kb.set_global("CharmAvailable", self.charm_available)

    # -- decision ---------------------------------------------------------
    def _decide(self) -> Action:
        assert self.kb is not None
        kb = self.kb
        if self.charm_available and kb.has("CharmAction"):
            direction = kb.value("CharmAction")
            return CastCharm(direction)  # type: ignore[arg-type]
        if kb.has("GoalEntrance"):
            return self._to_entrance("Carrying the heirloom, R18 sends me home.")
        if kb.has("Retreat"):
            return self._to_entrance("Oil is low (R23); retreat before exploring.")
        if kb.has("GoalTreasure"):
            target = kb.named("GoalTreasure")[0].cell
            if target is not None:
                action = self._move_to(target, safe=True, thought="R19: treasure is reachable.")
                if action is not None:
                    return action
        if kb.has("GoalSafe"):
            target = kb.named("GoalSafe")[0].cell
            if target is not None:
                action = self._move_to(target, safe=True, thought="R21: nearest safe room.")
                if action is not None:
                    return action
        if kb.has("GambleNeeded"):
            target = self._gamble_target()
            if target is not None:
                action = self._move_to(
                    target, safe=False, thought="R22: no safe goal; take the best gamble."
                )
                if action is not None:
                    return action
        return self._fallback()

    def _to_entrance(self, thought: str) -> Action:
        assert self.info is not None
        if self.pos == self.info.entrance:
            return Leave()
        action = self._move_to(self.info.entrance, safe=not self.has_treasure, thought=thought)
        if action is not None:
            return action
        action = self._move_to(self.info.entrance, safe=False, thought=thought)
        if action is not None:
            return action
        return self._fallback()

    def _move_to(self, target: Cell, *, safe: bool, thought: str) -> Action | None:
        assert self.kb is not None
        route: Route | None
        if safe:
            route = safe_route(self.kb, self.pos, target)
        else:
            avoid = self._avoid_wing()
            route = cautious_route(self.kb, self.pos, target, avoid=avoid, avoid_penalty=0.3)
        if route is None or route.first_step is None:
            return None
        direction = direction_between(self.pos, route.first_step)
        if direction is None:
            return None
        self.last = Explanation(thought=thought, firings=list(self.kb.firings))
        return Move(direction)

    def _gamble_target(self) -> Cell | None:
        assert self.kb is not None
        candidates = self.kb.frontier()
        if not candidates:
            candidates = [
                (x, y)
                for x in range(self.kb.info.size)
                for y in range(self.kb.info.size)
                if not self.kb.has("Visited", (x, y))
                and not self.kb.has("Pit", (x, y))
                and not self.kb.has("Ghost", (x, y))
            ]
        if not candidates:
            return None
        return min(candidates, key=lambda c: (manhattan(self.pos, c), c))

    def _avoid_wing(self) -> set[Cell]:
        assert self.kb is not None
        if not self.kb.has("AvoidWing"):
            return set()
        wing = self.kb.named("AvoidWing")[0].value
        return {c for c in self.kb.info.wings if self.kb.info.wings[c] == wing}

    def _fallback(self) -> Action:
        assert self.info is not None and self.kb is not None
        if self.pos == self.info.entrance and self.has_treasure:
            return Leave()
        options: list[Cell] = []
        for d in DIRS:
            nxt = step(self.pos, d)
            if not in_bounds(nxt, self.info.size):
                continue
            if self.kb.has("Unsafe", nxt) or self.kb.has("Pit", nxt) or self.kb.has("Ghost", nxt):
                continue
            options.append(nxt)
        unvisited = [c for c in options if not self.kb.has("Visited", c)]
        if not unvisited:
            unvisited = options
        if not unvisited:
            if self.pos == self.info.entrance:
                return Leave()
            target = self.info.entrance
            route = cautious_route(self.kb, self.pos, target)
            if route and route.first_step:
                d = direction_between(self.pos, route.first_step)
                if d:
                    return Move(d)
            return CastCharm("N") if self.charm_available else Move("N")
        target = min(unvisited, key=lambda c: (manhattan(self.pos, c), c))
        d = direction_between(self.pos, target)
        return Move(d) if d else Move("N")

    def _thought(self, action: Action) -> str:
        assert self.kb is not None
        ids = sorted({f.rule_id for f in self.kb.firings})
        rules = ",".join(ids) if ids else "no new rules"
        return f"{action!r} from {rules}."
