"""Tests for the PR2 audit tooling (tools/audit.py)."""

from __future__ import annotations

from shifting_manor.engine.types import Percepts
from tools.audit import _zero_risk_component, audit_single_seed
from tools.posterior import ExactPosterior


def _haunted_posterior() -> ExactPosterior:
    return ExactPosterior("haunted", size=6, pit_total=5)


def test_zero_component_follows_only_risk_zero_steps():
    post = _haunted_posterior()
    post.observe((0, 0), Percepts())
    comp = _zero_risk_component((0, 0), 6, post)
    # Entrance neighbourhood (1,0) and (0,1) are protected => risk 0, so in the component.
    assert (1, 0) in comp
    assert (0, 1) in comp
    # A risk-0 cell's neighbours are risk-0 too (a pit next to it would raise its
    # risk), so from the protected entrance area the whole safe region is closed.
    assert (0, 0) in comp
    # Far cells have positive marginal risk with no observations: never reachable.
    far = _zero_risk_component((5, 5), 6, post)
    assert far == {(5, 5): 0}
    assert (0, 0) not in far


def test_zero_component_blocks_positive_risk_cell():
    post = _haunted_posterior()
    post.observe((0, 0), Percepts())
    # Any cell with positive marginal risk cuts the component off: from a fresh
    # posterior only the protected entrance region is zero.
    comp = _zero_risk_component((0, 0), 6, post)
    for cell in comp:
        assert post.cell_hazard_risk(cell) <= 1e-9
    assert len(comp) < 36
    # Distances are BFS steps from the start cell.
    assert comp[(0, 0)] == 0
    assert comp[(1, 0)] == 1


def test_audit_single_seed_reports_consistent_record():
    record = audit_single_seed("apprentice", "AUDIT-CHECK-0001")
    assert record.mode == "apprentice"
    assert record.b4_par >= 1
    assert record.b3_outcome in {
        "escaped_treasure",
        "escaped_empty",
        "died_pit",
        "died_ghost",
        "died_oil",
        "stalled",
    }
    for pred, exact, is_haz in record.calibration_pairs:
        assert 0.0 <= pred <= 1.0
        assert 0.0 <= exact <= 1.0
        assert is_haz in (0, 1)
    if record.b3_outcome == "escaped_treasure":
        assert record.failure is None
    else:
        assert record.failure is not None
        assert record.failure.classification in {"avoidable", "suboptimal_gamble", "forced"}


def test_lambda_fix_saves_known_seed():
    """Regression: SIM-APPRENTICE-10146 died on a 0.5-risk gamble in a 3-room region.

    With RISK_LAMBDA=10 routing the agent now survives this seed.
    """
    from shifting_manor.sim.runner import run_game

    record = run_game("apprentice", "SIM-APPRENTICE-10146", "b3")
    assert not record.outcome.startswith("died")


def test_audit_imports_without_headless_pygame():
    """tools.audit only pulls engine/agents/sim layers: no pygame."""
    import subprocess
    import sys

    code = "import sys;import tools.audit;assert 'pygame' not in sys.modules"
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
