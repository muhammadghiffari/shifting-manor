# DECISIONS

Record every choice made between options (date, question, choice, reason). Newest first.

| Date | Question | Decision | Reason |
|---|---|---|---|
| 2026-10-22 | Engine for the game UI | pygame-ce | One language (Python), good animation/audio support, easy to demo offline |
| 2026-10-22 | Core AI approach | Forward chaining + exact enumeration + A* | Meets the brief (rule-based, forward chaining) and is stronger than forward chaining alone; see docs/ALGORITHMS.md |
| 2026-10-22 | RL | Optional, after M5 only | Brief does not require it; see PRD Section 16 |
| 2026-10-22 | Repo visibility | Private initially | Owners decide on publishing after the lecturer policy is checked |
| 2026-10-22 | Code license | MIT | Simple, permissive; assets are licensed per file |
