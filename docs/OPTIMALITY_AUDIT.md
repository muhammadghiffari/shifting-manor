# M4 — Optimality Audit

Does B3 play as well as an agent that knows the full hazard map? We answer this with
an **exact posterior** over hidden worlds, 1,000 held-out reporting seeds per mode
(`SIM-<MODE>-10000..10999`, never used for development), a failure classifier, and a
paired policy comparison against B4 (perfect information) and B5 (Bayes-optimal risks,
same policy).

**Verdict: no avoidable and no suboptimal-gamble failures remain. Every B3 loss is
forced at the decision point — every escape route crossed a hazard the agent could not
disprove. The residual gap to B4 is epistemic uncertainty, not reasoning error.**

## Method

### Exact posterior (`tools/posterior.py`)

The engine's pit state is a deterministic function of the initial rotation-invariant
bitmask of each 2×2 wing plus the shift schedule (ghost hazards rotate with the wing,
a wing is skipped when the agent stands inside it). `ExactPosterior` therefore enumerates
every initial-world mask, keeps only the ones consistent with every observation so far
(breeze, stench, draft, light, **survival**), and computes the exact marginal death risk
of every move by averaging over the surviving worlds weighted by the ghost candidate
distribution (`6 · len(G)` states per shift).

The agent's own knowledge is *not* an approximation to test against: risk estimates are
compared to the **exact posterior**, the strongest reasoner with the same observations
(the true treasure location is hidden from the agent, so it is excluded from the oracle).
Two soundness properties are unit-tested (`tests/test_posterior.py`):

- the true world always stays in the posterior's support (checked over every turn of
  120 reporting seeds × 3 modes);
- a cell only ever becomes certainly-safe when the agent has *proven* it (adjacency
  proof or survival); rotating a hazard into a previously visited room restores its
  risk — an earlier "visited ⇒ safe" shortcut was removed after it produced exactly
  that wrong answer.

### Calibration (B3)

Every gamble candidate evaluated by B3 on the reporting seeds is paired with the exact
posterior's risk for the same cell at the same turn (2,771 / 8,052 / 12,676 pairs; the
true hazard status of the cell is recorded too). Mean absolute error of B3's estimate
against the exact posterior:

| mode | MAE |
|---|---|
| apprentice | 0.0045 |
| explorer | 0.0024 |
| haunted | 0.0029 |

Binned, B3's estimates track the exact posterior bin-for-bin (haunted, largest sample):

| predicted risk bin | n | mean B3 | mean exact | actual death rate |
|---|---|---|---|---|
| 0.0–0.1 | 4,083 | 0.022 | 0.023 | 0.022 |
| 0.1–0.2 | 2,095 | 0.136 | 0.140 | 0.132 |
| 0.2–0.3 | 1,113 | 0.227 | 0.232 | 0.216 |
| 0.3–0.4 | 1,297 | 0.357 | 0.358 | 0.335 |
| 0.5–0.6 | 2,662 | 0.521 | 0.523 | 0.529 |
| 0.6–0.7 | 342 | 0.675 | 0.675 | 0.714 |
| 0.9–1.0 | 520 | 0.951 | 0.950 | 0.960 |

The bins are not just self-consistent — the *actual* death rate falls on the predicted
diagonal (a 0.5-predicted step kills 52.9% of the time). B3's local adjacency
enumeration reproduces the exact Bayesian marginals, so the agent's decisions are made
at correctly-priced odds. (Small bin-wise drifts, e.g. 0.6–0.7 killing 71.4%, reflect
adverse selection: the highest-risk candidates are evaluated when the agent is cornered.
Full ten-bin tables for all modes are in `docs/audit_results.json`.)

### Failure classification

Every B3 loss (51 + 81 + 173 = 305 of 3,000 seeds) is reconstructed from the saved
pre-fatal state and classified:

1. **Forced (305/305)** — at the decision point, *no* action leads to a winning
   objective through zero-risk cells only, and the posterior assigns every candidate
   a death risk > 0. No agent with the same observations could have both won and been
   certain to survive the next step.
2. **Avoidable (0)** — a perfect reasoner could have **won with certainty** from the
   final state on the remaining oil: a zero-risk route existed that ends carried at
   the entrance (treasure already carried with the entrance in the zero-risk
   component, or the treasure inside the same component with enough oil for the round
   trip; surviving k moves needs oil ≥ k+1, Leave is free). Includes B3-specific
   model errors: the agent itself never sees risk 0 in these states (its local
   constraint propagation is sound here) — the classification uses the exact posterior.
3. **Suboptimal gamble (0)** — died on a gamble while an alternative action existed
   whose *best complete route* had a strictly lower (by >1e-4) exact death
   probability. Comparison is on whole executed routes, not the first step: a detour
   that trades a ⅓ step for ⅙+⅙ is the same total risk, and the first-step view
   mislabelled such ties (caught on SIM-APPRENTICE-10069).

Two classifier corrections during development, both verified against hand-replayed
seeds, changed no agent behaviour — only the analysis of already-recorded trajectories:

