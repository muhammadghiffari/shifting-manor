# Shifting Manor

A haunted-manor deduction game in the spirit of Wumpus World, played by humans and by a rule-based, forward-chaining **Caretaker AI**. Every few moves a wing of the manor rotates, carrying hidden pits and the ghost with it, so the AI has to *transport* what it knows. Built for the Artificial Intelligence course (Week 6, Knowledge): a rule-based expert system with at least 15 IF–THEN rules and forward chaining, in Python.

**Authors:** Muhammad Ghiffari, Radithia Ary Winata · **License:** MIT (code); assets per `assets/CREDITS.md`

## Status

Project skeleton and handover bundle. See `STATUS.md` for what is built.

## Quick start (will work once M0–M4 are done)

```
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m shifting_manor                               # play
python -m shifting_manor.cli --agent b3 --mode explorer --seed HAUNT-4F2A --verbose   # AI trace demo
python -m shifting_manor.sim --runs 200 --out sim/results.json                         # evaluation
pytest -q
```

## Docs

| File | What |
|---|---|
| `docs/PRD.md` | Product requirements (game design, UX, AI, scope) |
| `docs/ALGORITHMS.md` | Algorithm choices and why |
| `docs/TEAM_PLAN.md` | Step-by-step plan for the two team members |
| `docs/KICKOFF_PROMPT.md` | Prompt to start the coding agent |
| `AGENT.md` | Build and handover instructions for the coding agent |
| `ASSETS.md` | Full art/audio specification |
| `STATUS.md`, `DECISIONS.md` | Live status and decision log |
