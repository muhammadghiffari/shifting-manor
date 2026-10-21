"""Agents: B0 random, B1 reactive, B2/B2b/B3 KB, B4 oracle (M3)."""

from __future__ import annotations

from shifting_manor.agents.base import Agent
from shifting_manor.agents.baselines import RandomAgent, ReactiveAgent
from shifting_manor.agents.kb_agent import KBAgent
from shifting_manor.engine.types import GameInfo

ALIASES = {
    "b0": "b0",
    "random": "b0",
    "b1": "b1",
    "reactive": "b1",
    "b2": "b2",
    "b2b": "b2b",
    "b3": "b3",
    "kb": "b3",
    "caretaker": "b3",
    "b4": "b4",
    "oracle": "b4",
}


def make_agent(name: str, info: GameInfo) -> Agent:
    key = ALIASES.get(name.lower())
    if key is None:
        raise ValueError(f"unknown agent {name!r}; choose from {sorted(ALIASES)}")
    if key == "b0":
        agent: Agent = RandomAgent()
    elif key == "b1":
        agent = ReactiveAgent()
    elif key in ("b2", "b2b", "b3"):
        agent = KBAgent(key)
    else:
        from shifting_manor.agents.oracle import OracleAgent

        agent = OracleAgent()
    agent.reset(info)
    return agent
