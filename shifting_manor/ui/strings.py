"""Every user-facing string lives here so the UI can be reworded in one place."""

from __future__ import annotations

TITLE = "SHIFTING MANOR"
TAGLINE = "A haunted-house deduction game where the rooms remember — even when wings rotate."
PRESS_ENTER = "Press Enter or click PLAY to begin"
TITLE_HINT = "Play manually, watch a real AI agent play live autonomously, or duel head-to-head."
TITLE_BUILD = "End-to-End Interactive Edition · Manual · Live Autonomous AI · Duel · SimLab"

TITLE_BTN_PLAY = "PLAY MANUALLY"
TITLE_BTN_PLAY_SUB = "Explore & deduce [Enter]"
TITLE_BTN_AUTO = "LIVE AI AGENT"
TITLE_BTN_AUTO_SUB = "Real agent plays live [A]"
TITLE_BTN_DUEL = "DUEL vs AI"
TITLE_BTN_DUEL_SUB = "Same seed showdown [D]"
TITLE_BTN_TUTORIAL = "TUTORIAL & GUIDE"
TITLE_BTN_TUTORIAL_SUB = "Learn how to play [H]"
TITLE_BTN_WATCH = "TRACE INSPECTOR [V]"
TITLE_BTN_SIMLAB = "SIM LAB [F2]"
TITLE_BTN_SETTINGS = "SETTINGS [O]"

MODE_TITLE = "CHOOSE YOUR NIGHT"
MODE_HINT = "1-3 difficulty · A cycle agent · Click seed to edit · N random seed · Esc back"
MODE_BEGIN = "PLAY MANUAL [Enter]"
MODE_LIVE_AI = "LIVE AI PLAY [L]"
MODE_DUEL = "DUEL vs AI [D]"
MODE_WATCH = "TRACE VIEW [V]"
MODE_GUIDE = "HOW TO PLAY [H]"
MODE_AGENT = "AI AGENT"
MODE_AGENT_HINT = "A cycles agent · L live autonomous play · V trace proof inspector"

AGENT_LABELS = {
    "b3": "B3 · Caretaker AI (Full KB + R16 Transport)",
    "b5": "B5 · Exact Bayesian KB (Optimal Posterior)",
    "b2b": "B2b · Forgetful KB (Drops Rotated Wing)",
    "b2": "B2 · Shift-Blind KB (Ignores Rotations)",
    "b1": "B1 · Reactive Agent (No Memory)",
    "b0": "B0 · Random Explorer (Baseline)",
    "b4": "B4 · Oracle (Full Map Upper Bound)",
}

AGENT_SHORT = {
    "b3": "B3 Caretaker",
    "b5": "B5 Exact",
    "b2b": "B2b Forgetful",
    "b2": "B2 Shift-Blind",
    "b1": "B1 Reactive",
    "b0": "B0 Random",
    "b4": "B4 Oracle",
}

WATCH_TITLE = "WATCH AI · TRACE INSPECTOR"
WATCH_REPLAY = "Frozen proof-tree trace of the real agent"
WATCH_TRACE_TAB = "TRACE"
WATCH_LOG_TAB = "INFERENCE LOG"
WATCH_KB_TAB = "KNOWLEDGE BASE"
WATCH_STEP = "TURN {step} / {total}"
WATCH_SPEED = "SPEED {speed:.1f}x"
WATCH_TRACE_HINT = "Space play/pause · Left/Right step · +/- speed · B beliefs · W why · Esc menu"
WATCH_THOUGHT = "AGENT THOUGHT"
WATCH_PERCEPTS = "PERCEPTS"
WATCH_GAMBLES = "R22 RISK CANDIDATES"
WATCH_NO_GAMBLE = "No forced gamble this turn — safe deduction available."
WATCH_LOG_NEW = "NEW ONLY"
WATCH_LOG_ALL = "ALL FIRINGS"
WATCH_LOG_EMPTY = "No firings yet."
WATCH_KB_HINT = "Click any rule to highlight its last firing on the board."
WATCH_KB_COUNTS = "first derivations"
WATCH_WHY_TITLE = "WHY? · PROOF TREE"
WATCH_WHY_HINT = "Click a premise to expand · Esc closes"
WATCH_WHY_EMPTY = "No derivation for this room yet."
WATCH_SHIFT = "SHIFT #{n} · {wing} {direction}"
WATCH_OVERLAY_ON = "BELIEF ON [B]"
WATCH_OVERLAY_OFF = "BELIEF OFF [B]"
WATCH_END = "END OF TRACE · Press R to replay or Esc for menu"
WATCH_RESTART = "R restart"
WATCH_SELECT = "Click any room or log line to inspect its proof tree"
WATCH_RISK = "risk {risk:.0f}% · pit {pit:.0f}% · ghost {ghost:.0f}%"
WATCH_RULE_LAST = "last turn {turn}"

