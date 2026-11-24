# Shifting Manor

A haunted-manor deduction game in the spirit of Wumpus World, playable **manually by humans** AND **autonomously in real time by a rule-based, forward-chaining Caretaker AI**. Every few moves a 3×3 wing of the manor rotates 90°, carrying hidden pits and the ghost with it, so the player and the AI must *transport* what they know (`R16`). Built for the Artificial Intelligence course (Week 6, Knowledge): a 24-rule IF–THEN expert system with forward chaining, exact frontier model enumeration, risk-weighted A*, and interactive proof-tree explainability in Python.

**Play Online Free (No Install):** [https://muhammadghiffari.github.io/shifting-manor/](https://muhammadghiffari.github.io/shifting-manor/)

Direct shareable links:
- **Play Manual:** `https://muhammadghiffari.github.io/shifting-manor/`
- **Watch Real Caretaker AI Play Live:** `https://muhammadghiffari.github.io/shifting-manor/?auto=1&agent=b3&mode=explorer&seed=HAUNT-4F2A`
- **Duel vs Caretaker AI:** `https://muhammadghiffari.github.io/shifting-manor/?duel=1&mode=explorer&seed=HAUNT-4F2A`
- **Interactive 4-Lesson Tutorial:** `https://muhammadghiffari.github.io/shifting-manor/?tutorial=1`
- **Simulation Lab:** `https://muhammadghiffari.github.io/shifting-manor/?simlab=1`

**Authors:** Muhammad Ghiffari, Radithia Ary Winata · **License:** MIT (code); assets per `assets/CREDITS.md`

## Features (End-to-End Complete)

- **Manual Play (`PLAY MANUALLY`)** — Atmospheric flickering lantern fog-of-war, remembered room sense badges, right-click/hotkey room notes that rotate with shifting wings, Charm aiming (`C`), Leave Manor at Entrance (`E`), contextual live coaching hints, and fair zero-cheating **AI Hint (`I`)**.
- **Real Autonomous Live AI Play (`LIVE AI AGENT` / `--auto`)** — Watch ANY real agent (`B3 Caretaker`, `B5 Exact Bayesian`, `B2b Forgetful`, `B2 Shift-Blind`, `B1 Reactive`, `B0 Random`, `B4 Oracle`) play a **live `Game` turn-by-turn** on the full board with planned route previews, live belief/risk overlay (`B`), streaming forward-chaining Inference Log, 24-rule KB heat bars, clickable `Why?` proof trees (`W`), speed control (`0.5×–4×`), Pause/Step, and **instant mid-game Take Over / AI Auto-Play (`T`)**!
- **Human vs AI Duel (`DUEL vs AI` / `--duel`)** — Play a seed manually first, then watch Caretaker `B3` tackle the exact same seed autonomously, and compare paths, scores, stars (vs Oracle par), and actions side by side.
- **Interactive 4-Lesson Tutorial & Visual Field Guide (`TUTORIAL & GUIDE` / `H`)** — Hands-on playable mini-boards teaching movement & Breeze, Pit deduction & Escaping at `(0,0)`, Ghost banishment with Charm, and Surviving a Wing Shift — plus a 4-tab illustrated Field Guide accessible anytime via `H`.
- **Watch AI Trace Inspector (`TRACE INSPECTOR` / `V`)** — Replay a frozen trace step-by-step (forward & backward), filter `NEW ONLY` vs `ALL` firings, view KB rule heat bars, and expand complete `Why?` proof trees back to original percepts.
- **Simulation Lab (`SIM LAB` / `F2`)** — Interactive bar charts of 200-seed win rates with 95% Wilson CIs, paired McNemar significance proofs, mean scores, stars, forced-guess rates, and a live in-app 30-seed benchmark runner.
- **Procedural Gothic Audio, Particles & Accessibility (`SETTINGS` / `O`)** — Zero-dependency synthesized SFX & calm/tense ambient audio layers, percept particles, charm beams, screen shake, Run Card PNG export (`S`), Reduce Motion, High Contrast, Font Scale, and Presenter Overlay (`F1`).

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Launch the full interactive game (Title screen)
python -m shifting_manor

# Launch directly into Live Autonomous AI Play (real Caretaker B3 playing live)
python -m shifting_manor --auto --agent b3 --mode explorer --seed HAUNT-4F2A

# Launch Human vs AI Duel, Interactive Tutorial, or Simulation Lab
python -m shifting_manor --duel --mode explorer --seed HAUNT-4F2A
python -m shifting_manor --tutorial
python -m shifting_manor --simlab

# Watch AI looping demo (presentation fallback)
python -m shifting_manor --demo --seed HAUNT-4F2A

# Headless CLI trace demo & 200-seed statistical evaluation
python -m shifting_manor.cli --agent b3 --mode explorer --seed HAUNT-4F2A --verbose
python -m shifting_manor.sim --runs 200 --out sim/results.json

# Test suite & lint
pytest -q
ruff check . && ruff format --check .
```

## Controls Reference

| Action | Input |
|---|---|
| Move | `WASD` / Arrow keys / Click glowing adjacent room |
| Leave Manor (at Entrance `(0,0)`) | `E` or click `LEAVE MANOR [E]` / Entrance tile |
| Cast Charm (1 per game, straight line) | `C` then Arrow / `WASD` / Click direction |
| Mark room notes | Right-click cycles `?` → `Pit` → `Ghost` → `Safe`; or `1–4` / `0` clear |
| Toggle Live Autonomous AI Takeover | `T` (hand over to / reclaim from real agent anytime!) |
| Fair AI Hint (manual play) | `I` |
| Toggle Live Belief & Risk Overlay | `B` |
| Live AI Playback | `Space` pause/play · `Right` / `.` step · `+`/`-` speed · `F` fast-finish |
| Inspect `Why?` Proof Tree | `W` or click a room / log firing |
| How to Play Field Guide / Settings | `H` / `O` |
| Simulation Lab / Presenter Overlay | `F2` / `F1` |
| Restart / New Seed / Fullscreen / Pause | `R` / `N` / `F11` / `Esc` |

## Featured Demo Seeds

- `HAUNT-4F2A` (Explorer — clear wing shifts, ghost banishment, full proof chains)
- `HAUNT-7C1D` (Explorer — overlapping constraints and R16 transport)
- `HAUNT-5D7C` (Explorer / Haunted — high-pressure deduction)

## Docs

| File | What |
|---|---|
| `docs/PRD.md` | Product requirements (game design, UX, AI, scope) |
| `docs/ALGORITHMS.md` | Algorithm choices and rationale |
| `docs/EVALUATION.md` | 200-seed baseline evaluation & statistical tests |
| `docs/OPTIMALITY_AUDIT.md` | 1,000-seed exact-posterior optimality audit |
| `docs/CODE_TOUR.md` | Walkthrough of engine, KB, agents, and UI |
| `docs/FORWARD_CHAINING_WALKTHROUGH.md` | Step-by-step trace of R01–R24 |
| `docs/DEMO_SCRIPT.md`, `docs/QA.md` | Live presentation script & lecturer Q&A |
| `STATUS.md`, `DECISIONS.md` | Live status and decision log |
