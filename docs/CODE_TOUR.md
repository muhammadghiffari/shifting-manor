# Code tour

This is the reading order for someone who has to explain the project, not just run it. Every path and line number below is from the current M5 tree. Read top to bottom; each section ends with one real excerpt and a plain-language line-by-line explanation.

Rules of the codebase:

- Only `shifting_manor/ui/` imports pygame. Engine, KB, agents and sim are headless and tested that way.
- `shifting_manor/engine/types.py` is the shared vocabulary: `Cell`, `Dir`, `Move`, `CastCharm`, `Leave`, `Percepts` and the event types. `Percepts` is lines 41–58; `GameInfo` is 61–72.
- A `Firing.turn` is **0-based**. The Watch UI displays `turn + 1`.

## 0. Rules vs planner logic

Do not call every IF–THEN-looking thing a rule. The split is deliberate:

| Part | Where | What runs it |
|---|---|---|
| R01–R15, R17–R24 | `shifting_manor/kb/rules.py` | The forward chainer in `kb/forward.py`. Each rule has a match function and a conclusion function. |
| R16 | `KnowledgeBase.apply_shift` (`kb/base.py:197-271`) plus the pure mapping in `kb/transport.py` | A `ShiftApplied` event. The `Rule` entry (`rules.py:377-381`) is metadata marked `event_driven=True`; `forward_chain` skips it. |
| Exact risk enumeration | `shifting_manor/kb/enumerate.py` | Called by the agent after the rule closure, not by a rule. |
| A* routing | `shifting_manor/agents/planner.py` | Called by the agent when it needs a route. |
| Gamble choice | `shifting_manor/agents/kb_agent.py::_gamble_target` (`265`) using `planner.expected_utility` | Planner code chooses the target and first risky step. R22 only says “a gamble is needed” and lists candidates. |
| Final action priority | `shifting_manor/agents/kb_agent.py::_decide` (`159`) | Planner/agent code, not the chainer. |

R16 is the one rule that changes state instead of only deriving a new fact. It is still logged as an R16 `Firing` with `Rotated(wing, direction)` as its premise, and it counts in the KB tab stats. Each moved fact or constraint gets its own R16 provenance edge whose premises are the rotation and the old item, which is why the proof tree can show both “moved from (3,0)” and the pre-shift observation.

## 1. `shifting_manor/engine/game.py` — the rules of the manor

**Purpose.** This file owns the authoritative game state and applies one action at a time. It does not know about the KB or the agent; it only updates pits, ghost, treasure, oil, the shift clock and the event list.

**Key functions.** `GameState` (line 49) is the mutable state; `Game.observe` (128) turns the true map into percepts; `Game.step` (149) is the one-action pipeline; `_apply` (207) handles Move/CastCharm/Leave; `_advance_shift` (276) decides when a wing rotates; `score` (166) and `stars` (177) are the rules for the result screen.

Excerpt, `Game.step` (lines 149–164):

```python
def step(self, action: Action) -> StepResult:
    if self.state.done:
        return StepResult(self.observe(), [], True)
    self._bump = False
    self._scream = False
    events: list[Event] = []
    result = self._apply(action, events)
    if result is not None:
        self._log(events)
        return result
    if not self.state.done:
        self._maybe_oil_low(events)
        if not self.state.done:
            self._advance_shift(events)
    self._log(events)
    return StepResult(self.observe(), events, self.state.done)
```

- `149` is the public call the agent, UI and sim all use.
- `150–151` makes a finished game idempotent: asking again returns the same percepts and no events.
- `152–153` clear the one-step “bumped the wall” and “ghost screamed” flags.
- `154` creates the event list that the agent will receive on its next turn.
- `155` applies the action. `_apply` returns a result only for a rejected action or a terminal step (death, leave, oil out).
- `156–158` logs and returns early in those cases. This is why a death is visible immediately.
- `159–162` otherwise handles the oil-low check and then the shift clock. Shift happens **after** the action, which is why a shift is reported on the next turn's events.
- `163–164` records the final event list and returns fresh percepts and `done`.

The important teaching point: the engine is a deterministic transition function. The same action, seed and state always produce the same result.

## 2. `shifting_manor/engine/shift.py` — valid rotations

**Purpose.** This file chooses a wing and direction and checks that the rotated map is still playable. It never changes the state itself; `Game._advance_shift` calls it and then applies the returned mapping.

