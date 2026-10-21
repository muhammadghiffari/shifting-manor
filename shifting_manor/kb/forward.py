"""Forward chainer and the Rule object. Fixed priority order, finite fixpoint."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from shifting_manor.kb.facts import Constraint, Fact, Firing

if TYPE_CHECKING:
    from shifting_manor.kb.base import KnowledgeBase

MAX_ITERATIONS = 100


@dataclass(frozen=True)
class Binding:
    premises: tuple[object, ...]
    data: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class Rule:
    id: str
    description: str
    matches: Callable[[KnowledgeBase], Iterable[Binding]]
    conclusions: Callable[[KnowledgeBase, Binding], Iterable[Fact | Constraint]]


def forward_chain(kb: KnowledgeBase, rules: Iterable[Rule], turn: int) -> list[Firing]:
    """Fire rules in fixed priority order until no new conclusion appears."""
    firings: list[Firing] = []
    rule_list = list(rules)
    for _ in range(MAX_ITERATIONS):
        changed = False
        for rule in rule_list:
            if rule.id == "R16":
                continue  # event-driven transport, logged by KnowledgeBase
            for binding in list(rule.matches(kb)):
                conclusions: list[Fact | Constraint] = []
                for item in rule.conclusions(kb, binding):
                    if kb.add(item):
                        conclusions.append(item)
                if conclusions:
                    firings.append(
                        Firing(rule.id, tuple(binding.premises), tuple(conclusions), turn)
                    )
                    changed = True
        if not changed:
            return firings
    raise AssertionError("forward chaining did not reach a fixpoint")
