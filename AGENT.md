# AGENT.md — Build and Handover Guide for Shifting Manor

You are the coding agent building **Shifting Manor**: a Wumpus-World-style haunted-house deduction game in Python, played by humans and by a rule-based knowledge-based AI (the "Caretaker AI"). Read `docs/PRD.md` (product intent; Section 16 = algorithm choices), `docs/ALGORITHMS.md`, `docs/TEAM_PLAN.md` and `ASSETS.md` (art/audio). This file tells you *how to build it* and *when you are done*.

**If you are starting a fresh session, do these in order:** (1) read this file fully; (2) read Section 13 (overnight protocol) and Section 12 (GitHub setup); (3) execute them; (4) keep `STATUS.md` updated.

## 0. Ground rules

1. **Simple and realistic beats clever.** This is a university project (Week 6: Knowledge / expert systems). Do not add features that are not in the PRD. If something is ambiguous, pick the simplest reading, record it in `DECISIONS.md` (date, question, choice, reason), and continue.
2. **Course requirement is non-negotiable:** facts + at least 15 IF–THEN rules (the PRD defines 24, R01–R24) + forward chaining + Python + demo with sample inputs and outputs. RL is optional and only after M5.
3. **Engine is pure Python.** `engine/`, `kb/`, `agents/`, `sim/` must never import pygame. All game logic must be testable headless.
4. **Determinism:** same seed → same map, same shift schedule, same outcome for a deterministic agent. Use `random.Random` instances derived from the seed (e.g. `Random(f"{seed}:map")`, `Random(f"{seed}:shift")`). Never use the global `random`.
5. **Assets must never block development.** Load everything through the asset manifest. Missing files fall back to generated placeholders (colored shapes, silence) with one warning log per asset.
6. Small commits, one milestone at a time, tests green before moving on.

## 1. Tech stack and commands

- Python 3.11+, `pygame-ce`, `pytest`, `ruff`. `numpy` optional (not required).
- No network access at runtime. No telemetry.

```
pip install -e ".[dev]"               # install
python -m shifting_manor              # launch the game (title screen)
python -m shifting_manor --mode explorer --seed HAUNT-4F2A --windowed --no-audio
python -m shifting_manor.cli --agent b3 --mode explorer --seed HAUNT-4F2A --verbose   # sample I/O demo
python -m shifting_manor.sim --runs 200 --out sim/results.json                        # baseline comparison
pytest -q                             # tests
ruff check . && ruff format --check .
```

## 2. Repository layout

```
shifting_manor/
  engine/    # pure rules: state, generator, actions, percepts, shift, scoring
  kb/        # facts, constraints, rules (R01-R24), forward chainer, proof log
  agents/    # random, reactive, kb_agent (b2, b2b, b3), planner, risk
  sim/       # headless batch runner, metrics, JSON/CSV export
  ui/        # scenes, widgets, tween, particles, lighting, audio, assets loader
  cli.py     # text-mode demo: percepts -> rules fired -> action
  __main__.py
assets/      # see ASSETS.md; manifest.json is the single source of truth
tests/
docs/PRD.md
DECISIONS.md
```

## 3. Game rules to implement (summary; PRD Section 6 is authoritative)

- Coordinates `(x, y)`, x right, y up; entrance `(0,0)`. 4-neighbourhood only.
- Modes: Apprentice 4x4 (2 pits, oil 40, no shifts); Explorer 6x6 (4 pits, oil 80, shift every 8 actions); Haunted 6x6 (5 pits, oil 70, shift every 5 actions). One ghost, one fixed treasure in all modes.
- Entrance and its two neighbours never contain hazards at generation. Treasure reachable from the entrance via hazard-free path at generation. Generator retries with the seeded RNG until valid.
- Percepts (only for the occupied room): `breeze`, `chill` (ghost alive), `glimmer` (treasure in room or any 4-neighbour), `bump`, `scream`, `rumble` (shift warning).
- Actions: `Move(dir)`, `CastCharm(dir)` (once; kills ghost anywhere on that line up to the wall; -10 score), `Leave` (only at entrance). Each Move/Cast costs 1 oil. Bump costs nothing and does not advance the action counter.
- Treasure auto-picked on entering its room. Death on entering a pit room or the living ghost's room. Oil 0 = lantern dies = defeat.
- Score: +1000 escaped with treasure, +200 ghost banished, -10 per charm, -1 per action, -1000 death.