**Key functions.** `request_shift` (26), `hazards_after` (34), `valid_after` (42), `plan_request` (60), `choose_shift` (87), `agent_inside_wing` (114). The actual coordinate rotation is in `grid.rotate_cell` (62) and `grid.rotation_mapping` (71).

Excerpt, `plan_request` (lines 71–84):

```python
for candidate in (request.direction, "ccw" if request.direction == "cw" else "cw"):
    mapping = rotation_mapping(request.wing, candidate, size)
    new_pits, new_ghost = hazards_after(pits, ghost, mapping)
    if valid_after(
        size=size,
        pits=new_pits,
        ghost=new_ghost,
        treasure=treasure,
        entrance=entrance,
        agent=agent,
        has_treasure=has_treasure,
    ):
        return ShiftPlan(request.wing, candidate, mapping)
return None
```

- `71` tries the requested direction first, then the opposite direction. That fallback is why the PRD says “if still invalid, mark it skipped”.
- `72` builds one cell-to-cell map for the whole wing.
- `73` moves the pits and ghost through that map.
- `74–82` checks the two invariants: no hazard on the treasure, and the required hazard-free path (entrance-to-treasure, or agent-to-entrance when carrying) still exists.
- `83` returns the first valid plan; `84` returns `None`, which the game records as a skipped shift.

`grid.rotate_cell` is the actual geometry: subtract the wing centre, apply the clockwise/counter-clockwise 90° formula, add the centre back. Keep that rotation matrix in mind when reading R16: R16 uses exactly the same mapping.

## 3. `shifting_manor/kb/facts.py` — the KB vocabulary

**Purpose.** These are the immutable records the whole inference layer shares. A `Fact` is a ground statement, a `Constraint` is a set of possible cells, and a `Firing` is one rule application with its premises and conclusions.

**Key functions.** `Fact` (52), `Constraint` (66), `Firing` (76), `Explanation` (87), `fact_sort_key` (94) for deterministic ordering.

Excerpt (lines 52–84):

```python
@dataclass(frozen=True)
class Fact:
    name: str
    cell: Cell | None = None
    value: Any = None


@dataclass(frozen=True)
class Constraint:
    kind: ConstraintKind
    cells: frozenset[Cell]


@dataclass(frozen=True)
class Firing:
    rule_id: str
    premises: tuple[object, ...]
    conclusions: tuple[object, ...]
    turn: int
    note: str = ""
    rederived: bool = False
    shift_index: int = 0
```

- `52–56` `Fact` is hashable because it is frozen. `cell` is optional because globals like `GhostAlive` and `HasTreasure` have no cell.
- `66–69` `Constraint` is one OR-set: “the pit is in exactly one of these cells”. It is also frozen so it can live in a set.
- `76–84` `Firing` is the audit record. `premises` and `conclusions` hold `Fact` or `Constraint` objects, `turn` is the 0-based decision turn, and `rederived` distinguishes a duplicate R08/R17 from real progress.
- `shift_index` is set only on R16 firings and their transported conclusions. The proof tree uses it to say “shift #1”.

Why the distinction matters: `Fact("NoPit", (2,2))` and `Constraint("PIT", {...})` are not interchangeable. A constraint is a disjunction; a fact is committed knowledge.

## 4. `shifting_manor/kb/rules.py` — R01–R24

**Purpose.** Each of the 24 PRD rules is a pair of functions: `_rNN` finds bindings that match the current KB, and `_rNN_out` returns the conclusions for one binding. `RULES` (line 361) is the fixed-priority list the forward chainer consumes.

**Key functions.** `_r01` (23), `_r04` (53), `_r05` (62), `_r06` (72), `_r07` (87), `_r08` (104), `_r15` (199), `_r17` (215), `_r20` (273), `_r21` (294), `_r22` (320), `_r23` (334), `_r24` (347), and the `RULES` table (361–390). R16 is the event-driven exception at 377–381: it has no match/conclusion pair and is skipped by the chainer. Its transport code lives in `kb/base.py:197-271` and `kb/transport.py`.

Excerpt, R07 (lines 87–101):

```python
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
```

