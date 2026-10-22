"""M2 CLI demo test: a full game prints percepts, rule firings and actions."""

from __future__ import annotations

from shifting_manor.cli import main


def test_cli_b3_full_game_verbose(capsys):
    code = main(["--agent", "b3", "--mode", "apprentice", "--seed", "CLI-DEMO", "--verbose"])
    out = capsys.readouterr().out
    assert code == 0
    assert "RESULT outcome=" in out
    assert "percepts=[" in out
    assert "new:" in out
    assert "=>" in out


def test_cli_runs_every_baseline(capsys):
    for name in ("b0", "b1", "b2", "b2b", "b3"):
        code = main(["--agent", name, "--mode", "apprentice", "--seed", f"CLI-{name}"])
        assert code == 0
    out = capsys.readouterr().out
    assert out.count("RESULT outcome=") == 5
