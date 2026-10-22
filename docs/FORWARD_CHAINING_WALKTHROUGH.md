# Forward-chaining walkthrough: HAUNT-4F2A, Explorer, B3

This is the trace the Watch AI screen replays. It is one real game, not a hand-built example. The seed is `HAUNT-4F2A`, the mode is Explorer, and the agent is B3 (full R16 transport).

**Turn numbering.** The KB stores `Firing.turn` as a **0-based** index. The UI adds one before drawing it. So the rule event below labelled **T13** is shown as **TURN 14** on screen, and the charm at **T17** is **TURN 18**. This document uses the KB's 0-based turns so it matches the raw firings and the proof tree.

The run lasts 34 actions and ends `escaped_treasure` with score 1157. The interesting part is T07–T13: a ghost clue, a rotation, a transport, and one final deduction.

## 1. The short version

```
T07  Chill(2,1)  -> R05: GHOST constraint {(1,1),(2,0),(2,2),(3,1)}
T08  shift #1, wing 1 clockwise
     R16: (3,1) -> (4,2), so the constraint becomes
          GHOST {(1,1),(2,0),(2,2),(4,2)}
     R16 also moves NoPit(3,1) -> NoPit(4,2)
T09  NoChill(3,0) -> NoGhost(3,1), not a candidate of the moved constraint
T11  Breeze+Chill(3,2) -> a second GHOST constraint and Pit(3,3)
T13  NoChill(4,1) -> NoGhost(4,2)
     The moved constraint now has only (2,2) without NoGhost
     R07: GHOST{(1,1),(2,0),(2,2),(4,2)} => Ghost(2,2)
T17  At(5,2), Ghost(2,2) is west in a straight line
     R20: => CharmAction='W'
     Agent: CastCharm(W), ghost banished
```

The transport is the step that makes T13 possible: the candidate that was at `(3,1)` before the rotation is now at `(4,2)`. The later `NoGhost(4,2)` removes it, leaving `(2,2)`.

## 2. Facts before and after each turn

"Before" means the durable closure at the end of the previous turn. "After" lists only the new facts and constraints that matter to this story; the full closure also contains `At`, `Visited`, `NoTreasure`, `Reachable` and other bookkeeping facts.

### T07 — first ghost clue

Position `(2,1)`. Percepts: no breeze, **chill**, no glimmer. Action: `Move(S)` to `(2,0)`.

| | Facts / constraints |
|---|---|
| Before | `At(2,1)`, `Safe(3,0)`, `NoPit(2,2)` not yet known |
| New after | `NoPit(2,2)`, `NoPit(3,1)` from R02; `GHOST{(1,1),(2,0),(2,2),(3,1)}` from R05; `NoTreasure(2,2)`, `NoTreasure(3,1)` from R13; `GoalSafe(3,0)` from R21 |

Why R05: a chill at `(2,1)` means the living ghost is in one of the four neighbours. The rule does not guess which one. It stores the four candidates as one constraint. The constraint, not a `Ghost` fact, is the honest conclusion.

### T08 — the first shift, and R16

The move at T07 entered `(2,0)` and triggered shift #1: wing 1, clockwise. Position `(2,0)`. Action: `Move(E)` to `(3,0)`.

The rotation mapping includes:

```
(3,1) -> (4,2)
```

R16 rewrites every pit/ghost fact and every PIT/GHOST constraint through that mapping. It is event-driven, not a normal rule match; the forward chainer skips R16 because the KB calls `apply_shift` when it receives `ShiftApplied`.

| | Facts / constraints |
|---|---|
| Before | `GHOST{(1,1),(2,0),(2,2),(3,1)}`, `NoPit(3,1)` |
| New after | `GHOST{(1,1),(2,0),(2,2),(4,2)}`, `NoPit(4,2)`, `NoPit(3,2)`, `NoGhost(3,2)`; plus `Safe(3,2)` from R08 and the normal observation facts |

The logged R16 line is one aggregate event with the rotation as its premise:

```
R16 Rotated(1, cw) => GHOST{(1,1),(2,0),(2,2),(4,2)}, NoGhost(3,2), NoPit(3,2), NoPit(4,2) · transported 3 facts (wing 1, cw)
```

The three **facts** are the moved cell facts. The constraint is rewritten as well but is shown in the same firing's conclusion tuple. `Rotated(1, cw)` is stored as a `GIVEN` leaf, and every moved fact/constraint gets its own R16 provenance edge whose premises are the rotation and the old item. That is how the proof below can show the move and still continue into the pre-shift observation. The `(3,1) -> (4,2)` example is the one that matters below.

### T09 — one candidate becomes known

Position `(3,0)`. Percepts: no breeze, no chill. Action: `Move(N)` to `(3,1)`.

| | Facts / constraints |
|---|---|
| New after | `NoPit(3,1)`, `NoPit(4,0)`, `NoGhost(3,1)`, `NoGhost(4,0)`; `Safe(3,1)`, `Safe(4,0)`; `GoalSafe(3,1)` |

The agent learns `NoGhost(3,1)`. That fact would have eliminated the pre-shift candidate `(3,1)`, but the rotation has already moved that candidate to `(4,2)`. The transported constraint still has `(4,2)` as an open candidate.

### T10 — walking north

Position `(3,1)`. Percepts: no breeze, no chill. Action: `Move(N)` to `(3,2)`.

