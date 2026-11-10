"""
main.py -- launch this file:   python main.py

A Tkinter window with five screens (Introduction, Level 1 Timing, Level 2 SPA,
Level 3 Noise + protection, Review). Matplotlib plots are embedded in the
window so students can zoom and pan with the toolbar under each plot.

File map
    config.py    all tunable numbers
    sim.py       the simulated smart lock + oscilloscope (no GUI)
    main.py      this file: window, screens, widgets
    selftest.py  headless difficulty check

Optional command-line flags
    --student ID   seed the game from a student ID (same ID = same key)
    --seed N       seed the game with an integer
With neither flag you are asked for a student ID at launch (blank = random).

Developer menu (top bar): reveal the key, load a new random target.

Tinkering tips are marked with  TINKER:  throughout the file.
"""

import argparse
import json
import os
import random
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator

import config as cfg
import sim

HERE = os.path.dirname(os.path.abspath(__file__))
RESPONSE_LOG = os.path.join(HERE, "responses_log.jsonl")


# =============================================================================
# Reusable widgets
# =============================================================================
def make_plot(parent, height_in=3.1):
    """Create a Matplotlib figure embedded in `parent`, with zoom/pan toolbar.
    Returns (figure, axes, canvas)."""
    fig = Figure(figsize=(9.5, height_in), dpi=100)
    ax = fig.add_subplot(111)
    canvas = FigureCanvasTkAgg(fig, master=parent)
    toolbar = NavigationToolbar2Tk(canvas, parent, pack_toolbar=False)
    toolbar.update()
    toolbar.pack(side="bottom", fill="x")
    canvas.get_tk_widget().pack(side="top", fill="both", expand=True)
    return fig, ax, canvas


class SubmitRow(ttk.Frame):
    """A labelled input + Submit button with a limited number of attempts.

    * `make_input(frame)` builds the input widgets inside `frame` and returns
      (get_guess, reset_input).
    * `check(guess)` returns True/False.
    * Feedback is deliberately minimal: only "correct" or "incorrect"
      (never how close the guess was), as in the proposal.
    """

    def __init__(self, parent, label, make_input, check):
        super().__init__(parent)
        self.check = check
        ttk.Label(self, text=label).pack(side="left")
        box = ttk.Frame(self)
        box.pack(side="left", padx=8)
        self.get_guess, self._reset_input = make_input(box)
        self.button = ttk.Button(self, text="Submit", command=self.submit)
        self.button.pack(side="left", padx=4)
        self.status = ttk.Label(self, text="")
        self.status.pack(side="left", padx=8)
        self.reset()

    def reset(self):
        self.attempts_left = cfg.MAX_ATTEMPTS
        self.solved = False
        self._reset_input()
        self._refresh("Attempts left: %d" % self.attempts_left)

    def _refresh(self, text):
        self.status.config(text=text)
        locked = self.solved or self.attempts_left <= 0
        self.button.config(state="disabled" if locked else "normal")

    def submit(self):
        if self.solved or self.attempts_left <= 0:
            return
        if self.check(self.get_guess()):
            self.solved = True
            self._refresh("Correct!")
            return
        self.attempts_left -= 1
        if self.attempts_left <= 0:
            self._refresh("Incorrect. No attempts left.")
        else:
            self._refresh("Incorrect. Attempts left: %d" % self.attempts_left)


def bit_toggle_input(frame):
    """Input made of KEY_BITS clickable 0/1 buttons (MSB first)."""
    values = [0] * cfg.KEY_BITS
    buttons = []

    def toggle(i):
        values[i] ^= 1
        buttons[i].config(text=str(values[i]))

    for i in range(cfg.KEY_BITS):
        b = tk.Button(frame, text="0", width=1, padx=2, command=lambda i=i: toggle(i))
        b.grid(row=0, column=i, padx=1)
        buttons.append(b)
        ttk.Label(frame, text=str(cfg.KEY_BITS - 1 - i),
                  font=("TkDefaultFont", 7)).grid(row=1, column=i)

    def reset():
        for i in range(cfg.KEY_BITS):
            values[i] = 0
            buttons[i].config(text="0")

    return (lambda: list(values)), reset


def count_input(frame):
    """Input for Level 1: a spinbox holding how many key bits are 1."""
    var = tk.IntVar(value=0)
    ttk.Spinbox(frame, from_=0, to=cfg.KEY_BITS, width=4, textvariable=var).pack()

    def get():
        try:
            return int(var.get())
        except (tk.TclError, ValueError):
            return -1

    return get, (lambda: var.set(0))