### 3.1 The Shift (get this exactly right)

- Wings for 6x6: `wing_id = (x // 3, y // 3)`: SW (0,0) = foyer, never rotates; SE (1,0), NW (0,1), NE (1,1) rotate. Wing centres: SE (4,1), NW (1,4), NE (4,4).
- Rotation affects **hidden contents only** (pits and ghost). Rooms, walls, treasure, entrance do not move. The wing centre content stays.
- Clockwise about centre `c`: `(dx, dy) -> (dy, -dx)`. Anticlockwise: `(dx, dy) -> (-dy, dx)`.
- Every K actions a shift executes; **2 actions before**, emit `ShiftTelegraph(wing, direction, in_actions)` and set `percepts.rumble`. The wing/direction come from the seeded shift RNG.
- At telegraph time validate: no hazard may land on the treasure room, and a hazard-free path entrance→treasure (or entrance→agent→... if treasure already held, entrance reachable from agent) must still exist. If invalid try the opposite direction; if still invalid, mark the shift skipped.
- If the agent stands inside the target wing at execution time, the shift is skipped (emit `ShiftSkipped`).
- Emit `ShiftApplied(wing, direction, mapping: dict[Cell, Cell])` so UI can animate and the KB can transport knowledge. Agent is told wing + direction, never new hazard positions.

Required unit tests for rotation: four clockwise rotations = identity; cw then ccw = identity; centre fixed; mapping is a bijection on the wing; 4-adjacency inside the wing is preserved.

## 4. Public interfaces (keep stable; UI, sim and CLI depend on them)

```python
Cell = tuple[int, int]
Dir = Literal["N", "E", "S", "W"]

@dataclass(frozen=True)
class Move:  dir: Dir
@dataclass(frozen=True)
class CastCharm: dir: Dir
@dataclass(frozen=True)
class Leave: ...

@dataclass(frozen=True)
class Percepts:
    breeze: bool; chill: bool; glimmer: bool; bump: bool; scream: bool
    rumble: ShiftWarning | None           # wing, direction, in_actions

@dataclass(frozen=True)
class GameInfo:                           # what an agent may know at reset
    size: int; pit_total: int; entrance: Cell; shift_every: int | None
    oil: int; wings: dict[Cell, int]      # cell -> wing id; foyer id marked non-rotating

class Game:
    def __init__(self, mode: Mode, seed: str): ...
    def info(self) -> GameInfo: ...
    def observe(self) -> Percepts: ...
    def step(self, action) -> StepResult  # (percepts, events: list[Event], done: bool)
    state: GameState                      # read-only for UI (hazards only revealed at game end)

class Agent(Protocol):
    def reset(self, info: GameInfo) -> None: ...
    def act(self, percepts: Percepts, events: list[Event]) -> Action: ...
    def explain(self) -> Explanation      # thought line, firings this turn, beliefs per cell

@dataclass
class Firing:   # one line in the Inference Log and nodes of the Why? proof tree
    rule_id: str; premises: tuple[Fact, ...]; conclusions: tuple[Fact, ...]; turn: int
```

Events (UI animates from these): `Moved`, `Bumped`, `PickedUp`, `CharmCast`, `GhostBanished`, `Died(cause)`, `OilLow`, `ShiftTelegraph`, `ShiftApplied`, `ShiftSkipped`, `Escaped`, `OilOut`.

## 5. Knowledge base and inference (the graded core)

