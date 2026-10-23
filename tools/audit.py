"""Full Optimality Audit runner for PR2.

Evaluates B3 vs B5 vs B4 across 1,000 reporting seeds per mode
(SIM-<MODE>-10000..10999), measures B3 risk calibration against the exact posterior,
classifies every B3 loss, and computes paired statistical tests.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shifting_manor.agents import make_agent
from shifting_manor.agents.planner import cautious_route
from shifting_manor.engine.game import Game
from shifting_manor.engine.grid import neighbours
from shifting_manor.engine.types import Cell
from shifting_manor.sim.stats import mcnemar, wilson_ci
from tools.posterior import ExactPosterior


@dataclass
class FailureReport:
    seed: str
    mode: str
    outcome: str
    classification: str  # "avoidable", "suboptimal_gamble", "forced"
    pos: Cell
    actions_taken: int
    detail: str


@dataclass
class SeedAuditResult:
    seed: str
    mode: str
    b3_outcome: str
    b3_score: int
    b3_actions: int
    b3_stars: int
    b5_outcome: str
    b5_score: int
    b5_actions: int
    b5_stars: int
    b4_par: int
    b4_outcome: str
    calibration_pairs: list[tuple[float, float, int]]  # (b3_risk, exact_risk, is_hazard)
    failure: FailureReport | None


def _zero_risk_component(pos: Cell, size: int, post: ExactPosterior) -> dict[Cell, int]:
    """Steps-to-pos for every cell reachable stepping only through exact risk-0 cells."""
    queue = deque([pos])
    dist = {pos: 0}
    while queue:
        cur = queue.popleft()
        for nxt in neighbours(cur, size):
            if nxt not in dist and post.cell_hazard_risk(nxt) <= 1e-9:
                dist[nxt] = dist[cur] + 1
                queue.append(nxt)
    return dist


def audit_single_seed(mode: str, seed: str) -> SeedAuditResult:
    # 1. Oracle run (B4) for par and validation
    g4 = Game(mode, seed)
    b4 = make_agent("b4", g4.info())
    p4, e4 = g4.observe(), []
    while not g4.state.done:
        a = b4.act(p4, e4)
        res = g4.step(a)
        p4, e4 = res.percepts, res.events
    b4_par = g4.state.actions_taken
    b4_outcome = g4.state.outcome or "unknown"

    # 2. B3 run with exact posterior monitoring
    g3 = Game(mode, seed)
    b3 = make_agent("b3", g3.info())
    post = ExactPosterior.from_info(g3.info())

    p3, e3 = g3.observe(), []
    calibration_pairs: list[tuple[float, float, int]] = []
    last_state = None

    while not g3.state.done:
        post.observe(g3.state.agent, p3, e3)
        action = b3.act(p3, e3)

        # Collect calibration data from gamble candidate evaluations
        if getattr(b3, "gamble_candidates", None):
            for cand in b3.gamble_candidates:
                c = cand.cell
                exact_r = post.cell_hazard_risk(c)
                is_haz = int(
                    c in g3.state.pits or (g3.state.ghost is not None and c == g3.state.ghost)
                )
                calibration_pairs.append((round(cand.risk, 6), round(exact_r, 6), is_haz))

        last_state = (
            g3.state.agent,
            action,
            getattr(b3, "last_gamble", None),
            getattr(b3, "gamble_candidates", []),
            getattr(b3, "last_route", None),
            post,
            b3.kb,
            g3.state.has_treasure,
            g3.state.oil,
        )

        res = g3.step(action)
        p3, e3 = res.percepts, res.events

    b3_outcome = g3.state.outcome or "unknown"
    b3_score = g3.score()
    b3_actions = g3.state.actions_taken
    b3_stars = g3.stars(b4_par)

    # Failure classification if lost
    failure: FailureReport | None = None
    if b3_outcome != "escaped_treasure" and last_state is not None:
        pos, _act, gamble, g_cands, chosen_route, fatal_post, fatal_kb, carried, oil = last_state

        def route_death(cells: list[Cell]) -> float:
            survival = 1.0
            for c in cells[1:]:
                survival *= 1.0 - fatal_post.cell_hazard_risk(c)
            return 1.0 - survival

        # Avoidable = a perfect reasoner could have *won with certainty* from this
        # state on the remaining oil: a zero-risk round trip existed that ends
        # carried at the entrance (engine kills at oil <= 0; Leave is free, so
        # surviving k steps needs oil >= k + 1). Dying with the treasure outside
        # the component is forced: every winning route still crosses a >0-risk
        # step (the generator's hazard-free path is invisible to the posterior),
        # and refuge pockets where the agent could hide forever win nothing.
        comp = _zero_risk_component(pos, g3.state.size, fatal_post)
        entrance = g3.state.entrance
        treasure = g3.state.treasure
        steps = None  # zero-risk moves to arrive carried at the entrance
        if carried and entrance in comp:
            steps = comp[entrance]
        elif treasure in comp and entrance in comp:
            # shortest treasure->entrance walk that stays inside the component
            dq = deque([treasure])
            back = {treasure: 0}
            while dq:
                cur = dq.popleft()
                for nxt in neighbours(cur, g3.state.size):
                    if nxt in comp and nxt not in back:
                        back[nxt] = back[cur] + 1
                        dq.append(nxt)
            if entrance in back:
                steps = comp[treasure] + back[entrance]
        zero_win = steps is not None and oil >= steps + 1

        if zero_win:
            failure = FailureReport(
                seed=seed,
                mode=mode,
                outcome=b3_outcome,
                classification="avoidable",
                pos=pos,
                actions_taken=b3_actions,
                detail=(
                    f"Zero-risk win route of {steps} steps existed with {oil} oil (exact posterior)"
                ),
            )
        elif gamble is not None and chosen_route is not None and len(chosen_route.cells) > 1:
            # Was this gamble suboptimal under the exact posterior? Compare death
            # probability of the executed route vs every candidate's best route.
            chosen_death = route_death(chosen_route.cells)
            cand_deaths = [
                route_death(rc.cells)
                for rc in (
                    cautious_route(fatal_kb, pos, cand.cell, risk_of=fatal_post.cell_hazard_risk)
                    for cand in g_cands
                )
                if rc is not None and len(rc.cells) > 1
            ]
            min_death = min(cand_deaths) if cand_deaths else chosen_death

            if chosen_death > min_death + 1e-4:
                failure = FailureReport(
                    seed=seed,
                    mode=mode,
                    outcome=b3_outcome,
                    classification="suboptimal_gamble",
                    pos=pos,
                    actions_taken=b3_actions,
                    detail=f"Chosen route death {chosen_death:.4f} > min available {min_death:.4f}",
                )
            else:
                failure = FailureReport(
                    seed=seed,
                    mode=mode,
                    outcome=b3_outcome,
                    classification="forced",
                    pos=pos,
                    actions_taken=b3_actions,
                    detail=f"Minimal-death gamble {chosen_death:.4f} on forced frontier guess",
                )
        else:
            failure = FailureReport(
                seed=seed,
                mode=mode,
                outcome=b3_outcome,
                classification="forced",
                pos=pos,
                actions_taken=b3_actions,
                detail=f"No certain winning route on remaining oil: outcome={b3_outcome}",
            )

    # 3. B5 run
    g5 = Game(mode, seed)
    b5 = make_agent("b5", g5.info())
    p5, e5 = g5.observe(), []
    while not g5.state.done:
        a = b5.act(p5, e5)
        res = g5.step(a)
        p5, e5 = res.percepts, res.events
    b5_outcome = g5.state.outcome or "unknown"
    b5_score = g5.score()
    b5_actions = g5.state.actions_taken
    b5_stars = g5.stars(b4_par)

    return SeedAuditResult(
        seed=seed,
        mode=mode,
        b3_outcome=b3_outcome,
        b3_score=b3_score,
        b3_actions=b3_actions,
        b3_stars=b3_stars,
        b5_outcome=b5_outcome,
        b5_score=b5_score,
        b5_actions=b5_actions,
        b5_stars=b5_stars,
        b4_par=b4_par,
        b4_outcome=b4_outcome,
        calibration_pairs=calibration_pairs,
        failure=failure,
    )


def _worker_task(args: tuple[str, str]) -> SeedAuditResult:
    mode, seed = args
    return audit_single_seed(mode, seed)


def run_audit(
    modes: tuple[str, ...] = ("apprentice", "explorer", "haunted"),
    count_per_mode: int = 1000,
    seed_start: int = 10000,
    workers: int | None = None,
) -> dict[str, Any]:
    max_workers = workers or min(12, os.cpu_count() or 4)
    print(
        f"Starting audit: {len(modes)} modes x {count_per_mode} seeds using {max_workers} workers..."
    )
    t_start = time.time()

    all_results: dict[str, list[SeedAuditResult]] = {}

    for mode in modes:
        t0 = time.time()
        seeds = [f"SIM-{mode.upper()}-{seed_start + i}" for i in range(count_per_mode)]
        tasks = [(mode, s) for s in seeds]

        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            results = list(pool.map(_worker_task, tasks, chunksize=10))

        all_results[mode] = results
        t_mode = time.time() - t0
        print(
            f"Mode {mode.upper()} completed: {count_per_mode} seeds in {t_mode:.2f}s ({t_mode / count_per_mode:.3f}s/seed)"
        )

    total_time = time.time() - t_start
    print(f"All runs finished in {total_time:.2f}s.")

    # Process and summarize
    summary: dict[str, Any] = {"modes": {}, "total_time": round(total_time, 2)}

    for mode, results in all_results.items():
        n = len(results)
        b3_wins = sum(1 for r in results if r.b3_outcome == "escaped_treasure")
        b5_wins = sum(1 for r in results if r.b5_outcome == "escaped_treasure")
        b4_wins = sum(1 for r in results if r.b4_outcome == "escaped_treasure")

        b3_scores = [r.b3_score for r in results]
        b5_scores = [r.b5_score for r in results]
        b4_pars = [r.b4_par for r in results]

        b3_win_vec = [r.b3_outcome == "escaped_treasure" for r in results]
        b5_win_vec = [r.b5_outcome == "escaped_treasure" for r in results]
        b4_win_vec = [r.b4_outcome == "escaped_treasure" for r in results]

        mcnemar_b3_b5 = mcnemar(b3_win_vec, b5_win_vec)
        mcnemar_b3_b4 = mcnemar(b3_win_vec, b4_win_vec)

        # Failure breakdown
        failures = [r.failure for r in results if r.failure is not None]
        avoidable = [f for f in failures if f.classification == "avoidable"]
        suboptimal = [f for f in failures if f.classification == "suboptimal_gamble"]
        forced = [f for f in failures if f.classification == "forced"]

        # Stars
        b3_stars = {s: sum(1 for r in results if r.b3_stars == s) for s in (0, 1, 2, 3)}
        b5_stars = {s: sum(1 for r in results if r.b5_stars == s) for s in (0, 1, 2, 3)}

        # Calibration
        all_cal: list[tuple[float, float, int]] = []
        for r in results:
            all_cal.extend(r.calibration_pairs)

        mae = (
            sum(abs(pred - exact) for pred, exact, _ in all_cal) / len(all_cal) if all_cal else 0.0
        )

        # Binned calibration
        bins = []
        for b_idx in range(10):
            lo = b_idx * 0.1
            hi = (b_idx + 1) * 0.1
            bin_items = [
                (p, e, h) for p, e, h in all_cal if (lo <= p < hi if b_idx < 9 else lo <= p <= hi)
            ]
            count = len(bin_items)
            mean_pred = sum(p for p, _, _ in bin_items) / count if count else lo + 0.05
            mean_exact = sum(e for _, e, _ in bin_items) / count if count else lo + 0.05
            haz_rate = sum(h for _, _, h in bin_items) / count if count else 0.0
            bins.append(
                {
                    "bin": f"{lo:.1f}-{hi:.1f}",
                    "count": count,
                    "mean_pred": round(mean_pred, 4),
                    "mean_exact": round(mean_exact, 4),
                    "hazard_rate": round(haz_rate, 4),
                }
            )

        summary["modes"][mode] = {
            "n": n,
            "b3": {
                "wins": b3_wins,
                "win_rate": round(b3_wins / n, 4),
                "win_rate_ci95": [round(x, 4) for x in wilson_ci(b3_wins, n)],
                "mean_score": round(sum(b3_scores) / n, 2),
                "stars": b3_stars,
            },
            "b5": {
                "wins": b5_wins,
                "win_rate": round(b5_wins / n, 4),
                "win_rate_ci95": [round(x, 4) for x in wilson_ci(b5_wins, n)],
                "mean_score": round(sum(b5_scores) / n, 2),
                "stars": b5_stars,
            },
            "b4": {
                "wins": b4_wins,
                "win_rate": round(b4_wins / n, 4),
                "mean_par": round(sum(b4_pars) / n, 2),
            },
            "paired_b3_vs_b5": mcnemar_b3_b5,
            "paired_b3_vs_b4": mcnemar_b3_b4,
            "failures": {
                "total": len(failures),
                "avoidable": len(avoidable),
                "suboptimal_gamble": len(suboptimal),
                "forced": len(forced),
                "avoidable_details": [asdict(f) for f in avoidable],
                "suboptimal_details": [asdict(f) for f in suboptimal],
            },
            "calibration": {
                "total_pairs": len(all_cal),
                "mae": round(mae, 4),
                "bins": bins,
            },
        }

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="PR2 Optimality Audit runner.")
    parser.add_argument("--count", type=int, default=1000, help="Seeds per mode")
    parser.add_argument("--seed-start", type=int, default=10000, help="Starting seed index")
    parser.add_argument("--workers", type=int, default=None, help="Worker processes")
    parser.add_argument("--out", default="docs/audit_results.json", help="Path for JSON output")
    args = parser.parse_args()

    results = run_audit(
        count_per_mode=args.count,
        seed_start=args.seed_start,
        workers=args.workers,
    )

    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Audit results written to {args.out}")


if __name__ == "__main__":
    main()
