"""
Side-Channel Attack Game -- Level 1: Timing Attack
==================================================

A smart-lock microcontroller computes modular exponentiation with
square-and-multiply using a secret 16-bit exponent.  For every key bit it
SQUARES (S); if the bit is 1 it also MULTIPLIES (M).  The player measures the
total execution time over many runs and must infer how many key bits are 1.

Model (from the proposal):
    T = (#S * t_S) + (#M * t_M) + jitter
    #S = 16, #M = number of 1 bits (Hamming weight of the key)
    t_M = 1.5 * t_S,  jitter ~ N(0, sigma_j),  sigma_j = 0.5 * t_M
    Runs per batch: 20 .. 50
    Bit-count submission: 3 attempts, 3 / 2 / 1 points, told only correct/incorrect
    Short answer: checked against rubric points 1 & 2 (keywords in the same sentence)

Run:
    python level1_timing.py                  # asks for a student ID
    python level1_timing.py --student-id abc  # skip the login screen
    python level1_timing.py --protect         # Windows: block screenshots/recording

Requires: Python 3.9+, numpy, matplotlib, tkinter (bundled with Python on
Windows/macOS; `sudo apt install python3-tk` on Debian/Ubuntu).

The simulation (`TimingSimulator`) and scoring (`score_short_answer`) have no
UI dependencies, so they can be reused by other levels / a launcher.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass, field

import numpy as np
import matplotlib

matplotlib.use("TkAgg")
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: E402


# =============================================================================
#  Simulation
# =============================================================================

KEY_BITS = 16
T_S_US = 150.0                 # time of one square, microseconds (told to student)
T_M_US = 1.5 * T_S_US          # time of one multiply (told to student as 1.5 * t_S)
JITTER_SIGMA_US = 0.5 * T_M_US  # run-to-run jitter, ~ +/- one multiply per run
MIN_RUNS, MAX_RUNS = 20, 50
MAX_ATTEMPTS = 3


def seed_for(student_id: str, level: str = "level1") -> int:
    """Deterministic per-student seed so every student gets a different key."""
    digest = hashlib.sha256(f"{student_id.strip().lower()}|{level}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


@dataclass
class TimingSimulator:
    student_id: str
    rng: np.random.Generator = field(init=False)
    key: int = field(init=False)

    def __post_init__(self) -> None:
        self.rng = np.random.default_rng(seed_for(self.student_id))
        # Real exponents have the top bit set; keep the weight away from the
        # extremes so the answer is not guessable.
        while True:
            key = int(self.rng.integers(0, 1 << KEY_BITS)) | (1 << (KEY_BITS - 1))
            if 4 <= bin(key).count("1") <= 12:
                break
        self.key = key

    @property
    def ones(self) -> int:
        return bin(self.key).count("1")

    def operation_sequence(self) -> str:
        """'S' / 'SM' per bit, MSB first -- what the chip actually executes."""
        bits = format(self.key, f"0{KEY_BITS}b")
        return "".join("SM" if b == "1" else "S" for b in bits)

    def run_batch(self, n: int) -> np.ndarray:
        """Total execution time (µs) of n independent runs."""
        n = int(np.clip(n, MIN_RUNS, MAX_RUNS))
        base = KEY_BITS * T_S_US + self.ones * T_M_US
        return base + self.rng.normal(0.0, JITTER_SIGMA_US, size=n)


def points_for_attempt(attempt: int) -> int:
    """Attempt 1 -> 3 pts, attempt 2 -> 2 pts, attempt 3 -> 1 pt."""
    return max(0, 4 - attempt)


# =============================================================================
#  Short-answer scoring (rubric points 1 & 2)
# =============================================================================

_T = {
    "mult": r"multipl\w*|\bmul\b|\bm\b|\bs\s*\+\s*m\b",
    "one": r"\b1\b|\bones?\b|\b1s\b|\b1-bits?\b|\bset\b|\bhigh\b|\bnon-?zero\b",
    "time": r"\btim(e|es|ing|ed)\b|\bduration\b|\blonger\b|\bslower\b|\bexecution\b"
            r"|\bruntime\b|\btakes?\b|\bclock\b|\bcycles?\b",
    "count": r"\bhow many\b|\bnumber\b|\bcount\w*\b|\bamount\b|\bhamming weight\b"
             r"|\bweight\b|\btotal\b|\bquantity\b",
    "where": r"\bwhere\b|\bpositions?\b|\blocations?\b|\border\b|\bwhich (bits?|ones?)\b"
             r"|\bsequence\b|\bplaces?\b|\bindex\w*\b|\barrangement\b",
    "neg": r"\bnot\b|n't\b|\bno\b|\bcannot\b|\bnever\b|\bwithout\b|\bunable\b|\bimpossible\b",
}
_RX = {k: re.compile(v, re.IGNORECASE) for k, v in _T.items()}

RUBRIC = [
    # (id, needs-in-same-sentence, description shown after submitting, hint if missed)
    ("R1", ("mult", "one"),
     "A multiply happens only when a key bit is 1, so control flow depends on the key.",
     "What extra operation does the chip perform, and for which key bits?"),
    ("R2a", ("time", "count"),
     "Total time reveals how many bits are 1 …",
     "What exactly can you compute from the average total time?"),
    ("R2b", ("where", "neg"),
     "… but not where they are.",
     "Is there anything about the key that the total time can NOT tell you?"),
]


# Progressive hints for the bit-count puzzle. The last one only unlocks after a
# wrong attempt, so a student can't skip straight to the method.
HINTS = [
    "Every run does exactly 16 squares, no matter what the key is. The only thing "
    "that changes the run time is how many multiplies happen.",
    "Don't trust a single run: jitter moves it by about one multiply. Use the MEAN "
    "time, and add batches until the running mean stops moving.",
    "Take the mean time, subtract the time of the 16 squares, then divide what is "
    "left by the time of one multiply. Round to the nearest whole number.",
]
HINT_LOCKED_UNTIL_WRONG = 2  # index of the hint that needs a wrong attempt first


def _sentences(text: str) -> list[str]:
    """Split into sentences, dropping fragments that look like keyword lists."""
    parts = re.split(r"(?<=[.!?;])\s+|\n+", text.strip())
    keep = []
    for p in parts:
        words = re.findall(r"[\w'+-]+", p)
        if len(words) < 6:
            continue
        hits = sum(1 for w in words if any(r.fullmatch(w) or r.search(f" {w} ")
                                           for r in _RX.values()))
        if hits / len(words) <= 0.5:  # mostly real prose, not stuffed keywords
            keep.append(p)
    return keep


def score_short_answer(text: str) -> list[tuple[str, bool, str, str]]:
    """Return [(rubric_id, met, description, hint), ...]."""
    sents = _sentences(text)
    out = []
    for rid, needs, desc, hint in RUBRIC:
        met = any(all(_RX[n].search(s) for n in needs) for s in sents)
        out.append((rid, met, desc, hint))
    return out


# =============================================================================
#  UI theme / widgets
# =============================================================================

C = {
    "bg": "#0d1117", "panel": "#161b22", "panel2": "#1c2330", "border": "#2a3341",
    "text": "#e6edf3", "muted": "#8b98a9", "dim": "#5b6675",
    "accent": "#3ddc97", "accent_dk": "#1f8f60", "accent2": "#58a6ff",
    "warn": "#f2cc60", "bad": "#ff6b6b", "good": "#3ddc97", "scope": "#0a0f14",
}


def pick_font(root: tk.Misc, candidates: list[str]) -> str:
    fams = set(tkfont.families(root))
    for c in candidates:
        if c in fams:
            return c
    return candidates[-1]


class FlatButton(tk.Label):
    """Label-based button so colours work on every OS (macOS ignores tk.Button bg)."""

    def __init__(self, master, text, command, kind="primary", font=None, **kw):
        self.palette = {
            "primary": (C["accent"], "#0b1a12", "#5ff0b0"),
            "secondary": (C["panel2"], C["text"], C["border"]),
            "blue": (C["accent2"], "#08121f", "#82bdff"),
        }[kind]
        bg, fg, _ = self.palette
        super().__init__(master, text=text, bg=bg, fg=fg, font=font, cursor="hand2",
                         padx=16, pady=9, **kw)
        self.command = command
        self.enabled = True
        self.bind("<Enter>", lambda e: self.enabled and self.config(bg=self.palette[2]))
        self.bind("<Leave>", lambda e: self.enabled and self.config(bg=self.palette[0]))
        self.bind("<Button-1>", lambda e: self.enabled and self.command())

    def set_enabled(self, on: bool) -> None:
        self.enabled = on
        bg, fg, _ = self.palette
        self.config(bg=bg if on else C["panel2"], fg=fg if on else C["dim"],
                    cursor="hand2" if on else "arrow")


def card(master, title=None, fonts=None, **pack):
    outer = tk.Frame(master, bg=C["panel"], highlightbackground=C["border"],
                     highlightthickness=1)
    outer.pack(**pack)
    inner = tk.Frame(outer, bg=C["panel"])
    inner.pack(fill="both", expand=True, padx=16, pady=14)
    if title:
        tk.Label(inner, text=title.upper(), bg=C["panel"], fg=C["muted"],
                 font=fonts["label"], anchor="w").pack(fill="x", pady=(0, 8))
    return inner


# =============================================================================
#  Application
# =============================================================================

class Level1App:
    def __init__(self, root: tk.Tk, student_id: str | None, protect: bool) -> None:
        self.root = root
        self.protect = protect
        root.title("Side-Channel Lab — Level 1: Timing")
        root.configure(bg=C["bg"])
        root.geometry("1360x820")
        root.minsize(1180, 740)

        sans = pick_font(root, ["Segoe UI", "SF Pro Text", "Helvetica Neue", "Inter",
                                "Helvetica", "Arial", "DejaVu Sans"])
        mono = pick_font(root, ["Cascadia Mono", "Consolas", "Menlo", "SF Mono",
                                "DejaVu Sans Mono", "Courier New"])
        self.F = {
            "hero": (sans, 30, "bold"), "h1": (sans, 18, "bold"), "h2": (sans, 13, "bold"),
            "body": (sans, 11), "bodyb": (sans, 11, "bold"), "small": (sans, 10),
            "label": (sans, 9, "bold"), "mono": (mono, 11), "monob": (mono, 13, "bold"),
            "big": (mono, 26, "bold"), "btn": (sans, 11, "bold"),
        }
        self.mono_family = mono
        self.sans_family = sans

        self.container = tk.Frame(root, bg=C["bg"])
        self.container.pack(fill="both", expand=True)
        self.tutorial_seen = False
        self.tour = None

        if protect:
            root.after(300, self._enable_capture_protection)

        if student_id:
            self.start(student_id)
        else:
            self.show_login()

    # ------------------------------------------------------------------ util
    def _clear(self) -> None:
        self.tour = None
        for w in self.container.winfo_children():
            w.destroy()

    def _enable_capture_protection(self) -> None:
        """Proposal: block screenshots on Windows (WDA_EXCLUDEFROMCAPTURE)."""
        if sys.platform != "win32":
            return
        try:
            import ctypes
            hwnd = int(self.root.wm_frame(), 16)
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x11)
        except Exception:
            pass

    def _topbar(self, subtitle: str, help_button: bool = False) -> None:
        bar = tk.Frame(self.container, bg=C["bg"])
        bar.pack(fill="x", padx=24, pady=(18, 10))
        left = tk.Frame(bar, bg=C["bg"])
        left.pack(side="left")
        tk.Label(left, text="LEVEL 1  ·  TIMING ATTACK", bg=C["bg"], fg=C["accent"],
                 font=self.F["label"]).pack(anchor="w")
        tk.Label(left, text=subtitle, bg=C["bg"], fg=C["text"],
                 font=self.F["h1"]).pack(anchor="w")
        right = tk.Frame(bar, bg=C["bg"])
        right.pack(side="right")
        self.score_lbl = tk.Label(right, text=self._score_text(), bg=C["bg"],
                                  fg=C["text"], font=self.F["bodyb"])
        self.score_lbl.pack(anchor="e")
        tk.Label(right, text=f"Student: {self.student_id}", bg=C["bg"], fg=C["muted"],
                 font=self.F["small"]).pack(anchor="e")
        if help_button:
            FlatButton(bar, "?  How to play", self.start_tour, kind="secondary",
                       font=self.F["small"]).pack(side="right", padx=(0, 20))

    def _score_text(self) -> str:
        return f"SCORE  {self.bit_points + self.sa_points} / 6"

    # ---------------------------------------------------------------- login
    def show_login(self) -> None:
        self._clear()
        wrap = tk.Frame(self.container, bg=C["bg"])
        wrap.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(wrap, text="SIDE-CHANNEL LAB", bg=C["bg"], fg=C["accent"],
                 font=self.F["label"]).pack()
        tk.Label(wrap, text="Level 1 — Timing Attack", bg=C["bg"], fg=C["text"],
                 font=self.F["hero"]).pack(pady=(4, 6))
        tk.Label(wrap, text="Break into a smart lock using nothing but a stopwatch.",
                 bg=C["bg"], fg=C["muted"], font=self.F["body"]).pack(pady=(0, 26))

        box = card(wrap, "Sign in", self.F, fill="x")
        tk.Label(box, text="Student ID (your secret key is generated from it)",
                 bg=C["panel"], fg=C["text"], font=self.F["body"]).pack(anchor="w")
        entry = tk.Entry(box, width=34, bg=C["scope"], fg=C["text"], relief="flat",
                         insertbackground=C["accent"], font=self.F["mono"],
                         highlightthickness=1, highlightbackground=C["border"],
                         highlightcolor=C["accent"])
        entry.pack(fill="x", pady=(8, 6), ipady=7)
        entry.focus_set()
        err = tk.Label(box, text="", bg=C["panel"], fg=C["bad"], font=self.F["small"])
        err.pack(anchor="w")

        def go(_=None):
            sid = entry.get().strip()
            if len(sid) < 2:
                err.config(text="Please enter your student ID.")
                return
            self.start(sid)

        entry.bind("<Return>", go)
        FlatButton(box, "Start level  →", go, font=self.F["btn"]).pack(fill="x", pady=(6, 0))

    # ------------------------------------------------------------------ lab
    def start(self, student_id: str) -> None:
        self.student_id = student_id
        self.sim = TimingSimulator(student_id)
        self.times = np.empty(0)
        self.batch_ids = np.empty(0, dtype=int)
        self.n_batches = 0
        self.attempt = 0
        self.bit_points = 0
        self.sa_points = 0
        self.bits_done = False
        self.hints_shown = 0
        self.show_lab()

    def show_lab(self) -> None:
        self._clear()
        self._topbar("Count the 1 bits in the lock's secret key", help_button=True)

        body = tk.Frame(self.container, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        # left: briefing ---------------------------------------------------
        left = tk.Frame(body, bg=C["bg"], width=300)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        brief = card(left, "Mission briefing", self.F, fill="x")
        self.t_brief = brief.master
        tk.Label(brief, justify="left", wraplength=262, bg=C["panel"], fg=C["text"],
                 font=self.F["body"], text=(
                     "The SmartLock MCU unlocks by computing a modular exponentiation "
                     "with a secret 16-bit exponent, using square-and-multiply.\n\n"
                     "For every key bit it squares (S). When the bit is 1 it also "
                     "multiplies (M).\n\n"
                     "You can't see the key or the code, but you can time the device. "
                     "Each run has random clock jitter, so a single measurement isn't "
                     "reliable.")).pack(anchor="w")

        specs = card(left, "Known device specs", self.F, fill="x", pady=(12, 0))
        self.t_specs = specs.master
        for k, v in [("Key length", f"{KEY_BITS} bits"),
                     ("Square  t_S", f"{T_S_US:.1f} µs"),
                     ("Multiply t_M", f"1.5 × t_S"),
                     ("Jitter", "random, every run")]:
            row = tk.Frame(specs, bg=C["panel"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text=k, bg=C["panel"], fg=C["muted"],
                     font=self.F["small"]).pack(side="left")
            tk.Label(row, text=v, bg=C["panel"], fg=C["accent"],
                     font=self.F["mono"]).pack(side="right")

        goal = card(left, "Objective", self.F, fill="x", pady=(12, 0))
        tk.Label(goal, justify="left", wraplength=262, bg=C["panel"], fg=C["text"],
                 font=self.F["body"],
                 text="Collect timing measurements and work out how many of the "
                      "16 key bits are 1. You have 3 attempts.").pack(anchor="w")

        # right: controls --------------------------------------------------
        right = tk.Frame(body, bg=C["bg"], width=300)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        meas = card(right, "1 · Measure", self.F, fill="x")
        self.t_meas = meas.master
        self.runs_var = tk.IntVar(value=30)
        hdr = tk.Frame(meas, bg=C["panel"])
        hdr.pack(fill="x")
        tk.Label(hdr, text="Runs per batch", bg=C["panel"], fg=C["text"],
                 font=self.F["body"]).pack(side="left")
        tk.Label(hdr, textvariable=self.runs_var, bg=C["panel"], fg=C["accent"],
                 font=self.F["monob"]).pack(side="right")
        tk.Scale(meas, from_=MIN_RUNS, to=MAX_RUNS, orient="horizontal",
                 variable=self.runs_var, showvalue=0, bg=C["accent"],
                 troughcolor=C["scope"], highlightthickness=0, bd=0, width=12,
                 activebackground="#5ff0b0", sliderrelief="flat", sliderlength=22,
                 length=260).pack(fill="x", pady=(8, 0))
        scale_lbl = tk.Frame(meas, bg=C["panel"])
        scale_lbl.pack(fill="x")
        for side, txt in (("left", MIN_RUNS), ("right", MAX_RUNS)):
            tk.Label(scale_lbl, text=str(txt), bg=C["panel"], fg=C["dim"],
                     font=self.F["small"]).pack(side=side)
        FlatButton(meas, "▶  Run batch", self.run_batch, font=self.F["btn"]).pack(
            fill="x", pady=(8, 6))
        self.reset_btn = FlatButton(meas, "Clear measurements", self.clear_runs,
                                    kind="secondary", font=self.F["small"])
        self.reset_btn.pack(fill="x")

        sub = card(right, "2 · Submit", self.F, fill="x", pady=(12, 0))
        self.t_sub = sub.master
        tk.Label(sub, text="Number of 1 bits in the key", bg=C["panel"], fg=C["text"],
                 font=self.F["body"]).pack(anchor="w")
        rowf = tk.Frame(sub, bg=C["panel"])
        rowf.pack(fill="x", pady=(8, 8))
        self.guess_var = tk.StringVar(value="")
        self.guess = tk.Spinbox(rowf, from_=0, to=KEY_BITS, textvariable=self.guess_var,
                                width=4, font=self.F["monob"], bg=C["scope"],
                                fg=C["text"], buttonbackground=C["panel2"],
                                relief="flat", insertbackground=C["accent"],
                                highlightthickness=1, highlightbackground=C["border"],
                                justify="center")
        self.guess.pack(side="left", ipady=4)
        self.guess_var.set("")
        tk.Label(rowf, text=f" / {KEY_BITS}", bg=C["panel"], fg=C["muted"],
                 font=self.F["monob"]).pack(side="left")
        self.guess.bind("<Return>", lambda e: self.submit_bits())

        self.submit_btn = FlatButton(sub, "Submit answer", self.submit_bits,
                                     kind="blue", font=self.F["btn"])
        self.submit_btn.pack(fill="x")

        att = tk.Frame(sub, bg=C["panel"])
        att.pack(fill="x", pady=(10, 0))
        tk.Label(att, text="Attempts", bg=C["panel"], fg=C["muted"],
                 font=self.F["small"]).pack(side="left")
        self.att_dots = tk.Label(att, text="", bg=C["panel"], font=self.F["h2"])
        self.att_dots.pack(side="right")
        self.worth_lbl = tk.Label(sub, text="", bg=C["panel"], fg=C["muted"],
                                  font=self.F["small"], anchor="w")
        self.worth_lbl.pack(fill="x")
        self.feedback = tk.Label(sub, text="", bg=C["panel"], font=self.F["bodyb"],
                                 wraplength=262, justify="left", anchor="w")
        self.feedback.pack(fill="x", pady=(8, 0))

        hint = card(right, "Stuck?", self.F, fill="x", pady=(12, 0))
        self.t_hint = hint.master
        self.hint_text = tk.Label(hint, text="Hints help you find the method. They "
                                  "don't cost points.", bg=C["panel"], fg=C["muted"],
                                  font=self.F["small"], wraplength=262, justify="left",
                                  anchor="w")
        self.hint_text.pack(fill="x")
        self.hint_btn = FlatButton(hint, "", self.next_hint, kind="secondary",
                                   font=self.F["small"])
        self.hint_btn.pack(fill="x", pady=(8, 0))

        self.next_btn = FlatButton(right, "Continue  →  Explain your reasoning",
                                   self.show_short_answer, font=self.F["btn"])

        # centre: scope ----------------------------------------------------
        mid = tk.Frame(body, bg=C["bg"])
        mid.pack(side="left", fill="both", expand=True, padx=16)

        stats = tk.Frame(mid, bg=C["bg"])
        stats.pack(fill="x", pady=(0, 10))
        self.stat_lbls = {}
        for i, (key, title) in enumerate([("n", "Runs collected"), ("mean", "Mean time"),
                                          ("std", "Std deviation"), ("sem", "Std error of mean")]):
            c = tk.Frame(stats, bg=C["panel"], highlightbackground=C["border"],
                         highlightthickness=1)
            c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))
            stats.grid_columnconfigure(i, weight=1, uniform="s")
            tk.Label(c, text=title.upper(), bg=C["panel"], fg=C["muted"],
                     font=self.F["label"]).pack(anchor="w", padx=12, pady=(10, 0))
            v = tk.Label(c, text="—", bg=C["panel"], fg=C["text"], font=self.F["monob"])
            v.pack(anchor="w", padx=12, pady=(2, 10))
            self.stat_lbls[key] = v

        self.t_stats = stats
        scope = tk.Frame(mid, bg=C["panel"], highlightbackground=C["border"],
                         highlightthickness=1)
        self.t_scope = scope
        scope.pack(fill="both", expand=True)
        self.fig = Figure(figsize=(7, 5), dpi=100, facecolor=C["panel"])
        self.ax_runs = self.fig.add_subplot(2, 1, 1)
        self.ax_hist = self.fig.add_subplot(2, 1, 2)
        self.fig.subplots_adjust(left=0.1, right=0.97, top=0.93, bottom=0.1, hspace=0.45)
        self.canvas = FigureCanvasTkAgg(self.fig, master=scope)
        self.canvas.get_tk_widget().configure(bg=C["panel"], highlightthickness=0)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=6)

        self._refresh()
        if not self.tutorial_seen:
            self.root.after(250, self.start_tour)

    # ---------------------------------------------------------- lab actions
    def next_hint(self) -> None:
        if self.hints_shown >= len(HINTS) or not self._hint_available():
            return
        self.hints_shown += 1
        self._hint_view = self.hints_shown - 1
        lines = [f"{i + 1}.  {h}" for i, h in enumerate(HINTS[:self.hints_shown])]
        self.hint_text.config(text="\n\n".join(lines[-1:]), fg=C["text"])
        self._refresh_hint()

    def _hint_available(self) -> bool:
        return not (self.hints_shown == HINT_LOCKED_UNTIL_WRONG and self.attempt == 0)

    def _refresh_hint(self) -> None:
        n = self.hints_shown
        if n >= len(HINTS):
            self.hint_btn.config(text="All hints shown")
            self.hint_btn.set_enabled(False)
        elif not self._hint_available():
            self.hint_btn.config(text="Next hint unlocks after one attempt")
            self.hint_btn.set_enabled(False)
        else:
            self.hint_btn.config(text=f"Show hint {n + 1} of {len(HINTS)}")
            self.hint_btn.set_enabled(True)
        if n > 1:  # let students flip back to earlier hints
            self.hint_text.bind("<Button-1>", lambda e: self._cycle_hint())
            self.hint_text.config(cursor="hand2")

    def _cycle_hint(self) -> None:
        self._hint_view = (getattr(self, "_hint_view", self.hints_shown - 1) + 1) % self.hints_shown
        self.hint_text.config(text=f"{self._hint_view + 1}.  {HINTS[self._hint_view]}"
                                   "\n(click to see your other hints)")

    # ---------------------------------------------------------------- tour
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
             "Pick how many runs to time, then press Run batch. You can run as many "
             "batches as you like. More runs give a more reliable answer."),
            (self.t_scope, "Read the results",
             "Each dot is one run. Random jitter makes the dots scatter, so one run "
             "isn't enough. The white line is the running mean: it settles down as you "
             "add runs. The yellow line in the histogram marks the mean."),
            (self.t_stats, "The numbers",
             "The exact mean time is here. The standard error tells you how much the "
             "mean could still move. Smaller is better."),
            (self.t_sub, "Step 2 · Submit",
             "Enter how many key bits are 1. You get 3 attempts, worth 3, 2 and 1 "
             "points. You'll only be told correct or incorrect."),
            (self.t_hint, "Need help?",
             "Hints are here and don't cost points. The last hint unlocks after your "
             "first attempt. You can replay this tour from \"How to play\" at the top."),
        ]

    def start_tour(self) -> None:
        self.end_tour()
        self.tutorial_seen = True
        self.tour = {"i": 0, "steps": self._tour_steps(), "card": None, "hl": None}
        self._tour_show()

    def end_tour(self) -> None:
        if not self.tour:
            return
        if self.tour["hl"] is not None:
            try:
                self.tour["hl"].config(highlightbackground=C["border"], highlightthickness=1)
            except tk.TclError:
                pass
        if self.tour["card"] is not None:
            self.tour["card"].destroy()
        self.tour = None

    def _tour_move(self, d: int) -> None:
        i = self.tour["i"] + d
        if i >= len(self.tour["steps"]):
            self.end_tour()
            return
        self.tour["i"] = max(0, i)
        self._tour_show()

    def _tour_show(self) -> None:
        t = self.tour
        if t["hl"] is not None:
            t["hl"].config(highlightbackground=C["border"], highlightthickness=1)
        if t["card"] is not None:
            t["card"].destroy()
        target, title, text = t["steps"][t["i"]]
        n = len(t["steps"])

        if target is not None:
            target.config(highlightbackground=C["warn"], highlightthickness=3)
        t["hl"] = target

        W = 360
        cardf = tk.Frame(self.container, bg=C["panel2"], highlightbackground=C["warn"],
                         highlightthickness=2)
        t["card"] = cardf
        inner = tk.Frame(cardf, bg=C["panel2"])
        inner.pack(fill="both", expand=True, padx=18, pady=16)
        tk.Label(inner, text=f"HOW TO PLAY  ·  {t['i'] + 1} / {n}", bg=C["panel2"],
                 fg=C["warn"], font=self.F["label"]).pack(anchor="w")
        tk.Label(inner, text=title, bg=C["panel2"], fg=C["text"],
                 font=self.F["h2"]).pack(anchor="w", pady=(4, 6))
        tk.Label(inner, text=text, bg=C["panel2"], fg=C["text"], font=self.F["body"],
                 wraplength=W - 40, justify="left").pack(anchor="w")
        dots = tk.Label(inner, text=" ".join("●" if k == t["i"] else "○" for k in range(n)),
                        bg=C["panel2"], fg=C["warn"], font=self.F["small"])
        dots.pack(anchor="w", pady=(12, 0))
        row = tk.Frame(inner, bg=C["panel2"])
        row.pack(fill="x", pady=(10, 0))
        last = t["i"] == n - 1
        FlatButton(row, "Let's go!" if last else "Next  →", lambda: self._tour_move(1),
                   font=self.F["btn"]).pack(side="right")
        if t["i"] > 0:
            FlatButton(row, "←  Back", lambda: self._tour_move(-1), kind="secondary",
                       font=self.F["small"]).pack(side="right", padx=6)
        if not last:
            skip = tk.Label(row, text="Skip tour", bg=C["panel2"], fg=C["muted"],
                            font=self.F["small"], cursor="hand2")
            skip.pack(side="left")
            skip.bind("<Button-1>", lambda e: self.end_tour())

        # position the card next to the highlighted element
        self.container.update_idletasks()
        cw, ch = self.container.winfo_width(), self.container.winfo_height()
        cardf.place(x=0, y=0, width=W)
        cardf.update_idletasks()
        h = cardf.winfo_reqheight()
        if target is None:
            x, y = (cw - W) // 2, (ch - h) // 2
        else:
            tx = target.winfo_rootx() - self.container.winfo_rootx()
            ty = target.winfo_rooty() - self.container.winfo_rooty()
            tw, th = target.winfo_width(), target.winfo_height()
            if tx + tw / 2 < cw * 0.3:            # left column -> card on its right
                x, y = tx + tw + 16, ty
            elif tx + tw / 2 > cw * 0.7:          # right column -> card on its left
                x, y = tx - W - 16, ty
            elif th > ch * 0.4:                   # big centre panel -> inside it
                x, y = tx + tw - W - 20, ty + 20
            else:                                 # small centre element -> below it
                x, y = tx + (tw - W) // 2, ty + th + 16
            y = max(10, min(y, ch - h - 10))
        cardf.place(x=x, y=y, width=W)
        cardf.lift()
    def run_batch(self) -> None:
        new = self.sim.run_batch(self.runs_var.get())
        self.n_batches += 1
        self.times = np.concatenate([self.times, new])
        self.batch_ids = np.concatenate([self.batch_ids, np.full(len(new), self.n_batches)])
        self._refresh()

    def clear_runs(self) -> None:
        self.times = np.empty(0)
        self.batch_ids = np.empty(0, dtype=int)
        self.n_batches = 0
        self._refresh()

    def submit_bits(self) -> None:
        if self.bits_done or not self.submit_btn.enabled:
            return
        try:
            g = int(self.guess_var.get().strip())
            if not 0 <= g <= KEY_BITS:
                raise ValueError
        except ValueError:
            self.feedback.config(text=f"Enter a whole number from 0 to {KEY_BITS}.",
                                 fg=C["warn"])
            return
        self.attempt += 1
        if g == self.sim.ones:
            self.bit_points = points_for_attempt(self.attempt)
            self.bits_done = True
            self.feedback.config(fg=C["good"], text=f"✔  Correct!  +{self.bit_points} points")
        elif self.attempt >= MAX_ATTEMPTS:
            self.bits_done = True
            self.feedback.config(fg=C["bad"], text="✘  Incorrect. No attempts left.")
        else:
            self.feedback.config(fg=C["bad"], text="✘  Incorrect. Try again.")
        self._refresh()

    def _refresh(self) -> None:
        # attempt dots + availability
        left = MAX_ATTEMPTS - self.attempt
        self.att_dots.config(text="● " * left + "○ " * self.attempt,
                             fg=C["accent2"] if left else C["dim"])
        if self.bits_done:
            self.worth_lbl.config(text="")
        else:
            self.worth_lbl.config(
                text=f"Next correct answer is worth {points_for_attempt(self.attempt + 1)} pts")
        has_data = len(self.times) >= MIN_RUNS
        self.submit_btn.set_enabled(has_data and not self.bits_done)
        if not has_data and not self.bits_done and not self.feedback.cget("text"):
            self.feedback.config(text="Run at least one batch first.", fg=C["muted"])
        elif has_data and self.feedback.cget("text") == "Run at least one batch first.":
            self.feedback.config(text="")
        if self.bits_done:
            self.guess.config(state="disabled")
            self.t_hint.pack_forget()  # hints are only for the bit-count puzzle
            self.next_btn.pack(fill="x", pady=(12, 0))
        self.score_lbl.config(text=self._score_text())
        self._refresh_hint()

        # stats
        t = self.times
        if len(t):
            self.stat_lbls["n"].config(text=f"{len(t)}")
            self.stat_lbls["mean"].config(text=f"{t.mean():,.1f} µs")
            sd = t.std(ddof=1) if len(t) > 1 else 0.0
            self.stat_lbls["std"].config(text=f"{sd:,.1f} µs")
            self.stat_lbls["sem"].config(text=f"± {sd / np.sqrt(len(t)):,.1f} µs")
        else:
            for v in self.stat_lbls.values():
                v.config(text="—")

        self._draw()

    def _style_ax(self, ax, title, xlabel, ylabel) -> None:
        ax.set_facecolor(C["scope"])
        for s in ax.spines.values():
            s.set_color(C["border"])
        ax.tick_params(colors=C["muted"], labelsize=8)
        ax.grid(True, color="#1d2a36", linewidth=0.8)
        ax.set_axisbelow(True)
        ax.set_title(title, color=C["text"], fontsize=10, loc="left", fontweight="bold",
                     family=self.sans_family)
        ax.set_xlabel(xlabel, color=C["muted"], fontsize=8.5)
        ax.set_ylabel(ylabel, color=C["muted"], fontsize=8.5)

    def _draw(self) -> None:
        a1, a2 = self.ax_runs, self.ax_hist
        a1.clear()
        a2.clear()
        self._style_ax(a1, "Execution time per run", "run #", "time (µs)")
        self._style_ax(a2, "Distribution of execution times", "time (µs)", "runs")
        t = self.times
        if not len(t):
            for ax in (a1, a2):
                ax.set_xticks([])
                ax.set_yticks([])
            a1.text(0.5, 0.5, "No measurements yet — press  ▶ Run batch",
                    transform=a1.transAxes, ha="center", va="center",
                    color=C["dim"], fontsize=11)
            self.canvas.draw_idle()
            return

        palette = ["#3ddc97", "#58a6ff", "#f2cc60", "#d2a8ff", "#ff9b6b", "#7ee0e6"]
        x = np.arange(1, len(t) + 1)
        for b in np.unique(self.batch_ids):
            m = self.batch_ids == b
            a1.scatter(x[m], t[m], s=14, color=palette[(b - 1) % len(palette)],
                       alpha=0.9, linewidths=0, label=f"batch {b}")
        running = np.cumsum(t) / x
        a1.plot(x, running, color=C["text"], linewidth=1.6, label="running mean")
        a1.set_xlim(0, max(len(t) + 1, MIN_RUNS))
        pad = max(3 * JITTER_SIGMA_US, 1)
        a1.set_ylim(t.mean() - 1.6 * pad, t.mean() + 1.6 * pad)
        leg = a1.legend(loc="upper right", fontsize=7.5, facecolor=C["panel2"],
                        edgecolor=C["border"], labelcolor=C["text"], ncol=4)
        leg.get_frame().set_alpha(0.9)

        bins = max(10, min(30, len(t) // 4))
        a2.hist(t, bins=bins, color=C["accent2"], alpha=0.75, edgecolor=C["scope"])
        mean = t.mean()
        sem = t.std(ddof=1) / np.sqrt(len(t)) if len(t) > 1 else 0
        a2.axvspan(mean - sem, mean + sem, color=C["warn"], alpha=0.18, linewidth=0)
        a2.axvline(mean, color=C["warn"], linewidth=1.8)
        a2.text(mean, a2.get_ylim()[1] * 0.92, f"  mean = {mean:,.1f} µs",
                color=C["warn"], fontsize=8.5, va="top", family=self.mono_family)
        self.canvas.draw_idle()

    # --------------------------------------------------------- short answer
    def show_short_answer(self) -> None:
        self._clear()
        self._topbar("Explain your reasoning")
        wrap = tk.Frame(self.container, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        q = card(wrap, "Short answer", self.F, fill="both", expand=True)
        tk.Label(q, justify="left", wraplength=1000, bg=C["panel"], fg=C["text"],
                 font=self.F["h2"], text=(
                     "In a few full sentences: why does the lock's total execution time "
                     "reveal how many key bits are 1? Is there anything about the key "
                     "that timing cannot tell you, and why?")).pack(anchor="w")
        tk.Label(q, text="Answer in your own words. You can submit once.",
                 bg=C["panel"], fg=C["muted"], font=self.F["small"]).pack(anchor="w",
                                                                         pady=(4, 10))
        self.answer = tk.Text(q, height=9, wrap="word", bg=C["scope"], fg=C["text"],
                              insertbackground=C["accent"], relief="flat",
                              font=(self.sans_family, 12), padx=12, pady=10,
                              highlightthickness=1, highlightbackground=C["border"],
                              highlightcolor=C["accent"])
        self.answer.pack(fill="both", expand=True)
        self.answer.focus_set()

        bottom = tk.Frame(q, bg=C["panel"])
        bottom.pack(fill="x", pady=(10, 0))
        self.wc = tk.Label(bottom, text="0 words", bg=C["panel"], fg=C["muted"],
                           font=self.F["small"])
        self.wc.pack(side="left")
        self.sa_submit = FlatButton(bottom, "Submit explanation", self.submit_answer,
                                    kind="blue", font=self.F["btn"])
        self.sa_submit.pack(side="right")
        self.answer.bind("<KeyRelease>", lambda e: self.wc.config(
            text=f"{len(self.answer.get('1.0', 'end').split())} words"))

        self.sa_result = tk.Frame(q, bg=C["panel"])
        self.sa_result.pack(fill="x", pady=(12, 0))

    def submit_answer(self) -> None:
        text = self.answer.get("1.0", "end").strip()
        if len(text.split()) < 12:
            self.wc.config(text="Please write at least a couple of full sentences.",
                           fg=C["warn"])
            return
        self.sa_submit.set_enabled(False)
        self.sa_submit.unbind("<Button-1>")
        self.answer.config(state="disabled", fg=C["muted"])
        results = score_short_answer(text)
        self.sa_points = sum(1 for r in results if r[1])
        self.score_lbl.config(text=self._score_text())

        tk.Label(self.sa_result, text=f"Rubric check: {self.sa_points} / {len(results)}",
                 bg=C["panel"], fg=C["text"], font=self.F["h2"]).pack(anchor="w", pady=(0, 6))
        for _, met, desc, hint in results:
            row = tk.Frame(self.sa_result, bg=C["panel"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text="✔" if met else "✘", width=2, bg=C["panel"],
                     fg=C["good"] if met else C["bad"], font=self.F["bodyb"]).pack(side="left")
            tk.Label(row, text=desc if met else f"Missing — hint: {hint}", bg=C["panel"],
                     fg=C["text"] if met else C["muted"], font=self.F["body"],
                     anchor="w", justify="left", wraplength=980).pack(side="left", fill="x")
        FlatButton(self.sa_result, "Finish level  →", self.show_results,
                   font=self.F["btn"]).pack(anchor="e", pady=(10, 0))

    # -------------------------------------------------------------- results
    def show_results(self) -> None:
        self._clear()
        self._topbar("Level complete")
        wrap = tk.Frame(self.container, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        top = tk.Frame(wrap, bg=C["bg"])
        top.pack(fill="x")
        for i, (title, val, sub) in enumerate([
            ("Bit count", f"{self.bit_points} / 3",
             f"solved on attempt {self.attempt}" if self.bit_points else "not solved"),
            ("Explanation", f"{self.sa_points} / 3", "rubric points 1 & 2"),
            ("Level total", f"{self.bit_points + self.sa_points} / 6", ""),
        ]):
            c = tk.Frame(top, bg=C["panel"], highlightbackground=C["border"],
                         highlightthickness=1)
            c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 12, 0))
            top.grid_columnconfigure(i, weight=1, uniform="r")
            tk.Label(c, text=title.upper(), bg=C["panel"], fg=C["muted"],
                     font=self.F["label"]).pack(anchor="w", padx=18, pady=(14, 0))
            tk.Label(c, text=val, bg=C["panel"], fg=C["accent"] if i == 2 else C["text"],
                     font=self.F["big"]).pack(anchor="w", padx=18)
            tk.Label(c, text=sub, bg=C["panel"], fg=C["muted"],
                     font=self.F["small"]).pack(anchor="w", padx=18, pady=(0, 14))

        k = self.sim.ones
        reveal = card(wrap, "What you learned about the key", self.F, fill="x", pady=(16, 0))
        tk.Label(reveal, bg=C["panel"], fg=C["text"], font=self.F["body"], justify="left",
                 wraplength=1200, text=(
                     f"The key has {k} one-bits, so every run did 16 squares and {k} "
                     f"multiplies:   T ≈ 16 × {T_S_US:.0f} + {k} × {T_M_US:.0f} = "
                     f"{16 * T_S_US + k * T_M_US:,.0f} µs.   Averaging many runs cancels "
                     "the jitter, so the mean pins down the number of multiplies.")).pack(
            anchor="w")
        boxes = tk.Frame(reveal, bg=C["panel"])
        boxes.pack(anchor="w", pady=(14, 6))
        for i in range(KEY_BITS):
            tk.Label(boxes, text="?", width=3, bg=C["scope"], fg=C["warn"],
                     font=self.F["monob"], highlightthickness=1,
                     highlightbackground=C["border"]).pack(side="left", padx=2, ipady=6)
        tk.Label(reveal, bg=C["panel"], fg=C["muted"], font=self.F["body"],
                 text=f"{k} of these 16 bits are 1 — but timing can't tell you which ones. "
                      "A power trace can.  →  Level 2: Simple Power Analysis").pack(
            anchor="w", pady=(4, 0))

        btns = tk.Frame(wrap, bg=C["bg"])
        btns.pack(fill="x", pady=(16, 0))
        FlatButton(btns, "Quit", self.root.destroy, kind="secondary",
                   font=self.F["btn"]).pack(side="right")
        FlatButton(btns, "Replay level", lambda: self.start(self.student_id),
                   kind="secondary", font=self.F["btn"]).pack(side="right", padx=8)


# =============================================================================

def main() -> None:
    ap = argparse.ArgumentParser(description="Side-Channel Lab — Level 1 (Timing)")
    ap.add_argument("--student-id", help="skip the sign-in screen")
    ap.add_argument("--protect", action="store_true",
                    help="Windows only: hide the window from screenshots / screen recording")
    args = ap.parse_args()

    if sys.platform == "win32":  # crisp text on high-DPI Windows displays
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    root = tk.Tk()
    Level1App(root, args.student_id, args.protect)
    root.mainloop()


if __name__ == "__main__":
    main()
