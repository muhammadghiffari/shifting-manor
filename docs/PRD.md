# Shifting Manor — Product Requirements Document

Version 1.1 · Course: Artificial Intelligence (Week 6, Knowledge) · Team of 2 (Muhammad Ghiffari, Radithia Ary Winata) · Presentation: next week · Status: approved for build

> Canonical copy of the PRD lives in this repo (`docs/PRD.md`). Section 16 was added in v1.1.

## 1. Summary

Shifting Manor is a single-player haunted-house deduction game in the tradition of Wumpus World. You explore a dark manor with a lantern, sense hazards only through nearby clues (breeze, chill, glimmer), fetch the heirloom and escape before your lantern oil runs out. The signature twist: every few moves one wing of the manor **rotates**, carrying hidden pits and the ghost to new places. What you knew must be *transported*, not just trusted.

The same game is played by the **Caretaker AI**: a knowledge-based agent with an IF–THEN rule base and a forward-chaining inference engine. The UX goal is twofold: humans enjoy playing it, and anyone can watch the AI think step by step, so the lecturer sees expert-system concepts working live instead of on slides.

## 2. Goals and non-goals

**Goals**

- G1 Satisfy the Week 6 brief: facts + at least 15 IF–THEN rules, forward chaining, Python, a demo with sample inputs and outputs.
- G2 A game classmates want to play: a round takes under 3 minutes, with atmosphere, animation and sound.
- G3 Make AI reasoning visible (inference log, belief overlay, a ‘Why?’ button).
- G4 Fit in about 7 working days for 2 people.

**Non-goals (v1)**

- Reinforcement learning (optional stretch only, see 7.7), online multiplayer, mobile, level editor, story or dialogue systems, accounts, monetisation.

## 3. Brief traceability

| Brief requirement | Where it is satisfied |
|---|---|
| Topic: any domain | Game-playing deduction (knowledge-based agent), Sections 6–7 |
| Facts + at least 15 IF–THEN rules | Rule table R01–R24, Section 7.3 |
| Forward or backward chaining | Forward chaining to fixpoint after every percept, Sections 7.4 and 16 |
| Python, sample inputs and outputs | Python 3.11 + pygame-ce; CLI mode prints percepts → rules fired → action; Section 9 |
| Keep it simple and realistic | Scope tiers (Section 10), engine is pure Python, one signature twist only |

## 4. Users and moments of use

- **Lecturer (grader):** wants to see the knowledge base, the rules, and an inference trace that is correct. Needs the rule list to be one click away.
- **Classmates:** play one round in under 3 minutes and want a clear ‘beat the AI’ challenge.
- **Presenters (the team):** need one-command launch, reliable audio and video, fixed demo seeds and a fallback if something breaks.

## 5. UX pillars

1. **Dread you can feel.** Darkness, a flickering lantern, sound that tells you something is near.
2. **Read the machine’s mind.** Human notes and AI beliefs share one visual language, so watching the AI teaches you to play better.
3. **Fair and replayable.** Every map has a seed code. Same seed, same map, same shifts. Share a code, challenge a friend.
4. **Never make the player wait.** Input feedback under 100 ms, every animation skippable, restart in one key.

## 6. Game design

### 6.1 Premise

You are the Caretaker. The old manor swallowed the family heirloom. Retrieve it and return to the entrance door before the lantern oil burns out. Pits and one ghost haunt the rooms, and the manor’s wings grind and turn when it wants to.

### 6.2 Board and difficulties

| Mode | Grid | Pits | Ghost | Oil (actions) | Shift every |
|---|---|---|---|---|---|
| Apprentice | 4×4 | 2 | 1 | 40 | never |
| Explorer | 6×6 | 4 | 1 | 80 | 8 actions |
| Haunted | 6×6 | 5 | 1 | 70 | 5 actions |

Coordinates are (x, y) with x to the right and y upward; the entrance is (0, 0) at bottom-left. The 6×6 board is split into four 3×3 **wings**: SW (the foyer, containing the entrance), SE, NW, NE. The foyer never rotates.

### 6.3 Entities

- **Entrance door** at (0,0): start and exit.
- **Pits:** entering one kills you. **Ghost:** entering its room kills you (while alive).
- **Heirloom (treasure):** one, fixed in place, never rotates. Picked up automatically on entering its room.
- The entrance and its two neighbours never contain hazards at generation. The heirloom is reachable from the entrance by a hazard-free path at generation.

