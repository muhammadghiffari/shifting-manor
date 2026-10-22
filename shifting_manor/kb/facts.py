"""Facts, constraints and firing records for the Caretaker knowledge base."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from shifting_manor.engine.types import Cell

ConstraintKind = Literal["PIT", "GHOST", "TREASURE"]

# Facts that are recomputed from the durable base every turn. They are never
# committed, so a removed goal does not linger after the next step.
DERIVED_ONLY = frozenset(
    {
        "Safe",
        "Unsafe",
        "Reachable",
        "GoalSafe",
        "GoalTreasure",
        "GoalEntrance",
        "CharmAction",
        "AvoidWing",
        "GambleNeeded",
        "Retreat",
    }
)

# Raw percepts are used for one chaining pass, then archived in the history.
OBSERVATION_NAMES = frozenset(
    {
        "Breeze",
        "NoBreeze",
        "Chill",
        "NoChill",
        "Glimmer",
        "NoGlimmer",
        "Scream",
        "Rumble",
    }
)

GLOBAL_NAMES = frozenset(
    {"PitTotal", "Oil", "GhostAlive", "HasTreasure", "CharmAvailable", "ActionCount"}
)

PIT_GHOST_CELL_FACTS = frozenset({"Pit", "NoPit", "Ghost", "NoGhost"})

_MISSING = object()


@dataclass(frozen=True)
class Fact:
    name: str
    cell: Cell | None = None
    value: Any = None

    def __repr__(self) -> str:
        if self.cell is not None:
            return f"{self.name}{self.cell}"
        if self.value is not None:
            return f"{self.name}={self.value!r}"
        return self.name


@dataclass(frozen=True)
class Constraint:
    kind: ConstraintKind
    cells: frozenset[Cell]

    def __repr__(self) -> str:
        cells = ",".join(str(c) for c in sorted(self.cells))
        return f"Constraint({self.kind}, {{{cells}}})"


@dataclass(frozen=True)
class Firing:
    rule_id: str
    premises: tuple[object, ...]
    conclusions: tuple[object, ...]
    turn: int
    note: str = ""
    rederived: bool = False
    shift_index: int = 0


@dataclass
class Explanation:
    thought: str = ""
    firings: list[Firing] = field(default_factory=list)
    beliefs: dict[Cell, str] = field(default_factory=dict)


def fact_sort_key(item: object) -> tuple:
    if isinstance(item, Fact):
        return ("F", item.name, item.cell or (-1, -1), repr(item.value))
    if isinstance(item, Constraint):
        return ("C", item.kind, tuple(sorted(item.cells)), "")
    return ("Z", repr(item), (), "")


def fact(name: str, cell: Cell | None = None, value: Any = None) -> Fact:
    return Fact(name, cell, value)
