"""Tests for the exact posterior ground truth tool (tools/posterior.py)."""

from __future__ import annotations

from shifting_manor.engine.game import Game
from shifting_manor.engine.types import Percepts, ShiftApplied
from tools.posterior import ExactPosterior


def test_posterior_initial_state_respects_protected_cells():
    post = ExactPosterior("apprentice", size=4, pit_total=2)
    post.observe((0, 0), Percepts())
    probs = post.compute()

    assert probs.consistent_worlds > 0
    # Entrance and protected cells have zero hazard
    assert probs.risk((0, 0)) == 0.0
    assert probs.risk((1, 0)) == 0.0
    assert probs.risk((0, 1)) == 0.0
    # Non-protected cells share positive hazard probability
    assert probs.risk((2, 2)) > 0.0


def test_posterior_truth_is_consistent_with_game_state():
    game = Game("explorer", "POSTERIOR-TEST-1")
    post = ExactPosterior.from_info(game.info())

    percepts = game.observe()
    events = []
    post.observe(game.state.agent, percepts, events)
    probs = post.compute()

    # Ground truth pits must have non-zero probability (or 1.0 if determined)
    for pit in game.state.pits:
        assert probs.pit_risk[pit] > 0.0 or probs.hazard_risk[pit] > 0.0


def test_posterior_transports_under_shift():
    post = ExactPosterior("explorer", size=6, pit_total=4)
    post.observe((0, 0), Percepts())

    # Simulate shift on wing 1 rotating (3,0) to (3,2)
    from shifting_manor.engine.grid import rotation_mapping

    mapping = rotation_mapping(1, "cw", 6)
    post.observe((0, 0), Percepts(), [ShiftApplied(1, "cw", mapping)])

    assert post.mapping[(3, 0)] == mapping[(3, 0)]
    assert post.inv_mapping[mapping[(3, 0)]] == (3, 0)


def test_posterior_ghost_risk_zero_after_scream():
    post = ExactPosterior("haunted", size=6, pit_total=5)
    post.observe((0, 0), Percepts(scream=True))
    probs = post.compute()

    assert all(r == 0.0 for r in probs.ghost_risk.values())


def test_visited_room_regains_risk_after_shift_rotates_hazards_in():
    """A shift rotates pits into old visited rooms: risk is NOT pinned to 0 there."""
    from shifting_manor.engine.grid import rotation_mapping

    post = ExactPosterior("explorer", size=6, pit_total=4)
    post.observe((3, 0), Percepts())
    assert post.cell_hazard_risk((3, 0)) == 0.0  # survived standing there

    mapping = rotation_mapping(1, "cw", 6)
    dest = mapping[(3, 0)]
    assert dest != (3, 0)
    post.apply_shift(mapping)
    # The pit-free belief travels with the initial cell to `dest`...
    assert post.cell_hazard_risk(dest) == 0.0
    # ...but room (3,0) now holds a DIFFERENT initial cell's contents,
    # which was never conditioned pit-free: it must carry positive risk.
    assert post.cell_hazard_risk((3, 0)) > 0.0
    probs = post.compute()
    assert probs.hazard_risk[(3, 0)] == post.cell_hazard_risk((3, 0))


def test_visited_rooms_never_free_after_shift_on_real_game():
    """On a seeded game with shifts, some visited room carries positive risk."""
    from shifting_manor.agents import make_agent

    game = Game("explorer", "HAUNT-4F2A")
    agent = make_agent("b3", game.info())
    post = ExactPosterior.from_info(game.info())
    p, e = game.observe(), []
    shifted = False
    while not game.state.done:
        post.observe(game.state.agent, p, e)
        if any(hasattr(ev, "mapping") for ev in e):
            shifted = True
        res = game.step(agent.act(p, e))
        p, e = res.percepts, res.events
    assert shifted, "seed must include a shift"
    probs = post.compute()
    risky_visited = [c for c in post.visited_cells if probs.hazard_risk[c] > 0.0]
    assert risky_visited, "expected a shift to rotate risk into an old visited room"
