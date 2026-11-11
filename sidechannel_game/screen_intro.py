"""
screen_intro.py -- the Introduction level: read a few pages of text with
figures, answer the true/false checks, and unlock Level 1.

The words live in intro_content.py (edit that file, not this one).
This file draws the pages and the built-in figures.

Scoring: each true/false question is worth TF_POINTS (5) points. Pressing
FINISH on the last page scores the level; below progress.PASS_FRACTION (70%)
the level is failed and must be played again before Level 1 unlocks.
Replaying a passed level never changes the record.

TINKER:
  * To add a built-in figure: write a function fig_xxx(canvas, F) like the ones
    below and register it in FIGURES at the bottom of the file.
  * To use your own picture instead, put "assets/yourfile.png" as the page's
    "figure" in intro_content.py.
"""

import os
import tkinter as tk

import numpy as np

import audio
import intro_content
import progress
import scene_art
from retro import (C, Pips, ReadOnlyText, RetroButton, font, hexcolor, panel, px, topbar)
import retro

HERE = os.path.dirname(os.path.abspath(__file__))
FIG_W, FIG_H = 560, 340          # size of the figure area in pixels
TF_POINTS = 5                    # points per true/false question


# =============================================================================
# Small drawing helpers (blocky shapes on a Tk canvas)
# =============================================================================
def _rect(c, x0, y0, x1, y1, fill, outline="", width=0):
    return c.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline, width=width)


def _sprite(c, rows, palette, x, y, unit):
    """Draw a pixel sprite (list of strings) as unit x unit squares."""
    for j, row in enumerate(rows):
        i = 0
        while i < len(row):
            ch = row[i]
            if ch in palette:
                k = i
                while k + 1 < len(row) and row[k + 1] == ch:
                    k += 1
                _rect(c, x + i * unit, y + j * unit, x + (k + 1) * unit,
                      y + (j + 1) * unit, palette[ch])
                i = k + 1
            else:
                i += 1


def _arrow(c, x0, y0, x1, y1, color, width=4):
    c.create_line(x0, y0, x1, y1, fill=color, width=width, arrow="last",
                  arrowshape=(14, 16, 7), capstyle="butt")


def _fonts(F, size, bold=True):
    return font(size, bold)


# =============================================================================
# Figures.  Each takes (canvas, fonts) and draws into a FIG_W x FIG_H area.
# =============================================================================
def fig_padlock(c, F):
    palette = {k: hexcolor(v) for k, v in scene_art.PADLOCK_PALETTE.items()}
    _sprite(c, scene_art.PADLOCK, palette, 50, 92, 12)
    x = 250
    c.create_text(x, 90, text="THE MATH", anchor="w", fill=C["muted"], font=_fonts(F, 13))
    c.create_text(x, 124, text="UNBREAKABLE", anchor="w", fill=C["good"], font=_fonts(F, 28))
    c.create_text(x, 190, text="THE CHIP", anchor="w", fill=C["muted"], font=_fonts(F, 13))
    c.create_text(x, 224, text="LEAKS", anchor="w", fill=C["bad"], font=_fonts(F, 28))
    c.create_text(FIG_W // 2, FIG_H - 22, text="Strong math on leaky hardware is still leaky.",
                  fill=C["muted"], font=_fonts(F, 10, False))


def fig_leak(c, F):
    # the chip
    _rect(c, 36, 96, 176, 236, "#1a1a28", C["amber"], 4)
    for k in range(5):
        _rect(c, 22, 112 + k * 26, 36, 120 + k * 26, "#c4c8d4")
        _rect(c, 176, 112 + k * 26, 190, 120 + k * 26, "#c4c8d4")
    c.create_text(106, 150, text="MCU", fill=C["amber"], font=_fonts(F, 22))
    c.create_text(106, 196, text="KEY: ????", fill=C["cyan"], font=_fonts(F, 11))
    # three signals leaving the chip
    rows = [(110, "EXECUTION TIME", C["cyan"]), (166, "POWER DRAW", C["amber"]),
            (222, "EM EMISSIONS", C["good"])]
    for y, label, color in rows:
        pts = [200, y]
        x = 200
        for k in range(10):                       # zig-zag = a signal
            x += 14
            pts += [x, y + (9 if k % 2 == 0 else -9)]
        pts += [x + 14, y]
        c.create_line(*pts, fill=color, width=3)
        _arrow(c, x + 14, y, 384, y, color, 3)
        c.create_text(200, y - 22, text=label, anchor="w", fill=C["muted"], font=_fonts(F, 10))
    # the attacker
    _rect(c, 392, 96, 538, 236, C["panel"], C["bad"], 4)
    c.create_text(465, 146, text="ATTACKER", fill=C["bad"], font=_fonts(F, 16))
    c.create_text(465, 176, text="with a scope", fill=C["muted"], font=_fonts(F, 11, False))
    c.create_text(FIG_W // 2, FIG_H - 22, text="The secret leaks out through the physics.",
                  fill=C["muted"], font=_fonts(F, 10, False))


