"""Generate the README hero GIF: Watch AI autoplay with the live inference log.

Headless (SDL dummy) replay of the watch scene, capturing every Nth simulated
frame, assembled into a palette-optimised GIF with ffmpeg.

    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tools/make_gif.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

CAPTURE_EVERY = 6  # 60 Hz simulated -> 10 fps GIF
GIF_FPS = 10
GIF_WIDTH = 640
OUT = Path("docs/screens/watch_ai_demo.gif")


def capture_frames(seed: str, mode: str, max_frames: int = 1800) -> list[bytes]:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    import io

    from shifting_manor.ui.app import App

    app = App(audio=False, windowed=True, seed=seed)
    app.start_watch(mode, seed, "b3")
    watch = app.watch
    assert watch is not None
    watch.speed = 4.0
    watch.restart()
    watch.playing = True

    frames: list[bytes] = []
    for i in range(max_frames):
        app.update(1.0 / 60.0)
        app.draw()
        if i % CAPTURE_EVERY == 0:
            buf = io.BytesIO()
            app.pygame.image.save(app.canvas, buf, namehint="PNG")
            frames.append(buf.getvalue())
        if watch.finished():
            break
    app.pygame.quit()
    return frames


def assemble(frames: list[bytes], out: Path) -> None:
    import shutil

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
                str(GIF_FPS),
                "-i",
                f"{td}/f%05d.png",
                "-vf",
                f"scale={GIF_WIDTH}:-1:flags=lanczos,palettegen=stats_mode=diff",
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
                str(GIF_FPS),
                "-i",
                f"{td}/f%05d.png",
                "-i",
                str(palette),
                "-lavfi",
                f"scale={GIF_WIDTH}:-1:flags=lanczos [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=4",
                "-loop",
                "0",
                str(out),
            ],
            check=True,
            capture_output=True,
        )


def main() -> None:
    frames = capture_frames("HAUNT-4F2A", "explorer")
    assemble(frames, OUT)
    print(f"{OUT} <- {len(frames)} captured frames ({OUT.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
