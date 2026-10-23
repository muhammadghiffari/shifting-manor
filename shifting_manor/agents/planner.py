"""BFS/A* helpers. A* uses risk-weighted edge cost (AGENT.md 5, M3)."""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass

from shifting_manor.engine.grid import manhattan, neighbours
from shifting_manor.engine.types import Cell
from shifting_manor.kb.base import KnowledgeBase


@dataclass(frozen=True)
class Route:
    cells: list[Cell]
    cost: float
    steps: int

    @property
    def first_step(self) -> Cell | None:
        return self.cells[1] if len(self.cells) > 1 else None


def kb_risk(kb: KnowledgeBase, cell: Cell) -> float:
    """M2 approximation; M3 replaces this with exact enumeration."""
    if kb.has("Pit", cell) or kb.has("Ghost", cell) or kb.has("Unsafe", cell):
        return 1.0
    if kb.has("Safe", cell) or (kb.has("NoPit", cell) and kb.has("NoGhost", cell)):
        return 0.0
    return 0.5


def astar(
    start: Cell,
    goals: set[Cell] | frozenset[Cell],
    size: int,
    *,
    risk_of,
    blocked: set[Cell] | frozenset[Cell] = frozenset(),
    avoid: set[Cell] | frozenset[Cell] = frozenset(),
    avoid_penalty: float = 0.0,
    lambda_: float = 1.0,
) -> Route | None:
    """Risk-weighted A*; heuristic = Manhattan distance to the nearest goal."""
    if not goals:
        return None
    if start in goals:
        return Route([start], 0.0, 0)

    def heuristic(cell: Cell) -> int:
        return min(manhattan(cell, g) for g in goals)

    counter = 0
    frontier: list[tuple[float, float, int, Cell, tuple[Cell, ...]]] = [
        (heuristic(start), 0.0, counter, start, (start,))
    ]
    best: dict[Cell, float] = {start: 0.0}
    while frontier:
        _f, g, _, cell, path = heapq.heappop(frontier)
        if cell in goals:
            return Route(list(path), g, len(path) - 1)
        if g > best.get(cell, math.inf):
            continue
        for nxt in neighbours(cell, size):
            if nxt in blocked:
                continue
            risk = min(max(risk_of(nxt), 0.0), 0.999999)
            if risk >= 1.0:
                continue
            edge = 1.0 + lambda_ * (-math.log(1.0 - risk))
            if nxt in avoid:
                edge += avoid_penalty
            new_g = g + edge
            if new_g >= best.get(nxt, math.inf):
                continue
            best[nxt] = new_g
            counter += 1
            heapq.heappush(frontier, (new_g + heuristic(nxt), new_g, counter, nxt, (*path, nxt)))
    return None


def safe_route(kb: KnowledgeBase, start: Cell, goal: Cell) -> Route | None:
    safe = kb.cell_set("Safe") | {start}
    size = kb.info.size
    blocked = {c for c in _all_cells(size) if c not in safe}
    return astar(start, {goal}, size, risk_of=lambda c: 0.0, blocked=blocked)


# Risk weight for the survival term of A* edge costs: 1.0 + RISK_LAMBDA * -log(1-risk).
# -log(1-risk) ~ risk for small risk, so lambda=1000 makes routing price death at
# the same rate as the -1000 * risk term in expected_utility; a zero-risk detour
# then always beats a risky shortcut to the same room (tools/audit.py found both).
RISK_LAMBDA = 1000.0


def cautious_route(
    kb: KnowledgeBase,
    start: Cell,
    goal: Cell,
    *,
    risk_of=None,
    avoid: set[Cell] | frozenset[Cell] = frozenset(),
    avoid_penalty: float = 0.0,
) -> Route | None:
    blocked = kb.cell_set("Unsafe") | kb.cell_set("Pit") | kb.cell_set("Ghost")
    return astar(
        start,
        {goal},
        kb.info.size,
        risk_of=risk_of or (lambda c: kb_risk(kb, c)),
        blocked=blocked,
        avoid=avoid,
        avoid_penalty=avoid_penalty,
        lambda_=RISK_LAMBDA,
    )


def expected_utility(risk: float, path_cost: int, unknown_neighbours: int) -> float:
    """R22 gamble score from ALGORITHMS.md 4.

    `risk` is the death probability of the whole route: the product of step
    survival probabilities (1 - risk(c)) over every cell entered en route,
    target included — a safe detour beats a riskier shortcut even when both
    end on cells with the same posterior risk.
    """
    return -1000.0 * risk - path_cost + 0.5 * unknown_neighbours


def _all_cells(size: int) -> list[Cell]:
    return [(x, y) for y in range(size) for x in range(size)]
