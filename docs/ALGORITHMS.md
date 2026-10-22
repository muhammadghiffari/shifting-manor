# Algorithms and why we chose them

Audience: the two team members, the lecturer, and the coding agent. Short on theory, long on reasons.

## 1. The stack at a glance

| Layer | Algorithm | Role |
|---|---|---|
| 1 | Forward chaining over IF–THEN rules (R01–R24) | The expert system proper. Required by the brief. Produces every explanation the UI shows |
| 2 | Exact model enumeration over frontier cells | Finds conclusions the rules miss, and gives exact risk numbers |
| 3 | A* with risk-weighted edge cost | Moves safely and economically |
| 4 | Expected-utility choice among gambles | Decides what to do when nothing is certainly safe |
| 5 | Knowledge transport (R16) | Keeps beliefs correct when a wing rotates |

RL, minimax and MCTS are deliberately not in the core. See Section 6.

## 2. Forward chaining

Data-driven inference: start from known facts, fire every rule whose premises hold, add its conclusions, repeat until no new fact appears (the fixpoint).

```
function FORWARD_CHAIN(kb, rules):
    log = []
    repeat
        new = false
        for rule in rules (fixed priority order):
            for binding in rule.matches(kb):
                for fact in rule.conclusions(binding):
                    if fact not in kb:
                        kb.add(fact)
                        log.append(Firing(rule.id, binding.premises, [fact], turn))
                        new = true
    until not new
    return log
```

**Why forward and not backward:** in this game the percepts arrive one at a time and we want everything that follows from them immediately (which neighbours are safe now?). Backward chaining answers a single query ("is cell X safe?") and would be re-run per cell. Forward chaining also gives the natural trace "percept → rule → new fact" that the Inference Log and the Why? button show.

**Properties:** sound (only valid conclusions, if the rules are valid); terminates because the set of possible facts is finite; each pass is cheap on a 6×6 board.

**Limit:** rules with "at least one of these cells" clues (disjunctions) do not always resolve by simple matching. Example: Breeze at A says a pit is in {1,2}; Breeze at B says a pit is in {2,3}; with only one pit left, the pit must be at 2. That needs case analysis. Hence Layer 2.

## 3. Exact model enumeration (model checking)

A *world* assigns pits (and the ghost) to the frontier cells: those that appear in any constraint set and are not already decided. A world is *consistent* if it satisfies every NoX fact, every constraint (at least one hazard in each set), the total pit count, and the single-ghost rule.

```
function ENUMERATE(frontier, constraints, facts, pits_left, U):
    worlds = []
    for each assignment of pit/no-pit to frontier cells (backtracking, prune early):
        if consistent(assignment):
            k = number of pits in assignment
            if k <= pits_left and (pits_left - k) <= U:
                weight = C(U, pits_left - k)       # ways to place the rest among the other unknown cells
                worlds.append((assignment, weight))
    return worlds

entailed(Pit(c))    iff c has a pit in every world
entailed(NoPit(c))  iff c has no pit in any world
risk(c) = sum(weight of worlds with a pit at c) / sum(weight of all worlds)
```

For non-frontier unknown cells the risk is `E[pits_left - k] / U` over the weighted worlds.

**Why exact:** with at most 14 frontier cells there are at most 16,384 assignments, and backtracking prunes most of them. Exactness means the agent never takes a risk it could have excluded, and the risk numbers are trustworthy enough to show to the lecturer.

**Why this and not SAT/DPLL:** DPLL finds the same entailments, but we also want probabilities, and enumeration yields both from one computation. At this size simplicity wins. If the frontier is larger than 14 cells, fall back to an independence approximation and log it.

**Why weights `C(U, pits_left - k)`:** the pit total is known, so pits are not independent. A world that uses more pits on the frontier leaves fewer to spread over other cells; the binomial counts exactly how many full-board worlds each frontier assignment represents.

**Cross-check test:** every fact produced by forward chaining must be entailed by the enumeration. This catches wrong rules.

## 4. Movement and decisions

**A* with risk-aware cost.** Edge cost into cell c = `1 + lambda * (-ln(1 - risk(c)))`. Summing `-ln(1-p)` along a path is the same as maximising the product of survival probabilities, so A* returns the route with the best trade-off between oil used and survival. Heuristic = Manhattan distance, which never overestimates the oil cost, so A* stays optimal. Known-unsafe cells are impassable.

**Gamble choice (rule R22).** When no cell is certainly safe and the treasure is not reachable, choose the frontier cell maximising

```
utility(c) = -1000 * risk(c) - path_cost(c) + 0.5 * unknown_neighbours(c)
```

The last term is a cheap proxy for information value (a room with many unknown neighbours reveals more). Exact expected entropy reduction is an optional upgrade. Ties: shorter distance, then deterministic cell order.

**Retreat (R23).** If remaining oil is within a small margin of the safest return path, go home.

## 5. Knowledge transport (R16)

When a wing rotates by a known mapping `m: cell -> cell` (the wing's rotation), every stored pit/ghost fact `X(c)` becomes `X(m(c))`, and every pit/ghost constraint set `S` becomes `{m(c) for c in S}`. Treasure facts are untouched because the treasure does not rotate. Nothing is guessed: rotations are deterministic and announced, so beliefs can be moved exactly. The KB records one aggregate R16 firing with `Rotated(wing, direction)` as its premise, plus a per-item provenance edge from each old fact/constraint to its new one.

Two weaker variants exist as baselines to show the value of doing it right: B2 (ignores the shift, so it is confidently wrong) and B2b (forgets the wing, so it is safe but wasteful).

## 6. Why not the alternatives?

| Alternative | Why not the core |
|---|---|
| Reinforcement learning (Q-learning, DQN, PPO) | The brief is about knowledge-based systems. Each game is a new random map with partial observability, so learning needs hand-built state features and many episodes, and the result is opaque. An exact reasoner already exists at this scale. RL stays an optional meta-policy after M5 |
| Minimax / alpha-beta | For adversarial games. The manor is not an opponent; hazards do not react to the player |
| MCTS / POMCP | A strong general POMDP method, but heavy, stochastic, and hard to explain. Overkill when exact enumeration is feasible |
| Pure backward chaining | Re-runs per query; weaker live trace |
| Pure BFS planning | Ignores risk |

## 7. Honest limits

- Not provably optimal. The optimal policy would solve the full POMDP. Ours is sound logic plus greedy expected-utility choices.
- Some maps force a guess. No agent can avoid that. We report the forced-guess rate.
- The 14-cell cap is a practical limit; the 6×6 board rarely reaches it.
- We therefore measure: B0 random, B1 reactive, B2 shift-blind, B2b forgetful, B3 full, B4 oracle (sees the map; upper bound).

## 8. Reference

Russell & Norvig, *Artificial Intelligence: A Modern Approach*, 4th ed. (logical agents and the Wumpus World; the probabilistic treatment of the Wumpus World in the uncertainty chapters). Check chapter and section numbers in your edition.
