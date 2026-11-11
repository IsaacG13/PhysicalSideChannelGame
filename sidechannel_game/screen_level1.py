"""
screen_level1.py -- Level 1: Timing attack, in the retro style.

The game logic is NOT in this file. It is reused from game_with_hints.py:
    TimingSimulator   the lock's timing model (key, jitter, batches of runs)
    score_short_answer  the rubric check for the written explanation
    HINTS / points_for_attempt / MIN_RUNS / ...   the rules and constants
so changing a rule there (jitter, t_S, hints, rubric words) changes it here.
This file only draws the screens and talks to the save file.

Flow:  lab (measure + submit bit count)  ->  short answer  ->  results

Lab rules (numbers live in game_with_hints.py):
  * at most MAX_BATCHES batches of runs; the plot's colour key (legend) can be
    hidden / shown with the KEY button above the plot
  * a wrong number can't be submitted twice: repeating it is refused and does
    not use up an attempt
  * hint 1 is open from the start; hint 2 unlocks after 1 wrong attempt, hint 3
    after 2 (g.hint_unlocked)
  * once the bit-count puzzle is over, "Show correct answer & explanation"
    opens a card with the answer worked out from the player's own measurements
    (it opens by itself after the last wrong attempt)

The player's seed picks the key: TimingSimulator is seeded with the saved seed.

Saving (progress.py)
  * after every bit-count submission the attempts used are saved, so leaving
    and coming back cannot reset the "3 attempts" limit
  * the level counts as completed when the written explanation is submitted
  * a completed level can be replayed as PRACTICE; practice never changes the
    saved record or score

Scores are kept in the save file (score / max_score) but the main menu still
shows the 0/0 placeholder - see progress.py (SHOW_REAL_SCORES).

TINKER: layout numbers (column widths, paddings) are near the top of
show_lab(). Tour text is in _tour_steps().
"""

import tkinter as tk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import game_with_hints as g
import retro
from retro import C, Pips, RetroButton, font, panel, px, style_axes, topbar

MAX_SCORE = 6               # 3 points for the bit count + 3 for the explanation
COL_W_BASE = 290            # width of the left and right columns (96-DPI pixels)