### 6.4 Percepts (only in the room you stand in)

| Percept | Condition |
|---|---|
| Breeze | a pit is in a 4-neighbour room |
| Chill | the ghost is in a 4-neighbour room and alive |
| Glimmer | the heirloom is in this room’s 4-neighbourhood (this room included) |
| Bump | you walked into a wall (no action cost) |
| Scream | your charm banished the ghost |
| Rumble | a shift is coming (see 6.7) |

Absence is information too: no Breeze means no pit in any neighbour.

### 6.5 Actions

- **Move** N/E/S/W: 1 oil.
- **Cast Charm** in a direction: 1 oil, once per game. Kills the ghost if it is anywhere in that row or column segment up to the wall. Costs 10 score.
- **Leave Manor**: only at the entrance. Ends the run with or without the heirloom.
- Oil reaching 0 ends the run in defeat (the lantern dies).

### 6.6 Scoring

Score = 1000 if escaped with heirloom + 200 if the ghost was banished − 10 per charm cast − 1 per action − 1000 on death. Star rating uses par = the oracle's action count on the same seed: 3 stars = escaped with the heirloom in at most par + 15 actions; 2 stars = escaped with the heirloom (slower); 1 star = escaped empty-handed; 0 = died or stalled. Relative par keeps a fast map from handing out free 3-star runs.

### 6.7 The Shift (signature mechanic)

- Every K actions (K in the table above) one rotating wing turns 90°. The target wing and direction (↻ or ↺) come from the seed.
- **Telegraph:** 2 actions before it happens a Rumble is perceived. The target wing glows with its direction arrow and a countdown appears.
- **What rotates:** the *hidden contents* of the wing (pits and ghost) turn 90° about the wing’s centre room. Rooms, walls and the heirloom stay put. In (x, y) relative to the centre, clockwise maps (dx, dy) to (dy, −dx); anticlockwise maps (dx, dy) to (−dy, dx).
- **Player rule:** a wing that contains the player never rotates (‘the manor holds its breath’). Standing in a wing can cancel its shift. That is a tactic.
- **Validation at telegraph time:** if the rotation would put a hazard on the heirloom room, or break the hazard-free path from entrance to heirloom, try the opposite direction; if that fails too, the shift is skipped.
- The player is told which wing and which direction, but never where hazards end up. Knowledge about hazards in that wing must be transported by the same rotation.
- **Why this is good logic, not a gimmick:** old observations don’t become false, they become *relocated*. A smart agent applies the rotation to its beliefs; a naive one is confidently wrong. That gap is measurable (see 7.6).

### 6.8 Seeds

A seed string such as HAUNT-4F2A fully determines the map, the wing order and the shift directions. The seed is shown on the HUD and result screen and can be typed on the mode-select screen.

## 7. The Caretaker AI

### 7.1 Approach

A knowledge-based agent: a knowledge base (KB) of facts and constraints, a rule base of IF–THEN rules, and a forward-chaining inference engine that runs to a fixpoint after every percept and every shift. A planner then picks an action from the derived facts. Every rule firing is logged for the UI.

### 7.2 Knowledge representation

- **Cell facts:** NoPit(c), NoGhost(c), Pit(c), Ghost(c), Safe(c), Unsafe(c), NoTreasure(c), TreasureAt(c), Visited(c).
- **Constraints:** Constraint(kind, S) means at least one hazard of that kind is in the cell set S (from Breeze, Chill, Glimmer observations).
- **Globals:** PitTotal, GhostAlive, HasTreasure, CharmAvailable, Oil, ActionCount.
- Derived facts are recomputed to fixpoint from the *observation base* each turn, so retraction and transport stay simple and bug-free.

### 7.3 Rule base (24 rules)