MODE_BLURB = {
    "apprentice": "4×4 · 2 pits · 40 oil · no shifts\nBest for your first run. Learn senses & deduction.",
    "explorer": "6×6 · 4 pits · 80 oil · shift every 8\nWings rotate! Transport your notes & beliefs.",
    "haunted": "6×6 · 5 pits · 70 oil · shift every 5\nFast shifts, tight oil. True deduction test.",
}

HUD_OIL = "LANTERN OIL"
HUD_SCORE = "SCORE"
HUD_CHARM = "CHARM"
HUD_CHARM_READY = "READY [C]"
HUD_CHARM_SPENT = "SPENT"
HUD_HEIRLOOM = "HEIRLOOM"
HUD_HEIRLOOM_HELD = "CARRIED — GO TO (0,0)!"
HUD_HEIRLOOM_LOST = "UNFOUND"
HUD_SEED = "SEED"
HUD_SHIFT = "SHIFT CLOCK"
HUD_SHIFT_STEADY = "STEADY"
HUD_SHIFT_EVERY = "every {k} moves"
HUD_SHIFT_SOON = "in {n} moves"
HUD_POSITION = "room ({x}, {y})"

PLAY_LEAVE_BTN = "LEAVE MANOR [E]"
PLAY_AUTO_ON = "AI PLAYING [T]"
PLAY_AUTO_OFF = "AI AUTO-PLAY [T]"
PLAY_HINT_BTN = "AI HINT [I]"
PLAY_GUIDE_BTN = "GUIDE [H]"
PLAY_BELIEF_ON = "BELIEFS ON [B]"
PLAY_BELIEF_OFF = "BELIEFS OFF [B]"
PLAY_TAKE_OVER = "TAKE CONTROL [T]"

SENSES_TITLE = "CURRENT ROOM SENSES"
SENSE_BREEZE = "BREEZE — A hidden Pit is in an adjacent room."
SENSE_CHILL = "CHILL — The Ghost lurks in an adjacent room."
SENSE_GLIMMER = "GLIMMER — The Heirloom is here or in a neighbour!"
SENSE_RUMBLE = "RUMBLE — Wing {wing} rotates {dir} in {n} move(s)!"
SENSE_SCREAM = "SCREAM — Your charm banished the Ghost! (+200)"
SENSE_BUMP = "BUMP — Solid wall. No oil spent."
SENSE_QUIET = "QUIET — No Breeze or Chill. All 4 neighbours are SAFE!"

LEGEND_TITLE = "MARKS & QUICK ACTIONS"
LEGEND_SAFE = "safe [4]"
LEGEND_PIT = "pit [2]"
LEGEND_GHOST = "ghost [3]"
LEGEND_UNKNOWN = "suspect [1]"
CONTROLS = [
    "Move: WASD / Arrows / Click glowing neighbour",
    "Escape: Stand on golden Entrance (0,0) & press E",
    "Charm: Press C (or click Charm), then pick direction",
    "Notes: Right-click any room · 1-4 mark · 0 clear",
    "Assist: [I] AI Hint · [T] Let Real AI Play · [H] Guide",
]