class Level1Screen(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=C["bg"])
        self.app, self.save, self.F = app, app.save, app.fonts
        self.root = app.root
        self.practice = self.save.is_complete("level1")
        self.sim = g.TimingSimulator(student_id=str(self.save.seed))

        # --- state of this visit --------------------------------------------
        self.times = np.empty(0)
        self.batch_ids = np.empty(0, dtype=int)
        self.n_batches = 0
        self.attempt = 0
        self.bit_points = 0
        self.sa_points = 0
        self.bits_done = False
        self.hints_shown = 0
        self.guesses = []                          # every number submitted, in order
        self.show_key = not self.save.flag("level1_hide_key")
        self.tour = None
        self._modal_close = None
        self._hint_view = 0
        if not self.practice:                      # resume where the player left off
            rec = self.save.level("level1")
            self.attempt = int(rec.get("attempt", 0))
            self.bit_points = int(rec.get("bit_points", 0))
            self.bits_done = bool(rec.get("bits_done", False))
            self.guesses = [int(x) for x in rec.get("guesses", [])]

        # --- frame: top bar + a stage that is swapped between views ------------
        self.bar, right = topbar(self, self.F, "LEVEL 1  -  TIMING ATTACK", "", self.app.show_menu)
        self.help_btn = RetroButton(self.bar, "?  HOW TO PLAY", self.start_tour,
                                    kind="secondary", font=self.F["smallb"])
        self.help_btn.pack(side="right", padx=(0, 20))
        self.score_lbl = tk.Label(right, text="", bg=C["bg"], fg=C["text"], font=self.F["bodyb"])
        self.score_lbl.pack(anchor="e")
        sub = "PRACTICE: SCORE NOT RECORDED" if self.practice else "SEED %s" % self.save.seed
        tk.Label(right, text=sub, bg=C["bg"], fg=C["amber"] if self.practice else C["muted"],
                 font=self.F["label"]).pack(anchor="e")

        self.stage = tk.Frame(self, bg=C["bg"])
        self.stage.pack(fill="both", expand=True)
        self.show_lab()

    # ------------------------------------------------------------------ utils
    def _clear(self):
        self.end_tour()
        self._close_modal()
        for w in self.stage.winfo_children():
            w.destroy()

    def _title(self, text):
        self.bar.title_lbl.config(text=text)

    def _score_text(self):
        return "SCORE  %d / %d" % (self.bit_points + self.sa_points, MAX_SCORE)

    def _persist(self, **fields):
        if not self.practice:
            self.save.update_level("level1", **fields)

    # =========================================================================
    # View 1: the lab
    # =========================================================================
    def show_lab(self):
        self._clear()
        F = self.F
        COL_W = px(COL_W_BASE)
        self._title("Count the 1 bits in the lock's secret key")
        self.help_btn.pack(side="right", padx=(0, 20))
        self.score_lbl.config(text=self._score_text())

        body = tk.Frame(self.stage, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        # ---- left column: briefing, specs, objective ----------------------------
        left = tk.Frame(body, bg=C["bg"], width=COL_W)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        brief = panel(left, "Mission briefing", F, fill="x")
        self.t_brief = brief.outer
        tk.Label(brief, justify="left", wraplength=COL_W - px(50), bg=C["panel"], fg=C["text"],
                 font=F["small"], text=(
                     "The SmartLock MCU unlocks by computing a modular exponentiation "
                     "with a secret 16-bit exponent, using square-and-multiply.\n\n"
                     "For every key bit it squares (S). When the bit is 1 it also "
                     "multiplies (M).\n\n"
                     "You can't see the key or the code, but you can time the device. "
                     "Each run has random clock jitter, so a single measurement isn't "
                     "reliable.")).pack(anchor="w")

        specs = panel(left, "Known device specs", F, fill="x", pady=(8, 0))
        self.t_specs = specs.outer
        for k, v in [("Key length", "%d bits" % g.KEY_BITS),
                     ("Square  t_S", "%.1f µs" % g.T_S_US),
                     ("Multiply t_M", "1.5 × t_S"),
                     ("Jitter", "random")]:
            row = tk.Frame(specs, bg=C["panel"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text=k, bg=C["panel"], fg=C["muted"], font=F["small"]).pack(side="left")
            tk.Label(row, text=v, bg=C["panel"], fg=C["amber"], font=F["smallb"]).pack(side="right")

        goal = panel(left, "Objective", F, fill="x", pady=(8, 0))
        tk.Label(goal, justify="left", wraplength=COL_W - px(50), bg=C["panel"], fg=C["text"],
                 font=F["small"],
                 text="Collect timing measurements and work out how many of the "
                      "16 key bits are 1. You have 3 attempts.").pack(anchor="w")

        # ---- right column: measure, submit, hints ---------------------------------
        right = tk.Frame(body, bg=C["bg"], width=COL_W)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        meas = panel(right, "1 · Measure", F, fill="x")
        self.t_meas = meas.outer
        self.runs_var = tk.IntVar(value=30)
        hdr = tk.Frame(meas, bg=C["panel"])
        hdr.pack(fill="x")
        tk.Label(hdr, text="Runs per batch (%d-%d)" % (g.MIN_RUNS, g.MAX_RUNS),
                 bg=C["panel"], fg=C["text"], font=F["small"]).pack(side="left")
        tk.Label(hdr, textvariable=self.runs_var, bg=C["panel"], fg=C["amber"],
                 font=F["stat"]).pack(side="right")
        tk.Scale(meas, from_=g.MIN_RUNS, to=g.MAX_RUNS, orient="horizontal",
                 variable=self.runs_var, showvalue=0, bg=C["amber"], troughcolor=C["inset"],
                 highlightthickness=0, bd=0, width=16, activebackground=C["amber_hi"],
                 sliderrelief="raised", sliderlength=26, length=COL_W - px(50)).pack(fill="x", pady=(8, 2))
        self.run_btn = RetroButton(meas, "> RUN BATCH", self.run_batch, font=F["btn"])
        self.run_btn.pack(fill="x", pady=(8, 6))
        RetroButton(meas, "CLEAR MEASUREMENTS", self.clear_runs, kind="secondary",
                    font=F["small"]).pack(fill="x")

        sub = panel(right, "2 · Submit", F, fill="x", pady=(8, 0))
        self.t_sub = sub.outer
        tk.Label(sub, text="Number of 1 bits in the key", bg=C["panel"], fg=C["text"],
                 font=F["small"]).pack(anchor="w")
        rowf = tk.Frame(sub, bg=C["panel"])
        rowf.pack(fill="x", pady=(6, 8))
        self.guess_var = tk.StringVar(value="")
        self.guess = tk.Spinbox(rowf, from_=0, to=g.KEY_BITS, textvariable=self.guess_var,
                                width=4, font=F["stat"], bg=C["inset"], fg=C["amber_hi"],
                                buttonbackground=C["panel2"], relief="flat",
                                insertbackground=C["amber"], highlightthickness=2,
                                highlightbackground=C["border"], highlightcolor=C["amber"],
                                justify="center")
        self.guess.pack(side="left", ipady=3)
        self.guess_var.set("")
        tk.Label(rowf, text=" / %d" % g.KEY_BITS, bg=C["panel"], fg=C["muted"],
                 font=F["stat"]).pack(side="left")
        self.guess.bind("<Return>", lambda e: self.submit_bits())

        self.submit_btn = RetroButton(sub, "SUBMIT ANSWER", self.submit_bits, kind="blue",
                                      font=F["btn"])
        self.submit_btn.pack(fill="x")
        att = tk.Frame(sub, bg=C["panel"])
        att.pack(fill="x", pady=(8, 0))
        tk.Label(att, text="Attempts", bg=C["panel"], fg=C["muted"],
                 font=F["small"]).pack(side="left")
        self.pips = Pips(att, g.MAX_ATTEMPTS)
        self.pips.pack(side="right")
        self.worth_lbl = tk.Label(sub, text="", bg=C["panel"], fg=C["muted"], font=F["small"],
                                  anchor="w")
        self.worth_lbl.pack(fill="x", pady=(4, 0))
        self.feedback = tk.Label(sub, text="", bg=C["panel"], font=F["smallb"],
                                 wraplength=COL_W - px(50), justify="left", anchor="w")
        self.feedback.pack(fill="x", pady=(4, 0))
        self.explain_btn = RetroButton(sub, "", self.show_explanation, kind="secondary",
                                       font=F["small"])

        self.hint_panel = panel(right, "Stuck?", F, fill="x", pady=(8, 0))
        self.t_hint = self.hint_panel.outer
        self.hint_text = tk.Label(self.hint_panel, text="Hints help you find the method. "
                                  "They don't cost points.", bg=C["panel"], fg=C["muted"],
                                  font=F["small"], wraplength=COL_W - px(50), justify="left",
                                  anchor="w")
        self.hint_text.pack(fill="x")
        self.hint_btn = RetroButton(self.hint_panel, "", self.next_hint, kind="secondary",
                                    font=F["small"])
        self.hint_btn.pack(fill="x", pady=(8, 0))

        self.next_btn = RetroButton(right, "CONTINUE: EXPLAIN >", self.show_short_answer,
                                    font=F["btn"])

        # ---- centre: statistics and plots ------------------------------------------
        mid = tk.Frame(body, bg=C["bg"])
        mid.pack(side="left", fill="both", expand=True, padx=14)

        stats = tk.Frame(mid, bg=C["bg"])
        stats.pack(fill="x", pady=(0, 10))
        self.t_stats = stats
        self.stat_lbls = {}
        # The unit goes in the title so the numbers always fit their boxes.
        # (Titles are typed in capitals by hand: calling .upper() would turn the
        # unit "µs" into a capital Greek Mu, which looks like "MS" = milliseconds.)
        for i, (key, title) in enumerate([("n", "RUNS"), ("mean", "MEAN (µs)"),
                                          ("std", "STD DEV (µs)"), ("sem", "STD ERR (µs)")]):
            outer = tk.Frame(stats, bg=C["border"])
            outer.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))
            stats.grid_columnconfigure(i, weight=1, uniform="s")
            inner = tk.Frame(outer, bg=C["panel"])
            inner.pack(fill="both", expand=True, padx=3, pady=3)
            tk.Label(inner, text=title, bg=C["panel"], fg=C["muted"],
                     font=F["label"]).pack(anchor="w", padx=10, pady=(7, 0))
            v = tk.Label(inner, text="—", bg=C["panel"], fg=C["text"], font=F["stat"])
            v.pack(anchor="w", padx=10, pady=(1, 7))
            self.stat_lbls[key] = v

        scope_outer = tk.Frame(mid, bg=C["border"])
        scope_outer.pack(fill="both", expand=True)
        self.t_scope = scope_outer
        scope = tk.Frame(scope_outer, bg=C["inset"])
        scope.pack(fill="both", expand=True, padx=3, pady=3)
        self.fig = Figure(figsize=(7, 5), dpi=100 * retro.UI["scale"], facecolor=C["inset"])
        self.ax_runs = self.fig.add_subplot(2, 1, 1)
        self.ax_hist = self.fig.add_subplot(2, 1, 2)
        self.fig.subplots_adjust(left=0.11, right=0.97, top=0.93, bottom=0.1, hspace=0.5)
        self.canvas = FigureCanvasTkAgg(self.fig, master=scope)
        self.canvas.get_tk_widget().configure(bg=C["inset"], highlightthickness=0)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)
        # show / hide the batch colour key; sits over the plot's top-right corner
        self.key_btn = RetroButton(scope, "", self.toggle_key, kind="secondary",
                                   font=F["label"])
        self.key_btn.config(padx=8, pady=2)
        self.key_btn.place(relx=1.0, x=-px(10), y=px(6), anchor="ne")
        self._refresh_key_btn()

        if self.bits_done:
            if self.guesses:
                self.guess_var.set(str(self.guesses[-1]))
            self.guess.config(state="disabled")
        self._refresh()
        if not self.save.flag("level1_tour_seen") and not self.bits_done:
            self.after(450, self.start_tour)

    # ------------------------------------------------------------ lab: hints
    def _hint_available(self):
        """The next hint is open once enough wrong attempts have been made."""
        return g.hint_unlocked(self.hints_shown, self.attempt)

    def next_hint(self):
        if self.hints_shown >= len(g.HINTS) or not self._hint_available():
            return
        self.hints_shown += 1
        self._hint_view = self.hints_shown - 1
        self.hint_text.config(text="%d.  %s" % (self.hints_shown, g.HINTS[self._hint_view]),
                              fg=C["text"])
        self._refresh_hint()

    def _refresh_hint(self):
        n = self.hints_shown
        if n >= len(g.HINTS):
            self.hint_btn.pack_forget()             # nothing left to reveal
        elif not self.hint_btn.winfo_ismapped():
            self.hint_btn.pack(fill="x", pady=(8, 0))
        if n >= len(g.HINTS):
            pass
        elif not self._hint_available():
            need = self.hints_shown - self.attempt
            self.hint_btn.config(text="HINT %d: AFTER %d MORE MISS%s"
                                      % (n + 1, need, "" if need == 1 else "ES"))
            self.hint_btn.set_enabled(False)
        else:
            self.hint_btn.config(text="SHOW HINT %d OF %d" % (n + 1, len(g.HINTS)))
            self.hint_btn.set_enabled(True)
        if n > 1:                                   # click the text to flip between hints
            self.hint_text.bind("<Button-1>", lambda e: self._cycle_hint())
            self.hint_text.config(cursor="hand2")

    def _cycle_hint(self):
        self._hint_view = (self._hint_view + 1) % self.hints_shown
        self.hint_text.config(text="%d.  %s\n(click to see your other hints)"
                                   % (self._hint_view + 1, g.HINTS[self._hint_view]))

    # ------------------------------------------------------- lab: the tour
    def _tour_steps(self):
        return [
            (None, "Welcome, attacker",
             "Your target is a smart lock with a secret 16-bit key. You can't see the "
             "key or the code, but you can time how long the lock takes to run.\n\n"
             "Your goal: work out how many of the 16 key bits are 1."),
            (self.t_brief, "How the lock works",
             "For every key bit the lock does a square. If the bit is 1, it also does "
             "a multiply. So the more 1 bits the key has, the longer each run takes."),
            (self.t_specs, "Your tools",
             "These are the numbers you'll need: how long one square and one multiply "
             "take. Keep them in mind."),
            (self.t_meas, "Step 1 · Measure",
             "Pick how many runs to time, then press Run batch. You can run up to "
             "%d batches. More runs give a more reliable answer." % g.MAX_BATCHES),
            (self.t_scope, "Read the results",
             "Each dot is one run. Random jitter makes the dots scatter, so one run "
             "isn't enough. The white line is the running mean: it settles down as you "
             "add runs. The yellow line in the histogram marks the mean. The KEY button "
             "in the corner hides or shows the batch colour key."),
            (self.t_stats, "The numbers",
             "The exact mean time is here. The standard error tells you how much the "
             "mean could still move. Smaller is better."),
            (self.t_sub, "Step 2 · Submit",
             "Enter how many key bits are 1. You get 3 attempts, worth 3, 2 and 1 "
             "points. You'll only be told correct or incorrect, and you can't submit "
             "the same wrong number twice."),
            (self.t_hint, "Need help?",
             "Hints are here and don't cost points. Hint 1 is open now; hint 2 unlocks "
             "after a wrong attempt and hint 3 after a second one. You can replay this "
             "tour from \"How to play\" at the top."),
        ]

    def start_tour(self):
        if not hasattr(self, "t_brief") or not self.t_brief.winfo_exists():
            return                                  # not in the lab view
        self.end_tour()
        self.save.set_flag("level1_tour_seen")
        steps = [s for s in self._tour_steps() if s[0] is None or s[0].winfo_ismapped()]
        self.tour = {"i": 0, "steps": steps, "card": None, "hl": None}
        self._tour_show()

    def end_tour(self):
        t = self.tour
        if not t:
            return
        self.tour = None
        if t["hl"] is not None:
            try:
                t["hl"].config(bg=C["border"])
            except tk.TclError:
                pass
        if t["card"] is not None:
            try:
                t["card"].destroy()
            except tk.TclError:
                pass

    def _tour_move(self, d):
        i = self.tour["i"] + d
        if i >= len(self.tour["steps"]):
            self.end_tour()
            return
        self.tour["i"] = max(0, i)
        self._tour_show()

    def _tour_show(self):
        t, F = self.tour, self.F
        if t["hl"] is not None:
            t["hl"].config(bg=C["border"])
        if t["card"] is not None:
            t["card"].destroy()
        target, title, text = t["steps"][t["i"]]
        n = len(t["steps"])
        if target is not None:
            target.config(bg=C["warn"])             # bright border = highlighted panel
        t["hl"] = target

        W = px(360)
        card = tk.Frame(self, bg=C["warn"])
        t["card"] = card
        inner = tk.Frame(card, bg=C["panel2"])
        inner.pack(fill="both", expand=True, padx=3, pady=3)
        pad = tk.Frame(inner, bg=C["panel2"])
        pad.pack(fill="both", expand=True, padx=16, pady=14)
        tk.Label(pad, text="HOW TO PLAY  ·  %d / %d" % (t["i"] + 1, n), bg=C["panel2"],
                 fg=C["warn"], font=F["label"]).pack(anchor="w")
        tk.Label(pad, text=title, bg=C["panel2"], fg=C["text"], font=F["h2"]).pack(
            anchor="w", pady=(4, 6))
        tk.Label(pad, text=text, bg=C["panel2"], fg=C["text"], font=F["small"],
                 wraplength=W - px(50), justify="left").pack(anchor="w")
        dots = Pips(pad, n, bg=C["panel2"], size=9, gap=4)
        dots.pack(anchor="w", pady=(12, 0))
        dots.set(t["i"] + 1, on="warn", off="dim")
        row = tk.Frame(pad, bg=C["panel2"])
        row.pack(fill="x", pady=(10, 0))
        last = t["i"] == n - 1
        RetroButton(row, "LET'S GO!" if last else "NEXT >", lambda: self._tour_move(1),
                    font=F["smallb"]).pack(side="right")
        if t["i"] > 0:
            RetroButton(row, "< BACK", lambda: self._tour_move(-1), kind="secondary",
                        font=F["small"]).pack(side="right", padx=6)
        if not last:
            skip = tk.Label(row, text="Skip tour", bg=C["panel2"], fg=C["muted"],
                            font=F["small"], cursor="hand2")
            skip.pack(side="left")
            skip.bind("<Button-1>", lambda e: self.end_tour())

        # place the card beside the highlighted panel
        self.update_idletasks()
        cw, ch = self.winfo_width(), self.winfo_height()
        card.place(x=0, y=0, width=W)
        card.update_idletasks()
        h = card.winfo_reqheight()
        if target is None:
            x, y = (cw - W) // 2, (ch - h) // 2
        else:
            tx = target.winfo_rootx() - self.winfo_rootx()
            ty = target.winfo_rooty() - self.winfo_rooty()
            tw, th = target.winfo_width(), target.winfo_height()
            if tx + tw / 2 < cw * 0.3:              # left column -> card on its right
                x, y = tx + tw + 16, ty
            elif tx + tw / 2 > cw * 0.7:            # right column -> card on its left
                x, y = tx - W - 16, ty
            elif th > ch * 0.4:                     # big centre panel -> inside it
                x, y = tx + tw - W - 20, ty + 20
            else:                                   # small centre element -> below it
                x, y = tx + (tw - W) // 2, ty + th + 16
            y = max(10, min(y, ch - h - 10))
        card.place(x=x, y=y, width=W)
        card.lift()

    # ------------------------------------------------------- lab: actions
    def run_batch(self):
        if self.n_batches >= g.MAX_BATCHES:
            return
        new = self.sim.run_batch(self.runs_var.get())
        self.n_batches += 1
        self.times = np.concatenate([self.times, new])
        self.batch_ids = np.concatenate([self.batch_ids, np.full(len(new), self.n_batches)])
        self._refresh()

    def clear_runs(self):
        self.times = np.empty(0)
        self.batch_ids = np.empty(0, dtype=int)
        self.n_batches = 0
        self._refresh()

    def toggle_key(self):
        self.show_key = not self.show_key
        self.save.set_flag("level1_hide_key", not self.show_key)
        self._refresh_key_btn()
        self._draw()

    def _refresh_key_btn(self):
        self.key_btn.config(text="HIDE KEY" if self.show_key else "SHOW KEY")

    def submit_bits(self):
        if self.bits_done or not self.submit_btn.enabled:
            return
        try:
            guess = int(self.guess_var.get().strip())
            if not 0 <= guess <= g.KEY_BITS:
                raise ValueError
        except ValueError:
            self.feedback.config(text="Enter a whole number from 0 to %d." % g.KEY_BITS,
                                 fg=C["warn"])
            return
        if guess in self.guesses:                   # same wrong answer again: no attempt used
            self.feedback.config(fg=C["warn"],
                                 text="Already tried %d - not counted. Pick another number."
                                      % guess)
            return
        self.attempt += 1
        self.guesses.append(guess)
        failed = False
        if guess == self.sim.ones:
            self.bit_points = g.points_for_attempt(self.attempt)
            self.bits_done = True
            self.feedback.config(fg=C["good"], text="CORRECT!  +%d points" % self.bit_points)
        elif self.attempt >= g.MAX_ATTEMPTS:
            self.bits_done = True
            failed = True
            self.feedback.config(fg=C["bad"], text="INCORRECT. No attempts left.")
        else:
            msg = "INCORRECT. Try again."
            if self.attempt < len(g.HINTS) and g.hint_unlocked(self.attempt, self.attempt):
                msg += "  Hint %d unlocked." % (self.attempt + 1)
            self.feedback.config(fg=C["bad"], text=msg)
        self._persist(attempt=self.attempt, bits_done=self.bits_done,
                      bit_points=self.bit_points, guesses=list(self.guesses))
        self._refresh()
        if failed:
            self.after(400, self.show_explanation)  # show the answer right away

    def _refresh(self):
        left = g.MAX_ATTEMPTS - self.attempt
        self.pips.set(left, on="cyan", off="dim")
        if self.bits_done:
            self.worth_lbl.config(text="")
        else:
            pts = g.points_for_attempt(self.attempt + 1)
            self.worth_lbl.config(
                text="Worth %d pts  ·  tried %s" % (pts, ", ".join(map(str, self.guesses)))
                if self.guesses else "Next correct answer: %d pts" % pts)
        if self.n_batches < g.MAX_BATCHES:
            self.run_btn.config(text="> RUN BATCH  %d/%d" % (self.n_batches + 1, g.MAX_BATCHES))
            self.run_btn.set_enabled(True)
        else:
            self.run_btn.config(text="BATCH LIMIT REACHED")
            self.run_btn.set_enabled(False)
        has_data = len(self.times) >= g.MIN_RUNS
        self.submit_btn.set_enabled(has_data and not self.bits_done)
        placeholder = "Run at least one batch first."
        if not has_data and not self.bits_done and not self.feedback.cget("text"):
            self.feedback.config(text=placeholder, fg=C["muted"])
        elif has_data and self.feedback.cget("text") == placeholder:
            self.feedback.config(text="")
        if self.bits_done:
            if not self.feedback.cget("text"):      # e.g. coming back to a saved game
                self.feedback.config(
                    fg=C["good"] if self.bit_points else C["bad"],
                    text=("CORRECT!  +%d points" % self.bit_points) if self.bit_points
                    else "INCORRECT. No attempts left.")
            self.guess.config(state="disabled")
            self.explain_btn.config(text="SEE EXPLANATION" if self.bit_points
                                    else "ANSWER & EXPLANATION")
            if not self.explain_btn.winfo_ismapped():
                self.explain_btn.pack(fill="x", pady=(8, 0))
            self.hint_panel.outer.pack_forget()     # hints are only for the bit-count puzzle
            self.next_btn.pack(fill="x", pady=(12, 0))
        self.score_lbl.config(text=self._score_text())
        self._refresh_hint()

        t = self.times
        if len(t):
            sd = t.std(ddof=1) if len(t) > 1 else 0.0
            self.stat_lbls["n"].config(text="%d" % len(t))
            self.stat_lbls["mean"].config(text=format(t.mean(), ",.1f"))
            self.stat_lbls["std"].config(text=format(sd, ",.1f"))
            self.stat_lbls["sem"].config(text="± " + format(sd / np.sqrt(len(t)), ",.1f"))
        else:
            for v in self.stat_lbls.values():
                v.config(text="—")
        self._draw()

    def _draw(self):
        a1, a2 = self.ax_runs, self.ax_hist
        a1.clear()
        a2.clear()
        style_axes(a1, "EXECUTION TIME PER RUN", "run #", "time (µs)")
        style_axes(a2, "DISTRIBUTION OF TIMES", "time (µs)", "runs")
        t = self.times
        if not len(t):
            for ax in (a1, a2):
                ax.set_xticks([])
                ax.set_yticks([])
            a1.text(0.5, 0.5, "NO MEASUREMENTS YET - PRESS  > RUN BATCH",
                    transform=a1.transAxes, ha="center", va="center", color=C["dim"],
                    fontsize=10)
            self.canvas.draw_idle()
            return

        palette = [C["cyan"], C["amber"], C["good"], "#d2a8ff", "#ff9b6b",
                   "#7ee0e6", "#ff6fae", "#b8f35a", "#6f8cff", "#e8e8e8"]   # one per batch
        x = np.arange(1, len(t) + 1)
        for b in np.unique(self.batch_ids):
            m = self.batch_ids == b
            a1.scatter(x[m], t[m], s=22, marker="s", color=palette[(b - 1) % len(palette)],
                       linewidths=0, label="batch %d" % b)
        running = np.cumsum(t) / x
        a1.plot(x, running, color=C["text"], linewidth=2.5, label="running mean")
        a1.set_xlim(0, max(len(t) + 1, g.MIN_RUNS))
        pad = max(3 * g.JITTER_SIGMA_US, 1)
        a1.set_ylim(t.mean() - 1.6 * pad, t.mean() + 1.6 * pad)
        if self.show_key:
            leg = a1.legend(loc="upper right", fontsize=7, facecolor=C["panel2"],
                            edgecolor=C["border"], labelcolor=C["text"], ncol=4)
            leg.get_frame().set_alpha(0.95)

        bins = max(10, min(30, len(t) // 4))
        a2.hist(t, bins=bins, color=C["cyan"], edgecolor=C["inset"], linewidth=1)
        mean = t.mean()
        sem = t.std(ddof=1) / np.sqrt(len(t)) if len(t) > 1 else 0
        a2.axvspan(mean - sem, mean + sem, color=C["warn"], alpha=0.25, linewidth=0)
        a2.axvline(mean, color=C["warn"], linewidth=2.5)
        a2.text(mean, a2.get_ylim()[1] * 0.92, "  mean = %s µs" % format(mean, ",.1f"),
                color=C["warn"], fontsize=8, va="top")
        self.canvas.draw_idle()

    # ------------------------------------------------- lab: answer + explanation
    def _close_modal(self):
        if self._modal_close is not None:
            self._modal_close()

    def _modal(self, label, title, width=640):
        """Overlay with a centred card on top of the current view.
        Returns (body_frame, close_fn)."""
        self.end_tour()
        self._close_modal()
        shade = tk.Frame(self.stage, bg=C["inset"])
        shade.place(x=0, y=0, relwidth=1, relheight=1)
        box = tk.Frame(shade, bg=C["amber"])
        box.place(relx=0.5, rely=0.5, anchor="center", width=px(width))
        inner = tk.Frame(box, bg=C["panel2"])
        inner.pack(fill="both", expand=True, padx=3, pady=3)
        body = tk.Frame(inner, bg=C["panel2"])
        body.pack(fill="both", expand=True, padx=24, pady=18)
        tk.Label(body, text=label, bg=C["panel2"], fg=C["amber"],
                 font=self.F["label"]).pack(anchor="w")
        tk.Label(body, text=title, bg=C["panel2"], fg=C["text"],
                 font=self.F["h1"]).pack(anchor="w", pady=(2, 10))

        def close():
            self._modal_close = None
            try:
                self.root.unbind("<Escape>")
                shade.destroy()
            except tk.TclError:
                pass
        self._modal_close = close
        self.root.bind("<Escape>", lambda e: close())
        return body, close

    def show_explanation(self):
        """The correct bit count and how to get it from the player's own data."""
        if not self.bits_done:
            return
        F = self.F
        k = self.sim.ones
        solved = self.bit_points > 0
        body, close = self._modal("THE ANSWER", "The key has %d one-bits" % k)
        W = px(590)

        def para(text, color=C["text"], fnt=None, pady=(0, 8)):
            tk.Label(body, text=text, bg=C["panel2"], fg=color, font=fnt or F["small"],
                     wraplength=W, justify="left", anchor="w").pack(fill="x", pady=pady)

        if self.guesses:
            para("Your answers: %s" % ", ".join(str(x) for x in self.guesses)
                 + ("" if solved else "   -   Correct answer: %d" % k),
                 C["good"] if solved else C["bad"], F["smallb"])

        squares = g.KEY_BITS * g.T_S_US
        para("Why: every run does 16 squares. Each 1 bit adds one multiply, so the "
             "total time grows by one multiply time for every 1 bit:")
        para("T = 16 × t_S + (number of 1 bits) × t_M + jitter\n"
             "T = 16 × %.0f + %d × %.0f = %s µs  (without jitter)"
             % (g.T_S_US, k, g.T_M_US, format(squares + k * g.T_M_US, ",.0f")),
             C["warn"], F["smallb"])

        if len(self.times):
            m = self.times.mean()
            est = (m - squares) / g.T_M_US
            para("Working it out from YOUR measurements:", C["muted"], F["smallb"],
                 pady=(2, 2))
            para("1. Mean of your %d runs          = %s µs\n"
                 "2. Subtract 16 squares (16 × %.0f) = %s µs\n"
                 "3. Divide by one multiply (%.0f)   = %.2f\n"
                 "4. Round to a whole number         = %d"
                 % (len(self.times), format(m, ",.1f"), g.T_S_US,
                    format(m - squares, ",.1f"), g.T_M_US, est, round(est)))
            if round(est) != k:
                para("Your mean was still too noisy to land on the right number. "
                     "More runs would have pulled the mean closer to the true value.",
                     C["muted"])
        para("A single run is off by about ±1 multiply because of jitter, which is why "
             "you have to average many runs. Timing tells you HOW MANY bits are 1, "
             "but not WHERE they are.", pady=(2, 12))
        RetroButton(body, "GOT IT", close, font=F["btn"]).pack(anchor="e")

    # =========================================================================
    # View 2: short answer
    # =========================================================================
    def show_short_answer(self):
        self._clear()
        F = self.F
        self._title("Explain your reasoning")
        self.help_btn.pack_forget()
        wrap = tk.Frame(self.stage, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        q = panel(wrap, "Short answer", F, fill="both", expand=True)
        tk.Label(q, justify="left", wraplength=px(1000), bg=C["panel"], fg=C["text"], font=F["h2"],
                 text=("In a few full sentences: why does the lock's total execution time "
                       "reveal how many key bits are 1? Is there anything about the key "
                       "that timing cannot tell you, and why?")).pack(anchor="w")
        tk.Label(q, text="Answer in your own words. You can submit once.", bg=C["panel"],
                 fg=C["muted"], font=F["small"]).pack(anchor="w", pady=(4, 10))
        self.answer = tk.Text(q, height=8, wrap="word", bg=C["inset"], fg=C["text"],
                              insertbackground=C["amber"], insertwidth=3, relief="flat",
                              font=font(12), padx=12, pady=10, highlightthickness=3,
                              highlightbackground=C["border"], highlightcolor=C["amber"])
        self.answer.pack(fill="both", expand=True)
        self.answer.focus_set()

        bottom = tk.Frame(q, bg=C["panel"])
        bottom.pack(fill="x", pady=(10, 0))
        self.wc = tk.Label(bottom, text="0 words", bg=C["panel"], fg=C["muted"], font=F["small"])
        self.wc.pack(side="left")
        self.sa_submit = RetroButton(bottom, "SUBMIT EXPLANATION", self.submit_answer,
                                     kind="blue", font=F["btn"])
        self.sa_submit.pack(side="right")
        self.answer.bind("<KeyRelease>", lambda e: self.wc.config(
            text="%d words" % len(self.answer.get("1.0", "end").split()), fg=C["muted"]))
        self.sa_result = tk.Frame(q, bg=C["panel"])
        self.sa_result.pack(fill="x", pady=(12, 0))

    def submit_answer(self):
        text = self.answer.get("1.0", "end").strip()
        if len(text.split()) < 12:
            self.wc.config(text="Please write at least a couple of full sentences.",
                           fg=C["warn"])
            return
        F = self.F
        self.sa_submit.set_enabled(False)
        self.answer.config(state="disabled", fg=C["muted"])
        results = g.score_short_answer(text)
        self.sa_points = sum(1 for r in results if r[1])
        self.score_lbl.config(text=self._score_text())
        if not self.practice:                        # the level is now complete
            self.save.mark_complete(
                "level1", attempt=self.attempt, bits_done=True, bit_points=self.bit_points,
                sa_points=self.sa_points, score=self.bit_points + self.sa_points,
                max_score=MAX_SCORE, answer=text)

        tk.Label(self.sa_result, text="Rubric check: %d / %d" % (self.sa_points, len(results)),
                 bg=C["panel"], fg=C["text"], font=F["h2"]).pack(anchor="w", pady=(0, 6))
        for _, met, desc, hint in results:
            row = tk.Frame(self.sa_result, bg=C["panel"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text="[OK]" if met else "[ X]", bg=C["panel"],
                     fg=C["good"] if met else C["bad"], font=F["bodyb"]).pack(side="left",
                                                                             padx=(0, 8))
            tk.Label(row, text=desc if met else "Missing - hint: %s" % hint, bg=C["panel"],
                     fg=C["text"] if met else C["muted"], font=F["body"], anchor="w",
                     justify="left", wraplength=px(960)).pack(side="left", fill="x")
        RetroButton(self.sa_result, "FINISH LEVEL >", self.show_results,
                    font=F["btn"]).pack(anchor="e", pady=(10, 0))

    # =========================================================================
    # View 3: results
    # =========================================================================
    def show_results(self):
        self._clear()
        F = self.F
        self._title("Level complete")
        self.help_btn.pack_forget()
        wrap = tk.Frame(self.stage, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        top = tk.Frame(wrap, bg=C["bg"])
        top.pack(fill="x")
        cards = [("Bit count", "%d / 3" % self.bit_points,
                  "solved on attempt %d" % self.attempt if self.bit_points else "not solved"),
                 ("Explanation", "%d / 3" % self.sa_points, "rubric points 1 & 2"),
                 ("Level total", "%d / %d" % (self.bit_points + self.sa_points, MAX_SCORE), "")]
        for i, (title, val, sub) in enumerate(cards):
            outer = tk.Frame(top, bg=C["border"])
            outer.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 12, 0))
            top.grid_columnconfigure(i, weight=1, uniform="r")
            inner = tk.Frame(outer, bg=C["panel"])
            inner.pack(fill="both", expand=True, padx=3, pady=3)
            tk.Label(inner, text=title.upper(), bg=C["panel"], fg=C["muted"],
                     font=F["label"]).pack(anchor="w", padx=16, pady=(12, 0))
            tk.Label(inner, text=val, bg=C["panel"], fg=C["amber"] if i == 2 else C["text"],
                     font=F["big"]).pack(anchor="w", padx=16)
            tk.Label(inner, text=sub, bg=C["panel"], fg=C["muted"],
                     font=F["small"]).pack(anchor="w", padx=16, pady=(0, 12))

        k = self.sim.ones
        reveal = panel(wrap, "What you learned about the key", F, fill="x", pady=(16, 0))
        tk.Label(reveal, bg=C["panel"], fg=C["text"], font=F["body"], justify="left",
                 wraplength=px(1060), text=(
                     "The key has %d one-bits, so every run did 16 squares and %d "
                     "multiplies:   T ≈ 16 × %.0f + %d × %.0f = %s µs.   Averaging many "
                     "runs cancels the jitter, so the mean pins down the number of "
                     "multiplies." % (k, k, g.T_S_US, k, g.T_M_US,
                                      format(16 * g.T_S_US + k * g.T_M_US, ",.0f")))).pack(
            anchor="w")
        boxes = tk.Frame(reveal, bg=C["panel"])
        boxes.pack(anchor="w", pady=(14, 6))
        for _ in range(g.KEY_BITS):
            tk.Label(boxes, text="?", width=3, bg=C["inset"], fg=C["warn"], font=F["stat"],
                     highlightthickness=2, highlightbackground=C["border"]).pack(
                side="left", padx=2, ipady=5)
        tk.Label(reveal, bg=C["panel"], fg=C["muted"], font=F["body"],
                 text="%d of these 16 bits are 1 - but timing can't tell you which ones. "
                      "A power trace can.  ->  Level 2: Simple Power Analysis" % k).pack(
            anchor="w", pady=(4, 0))

        btns = tk.Frame(wrap, bg=C["bg"])
        btns.pack(fill="x", pady=(16, 0))
        first_time = not self.practice
        RetroButton(btns, "BACK TO MENU",
                    lambda: self.app.show_menu(message="LEVEL 2 UNLOCKED!" if first_time else None),
                    font=F["btn"]).pack(side="right")

    def destroy(self):
        self.end_tour()
        super().destroy()
