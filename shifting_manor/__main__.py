"""`python -m shifting_manor` entry point."""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="shifting-manor")
    parser.add_argument("--mode", choices=["apprentice", "explorer", "haunted"], default=None)
    parser.add_argument("--seed", default="HAUNT-4F2A")
    parser.add_argument(
        "--windowed", action="store_true", default=True, help="windowed (the default)"
    )
    parser.add_argument("--fullscreen", action="store_true", help="use the whole screen")
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--frames", type=int, default=None, help="run N frames then exit")
    parser.add_argument("--screenshot", default=None, help="save the final frame as a PNG")
    args = parser.parse_args(argv)

    from shifting_manor.ui.app import main as ui_main

    ui_main(
        audio=not args.no_audio,
        windowed=not args.fullscreen,
        seed=args.seed,
        mode=args.mode,
        frames=args.frames,
        screenshot=args.screenshot,
    )


if __name__ == "__main__":
    main()
