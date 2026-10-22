"""Headless M4 UI tests: real keyboard/mouse events, every scene draws."""

from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from shifting_manor.ui.app import App

    app = App(audio=False, windowed=True)
    yield app
    app.pygame.quit()


def test_title_and_mode_select_flow(app):
    import pygame

    app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert app.scene == "modes"
    app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert app.scene == "play"
    assert app.game is not None


def test_keyboard_move_and_charm(app):
    import pygame

    app.start_game("apprentice", "UI-TEST")
    app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
    assert app.game.state.agent == (0, 1)
    assert app.game.state.actions_taken == 1

    app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_c))
    assert app.charm_aim is True
    app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
    assert app.game.state.charms_cast == 1
    assert app.game.state.charm_available is False


def test_mouse_move_and_cycle_mark(app):
    import pygame

    app.start_game("apprentice", "UI-TEST")
    assert app.game is not None
    target = app._cell_rect((0, 1)).center
    app.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=target))
    assert app.game.state.agent == (0, 1)

    app.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=3, pos=target))
    assert app.marks[(0, 1)] == "?"
    for expected in ("pit", "ghost", "safe", None):
        app.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=3, pos=target))
        assert app.marks.get((0, 1)) == expected


def test_shift_animation_rotates_marks(app):
    from shifting_manor.engine.grid import rotation_mapping
    from shifting_manor.engine.types import ShiftApplied, StepResult

    app.start_game("explorer", "UI-TEST")
    app.marks[(0, 3)] = "?"
    event = ShiftApplied(2, "ccw", rotation_mapping(2, "ccw", 6))
    app._after_step(StepResult(app.percepts, [event], False))

    assert app.marks[(2, 3)] == "?"
    assert app.marks.get((0, 3)) is None
    assert app.shift_anim is not None
    app.draw()
    app.update(2.0)
    assert app.shift_anim is None


def test_every_scene_draws_and_result_is_reachable(app):
    import pygame

    app.draw()  # title
    app.scene = "modes"
    app.draw()
    app.start_game("explorer", "UI-TEST")
    app.draw()  # play
    app.paused = True
    app.draw()  # pause overlay
    app.paused = False

    assert app.game is not None
    app.game.state.done = True
    app.game.state.outcome = "escaped_treasure"
    app._finish()
    assert app.scene == "result"
    app.draw()
    app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r))
    assert app.scene == "play"


def test_shift_skip_by_any_key(app):
    import pygame

    app.start_game("explorer", "UI-TEST")
    app.shift_anim = SimpleNamespace(elapsed=0.0, duration=1.0)
    app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
    assert app.shift_anim is None


def test_result_layout_keeps_board_and_buttons_clear(app):
    app.start_game("explorer", "UI-TEST")
    assert app.game is not None
    app.game.state.done = True
    app.game.state.outcome = "escaped_empty"
    app._finish()
    app.draw()

    board = app._result_board_rect()
    panel = app._result_panel_rect()
    assert not board.colliderect(panel)
    for button in app._result_buttons():
        assert panel.contains(button)


def test_watch_view_wraps_long_r16_lines_without_truncation(app):
    """Watch AI inference log and trace wrap long R16 lines across rows without truncation."""
    import pygame

    from shifting_manor.trace import build_trace, format_firing
    from shifting_manor.ui import theme
    from shifting_manor.ui.watch import WatchView

    store = build_trace("explorer", "HAUNT-4F2A", "b3")
    r16 = next(f for f in store.steps[8].firings if f.rule_id == "R16")
    text = format_firing(r16)

    # 1. theme.wrap wraps without truncation
    lines = theme.wrap(text, 15, 566)
    assert len(lines) >= 2, "Long R16 line must wrap into at least 2 lines"
    assert not any(line.endswith("…") for line in lines), (
        "Lines must not be truncated with ellipsis"
    )
    font = theme.font(15)
    for line in lines:
        assert font.size(line)[0] <= 566
    # Content preserved
    assert " ".join(" ".join(lines).split()) == " ".join(text.split())

    # 2. WatchView log tab draws wrapped multi-line row with enlarged hit rect
    view = WatchView(store, to_logical=lambda p: p, on_exit=lambda: None)
    canvas = pygame.Surface((1280, 720))
    view.tab = 1
    view.set_step(8)
    view.draw(canvas)

    r16_hits = [rect for rect, row in view._log_hits if row.text.startswith("R16")]
    assert len(r16_hits) >= 1
    for rect in r16_hits:
        # A single line row has height 17; a 2-line wrapped row has height 35.
        assert rect.height >= 35, f"Expected wrapped multi-line height >= 35, got {rect.height}"

    # 3. WatchView trace tab draws without crashing
    view.tab = 0
    view.draw(canvas)
