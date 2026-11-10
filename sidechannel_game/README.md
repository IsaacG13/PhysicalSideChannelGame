# Side-Channel Attack Game - demo build

A playable test build of the square-and-multiply smart-lock game:
Introduction -> Level 1 (timing) -> Level 2 (SPA) -> Level 3 (noise + protected lock) -> Review.
Scoring is intentionally not implemented yet.

## Requirements
Python 3.9+ with Tkinter, NumPy and Matplotlib.

### Windows
1. Install Python from https://www.python.org/downloads/ (Tkinter is included; keep the
   "tcl/tk and IDLE" option ticked, and tick "Add python.exe to PATH").
2. In a terminal (PowerShell or cmd) inside this folder:
       python -m pip install -r requirements.txt
       python main.py

### macOS
1. Install Python from https://www.python.org/downloads/ (Tkinter included).
   If you use Homebrew Python instead, also run:  brew install python-tk
2. In Terminal inside this folder:
       python3 -m pip install -r requirements.txt
       python3 main.py

### Linux
1. Install Tkinter through your package manager (it is a separate package):
       Debian / Ubuntu:  sudo apt install python3-tk python3-pip
       Fedora:           sudo dnf install python3-tkinter python3-pip
       Arch:             sudo pacman -S tk python-pip
2. In a terminal inside this folder:
       python3 -m pip install -r requirements.txt
       python3 main.py
   (If pip complains about an "externally managed environment", use a virtual env:
    python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt)

## Launching
    python main.py                       # asks for a student ID (blank = random game)
    python main.py --student alice123    # same ID always gives the same key and traces
    python main.py --seed 42             # explicit integer seed

## Handy demo tools
* Developer menu -> "Reveal key (spoiler!)" and "New random target".
* Matplotlib toolbar under each plot: magnifier = zoom, cross = pan, house = reset view.
* `python selftest.py` checks difficulty (success rates at each level) with no GUI.

## Files
    config.py    every tunable number (timing, jitter, noise, attempts, trace budget)
    sim.py       the simulated lock + oscilloscope (no GUI code)
    main.py      the Tkinter app; look for "TINKER:" comments
    selftest.py  headless difficulty calibration
Written free-text answers are appended to responses_log.jsonl (no grading yet).