| ID | IF | THEN |
|---|---|---|
| R01 | Visited(c) | NoPit(c) and NoGhost(c) |
| R02 | NoBreeze observed at c | NoPit(n) for every neighbour n of c |
| R03 | NoChill observed at c | NoGhost(n) for every neighbour n of c |
| R04 | Breeze observed at c | add Constraint(PIT, neighbours of c) |
| R05 | Chill observed at c | add Constraint(GHOST, neighbours of c) |
| R06 | Constraint(PIT, S) and exactly one n in S lacks NoPit | Pit(n) |
| R07 | Constraint(GHOST, S) and exactly one n in S lacks NoGhost | Ghost(n) |
| R08 | NoPit(c) and NoGhost(c) | Safe(c) |
| R09 | Pit(c), or Ghost(c) with GhostAlive | Unsafe(c) |
| R10 | Ghost(g) known | NoGhost(x) for all x other than g (single ghost) |
| R11 | number of known Pit facts equals PitTotal | NoPit(x) for every cell without Pit |
| R12 | Scream perceived | GhostAlive = false; drop all ghost facts and constraints |
| R13 | NoGlimmer observed at c | NoTreasure(x) for x in c and its neighbours |
| R14 | Glimmer observed at c | add Constraint(TREASURE, c and its neighbours) |
| R15 | Constraint(TREASURE, S) and exactly one n in S lacks NoTreasure | TreasureAt(n) |
| R16 | Rotated(wing, direction) | **knowledge transport:** apply the wing’s rotation to every pit/ghost cell fact and every pit/ghost constraint set |
| R17 | path of Safe cells from agent to b | Reachable(b) |
| R18 | HasTreasure and Reachable(entrance) | Goal = entrance |
| R19 | TreasureAt(t), Reachable(t), not HasTreasure | Goal = t |
| R20 | Ghost(g), CharmAvailable, agent in line with g | Action = CastCharm toward g |
| R21 | no treasure goal, Safe unvisited cell exists | Goal = nearest such cell |
| R22 | no safe goal and not HasTreasure | Goal = frontier cell with best expected utility (lowest risk, see Section 16) |
| R23 | Oil less than or equal to shortest-safe-path to entrance + margin | Goal = entrance (retreat) |
| R24 | Rumble perceived for wing w and agent is outside w | prefer routes and goals that do not rely on Safe facts inside w beyond the shift |

### 7.4 Inference engine

Forward chaining: keep an agenda of rules whose premises hold, fire them in a fixed priority order, add conclusions, repeat until no new fact appears (fixpoint). Each firing emits a log record: rule ID, premise facts, conclusion facts, game turn. These records drive the Inference Log, the ‘Why?’ proof chain and the rule heat bars.

### 7.5 Action selection

Order of precedence: R20 charm, R18/R19 goals, R21 safe frontier (search over Safe cells), R23 retreat check, R22 risk fallback. Risk and gamble selection follow Section 16 (exact model enumeration over frontier cells, A* with risk-weighted edge cost, expected-utility choice). Ties are broken by shorter distance, then by information value.

### 7.6 Baselines and evaluation (for the presentation)

| Agent | Description |
|---|---|
| B0 Random | random legal moves |
| B1 Reactive | no memory; avoids rooms next to current percepts |
| B2 KB, shift-blind | full rule base but ignores R16 (never updates after a shift) |
| B2b KB, forgetful | on a shift, drops every fact about the rotated wing |
| B3 KB, transport | full rule base including R16, plus Section 16 algorithms |
| B4 Oracle | sees the full map; upper bound for comparison (not a fair competitor) |

Run 200 seeds per mode. Report win rate, mean score, mean actions and death causes. **Hypothesis to test, not assume:** B3 > B2b > B2 > B1 > B0 on Explorer and Haunted, with B4 as the ceiling. If B2 is not clearly worse than B3, the twist is cosmetic and K or hazard density needs tuning. Some maps force a guess; report the ‘forced-guess rate’ honestly.

### 7.7 Optional: reinforcement learning layer (Could)

Only after milestone M5. Tabular Q-learning over an abstract state (known-safe frontier count, minimum frontier risk bucket, oil bucket, has-treasure) to choose between ‘explore’, ‘gamble’ and ‘retreat’. Ship it only if it beats B3 in simulation; otherwise report it as a negative result, which is still a valid finding.

## 8. UX specification

### 8.1 Platform

Python 3.11+, pygame-ce, 1280×720 logical resolution with letterboxed scaling and fullscreen (F11), 60 FPS, keyboard and mouse, fully offline. Pixel art is drawn at 32 px tiles and rendered at integer scale ×3 (a room is 96 px).

### 8.2 Screen flow

Boot splash → Title → Mode Select (Play · Watch AI · Duel · Simulation Lab · How to Play · Settings) → [Tutorial on first run] → Gameplay → Result → (Replay same seed · New seed · Menu).

