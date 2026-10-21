# STATUS

_Last updated by:_ coding agent · _Date:_ 2026-10-22 (overnight run)

## Done

- **Section 12 — GitHub setup.** Private repo `muhammadghiffari/shifting-manor`, description, topics, MIT `LICENSE`, `main` pushed, CI green on the initial commit (run 39658869803). Milestones M0–M7 and issues #1–#8 created with acceptance criteria; labels created. Branch protection unavailable on this plan, so the per-milestone PR rule is followed by hand (see DECISIONS.md).
- **M0 — Scaffolding** (PR #9, merged `6f7e45c`, tag `m0`). Package layout, `pyproject.toml`, pygame-ce launcher with a placeholder window, ruff + pytest CI, headless UI smoke test.
- **M1 — Engine** (PR #10, merged `658f99d`, tag `m1`). Seeded generator (protected entrance neighbours, treasure reachable by a hazard-free path), percepts, Move/CastCharm/Leave, scoring, death/oil-out/escape, Shift telegraph + validation + skip + exact mapping. Rotation properties and the 1000-random-game soak test pass locally.
- **M2 — KB + inference.** Facts/constraints/globals, 24 separate rule objects R01–R24, fixed-priority forward chainer with a fixpoint guard and `Firing` log, pure R16 transport + B2/B2b variants, and a text CLI that prints percepts → rules fired → action for a full game. Every rule is hit by a hand-built scenario test.

## In progress

- M2 PR/CI, then M3 — agents + simulation.

## Blocked

- None.

## How to run and verify (exact commands)

```
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
ruff check . && ruff format --check .
python -m shifting_manor.cli --agent b3 --mode explorer --seed HAUNT-4F2A --verbose
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -c "from shifting_manor.ui.app import App; App(audio=False).run(max_frames=2)"
```

Sim commands are added in M3.

## Test counts / sim results

- M0: 2 tests pass (version smoke + 3-frame headless UI smoke). Ruff clean.
- M1: 154 tests pass locally (rotation, generator over 40 seeds/mode, percepts, actions/scoring, shift, deterministic event logs, 1000 random games). Ruff clean.
- M2: 191 tests pass locally (includes one scenario for every rule R01–R24, transport tests, CLI full-game tests for b0/b1/b2/b2b/b3). Ruff clean.

## Decisions made (also in DECISIONS.md)

- GitHub plan has no branch protection: milestone PRs are still opened and merged only when CI is green, enforced by hand.
- M0 title window is a placeholder; the real scene stack arrives in M4.

## Risks I see

- The repo is private and has no collaborator yet (see Needs human).
- CI installs pygame-ce from PyPI on every run; a network hiccup can make CI red for reasons unrelated to the code.

## Needs human

- Invite Radithia Ary Winata as collaborator (need GitHub username).
- Check the lecturer's policy on AI-assisted code/assets (PRD Section 14).
- Confirm the presentation OS/screen (PRD Section 14).
