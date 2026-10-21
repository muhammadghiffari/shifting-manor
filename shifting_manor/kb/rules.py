"""The 24 IF-THEN rules R01-R24 from PRD 7.3, each a separate Rule object."""

from __future__ import annotations

from collections import deque

from shifting_manor.engine.grid import DIRS, line_cells, neighbours
from shifting_manor.engine.types import Cell
from shifting_manor.kb.base import KnowledgeBase
from shifting_manor.kb.facts import Constraint, Fact
from shifting_manor.kb.forward import Binding, Rule


def _at(kb: KnowledgeBase) -> Cell:
    return kb.position


def _premises(*items: object) -> tuple[object, ...]:
    return tuple(item for item in items if item is not None)


# -- R01-R04: visited rooms and absence of clues ---------------------------
def _r01(kb: KnowledgeBase):
    # Only the room just entered: a durable Visited fact from an earlier turn
    # says nothing about what a shift may have moved into that room since.
    here = _at(kb)
    if not kb.has("Visited", here):
        return []
    return [Binding(_premises(Fact("Visited", here)), {"cell": here})]


def _r01_out(kb: KnowledgeBase, b: Binding):
    c = b.data["cell"]
    return (Fact("NoPit", c), Fact("NoGhost", c))


def _r02(kb: KnowledgeBase):
    return [Binding(_premises(f), {"cell": f.cell}) for f in kb.named("NoBreeze")]


def _r02_out(kb: KnowledgeBase, b: Binding):
    return (Fact("NoPit", n) for n in neighbours(b.data["cell"], kb.info.size))


def _r03(kb: KnowledgeBase):
    return [Binding(_premises(f), {"cell": f.cell}) for f in kb.named("NoChill")]


def _r03_out(kb: KnowledgeBase, b: Binding):
    return (Fact("NoGhost", n) for n in neighbours(b.data["cell"], kb.info.size))


def _r04(kb: KnowledgeBase):
    return [Binding(_premises(f), {"cell": f.cell}) for f in kb.named("Breeze")]


def _r04_out(kb: KnowledgeBase, b: Binding):
    c = b.data["cell"]
    return (Constraint("PIT", frozenset(neighbours(c, kb.info.size))),)


def _r05(kb: KnowledgeBase):
    return [Binding(_premises(f), {"cell": f.cell}) for f in kb.named("Chill")]


def _r05_out(kb: KnowledgeBase, b: Binding):
    c = b.data["cell"]
    return (Constraint("GHOST", frozenset(neighbours(c, kb.info.size))),)


# -- R06-R15: resolving constraints and treasure clues --------------------
def _r06(kb: KnowledgeBase):
    out = []
    for con in kb.constraints:
        if con.kind != "PIT":
            continue
        candidates = [c for c in con.cells if not kb.has("NoPit", c)]
        if len(candidates) == 1 and not kb.has("Pit", candidates[0]):
            out.append(Binding(_premises(con), {"cell": candidates[0]}))
    return out


def _r06_out(kb: KnowledgeBase, b: Binding):
    return (Fact("Pit", b.data["cell"]),)


def _r07(kb: KnowledgeBase):
    if not kb.value("GhostAlive", False):
        return []
    out = []
    for con in kb.constraints:
        if con.kind != "GHOST":
            continue
        candidates = [c for c in con.cells if not kb.has("NoGhost", c)]
        if len(candidates) == 1 and not kb.has("Ghost", candidates[0]):
            out.append(Binding(_premises(con), {"cell": candidates[0]}))
    return out


def _r07_out(kb: KnowledgeBase, b: Binding):
    return (Fact("Ghost", b.data["cell"]),)


def _r08(kb: KnowledgeBase):
    out = []
    for f in kb.named("NoPit"):
        c = f.cell
        if (
            c is not None
            and kb.has("NoGhost", c)
            and not kb.has("Pit", c)
            and not kb.has("Ghost", c)
        ):
            out.append(Binding(_premises(f, Fact("NoGhost", c)), {"cell": c}))
    return out


def _r08_out(kb: KnowledgeBase, b: Binding):
    return (Fact("Safe", b.data["cell"]),)


def _r09(kb: KnowledgeBase):
    out = []
    for f in kb.named("Pit"):
        out.append(Binding(_premises(f), {"cell": f.cell}))
    if kb.value("GhostAlive", False):
        for f in kb.named("Ghost"):
            out.append(Binding(_premises(f), {"cell": f.cell}))
    return out


def _r09_out(kb: KnowledgeBase, b: Binding):
    return (Fact("Unsafe", b.data["cell"]),)


def _r10(kb: KnowledgeBase):
    if not kb.value("GhostAlive", False):
        return []
    return [Binding(_premises(f), {"ghost": f.cell}) for f in kb.named("Ghost")]


