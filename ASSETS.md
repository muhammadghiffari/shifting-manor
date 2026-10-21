# ASSETS.md — Shifting Manor Asset Specification (for Astra)

Everything the game needs, with exact sizes, frame counts, names and priorities. File names (without extension) are the manifest keys the code uses, so please keep them exactly. If something is not produced, the game falls back to placeholders, so work in priority order: **P0 → P1 → P2**.

## 1. Style bible

- **Mood:** gothic haunted manor at night, cosy-creepy rather than gory. Warm lantern light against cold blue-violet darkness. No blood, no gore. Ghost is eerie but a little cute, readable at small size.
- **Look:** top-down 3/4 view pixel art, hand-pixelled feel, 1 px dark selective outlines, limited palette, soft dithering allowed in shadows.
- **Native tile size:** 32x32 px. The game renders at integer scale x3 (a room is 96 px on screen). Do not anti-alias or blur; use nearest-neighbour exports.
- **Light direction:** warm light from the player's lantern, so objects have warm highlights on the side facing the player and cool shadows opposite.
- **Readability rules:** hazards must read at a glance without colour (shape first). All status icons use **shape + colour** (colour-blind safe).

### Palette (use these, add shades only if needed)

| Role | Hex |
|---|---|
| Night base | #0E0B14 |
| Deep shadow | #1B1626 |
| Stone dark / mid / light | #3A3347 / #5B5470 / #8A8299 |
| Lantern warm / hot | #FFB347 / #FF7A2F |
| Gold (treasure) | #F2C14E |
| Safe (teal) | #3DD6C3 |
| Danger (orange-red) | #FF6B4A |
| Suspect (violet) | #8C7CFF |
| Stale (muted yellow) | #C9B458 |
| Ghost (pale cyan) | #9BE7FF |
| Miasma green | #8FD14F |
| Cold wind blue | #6FA8FF |
| Parchment (UI) | #E8D9B5 |
| Wood/ink (UI) | #2A1F1A |

### Shared AI-generation prompt prefix (if Astra uses a generator)

> pixel art, 32x32 sprite, top-down 3/4 view, gothic haunted manor, dark violet night palette with warm orange lantern light, 1px dark outline, limited palette, clean pixels, no anti-aliasing, transparent background, consistent style with a set

Always generate in sets (same session/seed/style reference), then clean up by hand: consistent outline weight, palette snapped to the table above, no stray semi-transparent pixels.

## 2. Technical delivery rules

- **Images:** PNG-32 with alpha, nearest-neighbour, no compression artefacts. Animations are **horizontal strips**: width = frame width x frame count, height = frame height.
- **Folders:** `assets/sprites/`, `assets/tiles/`, `assets/fx/`, `assets/ui/`, `assets/art/`, `assets/audio/music/`, `assets/audio/sfx/`, `assets/fonts/`.
- **Naming:** `snake_case`, exactly as listed. Variants end in `_01`, `_02`.
- **Audio:** OGG Vorbis, 44.1 kHz. Music stereo q5; SFX mono q4. Loops must be seamless (no click, no tail). Music about -18 LUFS, SFX peak at or below -6 dBFS. Keep each SFX under 200 KB, each music loop under 2.5 MB.
- **Total budget:** under 30 MB for the whole `assets/` folder.
- **Licensing:** original or CC0/permissive only. Provide `assets/CREDITS.md` listing the source, license and author for every non-original file and note which files are AI-generated.

## 3. Tiles and board (32x32 unless stated)

