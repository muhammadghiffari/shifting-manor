"""B5 agent: KB agent driven by the exact Bayesian posterior (PR2)."""

from __future__ import annotations

from collections.abc import Iterable

from shifting_manor.agents.kb_agent import Explanation, KBAgent
from shifting_manor.engine.types import Action, Cell, Event, GameInfo, Percepts
from tools.posterior import ExactPosterior


class LazyExactModel:
    """Exact posterior model computing cell risks lazily on demand."""

    def __init__(self, posterior: ExactPosterior) -> None:
        self.posterior = posterior
        self._cache: dict[Cell, float] = {}
        self.warnings: tuple[str, ...] = ()
        self.fallback = False

    @property
    def worlds(self) -> int:
        _, z = self.posterior._ensure_weights()
        return z

    def risk(self, cell: Cell) -> float:
        if cell not in self._cache:
            self._cache[cell] = self.posterior.cell_hazard_risk(cell)
        return self._cache[cell]


class B5Agent(KBAgent):
    """B5 uses the exact Bayesian posterior distribution over initial worlds.

    Its decision policy, rules, and forward chaining are identical to B3,
    but all risk evaluations (for routing, budgeting, and gamble selection)
    use exact posterior probabilities rather than the 14-cell frontier approximation.
    """

    def __init__(self) -> None:
        super().__init__(variant="b3")
        self.posterior: ExactPosterior | None = None

    def reset(self, info: GameInfo) -> None:
        super().reset(info)
        self.posterior = ExactPosterior.from_info(info)

    def act(self, percepts: Percepts, events: Iterable[Event]) -> Action:
        if self.info is None or self.kb is None or self.posterior is None:
            raise RuntimeError("reset() before act()")
        events = list(events)
        self.gamble_candidates = []
        self.last_gamble = None
        self.last = Explanation()

        # Update KB
        self.kb.on_events(events)
        self._absorb(events)
        self._sync_globals()
        self.kb.observe(percepts)
        self._sync_globals()

        # Update exact posterior and build exact Model
        self.posterior.observe(self.pos, percepts, events)
        self.model = LazyExactModel(self.posterior)  # type: ignore[assignment]

        action = self._decide()
        self.last_action = action
        self.last_firings = list(self.kb.firings)
        self.last = Explanation(
            thought=self.last.thought or self._thought(action),
            firings=self.last_firings,
            beliefs=self.kb.belief_labels(),
        )
        return action
