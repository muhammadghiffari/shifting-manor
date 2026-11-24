# /// script
# dependencies = [
#   "pygame-ce",
# ]
# ///
"""WebAssembly (pygbag) browser entry point for Shifting Manor.

Supports optional URL query parameters so anyone can share direct links, e.g.:
  ?mode=explorer&seed=HAUNT-4F2A
  ?auto=1&agent=b3&mode=haunted&seed=HAUNT-4F2A
  ?duel=1&mode=explorer&seed=HAUNT-7C1D
  ?tutorial=1
  ?simlab=1
"""

from __future__ import annotations

import asyncio
import sys
from urllib.parse import parse_qs

from shifting_manor.ui.app import App


def _read_query_params() -> dict[str, str]:
    if sys.platform != "emscripten":
        return {}
    try:
        import platform

        search = str(platform.window.location.search or "")
        parsed = parse_qs(search.lstrip("?"))
        return {k.lower(): v[0] for k, v in parsed.items() if v}
    except (ImportError, AttributeError, ValueError, RuntimeError):
        return {}


async def main() -> None:
    params = _read_query_params()
    seed = params.get("seed", "HAUNT-4F2A").upper()[:18] or "HAUNT-4F2A"
    mode = params.get("mode", "")
    if mode not in ("apprentice", "explorer", "haunted"):
        mode = ""
    agent = params.get("agent", "b3").lower()

    app = App(audio=True, windowed=True, seed=seed)
    if agent in app.agent_names:
        app.agent_index = app.agent_names.index(agent)

    if params.get("tutorial") in ("1", "true", "yes"):
        app.start_tutorial()
    elif params.get("simlab") in ("1", "true", "yes"):
        app.start_simlab()
    elif params.get("duel") in ("1", "true", "yes"):
        app.start_duel(mode or "explorer", seed)
    elif params.get("auto") in ("1", "true", "yes"):
        app.start_live_ai(mode or "explorer", seed, agent if agent in app.agent_names else "b3")
    elif params.get("watch") in ("1", "true", "yes"):
        app.start_watch(mode or "explorer", seed, agent)
    elif mode:
        app.start_game(mode, seed)

    await app.run_async()


asyncio.run(main())