| Key | Size per frame | Frames | Priority | Description |
|---|---|---|---|---|
| floor_stone_01, _02, _03 | 32x32 | 1 each | P0 | Dark stone/wood floor variants, tileable, low contrast so sprites pop |
| floor_visited_overlay | 32x32 | 2 variants | P0 | Faint dust footprints overlay, transparent |
| fog_tile_01, _02 | 32x32 | 1 each | P0 | Opaque near-black tile with subtle noise for unvisited rooms |
| wall_edge_n, wall_edge_s, wall_edge_e, wall_edge_w | 32x32 | 1 each | P0 | Outer manor wall pieces framing the board, tileable along their edge |
| wall_corner_ne, _nw, _se, _sw | 32x32 | 1 each | P0 | Outer wall corners |
| entrance_closed, entrance_open | 32x32 | 1 each | P0 | Front door at (0,0): closed, and open with warm light spilling out |
| wing_rune_edge | 32x32 | 4 (pulse) | P0 | Glowing rune line that marks wing borders, subtle at rest, brighter on the last frame |
| wing_rune_corner | 32x32 | 4 (pulse) | P1 | Matching corner piece |
| floor_cracked_overlay | 32x32 | 2 variants | P2 | Cracks overlay used briefly after a shift |

## 4. Characters and objects (32x32 unless stated)

| Key | Size per frame | Frames | fps | Priority | Description |
|---|---|---|---|---|---|
| caretaker_idle_down, _up, _side | 32x32 | 4 | 6 | P0 | Caretaker with hooded coat and lantern, breathing idle. Right = mirrored side |
| caretaker_walk_down, _up, _side | 32x32 | 6 | 10 | P0 | Walk cycle, lantern swinging |
| caretaker_cast | 32x32 | 5 | 12 | P1 | Raises hand, sigil glows (direction handled in code via the projectile) |
| caretaker_pickup | 32x32 | 5 | 10 | P1 | Reaches down and lifts the heirloom |
| caretaker_death_pit | 32x32 | 8 | 12 | P0 | Falls and shrinks into darkness, lantern tumbles |
| caretaker_death_ghost | 32x32 | 8 | 12 | P1 | Frozen in fright, lantern flame goes out, fades |
| caretaker_victory | 32x32 | 8 | 10 | P1 | Triumphant hop holding the heirloom |
| ghost_idle | 32x32 | 6 | 6 | P0 | Friendly-creepy floating ghost, shows only when revealed |
| ghost_reveal | 32x32 | 6 | 12 | P1 | Fades in with miasma |
| ghost_banish | 32x32 | 10 | 14 | P0 | Spirals into the charm sigil and vanishes |
| ghost_grab | 64x64 | 6 | 12 | P1 | Wide-arm lunge overlay centred on the player room (extends past the tile) |
| pit_hole | 32x32 | 1 | - | P0 | Bottomless dark hole with crumbling rim, drawn only when revealed |
| pit_reveal | 32x32 | 6 | 12 | P1 | Floor cracks and collapses to show the pit |
| heirloom_idle | 32x32 | 8 | 8 | P0 | Gilded locket/chest with a glint travelling across it |
| heirloom_collect | 32x32 | 6 | 12 | P1 | Rises, spins, sparkles |
| charm_projectile | 16x16 | 4 | 14 | P0 | Spinning violet-cyan sigil, drawn horizontal (code rotates it) |
| charm_hit | 32x32 | 8 | 16 | P1 | Burst of light on impact |

## 5. Effects and lighting

| Key | Size | Frames | Priority | Description |
|---|---|---|---|---|
| light_lantern_mask | 512x512 | 1 | P0 | Radial gradient alpha mask (white centre to transparent edge), smooth, used to cut the fog |
| light_glow_warm | 256x256 | 1 | P1 | Warm orange soft glow used under the player and near the entrance |
| vignette_1280x720 | 1280x720 | 1 | P0 | Dark edge vignette, transparent centre |
| overlay_edge_cold | 1280x720 | 1 | P1 | Faint blue edge gradient for Breeze |
| overlay_edge_green | 1280x720 | 1 | P1 | Faint green edge gradient for Chill |
| overlay_edge_gold | 1280x720 | 1 | P1 | Faint gold edge gradient for Glimmer |
| fx_wind_streak | 16x8 | 4 | P0 | Wind streak particle, white-blue |
| fx_miasma | 16x16 | 6 | P0 | Green wisp, loops |
| fx_sparkle | 8x8 | 6 | P0 | Gold twinkle |
| fx_dust_mote | 4x4 | 3 variants | P0 | Tiny dust specks |
| fx_debris | 8x8 | 4 variants | P1 | Stone chips for shifts |
| fx_smoke_puff | 24x24 | 6 | P1 | Dust cloud used while a wing rotates |
| fx_death_poof | 32x32 | 6 | P1 | Soft puff on death |