- Facts: `NoPit`, `NoGhost`, `Pit`, `Ghost`, `Safe`, `Unsafe`, `NoTreasure`, `TreasureAt`, `Visited`; constraints `Constraint(kind, frozenset[Cell])` meaning at least one hazard of `kind` is in the set. Globals: `PitTotal`, `GhostAlive`, `HasTreasure`, `CharmAvailable`, `Oil`.
- Store the **observation base** (percept history, with rotation transport applied) and **recompute derived facts to fixpoint every turn**. Do not hand-maintain retractions.
- Implement the 24 rules R01–R24 from PRD 7.3 as separate `Rule` objects with `id`, `description`, premise/conclusion functions. Do not collapse several rules into one function; the grader must be able to see each rule fire.
- Forward chainer: loop over rules in fixed priority order, add new facts, log a `Firing` for each new conclusion, stop at fixpoint. Guard against infinite loops with a max-iterations assertion.
- **R16 knowledge transport:** on `ShiftApplied(mapping)`, replace every cell `n` in all pit/ghost facts and all pit/ghost constraint sets by `mapping.get(n, n)`. Treasure facts are NOT transported. Keep this as one pure function `transport(kb_observations, mapping)` with its own tests.
- Agent variants (same class, flags): `b3` full; `b2` shift-blind (skips R16); `b2b` forgetful (on shift, delete all pit/ghost facts and constraints touching the rotated wing). Also implement `random`, `reactive` and `oracle` (B4: sees the full map, takes the best safe route; upper bound only).
- **Algorithm stack for b3 (full rationale in `docs/ALGORITHMS.md`):**
  1. Forward chaining over R01–R24 to fixpoint (the graded core; every conclusion logged as a `Firing`).
  2. `kb/enumerate.py`: exact model enumeration over frontier cells (cells that appear in any constraint set). A world = assignment of pits/ghost to frontier cells consistent with all NoX facts and constraints. Entailed facts = true in all worlds. Risk(c) = weighted share of worlds with a hazard at c, where a world with k frontier pits has weight `C(U, pits_left - k)` (U = unknown non-frontier cells). If the frontier has more than 14 cells, fall back to independence approximation and log a warning.
  3. Planning: A* (Dijkstra acceptable) over cells with edge cost `1 + lambda * (-ln(1 - risk(c)))`, lambda default 1.0; heuristic Manhattan distance. Known-Unsafe cells are impassable. Respect the oil budget: reject routes whose oil cost exceeds remaining oil minus return cost.
  4. Gamble choice when no safe goal exists (R22): maximise `-1000 * P(death) - path_cost + 0.5 * unknown_neighbours(c)`; tie-break by distance, then by cell order for determinism.
  5. Retreat (R23): if `oil <= shortest_safe_return + margin` (margin 3) go home.
- Property test (required): every fact derived by forward chaining must be entailed by the enumeration; if not, the rule is buggy. Enumeration must never be used to *mask* a wrong rule; fix the rule.
- Every rule must be hit by at least one test scenario (table-driven, small hand-built boards).

## 6. UI requirements (summary; PRD Section 8 is authoritative)

- 1280x720 logical, integer pixel scale x3 for 32px art, letterboxed fullscreen toggle (F11), 60 FPS, fixed-timestep logic with interpolated rendering.
- Scenes: Boot, Title, ModeSelect, Tutorial, Gameplay (Play / WatchAI / Duel share one scene with a controller), Result, SimLab, Settings, Pause.
- Gameplay layout: board left (576 px), right sidebar with HUD, Shift Clock, Senses panel, tabs (Notes, Inference Log, Knowledge Base).
- Lantern fog of war: alpha-mask light surface, flicker via low-frequency noise, dims below 25% oil. Cache the light surface; do not rebuild per frame.
- Percept feedback table in PRD 8.6 (visual + audio + text). Reduce-motion setting disables shake and rotation tween (instant cut).
- Marks: one shared icon set for human notes and AI beliefs (shape + colour). Marks inside a rotating wing rotate with it.
- Shift choreography per PRD 8.8; any key skips the animation but still applies the state change.
- Watch AI: thought bubble, belief overlay, clickable log lines highlight cells, Why? proof tree, speed 0.5x–4x, step/pause.
- Duel: human run, then AI on the same seed; side-by-side result.
- All user-facing strings in `ui/strings.py`. Font scale and colour-blind-safe palette from `ui/theme.py`.
- Audio manager: music crossfade between calm and tense layers by risk; SFX with per-sound cooldown (e.g. `rule_fire` max 8/s); master/music/sfx volumes in settings; `--no-audio` must fully work.

## 7. Asset handling

- `assets/manifest.json` maps logical keys to files, frame size, frame count and fallback colour. Example entry:

