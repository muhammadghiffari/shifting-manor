"""Agent protocol and small shared helpers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from shifting_manor.engine.types import Action, Event, GameInfo, Percepts
from shifting_manor.kb.facts import Explanation


class Agent(Protocol):
    name: str

    def reset(self, info: GameInfo) -> None: ...

    def act(self, percepts: Percepts, events: Iterable[Event]) -> Action: ...

    def explain(self) -> Explanation: ...
