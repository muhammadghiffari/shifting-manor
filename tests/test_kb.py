"""M2 KB tests: each rule R01-R24 fires, transport is pure, inferences are sound."""

from __future__ import annotations

import pytest

from shifting_manor.engine.grid import rotation_mapping, wing_map
from shifting_manor.engine.types import GameInfo, Percepts
from shifting_manor.kb.base import KnowledgeBase
from shifting_manor.kb.facts import GLOBAL_NAMES, Constraint, Fact
from shifting_manor.kb.rules import RULE_BY_ID, RULES
from shifting_manor.kb.transport import transport


def make_info(size: int = 6, pits: int = 4, oil: int = 80, shift: int | None = 8) -> GameInfo:
    return GameInfo(
        size=size,
        pit_total=pits,
        entrance=(0, 0),
        shift_every=shift,
        oil=oil,
        wings=wing_map(size),
        foyer_wing=0,
        rotating_wings=(1, 2, 3) if size == 6 else (),
        seed="KB-TEST",
        mode="explorer" if size == 6 else "apprentice",
    )


def fresh_kb(**kwargs) -> KnowledgeBase:
    kb = KnowledgeBase(make_info(**kwargs))
    kb.base = {f for f in kb.base if f.name in GLOBAL_NAMES}
    return kb


def add(kb: KnowledgeBase, *items) -> None:
    for item in items:
        kb.add_base(item)


# -- one scenario per rule -------------------------------------------------
def s_r01(kb):
    kb.set_position((1, 1))
    add(kb, Fact("Visited", (1, 1)))


def s_r02(kb):
    kb.inbox.add(Fact("NoBreeze", (1, 1)))


def s_r03(kb):
    kb.inbox.add(Fact("NoChill", (1, 1)))


def s_r04(kb):
    kb.inbox.add(Fact("Breeze", (1, 1)))


def s_r05(kb):
    kb.inbox.add(Fact("Chill", (1, 1)))


def s_r06(kb):
    add(kb, Constraint("PIT", frozenset({(1, 0), (2, 0)})), Fact("NoPit", (1, 0)))


def s_r07(kb):
    add(kb, Constraint("GHOST", frozenset({(1, 0), (2, 0)})), Fact("NoGhost", (1, 0)))


def s_r08(kb):
    add(kb, Fact("NoPit", (2, 2)), Fact("NoGhost", (2, 2)))


def s_r09(kb):
    add(kb, Fact("Pit", (3, 3)))


def s_r10(kb):
    add(kb, Fact("Ghost", (4, 4)))


def s_r11(kb):
    add(kb, *(Fact("Pit", c) for c in [(4, 4), (5, 4), (4, 5), (5, 5)]))


def s_r12(kb):
    add(kb, Fact("Ghost", (4, 4)))
    kb.prune_ghost()
    kb.inbox.add(Fact("Scream", (0, 0)))


def s_r13(kb):
    kb.inbox.add(Fact("NoGlimmer", (2, 2)))


def s_r14(kb):
    kb.inbox.add(Fact("Glimmer", (2, 2)))


def s_r15(kb):
    add(
        kb,
        Constraint("TREASURE", frozenset({(1, 1), (2, 1)})),
        Fact("NoTreasure", (1, 1)),
    )


def s_r16(kb):
    add(kb, Fact("Pit", (3, 0)))
    kb.apply_shift(1, "cw", rotation_mapping(1, "cw", 6))


def s_r17(kb):
    kb.set_position((0, 0))
    add(kb, Fact("Safe", (1, 0)), Fact("Safe", (2, 0)))


def s_r18(kb):
    kb.set_global("HasTreasure", True)
    kb.set_position((0, 0))
    add(kb, Fact("Safe", (1, 0)), Fact("Safe", (2, 0)))


def s_r19(kb):
    kb.set_position((0, 0))
    add(kb, Fact("Safe", (1, 0)), Fact("TreasureAt", (1, 0)))


def s_r20(kb):
    kb.set_position((0, 0))
    add(kb, Fact("Ghost", (2, 0)))


def s_r21(kb):
    kb.set_position((0, 0))
    add(kb, Fact("Safe", (1, 0)), Fact("Safe", (2, 0)))


def s_r22(kb):
    kb.set_position((0, 0))
    add(kb, Constraint("PIT", frozenset({(3, 3), (4, 4)})))


def s_r23(kb):
    kb.set_position((0, 0))
    kb.set_global("Oil", 2)


def s_r24(kb):
    kb.set_position((0, 0))
    kb.inbox.add(Fact("Rumble", value=1))


SCENARIOS = {
    "R01": s_r01,
    "R02": s_r02,
    "R03": s_r03,
    "R04": s_r04,
    "R05": s_r05,
    "R06": s_r06,
    "R07": s_r07,
    "R08": s_r08,
    "R09": s_r09,
    "R10": s_r10,
    "R11": s_r11,
    "R12": s_r12,
    "R13": s_r13,
    "R14": s_r14,
    "R15": s_r15,
    "R16": s_r16,
    "R17": s_r17,
    "R18": s_r18,
    "R19": s_r19,
    "R20": s_r20,
    "R21": s_r21,
    "R22": s_r22,
    "R23": s_r23,
    "R24": s_r24,
}