## 6. Board marks and percept icons

All marks are used for both human notes and AI beliefs. Opacity expresses confidence in code, so draw them fully opaque.

| Key | Size | Frames | Priority | Description |
|---|---|---|---|---|
| mark_safe | 16x16 | 1 | P0 | Teal check mark inside a small rounded square |
| mark_pit | 16x16 | 1 | P0 | Orange-red X inside a ring |
| mark_ghost | 16x16 | 1 | P0 | Pale cyan ghost silhouette |
| mark_suspect | 16x16 | 1 | P0 | Violet question mark |
| mark_stale | 32x32 | 1 | P0 | Dashed muted-yellow outline with a tiny rotation arrow (overlay for transported beliefs) |
| mark_rotate_cw, mark_rotate_ccw | 16x16 | 1 each | P0 | Rotation arrows used on the shift telegraph |
| icon_breeze | 24x24 | 2 (pulse) | P0 | Three curved wind lines, cold blue |
| icon_chill | 24x24 | 2 (pulse) | P0 | Wispy ghost-breath swirl, green |
| icon_glimmer | 24x24 | 2 (pulse) | P0 | Four-point star, gold |
| icon_rumble | 24x24 | 2 (pulse) | P0 | Cracked block with shake lines |
| icon_bump | 24x24 | 1 | P1 | Small impact star on a wall |
| icon_scream | 24x24 | 1 | P1 | Open-mouth ghost with burst lines |
| icon_quiet | 24x24 | 1 | P1 | Calm moon / zzz |

## 7. UI kit

| Key | Size | Notes | Priority |
|---|---|---|---|
| ui_panel_9slice | 48x48, 12 px corners | Dark wood/stone panel, subtle border | P0 |
| ui_panel_parchment_9slice | 48x48, 12 px corners | Parchment panel for text and result screens | P1 |
| ui_button_normal, _hover, _pressed, _disabled (9-slice) | 32x32, 8 px corners | Four states, same silhouette | P0 |
| ui_tab_active, ui_tab_inactive (9-slice) | 32x24, 6 px corners | Sidebar tabs | P0 |
| ui_gauge_oil_frame | 192x32 | Lantern-shaped or brass gauge frame | P0 |
| ui_gauge_oil_fill | 184x24 | Flame gradient fill strip (code crops by oil %) | P0 |
| ui_shift_clock_dial | 96x96 | Circular manor-clock face with 8 segments | P0 |
| ui_shift_clock_hand | 8x40 | Clock hand, pivot at the bottom centre | P0 |
| ui_shift_clock_glow | 96x96, 4 frames | Pulsing ring for the telegraph | P1 |
| ui_star_full, ui_star_empty | 32x32 | Rating stars | P0 |
| ui_slider_track (128x8), ui_slider_knob (16x16) | | Settings | P1 |
| ui_checkbox_off, ui_checkbox_on | 16x16 | Settings | P1 |
| ui_toast_9slice | 32x32 | Small hint bubble background | P1 |
| ui_thought_bubble_9slice | 32x32 | Bubble for the AI thought line, with a tail piece `ui_thought_tail` 16x16 | P0 |

