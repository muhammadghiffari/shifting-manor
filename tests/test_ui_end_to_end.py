"""End-to-end tests for Live Autonomous AI, Manual Leave, Duel, Tutorial, Guide, SimLab & Settings."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

ENV = {
    **os.environ,
    "SDL_VIDEODRIVER": "dummy",
    "SDL_AUDIODRIVER": "dummy",
}


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from shifting_manor.ui.app import App

    inst = App(audio=False, windowed=True, seed="HAUNT-4F2A")
    yield inst
    inst.pygame.quit()


def test_manual_leave_manor_at_entrance(app):
    import pygame

    app.start_game("apprentice", "UI-LEAVE-TEST")
    assert app.game is not None
    # Pressing E at (0,0) without treasure escapes empty-handed cleanly
    app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e))
    assert app.scene == "result"
    assert app.result is not None
    assert app.result["outcome"] == "escaped_empty"

    # Carrying treasure at (0,0) and pressing E wins with escaped_treasure
    app.start_game("apprentice", "UI-LEAVE-WIN")
    assert app.game is not None
    app.game.state.has_treasure = True
    app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e))
    assert app.scene == "result"
    assert app.result["outcome"] == "escaped_treasure"


@pytest.mark.parametrize("agent_name", ["b3", "b2", "b2b", "b5", "b1", "b0", "b4"])
def test_live_autonomous_ai_matches_headless_runner(app, agent_name):
    """Live Autonomous AI runs the REAL agent on a live Game identically to sim.runner."""
    from shifting_manor.sim.runner import run_game

    expected = run_game("explorer", "HAUNT-4F2A", agent_name)
    app.start_live_ai("explorer", "HAUNT-4F2A", agent_name)
    assert app.auto_play is True
    assert app.live_ai is not None

    # Step live via _fast_finish_live_ai (calls _step_live_ai turn-by-turn)
    app._fast_finish_live_ai()
    assert app.scene == "result"
    assert app.result is not None
    assert app.result["autonomous"] is True
    assert app.result["outcome"] == expected.outcome
    assert app.result["score"] == expected.score
    app.draw()


def test_live_ai_autoplay_timer_and_proof_tree(app):
    """Autonomous AI advances via update(dt), populates live beliefs/logs, and opens Why? proof."""
    app.start_live_ai("explorer", "HAUNT-4F2A", "b3")
    assert app.live_ai is not None
    app.auto_speed = 4.0
    for _ in range(12):
        app.update(0.2)
        app.draw()
    assert app.game is not None
    assert app.game.state.actions_taken >= 2
    assert app.live_ai.total_firings > 0
    assert app.live_ai.beliefs

    # Open Why? proof tree on entrance (0,0)
    app._open_live_proof((0, 0))
    assert app._proof is not None
    app.draw()


def test_manual_hint_and_midgame_ai_takeover(app):
    """Human plays manually, requests zero-cheating AI Hint, then hands over to real B3."""
    import pygame

    app.start_game("explorer", "HAUNT-4F2A")
    assert app.game is not None
    app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
    assert app.game.state.agent == (0, 1)

    # Request fair AI Hint
    app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_i))
    assert app.active_hint is not None
    assert app.active_hint.summary
    app.draw()

    # Seamless mid-game takeover to autonomous AI [T]
    app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_t))
    assert app.auto_play is True
    assert app.live_ai is not None
    app._fast_finish_live_ai()
    assert app.scene == "result"
    assert app.result is not None
    assert app.result["outcome"] in (
        "escaped_treasure",
        "escaped_empty",
        "died_pit",
        "died_ghost",
        "oil_out",
    )


def test_duel_mode_end_to_end(app):
    """Duel runs Human turn -> Halftime -> Real Caretaker AI on same seed -> Duel Result."""
    import pygame

    app.start_duel("explorer", "HAUNT-4F2A")
    assert app.duel_active is True
    assert app.duel_phase == "human"
    app.draw()

    # Human leaves early at (0,0) -> reaches halftime
    app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e))
    assert app.scene == "duel_halftime"
    assert app.duel_human is not None
    app.draw()

    # Launch AI challenger phase & fast-finish
    app.start_duel_ai_phase(fast=True)
    assert app.scene == "duel_result"
    assert app.duel_ai is not None
    assert app.duel_ai.outcome == "escaped_treasure"
    app.draw()


def test_interactive_tutorial_all_lessons(app):
    import pygame

    app.start_tutorial()
    assert app.scene == "tutorial"
    assert app.tutorial is not None

    for idx in range(4):
        app.tutorial.load_lesson(idx)
        app.update(0.1)
        app.draw()

    # Lesson 4 triggers deterministic wing SE shift at move 3 and rotates marks
    app.tutorial.load_lesson(3)
    assert app.tutorial.marks[(3, 0)] == "?"
    for key in (pygame.K_RIGHT, pygame.K_RIGHT, pygame.K_UP):
        app.handle(pygame.event.Event(pygame.KEYDOWN, key=key))
    assert app.tutorial.shift_done is True
    assert app.tutorial.marks.get((3, 2)) == "?"
    app.update(0.1)
    app.draw()


def test_guide_settings_and_simlab_scenes(app):
    import pygame

    # Field Guide all 4 tabs
    app.open_guide()
    assert app.guide is not None
    for tab in range(4):
        app.guide.tab = tab
        app.update(0.05)
        app.draw()
    app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert app.guide is None

    # Settings overlay
    app.open_settings()
    assert app.settings_overlay is not None
    app.draw()
    app.settings_overlay._activate("high_contrast", None)
    app.settings_overlay._activate("reduce_motion", None)
    app.draw()
    app.settings_overlay._activate("high_contrast", None)
    app.settings_overlay._activate("reduce_motion", None)
    app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert app.settings_overlay is None

    # Simulation Lab all modes & metrics
    app.start_simlab()
    assert app.scene == "simlab"
    assert app.simlab is not None
    for m in range(3):
        app.simlab.mode_index = m
        for met in range(4):
            app.simlab.metric_index = met
            app.draw()


def test_watch_ai_step_back_and_log_filter(app):
    import pygame

    app.start_watch("explorer", "HAUNT-4F2A", "b3")
    assert app.watch is not None
    app.watch.set_step(5)
    app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT))
    assert app.watch.index == 4

    app.watch.tab = 1
    app.watch.log_new_only = False
    app.draw()
    app.watch.tab = 2
    app.draw()


def test_run_card_export_and_audio_synthesis(app, tmp_path, monkeypatch):
    from shifting_manor.ui.audio import AudioManager

    monkeypatch.chdir(tmp_path)
    app.start_game("apprentice", "CARD-TEST")
    assert app.game is not None
    app.game.state.has_treasure = True
    app._try_leave()
    path = app.save_run_card()
    assert path.exists()
    assert path.stat().st_size > 1000

    # Audio manager works safely under dummy audio driver
    mgr = AudioManager(enabled=True)
    mgr.play("step")
    mgr.play("win")
    mgr.set_tension(0.7)


@pytest.mark.parametrize(
    "flags",
    [
        ["--auto", "--agent", "b3", "--mode", "explorer", "--frames", "12"],
        ["--duel", "--mode", "apprentice", "--frames", "10"],
        ["--tutorial", "--frames", "10"],
        ["--simlab", "--frames", "10"],
    ],
)
def test_cli_new_modes_launch_cleanly(flags):
    cmd = [sys.executable, "-m", "shifting_manor", "--windowed", "--no-audio", *flags]
    res = subprocess.run(cmd, env=ENV, capture_output=True, text=True, timeout=60, check=False)
    assert res.returncode == 0, res.stderr
    assert "Traceback" not in res.stderr
