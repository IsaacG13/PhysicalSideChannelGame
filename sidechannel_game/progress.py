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
    levels     per level: whether it was completed plus any score details
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

# The menu shows a placeholder score under every level for now.
# TINKER: set SHOW_REAL_SCORES = True once the scoring rules are decided, and
# edit score_text() below to format the numbers however you like.
SHOW_REAL_SCORES = False
PLACEHOLDER_SCORE = "0/0"


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
        self.update_level(level_id, completed=True, **fields)

    def score_text(self, level_id):
        """What the menu prints under a level name."""
        if not SHOW_REAL_SCORES:
            return PLACEHOLDER_SCORE
        rec = self.data["levels"].get(level_id, {})
        if "score" in rec and "max_score" in rec:
            return "%s/%s" % (rec["score"], rec["max_score"])
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
