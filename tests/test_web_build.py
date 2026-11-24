"""Tests for WebAssembly (pygbag) browser readiness, async loop, and web staging."""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path


def test_app_async_loop_runs_cleanly(monkeypatch):
    """App.run_async yields every frame for pygbag / WebAssembly browsers."""
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from shifting_manor.ui.app import App

    app = App(audio=False, windowed=True, seed="WEB-ASYNC")
    asyncio.run(app.run_async(max_frames=5))


def test_simlab_cooperative_benchmark_runs_without_threads(monkeypatch):
    """SimLab live benchmark advances frame-by-frame with zero OS threads (WASM-safe)."""
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    import pygame

    from shifting_manor.ui.simlab import SimLabScene

    pygame.init()
    try:
        lab = SimLabScene(on_exit=lambda: None)
        assert lab.data is not None  # loads results_summary.json or results.json
        lab.start_live_benchmark(runs=5)
        assert lab.running_live is True
        for _ in range(20):
            lab.update(0.016)
            if not lab.running_live:
                break
        assert lab.running_live is False
        assert lab.data is not None
        assert lab.data["config"]["runs"] == 5
        assert set(lab.data["modes"].keys()) == {"apprentice", "explorer", "haunted"}
    finally:
        pygame.quit()


def test_web_entrypoint_and_staging_layout(tmp_path):
    """web/main.py has valid PEP 723 metadata and build_web stages compact assets only."""
    root = Path(__file__).resolve().parent.parent
    entry = root / "web" / "main.py"
    src = entry.read_text(encoding="utf-8")
    assert "pygame-ce" in src
    assert "asyncio.run(main())" in src
    ast.parse(src)

    from tools.build_web import stage_web_app

    stage = stage_web_app(tmp_path / "shifting_manor")
    assert (stage / "main.py").is_file()
    assert (stage / "favicon.png").is_file()
    assert (stage / "shifting_manor" / "ui" / "app.py").is_file()
    assert (stage / "tools" / "posterior.py").is_file()
    assert (stage / "assets" / "fonts" / "DejaVuSans.ttf").is_file()
    assert (stage / "sim" / "results_summary.json").is_file()
    # Heavy raw datasets must stay excluded from the browser bundle
    assert not (stage / "sim" / "results.json").exists()
    assert not (stage / "sim" / "results-tuning.json").exists()
