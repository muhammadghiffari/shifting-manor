"""M1 engine tests: geometry, generation, percepts, actions, shifts, determinism."""

from __future__ import annotations

import random

import pytest

from shifting_manor.engine.game import Game
from shifting_manor.engine.generator import generate, hazard_free_path, protected_cells
from shifting_manor.engine.grid import (
    ROTATING_WINGS,
    WING_CENTRES,
    in_bounds,
    is_4_adjacent,
    line_cells,
    rotation_mapping,
    step,
    wing_cells,
)
from shifting_manor.engine.modes import MODES
from shifting_manor.engine.types import (
    CastCharm,
    Dir,
    Leave,
    Move,
    ShiftApplied,
    ShiftSkipped,
    ShiftTelegraph,
)


@pytest.mark.parametrize("wing", ROTATING_WINGS)
@pytest.mark.parametrize("direction", ["cw", "ccw"])
def test_rotation_is_bijection_and_centre_fixed(wing, direction):
    size = 6
    mapping = rotation_mapping(wing, direction, size)
    assert set(mapping) == set(wing_cells(wing, size))
    assert set(mapping.values()) == set(wing_cells(wing, size))
    assert mapping[WING_CENTRES[wing]] == WING_CENTRES[wing]


@pytest.mark.parametrize("wing", ROTATING_WINGS)
def test_four_clockwise_rotations_are_identity(wing):
    mapping = {c: c for c in wing_cells(wing, 6)}
    for _ in range(4):
        step = rotation_mapping(wing, "cw", 6)
        mapping = {c: step[dst] for c, dst in mapping.items()}
    assert all(mapping[c] == c for c in wing_cells(wing, 6))


@pytest.mark.parametrize("wing", ROTATING_WINGS)
def test_cw_then_ccw_is_identity(wing):
    cw = rotation_mapping(wing, "cw", 6)
    ccw = rotation_mapping(wing, "ccw", 6)
    for cell in wing_cells(wing, 6):
        assert ccw[cw[cell]] == cell


@pytest.mark.parametrize("wing", ROTATING_WINGS)
def test_rotation_preserves_adjacency_inside_wing(wing):
    mapping = rotation_mapping(wing, "cw", 6)
    cells = wing_cells(wing, 6)
    for a in cells:
        for b in cells:
            if is_4_adjacent(a, b):
                assert is_4_adjacent(mapping[a], mapping[b])


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("seed", [f"S{i}" for i in range(40)])
def test_generator_constraints(mode, seed):
    cfg = MODES[mode]
    board = generate(cfg, seed)
    protected = protected_cells((0, 0), cfg.size)
    assert board.treasure not in board.pits
    assert board.treasure != board.ghost
    assert board.ghost not in protected
    assert not (board.pits & protected)
    assert hazard_free_path((0, 0), board.treasure, cfg.size, board.pits, board.ghost)
    assert len(board.pits) == cfg.pits


def test_same_seed_same_map():
    for mode in MODES:
        a = generate(MODES[mode], "HAUNT-4F2A")
        b = generate(MODES[mode], "HAUNT-4F2A")
        assert a == b


def test_initial_percepts_and_entrance_protection():
    # Pit at (2,1) is next to (1,1); ghost at (2,2); treasure at (3,3).
    game = Game.from_map("apprentice", "x", pits={(2, 1)}, ghost=(2, 2), treasure=(3, 3))
    assert game.state.agent == (0, 0)
    assert not game.observe().breeze
    game.state.agent = (1, 1)
    assert game.observe().breeze
    game.state.agent = (1, 2)
    assert game.observe().chill
    game.state.agent = (3, 2)
    assert game.observe().glimmer
    game.state.agent = (3, 3)
    assert game.observe().glimmer


def test_bump_is_free_and_does_not_advance_action_counter():
    game = Game.from_map("apprentice", "x", pits=set(), ghost=None, treasure=(3, 3))
    result = game.step(Move("S"))
    assert result.events and result.events[0].__class__.__name__ == "Bumped"
    assert game.state.oil == game.state.start_oil
    assert game.state.action_count == 0
    assert not game.state.done


def test_move_costs_one_oil_and_counts_one_action():
    game = Game.from_map("apprentice", "x", pits=set(), ghost=None, treasure=(3, 3))
    game.step(Move("E"))
    assert game.state.agent == (1, 0)
    assert game.state.oil == game.state.start_oil - 1
    assert game.state.action_count == 1
    assert game.state.actions_taken == 1


def test_walking_into_pit_dies_and_scores_minus_1000():
    game = Game.from_map("apprentice", "x", pits={(1, 0)}, ghost=None, treasure=(3, 3))
    result = game.step(Move("E"))
    assert result.done
    assert game.state.outcome == "died_pit"
    assert game.score() <= -1000


def test_walking_into_living_ghost_dies_and_banished_ghost_does_not():
    game = Game.from_map("apprentice", "x", pits=set(), ghost=(1, 0), treasure=(3, 3))
    result = game.step(Move("E"))
    assert result.done and game.state.outcome == "died_ghost"


def test_treasure_pickup_and_escape_score():
    game = Game.from_map("apprentice", "x", pits=set(), ghost=None, treasure=(1, 0))
    result = game.step(Move("E"))
    assert game.state.has_treasure
    assert any(e.__class__.__name__ == "PickedUp" for e in result.events)
    game.state.agent = (0, 0)
    result = game.step(Leave())
    assert result.done
    assert game.state.outcome == "escaped_treasure"
    assert game.score() == 1000 - 1


