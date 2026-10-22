# Evaluation

This is the M5 reporting-set evaluation. It is deliberately blunt about what 200 seeds can and cannot show. The raw runs are in `sim/results.json`.

## 1. Protocol

- **200 seeds per mode, same seed for every agent.** Seeds are `SIM-<MODE>-0000` … `SIM-<MODE>-0199`. Every agent sees the same generated map, shift schedule and hazard layout.
- **Win** means `escaped_treasure`. An empty-handed escape is counted separately and earns one star, not a win.
- **95% Wilson score intervals** are reported for every win rate.
- **Paired comparisons** use the two-sided McNemar test on the same seeds, with continuity correction. The table reports discordant wins (`A`-only / `B`-only) and the p-value.
- **Forced guess.** A game is a forced-guess game if at least one action was chosen by the R22 gamble branch, i.e. the KB had no safe goal, no known-safe treasure route and no safe entrance route. B0, B1 and the oracle have no R22 branch, so their rate is shown as 0% rather than a meaningful rate.
- **B2 / B2b / B3.** B2 is shift-blind. B2b drops beliefs in the rotated wing and does not transport. B3 applies R16 transport and keeps the moved conclusions.
- **Stars.** Par is the oracle's action count on the same seed. 3 stars = escaped with the heirloom within par + 15; 2 stars = a slower heirloom escape; 1 star = empty-handed escape; 0 stars = death or stall.

Reproduce the table:

```
python -m shifting_manor.sim --runs 200 --out sim/results.json
```

`--jobs 8` only changes wall-clock time. The seed list and results are identical.

## 2. Reporting set (200 seeds per mode)

| Mode | Agent | Wins / n | Win % (95% Wilson CI) | Escaped any | Mean score | Mean actions | Mean stars | Forced-guess games |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Apprentice | B0 | 10 / 200 | 5.0% [2.7, 9.0] | 5.0% | −896.9 | 10.0 | 0.14 | 0.0% |
| Apprentice | B1 | 7 / 200 | 3.5% [1.7, 7.0] | 3.5% | −933.3 | 8.3 | 0.09 | 0.0% |
| Apprentice | B2 | 189 / 200 | 94.5% [90.4, 96.9] | 94.5% | 998.3 | 12.3 | 2.81 | 32.0% |
| Apprentice | B2b | 189 / 200 | 94.5% [90.4, 96.9] | 94.5% | 998.3 | 12.3 | 2.81 | 32.0% |
| Apprentice | B3 | 189 / 200 | 94.5% [90.4, 96.9] | 94.5% | 998.3 | 12.3 | 2.81 | 32.0% |
| Apprentice | Oracle (B4) | 200 / 200 | 100.0% [98.1, 100.0] | 100.0% | 1156.4 | 8.0 | 3.00 | 0.0% |
| Explorer | B0 | 9 / 200 | 4.5% [2.4, 8.3] | 4.5% | −920.9 | 14.3 | 0.13 | 0.0% |
| Explorer | B1 | 7 / 200 | 3.5% [1.7, 7.0] | 3.5% | −943.7 | 13.7 | 0.07 | 0.0% |
| Explorer | B2 | 155 / 200 | 77.5% [71.2, 82.7] | 77.5% | 617.0 | 21.9 | 2.09 | 42.5% |
| Explorer | B2b | 167 / 200 | 83.5% [77.7, 88.0] | 83.5% | 738.5 | 22.7 | 2.26 | 51.5% |
| Explorer | B3 | 183 / 200 | 91.5% [86.8, 94.6] | 91.5% | 903.8 | 24.1 | 2.40 | 47.0% |
| Explorer | Oracle (B4) | 200 / 200 | 100.0% [98.1, 100.0] | 100.0% | 1154.3 | 11.9 | 3.00 | 0.0% |
| Haunted | B0 | 9 / 200 | 4.5% [2.4, 8.3] | 4.5% | −921.5 | 12.8 | 0.13 | 0.0% |
| Haunted | B1 | 6 / 200 | 3.0% [1.4, 6.4] | 3.0% | −946.5 | 11.5 | 0.08 | 0.0% |
| Haunted | B2 | 132 / 200 | 66.0% [59.2, 72.2] | 66.0% | 375.3 | 20.0 | 1.82 | 51.5% |
| Haunted | B2b | 138 / 200 | 69.0% [62.3, 75.0] | 71.0% | 468.9 | 21.9 | 1.90 | 59.0% |
| Haunted | B3 | 165 / 200 | 82.5% [76.6, 87.1] | 83.0% | 728.6 | 23.3 | 2.21 | 54.0% |
| Haunted | Oracle (B4) | 200 / 200 | 100.0% [98.1, 100.0] | 100.0% | 1146.5 | 12.1 | 3.00 | 0.0% |

