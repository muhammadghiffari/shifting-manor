"""`python -m shifting_manor` entry point."""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="shifting-manor")
    parser.add_argument("--mode", choices=["apprentice", "explorer", "haunted"], default=None)
    parser.add_argument("--seed", default="HAUNT-4F2A")
    parser.add_argument(
        "--agent",
        choices=["b0", "b1", "b2", "b2b", "b3", "b4", "b5"],
        default="b3",
        help="agent for --auto / Watch AI (default: b3)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="launch Live Autonomous AI Play immediately on the selected mode and seed",
    )
    parser.add_argument(
        "--duel",
        action="store_true",
        help="launch Human vs AI Duel mode on the selected mode and seed",
    )
    parser.add_argument(
        "--tutorial",
        action="store_true",
        help="launch the interactive 4-lesson tutorial",
    )
    parser.add_argument(
        "--simlab",
        action="store_true",
        help="launch the Simulation Lab empirical charts",
    )
    parser.add_argument(
        "--windowed", action="store_true", default=True, help="windowed (the default)"
    )
    parser.add_argument("--fullscreen", action="store_true", help="use the whole screen")
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--frames", type=int, default=None, help="run N frames then exit")
    parser.add_argument("--screenshot", default=None, help="save the final frame as a PNG")
    parser.add_argument(
        "--demo", action="store_true", help="start Watch AI and loop the demo seeds"
    )
    args = parser.parse_args(argv)

    from shifting_manor.ui.app import main as ui_main

    ui_main(
        audio=not args.no_audio,
        windowed=not args.fullscreen,
        seed=args.seed,
        mode=args.mode,
        agent=args.agent,
        auto=args.auto,
        duel=args.duel,
        tutorial=args.tutorial,
        simlab=args.simlab,
        frames=args.frames,
        screenshot=args.screenshot,
        demo=args.demo,
    )


if __name__ == "__main__":
    main()