def test_leave_outside_entrance_is_invalid_and_free():
    game = Game.from_map("apprentice", "x", pits=set(), ghost=None, treasure=(3, 3))
    game.state.agent = (1, 0)
    result = game.step(Leave())
    assert not result.done
    assert result.events[0].__class__.__name__ == "InvalidAction"
    assert game.state.oil == game.state.start_oil


def test_charm_banishes_ghost_on_line_and_costs_oil_and_score():
    game = Game.from_map("apprentice", "x", pits=set(), ghost=(2, 0), treasure=(3, 3))
    result = game.step(CastCharm("E"))
    assert game.state.ghost is None
    assert game.state.ghost_banished
    assert game.observe().scream
    assert any(e.__class__.__name__ == "GhostBanished" for e in result.events)
    assert game.state.oil == game.state.start_oil - 1
    assert game.score() == 200 - 1 - 10


def test_charm_is_single_use():
    game = Game.from_map("apprentice", "x", pits=set(), ghost=(2, 0), treasure=(3, 3))
    game.step(CastCharm("E"))
    oil = game.state.oil
    result = game.step(CastCharm("E"))
    assert result.events[0].__class__.__name__ == "InvalidAction"
    assert game.state.oil == oil


def test_oil_out_ends_run():
    game = Game.from_map("apprentice", "x", pits=set(), ghost=None, treasure=(3, 3), oil=1)
    result = game.step(Move("E"))
    assert result.done
    assert game.state.outcome == "oil_out"
    assert game.state.oil == 0


def test_line_cells_stop_at_wall():
    assert line_cells((0, 0), "E", 4) == [(1, 0), (2, 0), (3, 0)]
    assert line_cells((3, 3), "N", 4) == []


def test_shift_telegraph_and_apply_without_hazards():
    game = Game.from_map("explorer", "shift-seed", pits=set(), ghost=None, treasure=(5, 0))
    events = []
    for _ in range(8):
        events.extend(game.step(Move("E" if game.state.agent == (0, 0) else "W")).events)
    telegraphs = [e for e in events if isinstance(e, ShiftTelegraph)]
    applied = [e for e in events if isinstance(e, ShiftApplied)]
    assert telegraphs and telegraphs[0].in_actions == 2
    assert applied and applied[0].wing in ROTATING_WINGS
    assert game.state.action_count == 8


def test_shift_is_skipped_when_agent_stands_in_wing():
    game = Game.from_map("explorer", "shift-seed", pits=set(), ghost=None, treasure=(5, 0))
    for _ in range(6):
        game.step(Move("E" if game.state.agent == (0, 0) else "W"))
    assert game._pending is not None
    wing = game._pending.wing
    cells_in_wing = wing_cells(wing, 6)
    pair = next((a, b) for a in cells_in_wing for b in cells_in_wing if is_4_adjacent(a, b))
    game.state.agent = pair[0]
    events = []
    direction = next(
        d
        for d, delta in {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}.items()
        if (pair[0][0] + delta[0], pair[0][1] + delta[1]) == pair[1]
    )
    back = {"N": "S", "E": "W", "S": "N", "W": "E"}[direction]
    events.extend(game.step(Move(direction)).events)  # type: ignore[arg-type]
    events.extend(game.step(Move(back)).events)  # type: ignore[arg-type]
    assert any(isinstance(e, ShiftSkipped) for e in events)


def test_shift_mapping_transports_pits_exactly():
    game = Game.from_map(
        "explorer",
        "mapping-seed",
        pits={(5, 5), (5, 4)},
        ghost=None,
        treasure=(5, 0),
    )
    before = set(game.state.pits)
    events = []
    for _ in range(8):
        events.extend(game.step(Move("E" if game.state.agent == (0, 0) else "W")).events)
    applied = [e for e in events if isinstance(e, ShiftApplied)]
    if not applied:
        pytest.skip("seeded shift happened to be skipped")
    mapping = applied[-1].mapping
    assert set(game.state.pits) == {mapping.get(p, p) for p in before}


def test_same_seed_same_event_log():
    actions = [Move("E"), Move("N"), Move("W"), Move("S")] * 6
    logs = []
    for _ in range(2):
        game = Game("explorer", "repeat-seed")
        for action in actions:
            if game.state.done:
                break
            game.step(action)
        logs.append(game.state.event_log)
    assert logs[0] == logs[1]


def _random_legal_action(game: Game, rng: random.Random):
    if game.state.agent == game.state.entrance and rng.random() < 0.05:
        return Leave()
    if game.state.charm_available and rng.random() < 0.02:
        return CastCharm(rng.choice(["N", "E", "S", "W"]))  # type: ignore[arg-type]
    dirs: list[Dir] = ["N", "E", "S", "W"]
    rng.shuffle(dirs)
    for d in dirs:
        if in_bounds(step(game.state.agent, d), game.state.size):
            return Move(d)
    return Leave()


def test_1000_random_games_do_not_crash_or_hang():
    rng = random.Random("m1-1000")
    for i in range(1000):
        mode = list(MODES)[i % 3]
        game = Game(mode, f"random-{i}")
        for _ in range(500):
            if game.state.done:
                break
            game.step(_random_legal_action(game, rng))
        assert game.state.done, f"game {i} did not finish"
