"""Generate polished demo GIFs and refresh official screenshots headlessly.

Produces:
  - docs/screens/gameplay_demo.gif : Edited multi-act showcase trailer
      (Title -> Manual Fog & Shift -> Live Autonomous B3 AI with Charm & R16 ->
       3-Star Result -> Duel & SimLab)
  - docs/screens/watch_ai_demo.gif : Upgraded Watch AI trace replay GIF
  - Refreshes legacy screenshots (04_shift_midframe, watch_ai_log/shift/why)

Run:
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tools/make_gif.py
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCREENS = ROOT / "docs" / "screens"
GAMEPLAY_GIF = SCREENS / "gameplay_demo.gif"
WATCH_GIF = SCREENS / "watch_ai_demo.gif"


def _init_headless() -> None:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))


def _stamp_caption(surface, label: str, accent: tuple[int, int, int]) -> None:
    """Draw a sleek cinema-style chapter badge in the bottom-right margin of a frame."""
    import pygame

    from shifting_manor.ui import theme

    f = theme.font(17, bold=True)
    tw, th = f.size(label)
    rect = pygame.Rect(0, 0, tw + 28, th + 12)
    rect.bottomright = (1264, 708)
    pill = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(pill, (12, 9, 20, 230), pill.get_rect(), border_radius=10)
    pygame.draw.rect(pill, (*accent, 235), pill.get_rect(), 2, border_radius=10)
    surface.blit(pill, rect.topleft)
    theme.text(surface, label, 17, accent, rect.center, anchor="center", bold=True)


def _save_png(surface, path: Path) -> None:
    """Save via in-memory buffer so WSL/Windows NTFS mounts never fail on overwrite."""
    import pygame

    buf = io.BytesIO()
    pygame.image.save(surface, buf, namehint="PNG")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buf.getvalue())


def _snap(app, caption: str | None = None, accent: tuple[int, int, int] = (236, 188, 92)) -> bytes:
    app.draw()
    frame = app.canvas.copy()
    if caption:
        _stamp_caption(frame, caption, accent)
    buf = io.BytesIO()
    app.pygame.image.save(frame, buf, namehint="PNG")
    return buf.getvalue()


def _crossfade(prev_surf, next_surf, steps: int = 3) -> list[bytes]:
    import pygame

    out: list[bytes] = []
    for k in range(1, steps + 1):
        alpha = int(255 * (k / (steps + 1)))
        blend = prev_surf.copy()
        overlay = next_surf.copy()
        overlay.set_alpha(alpha)
        blend.blit(overlay, (0, 0))
        buf = io.BytesIO()
        pygame.image.save(blend, buf, namehint="PNG")
        out.append(buf.getvalue())
    return out


def capture_gameplay_trailer() -> list[bytes]:
    """Record a punchy, edited 4-act demo showcasing manual play, shifts & live AI."""
    _init_headless()
    import pygame

    from shifting_manor.engine.grid import rotation_mapping
    from shifting_manor.engine.types import ShiftApplied, StepResult
    from shifting_manor.ui import theme
    from shifting_manor.ui.app import App

    app = App(audio=False, windowed=True, seed="HAUNT-4F2A")
    frames: list[bytes] = []

    def add_cut(cap: str, col: tuple[int, int, int]) -> pygame.Surface:
        app.draw()
        s = app.canvas.copy()
        _stamp_caption(s, cap, col)
        return s

    # --- ACT 1: Animated Gothic Title (10 frames @ 10fps = 1.0s) ---
    cap1 = "SHIFTING MANOR · FREE IN BROWSER"
    for _ in range(10):
        app.update(0.08)
        frames.append(_snap(app, cap1, theme.GOLD))
    last_surf = add_cut(cap1, theme.GOLD)

    # --- ACT 2: Manual Play with Lantern Fog, Marks & 90-deg Wing Shift (~2.8s) ---
    cap2 = "MANUAL PLAY · LANTERN FOG & 90° WING SHIFT"
    app.start_game("explorer", "HAUNT-4F2A")
    app.update(0.05)
    next_surf = add_cut(cap2, theme.TEAL)
    frames.extend(_crossfade(last_surf, next_surf, steps=2))

    # Walk 2 steps up, place marks, then trigger real SE wing rotation mid-frame
    for _ in range(4):
        app.update(0.06)
        frames.append(_snap(app, cap2, theme.TEAL))
    app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
    for _ in range(4):
        app.update(0.05)
        frames.append(_snap(app, cap2, theme.TEAL))
    app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
    app.marks[(0, 3)] = "?"
    app.marks[(2, 3)] = "pit"
    app.marks[(1, 1)] = "safe"
    app.marks[(4, 1)] = "ghost"
    for _ in range(5):
        app.update(0.05)
        frames.append(_snap(app, cap2, theme.TEAL))

    # Trigger dramatic SE wing shift animation + save fresh 04_shift_midframe.png!
    ev = ShiftApplied(1, "cw", rotation_mapping(1, "cw", 6))
    app._after_step(StepResult(app.percepts, [ev], False))
    for step_i in range(12):
        app.update(0.075)
        if step_i == 5:
            app.draw()
            _save_png(app.canvas, SCREENS / "04_shift_midframe.png")
        frames.append(_snap(app, cap2, theme.ORANGE))
    last_surf = add_cut(cap2, theme.ORANGE)

    # --- ACT 3: Real Autonomous Live AI (Caretaker B3) playing HAUNT-4F2A (~6.0s) ---
    cap3 = "LIVE AUTONOMOUS AI (B3) · 24 RULES + R16 TRANSPORT"
    app.start_live_ai("explorer", "HAUNT-4F2A", "b3")
    app.auto_speed = 4.0
    app.update(0.05)
    next_surf = add_cut(cap3, theme.CYAN)
    frames.extend(_crossfade(last_surf, next_surf, steps=2))

    # Advance through the real live AI game capturing key beats (moves, shifts, charm, pickup, win!)
    guard = 0
    while app.scene == "play" and guard < 180:
        app.update(0.08)
        if guard % 2 == 0 or app.shift_anim is not None or app.fx.beams:
            frames.append(_snap(app, cap3, theme.CYAN))
        guard += 1

    # Hold 3-Star Victory Result screen briefly
    cap4 = "3★ VICTORY · SCORE 1157 · 0 AVOIDABLE LOSSES"
    for _ in range(14):
        app.update(0.06)
        frames.append(_snap(app, cap4, theme.GOLD))
    last_surf = add_cut(cap4, theme.GOLD)

    # --- ACT 4: Interactive Tutorial & Simulation Lab Finale (~2.4s) ---
    cap5 = "SIMULATION LAB · B3 BEATS SHIFT-BLIND BY +16.5%!"
    app.start_simlab()
    next_surf = add_cut(cap5, theme.TEAL)
    frames.extend(_crossfade(last_surf, next_surf, steps=2))
    for _ in range(14):
        frames.append(_snap(app, cap5, theme.TEAL))

    # Refresh remaining Watch AI screenshots cleanly while pygame is live
    app.start_watch("explorer", "HAUNT-4F2A", "b3")
    app.watch.set_step(13)
    app.watch.tab = 1
    app.draw()
    _save_png(app.canvas, SCREENS / "watch_ai_log.png")
    app.watch.set_step(8)
    app.watch.elapsed = 0.25
    app.watch.tab = 0
    app.draw()
    _save_png(app.canvas, SCREENS / "watch_ai_shift_moment.png")
    app.watch.set_step(13)
    app.watch._open_room_proof((2, 2))
    app.draw()
    _save_png(app.canvas, SCREENS / "watch_ai_why.png")

    app.pygame.quit()
    return frames


def capture_watch_frames(seed: str = "HAUNT-4F2A", mode: str = "explorer") -> list[bytes]:
    _init_headless()
    from shifting_manor.ui.app import App

    app = App(audio=False, windowed=True, seed=seed)
    app.start_watch(mode, seed, "b3")
    watch = app.watch
    assert watch is not None
    watch.speed = 4.0
    watch.restart()
    watch.playing = True

    frames: list[bytes] = []
    for i in range(1500):
        app.update(1.0 / 60.0)
        if i % 6 == 0:
            frames.append(_snap(app))
        if watch.finished():
            for _ in range(8):
                frames.append(_snap(app))
            break
    app.pygame.quit()
    return frames


def assemble(frames: list[bytes], out: Path, *, fps: int = 10, width: int = 800) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise SystemExit("ffmpeg not found on PATH")
    with tempfile.TemporaryDirectory() as td:
        for n, png in enumerate(frames):
            Path(td, f"f{n:05d}.png").write_bytes(png)
        palette = Path(td, "p.png")
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-framerate",
                str(fps),
                "-i",
                f"{td}/f%05d.png",
                "-vf",
                f"scale={width}:-1:flags=lanczos,palettegen=max_colors=192:stats_mode=diff",
                str(palette),
            ],
            check=True,
            capture_output=True,
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-framerate",
                str(fps),
                "-i",
                f"{td}/f%05d.png",
                "-i",
                str(palette),
                "-lavfi",
                f"scale={width}:-1:flags=lanczos [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=4",
                "-loop",
                "0",
                str(out),
            ],
            check=True,
            capture_output=True,
        )


def main() -> None:
    gameplay = capture_gameplay_trailer()
    assemble(gameplay, GAMEPLAY_GIF, fps=10, width=820)
    print(f"{GAMEPLAY_GIF} <- {len(gameplay)} frames ({GAMEPLAY_GIF.stat().st_size / 1e6:.2f} MB)")

    watch = capture_watch_frames()
    assemble(watch, WATCH_GIF, fps=10, width=720)
    print(f"{WATCH_GIF} <- {len(watch)} frames ({WATCH_GIF.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
