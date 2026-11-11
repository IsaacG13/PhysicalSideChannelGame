"""
progress.py -- saving the player's seed, level progress and settings.

One save slot per computer user. The file is plain JSON so you can open it,
read it, or delete it to reset the game.

Where the file lives
    Windows : %APPDATA%\\SideChannelGame\\save.json
    macOS   : ~/Library/Application Support/SideChannelGame/save.json
    Linux   : ~/.local/share/SideChannelGame/save.json   (or $XDG_DATA_HOME)
If that folder cannot be written, the game falls back to a save.json next to
the program. Use  --save PATH  on the command line to choose another file.

What is stored
    seed       the player's seed (text exactly as entered / generated)
    levels     per level: whether it was completed (= passed) plus score details.
               A failed level keeps only {failed, score, max_score, fails}.
    settings   sound-effects / music on-off (audio comes later)
    flags      small "have we shown this once" markers (e.g. the Level 1 tour)
"""

import json
import os
import random
import sys
import tempfile

SAVE_VERSION = 1

# Order matters: each level unlocks when the one before it is completed.
# (id, name shown in the menu)
LEVELS = [
    ("intro", "INTRODUCTION"),
    ("level1", "LEVEL 1: TIMING"),
    ("level2", "LEVEL 2: SPA"),
    ("level3", "LEVEL 3: SPA ADVANCED"),
    ("review", "REVIEW"),
]
LEVEL_IDS = [lid for lid, _ in LEVELS]

# Scores shown in the menu. TINKER: set SHOW_REAL_SCORES = False to go back to
# the "0/0" placeholder everywhere.
SHOW_REAL_SCORES = True
PLACEHOLDER_SCORE = "0/0"          # levels with no scoring yet
MAX_SCORES = {"intro": 10, "level1": 10}   # shown as 0/N before a level is played

# A level is passed with at least this share of its points; below it the level
# is failed, stays incomplete, and must be played again before the next unlocks.
PASS_FRACTION = 0.70

# Levels whose data comes from the seed. Failing one of these gives the player a
# NEW random seed (new key), so a level can't be brute-forced by replaying it.
SEEDED_LEVELS = ("level1", "level2", "level3")


def level_name(level_id):
    return dict(LEVELS).get(level_id, level_id.upper())


def passed(score, max_score):
    """True if score is at least PASS_FRACTION of max_score."""
    return max_score > 0 and score >= PASS_FRACTION * max_score - 1e-9


def default_save_path():
    """Per-user save location, different on each operating system."""
    home = os.path.expanduser("~")
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
    elif sys.platform == "darwin":
        base = os.path.join(home, "Library", "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
    return os.path.join(base, "SideChannelGame", "save.json")


def fallback_save_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "save.json")


def random_seed():
    """A fresh random 8-digit seed, as text."""
    return str(random.SystemRandom().randrange(10_000_000, 100_000_000))


def clean_seed(text):
    """Normalise what the player typed. Returns '' if nothing usable."""
    return " ".join(str(text).split())[:24]


def _blank():
    return {
        "version": SAVE_VERSION,
        "seed": None,
        "levels": {},
        "settings": {"sfx": True, "music": True},
        "flags": {},
    }


class SaveData:
    """Loads, edits and writes the save file."""

    def __init__(self, path=None):
        self.path = path or default_save_path()
        self.data = _blank()
        self.load()

    # ------------------------------------------------------------ file access
    def load(self):
        """Read the first save file that exists (default location, then the
        fallback next to the program). A corrupt file is kept as .bak."""
        for candidate in dict.fromkeys([self.path, fallback_save_path()]):
            if not os.path.exists(candidate):
                continue
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if not isinstance(loaded, dict):
                    raise ValueError("save file is not a JSON object")
            except (OSError, ValueError):
                try:
                    os.replace(candidate, candidate + ".bak")
                except OSError:
                    pass
                continue
            merged = _blank()
            merged.update(loaded)
            merged["settings"] = {**_blank()["settings"], **loaded.get("settings", {})}
            self.path = candidate
            self.data = merged
            return

    def save(self):
        """Write atomically so a crash mid-write cannot corrupt the save."""
        for path in (self.path, fallback_save_path()):
            try:
                folder = os.path.dirname(path)
                os.makedirs(folder, exist_ok=True)
                fd, tmp = tempfile.mkstemp(dir=folder, suffix=".tmp")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, indent=2)
                os.replace(tmp, path)
                self.path = path
                return True
            except OSError:
                continue
        return False  # saving is best-effort: the game keeps running

    # ------------------------------------------------------------------- seed
    @property
    def seed(self):
        return self.data.get("seed")

    @property
    def has_game(self):
        return bool(self.data.get("seed"))

    def new_game(self, seed):
        """Start over with a new seed: progress is wiped, settings are kept."""
        settings = self.data.get("settings", _blank()["settings"])
        self.data = _blank()
        self.data["settings"] = settings
        self.data["seed"] = clean_seed(seed)
        self.save()

    # --------------------------------------------------------------- progress
    def level(self, level_id):
        """The stored record for a level (a dict; empty if never played)."""
        return self.data["levels"].setdefault(level_id, {})

    def is_complete(self, level_id):
        return bool(self.data["levels"].get(level_id, {}).get("completed"))

    def is_unlocked(self, level_id):
        index = LEVEL_IDS.index(level_id)
        return index == 0 or self.is_complete(LEVEL_IDS[index - 1])

    def update_level(self, level_id, **fields):
        self.level(level_id).update(fields)
        self.save()

    def mark_complete(self, level_id, **fields):
        self.update_level(level_id, completed=True, failed=False, **fields)

    def fail_level(self, level_id, score, max_score):
        """Record a failed attempt: the level stays incomplete and starts fresh
        next time. For a seeded level the player also gets a new random seed,
        and every seeded level's progress is cleared. Returns the new seed, or
        None if the seed was kept."""
        fails = int(self.level(level_id).get("fails", 0)) + 1
        new_seed = self.reseed(save=False) if level_id in SEEDED_LEVELS else None
        self.data["levels"][level_id] = {"failed": True, "score": score,
                                         "max_score": max_score, "fails": fails}
        self.save()
        return new_seed

    def reseed(self, save=True):
        """Give the player a new random seed (a new key) and clear the progress
        of every seeded level. Used when a seeded level is failed or restarted
        after an attempt. Returns the new seed."""
        new_seed = random_seed()
        self.data["seed"] = new_seed
        for lid in SEEDED_LEVELS:
            rec = self.data["levels"].pop(lid, None)
            if rec and rec.get("completed"):     # never undo a level already passed
                self.data["levels"][lid] = rec
        if save:
            self.save()
        return new_seed

    def score_text(self, level_id):
        """What the menu prints under a level name: the last score, or 0/max."""
        if not SHOW_REAL_SCORES:
            return PLACEHOLDER_SCORE
        rec = self.data["levels"].get(level_id, {})
        if "score" in rec and "max_score" in rec:
            return "%s/%s" % (rec["score"], rec["max_score"])
        if level_id in MAX_SCORES:
            return "0/%d" % MAX_SCORES[level_id]
        return PLACEHOLDER_SCORE

    # --------------------------------------------------------------- settings
    def setting(self, name):
        return bool(self.data["settings"].get(name, True))

    def toggle_setting(self, name):
        self.data["settings"][name] = not self.setting(name)
        self.save()
        return self.data["settings"][name]

    def flag(self, name):
        return bool(self.data["flags"].get(name))

    def set_flag(self, name, value=True):
        self.data["flags"][name] = value
        self.save()
