"""Procedural gothic audio engine with graceful silent fallback.

Generates atmospheric sound effects and layered ambient loops in memory using
pure Python stdlib + pygame.mixer so audio works out of the box without binary
assets, while remaining 100% safe under ``--no-audio`` and SDL dummy drivers.
"""

from __future__ import annotations

import array
import math
import random
import sys
import time

import pygame

IS_WEB = sys.platform == "emscripten"
SAMPLE_RATE = 11025 if IS_WEB else 22050
AMBIENT_DURATION = 1.6 if IS_WEB else 4.0


def _clamp16(sample: float) -> int:
    return max(-32767, min(32767, int(sample * 32767.0)))


def _build_sound(samples: list[float]) -> pygame.mixer.Sound:
    buf = array.array("h", (_clamp16(s) for s in samples))
    return pygame.mixer.Sound(buffer=buf)


def _tone(
    duration: float,
    freq_start: float,
    freq_end: float | None = None,
    *,
    amp: float = 0.25,
    wave: str = "sine",
    attack: float = 0.01,
    release: float = 0.08,
    noise_mix: float = 0.0,
    seed: int = 1,
) -> list[float]:
    n = max(1, int(SAMPLE_RATE * duration))
    f1 = freq_end if freq_end is not None else freq_start
    rng = random.Random(seed)
    phase = 0.0
    out: list[float] = []
    att_n = max(1, int(SAMPLE_RATE * attack))
    rel_n = max(1, int(SAMPLE_RATE * release))
    for i in range(n):
        t = i / n
        freq = freq_start + (f1 - freq_start) * t
        phase += 2.0 * math.pi * freq / SAMPLE_RATE
        if wave == "sine":
            val = math.sin(phase)
        elif wave == "triangle":
            val = (2.0 / math.pi) * math.asin(math.sin(phase))
        elif wave == "square":
            val = 0.6 if math.sin(phase) >= 0 else -0.6
        else:
            val = math.sin(phase) + 0.35 * math.sin(2.0 * phase)
        if noise_mix > 0.0:
            val = val * (1.0 - noise_mix) + (rng.random() * 2.0 - 1.0) * noise_mix
        env = 1.0
        if i < att_n:
            env = i / att_n
        if n - i < rel_n:
            env = min(env, (n - i) / rel_n)
        out.append(val * amp * env)
    return out


def _chord(freqs: tuple[float, ...], duration: float, *, amp: float = 0.16) -> list[float]:
    n = max(1, int(SAMPLE_RATE * duration))
    out = [0.0] * n
    for idx, f in enumerate(freqs):
        delay = int(idx * 0.06 * SAMPLE_RATE)
        part = _tone(
            max(0.05, duration - idx * 0.06),
            f,
            amp=amp / max(1, len(freqs) * 0.6),
            wave="soft",
            attack=0.015,
            release=min(0.28, duration * 0.65),
        )
        for i, s in enumerate(part):
            if delay + i < n:
                out[delay + i] += s
    return out


def _ambient_pad(freqs: tuple[float, ...], duration: float = 4.0, amp: float = 0.07) -> list[float]:
    n = int(SAMPLE_RATE * duration)
    out = [0.0] * n
    for f in freqs:
        # Snap frequency to an integer cycle count for a click-free seamless loop.
        cycles = max(1, round(f * duration))
        exact_f = cycles / duration
        for i in range(n):
            t = i / SAMPLE_RATE
            lfo = 0.8 + 0.2 * math.sin(2.0 * math.pi * (1.0 / duration) * t)
            out[i] += math.sin(2.0 * math.pi * exact_f * t) * amp * lfo / len(freqs)
    return out


