"""
screen_menu.py -- the main menu.

A dark room, a lamp, a table with the smart-lock board on it, the game title
in big pixel letters, and the five levels listed underneath.

How it works: the whole screen is one small pixel image (see scene_art.py)
that is redrawn whenever something changes (hover, selection, blinking LED)
and shown enlarged by a whole-number zoom. Menu text is drawn into that image
with the built-in pixel font, so it looks the same on every operating system.

Controls: mouse (hover + click) or keyboard (Up / Down / Enter).

TINKER: layout numbers are at the top of the file. Level names and the
unlock order live in progress.py (LEVELS).
"""

import time
import tkinter as tk

import numpy as np

import audio
import pixelfont
import scene_art
from progress import LEVELS
from retro import C, array_to_photo, rgb

MIN_W, MIN_H = scene_art.SCENE_W, scene_art.SCENE_H   # smallest design size (art pixels)

# --- layout (logical pixels) -------------------------------------------------
TITLE_X = 14
TITLE_Y1, TITLE_Y2 = 10, 36
LIST_X = 24                  # where level names start
LIST_Y = 66                  # y of the first level name
LIST_PITCH = 19              # vertical distance between levels
MESSAGE_Y = 161
MESSAGE_MAX_W = 196          # long messages wrap so they stay clear of the board art
BOTTOM_FROM_EDGE = 11        # the SEED / NEW GAME row sits this far above the bottom

# --- colours -------------------------------------------------------------------
INK = (10, 6, 20)
AMBER, AMBER_HI, AMBER_DK = rgb("amber"), rgb("amber_hi"), (150, 62, 0)
CYAN, CYAN_DK = rgb("cyan"), (18, 78, 120)
CREAM, MUTED, DIM = rgb("text"), rgb("muted"), rgb("dim")
GOOD, BAD = rgb("good"), rgb("bad")

LOCK_ICON = [        # 5x7 padlock shown next to locked levels
    ".###.",
    "#...#",
    "#...#",
    "#####",
    "##.##",
    "##.##",
    "#####",
]
CHECK_ICON = [       # 7x7 tick shown next to completed levels
    ".......",
    "......#",
    ".....##",
    "#...##.",
    "##.##..",
    ".###...",
    "..#....",
]
SPEAKER_ICON = [     # 11x9
    "...#.......",
    "..##..#....",
    "####...#.#.",
    "####.#..#.#",
    "####.#..#.#",
    "####...#.#.",
    "..##..#....",
    "...#.......",
]
MUSIC_ICON = [       # 9x8
    "..#######",
    "..#.....#",
    "..#.....#",
    "..#.....#",
    "..#.....#",
    ".##....##",
    "###...###",
    ".#.....#.",
]


