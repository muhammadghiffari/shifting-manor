# Changelog

All notable changes to **Shifting Manor** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-24

### Added
- **Deterministic Shifting-Wing Game Engine (`shifting_manor.engine`)**: Seeded 4×4 (`apprentice`) and 6×6 (`explorer`, `haunted`) manor generation, sensory percepts (`Breeze`, `Chill`, `Glimmer`, `Scream`, `Rumble`), Charm banishment, scoring, oil budget, and 90° rotating 3×3 wings carrying hidden hazards and player marks while keeping the Heirloom fixed.
- **24-Rule Forward-Chaining Knowledge Base (`shifting_manor.kb`)**: Explicit rules `R01–R24`, provenance tracking for interactive `Why?` proof trees, exact `R16` knowledge transport across wing rotations, and exact weighted model enumeration.
- **7 Comparable Agents & Empirical Benchmark Suite (`shifting_manor.agents`, `shifting_manor.sim`, `tools/audit.py`)**: `B0` Random, `B1` Reactive, `B2` Shift-Blind, `B2b` Forgetful, `B3` Caretaker (full KB + R16), `B4` Oracle, and `B5` Exact Bayesian Posterior. Audited over 3,000 seeds with 0 avoidable losses and +16.5 pp Haunted win-rate gain over Shift-Blind (`p = 6.3e-8`).
- **Interactive Desktop & WebAssembly UI (`shifting_manor.ui`, `web/`)**:
  - Manual Play with flickering radial lantern fog-of-war, right-click room marks, explicit Entrance `(0,0)` escape, and fair zero-cheating AI Hint (`I`).
  - **Live Autonomous AI Play (`--auto`)** running real agents turn-by-turn with instant mid-game Takeover / AI Auto-Play (`T`), belief overlay (`B`), streaming forward-chaining log, and `Why?` proof trees.
  - **Human vs AI Duel (`--duel`)**, **4-Lesson Interactive Tutorial (`--tutorial`)**, **4-Tab Field Guide (`H`)**, **Watch AI Trace Inspector (`V`)**, **Simulation Lab (`F2`)**, **Settings (`O`)**, procedural gothic audio, and Run Card PNG export (`S`).
- **Free Browser Play via WebAssembly & GitHub Pages (`tools/build_web.py`, `.github/workflows/pages.yml`)**: Automated pygbag WebAssembly build, game-native landing page (`web/landing.html`) with live interactive 2×2 wing diorama and 3×3 R16 shift sandbox, custom gothic lantern vector emblem (`web/logo.svg`), and multi-format favicons (`logo.svg`, `favicon.png`, `favicon.ico`).
