"""Headless batch runner and baseline metrics."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shifting_manor.agents import make_agent
from shifting_manor.engine.game import Game
from shifting_manor.engine.modes import MODES

AGENTS = ("b0", "b1", "b2", "b2b", "b3", "b4")
MODE_NAMES = tuple(MODES)


@dataclass
class GameRecord:
    mode: str
    seed: str
    agent: str
    outcome: str
    score: int
    actions: int
    oil_left: int
    forced_guess: bool = False
    rules_fired: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def win(self) -> bool:
        return self.outcome == "escaped_treasure"


def run_game(mode: str, seed: str, agent_name: str, *, max_steps: int = 500) -> GameRecord:
    game = Game(mode, seed)
    agent = make_agent(agent_name, game.info())
    percepts = game.observe()
    events: list[Any] = []
    forced_guess = False
    steps = 0
    while not game.state.done and steps < max_steps:
        action = agent.act(percepts, events)
        explanation = agent.explain()
        if any(f.rule_id == "R22" for f in explanation.firings):
            forced_guess = True
        result = game.step(action)
        percepts = result.percepts
        events = result.events
        steps += 1
    if not game.state.done:
        game.state.done = True
        game.state.outcome = "stalled"
    kb = getattr(agent, "kb", None)
    return GameRecord(
        mode=mode,
        seed=seed,
        agent=agent_name,
        outcome=game.state.outcome or "stalled",
        score=game.score(),
        actions=game.state.actions_taken,
        oil_left=game.state.oil,
        forced_guess=forced_guess,
        rules_fired=len(kb.log) if kb is not None else 0,
        warnings=list(kb.warnings) if kb is not None else [],
    )


def _metrics(records: list[GameRecord]) -> dict[str, Any]:
    n = len(records)
    if not n:
        return {}
    outcomes = Counter(r.outcome for r in records)
    return {
        "games": n,
        "wins": sum(r.win for r in records),
        "win_rate": sum(r.win for r in records) / n,
        "escaped_any": sum(r.outcome.startswith("escaped") for r in records) / n,
        "mean_score": sum(r.score for r in records) / n,
        "mean_actions": sum(r.actions for r in records) / n,
        "mean_rules_fired": sum(r.rules_fired for r in records) / n,
        "forced_guess_rate": sum(r.forced_guess for r in records) / n,
        "deaths_pit": outcomes["died_pit"],
        "deaths_ghost": outcomes["died_ghost"],
        "oil_out": outcomes["oil_out"],
        "escaped_empty": outcomes["escaped_empty"],
        "stalled": outcomes["stalled"],
        "warning_runs": sum(bool(r.warnings) for r in records),
    }


def run_suite(
    *,
    runs: int = 200,
    modes: tuple[str, ...] = MODE_NAMES,
    agents: tuple[str, ...] = AGENTS,
    seed_prefix: str = "SIM",
    progress: bool = True,
) -> dict[str, Any]:
    results: dict[str, Any] = {"config": {"runs": runs, "seed_prefix": seed_prefix}, "modes": {}}
    for mode in modes:
        by_agent: dict[str, list[GameRecord]] = {a: [] for a in agents}
        for i in range(runs):
            seed = f"{seed_prefix}-{mode.upper()}-{i:03d}"
            for agent_name in agents:
                record = run_game(mode, seed, agent_name)
                by_agent[agent_name].append(record)
            if progress and (i + 1) % 25 == 0:
                print(f"  {mode}: {i + 1}/{runs} seeds", flush=True)
        results["modes"][mode] = {
            "agents": {a: _metrics(recs) for a, recs in by_agent.items()},
            "records": [r.__dict__ | {"win": r.win} for recs in by_agent.values() for r in recs],
        }
    return results


def format_table(results: dict[str, Any]) -> str:
    lines = [
        "mode      agent  win%   score  actions  pit  ghost  oil  forced",
        "---------------------------------------------------------------",
    ]
    for mode, data in results["modes"].items():
        for agent, m in data["agents"].items():
            if not m:
                continue
            lines.append(
                f"{mode:<10}{agent:<7}{100 * m['win_rate']:>5.1f} "
                f"{m['mean_score']:>7.1f} {m['mean_actions']:>8.1f} "
                f"{m['deaths_pit']:>4} {m['deaths_ghost']:>6} {m['oil_out']:>4} "
                f"{100 * m['forced_guess_rate']:>5.1f}%"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="python -m shifting_manor.sim")
    parser.add_argument("--runs", type=int, default=200)
    parser.add_argument("--out", default="sim/results.json")
    parser.add_argument("--modes", default=",".join(MODE_NAMES))
    parser.add_argument("--agents", default=",".join(AGENTS))
    parser.add_argument("--seed-prefix", default="SIM")
    args = parser.parse_args(argv)

    modes = tuple(m.strip() for m in args.modes.split(",") if m.strip())
    agents = tuple(a.strip() for a in args.agents.split(",") if a.strip())
    unknown = set(modes) - set(MODE_NAMES)
    if unknown:
        parser.error(f"unknown modes: {sorted(unknown)}")
    print(f"Running {args.runs} seeds x {len(modes)} modes x {len(agents)} agents ...")
    results = run_suite(runs=args.runs, modes=modes, agents=agents, seed_prefix=args.seed_prefix)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(format_table(results))
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