class MenuScreen(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=C["bg"])
        self.app = app
        self.save = app.save

        self.canvas = tk.Canvas(self, bg=C["bg"], highlightthickness=0, bd=0,
                                takefocus=True)
        self.canvas.pack(fill="both", expand=True)
        self.image_id = self.canvas.create_image(0, 0, anchor="nw")

        self.zoom = 3                       # screen pixels per art pixel
        self.sw, self.sh = MIN_W, MIN_H     # current art size (grows with the window)
        self.photo = None
        self.led_on = True
        self.hit = []                       # [(kind, key, x0, y0, x1, y1)]
        self.message, self.message_until = "", 0.0
        self.confirm_until = 0.0            # "click NEW GAME again" window
        self.hover_icon = None
        self._after_ids = []                # one-shot timers (cancelled on destroy)
        self._blink_id = None               # the repeating LED blink timer

        # start with the first level that is unlocked but not yet completed
        self.sel = 0
        for i, (lid, _) in enumerate(LEVELS):
            if self.save.is_unlocked(lid) and not self.save.is_complete(lid):
                self.sel = i
                break
        else:
            self.sel = len(LEVELS) - 1

        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", lambda e: self._set_hover(None, None))
        self.canvas.bind("<Button-1>", self._on_click)
        for key in ("<Up>", "<Down>", "<Return>", "<space>", "<KP_Enter>"):
            self.canvas.bind(key, self._on_key)
        self.after(50, self.canvas.focus_set)
        self._blink()

    # ---------------------------------------------------------------- drawing
    def _compose(self):
        """Draw the backdrop plus all menu text into one pixel image."""
        buf = scene_art.build_backdrop(self.sw, self.sh, self.led_on)
        self.hit = []
        bottom_y = self.sh - BOTTOM_FROM_EDGE

        # title
        pixelfont.draw_text(buf, TITLE_X, TITLE_Y1, "SIDE-CHANNEL", AMBER, scale=3,
                            outline=INK, shadow=AMBER_DK, shadow_offset=2)
        pixelfont.draw_text(buf, TITLE_X, TITLE_Y2, "ATTACK!", CYAN, scale=3,
                            outline=INK, shadow=CYAN_DK, shadow_offset=2)

        # the five levels
        for i, (lid, name) in enumerate(LEVELS):
            self._draw_level(buf, i, lid, name)

        # transient message line
        now = time.time()
        if self.message and now < self.message_until:
            lines = self._wrap(self.message)
            y = min(MESSAGE_Y, bottom_y - 3 - 9 * len(lines))   # never over the seed row
            for line in lines:
                pixelfont.draw_text(buf, LIST_X - 12, y, line, AMBER_HI, outline=INK)
                y += 9
        # bottom bar: seed + new game
        seed_text = "SEED " + str(self.save.seed or "-")
        pixelfont.draw_text(buf, 12, bottom_y, seed_text, MUTED, outline=INK)
        sx = 12 + pixelfont.text_size(seed_text)[0] + 14
        confirming = now < self.confirm_until
        label = "ERASE PROGRESS? CLICK AGAIN" if confirming else "NEW GAME"
        hot = self.hover_icon == "new"
        color = BAD if confirming else (AMBER_HI if hot else AMBER)
        w, h = pixelfont.text_size(label)
        pixelfont.draw_text(buf, sx, bottom_y, label, color, outline=INK)
        self.hit.append(("new", None, sx - 2, bottom_y - 3, sx + w + 2, bottom_y + h + 3))

        self._draw_icons(buf)
        return buf

    def _draw_level(self, buf, i, lid, name):
        y = LIST_Y + i * LIST_PITCH
        unlocked = self.save.is_unlocked(lid)
        done = self.save.is_complete(lid)
        selected = i == self.sel
        name_w = pixelfont.text_size(name)[0]

        if selected:                                   # highlight bar + pointer
            y0, y1 = y - 3, y + 16
            region = buf[y0:y1 + 1, 8:LIST_X + name_w + 34]
            region[:] = (region * 0.35 + np.array((38, 30, 78)) * 0.65).astype(np.uint8)
            buf[y0:y1 + 1, 8:10] = AMBER
            pixelfont.draw_text(buf, 13, y + 1, ">", AMBER_HI)   # pointer arrow

        if not unlocked:
            # locked levels are dim, but stay readable when highlighted
            name_color, score_color = ((150, 142, 190), (112, 104, 150)) if selected \
                else ((104, 96, 142), (78, 72, 108))
        elif selected:
            name_color, score_color = AMBER_HI, AMBER
        else:
            name_color, score_color = CREAM, MUTED
        pixelfont.draw_text(buf, LIST_X, y, name, name_color,
                            outline=INK if unlocked else None)
        pixelfont.draw_text(buf, LIST_X, y + 9, "SCORE " + self.save.score_text(lid),
                            score_color)

        icon_x = LIST_X + name_w + 6
        if not unlocked:
            pixelfont.draw_bitmap(buf, icon_x, y, LOCK_ICON, {"#": DIM})
        elif done:
            pixelfont.draw_bitmap(buf, icon_x, y, CHECK_ICON, {"#": GOOD})

        self.hit.append(("level", i, 8, y - 3, LIST_X + name_w + 34, y + 16))

    def _draw_icons(self, buf):
        """Sound-effects and music toggles in the top-right corner."""
        W = self.sw
        specs = [("sfx", SPEAKER_ICON, 11, 8, W - 36, "SOUND"),
                 ("music", MUSIC_ICON, 9, 8, W - 18, "MUSIC")]
        for key, sprite, sw, sh, x, label in specs:
            on = self.save.setting(key)
            hot = self.hover_icon == key
            # backing box
            bx0, by0, bx1, by1 = x - 3, 3, x + sw + 2, 3 + sh + 5
            buf[by0:by1 + 1, bx0:bx1 + 1] = (22, 17, 44)
            edge = AMBER if hot else (91, 75, 154)
            buf[by0, bx0:bx1 + 1] = edge
            buf[by1, bx0:bx1 + 1] = edge
            buf[by0:by1 + 1, bx0] = edge
            buf[by0:by1 + 1, bx1] = edge
            color = (AMBER_HI if hot else CREAM) if on else DIM
            pixelfont.draw_bitmap(buf, x, 6, sprite, {"#": color})
            if not on:                                  # red cross = muted
                for k in range(sw):
                    yy = 6 + int(k * (sh - 1) / max(1, sw - 1))
                    buf[yy, x + k] = BAD
                    buf[6 + (sh - 1) - (yy - 6), x + k] = BAD
            self.hit.append(("icon", key, bx0, by0, bx1, by1))
            if hot:
                text = "%s %s" % (label, "ON" if on else "OFF")
                tw = pixelfont.text_size(text)[0]
                pixelfont.draw_text(buf, min(W - tw - 4, bx0), by1 + 4, text,
                                    AMBER_HI, outline=INK)

    def render(self):
        buf = self._compose()
        self.photo = array_to_photo(buf, self.zoom)
        self.canvas.itemconfig(self.image_id, image=self.photo)

    # ----------------------------------------------------------------- events
    def _on_resize(self, event):
        # whole-number zoom so pixels stay square; the art itself is generated
        # large enough to fill the window
        self.zoom = max(1, min(event.width // MIN_W, event.height // MIN_H))
        self.sw = max(MIN_W, -(-event.width // self.zoom))      # round up: no gaps
        self.sh = max(MIN_H, -(-event.height // self.zoom))
        self.render()

    def _logical(self, event):
        return event.x // self.zoom, event.y // self.zoom

    def _find(self, event):
        lx, ly = self._logical(event)
        for kind, key, x0, y0, x1, y1 in self.hit:
            if x0 <= lx <= x1 and y0 <= ly <= y1:
                return kind, key
        return None, None

    def _set_hover(self, kind, key):
        icon = key if kind == "icon" else ("new" if kind == "new" else None)
        changed = icon != self.hover_icon
        self.hover_icon = icon
        if kind == "level" and key != self.sel:
            self.sel = key
            changed = True
        self.canvas.config(cursor="hand2" if kind else "arrow")
        if changed:
            self.render()

    def _on_motion(self, event):
        self._set_hover(*self._find(event))

    def _on_click(self, event):
        self.canvas.focus_set()
        kind, key = self._find(event)
        if kind == "level":
            self.sel = key
            self._activate(key)
        elif kind == "icon":
            on = self.save.toggle_setting(key)
            if key == "music":
                audio.set_music(on)
            audio.play("click")             # silent when SOUND was just turned off
            self.render()
        elif kind == "new":
            audio.play("click")
            if time.time() < self.confirm_until:
                self.app.start_new_game()
            else:
                self.confirm_until = time.time() + 3.5
                self.render()

    def _on_key(self, event):
        if event.keysym == "Up":
            self.sel = (self.sel - 1) % len(LEVELS)
        elif event.keysym == "Down":
            self.sel = (self.sel + 1) % len(LEVELS)
        else:
            self._activate(self.sel)
            return
        self.render()

    def _activate(self, index):
        lid, name = LEVELS[index]
        if not self.save.is_unlocked(lid):
            audio.play("wrong")
            self.say("LOCKED: PASS THE LEVEL ABOVE")
            return
        audio.play("click")
        self.app.open_level(lid)

    @staticmethod
    def _wrap(text):
        """Split a message into lines no wider than MESSAGE_MAX_W."""
        lines, cur = [], ""
        for word in text.split():
            trial = (cur + " " + word).strip()
            if cur and pixelfont.text_size(trial)[0] > MESSAGE_MAX_W:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        return lines + [cur] if cur else lines

    def say(self, text, seconds=2.5):
        """Show a short message under the level list."""
        self.message, self.message_until = text, time.time() + seconds
        self.render()
        self._after(int(seconds * 1000) + 50, self.render)

    # ----------------------------------------------------------------- timers
    def _after(self, ms, fn):
        aid = self.after(ms, fn)
        self._after_ids.append(aid)

    def _blink(self):
        self.led_on = not self.led_on
        self.render()
        self._blink_id = self.after(550, self._blink)

    def destroy(self):
        if self._blink_id is not None:
            try:
                self.after_cancel(self._blink_id)
            except tk.TclError:
                pass
        for aid in self._after_ids:
            try:
                self.after_cancel(aid)
            except tk.TclError:
                pass
        super().destroy()
