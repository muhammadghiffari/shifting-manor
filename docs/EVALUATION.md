# Evaluation

This is the M4.1 evaluation report for the Caretaker agents. It is deliberately blunt about what the numbers do and do not show. The raw runs are `sim/results.json` (reporting set) and `sim/results-tuning.json` (tuning set).

## 1. Protocol

- **Two disjoint seed sets, 1000 seeds each.** Tuning: `TUNE-<MODE>-0000` … `0999` (seeds 0–999). Reporting: `REPORT-<MODE>-0000` … `10999` (seeds 10000–10999). Every agent sees the same seed and therefore the same generated map.
- **No tuning on the reporting set.** The M3 agent code is unchanged. The tuning set was run only as a second out-of-sample check; it did not select parameters.
- **Win** means `escaped_treasure` (the heirloom). An empty-handed escape is reported separately and counts for one star, not for the win rate.
- **95% Wilson score intervals** are reported for every win rate. They are appropriate for a binomial proportion and behave sensibly at 0% and 100%; no normal approximation is used on small counts.
- **Paired comparisons** use the two-sided McNemar test on the same seeds, with continuity correction. Reported cells are b3-only wins and other-only wins (discordant pairs), the chi-square statistic on one degree of freedom, and the p-value.
- **Forced guess.** After forward chaining, R22 (`GambleNeeded`) holds when the KB has no safe goal, no known-safe treasure route and no safe entrance route. The action chosen on such a turn is a Move produced by the R22 gamble branch. A game is a forced-guess game if at least one action was chosen this way. The rate below is the fraction of games with one or more forced guesses. B0, B1 and the oracle have no KB or no R22 branch, so the rate is not applicable to them.
- **Gamble calibration event.** A gamble event is a single Move chosen while R22 selected the destination. The estimated death risk is the exact-enumeration risk of the room that Move enters, evaluated before the move. The outcome is whether that Move killed the agent (pit or living ghost). This is the probability the action actually takes; it is not the target's risk, which can be zero when a safe target is reached through a risky shortcut.
- **Stars.** Par is the oracle's action count on the same seed. 3 stars = escaped with the heirloom in at most par + 15 actions; 2 stars = escaped with the heirloom more slowly; 1 star = escaped empty-handed; 0 stars = died or stalled.

Reproduce:

```
python -m shifting_manor.sim --runs 1000 --seed-start 10000 --seed-prefix REPORT --jobs 8 --out sim/results.json
python -m shifting_manor.sim --runs 1000 --seed-start 0     --seed-prefix TUNE   --jobs 8 --out sim/results-tuning.json
```

`--jobs` only changes wall-clock time; the seed list and results are identical.

## 2. Reporting set (1000 seeds per mode)

