"""PR3 audit-of-the-audit: the audit must detect deliberate breakage of B3.

Each test mutates one component of B3's risk pipeline on a DEV-band seed whose
trajectory is known (found by scanning DEV-<MODE>-0000..0039), runs the same
classifier + exact-posterior machinery as the report, and asserts the audit
signals the breakage (a non-forced classification or a calibration blow-up).
The exact posterior (tools/posterior.py) is shared ground truth between mutant
and victim, so detection must come from B3's behaviour, never the oracle.

Baseline expectations (the same seed unmutated) are asserted in the same test
so a future engine change that invalidates the seed fails loudly here.
"""

from __future__ import annotations

from tools.audit import audit_single_seed


def _mae(pairs) -> float:
    return sum(abs(p - e) for p, e, _ in pairs) / len(pairs) if pairs else 0.0


def _patch_lambda(monkeypatch):
    from shifting_manor.agents import planner

    monkeypatch.setattr(planner, "RISK_LAMBDA", 1.0)


def _patch_weights(monkeypatch):
    import shifting_manor.kb.enumerate as enum

    class _StubMath:  # comb() -> uniform hidden-world weights
        comb = staticmethod(lambda n, k: 1 if 0 <= k <= n else 0)

    monkeypatch.setattr(enum, "math", _StubMath())


def _patch_r16(monkeypatch):
    from shifting_manor.kb.base import KnowledgeBase

    monkeypatch.setattr(KnowledgeBase, "apply_shift", lambda self, *a, **k: None)


def _patch_r07(monkeypatch):
    import shifting_manor.kb.rules as rules_mod

    monkeypatch.setattr(rules_mod, "RULES", [r for r in rules_mod.RULES if r.id != "R07"])


def test_audit_detects_risk_lambda_collapse(monkeypatch):
    """DEV-EXPLORER-0024: at lambda=1000 B3 wins; at lambda=1 the audit must
    classify the resulting loss as avoidable/suboptimal, not forced."""
    base = audit_single_seed("explorer", "DEV-EXPLORER-0024", skip_b5=True)
    assert base.b3_outcome == "escaped_treasure"
    assert base.failure is None

    _patch_lambda(monkeypatch)
    mut = audit_single_seed("explorer", "DEV-EXPLORER-0024", skip_b5=True)
    assert mut.failure is not None
    assert mut.failure.classification in ("avoidable", "suboptimal_gamble"), mut.failure.detail


def test_audit_detects_uniform_world_weights(monkeypatch):
    """DEV-EXPLORER-0012: combinatorial hidden-world weights are load-bearing.

    With uniform weights B3's own risk estimates drift from the exact posterior
    on the *same seed* (0.003 -> >0.15 MAE); the calibration column catches it."""
    base = audit_single_seed("explorer", "DEV-EXPLORER-0012", skip_b5=True)
    assert _mae(base.calibration_pairs) < 0.02

    _patch_weights(monkeypatch)
    mut = audit_single_seed("explorer", "DEV-EXPLORER-0012", skip_b5=True)
    assert _mae(mut.calibration_pairs) > 0.15


def test_audit_detects_r16_transport_disabled(monkeypatch):
    """DEV-EXPLORER-0001: without R16, B3 re-derives stale safety after a shift.

    Baseline wins; the mutant dies and the exact posterior proves a zero-risk
    winning route existed (avoidable)."""
    base = audit_single_seed("explorer", "DEV-EXPLORER-0001", skip_b5=True)
    assert base.b3_outcome == "escaped_treasure"

    _patch_r16(monkeypatch)
    mut = audit_single_seed("explorer", "DEV-EXPLORER-0001", skip_b5=True)
    assert mut.failure is not None
    assert mut.failure.classification in ("avoidable", "suboptimal_gamble"), mut.failure.detail


def test_audit_detects_r07_ghost_rule_disabled(monkeypatch):
    """DEV-EXPLORER-0027: without R07 the ghost stays undeduced.

    Baseline wins; the mutant loses and the audit no longer sees a clean run."""
    base = audit_single_seed("explorer", "DEV-EXPLORER-0027", skip_b5=True)
    assert base.b3_outcome == "escaped_treasure"

    _patch_r07(monkeypatch)
    mut = audit_single_seed("explorer", "DEV-EXPLORER-0027", skip_b5=True)
    assert mut.failure is not None
    assert mut.failure.classification in ("avoidable", "suboptimal_gamble"), mut.failure.detail


def test_posterior_shares_no_risk_code_with_b3():
    """Independence: tools/posterior.py imports nothing from agents/ or kb/ — its
    risk numbers are computed from engine primitives only, so B3's model cannot
    bias the ground truth it is graded against."""
    import ast
    from pathlib import Path

    tree = ast.parse(
        (Path(__file__).resolve().parent.parent / "tools" / "posterior.py").read_text(
            encoding="utf-8"
        )
    )

    def imports_in(body):
        found = set()
        for node in body:
            if isinstance(node, ast.Import):
                found.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                found.add(node.module or "")
            elif isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                if node.name == "main":
                    continue  # CLI replay driver may drive any agent; not risk code
                found |= imports_in(node.body)
            else:
                for child in ast.walk(node):
                    if isinstance(child, (ast.Import, ast.ImportFrom)):
                        found.add(child.module or child.names[0].name)
        return found

    mods = imports_in(tree.body)
    banned = ("shifting_manor.agents", "shifting_manor.kb")
    assert not [m for m in mods if m.startswith(banned)], sorted(mods)


def test_b5_risks_come_only_from_the_exact_posterior():
    """B5Agent overrides act() end to end and swaps self.model for
    LazyExactModel; the approximate enumerate_models call in KBAgent.act is
    therefore never reached by B5."""
    import inspect

    from shifting_manor.agents.b5 import B5Agent

    src = inspect.getsource(B5Agent.act)
    assert "enumerate_models" not in src
    assert "LazyExactModel" in src
    assert "act" in B5Agent.__dict__, "B5 must override act, not inherit KBAgent.act"