def _r10_out(kb: KnowledgeBase, b: Binding):
    g = b.data["ghost"]
    return (
        Fact("NoGhost", (x, y))
        for x in range(kb.info.size)
        for y in range(kb.info.size)
        if (x, y) != g
    )


def _r11(kb: KnowledgeBase):
    total = int(kb.value("PitTotal", 0))
    pits = kb.cell_set("Pit")
    if total and len(pits) == total:
        return [Binding(_premises(), {"pits": pits})]
    return []


def _r11_out(kb: KnowledgeBase, b: Binding):
    pits = b.data["pits"]
    return (
        Fact("NoPit", (x, y))
        for x in range(kb.info.size)
        for y in range(kb.info.size)
        if (x, y) not in pits
    )


def _r12(kb: KnowledgeBase):
    return [Binding(_premises(f)) for f in kb.named("Scream")]


def _r12_out(kb: KnowledgeBase, b: Binding):
    return (
        *(Fact("NoGhost", (x, y)) for x in range(kb.info.size) for y in range(kb.info.size)),
        Fact("GhostAlive", value=False),
    )


def _r13(kb: KnowledgeBase):
    return [Binding(_premises(f), {"cell": f.cell}) for f in kb.named("NoGlimmer")]


def _r13_out(kb: KnowledgeBase, b: Binding):
    c = b.data["cell"]
    return (Fact("NoTreasure", x) for x in [c, *neighbours(c, kb.info.size)])


def _r14(kb: KnowledgeBase):
    return [Binding(_premises(f), {"cell": f.cell}) for f in kb.named("Glimmer")]


def _r14_out(kb: KnowledgeBase, b: Binding):
    c = b.data["cell"]
    return (Constraint("TREASURE", frozenset([c, *neighbours(c, kb.info.size)])),)


def _r15(kb: KnowledgeBase):
    out = []
    for con in kb.constraints:
        if con.kind != "TREASURE":
            continue
        candidates = [c for c in con.cells if not kb.has("NoTreasure", c)]
        if len(candidates) == 1 and not kb.has("TreasureAt", candidates[0]):
            out.append(Binding(_premises(con), {"cell": candidates[0]}))
    return out


def _r15_out(kb: KnowledgeBase, b: Binding):
    return (Fact("TreasureAt", b.data["cell"]),)


# -- R17-R24: goals and action selection ----------------------------------
def _r17(kb: KnowledgeBase):
    start = _at(kb)
    safe = kb.cell_set("Safe") | {start}
    seen = {start}
    queue = deque([start])
    while queue:
        cur = queue.popleft()
        for nxt in neighbours(cur, kb.info.size):
            if nxt in safe and nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return [
        Binding(_premises(Fact("At", start), Fact("Safe", c) if c in safe else None), {"cell": c})
        for c in sorted(seen)
    ]


def _r17_out(kb: KnowledgeBase, b: Binding):
    return (Fact("Reachable", b.data["cell"]),)


def _r18(kb: KnowledgeBase):
    if kb.value("HasTreasure", False) and kb.has("Reachable", kb.info.entrance):
        return [Binding(_premises(Fact("HasTreasure", value=True)))]
    return []


def _r18_out(kb: KnowledgeBase, b: Binding):
    return (Fact("GoalEntrance"),)


def _r19(kb: KnowledgeBase):
    if kb.value("HasTreasure", False):
        return []
    return [
        Binding(_premises(f), {"cell": f.cell})
        for f in kb.named("TreasureAt")
        if kb.has("Reachable", f.cell)
    ]


def _r19_out(kb: KnowledgeBase, b: Binding):
    return (Fact("GoalTreasure", b.data["cell"]),)


def _r20(kb: KnowledgeBase):
    if not (kb.value("GhostAlive", False) and kb.value("CharmAvailable", False)):
        return []
    agent = _at(kb)
    out = []
    for f in kb.named("Ghost"):
        ghost = f.cell
        direction = None
        for d in DIRS:
            if ghost in line_cells(agent, d, kb.info.size):
                direction = d
                break
        if direction is not None:
            out.append(Binding(_premises(f, Fact("At", agent)), {"dir": direction}))
    return out


def _r20_out(kb: KnowledgeBase, b: Binding):
    return (Fact("CharmAction", value=b.data["dir"]),)