- `88–89` a banished ghost means no ghost conclusion should be derived.
- `91–93` only GHOST constraints are relevant; PIT constraints belong to R06.
- `94` removes candidates already known to have no ghost.
- `95` fires only when exactly one candidate remains and it is not already a `Ghost` fact. This is a least-commitment rule: it refuses to guess while two rooms are possible.
- `96` keeps the whole constraint as the premise, so the proof tree can show where the disjunction came from.
- `100–101` converts the one remaining candidate into a ground `Ghost(cell)` fact.

R06 is the same pattern for pits. R08 combines `NoPit` and `NoGhost` into `Safe`. R16’s description is in the table, but its body is not a normal match/conclude pair: the KB calls `apply_shift` directly, which keeps transport atomic and lets it update both facts and constraints. R17’s log/proof note records the actual safe path it used, not just the endpoints.

## 5. `shifting_manor/kb/forward.py` — the engine of the inference

**Purpose.** This is the forward chainer: fixed rule order, repeat until nothing new is added. It returns every firing, including conclusions that the KB later classifies as re-derivations.

**Key functions.** `Binding` (18), `Rule` (24), `forward_chain` (33). `MAX_ITERATIONS = 100` is the loop guard.

Excerpt (lines 33–61):

```python
def forward_chain(kb: KnowledgeBase, rules: Iterable[Rule], turn: int) -> list[Firing]:
    """Fire rules in fixed priority order until no new conclusion appears."""
    firings: list[Firing] = []
    rule_list = list(rules)
    for _ in range(MAX_ITERATIONS):
        changed = False
        for rule in rule_list:
            if rule.event_driven:
                continue  # R16 transport is logged by KnowledgeBase.apply_shift
            assert rule.matches is not None and rule.conclusions is not None
            for binding in list(rule.matches(kb)):
                conclusions: list[Fact | Constraint] = []
                for item in rule.conclusions(kb, binding):
                    if kb.add(item):
                        conclusions.append(item)
                if conclusions:
                    firings.append(
                        Firing(
                            rule.id,
                            tuple(binding.premises),
                            tuple(conclusions),
                            turn,
                            note=binding.note,
                        )
                    )
                    changed = True
        if not changed:
            return firings
    raise AssertionError("forward chaining did not reach a fixpoint")
```

- `37` is the outer fixpoint loop. A new fact can enable an earlier rule, so the chainer runs another full pass.
- `40–41` skips R16: the KB already applied transport before `run()` was called.
- `42` is a guard: every normal rule must have both functions. R16 is the only event-driven rule.
- `43` copies matches into a list; `kb.add` can change the KB while the rule is firing, so iterating a live view would be unsafe.
- `45–47` adds every conclusion unless the KB already has it. `kb.add` returns `False` for duplicates, which is what prevents infinite loops.
- `50–57` records one `Firing` only if at least one conclusion was new. `Binding.note` (line 22) is copied into the firing; R17 uses it for “via safe path: …”.
- `58` marks the pass dirty.
- `59–60` a clean pass is the fixpoint. `61` turns a bug (a rule that keeps adding) into a loud failure instead of a hang.

## 6. `shifting_manor/kb/base.py` — storage, observation, transport, delta

**Purpose.** `KnowledgeBase` is the fact store plus the lifecycle: receive events, apply R16, observe one room, run the chainer, and label conclusions as new or re-derived. It also keeps first-provenance for every fact and constraint.

**Key functions.** `add` (127), `observe` (150), `on_events` (172), `apply_shift` (197), `_transport_fact` (274), `run` (280), `belief_labels` (408).

Excerpt, R16 transport (lines 221–245):

```python
old_base = self.base
old_constraints = self.constraints
new_base, new_constraints = transport(self.base, self.constraints, mapping)
moved_pairs = [
    (old, Fact(old.name, mapping[old.cell], old.value))
    for old in old_base
    if old.name in PIT_GHOST_CELL_FACTS
    and old.cell is not None
    and mapping.get(old.cell, old.cell) != old.cell
]
changed = tuple(
    sorted(
        (set(new_base) - self.base) | (set(new_constraints) - self.constraints),
        key=repr,
    )
)
self.base = set(new_base)
self.constraints = set(new_constraints)
self.derived_prev = {self._transport_fact(f, mapping) for f in self.derived_prev}
premise = Fact("Rotated", value=(wing, direction))
# The rotation event is a leaf: it comes from the engine, not a rule.
self.provenance.setdefault(premise, Firing("GIVEN", (), (premise,), self.turn))
count = len(moved_pairs)
note = f"transported {count} fact{'' if count == 1 else 's'} (wing {wing}, {direction})"
firing = Firing("R16", (premise,), changed, self.turn, note, shift_index=self.shift_count)
```