| Mode | Agent | Wins / n | Win % (95% Wilson CI) | Escaped any | Mean score | Mean actions | Mean stars | Forced-guess games |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Apprentice | B0 | 60 / 1000 | 6.0% [4.7, 7.6] | 6.0% | −869.0 | 10.5 | 0.17 | n/a |
| Apprentice | B1 | 56 / 1000 | 5.6% [4.3, 7.2] | 5.6% | −886.7 | 8.7 | 0.16 | n/a |
| Apprentice | B2 | 958 / 1000 | 95.8% [94.4, 96.9] | 95.8% | 1015.6 | 12.5 | 2.87 | 34.1% |
| Apprentice | B2b | 958 / 1000 | 95.8% [94.4, 96.9] | 95.8% | 1015.6 | 12.5 | 2.87 | 34.1% |
| Apprentice | B3 | 958 / 1000 | 95.8% [94.4, 96.9] | 95.8% | 1015.6 | 12.5 | 2.87 | 34.1% |
| Apprentice | Oracle | 1000 / 1000 | 100.0% [99.6, 100.0] | 100.0% | 1161.3 | 8.0 | 3.00 | n/a |
| Explorer | B0 | 36 / 1000 | 3.6% [2.6, 4.9] | 3.6% | −933.0 | 14.7 | 0.10 | n/a |
| Explorer | B1 | 31 / 1000 | 3.1% [2.2, 4.4] | 3.1% | −949.2 | 13.2 | 0.09 | n/a |
| Explorer | B2 | 792 / 1000 | 79.2% [76.6, 81.6] | 79.3% | 656.8 | 23.0 | 2.10 | 40.0% |
| Explorer | B2b | 820 / 1000 | 82.0% [79.5, 84.3] | 83.9% | 732.9 | 24.4 | 2.20 | 47.8% |
| Explorer | B3 | 903 / 1000 | 90.3% [88.3, 92.0] | 90.3% | 888.1 | 24.8 | 2.35 | 42.6% |
| Explorer | Oracle | 1000 / 1000 | 100.0% [99.6, 100.0] | 100.0% | 1153.0 | 12.1 | 3.00 | n/a |
| Haunted | B0 | 32 / 1000 | 3.2% [2.3, 4.5] | 3.2% | −943.6 | 12.9 | 0.09 | n/a |
| Haunted | B1 | 22 / 1000 | 2.2% [1.5, 3.3] | 2.2% | −964.8 | 11.8 | 0.06 | n/a |
| Haunted | B2 | 662 / 1000 | 66.2% [63.2, 69.1] | 66.3% | 379.8 | 20.7 | 1.82 | 52.1% |
| Haunted | B2b | 697 / 1000 | 69.7% [66.8, 72.5] | 71.5% | 473.6 | 21.7 | 1.94 | 58.7% |
| Haunted | B3 | 797 / 1000 | 79.7% [77.1, 82.1] | 79.9% | 662.9 | 22.8 | 2.12 | 54.8% |
| Haunted | Oracle | 1000 / 1000 | 100.0% [99.6, 100.0] | 100.0% | 1151.3 | 12.1 | 3.00 | n/a |

The ordering is stable: oracle ≥ B3 > B2b > B2 > B1 ≈ B0. Apprentice has no shifts (and therefore no difference between B2, B2b and B3); the variants only matter once R16 transport and B2b forgetting are exercised.

### Paired tests

| Mode | Comparison | B3-only wins | Other-only wins | McNemar χ² | p |
|---|---|---:|---:|---:|---:|
| Explorer | B3 vs B2 | 122 | 11 | 90.98 | 1.45 × 10⁻²¹ |
| Explorer | B3 vs B2b | 89 | 6 | 70.78 | 4.00 × 10⁻¹⁷ |
| Haunted | B3 vs B2 | 161 | 26 | 96.02 | 1.14 × 10⁻²² |
| Haunted | B3 vs B2b | 128 | 28 | 62.83 | 2.26 × 10⁻¹⁵ |

Apprentice has zero discordant pairs for every comparison because the three KB variants are identical without shifts.

## 3. What the 1000 seeds show

- **B3 clearly beats B2.** The gap is 11.1 pp on Explorer and 13.5 pp on Haunted; both paired tests are far below p = 0.001.
- **B3 also clearly beats B2b.** The gap is 8.3 pp on Explorer and 10.0 pp on Haunted; both paired tests reject equality. This is the honest answer to the 200-seed observation that B2b-vs-B2 looked indistinguishable: B2b is a small improvement over B2, but it is not a substitute for R16 transport.
- **B2b vs B2 is small but detectable at 1000 seeds.** McNemar gives 83/55 discordant wins on Explorer (p = 0.022) and 110/75 on Haunted (p = 0.012). The win-rate gain is only 2.8 pp and 3.5 pp. B2b buys extra empty-handed escapes (18–19 per 1000) rather than many more heirloom escapes.
- **Absolute rates are consistent with M3.** The earlier 200-seed table reported B3 at 89.5% Explorer and 79.0% Haunted; the 1000-seed reporting set gives 90.3% and 79.7%. The earlier “13 pp / 16 pp” gaps shrink to 11.1 pp / 13.5 pp with more seeds — still large and clearly real.

## 4. Stars

Par (oracle actions) is 8.0 on Apprentice and 12.1 on Explorer/Haunted. B3's star distribution:

| Mode | 3★ | 2★ | 1★ | 0★ | 3★ share of heirloom escapes |
|---|---:|---:|---:|---:|---:|
| Apprentice | 952 | 6 | 0 | 42 | 99.4% |
| Explorer | 543 | 360 | 0 | 97 | 60.1% |
| Haunted | 525 | 272 | 2 | 201 | 65.9% |

