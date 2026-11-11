"""
audio.py -- sound effects and background music.

Uses pygame's mixer (pip install pygame). If pygame is missing, or the
computer has no sound device, the game simply runs silently.

The SOUND and MUSIC toggles on the main menu are the "sfx" and "music"
settings in the save file (progress.py); this module reads them.

Sounds (files in assets/sounds/):
    click      any button / menu click                  click.mp3
    correct    a right answer or a passed level         correct.mp3
    wrong      a wrong answer, refused input, a failed  wrong.mp3
               level, a locked level
    music      background track, looped                 music.mp3

Background music: the first play starts at full volume. Near the end of the
track it fades down (FADE_OUT_SECONDS, to FADE_FLOOR of full volume); when the
loop starts again it fades back up over FADE_IN_SECONDS.

Usage from anywhere in the game:
    import audio
    audio.play("correct")

TINKER: volumes and fade times are the constants below.
"""

import os
import threading

try:                                    # hide pygame's hello banner
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import pygame
except Exception:                       # pygame not installed -> silent game
    pygame = None

HERE = os.path.dirname(os.path.abspath(__file__))
SOUND_DIR = os.path.join(HERE, "assets", "sounds")
SOUND_FILES = {"click": "click.mp3", "correct": "correct.mp3", "wrong": "wrong.mp3"}
MUSIC_FILE = "music.mp3"

SFX_VOLUME = {"click": 0.6, "correct": 0.7, "wrong": 0.7}
MUSIC_VOLUME = 0.35          # full background-music volume (0..1)
FADE_OUT_SECONDS = 8.0       # the fade-down starts this long before the track ends
FADE_IN_SECONDS = 5.0        # fade-up when the loop restarts
FADE_FLOOR = 0.15            # lowest point of the fade, as a share of MUSIC_VOLUME
TICK_MS = 100                # how often the music volume is updated

_state = {
    "ready": False,          # mixer working?
    "root": None,            # Tk root (for timers)
    "save": None,            # SaveData (for the on/off settings)
    "sounds": {},
    "music_len": None,       # track length in seconds (measured in the background)
    "music_on": False,       # is the track supposed to be playing?
    "looped": False,         # has the track restarted at least once?
}


def init(root, save):
    """Start the mixer, load the sound effects and, if the MUSIC setting is
    on, start the background track. Safe to call when pygame is missing."""
    _state["root"], _state["save"] = root, save
    if pygame is None:
        return
    try:
        pygame.mixer.init()
        for name, filename in SOUND_FILES.items():
            snd = pygame.mixer.Sound(os.path.join(SOUND_DIR, filename))
            snd.set_volume(SFX_VOLUME.get(name, 0.7))
            _state["sounds"][name] = snd
        pygame.mixer.music.load(os.path.join(SOUND_DIR, MUSIC_FILE))
    except Exception:                   # no audio device / missing file
        _state["ready"] = False
        return
    _state["ready"] = True
    # Measuring the track length means decoding it, which takes a moment:
    # do it in the background so the window opens straight away.
    threading.Thread(target=_measure_music, daemon=True).start()
    if save.setting("music"):
        set_music(True, fade_in=False)
    root.after(TICK_MS, _tick)


def _measure_music():
    try:
        _state["music_len"] = pygame.mixer.Sound(
            os.path.join(SOUND_DIR, MUSIC_FILE)).get_length()
    except Exception:
        _state["music_len"] = None      # no fade-out, the loop still works


# --------------------------------------------------------------- sound effects
def play(name):
    """Play a sound effect ("click", "correct" or "wrong") if SOUND is on."""
    if not _state["ready"] or _state["save"] is None or not _state["save"].setting("sfx"):
        return
    snd = _state["sounds"].get(name)
    if snd is not None:
        try:
            snd.stop()                  # restart rather than stack the same sound
            snd.play()
        except Exception:
            pass


# ---------------------------------------------------------------------- music
def set_music(on, fade_in=True):
    """Turn the background music on or off (the menu's MUSIC toggle)."""
    if not _state["ready"]:
        return
    _state["music_on"] = on
    try:
        if on:
            pygame.mixer.music.stop()
            pygame.mixer.music.set_volume(MUSIC_VOLUME * (FADE_FLOOR if fade_in else 1.0))
            pygame.mixer.music.play()
            _state["looped"] = fade_in  # fade_in=True behaves like a loop restart
        else:
            pygame.mixer.music.stop()
    except Exception:
        pass


def _envelope(pos):
    """Volume share (FADE_FLOOR..1) at `pos` seconds into the track."""
    level = 1.0
    if _state["looped"] and pos < FADE_IN_SECONDS:              # fading back in
        level = min(level, FADE_FLOOR + (1 - FADE_FLOOR) * pos / FADE_IN_SECONDS)
    length = _state["music_len"]
    if length:                                                  # fading out
        left = length - pos
        if left < FADE_OUT_SECONDS:
            share = max(0.0, left) / FADE_OUT_SECONDS
            level = min(level, FADE_FLOOR + (1 - FADE_FLOOR) * share)
    return level


def _tick():
    """Loop the track and update its volume. Runs every TICK_MS."""
    try:
        if _state["music_on"]:
            if not pygame.mixer.music.get_busy():               # track ended: loop
                _state["looped"] = True
                pygame.mixer.music.set_volume(MUSIC_VOLUME * FADE_FLOOR)
                pygame.mixer.music.play()
            pos = max(0, pygame.mixer.music.get_pos()) / 1000.0
            pygame.mixer.music.set_volume(MUSIC_VOLUME * _envelope(pos))
    except Exception:
        pass
    root = _state["root"]
    try:
        root.after(TICK_MS, _tick)
    except Exception:                   # window closed
        pass


def shutdown():
    if _state["ready"]:
        try:
            pygame.mixer.quit()
        except Exception:
            pass
    _state["ready"] = False
