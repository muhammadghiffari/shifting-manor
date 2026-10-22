"""One stored trace per turn for the Watch AI scene (no pygame here).

The trace is built once from a real agent playing a real game. The UI only
reads it: it must never re-run the agent or re-derive a belief per frame.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from shifting_manor.agents import make_agent
from shifting_manor.agents.kb_agent import GambleCandidate, GambleDecision
from shifting_manor.engine.game import Game
from shifting_manor.engine.types import Cell, GameInfo, Percepts, ShiftApplied
from shifting_manor.kb.facts import Constraint, Fact, Firing, fact_sort_key

WATCH_AGENTS = ("b3", "b2", "b2b")


@dataclass(frozen=True)
class Belief:
    cell: Cell
    label: str
    pit_risk: float
    ghost_risk: float
    risk: float
    stale: bool = False


@dataclass(frozen=True)
class ShiftInfo:
    wing: int
    direction: str
    mapping: tuple[tuple[Cell, Cell], ...]
    shift_index: int
    before: tuple[Belief, ...] = ()

    def target(self, cell: Cell) -> Cell:
        for old, new in self.mapping:
            if old == cell:
                return new
        return cell


@dataclass(frozen=True)
class StepTrace:
    index: int
    turn: int
    position: Cell
    oil: int
    percepts: Percepts
    firings: tuple[Firing, ...]
    all_firings: tuple[Firing, ...]
    beliefs: tuple[Belief, ...]
    facts: tuple[Fact, ...]
    gamble_candidates: tuple[GambleCandidate, ...]
    gamble: GambleDecision | None
    action: Any
    thought: str
    events: tuple[Any, ...]
    visited: frozenset[Cell]
    after_position: Cell
    shift: ShiftInfo | None
    provenance: dict[Fact, Firing]
    constraint_provenance: dict[Constraint, Firing]

    @property
    def belief_by_cell(self) -> dict[Cell, Belief]:
        return {b.cell: b for b in self.beliefs}


@dataclass(frozen=True)
class ProofNode:
    id: int
    label: str
    detail: str
    cells: tuple[Cell, ...]
    children: tuple[ProofNode, ...]
    leaf: bool = False


@dataclass(frozen=True)
class LogRow:
    step_index: int
    turn: int
    firing: Firing
    text: str
    cells: tuple[Cell, ...]
    new: bool


@dataclass(frozen=True)
class TraceStore:
    mode: str
    seed: str
    agent: str
    info: GameInfo
    steps: tuple[StepTrace, ...]
    outcome: str
    score: int
    rule_counts_by_step: tuple[dict[str, int], ...]
    rule_last_by_step: tuple[dict[str, Firing], ...]

    @property
    def size(self) -> int:
        return self.info.size

    @property
    def entrance(self) -> Cell:
        return self.info.entrance

    def log_rows(self) -> list[LogRow]:
        rows: list[LogRow] = []
        for step in self.steps:
            for firing in step.all_firings:
                rows.append(
                    LogRow(
                        step_index=step.index,
                        turn=firing.turn,
                        firing=firing,
                        text=format_firing(firing),
                        cells=firing_cells(firing),
                        new=not firing.rederived,
                    )
                )
        return rows

    def proof(self, step_index: int, item: Fact | Firing) -> ProofNode:
        step = self.steps[max(0, min(step_index, len(self.steps) - 1))]
        counter = _Counter()
        if isinstance(item, Firing):
            return _firing_node(item, step, counter, set())
        return _item_node(item, step, counter, set())

    def rule_stats(self, step_index: int) -> tuple[dict[str, int], dict[str, Firing]]:
        i = max(0, min(step_index, len(self.steps) - 1))
        return dict(self.rule_counts_by_step[i]), dict(self.rule_last_by_step[i])


def build_trace(
    mode: str,
    seed: str,
    agent_name: str = "b3",
    *,
    max_steps: int = 500,
) -> TraceStore:
    """Play one game with the real agent and freeze every decision."""
    if agent_name not in WATCH_AGENTS:
        raise ValueError(f"watch agent must be one of {WATCH_AGENTS}")
    game = Game(mode, seed)
    agent = make_agent(agent_name, game.info())
    percepts = game.observe()
    events: list[Any] = []
    visited: set[Cell] = {game.state.agent}
    steps: list[StepTrace] = []
    shift_index = 0
    steps_taken = 0

    while not game.state.done and steps_taken < max_steps:
        action = agent.act(percepts, events)
        kb = getattr(agent, "kb", None)
        model = getattr(agent, "model", None)
        before = steps[-1].beliefs if steps else ()
        shift: ShiftInfo | None = None
        for event in events:
            if isinstance(event, ShiftApplied):
                shift_index += 1
                shift = ShiftInfo(
                    wing=event.wing,
                    direction=event.direction,
                    mapping=tuple(sorted(event.mapping.items())),
                    shift_index=shift_index,
                    before=before,
                )
        labels = kb.belief_labels() if kb is not None else {}
        beliefs = tuple(
            Belief(
                cell=(x, y),
                label=labels.get((x, y), "unknown"),
                pit_risk=model.pit_risk.get((x, y), 0.0) if model is not None else 0.0,
                ghost_risk=model.ghost_risk.get((x, y), 0.0) if model is not None else 0.0,
                risk=model.risk((x, y)) if model is not None else 0.0,
                stale=bool(shift and (x, y) in {new for _, new in shift.mapping}),
            )
            for x in range(game.info().size)
            for y in range(game.info().size)
        )
        step = StepTrace(
            index=len(steps),
            turn=len(steps),
            position=game.state.agent,
            oil=game.state.oil,
            percepts=percepts,
            firings=tuple(kb.firings) if kb is not None else (),
            all_firings=tuple(kb.all_firings) if kb is not None else (),
            beliefs=beliefs,
            facts=tuple(sorted(kb.facts, key=fact_sort_key)) if kb is not None else (),
            gamble_candidates=tuple(getattr(agent, "gamble_candidates", ())),
            gamble=getattr(agent, "last_gamble", None),
            action=action,
            thought=agent.explain().thought,
            events=(),
            visited=frozenset(visited),
            after_position=game.state.agent,
            shift=shift,
            provenance=dict(kb.provenance) if kb is not None else {},
            constraint_provenance=dict(kb.constraint_provenance) if kb is not None else {},
        )
        result = game.step(action)
        visited.add(game.state.agent)
        steps.append(
            StepTrace(
                index=step.index,
                turn=step.turn,
                position=step.position,
                oil=step.oil,
                percepts=step.percepts,
                firings=step.firings,
                all_firings=step.all_firings,
                beliefs=step.beliefs,
                facts=step.facts,
                gamble_candidates=step.gamble_candidates,
                gamble=step.gamble,
                action=step.action,
                thought=step.thought,
                events=tuple(result.events),
                visited=frozenset(visited),
                after_position=game.state.agent,
                shift=step.shift,
                provenance=step.provenance,
                constraint_provenance=step.constraint_provenance,
            )
        )
        percepts = result.percepts
        events = list(result.events)
        steps_taken += 1

    if not game.state.done:
        game.state.done = True
        game.state.outcome = "stalled"

    counts: list[dict[str, int]] = []
    lasts: list[dict[str, Firing]] = []
    count: Counter[str] = Counter()
    last: dict[str, Firing] = {}
    for step in steps:
        for firing in step.firings:
            count[firing.rule_id] += 1
            last[firing.rule_id] = firing
        counts.append(dict(count))
        lasts.append(dict(last))

    return TraceStore(
        mode=mode,
        seed=seed,
        agent=agent_name,
        info=game.info(),
        steps=tuple(steps),
        outcome=game.state.outcome or "stalled",
        score=game.score(),
        rule_counts_by_step=tuple(counts),
        rule_last_by_step=tuple(lasts),
    )


# -- formatting shared by the log and proof panels ---------------------------
def format_item(item: object) -> str:
    if isinstance(item, Fact):
        if item.cell is not None:
            return f"{item.name}({item.cell[0]},{item.cell[1]})"
        if item.value is not None:
            return f"{item.name}={item.value!r}"
        return item.name
    if isinstance(item, Constraint):
        cells = ",".join(f"({x},{y})" for x, y in sorted(item.cells))
        return f"{item.kind}{{{cells}}}"
    return repr(item)


def format_firing(firing: Firing) -> str:
    if firing.rule_id == "R16" and firing.note:
        return firing.note
    premises = ", ".join(format_item(p) for p in firing.premises)
    conclusions = ", ".join(format_item(c) for c in firing.conclusions)
    return f"{firing.rule_id} {premises} => {conclusions}"


def firing_cells(firing: Firing) -> tuple[Cell, ...]:
    cells: set[Cell] = set()

    def add(item: object) -> None:
        if isinstance(item, Fact) and item.cell is not None:
            cells.add(item.cell)
        elif isinstance(item, Constraint):
            cells.update(item.cells)

    for premise in firing.premises:
        add(premise)
    for conclusion in firing.conclusions:
        add(conclusion)
    return tuple(sorted(cells))


class _Counter:
    def __init__(self) -> None:
        self.value = 0

    def next(self) -> int:
        self.value += 1
        return self.value


def _rule_detail(rule_id: str, turn: int, note: str = "", shift_index: int = 0) -> str:
    if rule_id in ("PERCEPT", "GIVEN"):
        return f"{rule_id.lower()} at turn {turn}"
    if rule_id == "R16":
        return f"R16 shift #{shift_index} at turn {turn}"
    from shifting_manor.kb.rules import RULE_BY_ID

    rule = RULE_BY_ID.get(rule_id)
    text = rule.description if rule is not None else rule_id
    return f"{rule_id} at turn {turn} · {text}"


def _item_node(
    item: Fact | Constraint,
    step: StepTrace,
    counter: _Counter,
    seen: set[object],
) -> ProofNode:
    node_id = counter.next()
    label = format_item(item)
    cells: tuple[Cell, ...] = ()
    if isinstance(item, Fact) and item.cell is not None:
        cells = (item.cell,)
    elif isinstance(item, Constraint):
        cells = tuple(sorted(item.cells))
    if item in seen:
        return ProofNode(node_id, label, "cycle", cells, (), True)
    seen = {*seen, item}
    firing = (
        step.provenance.get(item)
        if isinstance(item, Fact)
        else step.constraint_provenance.get(item)
    )
    if firing is None:
        return ProofNode(node_id, label, "assumption / not derived", cells, (), True)
    children = tuple(_item_node(p, step, counter, seen) for p in firing.premises)
    return ProofNode(
        node_id,
        label,
        _rule_detail(firing.rule_id, firing.turn, firing.note, firing.shift_index),
        cells,
        children,
        firing.rule_id in ("PERCEPT", "GIVEN") or not children,
    )


def _firing_node(
    firing: Firing,
    step: StepTrace,
    counter: _Counter,
    seen: set[object],
) -> ProofNode:
    node_id = counter.next()
    label = format_firing(firing)
    cells = firing_cells(firing)
    if firing.rule_id == "R16":
        return ProofNode(
            node_id,
            label,
            _rule_detail("R16", firing.turn, firing.note, firing.shift_index),
            cells,
            (),
            True,
        )
    children = tuple(_item_node(p, step, counter, seen) for p in firing.premises)
    return ProofNode(
        node_id,
        label,
        _rule_detail(firing.rule_id, firing.turn, firing.note, firing.shift_index),
        cells,
        children,
        firing.rule_id in ("PERCEPT", "GIVEN") or not children,
    )
