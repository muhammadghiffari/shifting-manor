"""Real-time autonomous AI controller & shadow hint engine for live Play mode.

Drives ANY real agent (B0..B5) live turn-by-turn against a live ``Game``,
captures real-time beliefs, planned routes, forward-chaining firings, live
rule counts, and on-demand Why? proof trees — and also supports seamless
manual-to-AI takeover and zero-cheating AI hints during human play.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from shifting_manor.agents import make_agent
from shifting_manor.agents.kb_agent import GambleCandidate, KBAgent
from shifting_manor.engine.types import (
    Action,
    CastCharm,
    Cell,
    GameInfo,
    Leave,
    Move,
    Percepts,
    ShiftApplied,
)
from shifting_manor.kb.facts import Fact, Firing, fact_sort_key
from shifting_manor.trace import (
    Belief,
    ProofNode,
    StepTrace,
    _Counter,
    _firing_node,
    _item_node,
    format_firing,
)

LIVE_AGENTS: tuple[str, ...] = ("b3", "b5", "b2b", "b2", "b1", "b0", "b4")


@dataclass(frozen=True)
class LiveLogEntry:
    turn: int
    firing: Firing
    text: str


@dataclass(frozen=True)
class HintInfo:
    action: Action
    summary: str
    detail: str
    target_cell: Cell | None


def describe_action(action: Action) -> str:
    if isinstance(action, Move):
        names = {"N": "North (Up)", "E": "East (Right)", "S": "South (Down)", "W": "West (Left)"}
        return f"Move {names.get(action.dir, action.dir)}"
    if isinstance(action, CastCharm):
        names = {"N": "North", "E": "East", "S": "South", "W": "West"}
        return f"Cast Charm {names.get(action.dir, action.dir)}"
    if isinstance(action, Leave):
        return "Leave Manor at Entrance (0,0)"
    return repr(action)


class LiveAIController:
    """Drives a real agent live on an active Game, or shadows a human player."""

    def __init__(self, info: GameInfo, agent_name: str = "b3") -> None:
        self.info = info
        self.agent_name = agent_name
        self.agent = make_agent(agent_name, info)
        self.turn = 0
        self.thought = f"{agent_name.upper()} ready — observing Entrance (0,0)."
        self.last_action: Action | None = None
        self.beliefs: dict[Cell, Belief] = {}
        self.facts: tuple[Fact, ...] = ()
        self.route: tuple[Cell, ...] = ()
        self.gamble_candidates: tuple[GambleCandidate, ...] = ()
        self.log: list[LiveLogEntry] = []
        self.rule_counts: Counter[str] = Counter()
        self.rule_last: dict[str, Firing] = {}
        self.total_firings = 0
        self._last_provenance: dict[Any, Firing] = {}
        self._last_constraint_prov: dict[Any, Firing] = {}
        self._last_position: Cell = info.entrance
        self._last_oil: int = info.oil
        self._last_percepts: Percepts = Percepts()
        self._last_visited: frozenset[Cell] = frozenset({info.entrance})
        self._last_shift_cells: set[Cell] = set()

    def decide_next(
        self, percepts: Percepts, events: list[Any], *, position: Cell, oil: int
    ) -> Action:
        """Ask the real agent for its next live action and snapshot its KB state."""
        shifted: set[Cell] = set()
        for ev in events:
            if isinstance(ev, ShiftApplied):
                shifted.update(ev.mapping.values())
        self._last_shift_cells = shifted

        action = self.agent.act(percepts, events)
        self.last_action = action
        self._capture_state(percepts, position=position, oil=oil, action=action)
        self.turn += 1
        return action

    def _capture_state(
        self,
        percepts: Percepts,
        *,
        position: Cell,
        oil: int,
        action: Action | None,
    ) -> None:
        kb = getattr(self.agent, "kb", None)
        model = getattr(self.agent, "model", None)
        exp = self.agent.explain()
        base_thought = exp.thought or ""
        act_str = describe_action(action) if action is not None else ""
        self.thought = (
            f"{act_str} — {base_thought}" if act_str and base_thought else (base_thought or act_str)
        )

        if kb is not None:
            labels = kb.belief_labels()
            pit_map = getattr(model, "pit_risk", {}) if model is not None else {}
            ghost_map = getattr(model, "ghost_risk", {}) if model is not None else {}
            self.beliefs = {
                (x, y): Belief(
                    cell=(x, y),
                    label=labels.get((x, y), "unknown"),
                    pit_risk=float(pit_map.get((x, y), 0.0)),
                    ghost_risk=float(ghost_map.get((x, y), 0.0)),
                    risk=float(model.risk((x, y))) if model is not None else 0.0,
                    stale=(x, y) in self._last_shift_cells,
                )
                for x in range(self.info.size)
                for y in range(self.info.size)
            }
            self.facts = tuple(sorted(kb.facts, key=fact_sort_key))
            self._last_provenance = dict(kb.provenance)
            self._last_constraint_prov = dict(kb.constraint_provenance)
            for firing in kb.firings:
                self.rule_counts[firing.rule_id] += 1
                self.rule_last[firing.rule_id] = firing
                self.total_firings += 1
                self.log.append(LiveLogEntry(self.turn, firing, format_firing(firing)))
            if len(self.log) > 400:
                self.log = self.log[-400:]
        else:
            self.beliefs = {}
            self.facts = ()
            self._last_provenance = {}
            self._last_constraint_prov = {}

        route_obj = getattr(self.agent, "last_route", None)
        self.route = tuple(route_obj.cells) if route_obj is not None else ()
        self.gamble_candidates = tuple(getattr(self.agent, "gamble_candidates", ()))
        self._last_position = position
        self._last_oil = oil
        self._last_percepts = percepts
        self._last_visited = self._last_visited | {position}

    def replay_prefix(
        self,
        prefix_history: list[tuple[Percepts, list[Any], Cell, int]],
    ) -> None:
        """Replay all prior turns (excluding the current un-acted turn).

        After calling this with ``history[:-1]``, the next call to
        ``decide_next(current_percepts, current_events, ...)`` produces the
        exact real action from the player's current position with zero desync.
        """
        self.agent = make_agent(self.agent_name, self.info)
        self.turn = 0
        self.log = []
        self.rule_counts = Counter()
        self.rule_last = {}
        self.total_firings = 0
        self._last_visited = frozenset({self.info.entrance})
        for percepts, events, pos, oil in prefix_history:
            self.decide_next(percepts, events, position=pos, oil=oil)

    def proof_for_cell(self, cell: Cell) -> ProofNode | None:
        priority = ("Safe", "Pit", "Ghost", "NoPit", "NoGhost", "NoTreasure", "Visited")
        fact = next(
            (f for name in priority for f in self.facts if f.name == name and f.cell == cell),
            None,
        )
        if fact is None:
            return None
        return _item_node(fact, self._as_step_trace(), _Counter(), set())

    def proof_for_firing(self, firing: Firing) -> ProofNode:
        return _firing_node(firing, self._as_step_trace(), _Counter(), set())

    def _as_step_trace(self) -> StepTrace:
        return StepTrace(
            index=max(0, self.turn - 1),
            turn=max(0, self.turn - 1),
            position=self._last_position,
            oil=self._last_oil,
            percepts=self._last_percepts,
            firings=(),
            all_firings=(),
            beliefs=tuple(self.beliefs.values()),
            facts=self.facts,
            gamble_candidates=self.gamble_candidates,
            gamble=None,
            action=self.last_action,
            thought=self.thought,
            events=(),
            visited=self._last_visited,
            after_position=self._last_position,
            shift=None,
            provenance=self._last_provenance,
            constraint_provenance=self._last_constraint_prov,
        )


def compute_human_hint(
    info: GameInfo,
    history: list[tuple[Percepts, list[Any], Cell, int]],
) -> tuple[HintInfo, LiveAIController]:
    """Compute a fair, zero-cheating B3 deduction hint from the human's history."""
    ctrl = LiveAIController(info, "b3")
    if not history:
        return (
            HintInfo(
                action=Move("E"),
                summary="Explore an adjacent room!",
                detail="No observations recorded yet.",
                target_cell=(1, 0),
            ),
            ctrl,
        )
    # Replay all turns including the current observation to get B3's exact recommendation
    ctrl.agent = KBAgent("b3")
    ctrl.agent.reset(info)
    action: Action = Move("E")
    for percepts, events, pos, oil in history:
        action = ctrl.decide_next(percepts, events, position=pos, oil=oil)
    target = ctrl.route[1] if len(ctrl.route) >= 2 else (ctrl.route[-1] if ctrl.route else None)
    if isinstance(action, Leave):
        summary = "Recommended: LEAVE MANOR [E] now!"
        target = info.entrance
    elif isinstance(action, CastCharm):
        summary = f"Recommended: CAST CHARM [C] toward {action.dir}!"
    else:
        summary = f"Recommended: {describe_action(action)}"
    detail = ctrl.agent.explain().thought or "Safe deduction from your observed senses."
    return HintInfo(action=action, summary=summary, detail=detail, target_cell=target), ctrl