The top rating is very easy on Apprentice because the oracle is already near-optimal there. On the shift modes roughly three in five B3 heirloom escapes are within par + 15. That is achievable for a strong agent but not automatic for a human; we kept the requested par + 15 rather than tightening it to par + 10 after seeing the distribution (see DECISIONS.md).

## 5. Gamble calibration

Every R22 gamble action is logged with the estimated risk and whether that action died. Values are the exact enumeration risk of the entered cell before the move. Counts are gamble actions, not games.

B3, all modes pooled:

| Risk bin | Deaths / gambles | Observed | Gap vs bin midpoint |
|---|---:|---:|---:|
| 0–10% | 28 / 2612 | 1.1% | −3.9 pp |
| 10–20% | 109 / 827 | 13.2% | −1.8 pp |
| 20–30% | 49 / 219 | 22.4% | −2.6 pp |
| 30–40% | 61 / 162 | 37.7% | +2.7 pp |
| 40–50% | 2 / 3 | 66.7% | +21.7 pp |
| 50–60% | 80 / 188 | 42.6% | −12.4 pp |
| 60–70% | 2 / 3 | 66.7% | +1.7 pp |
| 70–80% | 2 / 2 | 100.0% | +25.0 pp |
| 80–90% | 1 / 2 | 50.0% | −35.0 pp |

Per mode, the 50–60% bin is −14.5 pp on Apprentice (15/37), −13.9 pp on Explorer (23/56) and −10.8 pp on Haunted (42/95). All other bins with more than a handful of samples are within ±10 pp; the extreme high bins have 1–3 samples and should not be interpreted.

**Investigation of the one meaningful miss.** The 50–60% gamble bin is the only populated bin above 10 pp with a usable sample. We checked whether the enumeration weights, R16 transport or retreat margin were the cause:

- A model-level check over **every unknown cell** at sampled turns (not only the cells the policy chose) put the same 50–60% bin at 51.4% observed on Apprentice, 52.7% on Explorer and 53.2% on Haunted (n = 438–1,219). The enumeration itself is calibrated.
- The gamble-only subsample is selected by the policy using route structure and target safety; that selection makes the chosen high-risk step safer than a random cell with the same estimated risk. The cluster bootstrap over seeds for the B3 50–60% bin is [35.6%, 49.5%], so the gap is real for the selected sample but is not evidence of a bad weight table.
- Therefore no K, pit density or risk weight was changed. Changing the policy to close a calibration bin would be tuning the agent, which this milestone explicitly forbids.

## 6. Tuning set (1000 seeds per mode)

Tuning results are in `sim/results-tuning.json`. No parameter was selected from them; the point is to show the reporting numbers are not a lucky seed draw. Summary of win rates:

| Mode | B0 | B1 | B2 | B2b | B3 | Oracle |
|---|---:|---:|---:|---:|---:|---:|
| Apprentice | 5.9% | 6.5% | 95.6% | 95.6% | 95.6% | 100% |
| Explorer | 2.3% | 3.8% | 78.6% | 84.1% | 90.7% | 100% |
| Haunted | 1.6% | 2.7% | 68.1% | 68.7% | 81.3% | 100% |

The ordering and the size of the B3 lead reproduce on the tuning set. Reporting and tuning win rates differ by at most 1.6 pp for B3. The paired picture also reproduces: on Explorer B3-vs-B2 is 131/10 discordant (p = 5.2 × 10⁻²⁴) and B3-vs-B2b is 76/10 (p = 2.4 × 10⁻¹²); on Haunted the corresponding pairs are 158/26 and 145/19 (both p < 10⁻²¹).

## 7. Threats to validity / honest limits

- Gamble calibration bins with fewer than ~20 actions are not interpretable; the 40–100% bins fall into that category. The 50–60% selection effect above is the only non-trivial deviation and is documented rather than tuned away.
- The generator rejects maps where the heirloom is unreachable by a hazard-free path. That global constraint is not available to the agent (it does not know the heirloom's position), so a small selection effect in chosen cells is expected. It is a modelling limit, not a transport or weighting bug.
- The simulator is deterministic per seed and runner, but the 95% intervals treat games as independent samples. They are; the seeds are independent and no agent sees another's run.
- The evaluation is local CPU work; CI runs the tests and a 30-frame entry-point smoke test, not the 1000-seed suite.