```json
{ "caretaker_walk_side": { "file": "sprites/caretaker_walk_side.png", "frame": [32, 32], "frames": 6, "fps": 10, "fallback": "#FFB347" } }
```

- Loader returns an `AnimatedSprite`/`Surface`; if the file is missing, generate a placeholder (labelled coloured rect) and log once. Audio missing → silent stub.
- Key names equal the file names in `ASSETS.md` (without extension). Do not hardcode paths outside the manifest.

## 8. Milestones and acceptance criteria

| # | Milestone | Done when |
|---|---|---|
| M0 | Scaffolding | repo layout, `pyproject.toml`, CI-style script runs pytest + ruff, empty window opens |
| M1 | Engine | generator, percepts, actions, scoring, shift + validation; rotation tests pass; same seed reproduces same game; 1000 random-agent games run without exceptions |
| M2 | KB + inference | R01–R24 implemented, forward chainer, proof log; every rule covered by a test; `cli.py` prints percepts → rules fired → action for a full game |
| M3 | Agents + sim | random, reactive, b2, b2b, b3, oracle; enumeration + A* + expected-utility choice; `sim` runs 200 seeds/mode and writes JSON; b3 never crashes; metrics table printed |
| M4 | Play mode UI | title, mode select, board, fog, percept feedback, HUD, marks, result screen; fully playable by keyboard and mouse |
| M5 | Watch AI | belief overlay, inference log, Why?, speed controls, shift choreography, knowledge rearranging visuals |
| M6 | Polish and extras | audio layers, particles, tutorial, Duel, SimLab chart, Run Card PNG export, accessibility settings |
| M7 | Hardening | 60 FPS check, clean-checkout run, fallback demo recording script, README with screenshots |
| Opt | RL layer | only after M5; Q-learning over abstract state (PRD 7.7); ship only if it beats b3 in sim, otherwise document as negative result |

## 9. Testing requirements