- `221–223` take a snapshot and compute the moved base facts and constraints.
- `224–230` record only the cell facts whose cell actually changed; these are the “N facts” in the log line.
- `231–236` compute the actual change set for the firing, sorted for reproducible output.
- `237–239` install the transported state and move the previous closure the same way, so the delta comparison is fair.
- `240–245` build the aggregate R16 `Firing`: premise `Rotated(wing, direction)`, all changed conclusions, `shift_index`, and a human note. `pending_firings` is merged into `step.firings`, so Watch AI streams it and the KB tab counts it.
- `248–271` write a per-item R16 provenance edge for every moved fact and constraint. The premises are `(Rotated, old item)`, so a proof can show both the shift event and the pre-shift observation.

Early in the same method, `variant == "b2"` returns immediately (shift-blind), and `variant == "b2b"` drops only facts/constraints touching the rotated wing. B3 is the full transport path.

`run` (280–334) resets `derived` each turn, calls `forward_chain`, compares each conclusion with `derived_prev`, puts only fresh items into `firings`, and puts the complete set into `all_firings`. The UI uses `firings`; tests use `all_firings` to check re-derivations. Durable conclusions are moved into `base` at 326–331, so they survive the next turn.

## 7. `shifting_manor/kb/enumerate.py` — exact risk

**Purpose.** Forward chaining gives certainty and constraints; enumeration turns those constraints into probabilities over the small frontier. It counts complete worlds rather than treating every unknown cell as independent.

**Key functions.** `Model` (16), `risk` (27), `entailed` (32), `enumerate_models` (52), `_finish` (157), `cross_check` (214).

Excerpt (lines 60–67):

```python
no_pit = kb.cell_set("NoPit") | kb.cell_set("Ghost")
known_pits = kb.cell_set("Pit")
pit_constraints = [con.cells for con in kb.constraints if con.kind == "PIT"]
frontier_pits = sorted(
    (set().union(*pit_constraints) if pit_constraints else set()) - no_pit - known_pits
)
pits_left = kb.info.pit_total - len(known_pits)
unknown_rest = set(cells) - no_pit - known_pits - set(frontier_pits)
u_count = len(unknown_rest)
```

- `60` a known ghost room is also pit-free (the generator never stacks them), and `NoPit` is durable after a shift.
- `61` known pits are certain.
- `62–65` the only cells whose pit status interacts are the union of PIT constraints minus cells already ruled out. Everything else is exchangeable “rest”.
- `66` how many pits remain to place.
- `67–68` count the exchangeable rest, which is used as a combinatorial weight.

The exact branch at 81–121 tries every allowed number of frontier pits, checks each combination against every PIT constraint, and weights it by `comb(u_count, pits_left-k)`. Risk is the weighted fraction of worlds containing the cell. If the frontier is larger than 14 or inconsistent, 123–154 uses a documented independence fallback and records a warning. `_finish` (157–211) handles the ghost separately: a known ghost is certain, otherwise the intersection of GHOST constraints gives equiprobable candidates.

`risk(cell)` combines pit and ghost with `1 - (1-pit)(1-ghost)`; the agent uses that single number in A* and in R22.

## 8. `shifting_manor/agents/planner.py` — risk-weighted A*

**Purpose.** A* finds a route from the agent to a goal while charging more for risky cells. It is used twice: a strict safe route through `Safe` cells, and a cautious route that may cross unknown cells for R22.

**Key functions.** `Route` (15), `kb_risk` (25, the old M2 fallback), `astar` (34), `safe_route` (83), `cautious_route` (90), `expected_utility` (111).

Excerpt (lines 59–79):

