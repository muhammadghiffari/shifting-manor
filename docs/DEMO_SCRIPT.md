# 8-minute demo script

Seed: **HAUNT-4F2A**. Mode: **Explorer**. Agent: **B3** (full R16 transport). Every number below is from the real trace used by Watch AI.

## Before the timer starts

From the repo root, with the virtual environment active:

```
python -m shifting_manor --windowed --seed HAUNT-4F2A
```

- Window title: `Shifting Manor`.
- If the window is fullscreen, press `F11`.
- Do not launch with `--demo` for the live version; use the menu so the audience sees the entry point. Keep a terminal ready with the fallback commands below.

Optional pre-flight:

```
python -m shifting_manor --windowed --no-audio --frames 30
python -m shifting_manor --demo --windowed --seed HAUNT-4F2A
```

The second command is the fallback/recording mode: it starts Watch AI immediately and loops HAUNT-4F2A → HAUNT-7C1D → HAUNT-5D7C with a 3-second pause between traces.

## 0:00–0:45 — What the project is

Say:

> This is Shifting Manor. The player has to find the heirloom and leave before the lantern oil runs out. Every eight actions a wing of the manor rotates, so a room that was safe can become dangerous. The AI is a knowledge-based agent: it keeps a knowledge base, fires IF–THEN rules forward, turns the remaining uncertainty into exact probabilities, and plans with A*. It is not a neural network and it is not trained with reinforcement learning.

Point at the title screen, then press **Enter** to reach mode select.

## 0:45–1:30 — Mode select and the WATCH AI entry

On **CHOOSE YOUR NIGHT**:

1. Leave **Explorer** selected (Up/Down or click the card).
2. Point at **AGENT: B3 [A]**. Say: “The picker offers B3, B2 and B2b. B3 is the default because it is the only variant that transports beliefs through a rotation.”
3. Click **WATCH AI [V]** (or press `V`).

Say:

> The agent plays by itself. The board is the state at the start of each stored turn; the panel on the right is what the KB actually concluded. This is a replay of one real run, not an animation written by hand.

## 1:30–2:45 — Autoplay and the live delta log

Watch the first turns at 1x. Then:

- Press `+` to go to **2x**. Press `+` again for **4x**. Press `-` to go back.
- Press **Space** to pause, **Space** again to resume.
- Press **Right** to step one turn at a time.

Say:

> The log shows only firings that produced a new fact. Re-derived R08 and R17 lines are deliberately hidden; otherwise the panel would repeat the same “safe” conclusions every turn. The gold outline on the board marks the cells touched by the newest line.

Press **L** or click **INFERENCE LOG**. Scroll with the wheel if needed.

> Each line has the shape `R07 Constraint(GHOST,...) => Ghost(2,2)`. That is the rule id, the premises it matched, and the conclusion it added. The trace is stored before the action, so the position and percepts on screen are the ones the agent used for that decision.

## 2:45–4:15 — The deduction to explain: Ghost at T13

Pause when the header reads **TURN 14 / 34**. This is the KB's 0-based T13; the UI adds one.

1. Click the room **(2,2)** (third column from the left, third row from the bottom).
2. Press **W** if the proof tree is not already open.
3. Read the tree from the bottom up:

```
Ghost(2,2)                              R07, one candidate left
└── GHOST{(1,1),(2,0),(2,2),(4,2)}      R16 shift #1
    ├── Rotated(1, cw)                   event, T08
    └── GHOST{(1,1),(2,0),(2,2),(3,1)}  R05, Chill(2,1)
        └── Chill(2,1)                   percept, T07
```

Say:

> At T07 the agent felt a chill at (2,1). R05 does not guess the ghost's room; it stores four candidates. At T08 the first wing rotates clockwise. R16 moves the candidate at (3,1) to (4,2), and moves the NoPit belief with it. At T13 the agent feels no chill at (4,1), so R03 gives NoGhost(4,2). Now only (2,2) is left in the transported constraint, so R07 concludes Ghost(2,2). The R16 transport is the step that keeps the old constraint aligned with the rotated manor.

Press **Esc** to close the proof. If someone asks why the UI says TURN 14: “The KB's `Firing.turn` is 0-based; the UI adds one for humans.”

## 4:15–5:15 — The shift moment and the belief overlay

1. Press **R** to restart the trace, then pause at **TURN 9 / 34** (the first shift).
2. Wait for the gold dashed wing and the label **SHIFT #1 · SE CW**.
3. Press **B** twice: off, then on. Leave it on.

Say:

> Solid marks are certain: safe, pit or ghost. Translucent cells with a percentage are risk beliefs from exact enumeration; the percentage is the combined pit-or-ghost risk. The gold dashed outlines are beliefs that were transported through the rotation. A dashed outline is not “unknown”; it means this room's belief moved with the wing.

Point at the **R16 Rotated(1, cw) => …** line.

