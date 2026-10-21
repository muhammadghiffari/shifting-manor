"""Headless UI smoke test: SDL dummy driver, a few frames, no exceptions."""

from __future__ import annotations

import os


def test_app_opens_and_draws(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from shifting_manor.ui.app import App

    app = App(audio=False, windowed=True)
    app.run(max_frames=3)
    assert os.environ["SDL_VIDEODRIVER"] == "dummy"