```python
while frontier:
    _f, g, _, cell, path = heapq.heappop(frontier)
    if cell in goals:
        return Route(list(path), g, len(path) - 1)
    if g > best.get(cell, math.inf):
        continue
    for nxt in neighbours(cell, size):
        if nxt in blocked:
            continue
        risk = min(max(risk_of(nxt), 0.0), 0.999999)
        if risk >= 1.0:
            continue
        edge = 1.0 + lambda_ * (-math.log(1.0 - risk))
        if nxt in avoid:
            edge += avoid_penalty
        new_g = g + edge
        if new_g >= best.get(nxt, math.inf):
            continue
        best[nxt] = new_g
        counter += 1
        heapq.heappush(frontier, (new_g + heuristic(nxt), new_g, counter, nxt, (*path, nxt)))
return None
```

- `59–60` pop the lowest `f`; the path is carried in the tuple so the caller gets the full route.
- `61–62` the first popped goal is optimal.
- `63–64` discard stale queue entries.
- `66–67` blocked cells (`Pit`, `Ghost`, `Unsafe`) are never entered.
- `68–70` clamp risk and refuse a certain death. This is why B3 never steps on a known hazard.
- `71` the edge cost is `1 + -ln(1-risk)`: a 10% risk costs about 1.105, a 50% risk costs about 1.693. The log form is the standard “cost of a survival probability” trick.
- `72–73` adds a soft penalty for the wing the rumble warned about; it is a preference, not a hard block.
- `74–79` standard A* relaxation, with a deterministic counter to break ties.

`safe_route` blocks every cell that is not `Safe` (or the start), so it can only return a route through proven rooms. `cautious_route` leaves the risk cost in place and lets the agent choose a gamble.

## 9. `shifting_manor/agents/kb_agent.py` — the agent loop

**Purpose.** This is the only place where perception, inference, enumeration and planning are ordered. It turns one `Percepts` object plus the events from the previous action into one `Action` and an explanation for the UI.

**Key functions.** `KBAgent.reset` (89), `act` (106), `_absorb` (137), `_sync_globals` (151), `_decide` (159), `_move_to` (211), `_gamble_target` (265), `_fallback` (311), `_thought` (340).

Excerpt (lines 106–131):

```python
def act(self, percepts: Percepts, events: Iterable[Event]) -> Action:
    if self.info is None or self.kb is None:
        raise RuntimeError("reset() before act()")
    events = list(events)
    self.gamble_candidates = []
    self.last_gamble = None
    self.last = Explanation()
    self.kb.on_events(events)
    self._absorb(events)
    self._sync_globals()
    self.kb.observe(percepts)
    self._sync_globals()
    self.model = enumerate_models(self.kb)
    if self.model.warnings:
        for warning in self.model.warnings:
            if warning not in self.kb.warnings:
                self.kb.warnings.append(warning)
    action = self._decide()
    self.last_action = action
    self.last_firings = list(self.kb.firings)
    self.last = Explanation(
        thought=self.last.thought or self._thought(action),
        firings=self.last_firings,
        beliefs=self.kb.belief_labels(),
    )
    return action
```

- `107–108` fail loudly if the sim forgot `reset`; a silently empty KB would look like a bad agent.
- `109` materialises the event iterator once; it is consumed several times below.
- `110–112` clear the previous turn's gamble display and explanation.
- `113` tells the KB about `ShiftApplied`, `Moved`, `PickedUp`, etc. This is where R16 runs.
- `114` updates the agent's own position/oil counters.
- `115` syncs oil, action count, treasure and charm into KB globals before inference.
- `116` feeds percepts into the KB; this calls `observe` and the forward chainer.
- `118` runs exact enumeration after the closure is complete.
- `119–122` records enumeration warnings once.
- `123` chooses the action from the derived goals, in priority order.
- `125–130` freezes the firings and belief labels that Watch AI will replay.
- `131` returns exactly one action.

`_decide` (159–197) order is deliberate: charm if R20 set `CharmAction`, then R18 entrance goal, then R23 retreat, then R19 treasure, then R21 safe exploration, then R22 gamble, then fallback. `_move_to` checks the oil budget before committing; `_budget_ok` (239) requires enough oil to finish the route and return safely.

## 10. `shifting_manor/sim/runner.py` — the evaluation loop

**Purpose.** This file plays many games without a window, records one `GameRecord` per game, and aggregates win rate, score, actions, stars, forced guesses and gamble outcomes.

**Key functions.** `GameRecord` (21), `run_game` (41), `_metrics` (97), `_run_seed_bundle` (126), `run_suite` (141), `format_table` (197), `main` (216).

Excerpt (lines 56–75):

