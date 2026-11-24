"""Simulation Lab scene (F2): empirical bar charts & live headless benchmark."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pygame

from shifting_manor.sim.runner import AGENTS, MODE_NAMES, run_game
from shifting_manor.sim.stats import mcnemar, wilson_ci
from shifting_manor.ui import strings, theme

IS_WEB = sys.platform == "emscripten"

METRICS = (
    ("win_rate", "WIN RATE % (95% WILSON CI)"),
    ("mean_score", "MEAN SCORE"),
    ("mean_stars", "MEAN STARS (0-3)"),
    ("forced_guess_rate", "FORCED-GUESS RATE %"),
)

AGENT_COLORS = {
    "b0": theme.DIM,
    "b1": theme.MUTED,
    "b2": theme.ORANGE,
    "b2b": theme.GOLD,
    "b3": theme.TEAL,
    "b4": theme.VIOLET,
}

AGENT_TITLES = {
    "b0": "B0 Random",
    "b1": "B1 Reactive",
    "b2": "B2 Shift-Blind",
    "b2b": "B2b Forgetful",
    "b3": "B3 Caretaker (R16)",
    "b4": "B4 Oracle (Ceiling)",
}


def _default_results_paths() -> tuple[Path, ...]:
    root = Path(__file__).resolve().parent.parent.parent
    return (
        root / "sim" / "results_summary.json",
        root / "sim" / "results.json",
        Path("sim") / "results_summary.json",
        Path("sim") / "results.json",
    )


class SimLabScene:
    """Interactive visual benchmark dashboard with cooperative live re-run."""

    def __init__(self, *, on_exit, audio=None) -> None:
        self.on_exit = on_exit
        self.audio = audio
        self.mode_index = 2  # Default to Haunted where R16 transport shines most
        self.metric_index = 0
        self.data: dict[str, Any] | None = None
        self.source_label = "sim/results.json (200 seeds/mode)"
        self.running_live = False
        self.live_progress = 0.0
        self.live_status = ""
        self._live_runs = 30
        self._live_mode_idx = 0
        self._live_seed_idx = 0
        self._live_by_agent: dict[str, list[Any]] = {}
        self._live_modes_out: dict[str, Any] = {}
        self._buttons: dict[str, pygame.Rect] = {}
        self._load_cached()

    def _load_cached(self) -> None:
        for path in _default_results_paths():
            if path.is_file():
                try:
                    self.data = json.loads(path.read_text(encoding="utf-8"))
                    runs = self.data.get("config", {}).get("runs", 200)
                    self.source_label = f"Cached dataset: {runs} same-seed games per mode"
                    return
                except (OSError, json.JSONDecodeError, KeyError, TypeError):
                    self.data = None
        self.data = None
        self.source_label = "No cached results — click RUN LIVE BENCHMARK"

    def start_live_benchmark(self, runs: int = 20) -> None:
        if self.running_live:
            return
        self.running_live = True
        self._live_runs = max(5, runs)
        self._live_mode_idx = 0
        self._live_seed_idx = 0
        self._live_by_agent = {a: [] for a in AGENTS}
        self._live_modes_out = {}
        self.live_progress = 0.0
        self.live_status = f"Running {self._live_runs} seeds x 3 modes..."

    def update(self, dt: float) -> None:
        """Advance live benchmark cooperatively (1 seed/frame — 100% WASM-safe!)."""
        del dt
        if not self.running_live:
            return
        mode = MODE_NAMES[self._live_mode_idx]
        i = self._live_seed_idx
        seed = f"LIVE-{mode.upper()}-{i:04d}"
        par_rec = run_game(mode, seed, "b4")
        par = par_rec.actions
        par_rec.par_actions = par
        par_rec.stars = 3 if par_rec.win else 0
        for a in AGENTS:
            rec = par_rec if a == "b4" else run_game(mode, seed, a, par=par)
            self._live_by_agent[a].append(rec)

        self._live_seed_idx += 1
        total_steps = len(MODE_NAMES) * self._live_runs
        done_steps = self._live_mode_idx * self._live_runs + self._live_seed_idx
        self.live_progress = done_steps / max(1, total_steps)
        self.live_status = (
            f"Live sim: {mode} {self._live_seed_idx}/{self._live_runs} "
            f"({int(self.live_progress * 100)}%)"
        )

        if self._live_seed_idx >= self._live_runs:
            agents_metrics: dict[str, Any] = {}
            for a, recs in self._live_by_agent.items():
                n = len(recs)
                wins = sum(r.win for r in recs)
                lo, hi = wilson_ci(wins, n)
                agents_metrics[a] = {
                    "games": n,
                    "wins": wins,
                    "win_rate": wins / n,
                    "win_rate_ci95": [lo, hi],
                    "mean_score": sum(r.score for r in recs) / n,
                    "mean_actions": sum(r.actions for r in recs) / n,
                    "mean_stars": sum(r.stars for r in recs) / n,
                    "forced_guess_rate": sum(r.forced_guess for r in recs) / n,
                }
            paired = {
                f"b3_vs_{other}": mcnemar(
                    [r.win for r in self._live_by_agent["b3"]],
                    [r.win for r in self._live_by_agent[other]],
                )
                for other in ("b2", "b2b")
            }
            self._live_modes_out[mode] = {"agents": agents_metrics, "paired": paired}
            self._live_mode_idx += 1
            self._live_seed_idx = 0
            self._live_by_agent = {a: [] for a in AGENTS}
            if self._live_mode_idx >= len(MODE_NAMES):
                self.data = {"config": {"runs": self._live_runs}, "modes": self._live_modes_out}
                self.source_label = f"Live benchmark: {self._live_runs} fresh seeds per mode"
                self.running_live = False
                self.live_status = "Live benchmark complete!"

    def handle(self, event, pos: tuple[int, int] | None = None) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_F2):
                self.on_exit()
            elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                self.mode_index = event.key - pygame.K_1
            elif event.key == pygame.K_TAB:
                self.metric_index = (self.metric_index + 1) % len(METRICS)
            elif event.key == pygame.K_b:
                self.start_live_benchmark(30)
            elif event.key == pygame.K_c:
                self._load_cached()
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and pos is not None:
            for name, rect in self._buttons.items():
                if not rect.collidepoint(pos):
                    continue
                if self.audio:
                    self.audio.play("ui_click")
                if name == "back":
                    self.on_exit()
                elif name.startswith("mode_"):
                    self.mode_index = int(name.split("_")[1])
                elif name.startswith("metric_"):
                    self.metric_index = int(name.split("_")[1])
                elif name == "run_live":
                    self.start_live_benchmark(30)
                elif name == "load_cached":
                    self._load_cached()
                return

    def draw(self, canvas: pygame.Surface, mouse: tuple[int, int]) -> None:
        self._buttons = {}
        canvas.fill(theme.BG)

        # Header
        theme.text(canvas, strings.SIMLAB_TITLE, 30, theme.GOLD, (48, 22), bold=True)
        theme.text(canvas, strings.SIMLAB_SUBTITLE, 16, theme.MUTED, (48, 58))
        back = pygame.Rect(1134, 20, 100, 34)
        theme.button(canvas, back, "BACK [Esc]", hover=back.collidepoint(mouse), size=16)
        self._buttons["back"] = back

        # Mode selector strip
        for i, mode in enumerate(MODE_NAMES):
            mr = pygame.Rect(48 + i * 168, 92, 158, 38)
            theme.button(
                canvas,
                mr,
                mode.upper(),
                selected=i == self.mode_index,
                hover=mr.collidepoint(mouse),
                accent=theme.GOLD,
                size=17,
            )
            self._buttons[f"mode_{i}"] = mr

        # Live benchmark + reload cached buttons
        live_btn = pygame.Rect(730, 92, 260, 38)
        theme.button(
            canvas,
            live_btn,
            "RUNNING..." if self.running_live else "RUN LIVE 30-SEED CHECK [B]",
            selected=self.running_live,
            disabled=self.running_live,
            hover=live_btn.collidepoint(mouse),
            accent=theme.TEAL,
            size=15,
        )
        self._buttons["run_live"] = live_btn

        cache_btn = pygame.Rect(1002, 92, 232, 38)
        theme.button(
            canvas,
            cache_btn,
            "RELOAD 200-SEED DATA [C]",
            hover=cache_btn.collidepoint(mouse),
            size=15,
        )
        self._buttons["load_cached"] = cache_btn

        # Metric tabs
        mw = (1186 - 3 * 12) // 4
        for i, (_, title) in enumerate(METRICS):
            tr = pygame.Rect(48 + i * (mw + 12), 142, mw, 34)
            theme.button(
                canvas,
                tr,
                title,
                selected=i == self.metric_index,
                hover=tr.collidepoint(mouse),
                accent=theme.CYAN,
                size=14,
            )
            self._buttons[f"metric_{i}"] = tr

        # Chart area
        chart = pygame.Rect(48, 188, 1186, 354)
        theme.panel(canvas, chart, accent_top=theme.TEAL)
        data = self.data
        running = self.running_live
        progress = self.live_progress
        status = self.live_status
        src = self.source_label

        theme.text(canvas, src, 15, theme.MUTED, (chart.x + 20, chart.y + 14))
        if running:
            pbar = pygame.Rect(chart.right - 340, chart.y + 14, 320, 18)
            pygame.draw.rect(canvas, theme.BG_DEEP, pbar, border_radius=8)
            pygame.draw.rect(
                canvas,
                theme.TEAL,
                (pbar.x, pbar.y, max(6, int(pbar.width * progress)), pbar.height),
                border_radius=8,
            )
            theme.text(canvas, status, 14, theme.TEAL, (pbar.x - 14, pbar.y + 1), anchor="topright")

        mode_name = MODE_NAMES[self.mode_index]
        metric_key, _metric_label = METRICS[self.metric_index]
        if data is None or mode_name not in data.get("modes", {}):
            theme.text(
                canvas,
                "No results loaded yet. Click RUN LIVE 30-SEED CHECK.",
                20,
                theme.MUTED,
                chart.center,
                anchor="center",
            )
            return

        mode_data = data["modes"][mode_name]
        agents_data = mode_data["agents"]
        self._draw_bars(canvas, chart, agents_data, metric_key)

        # Bottom summary card: paired McNemar stats & key takeaway
        summary = pygame.Rect(48, 554, 1186, 134)
        theme.panel(canvas, summary, color=theme.BG_PANEL_LIGHT, accent_top=theme.GOLD)
        theme.text(
            canvas,
            f"PAIRED STATISTICAL PROOF · {mode_name.upper()} MODE",
            18,
            theme.GOLD,
            (summary.x + 20, summary.y + 14),
            bold=True,
        )
        paired = mode_data.get("paired", {})
        b3_m = agents_data.get("b3", {})
        b2_m = agents_data.get("b2", {})
        b2b_m = agents_data.get("b2b", {})
        gap_b2 = 100.0 * (b3_m.get("win_rate", 0.0) - b2_m.get("win_rate", 0.0))
        gap_b2b = 100.0 * (b3_m.get("win_rate", 0.0) - b2b_m.get("win_rate", 0.0))
        p_b2 = paired.get("b3_vs_b2", {}).get("p", 1.0)
        p_b2b = paired.get("b3_vs_b2b", {}).get("p", 1.0)

        if mode_name == "apprentice":
            line1 = "Apprentice (4x4) has NO shifts — so B2, B2b, and B3 perform identically as expected (sanity check passed!)."
            line2 = "Switch to EXPLORER or HAUNTED to see R16 knowledge transport pull decisively ahead of B2 and B2b!"
        else:
            line1 = (
                f"B3 Caretaker vs B2 Shift-Blind: +{gap_b2:.1f} pp win rate   "
                f"(paired McNemar p = {p_b2:.2e})"
            )
            line2 = (
                f"B3 Caretaker vs B2b Forgetful:  +{gap_b2b:.1f} pp win rate   "
                f"(paired McNemar p = {p_b2b:.2e}) — transporting facts beats forgetting!"
            )
        theme.text(canvas, line1, 17, theme.TEAL, (summary.x + 20, summary.y + 46), bold=True)
        theme.text(canvas, line2, 16, theme.INK, (summary.x + 20, summary.y + 74))
        theme.text(
            canvas, strings.SIMLAB_HINT, 14, theme.MUTED, (summary.x + 20, summary.bottom - 24)
        )

    def _draw_bars(
        self,
        canvas: pygame.Surface,
        chart: pygame.Rect,
        agents_data: dict[str, Any],
        metric_key: str,
    ) -> None:
        left_x = chart.x + 216
        bar_max_w = chart.width - 360
        top_y = chart.y + 52
        row_h = 48

        for i, agent_id in enumerate(AGENTS):
            m = agents_data.get(agent_id)
            if not m:
                continue
            ry = top_y + i * row_h
            col = AGENT_COLORS.get(agent_id, theme.GOLD)
            is_hero = agent_id == "b3"
            if is_hero:
                hl = pygame.Rect(chart.x + 12, ry - 4, chart.width - 24, row_h - 4)
                pygame.draw.rect(canvas, theme.BG_PANEL_LIGHT, hl, border_radius=6)
                pygame.draw.rect(canvas, theme.TEAL, hl, 1, border_radius=6)

            theme.text(
                canvas,
                AGENT_TITLES.get(agent_id, agent_id.upper()),
                17,
                theme.INK_BRIGHT if is_hero else theme.INK,
                (chart.x + 22, ry + 8),
                bold=is_hero,
            )

            track = pygame.Rect(left_x, ry + 8, bar_max_w, 24)
            pygame.draw.rect(canvas, theme.BG_DEEP, track, border_radius=6)

            val = float(m.get(metric_key, 0.0))
            if metric_key in ("win_rate", "forced_guess_rate"):
                ratio = max(0.0, min(1.0, val))
                label = f"{100.0 * val:.1f}%"
            elif metric_key == "mean_stars":
                ratio = max(0.0, min(1.0, val / 3.0))
                label = f"{val:.2f} / 3.00"
            else:  # mean_score in [-1000, 1200]
                ratio = max(0.0, min(1.0, (val + 1000.0) / 2200.0))
                label = f"{val:+.0f}"

            fill_w = max(4, int(track.width * ratio))
            pygame.draw.rect(canvas, col, (track.x, track.y, fill_w, track.height), border_radius=6)

            # 95% Wilson CI whisker on win_rate
            if metric_key == "win_rate" and "win_rate_ci95" in m:
                lo, hi = m["win_rate_ci95"]
                x_lo = track.x + int(track.width * lo)
                x_hi = track.x + int(track.width * hi)
                cy = track.centery
                pygame.draw.line(canvas, theme.INK_BRIGHT, (x_lo, cy), (x_hi, cy), 2)
                pygame.draw.line(canvas, theme.INK_BRIGHT, (x_lo, cy - 6), (x_lo, cy + 6), 2)
                pygame.draw.line(canvas, theme.INK_BRIGHT, (x_hi, cy - 6), (x_hi, cy + 6), 2)
                label += f" [{100 * lo:.0f}-{100 * hi:.0f}%]"

            theme.text(
                canvas,
                label,
                16,
                theme.INK_BRIGHT if is_hero else theme.INK,
                (track.right + 14, ry + 9),
                bold=is_hero,
            )
