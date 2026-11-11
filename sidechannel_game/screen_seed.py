"""
screen_seed.py -- the "NEW GAME" screen: type a seed or press RANDOMIZE.

The seed decides the lock's secret key (and every measurement the game
produces), so the same seed always gives the same game. It is saved together
with the player's progress (see progress.py).

Any text works as a seed ("12345678", "my-team-7", ...). Capitals and small
letters count as the same seed.

TINKER: the explanatory text is SEED_HELP below.
"""

import tkinter as tk

import scene_art
from progress import clean_seed, random_seed
from retro import C, RetroButton, array_to_photo, panel, pixel_label, px

MIN_W, MIN_H = scene_art.SCENE_W, scene_art.SCENE_H

SEED_HELP = (
    "The seed controls the game secret key. The same seed always gives "
    "the same game. Record the seed if you want to replay it later.\n\n"
    "Type any seed you like, or let the game pick one for you."
)


class SeedScreen(tk.Frame):
    def __init__(self, master, app, first_time):
        super().__init__(master, bg=C["bg"])
        self.app = app
        self.first_time = first_time

        self.canvas = tk.Canvas(self, bg=C["bg"], highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.image_id = self.canvas.create_image(0, 0, anchor="nw")
        self.photo = None
        self.zoom = 3

        # the form lives in a normal Tk panel floating over the backdrop
        self.form = tk.Frame(self.canvas, bg=C["bg"])
        body = panel(self.form, None, app.fonts, fill="both", expand=True)
        F = app.fonts

        pixel_label(body, "NEW GAME", zoom=4, color="amber", bg="panel",
                    shadow=None).pack(anchor="w")
        tk.Label(body, text=SEED_HELP, bg=C["panel"], fg=C["text"], font=F["body"],
                 justify="left", wraplength=px(520)).pack(anchor="w", pady=(10, 14))

        tk.Label(body, text="SEED", bg=C["panel"], fg=C["amber"],
                 font=F["label"]).pack(anchor="w")
        self.var = tk.StringVar()
        self.var.trace_add("write", self._limit_length)
        self.entry = tk.Entry(body, textvariable=self.var, width=24, font=F["stat"],
                              bg=C["inset"], fg=C["amber_hi"], relief="flat",
                              insertbackground=C["amber"], insertwidth=4,
                              highlightthickness=3, highlightbackground=C["border"],
                              highlightcolor=C["amber"])
        self.entry.pack(anchor="w", pady=(4, 6), ipady=7)
        self.entry.bind("<Return>", lambda e: self.start())

        self.status = tk.Label(body, text="", bg=C["panel"], fg=C["muted"],
                               font=F["small"], anchor="w", justify="left", wraplength=px(520))
        self.status.pack(anchor="w", pady=(0, 10))

        row = tk.Frame(body, bg=C["panel"])
        row.pack(anchor="w")
        RetroButton(row, "RANDOMIZE", self.randomize, kind="blue",
                    font=F["btn"]).pack(side="left")
        RetroButton(row, "START", self.start, kind="primary",
                    font=F["btn"]).pack(side="left", padx=12)
        if not first_time:
            RetroButton(row, "BACK", self.app.show_menu, kind="secondary",
                        font=F["btn"]).pack(side="left")
            self.bind_all("<Escape>", lambda e: self.app.show_menu())

        self.win_id = self.canvas.create_window(0, 0, window=self.form, anchor="w")
        self.canvas.bind("<Configure>", self._on_resize)
        self.after(80, self.entry.focus_set)

    # ----------------------------------------------------------------- layout
    def _on_resize(self, event):
        self.zoom = max(1, min(event.width // MIN_W, event.height // MIN_H))
        w = max(MIN_W, -(-event.width // self.zoom))            # art fills the window
        h = max(MIN_H, -(-event.height // self.zoom))
        self.photo = array_to_photo(scene_art.build_backdrop(w, h, True), self.zoom)
        self.canvas.itemconfig(self.image_id, image=self.photo)
        self.canvas.coords(self.win_id, 14 * self.zoom, event.height // 2)

    # ---------------------------------------------------------------- actions
    def _limit_length(self, *_):
        text = self.var.get()
        if len(text) > 24:
            self.var.set(text[:24])

    def randomize(self):
        self.var.set(random_seed())
        self.entry.select_range(0, "end")
        self.entry.focus_set()
        self.status.config(text="Random seed generated. Press START to play it.",
                           fg=C["cyan"])

    def start(self):
        seed = clean_seed(self.var.get())
        if not seed:
            self.status.config(text="Type a seed, or press RANDOMIZE.", fg=C["bad"])
            return
        self.unbind_all("<Escape>")
        self.app.begin_game(seed)

    def destroy(self):
        try:
            self.unbind_all("<Escape>")
        except tk.TclError:
            pass
        super().destroy()
