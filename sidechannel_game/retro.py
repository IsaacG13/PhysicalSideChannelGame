"""
retro.py -- the shared "retro" look: colours, fonts, chunky widgets, pixel
headings and Matplotlib styling. Every screen imports from here, so changing
a colour or a font in this one file restyles the whole game.

How the retro look is made (no CRT filter anywhere):
  * a limited, high-contrast colour palette (PALETTE below)
  * hard square corners and thick bevelled borders instead of thin rounded ones
  * a built-in pixel font for big headings (pixelfont.py)
  * pixel-art images enlarged with hard edges (nearest-neighbour zoom)
  * plots with squares for markers and no anti-aliasing
"""

import sys
import tkinter as tk
import tkinter.font as tkfont

import numpy as np

import audio
import pixelfont

# =============================================================================
# Palette.  TINKER: change these to re-colour everything.
# =============================================================================
PALETTE = {
    "bg": "#0d0a1a",          # screen background (deep violet-black)
    "panel": "#17122d",       # panel fill
    "panel2": "#231b45",      # raised / hovered panel fill
    "inset": "#0a0816",       # sunken areas (plots, text boxes)
    "border": "#5b4b9a",      # panel border
    "border_hi": "#8f7be0",   # bright border / bevel highlight
    "text": "#f1e9d2",        # body text (warm cream)
    "muted": "#a49cc4",       # secondary text
    "dim": "#5d5780",         # disabled / locked
    "amber": "#ffb000",       # main accent
    "amber_dk": "#a86f00",
    "amber_hi": "#ffd35a",
    "cyan": "#4de1ff",        # secondary accent
    "cyan_dk": "#1f7f95",
    "good": "#5cff8a",
    "bad": "#ff5a5a",
    "warn": "#ffd35a",
}
C = PALETTE   # short alias used across the code


def rgb(name):
    """Palette colour as an (r, g, b) tuple, e.g. for pixel buffers."""
    h = C.get(name, name).lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# =============================================================================
# Fonts
# =============================================================================
MONO_CANDIDATES = ["Consolas", "Menlo", "DejaVu Sans Mono", "Liberation Mono",
                   "Lucida Console", "Courier New", "Courier"]


def pick_font(root, candidates):
    families = set(tkfont.families(root))
    for name in candidates:
        if name in families:
            return name
    return "Courier"


# --- display scaling -----------------------------------------------------------
# All sizes in the game are designed for a normal 96-DPI screen. On a high-DPI
# display (e.g. Windows at 150%) every size is multiplied by UI["scale"] so the
# layout keeps its proportions. Fonts are specified in PIXELS (negative sizes in
# Tk), which also makes text the same size on Windows, macOS and Linux.
UI = {"scale": 1.0, "family": "Courier"}


def px(n):
    """A layout size in pixels, scaled for the current display."""
    return int(round(n * UI["scale"]))


def font(points, bold=False):
    """A font tuple. `points` is the size on a 96-DPI screen (11 = body text)."""
    size = -max(1, int(round(points * 96 / 72 * UI["scale"])))
    return (UI["family"], size, "bold") if bold else (UI["family"], size)


def display_scale(root):
    """1.0 on normal screens, 1.25 / 1.5 / 2.0 ... on high-DPI ones."""
    try:
        dpi = root.winfo_fpixels("1i")
    except tk.TclError:
        dpi = 96.0
    return max(1.0, round(dpi / 96.0 * 4) / 4)        # quarter steps; never below 1


def make_fonts(root):
    """Create the font set used by every screen. Returns a dict of tuples.
    Call this once, right after the Tk root exists: it also sets the display scale."""
    UI["scale"] = display_scale(root)
    UI["family"] = pick_font(root, MONO_CANDIDATES)
    return {
        "family": UI["family"],
        "body": font(11),
        "bodyb": font(11, True),
        "small": font(10),
        "smallb": font(10, True),
        "label": font(9, True),
        "h2": font(13, True),
        "h1": font(17, True),
        "big": font(24, True),
        "btn": font(11, True),
        "stat": font(14, True),
    }


# =============================================================================
# Pixel images
# =============================================================================
def array_to_photo(arr, zoom=1):
    """Turn an HxWx3 uint8 array into a Tk PhotoImage, enlarged by `zoom`
    with hard edges. (PPM is built in to Tk, so no extra libraries are needed.)"""
    arr = np.ascontiguousarray(arr, dtype=np.uint8)
    h, w = arr.shape[:2]
    photo = tk.PhotoImage(data=b"P6 %d %d 255\n" % (w, h) + arr.tobytes(), format="PPM")
    return photo.zoom(zoom) if zoom > 1 else photo


