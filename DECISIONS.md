# DECISIONS

Record every choice made between options (date, question, choice, reason). Newest first.

| Date | Question | Decision | Reason |
|---|---|---|---|
| 2026-10-22 | M4 UI canvas | Fixed 1280×720 logical surface, scaled/letterboxed into the window; F11 toggles fullscreen | One coordinate system for drawing, mouse mapping and screenshots; matches PRD 8.1 |
| 2026-10-22 | M4 UI strings | Every user-facing string in `ui/strings.py`, palette/fonts/helpers in `ui/theme.py` | One place to reword or re-theme without touching scene logic |
| 2026-10-22 | Result stars | Draw filled/empty star polygons instead of Unicode `★`/`☆` | pygame's default font shows missing-glyph boxes for those code points |
| 2026-10-22 | Shift overlay | Rotate a translucent 3×3 floor with grid lines, marks and dust inside the wing | A transparent square with only marks did not read as a rotating wing |
| 2026-10-22 | M4 scope | Only title, mode select, play, fog, HUD, marks and result; no Watch AI/Duel/SimLab/tutorial/settings | Those are M5/M6 deliverables; M4 is the playable human UI |
| 2026-10-22 | R01 vs. shifting rooms | R01 fires only for the room just entered, not for every historical `Visited` fact | A room visited earlier can receive a pit when its wing rotates. Re-deriving `NoPit` from `Visited` resurrected stale safety and killed B3; durable conclusions are now only those R16 transports |
| 2026-10-22 | Enumeration and `Visited` | `Visited` is not treated as current `NoPit`; a known ghost room is pit-free and a known pit room is ghost-free | Historical visits say nothing about post-shift contents; the generator never stacks a pit and the ghost |
| 2026-10-22 | Oracle and shifts | The oracle applies `ShiftApplied` mappings to its known pits/ghost | The oracle is an upper bound, so it must not plan on the pre-shift map after a rotation |
| 2026-10-22 | B3 forced guesses | R22 gamble deaths are reported as forced guesses, not hidden as failures | Some haunted/explorer boards have no certainly-safe unvisited room; the sim reports the rate so the claim is honest |
| 2026-10-22 | Sim seeds | Fixed `SIM-<MODE>-NNN` seeds per mode, 200 per mode, one JSON record per game | Same seed reproduces the same map/shift/outcome and the results file is directly comparable across agents |
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
