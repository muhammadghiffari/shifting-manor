# STATUS

_Last updated by:_ coding agent · _Date:_ 2026-10-22 (overnight run)

## Done

- **Section 12 — GitHub setup.** Private repo `muhammadghiffari/shifting-manor`, description, topics, MIT `LICENSE`, `main` pushed, CI green on the initial commit (run 39658869803). Milestones M0–M7 and issues #1–#8 created with acceptance criteria; labels created. Branch protection unavailable on this plan, so the per-milestone PR rule is followed by hand (see DECISIONS.md).
- **M0 — Scaffolding** (PR to be linked). Package layout, `pyproject.toml`, pygame-ce launcher with a placeholder window, ruff + pytest CI, headless UI smoke test.

## In progress

- M1 — Engine.

## Blocked

- None.

## How to run and verify (exact commands)

```
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
ruff check . && ruff format --check .
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -c "from shifting_manor.ui.app import App; App(audio=False).run(max_frames=2)"
```

CLI and sim commands are added when M2/M3 land.

## Test counts / sim results

- M0: 2 tests pass (version smoke + 3-frame headless UI smoke). Ruff clean.

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
