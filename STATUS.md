# STATUS

_Last updated by:_ coding agent · _Date:_ 2026-10-22 (M5 merged, tag `m5`; explainability review fixes pending merge)

## Done

- **Section 12 — GitHub setup.** Private repo `muhammadghiffari/shifting-manor`, description, topics, MIT `LICENSE`, `main` pushed, CI green on the initial commit (run 39658869803). Milestones M0–M7 and issues #1–#8 created with acceptance criteria; labels created. Branch protection unavailable on this plan, so the per-milestone PR rule is followed by hand (see DECISIONS.md).
- **M0 — Scaffolding** (PR #9, merged `6f7e45c`, tag `m0`). Package layout, `pyproject.toml`, pygame-ce launcher with a placeholder window, ruff + pytest CI, headless UI smoke test.
- **M1 — Engine** (PR #10, merged `658f99d`, tag `m1`). Seeded generator (protected entrance neighbours, treasure reachable by a hazard-free path), percepts, Move/CastCharm/Leave, scoring, death/oil-out/escape, Shift telegraph + validation + skip + exact mapping. Rotation properties and the 1000-random-game soak test pass locally.
- **M2 — KB + inference** (PR #11, merged `64e1ff2`, tag `m2`). Facts/constraints/globals, 24 separate rule objects R01–R24, fixed-priority forward chainer with a fixpoint guard and `Firing` log, pure R16 transport + B2/B2b variants, and a text CLI that prints percepts → rules fired → action for a full game. Every rule is hit by a hand-built scenario test.
- **M3 — Agents + simulation** (PR #12, merged `348c3fe`, tag `m3`). Random, reactive, B2, B2b, B3 and oracle agents; exact pit/ghost model enumeration with weighted worlds and a 14-cell fallback; risk-weighted A*; R22 expected-utility gamble; R23 retreat; 200-seed/mode headless runner that writes `sim/results.json` and prints the metrics table.
  - Bugs found by the sim and fixed at the root: R01 was re-deriving `NoPit`/`NoGhost` from durable `Visited` facts after a shift moved a hazard into an old room; enumeration also treated historical `Visited` as current `NoPit`; fully-resolved constraints were misreported as inconsistent; the oracle never applied `ShiftApplied`, so it planned on the pre-shift map.
  - B3 deaths in the 200-seed suite are all R22 forced guesses (no safe unvisited room), never a known-`Unsafe`/`Pit`/`Ghost` step.
- **M4 — Play mode UI** (PR #13, squash-merged `fb5ed75`, tag `m4`). Title, mode select, play board with lantern fog and wing runes, Senses panel, HUD with shift clock, right-click/key marks, pause, shift animation with rotating marks and dust, and result screen with stars/stats/seed and Replay/New seed/Menu. Keyboard and mouse both work. Screenshots in `docs/screens/` (title, mode select, board with fog, shift mid-frame, pause, result).
- **M4.1 — Hardening** (PR #14, squash-merged `594b3d8`, tag `m4.1`). Entry point fixed (`python -m shifting_manor` works; default windowed with `--fullscreen` opt-in; `--mode/--seed/--no-audio/--frames/--screenshot` forwarded), real subprocess tests with SDL dummy drivers, and a CI 30-frame smoke step. Inference logging is now a per-turn delta against the transported previous closure; re-derivations have separate debug counters; provenance `Fact -> first Firing` and `Constraint -> Firing` exists for the M5 proof tree; R16 logs one aggregate line. Stars are relative to oracle par (3★ at par + 15, 2★ slower treasure escape, 1★ empty-handed).
- **M5 — Watch AI** (PR #15, squash-merged `1a52949`, tag `m5`). Mode select now has **WATCH AI** with an agent picker (B3 default, B2, B2b). The replay uses the real stored trace: full-game board, delta-only inference log, gold highlights on touched cells, belief overlay (certain solid, risk translucent with %, rotated beliefs dashed/transported), rules tab, shift moment, 1×/2×/4× autoplay (`+`/`-`), Space pause, Right step, and a `Why?` proof tree for rooms and log rows. `--demo` starts immediately on the given seed and loops HAUNT-4F2A → HAUNT-7C1D → HAUNT-5D7C with a 3 s pause. Five screenshots are in `docs/screens/watch_ai_*.png`. The explainability pack is `docs/CODE_TOUR.md`, `docs/FORWARD_CHAINING_WALKTHROUGH.md`, `docs/DEMO_SCRIPT.md`, `docs/QA.md`, and `docs/EVALUATION.md`.
- **M5.1 — Explainability review fixes** (branch `fix/m5-explainability`). R16 is now a logged derivation with `Rotated(wing, direction)` as its premise and per-item provenance edges from old to new facts/constraints; it counts in the KB tab. R17 log/proof lines include the actual safe path. `docs/CODE_TOUR.md` now separates the forward-chaining rules from enumeration/A*/gamble planner logic and names `KnowledgeBase.apply_shift`/`kb/transport.py` as R16's home. Screenshots were regenerated for the new R16/R17 lines.

## In progress

- M5.1 review fixes are pending commit/push/PR; **M6 has not been started.**

## Explicitly not done (M5 scope)

- KB tab heat bars.
- Step-back.
- Log-filter UI.
- Duel.
- SimLab.
- Tutorial.
- Audio polish.

These are named in the PR and `DECISIONS.md`; they are not hidden omissions.

## Blocked

- None.

## How to run and verify (exact commands)

```
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
ruff check . && ruff format --check .
python -m shifting_manor --windowed --no-audio --frames 30
python -m shifting_manor --mode explorer --seed HAUNT-4F2A --screenshot /tmp/shot.png
python -m shifting_manor --demo --windowed --seed HAUNT-4F2A
python -m shifting_manor.cli --agent b3 --mode explorer --seed HAUNT-4F2A --verbose
python -m shifting_manor.sim --runs 200 --out sim/results.json
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy pytest -q tests/test_entrypoint.py tests/test_ui_play.py
```

## Test counts / sim results

- M0: 2 tests pass (version smoke + 3-frame headless UI smoke). Ruff clean.
- M1: 154 tests pass locally (rotation, generator over 40 seeds/mode, percepts, actions/scoring, shift, deterministic event logs, 1000 random games). Ruff clean.
- M2: 191 tests pass locally (includes one scenario for every rule R01–R24, transport tests, CLI full-game tests for b0/b1/b2/b2b/b3). Ruff clean.
- M3: 204 tests pass locally (adds enumeration weighting/entailment/fallback, A* risk trade-off, expected utility, cross-check on random games, b3 known-unsafe property, R01/oracle shift regressions, oracle-vs-b3 bound, sim smoke/JSON). Ruff clean.
- M4: 211 tests pass locally (adds 8 headless UI tests: title/mode flow, keyboard move/charm, mouse move/right-click marks, shift-mark rotation, shift skip, every scene draws, result reachable, result layout). Ruff clean.
- M4.1: 225 tests pass locally (adds 5 real-entry-point subprocess tests, delta/provenance/R16 tests, Wilson/McNemar/calibration tests, gamble logging and star tests). Ruff clean.
- **M5: 232 tests pass locally** (adds trace/proof/shift tests, delta-only log tests, the no-pygame-import headless guard, and the `--demo` subprocess test). `ruff check .` and `ruff format --check .` pass. CI is green on Python 3.11 and 3.12 (run 39722346245).
- **M5.1: 235 tests pass locally** (adds R16 log/stats/proof and R17 safe-path tests). `ruff check .` and `ruff format --check .` pass.
- **M5 reporting set: 200 seeds/mode, `SIM-<MODE>-0000..0199`** (`sim/results.json`), win rate:
  - Apprentice: b0 5.0%, b1 3.5%, b2/b2b/b3 94.5%, oracle 100%.
  - Explorer: b0 4.5%, b1 3.5%, b2 77.5%, b2b 83.5%, b3 91.5%, oracle 100%.
  - Haunted: b0 4.5%, b1 3.0%, b2 66.0%, b2b 69.0%, b3 82.5%, oracle 100%.
  - B3 vs B2 is clear: paired McNemar p = 1.8e-6 (Explorer) and 6.3e-8 (Haunted).
  - B2b vs B2 is **not distinguishable at 200 seeds**: p = 0.052 (Explorer) and 0.377 (Haunted). The docs do not claim B2b is better.
  - B3 vs B2b is also clear: p = 8.0e-4 and 1.4e-6.

## Decisions made (also in DECISIONS.md)

- GitHub plan has no branch protection: milestone PRs are still opened and merged only when CI is green, enforced by hand.
- M4 draws at a fixed 1280×720 logical canvas and letterboxes to the window; palette and drawing helpers live in `ui/theme.py`, every user-facing string in `ui/strings.py`.
- M4 result stars are drawn polygons, not Unicode `★`/`☆`, because pygame's default font renders those as missing-glyph boxes.
- M4 keeps the PRD's extra scenes out of scope; M5 adds only Watch AI.
- M4.1 defaults to windowed; `--windowed` is an explicit no-op; `--fullscreen` is opt-in. The real module is covered by subprocess tests.
- M4.1 logs only newly derived facts (delta after R16 transport), keeps re-derivations in debug counters, and stores provenance for the M5 proof trees.
- M5 scope is Watch AI only. KB heat bars, step-back, log-filter UI, Duel, SimLab, tutorial and audio polish are explicitly not done.
- M5 agent picker offers B3 (default), B2 and B2b; Apprentice has no shifts so all three agree there.
- M5 uses `step.firings` (new conclusions only) for the live log and keeps `all_firings` for tests/debug.
- M5 uses 200 same-seed games per mode for the reporting table. 200 shows the B3-vs-B2 gap; it does not resolve a 3–6 pp B2b effect, so the honest result is “not distinguishable”.
- `Firing.turn` stays 0-based; Watch AI displays `turn + 1`.
- M5 demo seeds are HAUNT-4F2A, HAUNT-7C1D and HAUNT-5D7C; `--demo` loops them with a 3 s pause.
- R16 is an event-driven logged derivation: one aggregate firing with `Rotated(wing, direction)` plus per-item provenance edges; it is skipped by the chainer but counted in the KB tab.
- R17 appends `via safe path: ...` to its log/proof line, using the BFS parent map.

## Risks I see

- The repo is private and has no collaborator yet (see Needs human).
- The five Watch AI screenshots were regenerated for the R16/R17 changes; they still need a human visual review on the presentation screen.
- The B2b-vs-B2 result is borderline on Explorer (p = 0.052) and null on Haunted; do not present it as a win.
- CI installs pygame-ce from PyPI on every run; a network hiccup can make CI red for reasons unrelated to the code.
- `sim/results.json` is ~0.2 MB now; the older 1000-seed tuning file remains in the repo. If clone size becomes a problem, keep aggregates and move raw records to a release artifact.
- The worktree still has an unrelated stray edit in `docs/TEAM_PLAN.md` and an untracked stale `docs/demo_trace.txt`; neither is committed.

## Needs human

- Review `docs/screens/watch_ai_*.png` on the presentation display and confirm the text is readable.
- Invite Radithia Ary Winata as collaborator (need GitHub username).
- Check the lecturer's policy on AI-assisted code/assets (PRD Section 14).
- Confirm the presentation OS/screen and whether a recorded video fallback is needed.