class ResponseBox(ttk.LabelFrame):
    """Free-text 'explain your reasoning' box.

    SCORING IS A STUB: responses are only appended to responses_log.jsonl.
    When you build the real rubric check, replace `grade()` below.
    """

    def __init__(self, parent, level_name, prompt):
        super().__init__(parent, text=prompt)
        self.level_name = level_name
        self.text = tk.Text(self, height=3, width=90, wrap="word")
        self.text.pack(side="left", padx=4, pady=4, fill="x", expand=True)
        side = ttk.Frame(self)
        side.pack(side="left", padx=4)
        ttk.Button(side, text="Save response", command=self.save).pack()
        self.status = ttk.Label(side, text="")
        self.status.pack()

    def grade(self, text):
        """TINKER: plug the rubric / keyword matcher in here later."""
        return None

    def save(self):
        text = self.text.get("1.0", "end").strip()
        if not text:
            self.status.config(text="Nothing to save")
            return
        record = {"time": time.strftime("%Y-%m-%d %H:%M:%S"),
                  "level": self.level_name, "response": text,
                  "grade": self.grade(text)}
        with open(RESPONSE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        self.status.config(text="Saved")

    def reset(self):
        self.text.delete("1.0", "end")
        self.status.config(text="")


# =============================================================================
# Intro / Review: text drawn on a canvas (not selectable, so not copy-pastable)
# with optional True/False questions.
# =============================================================================
class SlidePage(ttk.Frame):
    """A simple slide viewer. `slides` is a list of dicts:
        {"title": str, "text": str}                           -> reading slide
        {"title": str, "text": str, "tf": (bool, "why")}      -> True/False slide
    TINKER: the real intro/review content goes in INTRO_SLIDES / REVIEW_SLIDES
    near the bottom of this file."""

    def __init__(self, parent, slides):
        super().__init__(parent)
        self.slides = slides
        self.index = 0
        self.canvas = tk.Canvas(self, width=940, height=420, bg="white",
                                highlightthickness=1, highlightbackground="#999")
        self.canvas.pack(padx=10, pady=10)
        self.tf_row = ttk.Frame(self)
        ttk.Button(self.tf_row, text="True",
                   command=lambda: self.answer(True)).pack(side="left", padx=6)
        ttk.Button(self.tf_row, text="False",
                   command=lambda: self.answer(False)).pack(side="left", padx=6)
        self.feedback = ttk.Label(self, text="", font=("TkDefaultFont", 11))
        nav = ttk.Frame(self)
        nav.pack(side="bottom", pady=8)
        self.prev_btn = ttk.Button(nav, text="< Back", command=lambda: self.go(-1))
        self.prev_btn.pack(side="left", padx=6)
        self.counter = ttk.Label(nav, text="")
        self.counter.pack(side="left", padx=6)
        self.next_btn = ttk.Button(nav, text="Next >", command=lambda: self.go(1))
        self.next_btn.pack(side="left", padx=6)
        self.feedback.pack(side="bottom")
        self.tf_row.pack(side="bottom", pady=4)
        self.render()

    def go(self, step):
        self.index = max(0, min(len(self.slides) - 1, self.index + step))
        self.render()

    def answer(self, value):
        correct, why = self.slides[self.index]["tf"]
        verdict = "Correct." if value == correct else "Not quite."
        self.feedback.config(text="%s %s" % (verdict, why))

    def render(self):
        slide = self.slides[self.index]
        c = self.canvas
        c.delete("all")
        c.create_text(24, 20, anchor="nw", text=slide["title"],
                      font=("Helvetica", 18, "bold"), width=890)
        c.create_text(24, 64, anchor="nw", text=slide["text"],
                      font=("Helvetica", 13), width=890)
        self.feedback.config(text="")
        if "tf" in slide:
            self.tf_row.pack(side="bottom", pady=4)
        else:
            self.tf_row.pack_forget()
        self.counter.config(text="%d / %d" % (self.index + 1, len(self.slides)))
        self.prev_btn.config(state="normal" if self.index > 0 else "disabled")
        self.next_btn.config(
            state="normal" if self.index < len(self.slides) - 1 else "disabled")

    def reset(self):
        self.index = 0
        self.render()


# =============================================================================
# Level 1 - Timing
# =============================================================================
class TimingPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        ttk.Label(self, text=(
            "Level 1 - Timing.   The lock runs the same operation many times. "
            "Each run's total time wobbles a little (jitter).   "
            "t_S = %.1f ms,  t_M = 1.5 x t_S = %.1f ms,  key length = %d bits."
            % (cfg.T_S_MS, cfg.T_M_MS, cfg.KEY_BITS)),
            wraplength=940).pack(anchor="w", padx=10, pady=(8, 2))

        plot_frame = ttk.Frame(self)
        plot_frame.pack(fill="both", expand=True, padx=10)
        self.fig, self.ax, self.canvas = make_plot(plot_frame)

        controls = ttk.Frame(self)
        controls.pack(fill="x", padx=10, pady=4)
        ttk.Label(controls, text="Runs per batch:").pack(side="left")
        self.runs_var = tk.IntVar(value=cfg.L1_MIN_RUNS)
        ttk.Spinbox(controls, from_=cfg.L1_MIN_RUNS, to=cfg.L1_MAX_RUNS, width=5,
                    textvariable=self.runs_var).pack(side="left", padx=4)
        ttk.Button(controls, text="Run batch",
                   command=self.run_batch).pack(side="left", padx=4)
        self.readout = ttk.Label(controls, text="No data yet.")
        self.readout.pack(side="left", padx=14)

        self.submit = SubmitRow(
            self, "How many key bits are 1?  ", count_input,
            lambda g: self.app.target.check_count(g))
        self.submit.pack(anchor="w", padx=10, pady=4)

        self.response = ResponseBox(
            self, "level1_timing",
            "Explain: why does timing reveal how many bits are 1, but not where?")
        self.response.pack(fill="x", padx=10, pady=4)
        self.reset()

    def run_batch(self):
        # TINKER: each batch REPLACES the previous one. To let students pool
        # batches, keep a running list here instead.
        try:
            n = int(self.runs_var.get())
        except (tk.TclError, ValueError):
            n = cfg.L1_MIN_RUNS
        n = max(cfg.L1_MIN_RUNS, min(cfg.L1_MAX_RUNS, n))
        self.runs_var.set(n)
        times = self.app.target.timing_runs(n)
        self.draw(times)

    def draw(self, times):
        ax = self.ax
        ax.clear()
        mean = float(np.mean(times))
        ax.plot(np.arange(1, len(times) + 1), times, "o", markersize=4,
                label="single runs")
        ax.axhline(mean, color="tab:red", linewidth=1.5,
                   label="mean = %.2f ms" % mean)
        if cfg.L1_SHOW_REFERENCE_GRID:
            for j in range(cfg.KEY_BITS + 1):
                y = cfg.KEY_BITS * cfg.T_S_MS + j * cfg.T_M_MS
                ax.axhline(y, color="gray", alpha=0.2, linewidth=0.8)
                ax.text(len(times) + 0.6, y, str(j), fontsize=7, va="center")
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))  # whole run numbers
        ax.set_xlabel("run number")
        ax.set_ylabel("total execution time (ms)")
        ax.set_title("Total execution time over %d runs" % len(times))
        ax.legend(loc="upper right")
        self.fig.tight_layout()
        self.canvas.draw_idle()
        self.readout.config(text="Runs: %d   Mean: %.2f ms   Std dev: %.2f ms"
                            % (len(times), mean, float(np.std(times, ddof=1))))

    def reset(self):
        self.ax.clear()
        self.ax.set_title("Press 'Run batch' to collect timing data")
        self.canvas.draw_idle()
        self.readout.config(text="No data yet.")
        self.runs_var.set(cfg.L1_MIN_RUNS)
        self.submit.reset()
        self.response.reset()


