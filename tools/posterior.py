"""Exact ground-truth posterior distribution over initial worlds.

This tool is offline evaluation instrumentation, NOT part of any agent.
It calculates the exact Bayesian posterior hazard probability for every cell
given the full percept history and replayed shift schedule.
"""

from __future__ import annotations

import argparse
import itertools
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from shifting_manor.engine.grid import cells, neighbours
from shifting_manor.engine.modes import MODES
from shifting_manor.engine.types import Cell, Event, GameInfo, Percepts

# Cached initial combinations per (size, pit_total)
_COMBOS_CACHE: dict[tuple[int, int], tuple[list[Cell], dict[Cell, int], list[int]]] = {}


def _get_initial_combos(size: int, pit_total: int) -> tuple[list[Cell], dict[Cell, int], list[int]]:
    key = (size, pit_total)
    if key not in _COMBOS_CACHE:
        # Protected entrance + adjacent neighbours:
        protected = {(0, 0), (1, 0), (0, 1)}
        cands = [c for c in cells(size) if c not in protected]
        cand_to_bit = {c: 1 << i for i, c in enumerate(cands)}
        masks = [
            sum(cand_to_bit[c] for c in combo) for combo in itertools.combinations(cands, pit_total)
        ]
        _COMBOS_CACHE[key] = (cands, cand_to_bit, masks)
    return _COMBOS_CACHE[key]


@dataclass(frozen=True)
class HazardProbabilities:
    """Exact marginal hazard probabilities at the current state."""

    pit_risk: dict[Cell, float]
    ghost_risk: dict[Cell, float]
    hazard_risk: dict[Cell, float]
    consistent_worlds: int

    def risk(self, cell: Cell) -> float:
        return self.hazard_risk.get(cell, 0.0)

    def is_safe(self, cell: Cell, tol: float = 1e-9) -> bool:
        return self.hazard_risk.get(cell, 0.0) <= tol


class ExactPosterior:
    """Exact Bayesian posterior over hazard locations given full percept history."""

    def __init__(
        self,
        mode: str,
        size: int,
        pit_total: int,
        shift_every: int | None = None,
    ) -> None:
        self.mode = mode
        self.size = size
        self.pit_total = pit_total
        self.shift_every = shift_every
        self.entrance = (0, 0)
        self.protected = {(0, 0), (1, 0), (0, 1)}

        cands, c2b, masks = _get_initial_combos(size, pit_total)
        self.candidates = cands
        self.cand_to_bit = c2b
        self.pit_masks = list(masks)

        # In all modes, generator places at most 1 ghost
        self.ghost_candidates = set(self.candidates)
        self.ghost_alive = True
        self._weights: list[int] | None = None
        self._Z: int | None = None

        # Permutations: initial_cell <-> current_cell
        all_c = list(cells(size))
        self.mapping: dict[Cell, Cell] = {c: c for c in all_c}
        self.inv_mapping: dict[Cell, Cell] = {c: c for c in all_c}

        self.visited_cells: set[Cell] = set()
        self.turn = 0

    @classmethod
    def from_info(cls, info: GameInfo) -> ExactPosterior:
        return cls(
            mode=info.mode,
            size=info.size,
            pit_total=info.pit_total,
            shift_every=info.shift_every,
        )

    def apply_shift(self, shift_mapping: dict[Cell, Cell]) -> None:
        """Update coordinate permutation when a wing rotates."""
        self.mapping = {c0: shift_mapping.get(c, c) for c0, c in self.mapping.items()}
        self.inv_mapping = {v: k for k, v in self.mapping.items()}

    def observe(
        self,
        pos: Cell,
        percepts: Percepts,
        events: Iterable[Event] | None = None,
    ) -> None:
        """Condition the posterior on a new turn's observations and shift events."""
        events = list(events or [])
        self._weights = None
        self._Z = None

        # 1. Process shift events and ghost banishment from this turn:
        for ev in events:
            if hasattr(ev, "mapping"):
                self.apply_shift(ev.mapping)
            if type(ev).__name__ == "GhostBanished":
                self.ghost_alive = False

        if percepts.scream:
            self.ghost_alive = False

        # 2. Agent visited pos and survived: pos cannot have a pit or living ghost
        self.visited_cells.add(pos)
        pos0 = self.inv_mapping[pos]
        if pos0 in self.cand_to_bit:
            m_pos = self.cand_to_bit[pos0]
            self.pit_masks = [m for m in self.pit_masks if not (m & m_pos)]
            self.ghost_candidates.discard(pos0)

        # 3. Candidate neighbors in initial coordinates:
        curr_nbrs = neighbours(pos, self.size)
        nbrs0 = [self.inv_mapping[n] for n in curr_nbrs if self.inv_mapping[n] in self.cand_to_bit]
        m_nbrs = sum(self.cand_to_bit[c0] for c0 in nbrs0)

        # 4. Breeze observation:
        if percepts.breeze:
            self.pit_masks = [m for m in self.pit_masks if m & m_nbrs]
        else:
            self.pit_masks = [m for m in self.pit_masks if not (m & m_nbrs)]

        # 5. Chill observation:
        if self.ghost_alive:
            if percepts.chill:
                self.ghost_candidates.intersection_update(nbrs0)
            else:
                self.ghost_candidates.difference_update(nbrs0)

        self.turn += 1

    def _ensure_weights(self) -> tuple[list[int] | None, int]:
        if self._Z is not None:
            return self._weights, self._Z

        valid_ghost = self.ghost_candidates if self.ghost_alive else set()
        if not valid_ghost:
            self._weights = None
            self._Z = len(self.pit_masks)
        else:
            g_bits = [self.cand_to_bit[g] for g in valid_ghost if g in self.cand_to_bit]
            G_mask = sum(g_bits)
            len_G = len(g_bits)
            self._weights = [len_G - (m & G_mask).bit_count() for m in self.pit_masks]
            self._Z = sum(self._weights)
        return self._weights, self._Z

    def cell_hazard_risk(self, cell: Cell) -> float:
        """Compute exact hazard risk for a single cell on demand (fast).

        Visited rooms are NOT free: a shift rotates hazards into old rooms,
        so every non-protected cell carries its true mask marginal.
        """
        if cell == self.entrance or cell in self.protected:
            return 0.0

        c0 = self.inv_mapping.get(cell, cell)
        if c0 not in self.cand_to_bit:
            return 0.0

        bit = self.cand_to_bit[c0]
        total_p = len(self.pit_masks)
        if total_p == 0:
            return 0.0

        weights, Z = self._ensure_weights()
        if Z == 0:
            return 0.0

        if weights is None:
            pit_hits = sum(1 for m in self.pit_masks if m & bit)
            return pit_hits / total_p

        pit_weight = sum(w for m, w in zip(self.pit_masks, weights) if m & bit)
        pit_p = pit_weight / Z

        valid_ghost = self.ghost_candidates if self.ghost_alive else set()
        if c0 in valid_ghost:
            ghost_weight = sum(1 for m in self.pit_masks if not (m & bit))
            ghost_p = ghost_weight / Z
        else:
            ghost_p = 0.0

        return min(1.0, pit_p + ghost_p)

    def compute(self) -> HazardProbabilities:
        """Compute exact marginal probabilities for all cells at the current state."""
        all_cells = list(cells(self.size))
        total_p = len(self.pit_masks)
        valid_ghost = self.ghost_candidates if self.ghost_alive else set()
        weights, Z = self._ensure_weights()

        if weights is None or not valid_ghost:
            pit_risk = {c: 0.0 for c in all_cells}
            for c0, bit in self.cand_to_bit.items():
                if total_p > 0:
                    pit_hits = sum(1 for m in self.pit_masks if m & bit)
                    pit_risk[self.mapping[c0]] = pit_hits / total_p
            ghost_risk = {c: 0.0 for c in all_cells}
        else:
            pit_risk = {c: 0.0 for c in all_cells}
            for c0, bit in self.cand_to_bit.items():
                if Z > 0:
                    pit_weight = sum(w for m, w in zip(self.pit_masks, weights) if m & bit)
                    pit_risk[self.mapping[c0]] = pit_weight / Z

            ghost_risk = {c: 0.0 for c in all_cells}
            for g0 in valid_ghost:
                gb = self.cand_to_bit[g0]
                if Z > 0:
                    ghost_weight = sum(1 for m in self.pit_masks if not (m & gb))
                    ghost_risk[self.mapping[g0]] = ghost_weight / Z

        hazard_risk = {}
        for c in all_cells:
            if c == self.entrance or c in self.protected:
                p, g = 0.0, 0.0
            else:
                p = pit_risk.get(c, 0.0)
                g = ghost_risk.get(c, 0.0)
            hazard_risk[c] = min(1.0, p + g)

        return HazardProbabilities(
            pit_risk=pit_risk,
            ghost_risk=ghost_risk,
            hazard_risk=hazard_risk,
            consistent_worlds=Z,
        )


