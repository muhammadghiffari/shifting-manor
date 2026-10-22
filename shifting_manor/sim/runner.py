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
from shifting_manor.sim.stats import calibration, mcnemar, wilson_ci

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
    par_actions: int | None = None
    stars: int = 0
    gambles: list[dict[str, Any]] = field(default_factory=list)

    @property
    def win(self) -> bool:
        return self.outcome == "escaped_treasure"


def run_game(
    mode: str,
    seed: str,
    agent_name: str,
    *,
    max_steps: int = 500,
    par: int | None = None,
) -> GameRecord:
    game = Game(mode, seed)
    agent = make_agent(agent_name, game.info())
    percepts = game.observe()
    events: list[Any] = []
    forced_guess = False
    gambles: list[dict[str, Any]] = []
    steps = 0
    while not game.state.done and steps < max_steps:
        action = agent.act(percepts, events)
        gamble = getattr(agent, "last_gamble", None)
        entry = None
        if gamble is not None:
            forced_guess = True
            entry = {
                "target": list(gamble.target),
                "target_risk": gamble.target_risk,
                "step_cell": list(gamble.step_cell) if gamble.step_cell else None,
                "step_risk": gamble.step_risk,
                "died": False,
            }
            gambles.append(entry)
        result = game.step(action)
        if entry is not None and game.state.outcome in ("died_pit", "died_ghost"):
            entry["died"] = True
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
        par_actions=par,
        stars=game.stars(par) if par is not None else 0,
        gambles=gambles,
    )


def _metrics(records: list[GameRecord]) -> dict[str, Any]:
    n = len(records)
    if not n:
        return {}
    outcomes = Counter(r.outcome for r in records)
    wins = sum(r.win for r in records)
    lo, hi = wilson_ci(wins, n)
    return {
        "games": n,
        "wins": wins,
        "win_rate": wins / n,
        "win_rate_ci95": [lo, hi],
        "escaped_any": sum(r.outcome.startswith("escaped") for r in records) / n,
        "mean_score": sum(r.score for r in records) / n,
        "mean_actions": sum(r.actions for r in records) / n,
        "mean_stars": sum(r.stars for r in records) / n,
        "stars": {str(k): sum(r.stars == k for r in records) for k in range(4)},
        "mean_rules_fired": sum(r.rules_fired for r in records) / n,
        "forced_guess_rate": sum(r.forced_guess for r in records) / n,
        "gamble_actions": sum(len(r.gambles) for r in records),
        "deaths_pit": outcomes["died_pit"],
        "deaths_ghost": outcomes["died_ghost"],
        "oil_out": outcomes["oil_out"],
        "escaped_empty": outcomes["escaped_empty"],
        "stalled": outcomes["stalled"],
        "warning_runs": sum(bool(r.warnings) for r in records),
    }


def _run_seed_bundle(mode: str, seed: str, agents: tuple[str, ...]) -> list[GameRecord]:
    """One seed for all agents, with one oracle run shared as the star par."""
    par_record = run_game(mode, seed, "b4")
    par = par_record.actions
    par_record.par_actions = par
    par_record.stars = 3 if par_record.win else (1 if par_record.outcome == "escaped_empty" else 0)
    records: list[GameRecord] = []
    for agent_name in agents:
        if agent_name == "b4":
            records.append(par_record)
        else:
            records.append(run_game(mode, seed, agent_name, par=par))
    return records


def run_suite(
    *,
    runs: int = 200,
    modes: tuple[str, ...] = MODE_NAMES,
    agents: tuple[str, ...] = AGENTS,
    seed_prefix: str = "SIM",
    seed_start: int = 0,
    jobs: int = 1,
    progress: bool = True,
) -> dict[str, Any]:
    results: dict[str, Any] = {
        "config": {
            "runs": runs,
            "seed_prefix": seed_prefix,
            "seed_start": seed_start,
            "agents": list(agents),
        },
        "modes": {},
    }
    for mode in modes:
        by_agent: dict[str, list[GameRecord]] = {a: [] for a in agents}
        seeds = [f"{seed_prefix}-{mode.upper()}-{seed_start + i:04d}" for i in range(runs)]

        if jobs > 1:
            from concurrent.futures import ProcessPoolExecutor

            with ProcessPoolExecutor(max_workers=jobs) as pool:
                futures = [pool.submit(_run_seed_bundle, mode, seed, agents) for seed in seeds]
                for i, future in enumerate(futures):
                    for record in future.result():
                        by_agent[record.agent].append(record)
                    if progress and (i + 1) % 100 == 0:
                        print(f"  {mode}: {i + 1}/{runs} seeds", flush=True)
        else:
            for i, seed in enumerate(seeds):
                for record in _run_seed_bundle(mode, seed, agents):
                    by_agent[record.agent].append(record)
                if progress and (i + 1) % 100 == 0:
                    print(f"  {mode}: {i + 1}/{runs} seeds", flush=True)

        paired = {}
        for other in ("b2", "b2b"):
            if "b3" in by_agent and other in by_agent:
                paired[f"b3_vs_{other}"] = mcnemar(
                    [r.win for r in by_agent["b3"]],
                    [r.win for r in by_agent[other]],
                )
        results["modes"][mode] = {
            "agents": {a: _metrics(recs) for a, recs in by_agent.items()},
            "paired": paired,
            "calibration": {a: calibration(recs) for a, recs in by_agent.items()},
            "records": [r.__dict__ | {"win": r.win} for recs in by_agent.values() for r in recs],
        }
    return results


def format_table(results: dict[str, Any]) -> str:
    lines = [
        "mode      agent  win%    95% CI        score  actions  stars  forced  gambles",
        "------------------------------------------------------------------------------",
    ]
    for mode, data in results["modes"].items():
        for agent, m in data["agents"].items():
            if not m:
                continue
            lo, hi = m["win_rate_ci95"]
            lines.append(
                f"{mode:<10}{agent:<7}{100 * m['win_rate']:>5.1f} "
                f"[{100 * lo:>4.1f},{100 * hi:>5.1f}] {m['mean_score']:>7.1f} "
                f"{m['mean_actions']:>8.1f} {m['mean_stars']:>6.2f} "
                f"{100 * m['forced_guess_rate']:>5.1f}% {m['gamble_actions']:>7}"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="python -m shifting_manor.sim")
    parser.add_argument("--runs", type=int, default=200)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--out", default="sim/results.json")
    parser.add_argument("--modes", default=",".join(MODE_NAMES))
    parser.add_argument("--agents", default=",".join(AGENTS))
    parser.add_argument("--seed-prefix", default="SIM")
    parser.add_argument("--jobs", type=int, default=1, help="worker processes across seeds")
    args = parser.parse_args(argv)

    modes = tuple(m.strip() for m in args.modes.split(",") if m.strip())
    agents = tuple(a.strip() for a in args.agents.split(",") if a.strip())
    unknown = set(modes) - set(MODE_NAMES)
    if unknown:
        parser.error(f"unknown modes: {sorted(unknown)}")
    print(f"Running {args.runs} seeds x {len(modes)} modes x {len(agents)} agents ...")
    results = run_suite(
        runs=args.runs,
        modes=modes,
        agents=agents,
        seed_prefix=args.seed_prefix,
        seed_start=args.seed_start,
        jobs=args.jobs,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(format_table(results))
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
