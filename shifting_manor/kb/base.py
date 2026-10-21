"""Knowledge base: durable facts + per-turn forward-chained closure.

Design note: raw percept facts are used for exactly one chaining pass and then
archived, while their durable conclusions (NoPit, constraints, ...) are stored.
That is what lets R16 transport what the agent knows without a stale Breeze
fact re-deriving the pre-shift constraint on the next turn.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable

from shifting_manor.engine.grid import neighbours, wing_of
from shifting_manor.engine.types import Cell, Event, GameInfo, Percepts
from shifting_manor.kb.facts import (
    DERIVED_ONLY,
    GLOBAL_NAMES,
    OBSERVATION_NAMES,
    PIT_GHOST_CELL_FACTS,
    Constraint,
    Fact,
    Firing,
)
from shifting_manor.kb.transport import transport

_MISSING = object()

PIT_RISK_NAMES = frozenset({"Pit", "NoPit"})
GHOST_RISK_NAMES = frozenset({"Ghost", "NoGhost"})


class KnowledgeBase:
    def __init__(self, info: GameInfo, variant: str = "b3") -> None:
        self.info = info
        self.variant = variant
        self.base: set[Fact] = set()
        self.derived: set[Fact] = set()
        self.inbox: set[Fact] = set()
        self.constraints: set[Constraint] = set()
        self.percept_history: list[tuple[Cell, Percepts]] = []
        self.log: list[Firing] = []
        self.firings: list[Firing] = []
        self.turn = 0
        self.warnings: list[str] = []
        self.set_global("PitTotal", info.pit_total)
        self.set_global("Oil", info.oil)
        self.set_global("GhostAlive", True)
        self.set_global("HasTreasure", False)
        self.set_global("CharmAvailable", True)
        self.set_global("ActionCount", 0)
        self.add_base(Fact("At", info.entrance))
        self.add_base(Fact("Visited", info.entrance))

    # -- storage ----------------------------------------------------------
    @property
    def facts(self) -> set[Fact]:
        return self.base | self.derived | self.inbox

    def named(self, name: str) -> list[Fact]:
        return [f for f in self.facts if f.name == name]

    def has(self, name: str, cell: Cell | None = None, value: object = _MISSING) -> bool:
        for item in self.facts:
            if item.name != name:
                continue
            if cell is not None and item.cell != cell:
                continue
            if value is not _MISSING and item.value != value:
                continue
            return True
        return False

    def value(self, name: str, default: object = None) -> object:
        for item in self.base:
            if item.name == name:
                return item.value
        for item in self.derived:
            if item.name == name:
                return item.value
        return default

    def set_global(self, name: str, value: object) -> None:
        self.base = {f for f in self.base if f.name != name}
        self.derived = {f for f in self.derived if f.name != name}
        self.base.add(Fact(name, value=value))

    def add_base(self, item: Fact | Constraint) -> bool:
        if isinstance(item, Constraint):
            if item in self.constraints:
                return False
            self.constraints.add(item)
            return True
        if item.name in GLOBAL_NAMES:
            if self.value(item.name, _MISSING) == item.value:
                return False
            self.set_global(item.name, item.value)
            return True
        if item.name == "At":
            self.base = {f for f in self.base if f.name != "At"}
            self.derived = {f for f in self.derived if f.name != "At"}
        if item in self.base or item in self.derived:
            return False
        self.base.add(item)
        return True

    def add(self, item: Fact | Constraint) -> bool:
        """Chainer-facing add: new facts go to the derived layer."""
        if isinstance(item, Constraint):
            if item in self.constraints:
                return False
            self.constraints.add(item)
            return True
        if item.name in GLOBAL_NAMES:
            if self.value(item.name, _MISSING) == item.value:
                return False
            self.set_global(item.name, item.value)
            return True
        if item in self.base or item in self.derived or item in self.inbox:
            return False
        self.derived.add(item)
        return True

    def set_position(self, cell: Cell) -> None:
        self.add_base(Fact("At", cell))

    # -- observation and events ------------------------------------------
    def observe(self, percepts: Percepts) -> list[Firing]:
        cell = self.position
        self.percept_history.append((cell, percepts))
        self.add_base(Fact("Visited", cell))
        self.inbox.add(Fact("Breeze", cell) if percepts.breeze else Fact("NoBreeze", cell))
        self.inbox.add(Fact("Chill", cell) if percepts.chill else Fact("NoChill", cell))
        self.inbox.add(Fact("Glimmer", cell) if percepts.glimmer else Fact("NoGlimmer", cell))
        if percepts.scream:
            self.prune_ghost()
            self.inbox.add(Fact("Scream", cell))
        if percepts.rumble is not None:
            self.inbox.add(Fact("Rumble", value=percepts.rumble.wing))
        return self.run()

    def on_events(self, events: Iterable[Event]) -> None:
        for event in events:
            name = type(event).__name__
            if name == "Moved":
                self.set_position(event.cell)  # type: ignore[attr-defined]
            elif name == "PickedUp":
                self.set_global("HasTreasure", True)
            elif name == "CharmCast":
                self.set_global("CharmAvailable", False)
            elif name == "GhostBanished":
                self.prune_ghost()
            elif name == "ShiftApplied":
                self.apply_shift(
                    event.wing,  # type: ignore[attr-defined]
                    event.direction,  # type: ignore[attr-defined]
                    event.mapping,  # type: ignore[attr-defined]
                )

    def prune_ghost(self) -> None:
        self.base = {f for f in self.base if f.name != "Ghost"}
        self.derived = {f for f in self.derived if f.name != "Ghost"}
        self.constraints = {c for c in self.constraints if c.kind != "GHOST"}
        self.set_global("GhostAlive", False)

    def apply_shift(self, wing: int, direction: str, mapping: dict[Cell, Cell]) -> None:
        if self.variant == "b2":
            return
        self.derived = set()
        self.inbox = set()
        if self.variant == "b2b":
            wing_cells = set(mapping)
            self.base = {
                f
                for f in self.base
                if not (f.name in PIT_GHOST_CELL_FACTS and f.cell in wing_cells)
            }
            self.constraints = {
                c
                for c in self.constraints
                if not (c.kind in ("PIT", "GHOST") and (c.cells & wing_cells))
            }
            return
        new_base, new_constraints = transport(self.base, self.constraints, mapping)
        changed = tuple(
            sorted(
                (set(new_base) - self.base) | (set(new_constraints) - self.constraints),
                key=repr,
            )
        )
        self.base = set(new_base)
        self.constraints = set(new_constraints)
        premise = Fact("Rotated", value=(wing, direction))
        firing = Firing("R16", (premise,), changed, self.turn)
        self.firings.append(firing)
        self.log.append(firing)

    # -- inference --------------------------------------------------------
    def run(self) -> list[Firing]:
        from shifting_manor.kb.forward import forward_chain
        from shifting_manor.kb.rules import RULES

        self.derived = set()
        firings = forward_chain(self, RULES, self.turn)
        self.firings = firings
        self.log.extend(firings)
        durable = {
            f
            for f in self.derived
            if f.name not in DERIVED_ONLY and f.name not in OBSERVATION_NAMES
        }
        self.base |= durable
        self.inbox = set()
        self.turn += 1
        return firings

    # -- convenience ------------------------------------------------------
    @property
    def position(self) -> Cell:
        for item in self.facts:
            if item.name == "At" and item.cell is not None:
                return item.cell
        return self.info.entrance

    def cell_set(self, name: str) -> set[Cell]:
        return {f.cell for f in self.facts if f.name == name and f.cell is not None}

    def frontier(self) -> list[Cell]:
        cells: set[Cell] = set()
        for con in self.constraints:
            if con.kind in ("PIT", "GHOST"):
                cells.update(con.cells)
        decided = (
            self.cell_set("NoPit")
            | self.cell_set("Pit")
            | self.cell_set("NoGhost")
            | self.cell_set("Ghost")
        )
        return sorted(cells - decided)

    def frontier_pits(self) -> list[Cell]:
        uncertain = set()
        for con in self.constraints:
            if con.kind == "PIT":
                uncertain.update(con.cells)
        return sorted(uncertain - self.cell_set("NoPit") - self.cell_set("Pit"))

    def frontier_ghosts(self) -> list[Cell]:
        uncertain = set()
        for con in self.constraints:
            if con.kind == "GHOST":
                uncertain.update(con.cells)
        return sorted(uncertain - self.cell_set("NoGhost") - self.cell_set("Ghost"))

    def safe_reach(self, start: Cell | None = None) -> set[Cell]:
        start = start or self.position
        safe = self.cell_set("Safe") | {start}
        seen = {start}
        queue = deque([start])
        while queue:
            cur = queue.popleft()
            for nxt in neighbours(cur, self.info.size):
                if nxt in seen or nxt not in safe:
                    continue
                seen.add(nxt)
                queue.append(nxt)
        return seen

    def shortest_safe_to(self, goal: Cell, start: Cell | None = None) -> int | None:
        start = start or self.position
        safe = self.cell_set("Safe") | {start, goal}
        if start not in safe or goal not in safe:
            return None
        seen = {start: 0}
        queue = deque([start])
        while queue:
            cur = queue.popleft()
            if cur == goal:
                return seen[cur]
            for nxt in neighbours(cur, self.info.size):
                if nxt in safe and nxt not in seen:
                    seen[nxt] = seen[cur] + 1
                    queue.append(nxt)
        return None

    def belief_labels(self) -> dict[Cell, str]:
        labels: dict[Cell, str] = {}
        for x in range(self.info.size):
            for y in range(self.info.size):
                c = (x, y)
                if self.has("Safe", c):
                    labels[c] = "safe"
                elif self.has("Pit", c):
                    labels[c] = "pit"
                elif self.has("Ghost", c):
                    labels[c] = "ghost"
                elif self.has("Unsafe", c):
                    labels[c] = "unsafe"
                elif self.has("NoPit", c) and self.has("NoGhost", c):
                    labels[c] = "safe"
                elif self.has("NoPit", c):
                    labels[c] = "no-pit"
                elif self.has("NoGhost", c):
                    labels[c] = "no-ghost"
                elif self.has("NoTreasure", c):
                    labels[c] = "no-treasure"
                else:
                    labels[c] = "unknown"
        return labels

    def wing_of(self, cell: Cell) -> int:
        return wing_of(cell, self.info.size)
