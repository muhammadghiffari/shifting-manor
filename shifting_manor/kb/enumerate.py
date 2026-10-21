"""Exact model enumeration over frontier cells (AGENT.md 5, ALGORITHMS.md 3)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import combinations

from shifting_manor.engine.types import Cell
from shifting_manor.kb.base import KnowledgeBase

MAX_FRONTIER = 14


@dataclass
class Model:
    pit_risk: dict[Cell, float]
    ghost_risk: dict[Cell, float]
    entailed_pit: frozenset[Cell]
    entailed_nopit: frozenset[Cell]
    entailed_ghost: frozenset[Cell]
    entailed_noghost: frozenset[Cell]
    worlds: int
    fallback: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def risk(self, cell: Cell) -> float:
        pit = self.pit_risk.get(cell, 0.0)
        ghost = self.ghost_risk.get(cell, 0.0)
        return min(1.0, 1.0 - (1.0 - pit) * (1.0 - ghost))

    def entailed(self, item) -> bool:
        from shifting_manor.kb.facts import Fact

        if not isinstance(item, Fact) or item.cell is None:
            return True
        if item.name == "Pit":
            return item.cell in self.entailed_pit
        if item.name == "NoPit":
            return item.cell in self.entailed_nopit
        if item.name == "Ghost":
            return item.cell in self.entailed_ghost
        if item.name == "NoGhost":
            return item.cell in self.entailed_noghost
        return True


def _all_cells(size: int) -> list[Cell]:
    return [(x, y) for y in range(size) for x in range(size)]


def enumerate_models(kb: KnowledgeBase) -> Model:
    size = kb.info.size
    cells = _all_cells(size)
    warnings: list[str] = []

    # Visited is historical: a shift may since have moved a pit into that room.
    # The durable NoPit/NoGhost conclusions are transported instead. A known
    # ghost's room is also pit-free because the generator never stacks them.
    no_pit = kb.cell_set("NoPit") | kb.cell_set("Ghost")
    known_pits = kb.cell_set("Pit")
    pit_constraints = [con.cells for con in kb.constraints if con.kind == "PIT"]
    frontier_pits = sorted(
        (set().union(*pit_constraints) if pit_constraints else set()) - no_pit - known_pits
    )
    pits_left = kb.info.pit_total - len(known_pits)
    unknown_rest = set(cells) - no_pit - known_pits - set(frontier_pits)
    u_count = len(unknown_rest)

    fallback = False
    if len(frontier_pits) > MAX_FRONTIER:
        fallback = True
        warnings.append(
            f"frontier has {len(frontier_pits)} cells (> {MAX_FRONTIER}); "
            "using independence approximation"
        )
    elif pits_left < 0:
        fallback = True
        warnings.append("pit count is inconsistent; using independence approximation")

    if not fallback:
        worlds: list[tuple[frozenset[Cell], int]] = []
        for k in range(min(len(frontier_pits), max(pits_left, 0)) + 1):
            if pits_left - k > u_count:
                continue
            weight = math.comb(u_count, pits_left - k) if pits_left - k >= 0 else 0
            if weight == 0:
                continue
            for combo in combinations(frontier_pits, k):
                chosen = frozenset(combo)
                if all(any(c in chosen or c in known_pits for c in con) for con in pit_constraints):
                    worlds.append((chosen, weight))
        total = sum(w for _, w in worlds)
        if total == 0:
            fallback = True
            warnings.append("no consistent pit worlds; using independence approximation")
        else:
            pit_risk = {c: 0.0 for c in cells}
            for c in known_pits:
                pit_risk[c] = 1.0
            for c in no_pit:
                pit_risk[c] = 0.0
            for c in frontier_pits:
                hit = sum(w for chosen, w in worlds if c in chosen)
                pit_risk[c] = hit / total
            hidden_pits = sum(w * (pits_left - len(chosen)) for chosen, w in worlds) / total
            per_unknown = hidden_pits / u_count if u_count else 0.0
            for c in unknown_rest:
                pit_risk[c] = per_unknown
            entailed_pit = frozenset(known_pits | {c for c in frontier_pits if pit_risk[c] == 1.0})
            entailed_nopit = frozenset(no_pit | {c for c in frontier_pits if pit_risk[c] == 0.0})
            return _finish(
                kb,
                cells,
                pit_risk,
                entailed_pit,
                entailed_nopit,
                len(worlds),
                fallback=False,
                warnings=warnings,
            )

    # -- independence fallback -------------------------------------------
    pit_risk = {c: 0.0 for c in cells}
    for c in no_pit:
        pit_risk[c] = 0.0
    for c in known_pits:
        pit_risk[c] = 1.0
    unknown = [c for c in cells if c not in no_pit and c not in known_pits]
    base = pits_left / len(unknown) if unknown else 0.0
    for c in unknown:
        pit_risk[c] = max(0.0, min(1.0, base))
    for con in pit_constraints:
        if any(c in known_pits for c in con):
            continue
        candidates = [c for c in con if c not in no_pit and c not in known_pits]
        if len(candidates) == 1:
            pit_risk[candidates[0]] = 1.0
        elif candidates:
            share = 1.0 / len(candidates)
            for c in candidates:
                pit_risk[c] = max(pit_risk[c], share)
    entailed_pit = frozenset(known_pits | {c for c in cells if pit_risk[c] == 1.0})
    entailed_nopit = frozenset(no_pit | {c for c in cells if pit_risk[c] == 0.0})
    return _finish(
        kb,
        cells,
        pit_risk,
        entailed_pit,
        entailed_nopit,
        0,
        fallback=True,
        warnings=warnings,
    )


def _finish(
    kb: KnowledgeBase,
    cells: list[Cell],
    pit_risk: dict[Cell, float],
    entailed_pit: frozenset[Cell],
    entailed_nopit: frozenset[Cell],
    worlds: int,
    *,
    fallback: bool,
    warnings: list[str],
) -> Model:
    no_ghost = kb.cell_set("NoGhost") | kb.cell_set("Pit")
    known_ghost = kb.cell_set("Ghost")
    ghost_constraints = [con.cells for con in kb.constraints if con.kind == "GHOST"]

    if not kb.value("GhostAlive", False):
        ghost_risk = {c: 0.0 for c in cells}
        entailed_ghost: frozenset[Cell] = frozenset()
        entailed_noghost = frozenset(cells)
    elif known_ghost:
        g = next(iter(known_ghost))
        ghost_risk = {c: (1.0 if c == g else 0.0) for c in cells}
        entailed_ghost = frozenset({g})
        entailed_noghost = frozenset(c for c in cells if c != g)
    else:
        if ghost_constraints:
            candidates = sorted(
                {
                    c
                    for con in ghost_constraints
                    for c in con
                    if c not in no_ghost and all(c in other for other in ghost_constraints)
                }
            )
        else:
            candidates = [c for c in cells if c not in no_ghost]
        if not candidates:
            candidates = [c for c in cells if c not in no_ghost]
            warnings.append("no consistent ghost worlds; ghost is uniformly unknown")
        p = 1.0 / len(candidates) if candidates else 0.0
        ghost_risk = {c: (p if c in candidates else 0.0) for c in cells}
        entailed_ghost = frozenset(candidates) if len(candidates) == 1 else frozenset()
        entailed_noghost = frozenset(c for c in cells if c not in candidates) | no_ghost

    return Model(
        pit_risk=pit_risk,
        ghost_risk=ghost_risk,
        entailed_pit=entailed_pit,
        entailed_nopit=entailed_nopit,
        entailed_ghost=entailed_ghost,
        entailed_noghost=entailed_noghost,
        worlds=worlds,
        fallback=fallback,
        warnings=tuple(warnings),
    )


def cross_check(kb: KnowledgeBase, model: Model) -> list[object]:
    """Return KB facts the enumeration does not entail (empty means sound here)."""
    bad = []
    for item in kb.facts:
        if item.name in ("Pit", "NoPit", "Ghost", "NoGhost") and not model.entailed(item):
            bad.append(item)
    return bad
