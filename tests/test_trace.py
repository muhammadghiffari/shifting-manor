"""The Watch AI trace is frozen, deterministic and has observation-closed proofs."""

from __future__ import annotations

from shifting_manor.kb.facts import Fact
from shifting_manor.trace import build_trace, format_firing


def _summary(store):
    return [
        (
            step.index,
            step.position,
            step.action,
            step.thought,
            tuple(f.rule_id for f in step.firings),
            tuple(f.rule_id for f in step.all_firings),
            tuple((b.cell, b.label, round(b.risk, 6), b.stale) for b in step.beliefs),
            tuple((c.cell, round(c.risk, 6), round(c.utility, 6)) for c in step.gamble_candidates),
            step.shift.shift_index if step.shift else None,
            step.after_position,
        )
        for step in store.steps
    ]


def test_trace_is_deterministic_for_the_same_seed() -> None:
    first = build_trace("explorer", "TRACE-DETERMINISM", "b3")
    second = build_trace("explorer", "TRACE-DETERMINISM", "b3")
    assert _summary(first) == _summary(second)
    assert first.outcome == second.outcome
    assert first.steps[0].thought


def _leaves(node):
    if not node.children:
        return [node]
    out = []
    for child in node.children:
        out += _leaves(child)
    return out


def test_every_safe_pit_and_ghost_fact_has_an_observation_proof() -> None:
    store = build_trace("explorer", "TRACE-PROOF", "b3")
    checked = 0
    for step in store.steps:
        by_name = {("Safe", b.cell) for b in step.beliefs if b.label == "safe"}
        by_name |= {("Pit", b.cell) for b in step.beliefs if b.label == "pit"}
        by_name |= {("Ghost", b.cell) for b in step.beliefs if b.label == "ghost"}
        assert by_name  # every turn knows at least the current room
        for name, cell in by_name:
            fact = Fact(name, cell)
            cells = [f for f in step.facts if f.name == name and f.cell == cell]
            if not cells:
                continue
            node = store.proof(step.index, fact)
            assert node.children or node.leaf
            for leaf in _leaves(node):
                assert "percept at turn" in leaf.detail or "given at turn" in leaf.detail, (
                    name,
                    cell,
                    leaf.label,
                    leaf.detail,
                )
            checked += 1
    assert checked > 100


def test_log_rows_support_new_only_and_all() -> None:
    store = build_trace("explorer", "TRACE-LOG", "b3")
    rows = store.log_rows()
    new_rows = [row for row in rows if row.new]
    assert new_rows
    assert len(rows) >= len(new_rows)
    assert any(row.firing.rederived for row in rows)
    for step in store.steps:
        assert sum(row.step_index == step.index for row in new_rows) == len(step.firings)
        assert sum(row.step_index == step.index for row in rows) == len(step.all_firings)
    assert " => " in format_firing(store.steps[0].firings[0])
    for row in new_rows[:20]:
        assert row.text
        assert row.firing.rule_id in row.text


def test_r16_is_a_logged_derivation_and_a_proof_edge() -> None:
    store = build_trace("explorer", "HAUNT-4F2A", "b3")
    step = store.steps[8]
    r16 = next(firing for firing in step.firings if firing.rule_id == "R16")
    assert r16.premises == (Fact("Rotated", value=(1, "cw")),)
    assert format_firing(r16).startswith("R16 Rotated(1, cw) =>")
    assert "transported 3 facts (wing 1, cw)" in format_firing(r16)

    counts, last = store.rule_stats(8)
    assert counts["R16"] == 1
    assert last["R16"] is r16

    node = store.proof(8, Fact("Safe", (3, 2)))

    def walk(item):
        yield item
        for child in item.children:
            yield from walk(child)

    labels = {item.label for item in walk(node)}
    assert "Safe(3,2)" in labels
    assert "NoPit(3,2)" in labels
    assert "NoGhost(3,2)" in labels
    assert "NoPit(3,0)" in labels
    assert "NoGhost(3,0)" in labels
    assert "NoBreeze(2,0)" in labels
    assert "NoChill(2,0)" in labels
    assert "Rotated(1, cw)" in labels
    assert any("moved from (3, 0) by shift #1" in item.detail for item in walk(node))
    assert any(item.leaf and "percept at turn 6" in item.detail for item in walk(node))

    log_node = store.proof(8, r16)
    assert [child.label for child in log_node.children] == ["Rotated(1, cw)"]
    assert log_node.children[0].detail == "given at turn 8"


def test_r17_log_line_includes_the_safe_path() -> None:
    store = build_trace("explorer", "HAUNT-4F2A", "b3")
    firing = next(
        firing
        for step in store.steps
        for firing in step.firings
        if firing.rule_id == "R17" and " -> " in firing.note
    )
    text = format_firing(firing)
    assert "via safe path:" in text
    assert " -> " in text


def test_shift_is_a_stored_step_with_stale_beliefs() -> None:
    store = build_trace("explorer", "HAUNT-4F2A", "b3")
    shifts = [step for step in store.steps if step.shift is not None]
    assert shifts
    first = shifts[0]
    assert first.shift is not None
    assert first.shift.shift_index == 1
    assert len(first.shift.mapping) == 9
    assert sum(b.stale for b in first.beliefs) == 9
    assert first.shift.before == store.steps[first.index - 1].beliefs


def test_streamed_firings_are_new_deltas_only() -> None:
    store = build_trace("explorer", "TRACE-DELTA", "b3")
    for step in store.steps:
        assert all(not firing.rederived for firing in step.firings)
        assert len(step.firings) <= len(step.all_firings)


def test_headless_layers_do_not_import_pygame() -> None:
    import subprocess
    import sys

    code = (
        "import sys;"
        "import shifting_manor.engine.game;"
        "import shifting_manor.kb.base;"
        "import shifting_manor.kb.rules;"
        "import shifting_manor.kb.enumerate;"
        "import shifting_manor.agents;"
        "import shifting_manor.sim.runner;"
        "assert 'pygame' not in sys.modules"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
