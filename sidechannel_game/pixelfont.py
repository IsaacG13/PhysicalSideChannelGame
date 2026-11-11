"""
pixelfont.py -- a tiny built-in 5x7 bitmap font plus helpers for drawing
pixel art into a NumPy image buffer.

Why this exists: Tk's normal fonts are anti-aliased, which looks smooth rather
than retro, and which fonts exist differs per OS.  This font is just data, so
the title screen looks identical on Windows, macOS and Linux.

The font is UPPERCASE ONLY (lowercase letters are drawn as capitals).

TINKER: to add a character, add an entry to GLYPHS below. Each glyph is
7 rows of 5 characters; '#' is a lit pixel and '.' is empty.
"""

import numpy as np

GLYPH_W, GLYPH_H = 5, 7

GLYPHS = {
    " ": [".....", ".....", ".....", ".....", ".....", ".....", "....."],
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "F": ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    "G": [".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".###."],
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "I": [".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "J": ["..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    "K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "Q": [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "V": ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "W": ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"],
    "X": ["#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
    "Y": ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    "Z": ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
    "0": [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    "1": ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "2": [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    "3": [".###.", "#...#", "....#", "..##.", "....#", "#...#", ".###."],
    "4": ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    "5": ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    "6": ["..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."],
    "7": ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
    "8": [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    "9": [".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."],
    "!": ["..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."],
    "?": [".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."],
    ".": [".....", ".....", ".....", ".....", ".....", ".##..", ".##.."],
    ",": [".....", ".....", ".....", ".....", ".##..", "..#..", ".#..."],
    ":": [".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."],
    ";": [".....", ".##..", ".##..", ".....", ".##..", "..#..", ".#..."],
    "-": [".....", ".....", ".....", "#####", ".....", ".....", "....."],
    "+": [".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."],
    "=": [".....", ".....", "#####", ".....", "#####", ".....", "....."],
    "/": ["....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."],
    "(": ["...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."],
    ")": [".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."],
    "<": ["...#.", "..#..", ".#...", "#....", ".#...", "..#..", "...#."],
    ">": [".#...", "..#..", "...#.", "....#", "...#.", "..#..", ".#..."],
    "_": [".....", ".....", ".....", ".....", ".....", ".....", "#####"],
    "*": [".....", "#.#.#", ".###.", "#####", ".###.", "#.#.#", "....."],
    "%": ["##..#", "##..#", "...#.", "..#..", ".#...", "#..##", "#..##"],
    "'": ["..#..", "..#..", ".#...", ".....", ".....", ".....", "....."],
    '"': [".#.#.", ".#.#.", ".....", ".....", ".....", ".....", "....."],
    "#": [".#.#.", "#####", ".#.#.", ".#.#.", ".#.#.", "#####", ".#.#."],
}

_mask_cache = {}


def _glyph_mask(ch):
    """Return the 7x5 boolean mask for a character (cached)."""
    ch = ch.upper()
    if ch not in GLYPHS:
        ch = "?"
    if ch not in _mask_cache:
        _mask_cache[ch] = np.array([[c == "#" for c in row] for row in GLYPHS[ch]])
    return _mask_cache[ch]


def text_size(text, scale=1, spacing=1):
    """Width and height (in image pixels) the text will occupy."""
    if not text:
        return 0, GLYPH_H * scale
    w = (len(text) * (GLYPH_W + spacing) - spacing) * scale
    return w, GLYPH_H * scale


def text_mask(text, scale=1, spacing=1):
    """Boolean mask (rows x cols) of the whole string at the given scale."""
    w, h = text_size(text, scale, spacing)
    mask = np.zeros((GLYPH_H, max(1, w // scale)), dtype=bool)
    x = 0
    for ch in text:
        mask[:, x:x + GLYPH_W] = _glyph_mask(ch)
        x += GLYPH_W + spacing
    if scale > 1:
        mask = np.kron(mask, np.ones((scale, scale), dtype=bool))
    return mask


def _blit(buf, mask, x, y, color):
    """Paint `color` into buf wherever mask is True, clipped to the buffer."""
    h, w = mask.shape
    bh, bw = buf.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(bw, x + w), min(bh, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    sub = mask[y0 - y:y1 - y, x0 - x:x1 - x]
    region = buf[y0:y1, x0:x1]
    region[sub] = color


def _dilate(mask):
    """Grow a mask by one pixel in all 8 directions (used for outlines)."""
    out = mask.copy()
    p = np.pad(mask, 1)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            out |= p[1 + dy:1 + dy + mask.shape[0], 1 + dx:1 + dx + mask.shape[1]]
    return out


def draw_text(buf, x, y, text, color, scale=1, spacing=1, shadow=None,
              outline=None, shadow_offset=1):
    """Draw pixel text into buf (an HxWx3 uint8 array).

    shadow  : colour of a drop shadow, offset down-right by `shadow_offset`
    outline : colour of a 1-pixel outline around every letter
    """
    mask = text_mask(text, scale, spacing)
    if outline is not None:
        grown = _dilate(mask)
        _blit(buf, grown, x - 1, y - 1, outline)
        if shadow is not None:
            _blit(buf, grown, x - 1 + shadow_offset, y - 1 + shadow_offset, shadow)
            _blit(buf, grown, x - 1, y - 1, outline)
    elif shadow is not None:
        _blit(buf, mask, x + shadow_offset, y + shadow_offset, shadow)
    _blit(buf, mask, x, y, color)


def draw_bitmap(buf, x, y, rows, palette):
    """Draw a small sprite given as a list of strings.

    palette maps a character to an RGB tuple; '.' (and any character that is
    not in the palette) is transparent.
    """
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            color = palette.get(ch)
            if color is None:
                continue
            xx, yy = x + i, y + j
            if 0 <= yy < buf.shape[0] and 0 <= xx < buf.shape[1]:
                buf[yy, xx] = color