| | Facts / constraints |
|---|---|
| New after | `NoPit(4,1)`, `NoGhost(4,1)`, `Safe(4,1)`, `GoalSafe(3,2)` |

No new ghost information. This turn is here because it puts the agent at `(3,2)`, where the next observation happens.

### T11 — breeze and chill together

Position `(3,2)`. Percepts: **breeze** and **chill**. Action: `Move(S)` to `(3,1)`.

| | Facts / constraints |
|---|---|
| New after | `PIT{(2,2),(3,1),(3,3),(4,2)}` from R04; `GHOST{(2,2),(3,1),(3,3),(4,2)}` from R05; `Pit(3,3)` from R06; `Unsafe(3,3)` from R09; `NoTreasure(4,2)` from R13; `GoalSafe(4,1)` from R21 |

R06 can resolve the new PIT constraint because three of its cells are already excluded by `NoPit` (`(2,2)`, `(3,1)`, `(4,2)`), leaving `Pit(3,3)`.

The new GHOST constraint is **not** resolved; all four cells are still possible ghost rooms as far as this constraint is concerned. The older transported GHOST constraint is also still live.

### T12 — no new firings

Position `(3,1)`. Action: `Move(E)` to `(4,1)`.

The KB re-derives previous conclusions, but the delta log is empty. This is deliberate: the Watch AI log streams only new firings, so this turn has no line. (The raw trace keeps the re-derivations for debugging; the UI does not show them.)

### T13 — Ghost(2,2)

Position `(4,1)`. Percepts: no breeze, no chill. Action: `Move(S)` to `(4,0)`.

| | Facts / constraints |
|---|---|
| Key new facts | `NoPit(5,1)`, `NoGhost(4,2)`, `NoGhost(5,1)`, `Safe(4,2)`, `Safe(5,1)`, `Ghost(2,2)`, `Unsafe(2,2)` |
| Other new facts | `R10` marks every other cell `NoGhost`; `Reachable(4,2)`, `Reachable(5,1)`; `GoalSafe(4,0)` |

The critical rule is R07:

```
R07 Constraint(GHOST, {(1,1),(2,0),(2,2),(4,2)}) => Ghost(2,2)
```

Why it fires now:

1. `(1,1)` and `(2,0)` were already `NoGhost` (they were visited/safe earlier).
2. R03 at T13 turns `NoChill(4,1)` into `NoGhost(4,2)`.
3. That leaves only `(2,2)` in the transported GHOST constraint.
4. R07 sees one candidate and concludes `Ghost(2,2)`.

R08 also uses the transported `NoPit(4,2)` plus the new `NoGhost(4,2)` to derive `Safe(4,2)`. That is consistent with the elimination, but R07 fires before R08 in the fixed rule order; the elimination of `(4,2)` for R07 comes from `NoGhost`, not from `Safe`.

This is the exact proof tree stored in the trace:

```
Ghost(2,2)                                  R07, one candidate left
└── GHOST{(1,1),(2,0),(2,2),(4,2)}          R16 shift #1
    ├── Rotated(1, cw)                      event, T08
    └── GHOST{(1,1),(2,0),(2,2),(3,1)}      R05, Chill(2,1)
        └── Chill(2,1)                       percept, T07
```

The dashed outline in the UI marks `(4,2)` as a transported belief: the room moved through the rotation, but the belief moved with it. The old `(3,1)` candidate is not silently kept; R16 replaced it.

### T17 — why the charm goes west

Position `(5,2)`. The ghost has been at `(2,2)` since T13. The agent is on the same row, to the east.

| | Facts |
|---|---|
| Before | `Ghost(2,2)`, `At(5,2)`, charm available |
| New after | `CharmAction='W'` from R20; `GoalSafe(4,2)` from R21 |
| Action | `CastCharm(W)` |

R20 checks whether the ghost is in a straight line in one of the four directions. It is: `(2,2)` is west of `(5,2)`. The agent casts west, the game emits `CharmCast` and `GhostBanished`, and the ghost is removed. The later route picks up the heirloom at `(5,4)` and leaves by the entrance. If the agent had instead walked into `(2,2)`, it would have died.

## 3. Why this is forward chaining, not a lookup table

Every line above is data-driven. The chainer starts from percepts and known facts, tries rules in fixed priority order R01…R24, adds only conclusions that are not already present, and repeats until a full pass adds nothing. The T13 firing exists because three independent facts happen to meet:

- a GHOST constraint created at T07,
- the R16 mapping at T08,
- a `NoGhost` observation at T13.

No rule contains the answer `Ghost(2,2)`. The answer is a consequence of the constraint plus the observations.

The same code path is used for pits, treasure and goals. Watch AI does not rerun a special animation: it replays the stored `StepTrace` from `shifting_manor/trace.py` and draws `step.firings`.

## 4. Files to read next

- `shifting_manor/kb/rules.py:62-101` — R05, R06 and R07, the constraint-to-fact rules.
- `shifting_manor/kb/base.py:197-271` — R16 transport, aggregate firing and per-item provenance.
- `shifting_manor/kb/forward.py:33-61` — the fixed-priority fixpoint loop and the event-driven R16 skip.
- `shifting_manor/trace.py:142-266` — how this run is frozen into `StepTrace` records.
- `docs/CODE_TOUR.md` — the full reading order.
