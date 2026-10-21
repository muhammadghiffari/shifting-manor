"""B4 oracle: sees the full map and plans the best safe route (upper bound only)."""

from __future__ import annotations

from collections.abc import Iterable

from shifting_manor.agents.kb_agent import direction_between
from shifting_manor.agents.planner import astar
from shifting_manor.engine.generator import generate
from shifting_manor.engine.grid import DIRS, line_cells, step
from shifting_manor.engine.modes import get_mode
from shifting_manor.engine.types import (
    Action,
    CastCharm,
    Cell,
    Event,
    GameInfo,
    Leave,
    Move,
    Percepts,
)
from shifting_manor.kb.facts import Explanation


class OracleAgent:
    name = "b4"

    def __init__(self) -> None:
        self.info: GameInfo | None = None
        self.pits: frozenset[Cell] = frozenset()
        self.ghost: Cell | None = None
        self.treasure: Cell = (0, 0)
        self.pos: Cell = (0, 0)
        self.oil = 0
        self.has_treasure = False
        self.charm_available = True
        self.last = Explanation(thought="Oracle sees the map.")

    def reset(self, info: GameInfo) -> None:
        self.info = info
        board = generate(get_mode(info.mode), info.seed)
        self.pits = board.pits
        self.ghost = board.ghost
        self.treasure = board.treasure
        self.pos = info.entrance
        self.oil = info.oil
        self.has_treasure = False
        self.charm_available = True

    def act(self, percepts: Percepts, events: Iterable[Event]) -> Action:
        self._absorb(events)
        assert self.info is not None
        if self.pos == self.info.entrance and self.has_treasure:
            return Leave()
        if self.ghost is not None and self.charm_available:
            for d in DIRS:
                if self.ghost in line_cells(self.pos, d, self.info.size):
                    self.last = Explanation(thought="Oracle banishes the ghost.")
                    return CastCharm(d)
        target = self.info.entrance if self.has_treasure else self.treasure
        if not self.has_treasure:
            safe = self._route(target, avoid_hazards=True)
            if safe is None or safe.steps + self._distance_home(target) > self.oil:
                if self._distance_home(self.pos) <= self.oil:
                    target = self.info.entrance
                    safe = self._route(target, avoid_hazards=True)
                    if safe is not None and safe.first_step is not None:
                        self.last = Explanation(thought="Oracle banks the run before oil runs out.")
                        return Move(direction_between(self.pos, safe.first_step))  # type: ignore[arg-type]
                return Leave() if self.pos == self.info.entrance else self._fallback_move()
        else:
            safe = self._route(target, avoid_hazards=True)
        route = safe or self._route(target, avoid_hazards=False)
        if route is None or route.first_step is None:
            return Leave() if self.pos == self.info.entrance else self._fallback_move()
        direction = direction_between(self.pos, route.first_step)
        self.last = Explanation(thought=f"Oracle routes to {target}.")
        return Move(direction) if direction else self._fallback_move()

    def _fallback_move(self) -> Action:
        assert self.info is not None
        hazards = set(self.pits)
        if self.ghost is not None:
            hazards.add(self.ghost)
        for d in DIRS:
            nxt = step(self.pos, d)
            if 0 <= nxt[0] < self.info.size and 0 <= nxt[1] < self.info.size and nxt not in hazards:
                return Move(d)
        return Move("N")

    def _absorb(self, events: Iterable[Event]) -> None:
        for event in events:
            name = type(event).__name__
            if name == "Moved":
                self.pos = event.cell  # type: ignore[attr-defined]
                self.oil -= 1
            elif name == "PickedUp":
                self.has_treasure = True
            elif name == "CharmCast":
                self.oil -= 1
                self.charm_available = False
            elif name == "GhostBanished":
                self.ghost = None
            elif name == "ShiftApplied":
                mapping = event.mapping  # type: ignore[attr-defined]
                self.pits = frozenset(mapping.get(p, p) for p in self.pits)
                if self.ghost is not None:
                    self.ghost = mapping.get(self.ghost, self.ghost)

    def _route(self, goal: Cell, *, avoid_hazards: bool, start: Cell | None = None):
        assert self.info is not None
        hazards = set(self.pits)
        if self.ghost is not None:
            hazards.add(self.ghost)

        def risk(cell: Cell) -> float:
            if cell in hazards:
                return 0.0 if avoid_hazards else 0.999
            return 0.0

        blocked = hazards if avoid_hazards else set()
        return astar(
            start or self.pos,
            {goal},
            self.info.size,
            risk_of=risk,
            blocked=blocked,
        )

    def _distance_home(self, start: Cell) -> int:
        assert self.info is not None
        route = self._route(self.info.entrance, avoid_hazards=True, start=start)
        if route is not None:
            return route.steps
        # conservative Manhattan when every safe route is blocked
        return abs(start[0] - self.info.entrance[0]) + abs(start[1] - self.info.entrance[1])

    def explain(self) -> Explanation:
        return self.last
