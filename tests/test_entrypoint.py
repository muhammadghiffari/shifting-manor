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
