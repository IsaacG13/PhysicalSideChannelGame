"""
retro_game.py -- START THE GAME HERE:   python retro_game.py

Flow:  (first launch) NEW GAME screen -> main menu -> levels.
       (later launches) main menu straight away, with your saved seed and
       progress. NEW GAME (bottom-left of the menu) starts over.

Command-line options (all optional)
    --seed TEXT    start a new game with this seed (skips the seed screen).
                   If the saved game already uses this seed, progress is kept.
    --new          ignore the saved game and show the NEW GAME screen
    --save PATH    use a different save file (handy for testing / demos)

Files
    retro_game.py     this file: window + moving between screens
    screen_menu.py    main menu          screen_seed.py   seed entry
    screen_intro.py   introduction       screen_level1.py Level 1 (timing)
    intro_content.py  the text of the introduction (easy to edit)
    game_with_hints.py  Level 1 simulation, hints and scoring (reused as-is)
    retro.py          colours, fonts, widgets      pixelfont.py, scene_art.py  pixel art
    progress.py       save file
"""

import argparse
import tkinter as tk

import retro
from progress import SaveData, clean_seed
from retro import C


class App:
    def __init__(self, root, save, seed=None, force_new=False):
        self.root = root
        self.save = save
        self.fonts = retro.make_fonts(root)
        self.screen = None

        root.title("Side-Channel Attack!")
        root.configure(bg=C["bg"])
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h = min(retro.px(1200), sw - 40), min(retro.px(760), sh - 90)
        root.geometry("%dx%d+%d+%d" % (w, h, max(0, (sw - w) // 2), max(0, (sh - h) // 3)))
        root.minsize(min(retro.px(1100), w), min(retro.px(680), h))

        self.container = tk.Frame(root, bg=C["bg"])
        self.container.pack(fill="both", expand=True)

        seed = clean_seed(seed) if seed else ""
        if seed and seed != self.save.seed:
            self.save.new_game(seed)           # a different seed means a new game
        if force_new and not seed:
            self.show_seed(first_time=not self.save.has_game)
        elif self.save.has_game:
            self.show_menu()
        else:
            self.show_seed(first_time=True)

    # -------------------------------------------------------------- switching
    def _swap(self, make_screen):
        if self.screen is not None:
            self.screen.destroy()
        self.screen = make_screen(self.container)
        self.screen.pack(fill="both", expand=True)

    def show_menu(self, message=None, seconds=3.5):
        from screen_menu import MenuScreen
        self._swap(lambda parent: MenuScreen(parent, self))
        if message:
            screen = self.screen
            self.root.after(150, lambda: screen.winfo_exists() and screen.say(message, seconds))

    def fail_message(self, level_id, new_seed=None):
        """Menu message after a failed level (shown instead of 'UNLOCKED!')."""
        from progress import level_name
        text = "SCORE HIGHER ON %s TO PROCEED!\n" % level_name(level_id)
        if new_seed:
            text += "YOUR TAMPERING HAS CAUSED THE SEED TO SCRAMBLE!."
        return text

    def show_seed(self, first_time):
        from screen_seed import SeedScreen
        self._swap(lambda parent: SeedScreen(parent, self, first_time))

    def start_new_game(self):
        """Called by the menu after the player confirms."""
        self.show_seed(first_time=False)

    def begin_game(self, seed):
        """Called by the seed screen: save the seed, wipe progress, go to menu."""
        self.save.new_game(seed)
        self.show_menu()

    def open_level(self, level_id):
        if level_id == "intro":
            from screen_intro import IntroScreen
            self._swap(lambda parent: IntroScreen(parent, self))
        elif level_id == "level1":
            from screen_level1 import Level1Screen
            self._swap(lambda parent: Level1Screen(parent, self))
        else:                                   # levels not built yet
            if hasattr(self.screen, "say"):
                self.screen.say("COMING SOON")


def main():
    parser = argparse.ArgumentParser(description="Side-Channel Attack! (retro build)")
    parser.add_argument("--seed", help="start a new game with this seed")
    parser.add_argument("--new", action="store_true", help="show the NEW GAME screen")
    parser.add_argument("--save", help="path of the save file to use")
    args = parser.parse_args()

    retro.enable_hidpi()
    retro.apply_matplotlib_style()
    root = tk.Tk()
    App(root, SaveData(args.save), seed=args.seed, force_new=args.new)
    root.mainloop()


if __name__ == "__main__":
    main()