class AudioManager:
    """Procedural SFX + subtle calm/tense ambient layer with cooldowns."""

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self.ready = False
        self.master_volume = 0.8
        self.music_volume = 0.45
        self.sfx_volume = 0.75
        self.tension = 0.0
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._last_played: dict[str, float] = {}
        self._calm_channel: pygame.mixer.Channel | None = None
        self._tense_channel: pygame.mixer.Channel | None = None
        self._ambient_started = False
        if enabled:
            self._init_mixer()

    def _init_mixer(self) -> None:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=1, buffer=512)
            pygame.mixer.set_num_channels(12)
            self._synthesize()
            self.ready = True
        except (pygame.error, OSError, RuntimeError, NotImplementedError, ValueError):
            self.ready = False

    def _synthesize(self) -> None:
        self._sounds = {
            "step": _build_sound(_tone(0.11, 145, 78, amp=0.26, noise_mix=0.35, release=0.07)),
            "bump": _build_sound(_tone(0.14, 110, 52, amp=0.32, wave="triangle", release=0.09)),
            "mark": _build_sound(_tone(0.08, 660, 880, amp=0.16, wave="triangle", release=0.05)),
            "rule_fire": _build_sound(_tone(0.05, 520, 620, amp=0.09, wave="sine", release=0.03)),
            "breeze": _build_sound(_tone(0.32, 340, 220, amp=0.14, noise_mix=0.75, release=0.18)),
            "chill": _build_sound(_tone(0.38, 220, 175, amp=0.16, wave="soft", release=0.22)),
            "glimmer": _build_sound(_chord((880.0, 1108.7, 1318.5), 0.36, amp=0.18)),
            "pickup": _build_sound(_chord((523.25, 659.25, 783.99, 1046.5), 0.55, amp=0.24)),
            "charm_cast": _build_sound(
                _tone(0.35, 360, 920, amp=0.22, wave="soft", noise_mix=0.2, release=0.16)
            ),
            "ghost_banish": _build_sound(
                _tone(0.65, 640, 160, amp=0.24, wave="triangle", noise_mix=0.3, release=0.35)
            ),
            "rumble": _build_sound(
                _tone(0.45, 92, 58, amp=0.28, wave="triangle", noise_mix=0.45, release=0.22)
            ),
            "shift": _build_sound(
                _tone(0.75, 115, 62, amp=0.30, wave="triangle", noise_mix=0.55, release=0.30)
            ),
            "oil_low": _build_sound(_tone(0.22, 160, 118, amp=0.20, wave="sine", release=0.14)),
            "ui_click": _build_sound(
                _tone(0.06, 540, 420, amp=0.14, wave="triangle", release=0.04)
            ),
            "ui_hover": _build_sound(_tone(0.04, 720, 760, amp=0.06, wave="sine", release=0.025)),
            "ui_back": _build_sound(_tone(0.08, 420, 300, amp=0.12, wave="triangle", release=0.05)),
            "win": _build_sound(_chord((440.0, 554.37, 659.25, 880.0), 0.72, amp=0.25)),
            "lose": _build_sound(_chord((329.63, 293.66, 246.94, 196.0), 0.75, amp=0.24)),
            "escape_empty": _build_sound(_chord((392.0, 440.0, 349.23), 0.50, amp=0.18)),
            "bgm_calm": _build_sound(
                _ambient_pad((146.83, 220.0, 293.66, 349.23), AMBIENT_DURATION, amp=0.12)
            ),
            "bgm_tense": _build_sound(
                _ambient_pad((110.0, 164.81, 207.65, 233.08), AMBIENT_DURATION, amp=0.14)
            ),
        }

    def start_ambient(self) -> None:
        if not (self.enabled and self.ready) or self._ambient_started:
            return
        try:
            self._calm_channel = pygame.mixer.Channel(0)
            self._tense_channel = pygame.mixer.Channel(1)
            self._calm_channel.play(self._sounds["bgm_calm"], loops=-1)
            self._tense_channel.play(self._sounds["bgm_tense"], loops=-1)
            self._ambient_started = True
            self._apply_volumes()
        except (pygame.error, IndexError, RuntimeError):
            self._ambient_started = False

    def set_volumes(
        self,
        *,
        master: float | None = None,
        music: float | None = None,
        sfx: float | None = None,
    ) -> None:
        if master is not None:
            self.master_volume = max(0.0, min(1.0, master))
        if music is not None:
            self.music_volume = max(0.0, min(1.0, music))
        if sfx is not None:
            self.sfx_volume = max(0.0, min(1.0, sfx))
        self._apply_volumes()

    def set_tension(self, target: float) -> None:
        self.tension = max(0.0, min(1.0, target))
        self._apply_volumes()

    def _apply_volumes(self) -> None:
        if not self._ambient_started:
            return
        base = self.master_volume * self.music_volume if self.enabled else 0.0
        if self._calm_channel is not None:
            self._calm_channel.set_volume(base * (1.0 - 0.55 * self.tension))
        if self._tense_channel is not None:
            self._tense_channel.set_volume(base * self.tension)

    def play(self, name: str, *, cooldown: float = 0.04, gain: float = 1.0) -> None:
        if not (self.enabled and self.ready):
            return
        sound = self._sounds.get(name)
        if sound is None:
            return
        now = time.monotonic()
        if now - self._last_played.get(name, 0.0) < cooldown:
            return
        self._last_played[name] = now
        vol = max(0.0, min(1.0, self.master_volume * self.sfx_volume * gain))
        if vol <= 0.001:
            return
        try:
            sound.set_volume(vol)
            sound.play()
        except (pygame.error, RuntimeError):
            return