def _r21(kb: KnowledgeBase):
    if kb.value("HasTreasure", False) or kb.has("GoalTreasure") or kb.has("GoalEntrance"):
        return []
    agent = _at(kb)
    candidates = [
        f.cell
        for f in kb.named("Reachable")
        if f.cell is not None and kb.has("Safe", f.cell) and not kb.has("Visited", f.cell)
    ]
    scored = []
    for c in candidates:
        distance = kb.shortest_safe_to(c, start=agent)
        if distance is not None:
            scored.append((distance, c))
    if not scored:
        return []
    distance, cell = min(scored)
    return [
        Binding(_premises(Fact("At", agent), Fact("Safe", cell)), {"cell": cell, "dist": distance})
    ]


def _r21_out(kb: KnowledgeBase, b: Binding):
    return (Fact("GoalSafe", b.data["cell"]),)


def _r22(kb: KnowledgeBase):
    if kb.value("HasTreasure", False):
        return []
    if kb.has("GoalTreasure") or kb.has("GoalSafe") or kb.has("GoalEntrance"):
        return []
    if not kb.frontier():
        return []
    return [Binding(_premises(Fact("At", _at(kb))))]


def _r22_out(kb: KnowledgeBase, b: Binding):
    return (Fact("GambleNeeded"),)


def _r23(kb: KnowledgeBase):
    agent = _at(kb)
    distance = kb.shortest_safe_to(kb.info.entrance, start=agent)
    oil = int(kb.value("Oil", kb.info.oil))
    if distance is not None and oil <= distance + 3:
        return [Binding(_premises(Fact("At", agent), Fact("Oil", value=oil)), {"dist": distance})]
    return []


def _r23_out(kb: KnowledgeBase, b: Binding):
    return (Fact("Retreat"),)


def _r24(kb: KnowledgeBase):
    out = []
    agent = _at(kb)
    for f in kb.named("Rumble"):
        wing = f.value
        if wing is not None and kb.wing_of(agent) != wing:
            out.append(Binding(_premises(f, Fact("At", agent)), {"wing": wing}))
    return out


def _r24_out(kb: KnowledgeBase, b: Binding):
    return (Fact("AvoidWing", value=b.data["wing"]),)


RULES: list[Rule] = [
    Rule("R01", "Visited(c) => NoPit(c) and NoGhost(c)", _r01, _r01_out),
    Rule("R02", "NoBreeze(c) => NoPit(n) for every neighbour n of c", _r02, _r02_out),
    Rule("R03", "NoChill(c) => NoGhost(n) for every neighbour n of c", _r03, _r03_out),
    Rule("R04", "Breeze(c) => Constraint(PIT, neighbours(c))", _r04, _r04_out),
    Rule("R05", "Chill(c) => Constraint(GHOST, neighbours(c))", _r05, _r05_out),
    Rule("R06", "Constraint(PIT,S) and one candidate left => Pit", _r06, _r06_out),
    Rule("R07", "Constraint(GHOST,S) and one candidate left => Ghost", _r07, _r07_out),
    Rule("R08", "NoPit(c) and NoGhost(c) => Safe(c)", _r08, _r08_out),
    Rule("R09", "Pit(c), or living Ghost(c) => Unsafe(c)", _r09, _r09_out),
    Rule("R10", "Ghost(g) => NoGhost(x) for all x != g", _r10, _r10_out),
    Rule("R11", "known Pit count == PitTotal => NoPit everywhere else", _r11, _r11_out),
    Rule("R12", "Scream => GhostAlive=false; no ghost facts", _r12, _r12_out),
    Rule("R13", "NoGlimmer(c) => NoTreasure(c and neighbours)", _r13, _r13_out),
    Rule("R14", "Glimmer(c) => Constraint(TREASURE, c and neighbours)", _r14, _r14_out),
    Rule("R15", "Constraint(TREASURE,S), one candidate => TreasureAt", _r15, _r15_out),
    Rule(
        "R16",
        "Rotated(wing,direction) => transport pit/ghost facts and constraints",
        lambda kb: [],
        lambda kb, b: (),
    ),
    Rule("R17", "Safe path from agent to b => Reachable(b)", _r17, _r17_out),
    Rule("R18", "HasTreasure and Reachable(entrance) => Goal entrance", _r18, _r18_out),
    Rule("R19", "TreasureAt(t), Reachable(t), no treasure => Goal t", _r19, _r19_out),
    Rule("R20", "Ghost(g), charm available, agent in line => CastCharm", _r20, _r20_out),
    Rule("R21", "No treasure goal, safe unvisited reachable => nearest GoalSafe", _r21, _r21_out),
    Rule("R22", "No safe goal and no treasure => gamble on the frontier", _r22, _r22_out),
    Rule("R23", "Oil <= safe return + margin 3 => retreat", _r23, _r23_out),
    Rule("R24", "Rumble for w, agent outside w => avoid w", _r24, _r24_out),
]

RULE_BY_ID = {rule.id: rule for rule in RULES}
