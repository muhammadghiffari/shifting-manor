"""Evaluation statistics: Wilson intervals, paired McNemar and gamble calibration."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from typing import Any


def wilson_ci(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion."""
    if trials <= 0:
        return (0.0, 0.0)
    p = successes / trials
    denom = 1.0 + z * z / trials
    centre = (p + z * z / (2.0 * trials)) / denom
    margin = z * math.sqrt(p * (1.0 - p) / trials + z * z / (4.0 * trials * trials)) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def mcnemar(a: Sequence[bool], b: Sequence[bool]) -> dict[str, float | int]:
    """Paired comparison of two agents on the same seeds (two-sided McNemar)."""
    if len(a) != len(b):
        raise ValueError("paired samples must have equal length")
    a_only = sum(1 for x, y in zip(a, b) if x and not y)
    b_only = sum(1 for x, y in zip(a, b) if y and not x)
    discordant = a_only + b_only
    if discordant == 0:
        return {"a_only": a_only, "b_only": b_only, "statistic": 0.0, "p": 1.0}
    statistic = (abs(a_only - b_only) - 1.0) ** 2 / discordant
    p = math.erfc(math.sqrt(statistic / 2.0))
    return {"a_only": a_only, "b_only": b_only, "statistic": statistic, "p": p}


def calibration(records: Iterable[Any], width: int = 10) -> list[dict[str, Any]]:
    """Risk bins vs observed deaths for every gamble action.

    ``records`` may be GameRecord objects or dicts containing a ``gambles`` list.
    A gamble action's predicted risk is the enumeration risk of the room it
    entered; the outcome is whether that action killed the agent.
    """
    bins = [
        {"lo": lo, "hi": min(lo + width, 100), "n": 0, "deaths": 0} for lo in range(0, 100, width)
    ]
    for record in records:
        gambles = record.get("gambles", []) if isinstance(record, dict) else record.gambles
        for gamble in gambles:
            risk = float(gamble["step_risk"])
            idx = min(int(risk * 100) // width, len(bins) - 1)
            bins[idx]["n"] += 1
            bins[idx]["deaths"] += int(bool(gamble.get("died")))
    for item in bins:
        item["rate"] = item["deaths"] / item["n"] if item["n"] else None
    return bins


def calibration_error(bins: Iterable[dict[str, Any]]) -> float:
    """Largest absolute gap between predicted bin midpoint and observed rate."""
    worst = 0.0
    for item in bins:
        if not item["n"]:
            continue
        predicted = (item["lo"] + item["hi"]) / 200.0
        worst = max(worst, abs(predicted - item["rate"]))
    return worst
