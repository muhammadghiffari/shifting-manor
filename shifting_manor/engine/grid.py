"""Grid geometry: neighbours, wings, rotations. Pure functions, no pygame."""

from __future__ import annotations

from shifting_manor.engine.types import DIRS, Cell, Dir, Rot

# 6x6 wing ids: SW foyer = 0, SE = 1, NW = 2, NE = 3.
WING_CENTRES: dict[int, Cell] = {1: (4, 1), 2: (1, 4), 3: (4, 4)}
ROTATING_WINGS: tuple[int, ...] = (1, 2, 3)
FOYER_WING = 0


def cells(size: int) -> list[Cell]:
    return [(x, y) for y in range(size) for x in range(size)]


def in_bounds(cell: Cell, size: int) -> bool:
    x, y = cell
    return 0 <= x < size and 0 <= y < size


def step(cell: Cell, direction: Dir) -> Cell:
    dx, dy = DIRS[direction]
    return (cell[0] + dx, cell[1] + dy)


def neighbours(cell: Cell, size: int) -> list[Cell]:
    return [step(cell, d) for d in DIRS if in_bounds(step(cell, d), size)]


def manhattan(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def line_cells(start: Cell, direction: Dir, size: int) -> list[Cell]:
    """Cells strictly ahead of start up to the wall (for the charm)."""
    out: list[Cell] = []
    cur = step(start, direction)
    while in_bounds(cur, size):
        out.append(cur)
        cur = step(cur, direction)
    return out


def wing_of(cell: Cell, size: int) -> int:
    if size != 6:
        return FOYER_WING
    x, y = cell
    return {(0, 0): 0, (1, 0): 1, (0, 1): 2, (1, 1): 3}[(x // 3, y // 3)]


def wing_cells(wing: int, size: int) -> list[Cell]:
    if size != 6:
        return [] if wing else cells(size)
    return [c for c in cells(size) if wing_of(c, size) == wing]


def wing_map(size: int) -> dict[Cell, int]:
    return {c: wing_of(c, size) for c in cells(size)}


def rotate_cell(cell: Cell, wing: int, direction: Rot) -> Cell:
    """Rotate one cell of a wing about the wing centre (AGENT.md 3.1)."""
    cx, cy = WING_CENTRES[wing]
    dx, dy = cell[0] - cx, cell[1] - cy
    if direction == "cw":
        return (cx + dy, cy - dx)
    return (cx - dy, cy + dx)


def rotation_mapping(wing: int, direction: Rot, size: int) -> dict[Cell, Cell]:
    if size != 6 or wing not in WING_CENTRES:
        return {}
    return {c: rotate_cell(c, wing, direction) for c in wing_cells(wing, size)}


def is_4_adjacent(a: Cell, b: Cell) -> bool:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