### 8.3 Gameplay layout (1280×720)

- **Left (about 640 px):** the 6×6 board (576 px) with margin. Wing borders appear as faint rune lines.
- **Right (about 640 px), top:** HUD with oil gauge (lantern), score, charm, heirloom indicator, seed code and the **Shift Clock** (dial showing actions left and the next wing with ↻/↺).
- **Right, middle:** **Senses panel** showing the percept icons for the current room with short flavour text.
- **Right, bottom:** tabs: **Notes** (legend and shortcuts), **Inference Log**, **Knowledge Base** (rule list with fire counts).

### 8.4 Controls

| Action | Input |
|---|---|
| Move | Arrow keys or WASD, or click an adjacent room |
| Charm | C, then arrow key or click a direction (aim preview line) |
| Mark a room | Right-click cycles: none → ? → pit → ghost → safe (or keys 1–4) |
| Toggle belief overlay | B |
| Restart same seed / new seed | R / N |
| Pause | Esc |
| Cycle sidebar tabs | Tab |
| AI mode | Space play/pause, Right arrow step, + and − speed (0.5×–4×), click a room for ‘Why?’ |
| Presenter overlay | F1; Simulation Lab F2 |

### 8.5 Fog of war and lantern

Unvisited rooms are dark. The lantern is a soft radial light around the player that flickers subtly. It dims when oil is below 25% and a heartbeat-like pulse starts. Visited rooms stay dimly visible with dust footprints. Light is composited with an alpha mask over the board.

### 8.6 Percept feedback

| Percept | Visual | Audio | Text (Senses panel) |
|---|---|---|---|
| Breeze | drifting wind streaks, cool blue tint at screen edge, icon pulses | looping soft wind that rises with nearby pits | ‘A cold draft slips through the floor.’ |
| Chill | green miasma wisps, slight screen desaturation | low whispering growl | ‘Something is watching you.’ |
| Glimmer | gold sparkles, warm glow | rising chime | ‘Something gleams close by.’ |
| Rumble | board shake, wing border glows, arrow appears | stone rumble + clock tick | ‘The manor shifts in 2…’ |
| Quiet room | no effects | silence except music | ‘Nothing stirs.’ |

### 8.7 Marking system (shared visual language)

Human notes and AI beliefs use the same icons, always shape plus colour (colour-blind safe): **safe** = teal check, **pit** = orange-red X with a ring, **ghost** = pale cyan ghost glyph, **unknown/suspect** = violet question mark, **stale/transported** = dashed outline with a small rotation arrow. Confidence is shown by opacity. When a wing rotates, **all marks in that wing rotate with it** (for the human too), so notes stay truthful. That is a deliberate UX gift: shifting punishes sloppiness, not bookkeeping.

### 8.8 Shift choreography

1. Two actions before: Rumble, wing glows, clock dial flashes, tick sound.
2. Execution (about 1.4 s, skippable with any key): camera shake, the wing’s hidden-content layer spins 90° with dust particles and a stone grinding sound; marks inside spin with it.
3. Afterwards: a brief shimmer over the wing, ‘dust settles’ sound, the Shift Clock restarts.
4. In AI mode the belief overlay visibly rearranges. Scattered constraints crumble with a glassy sound. This is the key moment for the presentation.

### 8.9 Watch AI mode

- **Thought bubble** above the Caretaker with a one-line reason, e.g. ‘Safe by R02, moving to (2,1).’
- **Belief overlay** on the board: certain facts solid, probable facts translucent with risk percentage on hover.
- **Inference Log**: each line like ‘R02 NoBreeze(1,1) ⇒ NoPit(2,1), NoPit(0,1), NoPit(1,2).’ Clicking a line highlights the cells involved.
- **Why? on any room:** shows the derivation chain (proof tree) ending in the original percepts.
- **Knowledge Base tab:** the 24 rules with heat bars showing how often each fired this run.
- Playback: play, pause, single-step, speed 0.5×–4×.

### 8.10 Duel mode

The human plays a seed first, then the AI plays the same seed. The result screen shows both runs side by side: score, actions, path replay overlay, who took which risks. Classmates can challenge each other on the same seed code, then the AI.

### 8.11 Result screen

Outcome banner, stars, score breakdown, stats (actions, oil left, rules fired for AI runs), seed code, and a **Save Run Card** button that exports a PNG for slides. Buttons: Replay seed, New seed, Menu.

