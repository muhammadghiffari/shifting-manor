"""The Shift: deterministic wing rotation with telegraph-time validation."""

from __future__ import annotations

import random
from dataclasses import dataclass

from shifting_manor.engine.generator import hazard_free_path
from shifting_manor.engine.grid import ROTATING_WINGS, rotation_mapping, wing_of
from shifting_manor.engine.types import Cell, Rot


@dataclass(frozen=True)
class ShiftPlan:
    wing: int
    direction: Rot
    mapping: dict[Cell, Cell]


@dataclass(frozen=True)
class ShiftRequest:
    wing: int
    direction: Rot


def request_shift(rng: random.Random, size: int) -> ShiftRequest | None:
    if size != 6:
        return None
    wing = rng.choice(ROTATING_WINGS)
    direction: Rot = rng.choice(("cw", "ccw"))
    return ShiftRequest(wing, direction)


def hazards_after(
    pits: frozenset[Cell], ghost: Cell | None, mapping: dict[Cell, Cell]
) -> tuple[frozenset[Cell], Cell | None]:
    new_pits = frozenset(mapping.get(p, p) for p in pits)
    new_ghost = None if ghost is None else mapping.get(ghost, ghost)
    return new_pits, new_ghost


def valid_after(
    *,
    size: int,
    pits: frozenset[Cell],
    ghost: Cell | None,
    treasure: Cell,
    entrance: Cell,
    agent: Cell,
    has_treasure: bool,
) -> bool:
    """No hazard on the treasure, and the required hazard-free path survives."""
    if treasure in pits or treasure == ghost:
        return False
    if has_treasure:
        return hazard_free_path(agent, entrance, size, pits, ghost)
    return hazard_free_path(entrance, treasure, size, pits, ghost)


def plan_request(
    request: ShiftRequest,
    *,
    size: int,
    pits: frozenset[Cell],
    ghost: Cell | None,
    treasure: Cell,
    entrance: Cell,
    agent: Cell,
    has_treasure: bool,
) -> ShiftPlan | None:
    for candidate in (request.direction, "ccw" if request.direction == "cw" else "cw"):
        mapping = rotation_mapping(request.wing, candidate, size)
        new_pits, new_ghost = hazards_after(pits, ghost, mapping)
        if valid_after(
            size=size,
            pits=new_pits,
            ghost=new_ghost,
            treasure=treasure,
            entrance=entrance,
            agent=agent,
            has_treasure=has_treasure,
        ):
            return ShiftPlan(request.wing, candidate, mapping)
    return None


def choose_shift(
    rng: random.Random,
    *,
    size: int,
    pits: frozenset[Cell],
    ghost: Cell | None,
    treasure: Cell,
    entrance: Cell,
    agent: Cell,
    has_treasure: bool,
) -> ShiftPlan | None:
    """Pick wing+direction from the seeded rng; try cw then ccw, else skip."""
    request = request_shift(rng, size)
    if request is None:
        return None
    return plan_request(
        request,
        size=size,
        pits=pits,
        ghost=ghost,
        treasure=treasure,
        entrance=entrance,
        agent=agent,
        has_treasure=has_treasure,
    )


def agent_inside_wing(agent: Cell, wing: int, size: int) -> bool:
    return wing_of(agent, size) == wing
