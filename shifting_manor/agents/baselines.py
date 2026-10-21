"""B0 random and B1 reactive baselines. Deliberately weak but never crash."""

from __future__ import annotations

import random
from collections.abc import Iterable

from shifting_manor.engine.grid import DIRS, in_bounds, neighbours, step
from shifting_manor.engine.types import (
    Action,
    CastCharm,
    Cell,
    Dir,
    Event,
    GameInfo,
    Leave,
    Move,
    Percepts,
)
from shifting_manor.kb.facts import Explanation


class RandomAgent:
    name = "b0"

    def __init__(self) -> None:
        self.info: GameInfo | None = None
        self.pos: Cell = (0, 0)
        self.has_treasure = False
        self.charm_available = True
        self.oil = 0
        self.rng = random.Random(0)
        self.last = Explanation(thought="Random legal move.")

    def reset(self, info: GameInfo) -> None:
        self.info = info
        self.pos = info.entrance
        self.has_treasure = False
        self.charm_available = True
        self.oil = info.oil
        self.rng = random.Random(f"{info.seed}:agent:random")

    def act(self, percepts: Percepts, events: Iterable[Event]) -> Action:
        self._absorb(events)
        if self.info is None:
            raise RuntimeError("reset() before act()")
        choices: list[Action] = []
        for d in DIRS:
            if in_bounds(step(self.pos, d), self.info.size):
                choices.append(Move(d))
        if self.charm_available:
            choices.extend(CastCharm(d) for d in DIRS)
        if self.pos == self.info.entrance and self.has_treasure:
            return Leave()
        return self.rng.choice(choices)

    def _absorb(self, events: Iterable[Event]) -> None:
        for event in events:
            name = type(event).__name__
            if name == "Moved":
                self.pos = event.cell  # type: ignore[attr-defined]
                self.oil -= 1
            elif name == "Bumped":
                pass
            elif name == "PickedUp":
                self.has_treasure = True
            elif name == "CharmCast":
                self.charm_available = False
                self.oil -= 1

    def explain(self) -> Explanation:
        return self.last


class ReactiveAgent(RandomAgent):
    name = "b1"

    def reset(self, info: GameInfo) -> None:
        super().reset(info)
        self.rng = random.Random(f"{info.seed}:agent:reactive")

    def act(self, percepts: Percepts, events: Iterable[Event]) -> Action:
        self._absorb(events)
        if self.info is None:
            raise RuntimeError("reset() before act()")
        if self.pos == self.info.entrance and self.has_treasure:
            return Leave()
        danger: set[Cell] = set()
        if percepts.breeze or percepts.chill:
            danger.update(neighbours(self.pos, self.info.size))
        candidates = [
            Move(d)
            for d in DIRS
            if in_bounds(step(self.pos, d), self.info.size) and step(self.pos, d) not in danger
        ]
        if not candidates:
            candidates = [Move(d) for d in DIRS if in_bounds(step(self.pos, d), self.info.size)]
        if self.oil <= 8 and self.pos != self.info.entrance:
            toward = self._toward(self.info.entrance)
            if toward is not None:
                return toward
        if percepts.glimmer and not self.has_treasure:
            # No memory of where the glimmer was, so just keep moving.
            pass
        move = self.rng.choice(candidates)
        self.last = Explanation(thought=f"Reactive move {move.dir}.")
        return move

    def _toward(self, target: Cell) -> Action | None:
        dx = target[0] - self.pos[0]
        dy = target[1] - self.pos[1]
        options: list[Dir] = []
        if dx:
            options.append("E" if dx > 0 else "W")
        if dy:
            options.append("N" if dy > 0 else "S")
        self.rng.shuffle(options)
        for d in options:
            if in_bounds(step(self.pos, d), self.info.size):
                return Move(d)
        return None