def test_rule_table_is_complete_and_unique():
    ids = [r.id for r in RULES]
    assert ids == [f"R{i:02d}" for i in range(1, 25)]
    assert len(set(ids)) == 24
    assert set(SCENARIOS) == set(ids)


@pytest.mark.parametrize("rule_id", [f"R{i:02d}" for i in range(1, 25)])
def test_each_rule_fires_in_a_hand_built_scenario(rule_id):
    kb = fresh_kb()
    SCENARIOS[rule_id](kb)
    if rule_id != "R16":
        kb.run()
    fired = {f.rule_id for f in kb.log}
    assert rule_id in fired, f"{rule_id} did not fire; fired={sorted(fired)}"
    assert RULE_BY_ID[rule_id].description


def test_r02_conclusions_are_exactly_the_neighbours():
    kb = fresh_kb()
    s_r02(kb)
    kb.run()
    assert kb.cell_set("NoPit") == {(0, 1), (2, 1), (1, 0), (1, 2)}


def test_r06_infers_pit_from_single_candidate():
    kb = fresh_kb()
    s_r06(kb)
    kb.run()
    assert kb.has("Pit", (2, 0))


def test_r08_does_not_mark_pit_safe():
    kb = fresh_kb()
    add(kb, Fact("NoPit", (2, 2)), Fact("NoGhost", (2, 2)), Fact("Pit", (2, 2)))
    kb.run()
    assert not kb.has("Safe", (2, 2))


def test_r11_uses_pit_total_from_info():
    kb = fresh_kb(pits=4)
    s_r11(kb)
    kb.run()
    assert not kb.has("NoPit", (4, 4))
    assert kb.has("NoPit", (0, 0))


def test_r12_drops_ghost_facts_and_constraints():
    kb = fresh_kb()
    add(
        kb,
        Fact("Ghost", (4, 4)),
        Constraint("GHOST", frozenset({(4, 4), (3, 4)})),
        Fact("NoGhost", (0, 0)),
    )
    kb.observe(Percepts(scream=True))
    assert not kb.has("Ghost")
    assert all(c.kind != "GHOST" for c in kb.constraints)
    assert kb.value("GhostAlive") is False
    assert kb.has("NoGhost", (4, 4))


def test_transport_moves_pit_ghost_facts_but_not_treasure_or_rooms():
    facts = {
        Fact("Pit", (3, 0)),
        Fact("NoGhost", (3, 1)),
        Fact("TreasureAt", (3, 0)),
        Fact("Visited", (3, 0)),
        Fact("Safe", (3, 2)),
    }
    constraints = {
        Constraint("PIT", frozenset({(3, 0), (3, 1)})),
        Constraint("TREASURE", frozenset({(3, 0), (2, 0)})),
    }
    mapping = rotation_mapping(1, "cw", 6)
    moved, moved_cons = transport(facts, constraints, mapping)
    assert Fact("Pit", mapping[(3, 0)]) in moved
    assert Fact("NoGhost", mapping[(3, 1)]) in moved
    assert Fact("TreasureAt", (3, 0)) in moved
    assert Fact("Visited", (3, 0)) in moved
    assert Fact("Safe", (3, 2)) in moved
    assert Constraint("PIT", frozenset(mapping[c] for c in [(3, 0), (3, 1)])) in moved_cons
    assert Constraint("TREASURE", frozenset({(3, 0), (2, 0)})) in moved_cons


def test_transport_is_idempotent_under_identity_mapping():
    facts = {Fact("Pit", (3, 0)), Fact("TreasureAt", (1, 1))}
    constraints = {Constraint("PIT", frozenset({(3, 0), (4, 1)}))}
    moved, moved_cons = transport(facts, constraints, {c: c for c in [(3, 0), (4, 1)]})
    assert moved == frozenset(facts)
    assert moved_cons == frozenset(constraints)


def test_four_clockwise_transports_are_identity():
    """Applying 4 clockwise rotations transports facts and constraints back to start."""
    facts = frozenset({Fact("Pit", (3, 0)), Fact("NoGhost", (4, 1))})
    constraints = frozenset({Constraint("PIT", frozenset({(3, 0), (4, 1)}))})
    curr_f, curr_c = facts, constraints
    mapping = rotation_mapping(1, "cw", 6)
    for _ in range(4):
        curr_f, curr_c = transport(curr_f, curr_c, mapping)
    assert curr_f == facts
    assert curr_c == constraints


def test_cw_then_ccw_transports_are_identity():
    """Applying clockwise then counter-clockwise rotation restores original facts."""
    facts = frozenset({Fact("Pit", (3, 0)), Fact("NoGhost", (4, 1))})
    constraints = frozenset({Constraint("PIT", frozenset({(3, 0), (4, 1)}))})
    cw = rotation_mapping(1, "cw", 6)
    ccw = rotation_mapping(1, "ccw", 6)
    f_cw, c_cw = transport(facts, constraints, cw)
    f_orig, c_orig = transport(f_cw, c_cw, ccw)
    assert f_orig == facts
    assert c_orig == constraints