# =============================================================================
# Level 2 - Simple power analysis
# =============================================================================
class SPAPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        ttk.Label(self, text=(
            "Level 2 - Simple power analysis.   One power trace: the chip's supply "
            "current across a shunt resistor, one block per operation. "
            "Use the toolbar to zoom and pan, then enter the 16 key bits "
            "(MSB first; click a bit to flip it).   t_S = %.1f ms, t_M = %.1f ms."
            % (cfg.T_S_MS, cfg.T_M_MS)),
            wraplength=940).pack(anchor="w", padx=10, pady=(8, 2))

        plot_frame = ttk.Frame(self)
        plot_frame.pack(fill="both", expand=True, padx=10)
        self.fig, self.ax, self.canvas = make_plot(plot_frame)

        self.submit = SubmitRow(
            self, "Key bits (MSB -> LSB):  ", bit_toggle_input,
            lambda g: self.app.target.check_key(g))
        self.submit.pack(anchor="w", padx=10, pady=6)

        self.response = ResponseBox(
            self, "level2_spa",
            "Explain: why do the segment lengths differ, and what sets each block's height?")
        self.response.pack(fill="x", padx=10, pady=4)
        self.reset()

    def reset(self):
        # One fixed trace per target (the student gets exactly one).
        self.trace = self.app.target.acquire_trace(cfg.L2_NOISE_SIGMA)
        x = np.arange(len(self.trace)) * self.app.target.sample_period_ms
        ax = self.ax
        ax.clear()
        ax.plot(x, self.trace, linewidth=1)
        ax.set_xlabel("time (ms)")
        ax.set_ylabel("supply current (arbitrary units)")
        ax.set_title("Single power trace (noise sigma = %g)" % cfg.L2_NOISE_SIGMA)
        ax.grid(alpha=0.25)
        self.fig.tight_layout()
        self.canvas.draw_idle()
        self.submit.reset()
        self.response.reset()


