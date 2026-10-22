"""The real entry point must boot headless, reach every mode and save screenshots."""

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
BASE = [sys.executable, "-m", "shifting_manor", "--windowed", "--no-audio"]


def run_cli(*args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*BASE, *args],
        env=ENV,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


@pytest.mark.parametrize("mode", [None, "apprentice", "explorer", "haunted"])
def test_entrypoint_runs_every_menu_scene(mode: str | None) -> None:
    args = ["--frames", "30"]
    if mode is not None:
        args += ["--mode", mode]
    result = run_cli(*args)
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr


def test_entrypoint_saves_screenshot(tmp_path) -> None:
    path = tmp_path / "shot.png"
    result = run_cli("--mode", "explorer", "--screenshot", str(path))
    assert result.returncode == 0, result.stderr
    assert path.exists()
    assert path.stat().st_size > 1000


def test_demo_watch_headless_through_entry_point(tmp_path) -> None:
    path = tmp_path / "watch.png"
    result = run_cli("--demo", "--frames", "120", "--screenshot", str(path))
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr
    assert path.exists()
    assert path.stat().st_size > 1000


def test_entrypoint_exact_command_exits_zero() -> None:
    """Requirement: verify python -m shifting_manor --windowed --frames 30 exits 0."""
    cmd = [sys.executable, "-m", "shifting_manor", "--windowed", "--frames", "30"]
    result = subprocess.run(
        cmd,
        env=ENV,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr


def test_entrypoint_accepts_seed_flag() -> None:
    """The --seed flag is accepted and honored by the CLI entrypoint."""
    result = run_cli("--mode", "explorer", "--seed", "CUSTOM-SEED-42", "--frames", "5")
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr


def test_subprocess_smoke_every_scene() -> None:
    """Subprocess smoke test verifying that all 5 scenes draw without crashing.

    Scenes exercised: title, mode select, play, watch AI, result.
    """
    driver = """
import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

from shifting_manor.ui.app import App

app = App(audio=False, windowed=True, seed="SMOKE-SUBPROCESS")

# 1. Title scene
assert app.scene == "title"
app.draw()
app.update(0.1)

# 2. Mode select scene
app.scene = "modes"
app.draw()
app.update(0.1)

# 3. Play scene
app.start_game("explorer", "SMOKE-PLAY")
assert app.scene == "play"
app.draw()
app.update(0.1)

# 4. Watch AI scene
app.start_watch("explorer", "HAUNT-4F2A", "b3")
assert app.scene == "watch"
app.draw()
app.update(0.1)

# 5. Result scene
app.start_game("apprentice", "SMOKE-RESULT")
assert app.game is not None
app.game.state.done = True
app.game.state.outcome = "escaped_treasure"
app._finish()
assert app.scene == "result"
app.draw()
app.update(0.1)

app.pygame.quit()
print("ALL_SCENES_OK")
"""
    result = subprocess.run(
        [sys.executable, "-c", driver],
        env=ENV,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "ALL_SCENES_OK" in result.stdout
    assert "Traceback" not in result.stderr
