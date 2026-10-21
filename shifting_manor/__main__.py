"""`python -m shifting_manor` entry point."""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="shifting-manor")
    parser.add_argument("--mode", choices=["apprentice", "explorer", "haunted"], default="explorer")
    parser.add_argument("--seed", default="HAUNT-4F2A")
    parser.add_argument("--windowed", action="store_true", help="window instead of fullscreen")
    parser.add_argument("--no-audio", action="store_true")
    args = parser.parse_args(argv)

    from shifting_manor.ui.app import main as ui_main

    ui_main(audio=not args.no_audio, windowed=args.windowed, seed=args.seed)


if __name__ == "__main__":
    main()
