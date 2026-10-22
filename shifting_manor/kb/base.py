"""Knowledge base: durable facts + per-turn forward-chained closure.

Design note: raw percept facts are used for exactly one chaining pass and then
archived, while their durable conclusions (NoPit, constraints, ...) are stored.
That is what lets R16 transport what the agent knows without a stale Breeze
fact re-deriving the pre-shift constraint on the next turn.
"""

from __future__ import annotations

from collections import Counter, deque
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
        self.all_log: list[Firing] = []
        self.all_firings: list[Firing] = []
        self.pending_firings: list[Firing] = []
        self.provenance: dict[Fact, Firing] = {}
        self.constraint_provenance: dict[Constraint, Firing] = {}
        self.derived_prev: set[Fact] = set()
        self.rederivation_count = 0
        self.rederivation_by_rule: Counter[str] = Counter()
        self.last_rederivations = 0
        self.last_rederivations_by_rule: Counter[str] = Counter()
        self.shift_count = 0
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
        self.provenance[Fact("At", info.entrance)] = Firing(
            "GIVEN", (), (Fact("At", info.entrance),), 0
        )
        self.provenance[Fact("Visited", info.entrance)] = Firing(
            "PERCEPT", (), (Fact("Visited", info.entrance),), 0
        )

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
        item = Fact(name, value=value)
        self.base.add(item)
        # A global is given, not inferred; it is a proof leaf like a percept.
        self.provenance.setdefault(item, Firing("GIVEN", (), (item,), self.turn))

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
        item = Fact("At", cell)
        self.add_base(item)
        self.provenance[item] = Firing("PERCEPT", (), (item,), self.turn)

    # -- observation and events ------------------------------------------
    def observe(self, percepts: Percepts) -> list[Firing]:
        cell = self.position
        self.percept_history.append((cell, percepts))
        visited = Fact("Visited", cell)
        self.add_base(visited)
        self.provenance[visited] = Firing("PERCEPT", (), (visited,), self.turn)
        observed: list[Fact] = [
            Fact("Breeze", cell) if percepts.breeze else Fact("NoBreeze", cell),
            Fact("Chill", cell) if percepts.chill else Fact("NoChill", cell),
            Fact("Glimmer", cell) if percepts.glimmer else Fact("NoGlimmer", cell),
        ]
        if percepts.scream:
            self.prune_ghost()
            observed.append(Fact("Scream", cell))
        if percepts.rumble is not None:
            observed.append(Fact("Rumble", value=percepts.rumble.wing))
        for item in observed:
            self.inbox.add(item)
            # Percepts are proof leaves: no rule premises, turn of observation.
            self.provenance.setdefault(item, Firing("PERCEPT", (), (item,), self.turn))
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
        self.derived_prev = {f for f in self.derived_prev if f.name != "Ghost"}
        self.constraints = {c for c in self.constraints if c.kind != "GHOST"}
        self.set_global("GhostAlive", False)

    def apply_shift(self, wing: int, direction: str, mapping: dict[Cell, Cell]) -> None:
        self.shift_count += 1
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
            self.derived_prev = {
                f
                for f in self.derived_prev
                if not (f.name in PIT_GHOST_CELL_FACTS and f.cell in wing_cells)
            }
            return
        old_base = self.base
        old_constraints = self.constraints
        new_base, new_constraints = transport(self.base, self.constraints, mapping)
        moved_pairs = [
            (old, Fact(old.name, mapping[old.cell], old.value))
            for old in old_base
            if old.name in PIT_GHOST_CELL_FACTS
            and old.cell is not None
            and mapping.get(old.cell, old.cell) != old.cell
        ]
        changed = tuple(
            sorted(
                (set(new_base) - self.base) | (set(new_constraints) - self.constraints),
                key=repr,
            )
        )
        self.base = set(new_base)
        self.constraints = set(new_constraints)
        self.derived_prev = {self._transport_fact(f, mapping) for f in self.derived_prev}
        premise = Fact("Rotated", value=(wing, direction))
        count = len(moved_pairs)
        note = f"R16 transported {count} fact{'' if count == 1 else 's'} (wing {wing}, {direction})"
        firing = Firing("R16", (premise,), changed, self.turn, note, shift_index=self.shift_count)
        self.pending_firings.append(firing)
        self.log.append(firing)
        for old, new in moved_pairs:
            self.provenance[new] = Firing(
                "R16", (old,), (new,), self.turn, note, shift_index=self.shift_count
            )
        for old in old_constraints:
            if old.kind not in ("PIT", "GHOST"):
                continue
            new = Constraint(old.kind, frozenset(mapping.get(c, c) for c in old.cells))
            if new != old:
                self.constraint_provenance[new] = Firing(
                    "R16", (old,), (new,), self.turn, note, shift_index=self.shift_count
                )

    @staticmethod
    def _transport_fact(item: Fact, mapping: dict[Cell, Cell]) -> Fact:
        if item.name in PIT_GHOST_CELL_FACTS and item.cell is not None:
            return Fact(item.name, mapping.get(item.cell, item.cell), item.value)
        return item

    # -- inference --------------------------------------------------------
    def run(self) -> list[Firing]:
        from shifting_manor.kb.forward import forward_chain
        from shifting_manor.kb.rules import RULES

        event_firings, self.pending_firings = self.pending_firings, []
        self.derived = set()
        self.last_rederivations = 0
        self.last_rederivations_by_rule = Counter()
        firings = forward_chain(self, RULES, self.turn)
        new_firings: list[Firing] = []
        turn_firings: list[Firing] = []
        for firing in firings:
            fresh: list[object] = []
            for item in firing.conclusions:
                if isinstance(item, Fact) and item in self.derived_prev:
                    self.rederivation_count += 1
                    self.rederivation_by_rule[firing.rule_id] += 1
                    self.last_rederivations += 1
                    self.last_rederivations_by_rule[firing.rule_id] += 1
                else:
                    fresh.append(item)
            if not fresh:
                turn_firings.append(
                    Firing(
                        firing.rule_id,
                        firing.premises,
                        firing.conclusions,
                        firing.turn,
                        firing.note,
                        rederived=True,
                    )
                )
                continue
            logged = Firing(firing.rule_id, firing.premises, tuple(fresh), firing.turn, firing.note)
            new_firings.append(logged)
            turn_firings.append(logged)
            for item in fresh:
                if isinstance(item, Fact):
                    self.provenance.setdefault(item, logged)
                else:
                    self.constraint_provenance.setdefault(item, logged)
        self.derived_prev = set(self.derived)
        self.firings = [*event_firings, *new_firings]
        self.all_firings = [*event_firings, *turn_firings]
        self.log.extend(new_firings)
        self.all_log.extend(self.all_firings)
        durable = {
            f
            for f in self.derived
            if f.name not in DERIVED_ONLY and f.name not in OBSERVATION_NAMES
        }
        self.base |= durable
        self.inbox = set()
        self.turn += 1
        return self.firings

    # -- convenience ------------------------------------------------------
    @property
    def position(self) -> Cell:
        for item in self.facts:
            if item.name == "At" and item.cell is not None:
                return item.cell
        return self.info.entrance

    def cell_set(self, name: str) -> set[Cell]:
        return {f.cell for f in self.facts if f.name == name and f.cell is not None}

    def rule_counts(self) -> Counter[str]:
        """First-derivation counts per rule (the numbers the heat bars show)."""
        return Counter(f.rule_id for f in self.log)

    def frontier(self) -> list[Cell]:
        pit_cells: set[Cell] = set()
        ghost_cells: set[Cell] = set()
        for con in self.constraints:
            if con.kind == "PIT":
                pit_cells.update(con.cells)
            elif con.kind == "GHOST":
                ghost_cells.update(con.cells)
        pit_candidates = pit_cells - self.cell_set("NoPit") - self.cell_set("Pit")
        ghost_candidates = ghost_cells - self.cell_set("NoGhost") - self.cell_set("Ghost")
        return sorted(pit_candidates | ghost_candidates)

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