# =============================================================================
# Level 3 - Noise, averaging, and the protected device
# =============================================================================
class NoisePage(ttk.Frame):
    DEVICES = ("standard", "protected")

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        ttk.Label(self, text=(
            "Level 3 - Noise + protection.   Single traces are now buried in noise "
            "(SNR = 1). Acquire traces and look at their average. "
            "Then switch to the protected device and try again."),
            wraplength=940).pack(anchor="w", padx=10, pady=(8, 2))

        # Device selector
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10)
        self.device_var = tk.StringVar(value="standard")
        ttk.Label(top, text="Device:").pack(side="left")
        ttk.Radiobutton(top, text="Standard lock", value="standard",
                        variable=self.device_var,
                        command=self.on_device_change).pack(side="left", padx=6)
        ttk.Radiobutton(top, text="Protected lock", value="protected",
                        variable=self.device_var,
                        command=self.on_device_change).pack(side="left", padx=6)

        plot_frame = ttk.Frame(self)
        plot_frame.pack(fill="both", expand=True, padx=10)
        self.fig, self.ax, self.canvas = make_plot(plot_frame, height_in=2.9)

        controls = ttk.Frame(self)
        controls.pack(fill="x", padx=10, pady=4)
        ttk.Label(controls, text="Traces to acquire:").pack(side="left")
        self.n_var = tk.IntVar(value=10)
        ttk.Spinbox(controls, from_=1, to=cfg.L3_MAX_PER_BATCH, width=5,
                    textvariable=self.n_var).pack(side="left", padx=4)
        ttk.Button(controls, text="Acquire",
                   command=self.acquire).pack(side="left", padx=4)
        ttk.Button(controls, text="Clear average",
                   command=self.clear_average).pack(side="left", padx=4)
        self.overlay_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls, text="Show latest single trace",
                        variable=self.overlay_var,
                        command=self.redraw).pack(side="left", padx=10)
        self.budget_label = ttk.Label(controls, text="")
        self.budget_label.pack(side="left", padx=10)

        # One independent submit row per device (each has its own attempts).
        # The holder frame is created FIRST and the rows are its children;
        # otherwise Tk stacks the holder on top of the rows and hides them.
        self.response = ResponseBox(
            self, "level3_noise_protection",
            "Explain: why does averaging help, and why does the protected lock resist SPA?")
        self.response.pack(side="bottom", fill="x", padx=10, pady=4)
        self.submit_holder = ttk.Frame(self)
        self.submit_holder.pack(side="bottom", anchor="w", padx=10, pady=4)
        self.submits = {
            d: SubmitRow(self.submit_holder, "Key bits (%s device):  " % d,
                         bit_toggle_input,
                         lambda g: self.app.target.check_key(g))
            for d in self.DEVICES
        }
        self.reset()

    # -- state per device ------------------------------------------------------
    def _fresh_state(self):
        return {d: {"sum": None, "count": 0, "used": 0, "last": None}
                for d in self.DEVICES}

    def on_device_change(self):
        d = self.device_var.get()
        for row in self.submits.values():
            row.pack_forget()
        # Show only the row for the selected device, inside the holder frame
        self.submits[d].pack(anchor="w")
        self.redraw()

    def acquire(self):
        d = self.device_var.get()
        st = self.state[d]
        try:
            n = int(self.n_var.get())
        except (tk.TclError, ValueError):
            n = 1
        n = max(1, min(cfg.L3_MAX_PER_BATCH, n))
        n = min(n, cfg.L3_MAX_TRACES - st["used"])      # respect the budget
        if n <= 0:
            messagebox.showinfo("Budget used up",
                                "No traces left for this device.")
            return
        protected = d == "protected"
        for _ in range(n):
            tr = self.app.target.acquire_trace(cfg.L3_NOISE_SIGMA, protected)
            st["sum"] = tr if st["sum"] is None else st["sum"] + tr
            st["count"] += 1
            st["used"] += 1
            st["last"] = tr
        self.redraw()

    def clear_average(self):
        # Clears the average but does NOT refund the trace budget.
        st = self.state[self.device_var.get()]
        st["sum"], st["count"], st["last"] = None, 0, None
        self.redraw()

    def redraw(self):
        d = self.device_var.get()
        st = self.state[d]
        ax = self.ax
        ax.clear()
        if st["count"] == 0:
            ax.set_title("No traces yet - press Acquire (%s device)" % d)
        else:
            x = np.arange(len(st["sum"])) * self.app.target.sample_period_ms
            if self.overlay_var.get() and st["last"] is not None:
                ax.plot(x, st["last"], color="lightgray", linewidth=0.8,
                        label="latest single trace")
            ax.plot(x, st["sum"] / st["count"], color="tab:blue", linewidth=1.3,
                    label="average of %d traces" % st["count"])
            ax.legend(loc="upper right")
            ax.set_title("%s device - average of %d traces"
                         % (d.capitalize(), st["count"]))
        ax.set_xlabel("time (ms)")
        ax.set_ylabel("supply current (arbitrary units)")
        ax.grid(alpha=0.25)
        self.fig.tight_layout()
        self.canvas.draw_idle()
        self.budget_label.config(text="Traces used: %d / %d"
                                 % (st["used"], cfg.L3_MAX_TRACES))

    def reset(self):
        self.state = self._fresh_state()
        self.device_var.set("standard")
        for s in self.submits.values():
            s.reset()
        self.response.reset()
        self.on_device_change()