def pixel_text_photo(text, zoom=3, color="amber", bg="panel", shadow="amber_dk",
                     outline=None, pad=2):
    """A heading drawn in the built-in pixel font, as a PhotoImage."""
    w, h = pixelfont.text_size(text)
    buf = np.zeros((h + 2 * pad + 1, w + 2 * pad + 1, 3), dtype=np.uint8)
    buf[:] = rgb(bg)
    pixelfont.draw_text(buf, pad, pad, text, rgb(color),
                        shadow=rgb(shadow) if shadow else None,
                        outline=rgb(outline) if outline else None)
    return array_to_photo(buf, zoom)


def pixel_label(master, text, zoom=3, color="amber", bg="panel", shadow="amber_dk",
                outline=None, **kw):
    """A tk.Label showing pixel-font text. Keeps a reference to the image."""
    photo = pixel_text_photo(text, max(1, int(round(zoom * UI["scale"]))), color, bg, shadow,
                             outline)
    lbl = tk.Label(master, image=photo, bg=C[bg], bd=0, highlightthickness=0, **kw)
    lbl.image = photo
    return lbl


# =============================================================================
# Widgets
# =============================================================================
class RetroButton(tk.Label):
    """A chunky bevelled button. (A Label rather than tk.Button, because
    macOS ignores colours on real buttons.)

    kind: "primary" (amber), "secondary" (purple), "blue" (cyan)
    sound: audio effect played on click ("click" by default). Answer buttons
           pass sound=None and play "correct" / "wrong" themselves.
    """

    KINDS = {
        "primary": ("amber", "#1a1000", "amber_hi"),
        "secondary": ("panel2", "text", "border"),
        "blue": ("cyan", "#001820", "#9aefff"),
        "good": ("good", "#00200c", "#9affb8"),
        "bad": ("bad", "#250000", "#ff9a9a"),
    }

    def __init__(self, master, text, command, kind="primary", font=None, sound="click", **kw):
        self.sound = sound
        bg, fg, hover = self.KINDS[kind]
        self._bg, self._fg, self._hover = C.get(bg, bg), C.get(fg, fg), C.get(hover, hover)
        super().__init__(master, text=text, bg=self._bg, fg=self._fg, font=font,
                         cursor="hand2", padx=14, pady=7, bd=3, relief="raised", **kw)
        self.command = command
        self.enabled = True
        self.bind("<Enter>", lambda e: self.enabled and self.config(bg=self._hover))
        self.bind("<Leave>", lambda e: self.enabled and self.config(bg=self._bg, relief="raised"))
        self.bind("<ButtonPress-1>", lambda e: self.enabled and self.config(relief="sunken"))
        self.bind("<ButtonRelease-1>", self._release)

    def _release(self, event):
        if not self.enabled:
            return
        self.config(relief="raised")
        inside = 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height()
        if inside:
            if self.sound:
                audio.play(self.sound)
            self.command()

    def set_enabled(self, on):
        self.enabled = on
        self.config(bg=self._bg if on else C["panel2"],
                    fg=self._fg if on else C["dim"],
                    relief="raised" if on else "flat",
                    cursor="hand2" if on else "arrow")


def panel(master, title=None, fonts=None, accent="amber", **pack):
    """A bordered panel. Returns the inner frame to put content in.

    The thick outer border is available as inner.outer (the tutorial
    highlights panels by recolouring it).
    """
    outer = tk.Frame(master, bg=C["border"])
    outer.pack(**pack)
    inner = tk.Frame(outer, bg=C["panel"])
    inner.pack(fill="both", expand=True, padx=3, pady=3)
    body = tk.Frame(inner, bg=C["panel"])
    body.pack(fill="both", expand=True, padx=14, pady=8)
    body.outer = outer
    if title:
        row = tk.Frame(body, bg=C["panel"])
        row.pack(fill="x", pady=(0, 6))
        tk.Frame(row, bg=C[accent], width=8, height=8).pack(side="left", padx=(0, 8))
        tk.Label(row, text=title.upper(), bg=C["panel"], fg=C[accent],
                 font=fonts["label"], anchor="w").pack(side="left")
    return body