```python
while not game.state.done and steps < max_steps:
    action = agent.act(percepts, events)
    gamble = getattr(agent, "last_gamble", None)
    entry = None
    if gamble is not None:
        forced_guess = True
        entry = {
            "target": list(gamble.target),
            "target_risk": gamble.target_risk,
            "step_cell": list(gamble.step_cell) if gamble.step_cell else None,
            "step_risk": gamble.step_risk,
            "died": False,
        }
        gambles.append(entry)
    result = game.step(action)
    if entry is not None and game.state.outcome in ("died_pit", "died_ghost"):
        entry["died"] = True
    percepts = result.percepts
    events = result.events
    steps += 1
```

- `56` bounded loop; `max_steps=500` prevents a broken agent from hanging the suite.
- `57` is the same agent call a human game uses.
- `58–69` if R22 chose this action, record the target, the target risk and the risk of the first step. This is what makes calibration possible.
- `70–72` play the action and mark the gamble as fatal only if that exact move died.
- `73–75` carry percepts/events into the next turn and count the step.
- If the loop ends without a terminal state, 76–78 labels the game `stalled`.

`run_suite` (141–194) builds identical seeds for every agent, runs them in one process or a `ProcessPoolExecutor`, computes paired McNemar for B3 vs B2/B2b, and stores raw records so the report can be audited. `main` (216) parses `--runs`, `--seed-start`, `--seed-prefix`, `--jobs` and `--out`.

## 11. `shifting_manor/trace.py` — freezing a run for Watch AI

**Purpose.** `build_trace` replays one real game and stores everything the UI needs: every step's firings, beliefs, facts, gamble, action, thought and shift mapping. `TraceStore.proof` turns the stored provenance into a tree; `format_firing` produces the exact log line.

**Key functions.** `StepTrace` (48), `TraceStore` (95), `log_rows` (114), `proof` (130), `build_trace` (142), `format_item` (269), `format_firing` (284), `firing_cells` (291), `_item_node` (330), `_firing_node` (364).

Excerpt, the capture inside `build_trace` (lines 161–210):

```python
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
```

- `161–162` use the real agent, not a scripted demo.
- `163–165` grab the KB and model plus the previous step's beliefs for the “before shift” snapshot.
- `166–176` find a `ShiftApplied` event and record its full mapping and index. The `before` beliefs are how the UI can draw the dashed “transported” outline.
- `177–189` copy one `Belief` per cell, including both risks and the combined risk. `stale` is true for destinations of the rotation.
- `190–210` freeze the step **before** calling `game.step`, so position/action/percepts are the state in which the decision was made. `firings` is the delta; `all_firings` is kept for tests.
- `211–235` play the action and append the completed record with the resulting events and after-position.

The UI never reruns the agent. It reads these frozen records and draws them. That is what “Replaying the agent's actual trace” means.

`format_firing` (284) renders every firing in the same shape: `rule premises => conclusions · note`. R16's note says how many facts moved, and R17's note gives the actual safe path, so neither line is misleading. The proof builder starts from the stored provenance and stops at `PERCEPT`/`GIVEN` leaves, cycles, or items with no recorded derivation.

## 12. `shifting_manor/ui/watch.py` — playback, log, overlay, proof

**Purpose.** `WatchView` owns the Watch AI screen: autoplay, speed, tabs, belief overlay, live delta log, rules list and the proof overlay. It is deliberately a view; it does not inference or mutate the game.

**Key functions.** `WatchView` (60), `duration` (116), `visible_new` (121), `advance` (138), `update` (164), `_key` (205), `_click` (262), `_draw_board` (401), `_draw_belief` (442), `_draw_log` (733), `_visible_log` (788), `_draw_kb` (797), `_draw_proof` (890), `_open_room_proof` (315).

Excerpt, playback update (lines 164–183):

```python
def update(self, dt: float) -> None:
    self._t += dt
    target = 1.0 if self.overlay else 0.0
    if self.overlay_alpha < target:
        self.overlay_alpha = min(1.0, self.overlay_alpha + dt * 5.0)
    elif self.overlay_alpha > target:
        self.overlay_alpha = max(0.0, self.overlay_alpha - dt * 5.0)
    if not self.playing or self.proof is not None:
        return
    self.elapsed += dt
    visible = self.visible_new()
    changed = visible > self._last_visible_new
    self._last_visible_new = visible
    if changed and self.on_fire is not None:
        self.on_fire()
    if self.elapsed >= self.duration():
        if self.index < len(self.store.steps) - 1:
            self.advance()
        else:
            self.playing = False
```