# =============================================================================
# Placeholder slide content.  TINKER: replace with the real text later.
# =============================================================================
INTRO_SLIDES = [
    {"title": "Introduction (sample text)",
     "text": ("Hardware security: a chip can keep a secret perfectly well in "
              "software terms and still give it away through its physical "
              "behaviour. A side channel is any such unintended signal - "
              "execution time, power draw, electromagnetic emissions.\n\n"
              "Leakage means the measured signal depends on the secret. "
              "Simple power analysis (SPA) reads the secret directly from the "
              "shape of one power trace. Signal-to-noise ratio (SNR) compares "
              "the size of the useful signal with the size of the noise.")},
    {"title": "The target: a smart lock",
     "text": ("The lock proves who it is using modular exponentiation. It scans "
              "the secret key one bit at a time, from the top bit down.\n\n"
              "For every bit it SQUARES (S). If the bit is 1, it also "
              "MULTIPLIES (M). A 0 bit is just S; a 1 bit is S then M.\n\n"
              "So the work the chip does depends on the key.")},
    {"title": "Check yourself", "text": "A multiply happens on every key bit.",
     "tf": (False, "The multiply happens only when the key bit is 1.")},
    {"title": "Leakage model",
     "text": ("Every operation draws supply current. Here, a block's height is "
              "proportional to the Hamming weight (number of 1 bits) of the "
              "32-bit word being processed. Random 32-bit words have an "
              "average Hamming weight of 16.\n\n"
              "In this game you only ever see traces and timings - never the "
              "key and never the code.")},
    {"title": "Check yourself",
     "text": "Simple power analysis can sometimes recover a key from a single trace.",
     "tf": (True, "If the operations are visibly different, one trace can be enough.")},
]