### Paired tests

| Mode | Comparison | A-only wins | B-only wins | McNemar χ² | p |
|---|---|---:|---:|---:|---:|
| Explorer | B3 vs B2 | 30 | 2 | 22.78 | 1.8 × 10⁻⁶ |
| Explorer | B3 vs B2b | 18 | 2 | 11.25 | 8.0 × 10⁻⁴ |
| Explorer | B2b vs B2 | 22 (B2b) | 10 (B2) | 3.78 | 0.052 |
| Haunted | B3 vs B2 | 34 | 1 | 29.26 | 6.3 × 10⁻⁸ |
| Haunted | B3 vs B2b | 28 | 1 | 23.31 | 1.4 × 10⁻⁶ |
| Haunted | B2b vs B2 | 19 (B2b) | 13 (B2) | 0.78 | 0.377 |

Apprentice has no shifts, so B2, B2b and B3 are identical there: zero discordant pairs and p = 1.

## 3. What these 200 seeds show

- **B3 clearly beats B2.** The gap is 14.0 pp on Explorer (91.5% vs 77.5%) and 16.5 pp on Haunted (82.5% vs 66.0%). The paired tests are p = 1.8 × 10⁻⁶ and 6.3 × 10⁻⁸. This is the result the project claims.
- **B2b vs B2 is not distinguishable at 200 seeds.** B2b is 6.0 pp higher on Explorer (83.5% vs 77.5%) and 3.0 pp higher on Haunted (69.0% vs 66.0%), but the confidence intervals overlap heavily and the paired p-values are 0.052 and 0.377. The Explorer result is borderline, not significant at the 5% level. We do **not** claim B2b is better than B2 from this run.
- **B3 also clearly beats B2b** (91.5% vs 83.5%, p = 8.0 × 10⁻⁴ on Explorer; 82.5% vs 69.0%, p = 1.4 × 10⁻⁶ on Haunted). R16 transport is doing real work beyond simply forgetting the rotated wing.
- **The oracle is an upper bound, not a fair opponent.** It knows the true map, so its 100% is expected and is used only to set par and to prove the game is winnable on every seed.
- **Apprentice has no shifts.** B2, B2b and B3 are exactly the same agent there, which is why all three have 189 wins and identical score/action/star columns. Any difference would indicate a bug.

## 4. Stars (B3)

| Mode | 3★ | 2★ | 1★ | 0★ | 3★ share of heirloom escapes |
|---|---:|---:|---:|---:|---:|
| Apprentice | 185 | 4 | 0 | 11 | 97.9% |
| Explorer | 115 | 68 | 0 | 17 | 62.8% |
| Haunted | 110 | 55 | 1 | 34 | 66.7% |

The top rating is easy on Apprentice because the oracle is already close to optimal there. On the shifting modes about three in five B3 heirloom escapes are within par + 15. The threshold was fixed before this run; it was not tuned to make the table look better.

## 5. Honest limits

- **200 seeds is enough for the B3 claim, not for small B2b effects.** With 200 paired games, a 6 pp difference can be real and still fail to reach p < 0.05. The correct conclusion is “not shown here”, not “no effect”.
- **The confidence intervals are per win rate; the paired tests are the more sensitive comparison.** Overlapping CIs alone do not prove no difference, but the McNemar results agree with the cautious reading.
- **The simulator is deterministic per seed.** Games are independent samples because the seeds are independent; no agent sees another agent's run.
- **The evaluation is local CPU work.** CI runs the tests and a 30-frame entry-point smoke test, not the 200-seed suite.
- **Raw records are kept.** `sim/results.json` keeps one record per game, including gamble risk/outcome, so the paired tests can be recomputed without rerunning the suite.
- **The M4.1 1000-seed files are still in the repo** (`sim/results-tuning.json` and the older report in git history). They are not the reporting set for this document and should not be mixed with the table above.
