# DECISIONS

Record every choice made between options (date, question, choice, reason). Newest first.

| Date | Question | Decision | Reason |
|---|---|---|---|
| 2026-10-22 | Engine for the game UI | pygame-ce | One language (Python), good animation/audio support, easy to demo offline |
| 2026-10-22 | Core AI approach | Forward chaining + exact enumeration + A* | Meets the brief (rule-based, forward chaining) and is stronger than forward chaining alone; see docs/ALGORITHMS.md |
| 2026-10-22 | RL | Optional, after M5 only | Brief does not require it; see PRD Section 16 |
| 2026-10-22 | Repo visibility | Private initially | Owners decide on publishing after the lecturer policy is checked |
| 2026-10-22 | Branch protection | Not available on the current plan; follow the PR rule manually | Section 12.5 allows this; every milestone PR is merged only after green CI |
| 2026-10-22 | M0 window | Placeholder title window, real scenes in M4 | Keeps M0 small; the launcher/CI wiring is what M0 verifies |
| 2026-10-22 | `Leave` cost | Free; does not advance the action counter | The PRD gives oil costs only to Move and Cast Charm and says the run ends; counting it would make the final -1 score arbitrary |
| 2026-10-22 | Invalid shifts | Marked skipped at telegraph time and logged; next shift stays on the every-K schedule | Matches AGENT.md 3.1 ("if still invalid, mark the shift skipped") and keeps the clock predictable |
| 2026-10-22 | KB observation model | Raw percepts are used for one chaining pass, then archived; durable conclusions (NoPit, constraints, …) are stored and R16 transports them | Re-deriving from stale Breeze/NoBreeze facts after a shift would resurrect pre-shift constraints. This keeps one transport path and no retractions |
| 2026-10-22 | Retreat precedence | After R18/R19 goals, retreat (R23) is applied before safe exploration (R21) | A low lantern that explores first often dies one room from the exit; the PRD rule list is preserved, only the execution order is safer |
| 2026-10-22 | CLI says "sum over turns" | Firings are logged per turn because derived goals are recomputed every turn | Keeps the live log honest; totals are sums, not unique firings |
| 2026-10-22 | Code license | MIT | Simple, permissive; assets are licensed per file |