- Unit: rotation, generator validity, percept computation, scoring, each rule (R01–R24), transport function, planner decisions on fixed boards.
- Property tests: random boards → agents never crash; b3 never steps onto a cell its own KB marks `Unsafe` unless in the risk fallback (log those cases).
- Determinism test: two runs with same seed produce identical event logs.
- Cross-check: forward-chaining conclusions are entailed by enumeration (see Section 5).
- Sim sanity: on Apprentice, b3 win rate must exceed b1, and oracle must be >= b3; if not, treat as a bug before tuning anything.
- Headless UI smoke test: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy` start each scene for 60 frames without exceptions.

## 10. Do not

- Do not add online features, accounts, analytics, or external services.
- Do not rewrite rules as a monolithic if/else block; the rule objects are the deliverable.
- Do not tune game balance without sim data; record changes in `DECISIONS.md`.
- Do not start the RL layer before M5 is accepted by a human.
- Do not use RL, minimax or MCTS as the core agent. The core is forward chaining + enumeration + A* (see `docs/ALGORITHMS.md` for why).
- Do not commit large binaries; art/audio live in `assets/` and are small (see `ASSETS.md` limits).

## 11. Handover checklist (final step)

- [ ] `README.md`: what it is, install, run, controls, screenshots, how to demo (3 commands).
- [ ] `docs/PRD.md` and `ASSETS.md` current.
- [ ] `sim/results.json` and a short `docs/EVALUATION.md` with the baseline table and honest notes (forced-guess rate, where b3 fails).
- [ ] Fixed demo seeds listed in README (one Apprentice, two Explorer, one Haunted that shows a shift clearly).
- [ ] `DECISIONS.md` lists every assumption you made.
- [ ] Known issues list with workarounds.
- [ ] Fallback: `scripts/record_demo.py` or a documented screen-recording procedure.

## 12. GitHub setup (you have access; do this first)

You are authorised to create and configure **one** repository. Use the authenticated GitHub account (do not guess an owner name; read it from the API/CLI). Do not touch other repositories, organisations, account settings, secrets, or billing.

1. Create repo `shifting-manor`.
   - **Visibility: private** for now (the owners will decide later whether to make it public).
   - **Description:** `Haunted-manor deduction game with a rule-based, forward-chaining Caretaker AI. AI course Week 6 project (Python, pygame-ce).`
   - **Topics:** `python`, `pygame`, `artificial-intelligence`, `expert-system`, `forward-chaining`, `knowledge-based-agent`, `wumpus-world`, `game-ai`, `education`.
   - Default branch `main`. Enable Issues. No wiki needed.
2. **License:** MIT (file `LICENSE` already in this folder; copyright holders Muhammad Ghiffari and Radithia Ary Winata, 2026). Art/audio licensing is tracked per-file in `assets/CREDITS.md`; do not relabel third-party assets as MIT.
3. Push the initial commit from this folder as-is (`chore: initial handover bundle`). Confirm `.gitignore` excludes `__pycache__`, `.venv`, `dist`, `*.pyc`, `sim/results_tmp/`, and OS junk.
4. Create GitHub **milestones** M0–M7 and one issue per milestone containing its acceptance criteria (copy from Section 8). Labels: `engine`, `kb`, `agent`, `ui`, `audio`, `assets`, `docs`, `bug`, `blocked`.
5. Branching: `main` is always green. Work on `feat/m1-engine`, `feat/m2-kb`, and so on; open a PR per milestone with a checklist and test output; merge (squash) only when CI is green. If branch protection is not available on the plan, just follow the rule by hand and note it in `DECISIONS.md`.
6. CI: `.github/workflows/ci.yml` is provided (ruff + pytest, Python 3.11 and 3.12). Make sure it passes on the first push; fix the skeleton if not.
7. **Collaborator:** do NOT guess usernames. Write in `STATUS.md` under "Needs human": "Invite Radithia Ary Winata as collaborator (need GitHub username)".
8. Never force-push `main`, never delete branches you did not create, never commit secrets or personal data, never publish releases.

## 13. Overnight protocol (the human is asleep)

The humans start the run and review in the morning. Work autonomously within these limits.

**Scope for tonight:** Section 12 (GitHub setup) + milestones **M0, M1, M2, M3**. These are verifiable with tests and text output only.

**Stretch (only if M0–M3 are fully green):** M4 (Play mode UI). Verify visually by saving screenshots with `SDL_VIDEODRIVER=dummy` and `pygame.image.save(...)` into `docs/screens/` (title, board with fog, shift animation mid-frame, result). A human must review them before any further UI polish. Do not start M5 or later tonight.

**Rules of engagement**

- Commit small and often with conventional messages (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
- After each milestone: run `pytest -q` and `ruff check .`, open the PR, merge only if green, and tag `m1`, `m2`, and so on.
- If you are stuck on the same problem after 3 distinct attempts, write it in `STATUS.md` ("Blocked"), open an issue labelled `blocked`, and move to the next independent task.
- If an instruction would require a destructive, external, or irreversible action not listed in Section 12, skip it and note it.
- If you must choose between simple and clever, choose simple and note the choice in `DECISIONS.md`.
- Do not install anything outside the project virtualenv. No network calls at runtime from the game.
- Do not generate or download art/audio tonight. Assets are produced separately (see `ASSETS.md`). The loader must handle their absence.

**`STATUS.md` (update at least after every milestone and at the end)**: what is done (with commit/PR links), what is in progress, what is blocked, how to run and verify everything (exact commands), test counts, sim results table, decisions you made, risks you see, and "Needs human" items (including collaborator invite and the lecturer-policy questions in PRD Section 14).

## 14. Morning review checklist (for the humans; keep this section in sync with reality)

- [ ] Repo exists, private, description and topics set, MIT `LICENSE` present, CI green on `main`.
- [ ] `STATUS.md` is honest and specific; "Needs human" items are listed.
- [ ] `pytest -q` passes locally; the rotation tests and the "every rule fires" tests exist.
- [ ] `python -m shifting_manor.cli --agent b3 --mode explorer --seed HAUNT-4F2A --verbose` prints percepts, rules fired, and actions for a full game.
- [ ] `python -m shifting_manor.sim --runs 200` produced `sim/results.json`; the ordering oracle >= b3 > b2b > b2 > b1 > b0 is plausible, or the agent explains why not.
- [ ] No giant files, no secrets, no unexpected repos or settings touched.