### 8.12 Onboarding

A skippable 90-second interactive tutorial on first run, four mini-boards: (1) move and feel a Breeze, (2) deduce a pit from two clues, (3) banish a ghost with the charm, (4) survive a shift with marks rotating. Contextual hints appear once and can be turned off.

### 8.13 Juice and polish checklist

- Easing on every move (about 160 ms), idle animations, footstep sounds that vary with surface.
- Particles: wind, miasma, sparkles, dust, debris.
- Death: short hit-stop, fall or ghost-grab animation, then a soft fade to the result screen.
- UI: hover and click sounds, 250 ms scene fades, button press squash.
- Music: calm layer plus a tension layer that fades in as risk rises (same tempo, crossfaded). Volume ducks on stingers.

### 8.14 Accessibility

Shape plus colour everywhere, high-contrast option, reduce-motion toggle (no shake, no rotation tween, instant cut), separate music and effects volume, font scale 100/125/150%, no flashing faster than 3 Hz, full keyboard operation.

### 8.15 Presenter tools and Simulation Lab

- F1 toggles a large-type presenter overlay (seed, step, rule being fired).
- **Simulation Lab (F2):** loads cached results of the 200-seed baseline comparison and draws a bar chart (win rate and mean score per agent per mode). A ‘Run again’ button recomputes headless in a background thread with a progress bar. This is the slide that proves the twist matters.
- Launch flags: --windowed, --no-audio, --seed XXXX, --mode haunted.

## 9. Technical architecture (summary; details in AGENT.md)