def fig_square_multiply(c, F):
    bits = [1, 0, 1, 1, 0, 0]
    s_w, m_w, gap = 40, 60, 12          # M is 1.5 x as long as S
    total = len(bits) * s_w + sum(bits) * m_w + (len(bits) - 1) * gap
    x = (FIG_W - total) // 2
    c.create_text(FIG_W // 2, 28, text="AN EXAMPLE KEY (SHORT)", fill=C["muted"],
                  font=_fonts(F, 11))
    c.create_text(x, 52, text="KEY BIT", anchor="w", fill=C["muted"], font=_fonts(F, 9))
    y0, y1 = 128, 178
    c.create_text(x, 114, text="WHAT THE CHIP DOES", anchor="w", fill=C["muted"],
                  font=_fonts(F, 9))
    for bit in bits:
        width = s_w + (m_w if bit else 0)
        c.create_text(x + width // 2, 82, text=str(bit), fill=C["text"], font=_fonts(F, 22))
        _rect(c, x, y0, x + s_w, y1, C["cyan"])
        c.create_text(x + s_w // 2, (y0 + y1) // 2, text="S", fill="#001820", font=_fonts(F, 16))
        if bit:
            _rect(c, x + s_w, y0, x + width, y1, C["amber"])
            c.create_text(x + s_w + m_w // 2, (y0 + y1) // 2, text="M", fill="#1a1000",
                          font=_fonts(F, 16))
        x += width + gap
    ax = (FIG_W - total) // 2
    _arrow(c, ax, 202, ax + total, 202, C["muted"], 3)
    c.create_text(ax + total, 220, text="TIME", anchor="e", fill=C["muted"], font=_fonts(F, 10))
    # legend
    _rect(c, 60, 236, 84, 258, C["cyan"])
    c.create_text(96, 247, text="S  SQUARE: every bit", anchor="w", fill=C["text"],
                  font=_fonts(F, 11, False))
    _rect(c, 60, 268, 84, 290, C["amber"])
    c.create_text(96, 279, text="M  MULTIPLY: only if the bit is 1", anchor="w",
                  fill=C["text"], font=_fonts(F, 11, False))
    c.create_text(FIG_W // 2, FIG_H - 22, text="M takes 1.5 x as long as S.",
                  fill=C["muted"], font=_fonts(F, 10, False))


def fig_hamming(c, F):
    rng = np.random.default_rng(11)

    def word(ones):
        bits = np.zeros(32, dtype=int)
        bits[rng.choice(32, ones, replace=False)] = 1
        return bits

    words = [("WORD A", word(6), 56), ("WORD B", word(14), 176)]
    size, gap = 15, 3
    for label, bits, y in words:
        c.create_text(24, y - 14, text="%s: %d ONES" % (label, bits.sum()), anchor="w",
                      fill=C["muted"], font=_fonts(F, 10))
        for k, b in enumerate(bits):
            col, row = k % 16, k // 16
            x0 = 24 + col * (size + gap)
            y0 = y + row * (size + gap)
            if b:
                _rect(c, x0, y0, x0 + size, y0 + size, C["amber"])
            else:
                _rect(c, x0, y0, x0 + size, y0 + size, C["inset"], C["dim"], 1)
    # the resulting block heights
    base, per_one = 290, 14
    c.create_text(396, 28, text="BLOCK HEIGHT", fill=C["cyan"], font=_fonts(F, 11))
    for name, ones, x in (("A", 6, 360), ("B", 14, 450)):
        _rect(c, x, base - ones * per_one, x + 56, base, C["cyan"])
        c.create_text(x + 28, base - ones * per_one - 14, text=str(ones), fill=C["text"],
                      font=_fonts(F, 14))
        c.create_text(x + 28, base + 16, text=name, fill=C["muted"], font=_fonts(F, 11))
    c.create_line(340, base, 540, base, fill=C["border_hi"], width=3)
    c.create_text(24, FIG_H - 22, text="More 1 bits in the data = a taller block.",
                  anchor="w", fill=C["muted"], font=_fonts(F, 10, False))


def fig_trace(c, F):
    rng = np.random.default_rng(5)
    bits = [1, 0, 1, 1, 0]
    s_len, m_len, gap, pad = 10, 15, 4, 4

    def build(sigma):
        values, spans = [0.0] * pad, []
        for bit in bits:
            start = len(values)
            n = s_len + (m_len if bit else 0)
            values += [float(rng.integers(13, 20))] * n
            spans.append((start, start + n, bit))
            values += [0.0] * gap
        values += [0.0] * pad
        clean = np.array(values)
        return clean, clean + rng.normal(0, sigma, len(clean)), spans

    rng_state = rng.bit_generator.state
    clean, _, spans = build(0.0)
    rng.bit_generator.state = rng_state
    _, noisy, _ = build(10.0)

    def plot(y_top, data, color, label):
        left, right, h = 24, FIG_W - 24, 112
        _rect(c, left, y_top, right, y_top + h, C["inset"], C["border"], 2)
        n = len(data)
        pts = []
        for i, v in enumerate(data):
            pts += [left + 4 + i * (right - left - 8) / (n - 1), y_top + h - 8 - v * 3.2]
        c.create_line(*pts, fill=color, width=2)
        c.create_text(left + 6, y_top - 12, text=label, anchor="w", fill=color, font=_fonts(F, 10))
        return left + 4, (right - left - 8) / (n - 1)

    x0, step = plot(40, clean, C["cyan"], "HIGH SNR: THE PATTERN IS EASY TO READ")
    for start, end, bit in spans:                          # label each block
        c.create_text(x0 + (start + end) / 2 * step, 52, text="S+M" if bit else "S",
                      fill=C["amber"] if bit else C["cyan"], font=_fonts(F, 11))
    plot(206, noisy, C["amber"], "LOW SNR: THE PATTERN IS BURIED IN NOISE")


# Names usable as "figure" in intro_content.py
FIGURES = {
    "padlock": fig_padlock,
    "leak": fig_leak,
    "square_multiply": fig_square_multiply,
    "hamming": fig_hamming,
    "trace": fig_trace,
}


# =============================================================================
# The screen
# =============================================================================
class IntroScreen(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=C["bg"])
        self.app, self.save, self.F = app, app.save, app.fonts
        # reading pages use a larger body font than the rest of the game
        self.read_fonts = {**self.F, "body": font(14), "bodyb": font(14, True)}
        self.pages = intro_content.PAGES
        self.practice = self.save.is_complete("intro")   # replay: record is not changed
        self.index = 0
        self.tf_results = {}                             # page index -> answered correctly?
        self._images = []                                # keep PhotoImages alive

        _, right = topbar(self, self.F, "INTRODUCTION", "Briefing", self.app.show_menu)
        if self.practice:
            tk.Label(right, text="REPLAY: RECORD NOT CHANGED", bg=C["bg"], fg=C["muted"],
                     font=self.F["label"]).pack(anchor="e")
        self.page_lbl = tk.Label(right, text="", bg=C["bg"], fg=C["text"], font=self.F["bodyb"])
        self.page_lbl.pack(anchor="e")

        # The nav bar is packed BEFORE the page body (at the bottom) so it always
        # keeps its space; otherwise tall reading pages pushed it off-screen.
        nav = tk.Frame(self, bg=C["bg"])
        nav.pack(side="bottom", fill="x", padx=24, pady=(0, 18))
        self.body = tk.Frame(self, bg=C["bg"])
        self.body.pack(fill="both", expand=True, padx=24, pady=(0, 10))
        self.back_btn = RetroButton(nav, "< BACK", self.back, kind="secondary",
                                    font=self.F["btn"])
        self.back_btn.pack(side="left")
        self.pips = Pips(nav, len(self.pages), bg=C["bg"])
        self.pips.pack(side="left", padx=24)
        self.next_btn = RetroButton(nav, "NEXT >", self.next, font=self.F["btn"])
        self.next_btn.pack(side="right")

        self.bind_all("<Left>", lambda e: self.back())
        self.bind_all("<Right>", lambda e: self.next())
        self.render()

    # ---------------------------------------------------------------- drawing
    def render(self):
        for w in self.body.winfo_children():
            w.destroy()
        self._images.clear()
        page = self.pages[self.index]
        if "tf" in page:
            self._render_tf(page)
        else:
            self._render_reading(page)
        last = self.index == len(self.pages) - 1
        self.page_lbl.config(text="PAGE %d / %d" % (self.index + 1, len(self.pages)))
        self.pips.set(self.index + 1, on="amber", off="dim")
        self.back_btn.set_enabled(self.index > 0)
        self.next_btn.config(text="FINISH" if last else "NEXT >")
        self.next_btn.sound = None if last else "click"   # FINISH plays pass / fail
        self._refresh_next()

    def _render_reading(self, page):
        # Pack the figure first so it always keeps its space, then let the
        # text panel take whatever is left.
        if page.get("figure"):
            frame = panel(self.body, None, self.F, side="right", fill="y", padx=(14, 0))
            canvas = tk.Canvas(frame, width=px(FIG_W), height=px(FIG_H), bg=C["inset"],
                               highlightthickness=0)
            canvas.pack(expand=True)                  # centred vertically
            self._draw_figure(canvas, page["figure"])
            if retro.UI["scale"] != 1.0:              # figures are drawn at 96-DPI size
                canvas.scale("all", 0, 0, retro.UI["scale"], retro.UI["scale"])

        left = panel(self.body, page["title"], self.F, side="left", fill="both", expand=True)
        text = ReadOnlyText(left, self.read_fonts, width=24)
        text.config(spacing3=14)
        text.pack(fill="both", expand=True)
        text.set_paragraphs(page.get("text", []))

    def _draw_figure(self, canvas, figure):
        if figure in FIGURES:
            FIGURES[figure](canvas, self.F)
            return
        path = os.path.join(HERE, figure)                # a picture the author supplied
        try:
            image = tk.PhotoImage(file=path)
            self._images.append(image)
            canvas.create_image(FIG_W // 2, FIG_H // 2, image=image)
        except (tk.TclError, OSError):
            canvas.create_text(FIG_W // 2, FIG_H // 2, text="FIGURE NOT FOUND:\n%s" % figure,
                               fill=C["bad"], font=self.F["bodyb"], justify="center")

    def _render_tf(self, page):
        tf = page["tf"]
        box = panel(self.body, page["title"], self.F, expand=True, ipadx=px(40), ipady=px(20))
        tk.Label(box, text="TRUE OR FALSE?", bg=C["panel"], fg=C["cyan"],
                 font=self.F["label"]).pack(pady=(6, 10))
        tk.Label(box, text=tf["statement"], bg=C["panel"], fg=C["text"], font=self.F["h1"],
                 wraplength=px(640), justify="center").pack(pady=(0, 24))
        row = tk.Frame(box, bg=C["panel"])
        row.pack()
        self.true_btn = RetroButton(row, "TRUE", lambda: self._answer(True), kind="good", sound=None,
                                    font=self.F["h2"])
        self.true_btn.pack(side="left", padx=12)
        self.false_btn = RetroButton(row, "FALSE", lambda: self._answer(False), kind="bad", sound=None,
                                     font=self.F["h2"])
        self.false_btn.pack(side="left", padx=12)
        self.feedback = tk.Label(box, text="", bg=C["panel"], font=self.F["bodyb"],
                                 wraplength=px(640), justify="center")
        self.feedback.pack(pady=(24, 6))
        if self.index in self.tf_results:                # already answered (came back)
            self._show_feedback(self.tf_results[self.index])

    # ---------------------------------------------------------------- actions
    def _answer(self, value):
        if self.index in self.tf_results:
            return
        tf = self.pages[self.index]["tf"]
        self.tf_results[self.index] = (value == tf["answer"])
        audio.play("correct" if self.tf_results[self.index] else "wrong")
        self._show_feedback(self.tf_results[self.index])
        self._refresh_next()

    def _show_feedback(self, correct):
        tf = self.pages[self.index]["tf"]
        self.true_btn.set_enabled(False)
        self.false_btn.set_enabled(False)
        self.feedback.config(
            text=("CORRECT!  " if correct else "NOT QUITE.  ") + tf["explanation"],
            fg=C["good"] if correct else C["bad"])

    def _refresh_next(self):
        page = self.pages[self.index]
        needs_answer = "tf" in page and self.index not in self.tf_results
        self.next_btn.set_enabled(not needs_answer)

    def back(self):
        if self.index > 0:
            self.index -= 1
            self.render()

    def next(self):
        if not self.next_btn.enabled:
            return
        if self.index < len(self.pages) - 1:
            self.index += 1
            self.render()
        else:
            self.finish()

    def finish(self):
        if self.practice:
            self.app.show_menu()
            return
        correct = sum(self.tf_results.values())
        total = sum(1 for p in self.pages if "tf" in p)
        score, max_score = correct * TF_POINTS, total * TF_POINTS
        if progress.passed(score, max_score):
            self.save.mark_complete("intro", tf_correct=correct, tf_total=total,
                                    score=score, max_score=max_score)
            audio.play("correct")
            self.app.show_menu(message="LEVEL 1 UNLOCKED!")
        else:
            audio.play("wrong")
            self.save.fail_level("intro", score, max_score)
            self.app.show_menu(message=self.app.fail_message("intro"), seconds=6)

    def destroy(self):
        for seq in ("<Left>", "<Right>"):
            try:
                self.unbind_all(seq)
            except tk.TclError:
                pass
        super().destroy()
