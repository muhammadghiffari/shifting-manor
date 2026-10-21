"""R16 knowledge transport: one pure function with its own tests."""

from __future__ import annotations

from collections.abc import Iterable

from shifting_manor.engine.types import Cell
from shifting_manor.kb.facts import PIT_GHOST_CELL_FACTS, Constraint, Fact


def transport(
    facts: Iterable[Fact],
    constraints: Iterable[Constraint],
    mapping: dict[Cell, Cell],
) -> tuple[frozenset[Fact], frozenset[Constraint]]:
    """Move pit/ghost facts and pit/ghost constraints through a wing rotation.

    Treasure facts, visited rooms and globals are deliberately untouched:
    rooms, the treasure and the agent do not rotate.
    """
    moved_facts: set[Fact] = set()
    for item in facts:
        if item.name in PIT_GHOST_CELL_FACTS and item.cell is not None:
            moved_facts.add(Fact(item.name, mapping.get(item.cell, item.cell), item.value))
        else:
            moved_facts.add(item)
    moved_constraints: set[Constraint] = set()
    for con in constraints:
        if con.kind in ("PIT", "GHOST"):
            moved_constraints.add(
                Constraint(con.kind, frozenset(mapping.get(c, c) for c in con.cells))
            )
        else:
            moved_constraints.add(con)
    return frozenset(moved_facts), frozenset(moved_constraints)
