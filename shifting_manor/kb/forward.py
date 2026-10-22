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
    note: str = ""


@dataclass(frozen=True)
class Rule:
    id: str
    description: str
    matches: Callable[[KnowledgeBase], Iterable[Binding]] | None = None
    conclusions: Callable[[KnowledgeBase, Binding], Iterable[Fact | Constraint]] | None = None
    event_driven: bool = False


def forward_chain(kb: KnowledgeBase, rules: Iterable[Rule], turn: int) -> list[Firing]:
    """Fire rules in fixed priority order until no new conclusion appears."""
    firings: list[Firing] = []
    rule_list = list(rules)
    for _ in range(MAX_ITERATIONS):
        changed = False
        for rule in rule_list:
            if rule.event_driven:
                continue  # R16 transport is logged by KnowledgeBase.apply_shift
            assert rule.matches is not None and rule.conclusions is not None
            for binding in list(rule.matches(kb)):
                conclusions: list[Fact | Constraint] = []
                for item in rule.conclusions(kb, binding):
                    if kb.add(item):
                        conclusions.append(item)
                if conclusions:
                    firings.append(
                        Firing(
                            rule.id,
                            tuple(binding.premises),
                            tuple(conclusions),
                            turn,
                            note=binding.note,
                        )
                    )
                    changed = True
        if not changed:
            return firings
    raise AssertionError("forward chaining did not reach a fixpoint")
