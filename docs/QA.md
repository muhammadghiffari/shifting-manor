# Q&A for the lecturer

Short answers with the file and line to open if asked to prove it.

### 1. Why forward chaining and not backward chaining?

Forward chaining starts from what the agent perceives and derives everything that follows. Backward chaining would need a goal query and would repeatedly work back from “safe route”; the agent needs the whole closure anyway because a shift can invalidate and reopen beliefs. The chainer is fixed-priority and runs to a fixpoint in `shifting_manor/kb/forward.py:31-52`; the 24 rules are the table in `shifting_manor/kb/rules.py:348-378`.

### 2. What does exact enumeration add that the rules do not?

The rules produce certainties (`Safe`, `Pit`, `Ghost`) and disjunctions (constraints). They do not assign probabilities. `enumerate_models` (`shifting_manor/kb/enumerate.py:52`) counts complete pit placements over the frontier and returns per-cell risk, so A* can prefer a 10% room over a 50% room even when neither is proved safe.

### 3. How is the risk percentage computed?

For pits, the code enumerates frontier combinations, weights each by `comb(unknown_rest, pits_left-k)`, and divides by the total weight (`shifting_manor/kb/enumerate.py:81-121`). For the ghost, it uses the intersection of GHOST constraints and assigns equal probability to the remaining candidates (`enumerate.py:168-199`). `Model.risk` combines them as `1 - (1-pit)(1-ghost)` (`enumerate.py:27-30`).

### 4. What exactly does R16 do?

On a `ShiftApplied` event, R16 applies the same cell mapping that the engine used to rotate the wing. It moves pit/ghost cell facts and rewrites PIT/GHOST constraints atomically, then records provenance for the proof tree (`shifting_manor/kb/base.py:197-258`). It is event-driven, not a normal rule body; the placeholder is `shifting_manor/kb/rules.py:364-369`. The walkthrough's `(3,1) -> (4,2)` example is in `docs/FORWARD_CHAINING_WALKTHROUGH.md`.

### 5. Why not reinforcement learning?

The brief asks for a rule-based, explainable agent. This agent's action is selected from explicit derived facts and routes (`shifting_manor/agents/kb_agent.py:159-197`), and every conclusion has a firing and a proof tree. There is no training loop, reward model or learned weights to explain. RL was recorded as optional and out of scope in `DECISIONS.md:35`.

### 6. What is the difference between B2, B2b and B3?

B2 is shift-blind: on a shift it keeps its old KB (`shifting_manor/kb/base.py:199-200`). B2b drops the facts and constraints that touch the rotated wing but does not transport the rest (`base.py:203-220`). B3 transports every affected fact and constraint (`base.py:221-258`). In Apprentice there are no shifts, so all three are identical.

### 7. Is B3 really better than B2?

Yes for this 200-seed reporting set. B3 wins 91.5% vs 77.5% on Explorer and 82.5% vs 66.0% on Haunted; the paired McNemar p-values are 1.8e-6 and 6.3e-8 (`docs/EVALUATION.md:61`). The full table and CIs are in `docs/EVALUATION.md:23-57`.

### 8. Is B2b better than B2?

Not shown at 200 seeds. B2b is 6.0 pp higher on Explorer and 3.0 pp higher on Haunted, but the CIs overlap and the paired p-values are 0.052 and 0.377 (`docs/EVALUATION.md:62`). The honest claim is “not distinguishable here”, not “B2b is better”.

### 9. Does B3 cheat by seeing the real map?

No. B3 receives only percepts and events (`shifting_manor/agents/kb_agent.py:106-131`); the engine creates percepts from the agent's current room (`shifting_manor/engine/game.py:128-147`). The oracle is the only agent that regenerates the true map, and it is used only as an upper bound/par baseline (`shifting_manor/agents/oracle.py:37-42`).

### 10. What happens to beliefs after a shift?

The engine emits `ShiftApplied` with the exact mapping. B3's KB applies R16 before the next inference pass, moves durable pit/ghost facts and constraints, and keeps the moved facts' provenance (`shifting_manor/kb/base.py:172-188,197-258`). The Watch overlay marks destination cells as `stale` and draws the dashed transported outline (`shifting_manor/trace.py:185`, `shifting_manor/ui/watch.py:442-478`).

### 11. Why does the log not show every rule firing?

Because many R08/R17 conclusions are re-derived every turn. `KnowledgeBase.run` separates fresh conclusions (`firings`) from the complete set (`all_firings`) (`shifting_manor/kb/base.py:266-320`). Watch AI builds `rows_new` from `new=True` only (`shifting_manor/ui/watch.py:105-108,788-795`). The complete set is kept for tests and debugging; the log filter UI was dropped for M5.

### 12. How does the “Why?” proof tree work?

Every fact and constraint stores its first `Firing`; percepts are leaves. `TraceStore.proof` recursively expands `premises` until it reaches a percept/given leaf or a cycle (`shifting_manor/trace.py:327-358`). Clicking a room or log row opens the tree (`shifting_manor/ui/watch.py:262-321,890`). The `Ghost(2,2)` tree in the demo has four levels and includes the R16 hop.

### 13. What are the main limits and assumptions?

The generator guarantees a hazard-free route exists, but the agent does not know it (`shifting_manor/engine/generator.py:27-53`). Risk uses a small frontier and a documented fallback above 14 cells (`shifting_manor/kb/enumerate.py:71-76`). R22 forced guesses are reported, not hidden (`shifting_manor/sim/runner.py:58-72`). The evaluation is 200 seeds, so small effects are uncertain (`docs/EVALUATION.md:77-86`).

### 14. Why 200 seeds, and how should the confidence intervals be read?

200 same-seed games per mode are enough to show the large B3-vs-B2 gap, but not a 3–6 pp B2b effect. The table uses 95% Wilson intervals for each win rate and paired McNemar tests for the comparisons (`docs/EVALUATION.md:7-21,46-57`). “Not significant” means “not shown with this sample”, not “proved equal”. The raw records are in `sim/results.json`.

### 15. How do I reproduce the demo, the table and the tests?

```
python -m shifting_manor --windowed --seed HAUNT-4F2A
python -m shifting_manor --demo --windowed --seed HAUNT-4F2A
python -m shifting_manor.sim --runs 200 --out sim/results.json
pytest -q
ruff check . && ruff format --check .
```

The CLI flags are in `shifting_manor/__main__.py:9-21`; the demo loop is `shifting_manor/ui/app.py:191-198`; the subprocess tests (including `--demo`) are `tests/test_entrypoint.py:30-54`; CI runs the same commands in `.github/workflows/ci.yml:15-24`.

## If the lecturer asks for one sentence

> It is a forward-chaining knowledge base with exact risk enumeration and A*; the Watch AI screen is a replay of the real trace, and the evaluation shows the transport-enabled B3 clearly beats the shift-blind B2.