def compute_posterior_for_game(
    game: Any,
    history: list[tuple[Cell, Percepts, list[Event]]],
) -> HazardProbabilities:
    """Helper to evaluate the exact posterior at the end of a given percept history."""
    post = ExactPosterior.from_info(game.info())
    for pos, percepts, events in history:
        post.observe(pos, percepts, events)
    return post.compute()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Exact Bayesian posterior ground truth tool.")
    parser.add_argument("--mode", choices=list(MODES), default="explorer")
    parser.add_argument("--seed", default="HAUNT-4F2A")
    parser.add_argument("--steps", type=int, default=15, help="Number of agent moves to replay")
    parser.add_argument("--agent", default="b3", help="Agent to drive the replay")
    args = parser.parse_args(argv)

    from shifting_manor.agents import make_agent
    from shifting_manor.engine.game import Game

    game = Game(args.mode, args.seed)
    agent = make_agent(args.agent, game.info())
    post = ExactPosterior.from_info(game.info())

    percepts = game.observe()
    events: list[Event] = []
    step_num = 0

    print(f"Replaying {args.mode.upper()} seed={args.seed} agent={args.agent} ...")
    while not game.state.done and step_num < args.steps:
        post.observe(game.state.agent, percepts, events)
        res = post.compute()
        pos = game.state.agent
        print(
            f"Step {step_num:02d} pos={pos} consistent_worlds={res.consistent_worlds} "
            f"safe_rooms={sum(1 for c, r in res.hazard_risk.items() if r == 0.0)}"
        )
        action = agent.act(percepts, events)
        step_res = game.step(action)
        percepts = step_res.percepts
        events = step_res.events
        step_num += 1

    final_res = post.compute()
    print("\nFinal Hazard Probabilities:")
    size = game.state.size
    for y in range(size - 1, -1, -1):
        row_str = " ".join(f"{100 * final_res.risk((x, y)):4.0f}%" for x in range(size))
        print(f"y={y}: {row_str}")


if __name__ == "__main__":
    main()