COACH_START = (
    "STEP 1: Move with WASD / Arrows / Click a neighbour. Quiet rooms prove all 4 neighbours SAFE!"
)
COACH_BREEZE = "BREEZE! At least one adjacent room has a Pit. Right-click rooms to mark notes."
COACH_CHILL = (
    "CHILL! The Ghost is adjacent. Deduce its room, then press C + direction to banish it!"
)
COACH_GLIMMER = "GLIMMER! The golden Heirloom is adjacent (or here). Explore safely to grab it!"
COACH_RUMBLE = "RUMBLE! Wing {wing} rotates {dir} in {n}. Stand inside a wing to stop its shift!"
COACH_CARRYING = "HEIRLOOM FOUND! Return safely to the golden Entrance (0,0) and press E to escape!"
COACH_AT_EXIT = "AT ENTRANCE WITH HEIRLOOM! Press [E] or click LEAVE MANOR to win the night!"
COACH_OIL_LOW = (
    "LANTERN OIL LOW ({oil} left)! Head toward Entrance (0,0) before darkness takes you!"
)
COACH_LIVE_AI = (
    "LIVE AUTONOMOUS AGENT ({agent}) is playing this real game! Space pause · T take over"
)

PAUSED = "PAUSED"
PAUSE_HINT = "Esc resume · H guide · O settings · R restart · M menu · Q quit"

RESULT_TITLE = "THE NIGHT ENDS"
RESULT_OUTCOME = {
    "escaped_treasure": "ESCAPED WITH THE HEIRLOOM",
    "escaped_empty": "ESCAPED EMPTY-HANDED",
    "died_pit": "THE PIT TOOK YOU",
    "died_ghost": "THE GHOST TOOK YOU",
    "oil_out": "THE LANTERN DIED",
    "stalled": "THE NIGHT STALLED",
}
RESULT_REPLAY = "REPLAY [R]"
RESULT_NEW = "NEW SEED [N]"
RESULT_MENU = "MENU [M]"
RESULT_WATCH_AI = "LIVE AI ON SEED [L]"
RESULT_SAVE_CARD = "SAVE CARD [S]"
RESULT_SCORE = "SCORE"
RESULT_ACTIONS = "Actions taken"
RESULT_OIL = "Oil left"
RESULT_CHARMS = "Charms cast"
RESULT_RULES = "Marks / Rules"
RESULT_STARS = "Stars (vs Oracle par)"
RESULT_SEED = "Seed"
RESULT_MODE = "Mode"
RESULT_HINT = "Click a button or press the key in brackets. Hover map cells to inspect."

DUEL_TITLE = "DUEL SHOWDOWN · HUMAN vs CARETAKER AI"
DUEL_NEXT_AI = "START AI TURN [Enter]"
DUEL_SKIP_AI = "FAST-FINISH [F]"
DUEL_WIN_HUMAN = "VICTORY! YOU BEAT THE CARETAKER AI!"
DUEL_WIN_AI = "THE CARETAKER AI WINS THIS SEED!"
DUEL_TIE = "DEAD HEAT! EXACT TIE!"

SIMLAB_TITLE = "SIMULATION LAB · EMPIRICAL EVIDENCE"
SIMLAB_SUBTITLE = "200 same-seed games per mode · Does R16 knowledge transport actually matter?"
SIMLAB_HINT = "1-3 mode · Tab metric · B run live 30-seed check · Esc back"

SETTINGS_TITLE = "SETTINGS & ACCESSIBILITY"
SETTINGS_HINT = "Adjust audio, motion, contrast & hints · Esc closes"

GUIDE_TITLE = "HOW TO PLAY · CARETAKER'S FIELD GUIDE"
GUIDE_HINT = "Left/Right switch page · T start interactive tutorial · Esc close"

CONFIRM_QUIT = "Q quits from the title, pause or result screen."
