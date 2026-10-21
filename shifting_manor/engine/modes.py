"""Difficulty modes from PRD 6.2 and AGENT.md Section 3."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Mode:
    name: str
    size: int
    pits: int
    oil: int
    shift_every: int | None


MODES: dict[str, Mode] = {
    "apprentice": Mode("apprentice", 4, 2, 40, None),
    "explorer": Mode("explorer", 6, 4, 80, 8),
    "haunted": Mode("haunted", 6, 5, 70, 5),
}


def get_mode(mode: str | Mode) -> Mode:
    if isinstance(mode, Mode):
        return mode
    try:
        return MODES[mode.lower()]
    except KeyError as exc:
        raise ValueError(f"unknown mode {mode!r}; choose from {sorted(MODES)}") from exc