REVIEW_SLIDES = [
    {"title": "Review (sample text)",
     "text": ("Level 1 - Timing: total time tells you HOW MANY multiplies ran, "
              "so how many key bits are 1 - but not WHERE they are.\n\n"
              "Level 2 - SPA: in one clean trace, an S+M segment is longer than "
              "an S segment, so the bit pattern can be read directly. "
              "Block heights follow the Hamming weight of the data.\n\n"
              "Level 3 - Noise: averaging repeated traces makes the repeating "
              "signal stand out because independent noise shrinks roughly with "
              "the square root of the number of traces.")},
    {"title": "Why the protected lock works",
     "text": ("Square-and-multiply-ALWAYS performs a multiply on every bit, "
              "throwing the result away when the key bit is 0. Every bit now "
              "produces the same S+M pattern, so SPA has nothing to read.\n\n"
              "It is also constant-time: the total run time is the same for "
              "every key, so the Level 1 timing attack fails too.\n\n"
              "Protection is not the end of the story. Real devices can still "
              "leak through other routes, such as the data being processed, "
              "and need further defenses.")},
    {"title": "Bonus question (sample)",
     "text": "Averaging many traces defeats square-and-multiply-always.",
     "tf": (False, "Averaging removes noise, but there is no key-dependent "
                   "pattern in the protected trace to reveal.")},
    {"title": "Bonus question (sample)",
     "text": "Total execution time can reveal which positions in the key are 1.",
     "tf": (False, "Time only reveals how many multiplies ran, not where.")},
]


# =============================================================================
# The application window
# =============================================================================
class App(tk.Tk):
    def __init__(self, seed):
        super().__init__()
        self.title("Side-Channel Attack Game - demo build")
        self.geometry("1080x900")
        self.minsize(1000, 860)

        self.target = sim.Target(seed)

        # --- menu ---------------------------------------------------------------
        menubar = tk.Menu(self)
        dev = tk.Menu(menubar, tearoff=0)
        dev.add_command(label="Reveal key (spoiler!)", command=self.reveal_key)
        dev.add_command(label="New random target", command=self.new_random_target)
        menubar.add_cascade(label="Developer", menu=dev)
        self.config(menu=menubar)

        # --- navigation bar -----------------------------------------------------
        nav = ttk.Frame(self)
        nav.pack(fill="x", padx=8, pady=6)
        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True)

        # TINKER: add or reorder screens here.
        self.pages = {
            "Introduction": SlidePage(self.container, INTRO_SLIDES),
            "1. Timing": TimingPage(self.container, self),
            "2. SPA": SPAPage(self.container, self),
            "3. Noise + protection": NoisePage(self.container, self),
            "Review": SlidePage(self.container, REVIEW_SLIDES),
        }
        for name in self.pages:
            ttk.Button(nav, text=name,
                       command=lambda n=name: self.show(n)).pack(side="left", padx=3)
        self.seed_label = ttk.Label(nav, text="")
        self.seed_label.pack(side="right")
        self.update_seed_label()
        self.show("Introduction")

    def show(self, name):
        for p in self.pages.values():
            p.pack_forget()
        self.pages[name].pack(fill="both", expand=True)

    def update_seed_label(self):
        self.seed_label.config(text="target seed: %d" % self.target.seed)

    # --- developer actions --------------------------------------------------------
    def reveal_key(self):
        t = self.target
        messagebox.showinfo(
            "Secret key",
            "Key bits (MSB first): %s\nNumber of 1 bits: %d\nSeed: %d"
            % ("".join(map(str, t.key_bits)), sum(t.key_bits), t.seed))

    def new_random_target(self):
        self.load_target(random.SystemRandom().randrange(2 ** 63))

    def load_target(self, seed):
        self.target = sim.Target(seed)
        self.update_seed_label()
        for p in self.pages.values():
            p.reset()


# =============================================================================
# Entry point
# =============================================================================
def pick_seed(args):
    if args.seed is not None:
        return args.seed
    if args.student:
        return sim.seed_from_student_id(args.student)
    root = tk.Tk()
    root.withdraw()
    sid = simpledialog.askstring(
        "Student ID", "Enter your student ID (leave blank for a random game):",
        parent=root)
    root.destroy()
    if sid and sid.strip():
        return sim.seed_from_student_id(sid)
    return random.SystemRandom().randrange(2 ** 63)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Side-channel attack game demo")
    parser.add_argument("--student", help="student ID used to seed the game")
    parser.add_argument("--seed", type=int, help="integer seed (overrides --student)")
    App(pick_seed(parser.parse_args())).mainloop()
