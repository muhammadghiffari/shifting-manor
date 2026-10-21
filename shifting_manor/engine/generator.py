"""Seeded map generation with validity retries."""

from __future__ import annotations

import random
from dataclasses import dataclass

from shifting_manor.engine.grid import cells, neighbours
from shifting_manor.engine.modes import Mode


@dataclass(frozen=True)
class GeneratedMap:
    pits: frozenset[tuple[int, int]]
    ghost: tuple[int, int]
    treasure: tuple[int, int]


def protected_cells(entrance: tuple[int, int], size: int) -> set[tuple[int, int]]:
    """Entrance plus its two in-board neighbours are hazard-free (AGENT.md 3)."""
    out = {entrance}
    x, y = entrance
    out.update(c for c in ((x + 1, y), (x, y + 1)) if 0 <= c[0] < size and 0 <= c[1] < size)
    return out


def hazard_free_path(
    start: tuple[int, int],
    goal: tuple[int, int],
    size: int,
    pits: frozenset[tuple[int, int]] | set[tuple[int, int]],
    ghost: tuple[int, int] | None,
) -> bool:
    """BFS that treats pit rooms and a live ghost room as walls."""
    blocked = set(pits)
    if ghost is not None:
        blocked.add(ghost)
    if start in blocked or goal in blocked:
        return False
    seen = {start}
    queue = [start]
    while queue:
        cur = queue.pop(0)
        if cur == goal:
            return True
        for nxt in neighbours(cur, size):
            if nxt not in seen and nxt not in blocked:
                seen.add(nxt)
                queue.append(nxt)
    return False


def generate(mode: Mode, seed: str) -> GeneratedMap:
    """Same seed -> same map. Rejection-samples until the PRD constraints hold."""
    rng = random.Random(f"{seed}:map")
    size = mode.size
    entrance = (0, 0)
    protected = protected_cells(entrance, size)
    candidates = [c for c in cells(size) if c not in protected]
    if len(candidates) < mode.pits + 2:
        raise ValueError(f"board too small for mode {mode.name}")

    for _attempt in range(10_000):
        pits = frozenset(rng.sample(candidates, mode.pits))
        rest = [c for c in candidates if c not in pits]
        ghost = rng.choice(rest)
        rest = [c for c in rest if c != ghost]
        treasure = rng.choice(rest)
        if hazard_free_path(entrance, treasure, size, pits, ghost):
            return GeneratedMap(pits, ghost, treasure)
    raise RuntimeError("map generation failed after 10000 attempts")
