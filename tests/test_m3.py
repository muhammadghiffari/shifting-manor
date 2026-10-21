"""M3 tests: enumeration, A*, expected utility, agent properties, sim smoke."""

from __future__ import annotations

import json

import pytest

from shifting_manor.agents import make_agent
from shifting_manor.agents.planner import astar, expected_utility
from shifting_manor.engine.game import Game
from shifting_manor.engine.grid import rotation_mapping, step, wing_map
from shifting_manor.engine.types import GameInfo, Move, ShiftApplied
from shifting_manor.kb.base import KnowledgeBase
from shifting_manor.kb.enumerate import MAX_FRONTIER, cross_check, enumerate_models
from shifting_manor.kb.facts import Constraint, Fact
from shifting_manor.sim.runner import run_game, run_suite


def info(size: int = 6, pits: int = 5, oil: int = 70) -> GameInfo:
    return GameInfo(
        size=size,
        pit_total=pits,
        entrance=(0, 0),
        shift_every=8,
        oil=oil,
        wings=wing_map(size),
        foyer_wing=0,
        rotating_wings=(1, 2, 3) if size == 6 else (),
        seed="M3-TEST",
        mode="haunted",
    )


# -- enumeration -----------------------------------------------------------
def test_enumeration_weights_pit_total_exactly():
    kb = KnowledgeBase(info(size=4, pits=2))
    kb.set_global("GhostAlive", False)
    kb.add_base(Constraint("PIT", frozenset({(1, 1), (2, 1)})))

    model = enumerate_models(kb)

    # 29 of the 120 two-pit boards put at least one pit in the constraint.
    assert model.worlds == 3
    assert model.fallback is False
    assert model.pit_risk[(1, 1)] == pytest.approx(15 / 29)
    assert model.pit_risk[(2, 1)] == pytest.approx(15 / 29)
    # The second pit is less likely anywhere else than plain independence suggests.
    assert model.pit_risk[(0, 0)] == pytest.approx(2 / 29)


def test_enumeration_entails_the_last_candidate():
    kb = KnowledgeBase(info(size=4, pits=1))
    kb.set_global("GhostAlive", False)
    kb.add_base(Constraint("PIT", frozenset({(1, 1), (2, 1), (3, 1)})))
    kb.add_base(Fact("NoPit", (1, 1)))
    kb.add_base(Fact("NoPit", (2, 1)))

    model = enumerate_models(kb)

    assert model.pit_risk[(3, 1)] == 1.0
    assert model.pit_risk[(0, 0)] == 0.0
    assert (3, 1) in model.entailed_pit


def test_enumeration_falls_back_above_frontier_cap():
    kb = KnowledgeBase(info(size=6, pits=5))
    kb.set_global("GhostAlive", False)
    cells = [(x, y) for y in range(3) for x in range(6)]
    for cell in cells[: MAX_FRONTIER + 1]:
        kb.add_base(Constraint("PIT", frozenset({cell})))

    model = enumerate_models(kb)

    assert model.fallback is True
    assert any(str(MAX_FRONTIER) in warning for warning in model.warnings)


# -- planning --------------------------------------------------------------
def test_astar_trades_oil_against_risk():
    def risk(cell):
        return 0.9 if cell == (1, 0) else 0.0

    route = astar((0, 0), {(2, 0)}, 3, risk_of=risk)
    assert route is not None and route.cells[1] == (0, 1)

    def mild(cell):
        return 0.5 if cell == (1, 0) else 0.0

    route = astar((0, 0), {(2, 0)}, 3, risk_of=mild)
    assert route is not None and route.cells[1] == (1, 0)


def test_astar_respects_blocked_and_avoid_penalty():
    route = astar((0, 0), {(2, 0)}, 3, risk_of=lambda c: 0.0, blocked={(1, 0)})
    assert route is not None and (1, 0) not in route.cells

    route = astar(
        (0, 0),
        {(2, 0)},
        3,
        risk_of=lambda c: 0.0,
        avoid={(1, 0)},
        avoid_penalty=5.0,
    )
    assert route is not None and (1, 0) not in route.cells


def test_expected_utility_matches_formula():
    assert expected_utility(0.25, 3, 4) == pytest.approx(-251.0)


# -- KB / agent properties -------------------------------------------------
def test_visited_room_is_not_assumed_pit_free_after_a_shift():
    kb = KnowledgeBase(info())
    kb.set_global("GhostAlive", False)
    kb.set_position((0, 3))
    kb.add_base(Fact("Visited", (0, 3)))
    kb.run()
    assert kb.has("NoPit", (0, 3))

    kb.set_position((0, 0))
    kb.add_base(Fact("Visited", (0, 0)))
    kb.apply_shift(2, "ccw", rotation_mapping(2, "ccw", 6))
    kb.run()

    assert kb.has("NoPit", (2, 3))
    assert not kb.has("NoPit", (0, 3))


def test_oracle_applies_shift_mapping():
    agent = make_agent("b4", info())
    agent.pits = frozenset({(0, 3)})
    agent.ghost = (1, 4)

    agent._absorb([ShiftApplied(2, "ccw", rotation_mapping(2, "ccw", 6))])

    assert agent.pits == frozenset({(2, 3)})
    assert agent.ghost == (1, 4)


@pytest.mark.parametrize("mode", ["apprentice", "explorer", "haunted"])
def test_cross_check_and_known_unsafe_property(mode):
    for i in range(3):
        game = Game(mode, f"PROP-{mode}-{i}")
        agent = make_agent("b3", game.info())
        percepts = game.observe()
        events: list = []
        steps = 0
        while not game.state.done and steps < 300:
            action = agent.act(percepts, events)
            assert cross_check(agent.kb, agent.model) == []
            if isinstance(action, Move):
                target = step(agent.pos, action.dir)
                kb = agent.kb
                assert not (
                    kb.has("Unsafe", target) or kb.has("Pit", target) or kb.has("Ghost", target)
                )
            result = game.step(action)
            percepts, events = result.percepts, result.events
            steps += 1


def test_oracle_is_at_least_as_good_as_b3():
    b3_wins = b4_wins = 0
    b3_score = b4_score = 0
    for mode in ("apprentice", "explorer", "haunted"):
        for i in range(3):
            seed = f"BOUND-{mode}-{i}"
            b3 = run_game(mode, seed, "b3")
            b4 = run_game(mode, seed, "b4")
            b3_wins += b3.win
            b4_wins += b4.win
            b3_score += b3.score
            b4_score += b4.score
    assert b4_wins >= b3_wins
    assert b4_score > b3_score


# -- sim -------------------------------------------------------------------
def test_sim_suite_smoke_and_json():
    results = run_suite(
        runs=2,
        modes=("apprentice",),
        agents=("b0", "b3"),
        seed_prefix="SMOKE",
        progress=False,
    )

    data = results["modes"]["apprentice"]
    assert set(data["agents"]) == {"b0", "b3"}
    assert data["agents"]["b3"]["games"] == 2
    assert data["agents"]["b3"]["wins"] >= 1
    assert len(data["records"]) == 4
    assert json.dumps(results)