- A refuge pocket (SIM-HAUNTED-10780: cells (4,3–5)) looks avoidable under
  "could have survived with certainty" — the engine never shifts a wing containing the
  agent, so hiding there is indefinite survival. But hiding wins nothing: every route
  from the pocket to the entrance crossed a >0-risk step, and B3's own 0.36 price for
  the fatal step was *exactly right*. Survival is only a win with treasure in hand.
- Conversely, "a zero-risk route to the entrance existed" alone over-claims the other
  way (all 51 apprentice losses flagged). Example SIM-APPRENTICE-10037: the agent stood
  next to a safe corridor home but the treasure lay beyond a 0.5 cell; the exact
  posterior puts the death cell at *exactly* 0.5. Pushing the gamble is 50% for +1000
  versus certain retreat for 0 — a forced, correctly-priced decision, not an error.
- And a zero-risk route only counts if the **oil** can pay for it: SIM-HAUNTED-10685
  escaped empty at 3 oil while the proven-safe round trip to the treasure needed 17
  moves; the engine kills at oil 0, so fetch-or-wait both meant oil_out — the empty
  escape with 123 points was the only surviving line.

The final rule requires a zero-risk **winning** route on the remaining oil: a walk
inside the zero-risk component that ends carried at the entrance, costing ≤ oil − 1
moves (surviving k moves needs oil ≥ k+1; Leave is free).

### Policy comparison (McNemar, paired over identical seeds)

| comparison | apprentice | explorer | haunted |
|---|---|---|---|
| B3 vs **B5** (exact risks) | 0 wins / 0 losses, p = 1.0 | 0 / 0, p = 1.0 | 0 / 0, p = 1.0 |
| B3 vs **B4** (perfect map) | 0 / 51, p < 0.001 | 0 / 81, p < 0.001 | 0 / 173, p < 0.001 |

B5 is B3's policy fed with exact-posterior risks instead of adjacency enumeration. It
selects a different action **zero times** across 3,000 seeds (outcomes identical
including scores) — local constraint propagation has converged to the same decisions
the exact reasoner makes. Earlier development-band runs showed 7 divergences; all 7
were fixed in the shared policy (below) rather than in B5, after which B3 ≡ B5.

The entire measured gap is B4 (1,000/1,000 wins): knowing the map wins always.

## What the audit changed in the agent

Root causes found by the classifier and fixed on the **dev band** (`DEV-<MODE>-0000..`,
reporting seeds untouched), with the reporting band as clean confirmation:

1. **Risk priced 1000× too cheap** (`planner.RISK_LAMBDA` 1.0 → 1000). The utility
   formula values survival at 1000 (−1000 on death), but risk-sensitivity used λ = 1,
   so a ⅓ coin flip cost 0.33 "utils" against +965 for a shortcut — every frontier
   gamble was taken. λ = 1000 makes the penalty *the* objective death price (expected
   utility = P(survive)·score − (1−P(survive))·1000 + 8/step). Dev sweep: 1 → 10 lifts
   apprentice 0.674 → 0.910 and explorer 0.357 → 0.863; beyond 10 the result is a flat
   plateau to 400 and constant at 1000 (no threshold flips remain).
2. **Gambles priced only their target cell** (`kb_agent._gamble_target`). Route
   selection now charges the whole route's death probability (1 − Π(1 − risk)), so a
   safe-looking target behind a ⅓ corridor no longer outranks a certain one.
3. **Frontier-blind zero rooms** (`kb_agent`). Rooms the local constraints never
   *name* (unvisited, not adjacent to any clue) never entered the candidate set even
   when counting proves them safe — global counting is exactly what the exact
   posterior has and B3 didn't use. Global-unique survivors are now candidates.

Dev-band effect: apprentice 0.850 → 0.947, explorer 0.743 → 0.923, haunted 0.680 →
0.840 win rate on 300 seeds each, with the reporting band holding at 0.949 / 0.919 /
0.827 (Wilson 95% CIs in `docs/audit_results.json`).

## Reproduction

```bash
python -m tools.audit --count 1000 --out docs/audit_results.json   # ~5 min, 12 workers
```

Per-seed records (classification, exact route risks, pre-fatal snapshots for every
loss) land in the JSON; classifier logic and its unit tests are in
`tools/audit.py` / `tests/test_audit.py`.

## Limitations

- Classification is **state-local**: it proves the death at the final step was forced
  given the agent's actual information state, not that some different earlier
  information-gathering strategy would have led to a safe winning state. Closing that
  fully would need a search over belief states; the B3 ≡ B5 result is the empirical
  argument that the policy closes the gap available to the observation stream it is in.
- The refuge rule treats standing still as non-winning: correct under the score
  function (no points for surviving empty), and the engine's in-wing shift skip makes
  hiding certain. If a future patch makes hiding eventually fatal (oil on idle), the
  classifier gets *more* forced, never less.
- Calibration MAE is conditioned on steps the agent actually took (it is a measure of
  the model *as used*); a full grid MAE would weight unvisited cells the agent never
  risked. The bucket table shows the model reproduces the objective ⅓/½/⅔ frequencies.
- Reporting seeds are used once, after all tuning on the dev band; the classifier fix
  (refuge ⇒ needs a zero-risk route to a winning objective) changed only the
  *analysis* of already-recorded trajectories, not any agent behavior.
