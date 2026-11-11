"""
screen_power.py -- Levels 2 and 3 (PROTOTYPES): power-trace attacks, in the
retro style. Playable for demonstrations; still under development.

    Level 2  Simple power analysis: read all 16 key bits from ONE clean trace.
    Level 3  Noise and protection: average many noisy traces to read the key
             from the standard lock; see why the protected lock resists.

The traces come from sim.py (numbers in config.py). The text, hints and rubric
are in power_rules.py. The flow and scoring match Level 1:

    lab (inspect / acquire, submit the key)  ->  short answer  ->  results

  * key: 3 attempts worth 3 / 2 / 1 points; the same wrong key can't be
    submitted twice; feedback is only correct / incorrect
  * hint 1 is open from the start, hint 2 after 1 wrong attempt, hint 3 after 2
  * explanation: 7 points (power_rules RUBRIC). The full explanation only
    unlocks after it is submitted, so it can't be copied into the answer.
  * 70% (progress.PASS_FRACTION) passes; below that the level is failed and the
    player gets a new seed. RESTART after an attempt also gives a new seed.
  * a passed level can be replayed as PRACTICE (nothing is recorded)
"""

import tkinter as tk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import audio
import config as cfg
import game_with_hints as g
import power_rules
import progress
import retro
import sim
from retro import C, Pips, RetroButton, font, panel, px, style_axes, topbar

BIT_MAX = g.points_for_attempt(1)        # 3 points for the key
COL_W_BASE = 290                         # left / right column width (96-DPI pixels)
SAMPLE_US = cfg.T_S_US / cfg.SAMPLES_PER_S   # one trace sample, in µs
ZOOMS = (1, 2, 4, 8)                     # how many times the view can be magnified
NEXT_MESSAGE = {"level2": "LEVEL 3 UNLOCKED!", "level3": "LEVEL 3 COMPLETE!"}


