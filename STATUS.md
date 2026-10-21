# STATUS

_Last updated by:_ coding agent · _Date:_ 2026-10-22 (overnight run)

## Done

- **Section 12 — GitHub setup.** Private repo `muhammadghiffari/shifting-manor`, description, topics, MIT `LICENSE`, `main` pushed, CI green on the initial commit (run 39658869803). Milestones M0–M7 and issues #1–#8 created with acceptance criteria; labels created. Branch protection unavailable on this plan, so the per-milestone PR rule is followed by hand (see DECISIONS.md).
- **M0 — Scaffolding** (PR #9, merged `6f7e45c`, tag `m0`). Package layout, `pyproject.toml`, pygame-ce launcher with a placeholder window, ruff + pytest CI, headless UI smoke test.
- **M1 — Engine** (PR #10, merged `658f99d`, tag `m1`). Seeded generator (protected entrance neighbours, treasure reachable by a hazard-free path), percepts, Move/CastCharm/Leave, scoring, death/oil-out/escape, Shift telegraph + validation + skip + exact mapping. Rotation properties and the 1000-random-game soak test pass locally.
- **M2 — KB + inference** (PR #11, merged `64e1ff2`, tag `m2`). Facts/constraints/globals, 24 separate rule objects R01–R24, fixed-priority forward chainer with a fixpoint guard and `Firing` log, pure R16 transport + B2/B2b variants, and a text CLI that prints percepts → rules fired → action for a full game. Every rule is hit by a hand-built scenario test.
- **M3 — Agents + simulation** (PR #12, merged `348c3fe`, tag `m3`). Random, reactive, B2, B2b, B3 and oracle agents; exact pit/ghost model enumeration with weighted worlds and a 14-cell fallback; risk-weighted A*; R22 expected-utility gamble; R23 retreat; 200-seed/mode headless runner that writes `sim/results.json` and prints the metrics table.
  - Bugs found by the sim and fixed at the root: R01 was re-deriving `NoPit`/`NoGhost` from durable `Visited` facts after a shift moved a hazard into an old room; enumeration also treated historical `Visited` as current `NoPit`; fully-resolved constraints were misreported as inconsistent; the oracle never applied `ShiftApplied`, so it planned on the pre-shift map.
  - B3 deaths in the 200-seed suite are all R22 forced guesses (no safe unvisited room), never a known-`Unsafe`/`Pit`/`Ghost` step.
- **M4 — Play mode UI** (PR #13, tag pending). Title, mode select, play board with lantern fog and wing runes, Senses panel, HUD with shift clock, right-click/key marks, pause, shift animation with rotating marks and dust, and result screen with stars/stats/seed and Replay/New seed/Menu. Keyboard and mouse both work. Screenshots in `docs/screens/` (title, mode select, board with fog, shift mid-frame, pause, result).

## In progress

- M4 PR #13 CI and tag `m4`; stop before M5.

## Blocked

- None.

## How to run and verify (exact commands)

```
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
ruff check . && ruff format --check .
python -m shifting_manor.cli --agent b3 --mode explorer --seed HAUNT-4F2A --verbose
python -m shifting_manor.sim --runs 200 --out sim/results.json
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -c "from shifting_manor.ui.app import App; App(audio=False).run(max_frames=2)"
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy pytest -q tests/test_ui_play.py
```

## Test counts / sim results

- M0: 2 tests pass (version smoke + 3-frame headless UI smoke). Ruff clean.
- M1: 154 tests pass locally (rotation, generator over 40 seeds/mode, percepts, actions/scoring, shift, deterministic event logs, 1000 random games). Ruff clean.
- M2: 191 tests pass locally (includes one scenario for every rule R01–R24, transport tests, CLI full-game tests for b0/b1/b2/b2b/b3). Ruff clean.
- M3: 204 tests pass locally (adds enumeration weighting/entailment/fallback, A* risk trade-off, expected utility, cross-check on random games, b3 known-unsafe property, R01/oracle shift regressions, oracle-vs-b3 bound, sim smoke/JSON). Ruff clean.
- M4: 211 tests pass locally (adds 8 headless UI tests: title/mode flow, keyboard move/charm, mouse move/right-click marks, shift-mark rotation, shift skip, every scene draws, result reachable, result layout). Ruff clean.
- 200 seeds/mode (`sim/results.json`), win rate:
  - apprentice: b0 3.5%, b1 5.5%, b2 93.5%, b2b 93.5%, b3 93.5%, oracle 100%.
  - explorer: b0 2.0%, b1 5.0%, b2 76.5%, b2b 81.5%, b3 89.5%, oracle 100%.
  - haunted: b0 0.5%, b1 3.5%, b2 63.0%, b2b 65.5%, b3 79.0%, oracle 100%.
  - Ordering holds: oracle ≥ B3 > B2b > B2 > B1 > B0 once shifts matter; B3 beats B1 on Apprentice.

## Decisions made (also in DECISIONS.md)

- GitHub plan has no branch protection: milestone PRs are still opened and merged only when CI is green, enforced by hand.
- M0 title window is a placeholder; the real scene stack arrives in M4.
- M4 draws at a fixed 1280×720 logical canvas and letterboxes to the window; palette and drawing helpers live in `ui/theme.py`, every user-facing string in `ui/strings.py`.
- M4 result stars are drawn polygons, not Unicode `★`/`☆`, because pygame's default font renders those as missing-glyph boxes.
- M4 shift overlay draws a translucent floor and grid inside the rotating wing so the rotation is visible, not just moving marks.
- M4 keeps the PRD's extra scenes (Watch AI, Duel, SimLab, tutorial, settings) out of scope; they belong to M5/M6.

## Risks I see

- The repo is private and has no collaborator yet (see Needs human).
- CI installs pygame-ce from PyPI on every run; a network hiccup can make CI red for reasons unrelated to the code.
- M4 screenshots are correct but still need human visual review before any further UI polish (per AGENT.md).

## Needs human

- Invite Radithia Ary Winata as collaborator (need GitHub username).
- Check the lecturer's policy on AI-assisted code/assets (PRD Section 14).
- Confirm the presentation OS/screen (PRD Section 14).
- Review `docs/screens/` for M4 and confirm the UI look before M5/M6 polish.