> R16 is not a normal rule match. It is event-driven. It rewrites the PIT and GHOST constraints and the cell facts atomically, logs the rotation as its premise, and counts in the KB tab. Each moved item keeps a provenance edge back to the old one, so this proof tree can be reconstructed later.

## 5:15–6:00 — Rules tab

Click **RULES**.

- Scroll to R07, R16, R20.
- Click R07 to highlight the cells of its last firing.

Say:

> All 24 rules are separate objects, in a fixed priority order R01 to R24. The chainer runs passes until a full pass adds nothing. That is forward chaining: data first, then rules, then new data. There is no goal stack and no backward search.

## 6:00–6:45 — Charm at T17 and the end

Press **Esc** to leave the rules tab/proof, then step to **TURN 18 / 34** (KB T17). If you restarted, use Right or let it play.

Say:

> The ghost is still at (2,2). The agent is at (5,2), on the same row. R20 checks whether the ghost is in a straight line and sets CharmAction to West. The agent casts west, the ghost is banished, and the route collects the heirloom at (5,4) and returns to the entrance. The run ends escaped with treasure, 34 actions, 1157 points.

Let the trace finish. The last frame says **END OF TRACE**; in `--demo` mode it waits three seconds and starts the next seed.

## 6:45–7:30 — Evaluation, honestly

Switch to the terminal or show `docs/EVALUATION.md`.

Say:

> The 200-seed run is in `sim/results.json`. B3 escapes with the heirloom 91.5% of the time on Explorer and 82.5% on Haunted. B2 is 77.5% and 66.0%. The paired McNemar tests are p = 1.8e-6 and 6.3e-8, so the B3-vs-B2 gap is clear. B2b is 83.5% and 69.0%, but its paired test against B2 is p = 0.052 on Explorer and 0.377 on Haunted — we do not claim it is better from 200 seeds. The confidence intervals and the exact command are in `docs/EVALUATION.md`.

If asked “why only 200?”:

> The CIs are in the table. 200 is enough to show the B3 gap; it is not enough to resolve a small B2b effect. The honest result is “not distinguishable here”, not “no effect”.

## 7:30–8:00 — Limits and close

Say:

> The AI is not omniscient. It does not use the hidden map except in the oracle baseline. When no safe unvisited room exists, R22 takes the best risk-weighted gamble, and the sim reports the forced-guess rate instead of hiding it. The M5 scope is Watch AI; Duel, SimLab, the tutorial, KB heat bars, step-back and the log-filter UI are explicitly not done.

Close with:

> The core claim is simple: 24 readable rules, a forward chainer, exact enumeration and A* produce a demo you can explain line by line, and the comparison against the shift-blind agent is statistically clear.

## Fallbacks

### A. The GUI will not start (projector, SDL, fonts)

Use the headless CLI trace. It runs the same game and the same agent:

```
python -m shifting_manor.cli --agent b3 --mode explorer --seed HAUNT-4F2A --verbose
```

To jump straight to the important part, save it and show the section:

```
python -m shifting_manor.cli --agent b3 --mode explorer --seed HAUNT-4F2A --verbose > /tmp/haunt_trace.txt
sed -n '/^T07/,/^T14/p' /tmp/haunt_trace.txt
```

The CLI prints `T07` … `T13` with the same rule ids and conclusions. It also prints the `R16 Rotated(1, cw) => ...` line. The turn numbers there are 0-based, matching the KB.

### B. The GUI is too slow or a click is missed

Use the screenshots in `docs/screens/`:

- `watch_ai_overlay.png` — belief overlay and the live trace at TURN 14.
- `watch_ai_log.png` — inference log, new firings only.
- `watch_ai_why.png` — the Ghost(2,2) proof tree with the R16 hop and `Rotated(1, cw)` leaf.
- `watch_ai_kb.png` — the rules tab.
- `watch_ai_shift_moment.png` — the first shift, dashed transported beliefs.

Open them in any image viewer. The proof screenshot already contains the chain, so the explanation does not depend on live clicking.

### C. The live demo is completely unavailable (no machine, no GUI)

Use a previously recorded 90-second screen capture if one exists. If there is no recording, present the screenshots in the order above and use the CLI trace as the live evidence. Do not claim a video exists if it does not.

### D. The demo loop is needed unattended

```
python -m shifting_manor --demo --windowed --seed HAUNT-4F2A
```

This starts on HAUNT-4F2A, then loops HAUNT-7C1D and HAUNT-5D7C after three seconds on the end frame. Press `Esc` to leave the loop and return to mode select.

## Exact key map (for the presenter)

| Key | Action |
|---|---|
| `Space` | play/pause; at the end, restart |
| `Right` | finish this step, then go to the next |
| `+` / `-` | cycle 1x → 2x → 4x / 4x → 2x → 1x |
| `B` | belief overlay on/off |
| `W` | Why? for the hovered/clicked room |
| `L` / `K` | inference log / rules tab |
| `Tab` | cycle tabs |
| `R` | restart the trace |
| `Esc` | close proof, otherwise back to mode select |