class PowerLevelScreen(tk.Frame):
    LEVEL_ID = None          # "level2" / "level3"
    NOISY = False            # Level 3: noisy traces, averaging, two devices

    def __init__(self, master, app):
        super().__init__(master, bg=C["bg"])
        self.app, self.save, self.F = app, app.save, app.fonts
        self.root = app.root
        self.rules = power_rules.LEVELS[self.LEVEL_ID]
        self.max_score = BIT_MAX + self.rules["sa_max"]
        self.practice = self.save.is_complete(self.LEVEL_ID)
        self.target = sim.Target(sim.seed_from_student_id(str(self.save.seed)))
        self.key = "".join(str(b) for b in self.target.key_bits)

        # --- state of this visit ------------------------------------------------
        self.attempt = 0
        self.bit_points = 0
        self.sa_points = 0
        self.bits_done = False
        self.sa_done = False
        self.answer_draft = ""
        self.guesses = []                       # bit strings submitted, in order
        self.bits = [0] * cfg.KEY_BITS          # the player's current key guess
        self.hints_shown = 0
        self._hint_view = 0
        self._modal_close = None
        self.zoom, self.pan = 0, 0.0            # index into ZOOMS, view start (0..1)
        if self.NOISY:
            self.device = "standard"
            self.dev = {d: {"sum": None, "count": 0, "used": 0, "last": None}
                        for d in ("standard", "protected")}
            self.show_single = True
        else:
            self.trace = self.target.acquire_trace(cfg.L2_NOISE_SIGMA)   # one per seed
        if not self.practice:                   # resume where the player left off
            rec = self.save.level(self.LEVEL_ID)
            self.attempt = int(rec.get("attempt", 0))
            self.bit_points = int(rec.get("bit_points", 0))
            self.bits_done = bool(rec.get("bits_done", False))
            self.guesses = [str(x) for x in rec.get("guesses", [])]

        # --- top bar ------------------------------------------------------------------
        self.bar, right = topbar(self, self.F, self.rules["kicker"], "", self.app.show_menu)
        tools = tk.Frame(self.bar, bg=C["bg"])
        tools.pack(side="right", padx=(0, 14))
        self.restart_btn = RetroButton(tools, "RESTART", self.confirm_restart,
                                       kind="secondary", font=self.F["smallb"])
        self.restart_btn.grid(row=0, column=0, padx=(0, 8))
        self.help_btn = RetroButton(tools, "?  HOW TO PLAY", self.show_help,
                                    kind="secondary", font=self.F["smallb"])
        self.help_btn.grid(row=0, column=1)
        self.score_lbl = tk.Label(right, text="", bg=C["bg"], fg=C["text"], font=self.F["bodyb"])
        self.score_lbl.pack(anchor="e")
        sub = "PRACTICE: SCORE NOT RECORDED" if self.practice else "SEED %s" % self.save.seed
        tk.Label(right, text=sub, bg=C["bg"], fg=C["amber"] if self.practice else C["muted"],
                 font=self.F["label"]).pack(anchor="e")

        self.stage = tk.Frame(self, bg=C["bg"])
        self.stage.pack(fill="both", expand=True)
        self.show_lab()
        if not self.save.flag(self.LEVEL_ID + "_help_seen") and not self.bits_done:
            self.save.set_flag(self.LEVEL_ID + "_help_seen")
            self.after(400, self.show_help)

    # ------------------------------------------------------------------ utils
    def _clear(self):
        self._close_modal()
        for w in self.stage.winfo_children():
            w.destroy()

    def _title(self, text):
        self.bar.title_lbl.config(text=text)

    def _score_text(self):
        return "SCORE  %d / %d" % (self.bit_points + self.sa_points, self.max_score)

    def _persist(self, **fields):
        if not self.practice:
            self.save.update_level(self.LEVEL_ID, **fields)

    def _label(self, parent, text, width, fg=None, fnt=None, bg=None):
        tk.Label(parent, text=text, justify="left", wraplength=width, bg=bg or C["panel"],
                 fg=fg or C["text"], font=fnt or self.F["small"]).pack(anchor="w")

    # =========================================================================
    # View 1: the lab
    # =========================================================================
    def show_lab(self):
        self._clear()
        F = self.F
        COL_W = px(COL_W_BASE)
        self._title(self.rules["lab_title"])
        self.help_btn.grid()
        self.restart_btn.grid()
        self.score_lbl.config(text=self._score_text())

        body = tk.Frame(self.stage, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        # ---- left column: briefing, specs, objective, hints -------------------------
        left = tk.Frame(body, bg=C["bg"], width=COL_W)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        brief = panel(left, "Mission briefing", F, fill="x")
        self._label(brief, self.rules["brief"], COL_W - px(50))
        self._label(brief, "\nGOAL: " + self.rules["objective"], COL_W - px(50),
                    fg=C["amber_hi"])

        specs = panel(left, "Known device specs", F, fill="x", pady=(8, 0))
        rows = [("Square  S", "%d samples" % cfg.SAMPLES_PER_S),
                ("Multiply M", "%d samples" % cfg.SAMPLES_PER_M),
                ("Gap after each bit", "%d samples" % cfg.GAP_SAMPLES),
                ("1 sample", "%g µs" % SAMPLE_US)]
        for k, v in rows:
            row = tk.Frame(specs, bg=C["panel"])
            row.pack(fill="x", pady=1)
            tk.Label(row, text=k, bg=C["panel"], fg=C["muted"], font=F["small"]).pack(side="left")
            tk.Label(row, text=v, bg=C["panel"], fg=C["amber"], font=F["smallb"]).pack(side="right")

        self.hint_panel = panel(left, "Stuck?", F, fill="x", pady=(8, 0))
        self.hint_text = tk.Label(self.hint_panel, text="Hints help you find the method. "
                                  "They don't cost points.", bg=C["panel"], fg=C["muted"],
                                  font=F["small"], wraplength=COL_W - px(50), justify="left",
                                  anchor="w")
        self.hint_text.pack(fill="x")
        self.hint_btn = RetroButton(self.hint_panel, "", self.next_hint, kind="secondary",
                                    font=F["small"])
        self.hint_btn.pack(fill="x", pady=(8, 0))

        # ---- right column: acquire (Level 3), submit -----------------------------------
        right = tk.Frame(body, bg=C["bg"], width=COL_W)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        step = 1
        if self.NOISY:
            self._build_acquire(right, COL_W)
            step = 2

        sub = panel(right, "%d · Submit the key" % step, F, fill="x",
                    pady=(8, 0) if self.NOISY else 0)
        tk.Label(sub, text=("The STANDARD lock's key. " if self.NOISY else "")
                 + "Bit 15 first; click a box to flip it.", bg=C["panel"], fg=C["text"],
                 font=F["small"], wraplength=COL_W - px(50), justify="left").pack(anchor="w")
        grid = tk.Frame(sub, bg=C["panel"])
        grid.pack(fill="x", pady=(6, 8))
        self.bit_cells = []
        for i in range(cfg.KEY_BITS):
            r, c = divmod(i, 8)
            tk.Label(grid, text=str(cfg.KEY_BITS - 1 - i), bg=C["panel"], fg=C["muted"],
                     font=font(7)).grid(row=2 * r, column=c, pady=(4 if r else 0, 0))
            cell = tk.Label(grid, text="0", width=2, bg=C["inset"], fg=C["dim"],
                            font=F["stat"], cursor="hand2", highlightthickness=2,
                            highlightbackground=C["border"])
            cell.grid(row=2 * r + 1, column=c, padx=1, ipady=1)
            cell.bind("<Button-1>", lambda e, i=i: self.flip_bit(i))
            self.bit_cells.append(cell)
            grid.grid_columnconfigure(c, weight=1)
        self.submit_btn = RetroButton(sub, "SUBMIT KEY", self.submit_bits, kind="blue",
                                      font=F["btn"], sound=None)
        self.submit_btn.pack(fill="x")
        att = tk.Frame(sub, bg=C["panel"])
        att.pack(fill="x", pady=(8, 0))
        tk.Label(att, text="Attempts", bg=C["panel"], fg=C["muted"], font=F["small"]).pack(side="left")
        self.pips = Pips(att, g.MAX_ATTEMPTS)
        self.pips.pack(side="right")
        self.worth_lbl = tk.Label(sub, text="", bg=C["panel"], fg=C["muted"], font=F["small"],
                                  anchor="w", justify="left")
        self.worth_lbl.pack(fill="x", pady=(4, 0))
        self.feedback = tk.Label(sub, text="", bg=C["panel"], font=F["smallb"],
                                 wraplength=COL_W - px(50), justify="left", anchor="w")
        self.feedback.pack(fill="x", pady=(4, 0))
        self.explain_btn = RetroButton(sub, "", self.show_explanation, kind="secondary",
                                       font=F["small"])
        self.next_btn = RetroButton(right, "CONTINUE: EXPLAIN >", self.show_short_answer,
                                    font=F["btn"])

        # ---- centre: view controls + the scope ------------------------------------------
        mid = tk.Frame(body, bg=C["bg"])
        mid.pack(side="left", fill="both", expand=True, padx=14)
        tools = tk.Frame(mid, bg=C["bg"])
        tools.pack(fill="x", pady=(0, 8))
        if self.NOISY:
            self.dev_btns = {}
            for d in ("standard", "protected"):
                b = RetroButton(tools, d.upper(), lambda d=d: self.set_device(d),
                                kind="secondary", font=F["small"])
                b.pack(side="left", padx=(0, 6))
                self.dev_btns[d] = b
        for text, cmd in (("ALL", lambda: self.set_zoom(0)), (">", lambda: self.pan_view(1)),
                          ("<", lambda: self.pan_view(-1)), ("+", lambda: self.set_zoom(self.zoom + 1)),
                          ("-", lambda: self.set_zoom(self.zoom - 1))):
            RetroButton(tools, text, cmd, kind="secondary", font=F["smallb"]).pack(
                side="right", padx=(6, 0))
        tk.Label(tools, text="ZOOM", bg=C["bg"], fg=C["muted"], font=F["label"]).pack(
            side="right")

        scope_outer = tk.Frame(mid, bg=C["border"])
        scope_outer.pack(fill="both", expand=True)
        scope = tk.Frame(scope_outer, bg=C["inset"])
        scope.pack(fill="both", expand=True, padx=3, pady=3)
        self.fig = Figure(figsize=(7, 5), dpi=100 * retro.UI["scale"], facecolor=C["inset"])
        self.ax = self.fig.add_subplot(1, 1, 1)
        self.fig.subplots_adjust(left=0.11, right=0.97, top=0.92, bottom=0.11)
        self.canvas = FigureCanvasTkAgg(self.fig, master=scope)
        self.canvas.get_tk_widget().configure(bg=C["inset"], highlightthickness=0)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)

        if self.bits_done and self.guesses:
            self.bits = [int(b) for b in self.guesses[-1]]
        self._refresh()

    def _build_acquire(self, right, COL_W):
        F = self.F
        acq = panel(right, "1 · Acquire traces", F, fill="x")
        self.dev_lbl = tk.Label(acq, text="", bg=C["panel"], fg=C["amber"], font=F["smallb"],
                                anchor="w")
        self.dev_lbl.pack(fill="x")
        self.n_var = tk.IntVar(value=10)
        hdr = tk.Frame(acq, bg=C["panel"])
        hdr.pack(fill="x", pady=(4, 0))
        tk.Label(hdr, text="Traces per batch (1-%d)" % cfg.L3_MAX_PER_BATCH, bg=C["panel"],
                 fg=C["text"], font=F["small"]).pack(side="left")
        tk.Label(hdr, textvariable=self.n_var, bg=C["panel"], fg=C["amber"],
                 font=F["stat"]).pack(side="right")
        tk.Scale(acq, from_=1, to=cfg.L3_MAX_PER_BATCH, orient="horizontal",
                 variable=self.n_var, showvalue=0, bg=C["amber"], troughcolor=C["inset"],
                 highlightthickness=0, bd=0, width=16, activebackground=C["amber_hi"],
                 sliderrelief="raised", sliderlength=26, length=COL_W - px(50)).pack(
            fill="x", pady=(6, 2))
        self.acq_btn = RetroButton(acq, "> ACQUIRE", self.acquire, font=F["btn"])
        self.acq_btn.pack(fill="x", pady=(6, 4))
        row = tk.Frame(acq, bg=C["panel"])
        row.pack(fill="x")
        RetroButton(row, "CLEAR AVERAGE", self.clear_average, kind="secondary",
                    font=F["small"]).pack(side="left", fill="x", expand=True)
        self.single_btn = RetroButton(row, "", self.toggle_single, kind="secondary",
                                      font=F["small"])
        self.single_btn.pack(side="left", padx=(6, 0))

    # ------------------------------------------------------------ lab: actions
    def flip_bit(self, i):
        if self.bits_done:
            return
        audio.play("click")
        self.bits[i] ^= 1
        self._refresh_bits()

    def _refresh_bits(self):
        for b, cell in zip(self.bits, self.bit_cells):
            cell.config(text=str(b), fg=C["amber_hi"] if b else C["dim"],
                        highlightbackground=C["amber"] if b else C["border"])

    def set_device(self, d):
        self.device = d
        self._refresh()

    def acquire(self):
        st = self.dev[self.device]
        n = min(int(self.n_var.get()), cfg.L3_MAX_TRACES - st["used"])
        if n <= 0:
            audio.play("wrong")
            return
        protected = self.device == "protected"
        for _ in range(n):
            tr = self.target.acquire_trace(cfg.L3_NOISE_SIGMA, protected)
            st["sum"] = tr.copy() if st["sum"] is None else st["sum"] + tr
            st["count"] += 1
            st["used"] += 1
            st["last"] = tr
        self._refresh()

    def clear_average(self):
        st = self.dev[self.device]                 # the trace budget is NOT refunded
        st["sum"], st["count"], st["last"] = None, 0, None
        self._refresh()

    def toggle_single(self):
        self.show_single = not self.show_single
        self._refresh()

    def set_zoom(self, z):
        z = max(0, min(len(ZOOMS) - 1, z))
        centre = self.pan + 0.5 / ZOOMS[self.zoom]
        self.zoom = z
        self.pan = centre - 0.5 / ZOOMS[z]
        self._clamp_pan()
        self._draw()

    def pan_view(self, d):
        self.pan += d * 0.5 / ZOOMS[self.zoom]      # half a screen per click
        self._clamp_pan()
        self._draw()

    def _clamp_pan(self):
        self.pan = max(0.0, min(1.0 - 1.0 / ZOOMS[self.zoom], self.pan))

    def submit_bits(self):
        if self.bits_done:
            return
        if self.NOISY and not self.dev["standard"]["count"]:
            audio.play("wrong")
            self.feedback.config(fg=C["warn"], text="Acquire some standard-lock traces first.")
            return
        guess = "".join(map(str, self.bits))
        if guess in self.guesses:
            audio.play("wrong")
            self.feedback.config(fg=C["warn"],
                                 text="Already tried this key - not counted. Change some bits.")
            return
        self.attempt += 1
        self.guesses.append(guess)
        right = guess == self.key
        audio.play("correct" if right else "wrong")
        if right:
            self.bit_points = g.points_for_attempt(self.attempt)
            self.bits_done = True
            self.feedback.config(fg=C["good"], text="CORRECT!  +%d points" % self.bit_points)
        elif self.attempt >= g.MAX_ATTEMPTS:
            self.bits_done = True
            self.feedback.config(fg=C["bad"], text="INCORRECT. No attempts left.")
        else:
            msg = "INCORRECT. Try again."
            if self.attempt < len(self.rules["hints"]):
                msg += "  Hint %d unlocked." % (self.attempt + 1)
            self.feedback.config(fg=C["bad"], text=msg)
        self._persist(attempt=self.attempt, bits_done=self.bits_done,
                      bit_points=self.bit_points, guesses=list(self.guesses))
        self._refresh()

    # ------------------------------------------------------------- lab: hints
    def _hint_available(self):
        return g.hint_unlocked(self.hints_shown, self.attempt)

    def next_hint(self):
        hints = self.rules["hints"]
        if self.hints_shown >= len(hints) or not self._hint_available():
            return
        self.hints_shown += 1
        self._hint_view = self.hints_shown - 1
        self.hint_text.config(text="%d.  %s" % (self.hints_shown, hints[self._hint_view]),
                              fg=C["text"])
        self._refresh_hint()

    def _refresh_hint(self):
        hints, n = self.rules["hints"], self.hints_shown
        if n >= len(hints):
            self.hint_btn.pack_forget()
        elif not self._hint_available():
            need = n - self.attempt
            self.hint_btn.config(text="HINT %d: AFTER %d MORE MISS%s"
                                      % (n + 1, need, "" if need == 1 else "ES"))
            self.hint_btn.set_enabled(False)
        else:
            self.hint_btn.config(text="SHOW HINT %d OF %d" % (n + 1, len(hints)))
            self.hint_btn.set_enabled(True)
        if n > 1:
            self.hint_text.bind("<Button-1>", lambda e: self._cycle_hint())
            self.hint_text.config(cursor="hand2")

    def _cycle_hint(self):
        hints = self.rules["hints"]
        self._hint_view = (self._hint_view + 1) % self.hints_shown
        self.hint_text.config(text="%d.  %s\n(click to see your other hints)"
                                   % (self._hint_view + 1, hints[self._hint_view]))

    # ------------------------------------------------------------ lab: refresh
    def _refresh(self):
        self.pips.set(g.MAX_ATTEMPTS - self.attempt, on="cyan", off="dim")
        if self.bits_done:
            self.worth_lbl.config(text="")
            if not self.feedback.cget("text"):
                self.feedback.config(
                    fg=C["good"] if self.bit_points else C["bad"],
                    text=("CORRECT!  +%d points" % self.bit_points) if self.bit_points
                    else "INCORRECT. No attempts left.")
            self.submit_btn.set_enabled(False)
            self.explain_btn.config(text="SEE EXPLANATION" if self.sa_done else "SEE THE ANSWER")
            if not self.explain_btn.winfo_ismapped():
                self.explain_btn.pack(fill="x", pady=(8, 0))
            self.hint_panel.outer.pack_forget()
            self.next_btn.pack(fill="x", pady=(12, 0))
        else:
            self.worth_lbl.config(text="Next correct answer: %d pts"
                                  % g.points_for_attempt(self.attempt + 1)
                                  + ("  ·  tried %d" % len(self.guesses) if self.guesses else ""))
            self.submit_btn.set_enabled(True)
        self._refresh_bits()
        self.score_lbl.config(text=self._score_text())
        self._refresh_hint()
        if self.NOISY:
            st = self.dev[self.device]
            self.dev_lbl.config(text="%s  ·  %d / %d USED"
                                % (self.device.upper(), st["used"], cfg.L3_MAX_TRACES))
            left = cfg.L3_MAX_TRACES - st["used"]
            self.acq_btn.config(text="> ACQUIRE" if left else "BUDGET USED UP")
            self.acq_btn.set_enabled(left > 0)
            self.single_btn.config(text="HIDE SINGLE" if self.show_single else "SHOW SINGLE")
            for d, b in self.dev_btns.items():
                sel = d == self.device
                b.config(bg=C["amber"] if sel else C["panel2"],
                         fg="#1a1000" if sel else C["text"])
                b._bg, b._fg = (C["amber"], "#1a1000") if sel else (C["panel2"], C["text"])
        self._draw()

    def _draw(self):
        ax = self.ax
        ax.clear()
        if self.NOISY:
            st = self.dev[self.device]
            title = "%s LOCK - AVERAGE OF %d TRACE%s" % (
                self.device.upper(), st["count"], "" if st["count"] == 1 else "S")
        else:
            title = "ONE POWER TRACE"
        style_axes(ax, title, "time (µs)", "supply current")
        # the protected lock's trace is longer: it multiplies on every bit
        n = len(self.target._clean[self.NOISY and self.device == "protected"])
        x = np.arange(n) * SAMPLE_US
        if self.NOISY:
            if not st["count"]:
                ax.set_xticks([])
                ax.set_yticks([])
                ax.text(0.5, 0.5, "NO TRACES YET - PRESS  > ACQUIRE", transform=ax.transAxes,
                        ha="center", va="center", color=C["dim"], fontsize=10)
                self.canvas.draw_idle()
                return
            avg = st["sum"] / st["count"]
            if self.show_single and st["last"] is not None:
                ax.plot(x, st["last"], color=C["muted"], linewidth=0.6, alpha=0.35,
                        label="latest single trace")
            ax.plot(x, avg, color=C["cyan"], linewidth=1.8, drawstyle="steps-mid",
                    label="average of %d" % st["count"])
            ax.legend(loc="upper right", fontsize=7, facecolor=C["panel2"],
                      edgecolor=C["border"], labelcolor=C["text"])
            lo, hi = np.percentile(avg, [1, 99])
        else:
            ax.plot(x, self.trace, color=C["cyan"], linewidth=1.3, drawstyle="steps-mid")
            lo, hi = self.trace.min(), self.trace.max()
        pad = max(4.0, 0.15 * (hi - lo))
        ax.set_ylim(min(lo, 0) - pad, hi + pad)
        span = x[-1] / ZOOMS[self.zoom]
        x0 = self.pan * x[-1]
        ax.set_xlim(x0, x0 + span)
        self.canvas.draw_idle()

    # ------------------------------------------------------------- modals
    def _close_modal(self):
        if self._modal_close is not None:
            self._modal_close()

    def _modal(self, label, title, width=640):
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

    def _para(self, body, text, color=None, fnt=None, pady=(0, 8)):
        tk.Label(body, text=text, bg=C["panel2"], fg=color or C["text"],
                 font=fnt or self.F["small"], wraplength=px(590), justify="left",
                 anchor="w").pack(fill="x", pady=pady)

    def show_help(self):
        body, close = self._modal("HOW TO PLAY  ·  PROTOTYPE", self.rules["lab_title"])
        steps = ["This level is a PROTOTYPE: it is playable for demonstrations and "
                 "still under development.", self.rules["brief"]]
        if self.NOISY:
            steps.append("Use ACQUIRE to collect traces (budget: %d per lock). The plot shows "
                         "their average. Switch locks with the buttons above the plot."
                         % cfg.L3_MAX_TRACES)
        steps.append("Use the ZOOM buttons (+ / - and < >) above the plot to look closely. Click "
                     "the 16 bit boxes to set your key, then SUBMIT KEY. You have 3 "
                     "attempts worth 3, 2 and 1 points, and you'll only be told correct or "
                     "incorrect. Afterwards you explain your method (7 points).")
        for s in steps:
            self._para(body, s)
        RetroButton(body, "LET'S GO!", close, font=self.F["btn"]).pack(anchor="e", pady=(6, 0))

    def _key_boxes(self, parent, bg):
        """The key as 16 boxes with S / SM under each bit."""
        row = tk.Frame(parent, bg=bg)
        row.pack(anchor="w", pady=(4, 8))
        for i, b in enumerate(self.key):
            col = tk.Frame(row, bg=bg)
            col.pack(side="left", padx=2)
            tk.Label(col, text=b, width=2, bg=C["inset"], fg=C["amber_hi"] if b == "1" else C["muted"],
                     font=self.F["stat"], highlightthickness=2,
                     highlightbackground=C["amber"] if b == "1" else C["border"]).pack()
            tk.Label(col, text="SM" if b == "1" else "S", bg=bg, fg=C["muted"],
                     font=font(7)).pack()

    def show_explanation(self):
        if not self.bits_done:
            return
        body, close = self._modal("THE ANSWER", "The secret key")
        solved = self.bit_points > 0
        self._key_boxes(body, C["panel2"])
        self._para(body, "Your answers: %d   -   %s" % (
            len(self.guesses), "solved on attempt %d" % self.attempt if solved else "not solved"),
            C["good"] if solved else C["bad"], self.F["smallb"])
        if not self.sa_done:
            self._para(body, "The full explanation unlocks after you submit your written "
                       "explanation.", C["muted"], pady=(2, 12))
        else:
            for p in self.rules["explanation"]:
                self._para(body, p)
        RetroButton(body, "GOT IT", close, font=self.F["btn"]).pack(anchor="e", pady=(6, 0))

    # ------------------------------------------------------- restart / back
    def _restart_needs_new_seed(self):
        return not self.practice and (self.attempt > 0 or self.bits_done)

    def confirm_restart(self):
        new_seed = self._restart_needs_new_seed()
        body, close = self._modal("RESTART", "Restart this level?", width=520)
        text = "Your traces, hints and written draft will be cleared."
        if new_seed:
            text += (" Because you have already submitted a key, you will get a NEW seed: "
                     "the lock gets a different key, and your attempts start again from 3.")
        elif self.practice:
            text += " This is a practice run, so nothing in your record changes."
        tk.Label(body, text=text, bg=C["panel2"], fg=C["text"], font=self.F["small"],
                 wraplength=px(460), justify="left").pack(anchor="w", pady=(0, 14))
        row = tk.Frame(body, bg=C["panel2"])
        row.pack(fill="x")
        RetroButton(row, "RESTART", lambda: (close(), self.restart()),
                    font=self.F["btn"]).pack(side="right")
        RetroButton(row, "CANCEL", close, kind="secondary",
                    font=self.F["btn"]).pack(side="right", padx=(0, 10))

    def restart(self):
        seed = self.save.reseed() if self._restart_needs_new_seed() else None
        self.app.open_level(self.LEVEL_ID)
        if seed:
            self.app.screen.feedback.config(
                fg=C["warn"], text="Level restarted with a new seed (%s)." % seed)

    def back_to_lab(self):
        try:
            self.answer_draft = self.answer.get("1.0", "end").rstrip("\n")
        except (tk.TclError, AttributeError):
            pass
        self.show_lab()

    # =========================================================================
    # View 2: the question (short answer)
    # =========================================================================
    def show_short_answer(self):
        self._clear()
        F = self.F
        self._title("Explain your reasoning")
        self.help_btn.grid_remove()
        self.restart_btn.grid_remove() if self.sa_done else self.restart_btn.grid()
        wrap = tk.Frame(self.stage, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        q = panel(wrap, "Short answer", F, fill="both", expand=True)
        tk.Label(q, justify="left", wraplength=px(1000), bg=C["panel"], fg=C["text"],
                 font=F["h2"], text=self.rules["question"]).pack(anchor="w")
        tk.Label(q, text="Answer in your own words. You can submit once.", bg=C["panel"],
                 fg=C["muted"], font=F["small"]).pack(anchor="w", pady=(4, 10))
        self.answer = tk.Text(q, height=8, wrap="word", bg=C["inset"], fg=C["text"],
                              insertbackground=C["amber"], insertwidth=3, relief="flat",
                              font=font(12), padx=12, pady=10, highlightthickness=3,
                              highlightbackground=C["border"], highlightcolor=C["amber"])
        self.answer.pack(fill="both", expand=True)
        if self.answer_draft:
            self.answer.insert("1.0", self.answer_draft)
        self.answer.focus_set()
        bottom = tk.Frame(q, bg=C["panel"])
        bottom.pack(fill="x", pady=(10, 0))
        self.wc = tk.Label(bottom, text="%d words" % len(self.answer_draft.split()),
                           bg=C["panel"], fg=C["muted"], font=F["small"])
        self.wc.pack(side="left")
        self.sa_submit = RetroButton(bottom, "SUBMIT EXPLANATION", self.submit_answer,
                                     kind="blue", font=F["btn"], sound=None)
        self.sa_submit.pack(side="right")
        self.sa_back = RetroButton(bottom, "< BACK TO LAB", self.back_to_lab,
                                   kind="secondary", font=F["btn"])
        self.sa_back.pack(side="right", padx=(0, 10))
        self.answer.bind("<KeyRelease>", lambda e: self.wc.config(
            text="%d words" % len(self.answer.get("1.0", "end").split()), fg=C["muted"]))
        self.sa_result = tk.Frame(q, bg=C["panel"])
        self.sa_result.pack(fill="x", pady=(12, 0))

    def submit_answer(self):
        text = self.answer.get("1.0", "end").strip()
        if len(text.split()) < 12:
            audio.play("wrong")
            self.wc.config(text="Please write at least a couple of full sentences.",
                           fg=C["warn"])
            return
        F = self.F
        self.sa_done = True
        self.answer_draft = ""
        self.sa_submit.set_enabled(False)
        self.sa_back.pack_forget()
        self.restart_btn.grid_remove()
        self.answer.config(state="disabled", fg=C["muted"])
        results = power_rules.score_answer(self.LEVEL_ID, text)
        pts = self.rules["points"]
        self.sa_points = sum(pts[rid] for rid, met, _, _ in results if met)
        self.score_lbl.config(text=self._score_text())
        score = self.bit_points + self.sa_points
        self.passed = progress.passed(score, self.max_score)
        audio.play("correct" if self.passed else "wrong")
        self.new_seed = None
        if not self.practice:
            if self.passed:
                self.save.mark_complete(
                    self.LEVEL_ID, attempt=self.attempt, bits_done=True,
                    bit_points=self.bit_points, sa_points=self.sa_points, score=score,
                    max_score=self.max_score, answer=text)
            else:
                self.new_seed = self.save.fail_level(self.LEVEL_ID, score, self.max_score)

        tk.Label(self.sa_result, text="Explanation: %d / %d points"
                 % (self.sa_points, self.rules["sa_max"]),
                 bg=C["panel"], fg=C["text"], font=F["h2"]).pack(anchor="w", pady=(0, 6))
        for rid, met, desc, hint in results:
            row = tk.Frame(self.sa_result, bg=C["panel"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text="[+%d]" % (pts[rid] if met else 0), bg=C["panel"],
                     fg=C["good"] if met else C["bad"], font=F["bodyb"]).pack(
                side="left", padx=(0, 8))
            tk.Label(row, text=desc if met else "Missing - hint: %s" % hint, bg=C["panel"],
                     fg=C["text"] if met else C["muted"], font=F["body"], anchor="w",
                     justify="left", wraplength=px(960)).pack(side="left", fill="x")
        row = tk.Frame(self.sa_result, bg=C["panel"])
        row.pack(fill="x", pady=(10, 0))
        RetroButton(row, "FINISH LEVEL >", self.show_results, font=F["btn"]).pack(side="right")
        RetroButton(row, "SEE FULL EXPLANATION", self.show_explanation, kind="secondary",
                    font=F["btn"]).pack(side="right", padx=(0, 10))

    # =========================================================================
    # View 3: results
    # =========================================================================
    def show_results(self):
        self._clear()
        F = self.F
        passed = getattr(self, "passed", True)
        total = self.bit_points + self.sa_points
        self._title("Level complete" if passed else "Level failed")
        self.help_btn.grid_remove()
        self.restart_btn.grid_remove()
        wrap = tk.Frame(self.stage, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        top = tk.Frame(wrap, bg=C["bg"])
        top.pack(fill="x")
        need = int(-(-progress.PASS_FRACTION * self.max_score // 1))
        cards = [("Key", "%d / %d" % (self.bit_points, BIT_MAX),
                  "solved on attempt %d" % self.attempt if self.bit_points else "not solved"),
                 ("Explanation", "%d / %d" % (self.sa_points, self.rules["sa_max"]), "rubric"),
                 ("Level total", "%d / %d" % (total, self.max_score),
                  "PASSED" if passed else "FAILED - %d needed to pass" % need)]
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
            tk.Label(inner, text=sub, bg=C["panel"],
                     fg=C["muted"] if i < 2 else (C["good"] if passed else C["bad"]),
                     font=F["small"]).pack(anchor="w", padx=16, pady=(0, 12))
        if not passed:
            fail = panel(wrap, "Level failed", F, fill="x", pady=(16, 0), accent="bad")
            note = ("You need at least %d of %d points to pass. Score higher on this level "
                    "to continue." % (need, self.max_score))
            if self.new_seed:
                note += (" Your seed has been redone (new seed: %s), so the lock now has a "
                         "different key." % self.new_seed)
            elif self.practice:
                note += " (Practice run: your record was not changed.)"
            tk.Label(fail, text=note, bg=C["panel"], fg=C["text"], font=F["body"],
                     justify="left", wraplength=px(1060)).pack(anchor="w")
        reveal = panel(wrap, "The key you were attacking", F, fill="x", pady=(16, 0))
        self._key_boxes(reveal, C["panel"])
        tk.Label(reveal, text=self.rules["explanation"][-1], bg=C["panel"], fg=C["muted"],
                 font=F["body"], justify="left", wraplength=px(1060)).pack(anchor="w")

        btns = tk.Frame(wrap, bg=C["bg"])
        btns.pack(fill="x", pady=(16, 0))
        if self.practice:
            back = lambda: self.app.show_menu()
        elif passed:
            back = lambda: self.app.show_menu(message=NEXT_MESSAGE[self.LEVEL_ID])
        else:
            back = lambda: self.app.show_menu(
                message=self.app.fail_message(self.LEVEL_ID, self.new_seed), seconds=6)
        RetroButton(btns, "BACK TO MENU", back, font=F["btn"]).pack(side="right")
        RetroButton(btns, "SEE FULL EXPLANATION", self.show_explanation, kind="secondary",
                    font=F["btn"]).pack(side="right", padx=(0, 10))

    def destroy(self):
        self._close_modal()
        super().destroy()


class Level2Screen(PowerLevelScreen):
    LEVEL_ID = "level2"
    NOISY = False


class Level3Screen(PowerLevelScreen):
    LEVEL_ID = "level3"
    NOISY = True
