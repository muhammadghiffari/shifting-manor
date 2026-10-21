"""Public data types shared by the engine, agents and UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Cell = tuple[int, int]
Dir = Literal["N", "E", "S", "W"]
Rot = Literal["cw", "ccw"]

DIRS: dict[Dir, Cell] = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}
DIR_ORDER: tuple[Dir, ...] = ("N", "E", "S", "W")


@dataclass(frozen=True)
class Move:
    dir: Dir


@dataclass(frozen=True)
class CastCharm:
    dir: Dir


@dataclass(frozen=True)
class Leave:
    pass


Action = Move | CastCharm | Leave


@dataclass(frozen=True)
class ShiftWarning:
    wing: int
    direction: Rot
    in_actions: int


@dataclass(frozen=True)
class Percepts:
    breeze: bool = False
    chill: bool = False
    glimmer: bool = False
    bump: bool = False
    scream: bool = False
    rumble: ShiftWarning | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "breeze": self.breeze,
            "chill": self.chill,
            "glimmer": self.glimmer,
            "bump": self.bump,
            "scream": self.scream,
            "rumble": self.rumble,
        }


@dataclass(frozen=True)
class GameInfo:
    size: int
    pit_total: int
    entrance: Cell
    shift_every: int | None
    oil: int
    wings: dict[Cell, int]
    foyer_wing: int
    rotating_wings: tuple[int, ...]
    seed: str = ""
    mode: str = "explorer"


@dataclass(frozen=True)
class Moved:
    cell: Cell


@dataclass(frozen=True)
class Bumped:
    dir: Dir


@dataclass(frozen=True)
class PickedUp:
    cell: Cell


@dataclass(frozen=True)
class CharmCast:
    dir: Dir


@dataclass(frozen=True)
class GhostBanished:
    cell: Cell


@dataclass(frozen=True)
class Died:
    cause: Literal["pit", "ghost"]


@dataclass(frozen=True)
class OilLow:
    oil: int


@dataclass(frozen=True)
class ShiftTelegraph:
    wing: int
    direction: Rot
    in_actions: int = 2


@dataclass(frozen=True)
class ShiftApplied:
    wing: int
    direction: Rot
    mapping: dict[Cell, Cell]


@dataclass(frozen=True)
class ShiftSkipped:
    wing: int
    reason: str


@dataclass(frozen=True)
class Escaped:
    with_treasure: bool


@dataclass(frozen=True)
class OilOut:
    pass


@dataclass(frozen=True)
class InvalidAction:
    reason: str


Event = (
    Moved
    | Bumped
    | PickedUp
    | CharmCast
    | GhostBanished
    | Died
    | OilLow
    | ShiftTelegraph
    | ShiftApplied
    | ShiftSkipped
    | Escaped
    | OilOut
    | InvalidAction
)


@dataclass(frozen=True)
class StepResult:
    percepts: Percepts
    events: list[Event] = field(default_factory=list)
    done: bool = False