- **engine/**: pure Python game rules, seeded generator, shift logic. No pygame imports, fully testable.
- **kb/**: facts, constraints, rule definitions, forward-chaining engine, proof logging, exact enumeration.
- **agents/**: random, reactive, KB agents (B2, B2b, B3), oracle (B4), planner, risk estimator.
- **ui/**: pygame scenes, widgets, animation tweens, particles, audio manager.
- **sim/**: headless batch runner and metrics export (CSV and JSON).
- **assets/**: loaded via a manifest. Missing files fall back to generated placeholder shapes and silence, so development never blocks on art.
- CLI mode prints percepts → rules fired → chosen action, as the ‘sample inputs and outputs’ demo required by the brief.

## 10. Scope tiers and plan

| Tier | Content |
|---|---|
| **Must** | Engine + generator + shift, KB with 24 rules, forward chaining, B3 agent, Play and Watch AI modes, fog of war, percept feedback, belief overlay, inference log, sound basics, result screen, tests |
| **Should** | Duel mode, Simulation Lab, tutorial, marks rotating with wings, Why? proof tree, music layers, Run Card export |
| **Could** | RL layer (7.7), daily seed, web build via pygbag, extra skins |

Suggested 7-day plan: D1 engine, generator, tests · D2 KB, rules, inference, CLI demo · D3 UI skeleton and Play mode · D4 Watch AI mode, overlay, log · D5 shift choreography, audio, asset integration · D6 tutorial, Duel, Simulation Lab · D7 QA, rehearsal, recording a fallback video. (Day-by-day split for two people: `docs/TEAM_PLAN.md`.)

## 11. Definition of done

- All Must items work from a clean checkout with one command (pip install, then python -m shifting_manor).
- Engine and inference unit tests pass; same seed reproduces the same game byte-for-byte.
- Each of the 24 rules fires in at least one automated test scenario.
- B3 completes 200 seeds per mode without crashing; results are saved to JSON.
- The game holds 60 FPS on a mid-range laptop during a shift animation.
- A first-time player can finish a round without outside help.
- A fallback recording of a full demo exists.

## 12. Success metrics

- Playtest with at least 5 people: median round under 3 minutes, at least 4 of 5 say they would play again.
- B3 beats B2 on win rate by a clear margin in Haunted mode (target at least 15 percentage points; adjust after baselines are measured).
- Lecturer can find any rule and see it fire within 30 seconds of asking.

## 13. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Scope creep from polish | Scope tiers; polish only after Must is green |
| Shift logic makes inference buggy | Transport is one pure function; recompute derived facts each turn; property tests for rotation |
| AI looks dumb on forced-guess maps | Show the risk estimate honestly; report forced-guess rate; Apprentice mode for the first demo |
| Assets arrive late or are inconsistent | Placeholder fallback; style bible in ASSETS.md; replace in one pass |
| Audio latency or driver issues | --no-audio flag; small preloaded OGG files; test on the presentation laptop early |
| Live demo failure | Fixed demo seeds, a recorded fallback video, screenshots in slides |
| Team members cannot explain AI-written code | Explain-back checkpoints in TEAM_PLAN.md; both read every rule; each presents the part the other built |

## 14. Open questions

1. Does the lecturer expect RL, or is the rule-based expert system sufficient? (The brief says rule-based with forward or backward chaining.)
2. Which operating system and screen will be used for the presentation?
3. What is the course policy on AI-assisted code and assets, and must it be disclosed?
4. Which image/audio generation tool produces the assets (see ASSETS.md)?

## 15. Suggested presentation flow (8–10 minutes)

1. Hook (1 min): two classmates play the same seed in Duel mode.
2. Concept (2 min): knowledge base, facts, three example rules, forward chaining.
3. Live AI (3 min): Watch AI on an Explorer seed; click ‘Why?’ on a room; show a shift and the belief overlay rearranging.
4. Evidence (2 min): Simulation Lab bar chart, baselines B0–B4.
5. Reflection (1 min): limits (forced guesses, small board), what RL could add, Q&A.

## 16. Algorithm selection and rationale (v1.1)

The brief asks for a rule-based expert system with forward or backward chaining. That is the backbone. On top of it we add only the extra algorithms that make the agent measurably smarter, and each one has a stated reason.

| Layer | Algorithm | Why this one | Why not the alternative |
|---|---|---|---|
| Inference (required) | Forward chaining over the IF–THEN rules, run to fixpoint after every percept | Percepts arrive one at a time and every new fact should appear immediately. It is sound, cheap, and every conclusion traces back to a named rule, which the explanation UI depends on | Backward chaining answers one query at a time (is cell X safe?), so it would be re-run per cell and gives a weaker live log |
| Completeness check | Exact model enumeration over frontier cells | Rules over at-least-one clues can miss conclusions that need case analysis (two overlapping Breeze clues). Enumerating consistent worlds is exact and cheap for 14 frontier cells or fewer | DPLL/SAT finds the same entailments but gives no probabilities; sampling is unnecessary at this size |
| Risk | Cell risk from the same enumeration, each world weighted by the number of ways to place the remaining pits among the other unknown cells | Exact, consistent with the logic, and uses the known pit total (R11) | A fixed per-cell prior ignores the known pit count |
| Movement | A* (or Dijkstra) with edge cost = 1 oil + a risk penalty of −ln(1−p); Manhattan distance as heuristic | Maximises survival probability within the oil budget | Plain BFS ignores risk |
| Choice among gambles | Expected utility: −1000 × P(death) − path cost + small bonus for information (count of unknown neighbours as a cheap proxy) | A gamble is only taken when no safe move exists, and the cheap informative one wins | Always taking the lowest risk can stall; exact entropy is an optional upgrade |
| Shifts | Knowledge transport (R16) | Rotations are deterministic and announced, so beliefs can be moved exactly instead of forgotten | Forgetting (B2b) throws away valid information; ignoring (B2) is simply wrong |
| Reinforcement learning | Not in the core | See below | |

**Why RL is not the main brain.** (1) The brief is about knowledge-based systems. (2) A new random map every game plus partial observability makes learning slow and brittle without hand-made state features. (3) Learned policies are opaque, while our UX depends on explanations. (4) An exact reasoner already exists at this problem size, so RL would approximate what we can compute exactly. RL could still help with the explore / gamble / retreat meta-decision (see 7.7).

**Honest limit.** This agent is not provably optimal: the optimal policy solves a POMDP, ours is sound logic plus greedy expected-utility choices. We therefore measure instead of claim. Baseline **B4 Oracle** (sees the full map, plans the best safe route) gives an upper bound, so the report can say how close B3 gets.

**Correctness cross-check.** Every fact derived by forward chaining must also be entailed by the enumeration. A property test enforces this; a violation is a bug in a rule.

**Reference.** Russell & Norvig, Artificial Intelligence: A Modern Approach, 4th ed.: the logical-agents chapter (Wumpus World, forward chaining, model checking) and the probabilistic Wumpus discussion in the uncertainty chapters. Check section numbers in your edition.