def topbar(master, fonts, kicker, title, on_menu):
    """The bar across the top of every level screen: MENU button, titles.
    Returns (bar, right_frame); put score / status labels in right_frame."""
    bar = tk.Frame(master, bg=C["bg"])
    bar.pack(fill="x", padx=24, pady=(14, 8))
    RetroButton(bar, "< MENU", on_menu, kind="secondary",
                font=fonts["smallb"]).pack(side="left", padx=(0, 18))
    left = tk.Frame(bar, bg=C["bg"])
    left.pack(side="left")
    tk.Label(left, text=kicker, bg=C["bg"], fg=C["amber"], font=fonts["label"]).pack(anchor="w")
    bar.title_lbl = tk.Label(left, text=title, bg=C["bg"], fg=C["text"], font=fonts["h1"])
    bar.title_lbl.pack(anchor="w")             # screens change this text per view
    right = tk.Frame(bar, bg=C["bg"])
    right.pack(side="right")
    return bar, right


def hexcolor(rgb_tuple):
    """(r, g, b) -> '#rrggbb' for Tk."""
    return "#%02x%02x%02x" % tuple(rgb_tuple)


class ReadOnlyText(tk.Text):
    """A read-only text box that cannot be selected or copied from.
    Wrap a phrase in **double asterisks** to show it as a highlighted key term."""

    def __init__(self, master, fonts, **kw):
        super().__init__(master, wrap="word", bg=C["panel"], fg=C["text"],
                         font=fonts["body"], relief="flat", bd=0, padx=2, pady=2,
                         highlightthickness=0, cursor="arrow", spacing1=2, spacing3=6,
                         takefocus=0, **kw)
        self.tag_configure("key", foreground=C["amber_hi"], font=fonts["bodyb"])
        self.tag_configure("term", foreground=C["cyan"], font=fonts["bodyb"])
        for seq in ("<Button-1>", "<B1-Motion>", "<Double-Button-1>", "<Triple-Button-1>",
                    "<Shift-Button-1>", "<Control-a>", "<Control-c>", "<Command-c>",
                    "<<Copy>>", "<<SelectAll>>"):
            self.bind(seq, lambda e: "break")

    def set_paragraphs(self, paragraphs):
        """Fill with paragraphs; **term** is highlighted."""
        self.config(state="normal")
        self.delete("1.0", "end")
        for n, para in enumerate(paragraphs):
            parts = para.split("**")
            for k, part in enumerate(parts):
                self.insert("end", part, "key" if k % 2 else ())
            if n < len(paragraphs) - 1:
                self.insert("end", "\n")
        self.config(state="disabled")


class Pips(tk.Canvas):
    """A row of small squares, e.g. attempts remaining (filled = left)."""

    def __init__(self, master, total, bg=None, size=12, gap=5):
        bg = bg or C["panel"]
        size, gap = px(size), px(gap)
        w = total * size + (total - 1) * gap
        super().__init__(master, width=w, height=size, bg=bg, highlightthickness=0, bd=0)
        self.total, self.size, self.gap = total, size, gap

    def set(self, remaining, on="cyan", off="dim"):
        self.delete("all")
        for i in range(self.total):
            x = i * (self.size + self.gap)
            if i < remaining:
                self.create_rectangle(x, 0, x + self.size, self.size, fill=C[on], outline="")
            else:
                self.create_rectangle(x + 1, 1, x + self.size - 1, self.size - 1,
                                      fill="", outline=C[off], width=2)


# =============================================================================
# Matplotlib styling
# =============================================================================
def apply_matplotlib_style():
    """Blocky, anti-aliasing-free plots in the retro palette."""
    import matplotlib
    matplotlib.rcParams.update({
        "font.family": "monospace",
        "font.monospace": ["DejaVu Sans Mono", "Consolas", "Menlo", "Courier New"],
        "text.antialiased": False,
        "lines.antialiased": False,
        "patch.antialiased": False,
        "lines.linewidth": 2.0,
        "axes.linewidth": 2.0,
        "xtick.major.width": 2.0,
        "ytick.major.width": 2.0,
    })


def style_axes(ax, title="", xlabel="", ylabel=""):
    """Dark inset plot area, chunky spines, dotted grid, amber title."""
    ax.set_facecolor(C["inset"])
    for spine in ax.spines.values():
        spine.set_color(C["border_hi"])
        spine.set_linewidth(2)
    ax.tick_params(colors=C["muted"], labelsize=8, width=2)
    ax.grid(True, color="#2a2352", linewidth=1, linestyle=(0, (1, 2)))
    ax.set_axisbelow(True)
    ax.set_title(title, color=C["amber"], fontsize=9, loc="left", fontweight="bold")
    ax.set_xlabel(xlabel, color=C["muted"], fontsize=8)
    ax.set_ylabel(ylabel, color=C["muted"], fontsize=8)


# =============================================================================
# Small platform helpers
# =============================================================================
def enable_hidpi():
    """Crisp rendering on high-DPI Windows screens."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
