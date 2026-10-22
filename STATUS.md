# STATUS

_Last updated by:_ coding agent · _Date:_ 2026-10-22 (M4.1 merged, M5 next)

## Done

- **Section 12 — GitHub setup.** Private repo `muhammadghiffari/shifting-manor`, description, topics, MIT `LICENSE`, `main` pushed, CI green on the initial commit (run 39658869803). Milestones M0–M7 and issues #1–#8 created with acceptance criteria; labels created. Branch protection unavailable on this plan, so the per-milestone PR rule is followed by hand (see DECISIONS.md).
- **M0 — Scaffolding** (PR #9, merged `6f7e45c`, tag `m0`). Package layout, `pyproject.toml`, pygame-ce launcher with a placeholder window, ruff + pytest CI, headless UI smoke test.
- **M1 — Engine** (PR #10, merged `658f99d`, tag `m1`). Seeded generator (protected entrance neighbours, treasure reachable by a hazard-free path), percepts, Move/CastCharm/Leave, scoring, death/oil-out/escape, Shift telegraph + validation + skip + exact mapping. Rotation properties and the 1000-random-game soak test pass locally.
- **M2 — KB + inference** (PR #11, merged `64e1ff2`, tag `m2`). Facts/constraints/globals, 24 separate rule objects R01–R24, fixed-priority forward chainer with a fixpoint guard and `Firing` log, pure R16 transport + B2/B2b variants, and a text CLI that prints percepts → rules fired → action for a full game. Every rule is hit by a hand-built scenario test.
- **M3 — Agents + simulation** (PR #12, merged `348c3fe`, tag `m3`). Random, reactive, B2, B2b, B3 and oracle agents; exact pit/ghost model enumeration with weighted worlds and a 14-cell fallback; risk-weighted A*; R22 expected-utility gamble; R23 retreat; 200-seed/mode headless runner that writes `sim/results.json` and prints the metrics table.
  - Bugs found by the sim and fixed at the root: R01 was re-deriving `NoPit`/`NoGhost` from durable `Visited` facts after a shift moved a hazard into an old room; enumeration also treated historical `Visited` as current `NoPit`; fully-resolved constraints were misreported as inconsistent; the oracle never applied `ShiftApplied`, so it planned on the pre-shift map.
  - B3 deaths in the 200-seed suite are all R22 forced guesses (no safe unvisited room), never a known-`Unsafe`/`Pit`/`Ghost` step.
- **M4 — Play mode UI** (PR #13, squash-merged `fb5ed75`, tag `m4`). Title, mode select, play board with lantern fog and wing runes, Senses panel, HUD with shift clock, right-click/key marks, pause, shift animation with rotating marks and dust, and result screen with stars/stats/seed and Replay/New seed/Menu. Keyboard and mouse both work. Screenshots in `docs/screens/` (title, mode select, board with fog, shift mid-frame, pause, result).
- **M4.1 — Hardening** (PR #14, squash-merged `594b3d8`, tag `m4.1`). Entry point fixed (`python -m shifting_manor` works; default windowed with `--fullscreen` opt-in; `--mode/--seed/--no-audio/--frames/--screenshot` forwarded), real subprocess tests with SDL dummy drivers, and a CI 30-frame smoke step. Inference logging is now a per-turn delta against the transported previous closure; re-derivations have separate debug counters; provenance `Fact -> first Firing` with percept leaves exists for the M5 proof tree; R16 logs one aggregate line. Evaluation now has Wilson 95% CIs, paired McNemar tests, gamble risk/outcome logging and calibration, 1000 tuning + 1000 reporting seeds per mode, and `docs/EVALUATION.md`. Stars are relative to oracle par (3★ at par + 15, 2★ slower treasure escape, 1★ empty-handed).

## In progress

- M5 Watch AI on branch `feat/m5-watch-ai`, starting from tag `m4.1`. M6 remains out of scope.

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
python -m shifting_manor.cli --agent b3 --mode explorer --seed HAUNT-4F2A --verbose
python -m shifting_manor.sim --runs 1000 --seed-start 10000 --seed-prefix REPORT --jobs 8 --out sim/results.json
python -m shifting_manor.sim --runs 1000 --seed-start 0 --seed-prefix TUNE --jobs 8 --out sim/results-tuning.json
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy pytest -q tests/test_entrypoint.py tests/test_ui_play.py
```

## Test counts / sim results

- M0: 2 tests pass (version smoke + 3-frame headless UI smoke). Ruff clean.
- M1: 154 tests pass locally (rotation, generator over 40 seeds/mode, percepts, actions/scoring, shift, deterministic event logs, 1000 random games). Ruff clean.
- M2: 191 tests pass locally (includes one scenario for every rule R01–R24, transport tests, CLI full-game tests for b0/b1/b2/b2b/b3). Ruff clean.
- M3: 204 tests pass locally (adds enumeration weighting/entailment/fallback, A* risk trade-off, expected utility, cross-check on random games, b3 known-unsafe property, R01/oracle shift regressions, oracle-vs-b3 bound, sim smoke/JSON). Ruff clean.
- M4: 211 tests pass locally (adds 8 headless UI tests: title/mode flow, keyboard move/charm, mouse move/right-click marks, shift-mark rotation, shift skip, every scene draws, result reachable, result layout). Ruff clean.
- M4.1: 225 tests pass locally (adds 5 real-entry-point subprocess tests, delta/provenance/R16 tests, Wilson/McNemar/calibration tests, gamble logging and star tests). Ruff clean.
- 1000 reporting seeds/mode (`sim/results.json`), win rate:
  - apprentice: b0 6.0%, b1 5.6%, b2 95.8%, b2b 95.8%, b3 95.8%, oracle 100%.
  - explorer: b0 3.6%, b1 3.1%, b2 79.2%, b2b 82.0%, b3 90.3%, oracle 100%.
  - haunted: b0 3.2%, b1 2.2%, b2 66.2%, b2b 69.7%, b3 79.7%, oracle 100%.
  - B3 beats B2 by 11.1 pp (Explorer) and 13.5 pp (Haunted); B3 beats B2b by 8.3 pp and 10.0 pp. All four McNemar tests p < 0.001. B2b vs B2 is a small 2.8/3.5 pp gain (p = 0.022/0.012), not the earlier “indistinguishable” result.
  - Tuning set reproduces the ordering: B3 95.6% / 90.7% / 81.3% (apprentice/explorer/haunted). No K or pit-density tuning was done.

## Decisions made (also in DECISIONS.md)

- GitHub plan has no branch protection: milestone PRs are still opened and merged only when CI is green, enforced by hand.
- M0 title window is a placeholder; the real scene stack arrives in M4.
- M4 draws at a fixed 1280×720 logical canvas and letterboxes to the window; palette and drawing helpers live in `ui/theme.py`, every user-facing string in `ui/strings.py`.
- M4 result stars are drawn polygons, not Unicode `★`/`☆`, because pygame's default font renders those as missing-glyph boxes.
- M4 shift overlay draws a translucent floor and grid inside the rotating wing so the rotation is visible, not just moving marks.
- M4 keeps the PRD's extra scenes (Watch AI, Duel, SimLab, tutorial, settings) out of scope; they belong to M5/M6.
- M4.1 defaults to windowed and keeps `--windowed` as an explicit no-op; `--fullscreen` is the opt-in. The stale `ui.app.main` import is fixed and covered by subprocess tests that run the real module.
- M4.1 logs only newly derived facts (delta after R16 transport), keeps re-derivations in debug counters, and stores provenance so M5 can build proof trees. R16 shows one aggregate line in normal mode.
- M4.1 uses tuning seeds 0–999 and reporting seeds 10000–10999, Wilson CIs, paired McNemar tests, and gamble calibration; `docs/EVALUATION.md` is the report. No K or pit density was tuned.
- M4.1 stars are relative to oracle par (3★ at par + 15); the distribution is in `docs/EVALUATION.md`.

## Risks I see

- The repo is private and has no collaborator yet (see Needs human).
- CI installs pygame-ce from PyPI on every run; a network hiccup can make CI red for reasons unrelated to the code.
- M4 screenshots are correct but still need human visual review before any further UI polish (per AGENT.md).
- The gamble 50–60% calibration bin is 12.4 pp below its midpoint for B3; investigation shows the enumeration itself is calibrated and the gap is policy selection (see `docs/EVALUATION.md` §5). It is documented, not tuned away.
- `sim/results*.json` are now ~11 MB each because they keep every game and gamble record. If clone size becomes a problem, keep only the aggregate tables and move raw records to a release artifact.

## Needs human

- Invite Radithia Ary Winata as collaborator (need GitHub username).
- Check the lecturer's policy on AI-assisted code/assets (PRD Section 14).
- Confirm the presentation OS/screen (PRD Section 14).
- Review `docs/screens/` for M4 and confirm the UI look before M5/M6 polish.
