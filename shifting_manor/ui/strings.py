"""Every user-facing string lives here so the UI can be reworded in one place."""

from __future__ import annotations

TITLE = "SHIFTING MANOR"
TAGLINE = "A deduction game about a house that will not sit still."
PRESS_ENTER = "Press Enter or click to begin"
TITLE_HINT = "Arrow keys / WASD move  ·  C + direction charms  ·  Right-click marks"

MODE_TITLE = "CHOOSE YOUR NIGHT"
MODE_HINT = "Up/Down select  ·  Enter begin  ·  N new seed  ·  Esc back"
MODE_BEGIN = "BEGIN"
MODE_WATCH = "WATCH AI [V]"
MODE_AGENT = "AGENT"
MODE_AGENT_HINT = "A cycles the agent · V watches"

WATCH_TITLE = "WATCH AI"
WATCH_REPLAY = "Replaying the agent's actual trace"
WATCH_TRACE_TAB = "TRACE"
WATCH_LOG_TAB = "INFERENCE LOG"
WATCH_KB_TAB = "KNOWLEDGE BASE"
WATCH_STEP = "TURN {step} / {total}"
WATCH_SPEED = "SPEED {speed:.1f}x"
WATCH_TRACE_HINT = "Space play/pause · → step · +/- speed · B overlay · W why · Esc menu"
WATCH_THOUGHT = "THOUGHT"
WATCH_PERCEPTS = "PERCEPTS"
WATCH_GAMBLES = "R22 CANDIDATES"
WATCH_NO_GAMBLE = "No gamble this turn."
WATCH_LOG_NEW = "NEW ONLY"
WATCH_LOG_ALL = "ALL"
WATCH_LOG_EMPTY = "No firings yet."
WATCH_KB_HINT = "Click a rule to highlight its last firing."
WATCH_KB_COUNTS = "first derivations"
WATCH_WHY_TITLE = "WHY? · PROOF TREE"
WATCH_WHY_HINT = "Click a premise to follow it · Esc closes"
WATCH_WHY_EMPTY = "No derivation for this room yet."
WATCH_SHIFT = "SHIFT #{n} · {wing} {direction}"
WATCH_OVERLAY_ON = "BELIEF ON [B]"
WATCH_OVERLAY_OFF = "BELIEF OFF [B]"
WATCH_END = "END OF TRACE"
WATCH_RESTART = "R restart"
WATCH_SELECT = "Click a room to ask why"
WATCH_RISK = "risk {risk:.0f}% · pit {pit:.0f}% · ghost {ghost:.0f}%"
WATCH_RULE_LAST = "last turn {turn}"

MODE_BLURB = {
    "apprentice": "4×4 · 2 pits · 40 oil · no shifts\nLearn the lantern.",
    "explorer": "6×6 · 4 pits · 80 oil · shift every 8\nA fair haunting.",
    "haunted": "6×6 · 5 pits · 70 oil · shift every 5\nThe house is hungry.",
}

HUD_OIL = "OIL"
HUD_SCORE = "SCORE"
HUD_CHARM = "CHARM"
HUD_CHARM_READY = "ready"
HUD_CHARM_SPENT = "spent"
HUD_HEIRLOOM = "HEIRLOOM"
HUD_HEIRLOOM_HELD = "carried"
HUD_HEIRLOOM_LOST = "unfound"
HUD_SEED = "SEED"
HUD_SHIFT = "SHIFT CLOCK"
HUD_SHIFT_STEADY = "steady"
HUD_SHIFT_EVERY = "every {k} actions"
HUD_SHIFT_SOON = "in {n} actions"
HUD_POSITION = "room ({x}, {y})"

SENSES_TITLE = "SENSES"
SENSE_BREEZE = "A cold draft slips through the floor."
SENSE_CHILL = "Something is watching you."
SENSE_GLIMMER = "Something gleams close by."
SENSE_RUMBLE = "The manor shifts in {n}…"
SENSE_SCREAM = "A shriek; the ghost is gone."
SENSE_BUMP = "A wall. The house does not move for you."
SENSE_QUIET = "Nothing stirs."

LEGEND_TITLE = "MARKS & CONTROLS"
LEGEND_SAFE = "safe"
LEGEND_PIT = "pit"
LEGEND_GHOST = "ghost"
LEGEND_UNKNOWN = "suspect"
CONTROLS = [
    "Move: arrows / WASD / click a neighbour",
    "Charm: C then arrow or click a direction",
    "Mark: right-click cycles · 1–4 current room",
    "R restart · N new seed · Esc pause",
]

PAUSED = "PAUSED"
PAUSE_HINT = "Esc resume · R restart · M menu · Q quit"

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
RESULT_SCORE = "SCORE"
RESULT_ACTIONS = "Actions"
RESULT_OIL = "Oil left"
RESULT_CHARMS = "Charms"
RESULT_RULES = "Marks placed"
RESULT_STARS = "Stars"
RESULT_SEED = "Seed"
RESULT_MODE = "Mode"
RESULT_HINT = "Click a button, or use the key in brackets."

CONFIRM_QUIT = "Q quits from the title, pause or result screen."
