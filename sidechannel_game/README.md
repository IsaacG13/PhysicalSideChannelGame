# Side-Channel Attack! (retro build)

Start the game with:   python retro_game.py     (python3 on macOS / Linux)

Flow: first launch asks for a seed (type one or press RANDOMIZE) -> main menu ->
Introduction -> Level 1: Timing. Levels 2, 3 and Review show "COMING SOON".
Each level unlocks when the one above is completed. Progress and the seed are saved.

## Install
You need Python 3.9+ with Tkinter, NumPy and Matplotlib.

Windows:  install Python from python.org (keep "tcl/tk and IDLE" ticked and tick
          "Add python.exe to PATH"), then in this folder:
              python -m pip install -r requirements.txt
              python retro_game.py
macOS:    install Python from python.org (Homebrew Python also needs: brew install python-tk), then:
              python3 -m pip install -r requirements.txt
              python3 retro_game.py
Linux:    install Tkinter first:
              Debian/Ubuntu: sudo apt install python3-tk python3-pip
              Fedora:        sudo dnf install python3-tkinter python3-pip
              Arch:          sudo pacman -S tk python-pip
          then:  python3 -m pip install -r requirements.txt   (add --break-system-packages
          on newer distros if pip refuses)   and   python3 retro_game.py

Screen: designed for 1366x768 or larger (window height about 680 px). High-DPI
displays are scaled automatically.

## Options
    --seed TEXT   start a new game with that seed (same seed keeps progress)
    --new         show the NEW GAME screen
    --save PATH   use another save file (useful for demos and testing)

Save file: Windows %APPDATA%\SideChannelGame\save.json,
macOS ~/Library/Application Support/SideChannelGame/save.json,
Linux ~/.local/share/SideChannelGame/save.json (falls back to the game folder).
Delete it to reset everything.

## Where to tinker
    intro_content.py     Introduction text and figures (plain text, easy to edit)
    game_with_hints.py   Level 1 simulation, hints and scoring (imported by the game)
    screen_menu.py       menu layout; progress.py -> score_text / SHOW_REAL_SCORES for scores
    retro.py             colours and fonts       scene_art.py / pixelfont.py   pixel art
The older prototype files (main.py, level1_timing.py, ...) are kept untouched;
see README_old_prototype.md.
