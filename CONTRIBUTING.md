# Contributing to Shifting Manor

Thank you for your interest in contributing to **Shifting Manor**!

## Development Setup

```bash
git clone https://github.com/muhammadghiffari/shifting-manor.git
cd shifting-manor
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Architecture Boundary

- `shifting_manor/engine/`, `shifting_manor/kb/`, `shifting_manor/agents/`, and `shifting_manor/sim/` are **pure Python** and must never import `pygame` (enforced by automated tests).
- `shifting_manor/ui/` handles desktop and WebAssembly rendering, audio, and interaction.
- Any game-loop or background work in `shifting_manor/ui/` must remain cooperative and OS-thread-free so the WebAssembly (`pygbag`) browser build continues to work cleanly.

## Verification Checklist

Run these checks locally before opening a pull request:

```bash
ruff format --check .
ruff check .
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy pytest -q
```

If you modify `web/` or `tools/build_web.py`, also verify the browser bundle builds cleanly:

```bash
pip install pygbag
python -m tools.build_web --out dist/web
```

## Pull Request Process

1. Branch from `main` with a descriptive name (e.g., `fix/shift-hint-wrap` or `feat/new-seed-preset`).
2. Keep pull requests focused and include unit tests for engine, KB, or UI changes.
3. Ensure CI (`ruff` + `pytest` across Python 3.11 and 3.12) passes before requesting review.