def test_mutation_disabling_r16_fails_transport(monkeypatch):
    """Mutation check: disabling R16 transport drops facts that should be relocated."""
    kb = fresh_kb()
    add(kb, Fact("Pit", (3, 0)))
    mapping = rotation_mapping(1, "cw", 6)
    kb.apply_shift(1, "cw", mapping)
    dest = mapping[(3, 0)]
    assert kb.has("Pit", dest)

    # Disabling R16 transport by stubbing apply_shift to a no-op:
    monkeypatch.setattr(KnowledgeBase, "apply_shift", lambda self, *args, **kwargs: None)
    kb_mut = fresh_kb()
    add(kb_mut, Fact("Pit", (3, 0)))
    kb_mut.apply_shift(1, "cw", mapping)
    assert not kb_mut.has("Pit", dest)


def test_mutation_disabling_r07_fails_single_candidate_ghost(monkeypatch):
    """Mutation check: disabling R07 prevents deducing ghost from single candidate."""
    import shifting_manor.kb.rules as rules_mod

    # Standard R07 scenario derives Ghost(2, 0)
    kb = fresh_kb()
    s_r07(kb)
    kb.run()
    assert kb.has("Ghost", (2, 0))

    # Mutate: remove R07 from RULES
    mutated_rules = [r for r in rules_mod.RULES if r.id != "R07"]
    monkeypatch.setattr(rules_mod, "RULES", mutated_rules)

    kb_mut = fresh_kb()
    s_r07(kb_mut)
    kb_mut.run()
    assert not kb_mut.has("Ghost", (2, 0))
    assert not any(f.rule_id == "R07" for f in kb_mut.log)


def test_shift_rule_is_registered_as_r16():
    assert RULE_BY_ID["R16"].description.startswith("Rotated")


def test_no_ghost_facts_after_scream():
    kb = fresh_kb()
    add(kb, Fact("Ghost", (2, 2)))
    kb.observe(Percepts(scream=True))
    assert not any(f.name == "Ghost" for f in kb.facts)


def test_observation_is_only_used_once():
    kb = fresh_kb()
    kb.observe(Percepts())
    first = len([f for f in kb.log if f.rule_id == "R02"])
    assert first > 0
    kb.observe(Percepts())
    assert len([f for f in kb.log if f.rule_id == "R02"]) == first


def test_second_turn_logs_only_new_derivations():
    kb = fresh_kb()
    kb.observe(Percepts())
    assert kb.firings
    logged = len(kb.log)

    kb.observe(Percepts())

    assert kb.firings == []
    assert len(kb.log) == logged
    assert kb.last_rederivations > 0
    assert set(kb.last_rederivations_by_rule) <= {r.id for r in RULES}


def test_r17_logs_the_safe_path_it_used():
    kb = fresh_kb()
    s_r17(kb)
    kb.run()
    firing = next(
        f for f in kb.log if f.rule_id == "R17" and Fact("Reachable", (2, 0)) in f.conclusions
    )
    assert firing.note == "via safe path: (0,0) -> (1,0) -> (2,0)"
    assert Fact("Safe", (0, 0)) not in firing.premises
    assert Fact("At", (0, 0)) in firing.premises
    assert Fact("Safe", (2, 0)) in firing.premises


def test_provenance_points_from_fact_to_rule_and_percept_leaf():
    kb = fresh_kb()
    kb.observe(Percepts())

    leaf = kb.provenance[Fact("NoBreeze", (0, 0))]
    assert leaf.rule_id == "PERCEPT"
    assert leaf.premises == ()

    no_pit = kb.provenance[Fact("NoPit", (1, 0))]
    assert no_pit.rule_id == "R02"
    assert Fact("NoBreeze", (0, 0)) in no_pit.premises
    assert no_pit.turn == 0


def test_r16_logs_one_aggregate_line_and_keeps_provenance():
    kb = fresh_kb()
    mapping = rotation_mapping(1, "cw", 6)
    old_constraint = Constraint("GHOST", frozenset({(3, 0), (4, 1)}))
    add(kb, Fact("Pit", (3, 0)), Fact("NoPit", (3, 1)), old_constraint)
    kb.run()
    kb.apply_shift(1, "cw", mapping)

    r16 = [f for f in kb.log if f.rule_id == "R16"][-1]
    assert r16.note == "transported 2 facts (wing 1, cw)"
    assert r16.premises == (Fact("Rotated", value=(1, "cw")),)
    assert r16.shift_index == 1
    moved = Fact("Pit", mapping[(3, 0)])
    moved_firing = kb.provenance[moved]
    assert moved_firing.rule_id == "R16"
    assert moved_firing.premises == (r16.premises[0], Fact("Pit", (3, 0)))
    assert moved_firing.shift_index == 1
    moved_constraint = Constraint(
        "GHOST", frozenset(mapping.get(c, c) for c in old_constraint.cells)
    )
    constraint_firing = kb.constraint_provenance[moved_constraint]
    assert constraint_firing.rule_id == "R16"
    assert constraint_firing.premises == (r16.premises[0], old_constraint)
    assert constraint_firing.shift_index == 1