- `165–170` fade the belief overlay in/out independently of playback.
- `171–172` a paused trace or an open proof freezes the clock.
- `173` advance only the current step's clock.
- `174–177` compute how many of this step's firings should be visible; store the count so a new line can trigger the optional sound.
- `178–179` call the optional callback when a new line appears. The app currently passes none; audio polish is explicitly out of scope.
- `180–183` when the step's duration is over, move to the next step or stop at the last one. The app's demo loop watches `finished()` and waits 3 seconds before rebuilding the next trace.

The log at 733–786 lays out only `rows_new`, i.e. `step.firings` filtered to `new=True`. The `_visible_log` slice at 788–795 is the delta stream: previous turns are complete, the current turn grows line by line. The board's gold highlight comes from `firing_cells` (trace.py:291), not from a hard-coded coordinate.

`_open_room_proof` (315) first finds a fact for the clicked room, preferring `Safe`, `Pit`, `Ghost`, `NoPit`, `NoGhost`, `NoTreasure`, then `Visited`, and asks `TraceStore.proof`. The proof overlay draws the resulting `ProofNode` tree and lets a node expand if the chain is deeper than six levels.

## 13. `shifting_manor/__main__.py` and `ui/app.py` — the demo entry point

**Purpose.** `__main__.py` parses the real CLI and forwards every flag. `ui/app.py` owns the scene stack and starts either a human game, Watch AI, or the looping demo.

**Key functions.** `__main__.main` (8) and flags at 10–21; `App.start_watch` (173), `App.start_demo` (191), `App.update` (455), `App._handle_modes` (273), `ui.app.main` (1199).

Excerpt, CLI flags (lines 9–21):

```python
parser = argparse.ArgumentParser(prog="shifting-manor")
parser.add_argument("--mode", choices=["apprentice", "explorer", "haunted"], default=None)
parser.add_argument("--seed", default="HAUNT-4F2A")
parser.add_argument("--windowed", action="store_true", default=True, help="windowed (the default)")
parser.add_argument("--fullscreen", action="store_true", help="use the whole screen")
parser.add_argument("--no-audio", action="store_true")
parser.add_argument("--frames", type=int, default=None, help="run N frames then exit")
parser.add_argument("--screenshot", default=None, help="save the final frame as a PNG")
parser.add_argument("--demo", action="store_true", help="start Watch AI and loop the demo seeds")
```

- `10` `--mode` is optional; leaving it out opens the title/mode-select flow.
- `11` the default seed is the one used in the docs and screenshots.
- `12–14` windowed is the default; `--windowed` remains an explicit no-op for scripts.
- `15` fullscreen is opt-in.
- `16` `--no-audio` is accepted even though Watch AI has no audio polish in M5.
- `17–18` frame limit and screenshot path are the CI/demo escape hatch.
- `19–21` `--demo` bypasses the menu and starts the looping Watch AI sequence.

`start_demo` (191–198) builds the sequence `[given seed, HAUNT-7C1D, HAUNT-5D7C]` unless the given seed is already one of them. `update` (455–466) watches `watch.finished()`, counts three seconds, then calls `start_watch` for the next seed. `ui.app.main` (1199–1217) forwards `demo` and makes `--screenshot` without `--frames` render one frame.

## Suggested 20-minute reading plan

1. `engine/types.py:16-72` and `engine/game.py:149-164` — what a turn is.
2. `kb/facts.py:52-84` and `kb/rules.py:87-101` — what a fact and a rule look like.
3. `kb/forward.py:33-61` — how rules combine (and why R16 is skipped).
4. `kb/base.py:197-334` — event-driven transport and delta.
5. `kb/enumerate.py:60-121` — where probabilities come from.
6. `agents/planner.py:59-79` and `agents/kb_agent.py:106-131` — how a probability becomes a move.
7. `trace.py:161-235` and `ui/watch.py:164-183` — how the demo replays it.
8. `sim/runner.py:56-75` — how the table in `docs/EVALUATION.md` is produced.

If you can explain those eight stops, you can explain the project.
