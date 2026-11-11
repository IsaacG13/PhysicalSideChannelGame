# Side-Channel Attack!

A retro-style educational game about **physical side-channel attacks**. You play an
attacker who can't see a smart lock's secret key or code, only measure the device,
and you recover information about the key from how long it takes and how much
power it draws.

| Level | Topic | Status |
|---|---|---|
| Introduction | What side channels and leakage are (reading + true/false checks) | Playable |
| Level 1: Timing | Count the 1 bits of a square-and-multiply key from execution times | Playable |
| Level 2: SPA | Simple power analysis | Coming soon |
| Level 3: SPA Advanced | Noisy traces, averaging, a protected lock | Coming soon |
| Review | Wrap-up | Coming soon |

## Quick start

You need **Python 3.9+** with **Tkinter**, plus the packages in
`sidechannel_game/requirements.txt` (NumPy, Matplotlib and pygame).

```bash
cd sidechannel_game
python -m pip install -r requirements.txt
python retro_game.py
```

On macOS and Linux use `python3` instead of `python`.

### Installing Python and Tkinter

- **Windows:** install Python from [python.org](https://www.python.org/downloads/). Keep
  "tcl/tk and IDLE" ticked and tick "Add python.exe to PATH".
- **macOS:** install Python from [python.org](https://www.python.org/downloads/).
  Homebrew Python also needs `brew install python-tk`.
- **Linux:** install Tkinter with your package manager first:
  - Debian/Ubuntu: `sudo apt install python3-tk python3-pip`
  - Fedora: `sudo dnf install python3-tkinter python3-pip`
  - Arch: `sudo pacman -S tk python-pip`

  If pip refuses with "externally managed environment", use a virtual environment:

  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  ```

pygame is only used for sound. Without it (or without a sound device) the game
runs silently.

The screen is designed for 1366×768 or larger; high-DPI displays are scaled
automatically.

## How the game works

- **Seed:** the first launch asks for a seed (type one or press RANDOMIZE). The seed
  decides the lock's secret key, so the same seed always gives the same game.
- **Unlocking:** each level unlocks when the level above it is **passed**.
- **Scoring:** a level is passed with **70% or more** of its points.
  - Introduction: 5 points per true/false question (10 in total).
  - Level 1: 3 / 2 / 1 points for the 1-bit count (attempt 1 / 2 / 3) plus 7 points
    for the written explanation (10 in total).
- **Failing:** below 70% the level must be played again. Failing a level that uses
  the seed's data (Level 1 onwards) also gives you a **new seed**, so the key can't
  be brute-forced by replaying.
- **Sound:** the SOUND and MUSIC icons in the top-right of the main menu switch the
  effects and the background music on and off.
- **Saving:** progress, scores and the seed are saved automatically.

### Command-line options

```text
--seed TEXT   start a new game with that seed (the same seed keeps progress)
--new         show the NEW GAME screen
--save PATH   use another save file (handy for demos and testing)
```

### Save file

| OS | Location |
|---|---|
| Windows | `%APPDATA%\SideChannelGame\save.json` |
| macOS | `~/Library/Application Support/SideChannelGame/save.json` |
| Linux | `~/.local/share/SideChannelGame/save.json` |

If that folder can't be written, the game saves `save.json` next to the code.
Delete the file to reset everything.

## Project layout

All code lives in `sidechannel_game/`:

| File | What it does |
|---|---|
| `retro_game.py` | **Start here.** Window and moving between screens |
| `screen_menu.py`, `screen_seed.py` | Main menu and NEW GAME (seed) screen |
| `screen_intro.py`, `intro_content.py` | Introduction screens; the text lives in `intro_content.py` |
| `screen_level1.py` | Level 1 (timing attack) screens |
| `game_with_hints.py` | Level 1 simulation, hints and short-answer scoring |
| `config.py` | Tunable numbers: key, timing jitter, batch sizes, attempts, power-trace model |
| `sim.py` | Power-trace model for Levels 2 and 3 (not playable yet) |
| `progress.py` | Save file, scores, pass mark, unlocking |
| `audio.py`, `assets/sounds/` | Sound effects and background music |
| `retro.py`, `pixelfont.py`, `scene_art.py` | Colours, fonts, widgets and pixel art |
| `selftest.py` | Headless difficulty check (see below) |

### Tuning the difficulty

Change the numbers in `config.py` (for example `L1_JITTER_SIGMA_IN_TM`, the timing
jitter in multiples of one multiply time), then run:

```bash
python selftest.py
```

It simulates many students with the same simulator the game uses and prints how
often the correct answer comes out for different amounts of data.

## Credits

Background music: "Swing Jazz Study Session" by Alex Morgan. Sound effects are from
royalty-free libraries; check each file's licence before publishing the game.