**Icons (24x24, single colour #E8D9B5 with transparent background, 1 frame each) — P0 unless noted:** icon_play, icon_pause, icon_step, icon_speed_down, icon_speed_up, icon_restart, icon_new_seed, icon_copy, icon_camera (P1), icon_sound_on, icon_sound_off, icon_music_on, icon_music_off, icon_settings, icon_help, icon_trophy (P1), icon_eye (belief overlay), icon_book (knowledge base), icon_log (inference log), icon_lantern, icon_charm, icon_heirloom, icon_ghost_face, icon_home, icon_back, icon_close.

**Cursors (P1):** cursor_arrow 16x16, cursor_hand 16x16, cursor_aim 32x32 (crosshair sigil used while aiming the charm).

## 8. Key art and screens

| Key | Size | Priority | Description |
|---|---|---|---|
| title_bg | 1280x720 | P0 | Night illustration of the manor from outside, one window glowing warm, moon, fog. Leave the left third calmer for the logo |
| title_fog_layer | 1280x720 | P2 | Transparent drifting-fog layer for parallax |
| title_stars_layer | 1280x720 | P2 | Transparent star/cloud layer for parallax |
| logo_shifting_manor | 640x200 | P0 | Logo lettering with a subtle rotation motif, transparent background |
| mode_card_play | 320x200 | P0 | Illustration: caretaker with lantern at a dark corridor |
| mode_card_watch_ai | 320x200 | P0 | Illustration: a glowing lantern-robot or spectral mind peeking at a floor plan |
| mode_card_duel | 320x200 | P1 | Two lanterns facing each other |
| mode_card_lab | 320x200 | P1 | Bar chart drawn as stacked books/candles |
| result_banner_win, result_banner_lose, result_banner_empty | 640x120 | P0 | Banners: escaped with heirloom, perished, escaped empty-handed |
| runcard_template | 800x450 | P1 | Polaroid/parchment frame used to export the shareable Run Card PNG |
| tutorial_pictogram_01 to _04 | 128x128 | P2 | One icon-style image per tutorial step (move, deduce, charm, shift) |
| splash_boot | 1280x720 | P2 | Team logo placeholder on dark background |
| app_icon | 256x256 (PNG and .ico) | P1 | Lantern with a rotating ring |

## 9. Audio

### 9.1 Music (loops unless stated)

| Key | Length | Priority | Brief |
|---|---|---|---|
| bgm_title | 60–90 s loop | P0 | Slow, 80 bpm, minor key, celesta and music-box melody over a low drone. Inviting but eerie |
| bgm_explore_calm | 90 s loop | P0 | 70 bpm, sparse piano and soft pads, same key as the title music |
| bgm_explore_tense | 90 s loop | P0 | **Layer stem** exactly the same tempo, key and length as `bgm_explore_calm`, containing only the added tension: tremolo strings, pulsing low heartbeat. The game crossfades it over the calm loop |
| bgm_ai_watch | 90 s loop | P2 | Cooler, slightly mechanical variation (soft arpeggios), for Watch AI mode |
| stinger_win | 4 s | P0 | Warm uplifting resolve |
| stinger_lose | 4 s | P0 | Descending, lantern-goes-out feeling |
| stinger_escaped_empty | 3 s | P1 | Neutral, slightly deflated |

### 9.2 Sound effects (mono, 44.1 kHz)

| Key | Length | Variants | Priority | Description |
|---|---|---|---|---|
| sfx_step_stone | 0.2 s | 4 | P0 | Footstep on old floor |
| sfx_bump | 0.2 s | 1 | P1 | Soft thud on wall |
| sfx_door_open, sfx_door_close | 1.0 s | 1 each | P1 | Heavy wooden door |
| sfx_pickup_treasure | 1.2 s | 1 | P0 | Bright chime with a sparkle tail |
| sfx_charm_cast | 0.8 s | 1 | P0 | Whoosh with a magical hum |
| sfx_charm_hit | 0.8 s | 1 | P1 | Impact burst |
| sfx_ghost_banish | 1.5 s | 1 | P0 | Wail dissolving into wind |
| sfx_ghost_growl_loop | 3 s loop | 1 | P0 | Low whispering growl (volume rises near the ghost) |
| sfx_wind_loop | 3 s loop | 1 | P0 | Soft cold draft (volume rises near pits) |
| sfx_glimmer_chime | 1.0 s | 1 | P0 | Gentle rising chime when treasure is close |
| sfx_pit_fall | 2.0 s | 1 | P0 | Falling whistle fading, ends with a distant thud |
| sfx_death_ghost | 1.5 s | 1 | P1 | Gasp and a cold gust |
| sfx_rumble_warning | 2.0 s | 1 | P0 | Low stone rumble with dust trickle |
| sfx_wing_rotate | 1.4 s | 1 | P0 | Heavy stone grinding, rotating mechanism, ends with a clunk |
| sfx_dust_settle | 1.0 s | 1 | P1 | Soft dust and pebbles falling |
| sfx_clock_tick | 0.15 s | 2 | P0 | Wooden clock tick for the Shift Clock |
| sfx_belief_crumble | 0.6 s | 2 | P0 | Glassy crumble when an AI belief is scattered |
| sfx_rule_fire | 0.08 s | 3 | P0 | Tiny soft tick when a rule fires (heard often, so very quiet and pleasant) |
| sfx_mark_place, sfx_mark_remove | 0.2 s | 1 each | P0 | Chalk-on-stone mark / wipe |
| sfx_lantern_flicker | 0.5 s | 2 | P1 | Soft flame flutter |
| sfx_oil_low | 1.0 s | 1 | P0 | Warning tone with a gentle heartbeat |
| sfx_ui_hover | 0.1 s | 1 | P0 | Subtle tick |
| sfx_ui_click | 0.15 s | 1 | P0 | Wooden click |
| sfx_ui_back | 0.15 s | 1 | P1 | Softer click |
| sfx_ui_toggle | 0.15 s | 1 | P1 | Switch sound |
| sfx_error | 0.3 s | 1 | P1 | Dull buzz for invalid action |
| sfx_star_tally | 0.3 s | 3 | P1 | Ascending ticks for score tally and stars |
| sfx_screenshot | 0.4 s | 1 | P2 | Camera shutter for Run Card export |

## 10. Fonts (open licenses, include the license text)

- **Display / headings / HUD:** Silkscreen (OFL) or Press Start 2P (OFL). Sizes used: 16, 24, 32.
- **Body / logs / rule text:** VT323 (OFL) or IBM Plex Mono (OFL). Sizes used: 16, 20, 24. Must stay legible at 16 px for the Inference Log.
- Place in `assets/fonts/` as `.ttf` plus `LICENSE` files.

## 11. Delivery checklist for Astra

- [ ] Every P0 item delivered first (the game is fully playable with P0 only).
- [ ] Palette snapped to the table; outline weight consistent across a set.
- [ ] Strips have exact frame width x count; no extra padding; transparent background.
- [ ] Audio loops tested for seamlessness; music layers aligned sample-accurately.
- [ ] File names exactly as listed; folders as in section 2.
- [ ] `assets/CREDITS.md` written; AI-generated files flagged.
- [ ] A contact sheet PNG (`assets/_contact_sheet.png`) showing all sprites at x3 for a quick review.

## 12. Manifest entry format (the coding agent will generate the skeleton)

```json
{
  "caretaker_walk_side": { "file": "sprites/caretaker_walk_side.png", "frame": [32, 32], "frames": 6, "fps": 10 },
  "bgm_explore_calm":    { "file": "audio/music/bgm_explore_calm.ogg", "loop": true, "volume": 0.8 },
  "sfx_step_stone":      { "files": ["audio/sfx/sfx_step_stone_01.ogg", "audio/sfx/sfx_step_stone_02.ogg"], "volume": 0.6 }
}
```
