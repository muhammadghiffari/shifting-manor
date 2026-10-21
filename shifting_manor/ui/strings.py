"""Every user-facing string lives here so the UI can be reworded in one place."""

from __future__ import annotations

TITLE = "SHIFTING MANOR"
TAGLINE = "A deduction game about a house that will not sit still."
PRESS_ENTER = "Press Enter or click to begin"
TITLE_HINT = "Arrow keys / WASD move  ·  C + direction charms  ·  Right-click marks"

MODE_TITLE = "CHOOSE YOUR NIGHT"
MODE_HINT = "Up/Down select  ·  Enter begin  ·  N new seed  ·  Esc back"
MODE_BEGIN = "BEGIN"

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
