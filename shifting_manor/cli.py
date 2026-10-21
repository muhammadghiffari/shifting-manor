"""Text-mode demo: percepts -> rules fired -> action for a full game."""

from __future__ import annotations

import argparse
import sys

from shifting_manor.agents import make_agent
from shifting_manor.engine.game import Game
from shifting_manor.engine.types import Percepts


def describe_percepts(p: Percepts) -> str:
    bits = []
    for name in ("breeze", "chill", "glimmer", "bump", "scream"):
        if getattr(p, name):
            bits.append(name)
    if p.rumble is not None:
        bits.append(f"rumble(wing={p.rumble.wing},{p.rumble.direction},{p.rumble.in_actions})")
    return ", ".join(bits) if bits else "quiet"


def describe_events(events) -> str:
    return ", ".join(repr(e) for e in events) if events else "-"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m shifting_manor.cli")
    parser.add_argument("--agent", default="b3", help="b0|b1|b2|b2b|b3|b4/oracle")
    parser.add_argument("--mode", default="explorer", choices=["apprentice", "explorer", "haunted"])
    parser.add_argument("--seed", default="HAUNT-4F2A")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--max-steps", type=int, default=500)
    args = parser.parse_args(argv)

    game = Game(args.mode, args.seed)
    info = game.info()
    agent = make_agent(args.agent, info)
    print(f"Shifting Manor demo | agent={agent.name} mode={args.mode} seed={args.seed}")
    print(f"size={info.size} pits={info.pit_total} oil={info.oil} shift_every={info.shift_every}")
    print("-" * 78)

    percepts = game.observe()
    events = []
    step = 0
    total_firings = 0
    while not game.state.done and step < args.max_steps:
        action = agent.act(percepts, events)
        explanation = agent.explain()
        total_firings += len(explanation.firings)
        print(
            f"T{step:02d} at={game.state.agent} oil={game.state.oil:02d} "
            f"percepts=[{describe_percepts(percepts)}] action={action!r}"
        )
        if args.verbose:
            ids = sorted({f.rule_id for f in explanation.firings})
            print(f"     rules fired: {','.join(ids) if ids else '(none)'}")
            for firing in explanation.firings:
                premises = ", ".join(repr(p) for p in firing.premises) or "()"
                conclusions = ", ".join(repr(c) for c in firing.conclusions) or "()"
                print(f"     {firing.rule_id}: {premises} => {conclusions}")
            print(f"     why: {explanation.thought}")
        result = game.step(action)
        if result.events:
            print(f"     events: {describe_events(result.events)}")
        percepts = result.percepts
        events = result.events
        step += 1

    if not game.state.done:
        print(f"\nStopped after {step} steps without finishing (max-steps).")
        return 2
    print("-" * 78)
    print(
        f"RESULT outcome={game.state.outcome} score={game.score()} "
        f"stars={game.stars()} actions={game.state.actions_taken} oil_left={game.state.oil}"
    )
    print(f"rule firings (sum over turns)={total_firings}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
