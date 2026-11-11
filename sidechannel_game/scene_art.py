"""
scene_art.py -- the pixel art for the main menu / seed screen backdrop:
a dark room, an overhead lamp, a wooden table and a smart-lock microcontroller.

Everything is drawn into a small NumPy image which the game then enlarges by a
whole-number factor with hard edges. That is what gives it the chunky pixel
look. There is no filter or post-processing.

The room is generated for whatever size the window needs (build_backdrop takes
a width and height in art pixels). The lamp, table and board stay anchored to
the right / bottom, so a bigger window just reveals more dark room.

The light is faked with "ordered dithering": the brightness is rounded to a
few levels using a repeating 4x4 threshold pattern, which produces the
cross-hatched shading typical of old PC / console art.

TINKER: edit layout() to move things, the colour constants to re-colour them,
or the sprite strings (PADLOCK) to redraw the artwork.
"""

import numpy as np

from pixelfont import draw_bitmap, draw_text

# The smallest art size the screens are designed for. The window picks the
# biggest whole-number zoom for which this still fits.
SCENE_W, SCENE_H = 300, 190

# --- colours (R, G, B) ---------------------------------------------------------
WALL = (84, 76, 128)
WALL_SEAM = (100, 90, 150)
WOOD = [(118, 74, 40), (134, 86, 47), (104, 64, 34), (126, 80, 44)]
WOOD_GRAIN = (92, 56, 29)
WOOD_EDGE = (176, 122, 70)

LED_RED_ON = (255, 70, 70)
LED_RED_OFF = (110, 24, 24)

LAMP_BULB_Y = 10
POOL_WIDEN = 1.3     # how much wider the pool gets than the cone at the table edge
POOL_DROP = 26       # how far below the table's far edge the pool is widest (pixels)


def layout(w, h):
    """Where things go for an art size of w x h pixels."""
    lamp_x = w - 56
    return {
        "lamp_x": lamp_x,
        "table_y": h - 78,                 # far edge of the table
        "pool_cx": lamp_x, "pool_cy": h - 40,
        "mcu_x": w - 84, "mcu_y": h - 66,  # top-left of the circuit board
        "padlock_x": w - 105, "padlock_y": h - 62,
    }


def _bayer4():
    m = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]])
    return (m + 0.5) / 16.0


def _fill(buf, x0, y0, x1, y1, color):
    """Fill the rectangle x0..x1, y0..y1 (inclusive) with a colour."""
    buf[max(0, y0):max(0, y1 + 1), max(0, x0):max(0, x1 + 1)] = color


def _shadow(buf, cx, cy, rx, ry, strength=0.55):
    """Darken an ellipse of the image (a drop shadow on the table)."""
    h, w = buf.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w]
    inside = ((xs - cx) / rx) ** 2 + ((ys - cy) / ry) ** 2 <= 1.0
    buf[inside] = (buf[inside] * strength).astype(np.uint8)


# =============================================================================
# Room: wall, table, lighting
# =============================================================================
def _unlit_room(w, h, lay):
    """Wall and table in their 'full daylight' colours (lighting comes later)."""
    rng = np.random.default_rng(7)
    img = np.zeros((h, w, 3), dtype=float)
    table_y = lay["table_y"]

    # wall with faint vertical panel seams
    img[:table_y] = WALL
    for x in range(8, w, 46):
        img[:table_y, x] = WALL_SEAM

    # table: planks that get taller toward the viewer (cheap perspective)
    y, k = table_y, 0
    while y < h:
        plank = int(6 + k * 1.7)
        base = np.array(WOOD[int(rng.integers(len(WOOD)))], dtype=float)
        img[y:y + plank] = base
        for row in range(y, min(y + plank, h)):             # wood grain streaks
            for _ in range(3):
                gx = int(rng.integers(-10, w))
                gl = int(rng.integers(18, 70))
                if rng.random() < 0.55:
                    img[row, max(0, gx):gx + gl] = WOOD_GRAIN
        img[y:y + 1] = np.array(WOOD_GRAIN) * 0.8           # seam between planks
        y += plank
        k += 1
    img[table_y:table_y + 2] = WOOD_EDGE                    # lit lip of the table
    img[table_y + 2:table_y + 3] = np.array(WOOD_EDGE) * 0.6
    return img


def _light_map(w, h, lay):
    """Brightness 0..1 for every pixel: a cone from the lamp plus a pool on the table."""
    ys, xs = np.mgrid[0:h, 0:w].astype(float)
    lamp_x, table_y = lay["lamp_x"], lay["table_y"]

    # the cone widens as it goes down and gets a little weaker
    below = np.clip(ys - LAMP_BULB_Y, 0, None)
    half_width = 5.0 + below * 0.46
    cone = np.clip(1.0 - (np.abs(xs - lamp_x) / half_width) ** 2, 0, 1)
    cone *= np.clip(1.0 - below / 330.0, 0, 1)
    cone[ys < LAMP_BULB_Y] = 0

    # The pool where the light lands on the table. It is the cone's footprint seen
    # from above, so it must start exactly as wide as the cone is at the table edge
    # (otherwise the cone looks chopped off). We pick the ellipse's height so that
    # its width at the table edge equals the cone's width there.
    cone_hw = 5.0 + (table_y - LAMP_BULB_Y) * 0.46        # cone half-width at the table edge
    rx = cone_hw * POOL_WIDEN                             # widest point of the pool
    d = POOL_DROP                                         # centre sits this far below the edge
    ry = d / np.sqrt(max(1e-6, 1.0 - (cone_hw / rx) ** 2))
    cy = table_y + d
    r2 = ((xs - lay["pool_cx"]) / rx) ** 2 + ((ys - cy) / ry) ** 2
    pool = np.clip(1.0 - r2, 0, 1) ** 0.6
    pool[ys < table_y] = 0

    return np.clip(np.maximum(cone * (ys < table_y), pool), 0, 1)


def _apply_light(img, light, levels=5):
    """Quantise the light with ordered dithering, then tint and darken the room."""
    h, w = light.shape
    bayer = np.tile(_bayer4(), (h // 4 + 1, w // 4 + 1))[:h, :w]
    steps = levels - 1
    quant = np.clip(np.floor(light * steps + bayer) / steps, 0, 1)   # dithered, banded
    ambient = 0.16
    factor = ambient + (1.0 - ambient) * quant
    tint = np.stack([np.ones_like(quant),
                     1.0 - 0.10 * quant,
                     1.0 - 0.38 * quant], axis=-1)                    # warm light
    return np.clip(img * factor[..., None] * tint, 0, 255)


# =============================================================================
# Lamp, microcontroller, padlock
# =============================================================================
def _draw_lamp(buf, lay):
    x = lay["lamp_x"]
    for row in range(0, 9):                                  # conical shade
        half = 5 + row
        _fill(buf, x - half, row, x + half, row, (58, 56, 84) if row < 8 else (190, 192, 214))
        buf[row, x - half] = (36, 34, 56)
        buf[row, x + half] = (36, 34, 56)
    _fill(buf, x - 3, 2, x - 1, 6, (86, 84, 122))            # highlight on the shade
    _fill(buf, x - 4, 9, x + 4, 10, (255, 244, 190))         # bulb
    _fill(buf, x - 2, 11, x + 2, 11, (255, 224, 140))
    # soft dithered glow around the bulb
    yy, xx = np.mgrid[0:24, 0:44]
    d = np.sqrt((xx - 22) ** 2 + ((yy - 7) * 1.3) ** 2)
    bay = np.tile(_bayer4(), (7, 12))[:24, :44]
    glow = np.clip(1 - d / 20, 0, 1) * 0.9 > bay
    region = buf[8:32, x - 22:x + 22]
    sel = glow & (np.sum(region, axis=-1) < 330)
    region[sel] = (255, 222, 130)


PADLOCK = [
    "....SSSSS....",
    "...SS...SS...",
    "...S.....S...",
    "...S.....S...",
    "...S.....S...",
    ".ooooooooooo.",
    ".oggGGGGGGGo.",
    ".ogGGGGGGGGo.",
    ".oGGGkkkGGGo.",
    ".oGGGkkkGGGo.",
    ".oGGGGkGGGGo.",
    ".oGGGGkGGGGo.",
    ".oGGGGGGGGDo.",
    ".oooooooooo..",
]
PADLOCK_PALETTE = {
    "S": (205, 210, 224), "o": (110, 72, 12), "g": (255, 236, 150),
    "G": (240, 184, 52), "D": (196, 138, 30), "k": (40, 24, 8),
}


def draw_mcu(buf, lay, led_on=True):
    """The smart-lock microcontroller board (and its padlock), lit by the lamp."""
    x, y = lay["mcu_x"], lay["mcu_y"]
    w = buf.shape[1]
    _shadow(buf, x + 29, y + 33, 36, 6, 0.45)

    # board: thickness (front edge), then top face
    _fill(buf, x, y + 30, x + 55, y + 33, (14, 58, 42))
    _fill(buf, x, y + 33, x + 55, y + 33, (8, 34, 26))
    _fill(buf, x, y, x + 55, y + 29, (24, 112, 76))
    _fill(buf, x, y, x + 55, y, (66, 176, 120))              # lit top edge
    _fill(buf, x, y, x, y + 29, (56, 150, 104))
    _fill(buf, x + 55, y, x + 55, y + 29, (16, 78, 54))
    _fill(buf, x, y + 29, x + 55, y + 29, (16, 78, 54))

    for hx, hy in ((3, 3), (52, 3), (3, 26), (52, 26)):      # mounting holes
        _fill(buf, x + hx, y + hy, x + hx + 1, y + hy + 1, (10, 22, 18))

    # copper traces
    trace, pad = (52, 160, 108), (240, 190, 60)
    for ty in range(9, 22, 3):
        _fill(buf, x + 9, y + ty, x + 15, y + ty, trace)             # left side
        _fill(buf, x + 41, y + ty, x + 47, y + ty, trace)            # right side
        _fill(buf, x + 8, y + ty, x + 8, y + ty, pad)
    _fill(buf, x + 24, y + 3, x + 36, y + 3, trace)                  # top
    _fill(buf, x + 36, y + 3, x + 36, y + 5, trace)
    _fill(buf, x + 24, y + 25, x + 31, y + 25, trace)                # bottom

    # the chip
    _fill(buf, x + 17, y + 6, x + 38, y + 23, (26, 26, 36))
    _fill(buf, x + 17, y + 6, x + 38, y + 6, (70, 70, 92))
    _fill(buf, x + 17, y + 6, x + 17, y + 23, (60, 60, 82))
    _fill(buf, x + 38, y + 6, x + 38, y + 23, (14, 14, 22))
    _fill(buf, x + 17, y + 23, x + 38, y + 23, (14, 14, 22))
    for ty in range(8, 22, 3):                                       # side pins
        _fill(buf, x + 14, y + ty, x + 16, y + ty, (196, 200, 212))
        _fill(buf, x + 39, y + ty, x + 41, y + ty, (196, 200, 212))
    for tx in range(20, 37, 4):                                      # top/bottom pins
        _fill(buf, x + tx, y + 4, x + tx, y + 5, (196, 200, 212))
        _fill(buf, x + tx, y + 24, x + tx, y + 25, (196, 200, 212))
    _fill(buf, x + 19, y + 8, x + 20, y + 9, (120, 120, 150))        # pin-1 dot
    draw_text(buf, x + 20, y + 12, "MCU", (255, 190, 40))            # chip label

    # crystal oscillator (silver can)
    _fill(buf, x + 3, y + 13, x + 10, y + 17, (206, 210, 222))
    _fill(buf, x + 3, y + 13, x + 10, y + 13, (244, 246, 252))
    _fill(buf, x + 3, y + 17, x + 10, y + 17, (132, 136, 152))
    # capacitors and resistors
    for cy, col in ((7, (196, 150, 86)), (11, (196, 150, 86)),
                    (15, (40, 40, 52)), (19, (40, 40, 52))):
        _fill(buf, x + 45, y + cy, x + 48, y + cy + 1, col)
    # header pins along the bottom edge
    for i in range(7):
        _fill(buf, x + 10 + i * 4, y + 27, x + 11 + i * 4, y + 28, pad)
    # status LEDs (the red one blinks)
    r = LED_RED_ON if led_on else LED_RED_OFF
    if led_on:                                                       # tiny glow
        for dx, dy in ((48, 24), (51, 24), (49, 23), (50, 23), (49, 26), (50, 26)):
            buf[y + dy, x + dx] = (150, 60, 50)
    _fill(buf, x + 49, y + 24, x + 50, y + 25, r)
    _fill(buf, x + 52, y + 24, x + 53, y + 25, (70, 255, 130))

    # probe wire running off to the right edge (an oscilloscope lead)
    wire = (150, 150, 168)
    _fill(buf, x + 56, y + 27, x + 60, y + 27, wire)
    _fill(buf, x + 60, y + 27, x + 60, y + 31, wire)
    _fill(buf, x + 60, y + 31, w - 1, y + 31, wire)
    _fill(buf, x + 56, y + 28, x + 58, y + 28, (60, 60, 70))
    _fill(buf, x + 61, y + 32, w - 1, y + 32, (60, 60, 70))

    # the padlock that this controller operates
    px, py = lay["padlock_x"], lay["padlock_y"]
    _shadow(buf, px + 6, py + 14, 10, 3, 0.5)
    draw_bitmap(buf, px, py, PADLOCK, PADLOCK_PALETTE)


# =============================================================================
# Public: build the finished backdrop
# =============================================================================
_cache = {}


def build_backdrop(w=SCENE_W, h=SCENE_H, led_on=True):
    """Return the finished scene as an h x w x 3 uint8 array.
    The (expensive) room is cached per size; only the board is redrawn."""
    w, h = max(w, SCENE_W), max(h, SCENE_H)
    lay = layout(w, h)
    if (w, h) not in _cache:
        if len(_cache) > 6:
            _cache.clear()
        room = _apply_light(_unlit_room(w, h, lay), _light_map(w, h, lay)).astype(np.uint8)
        _draw_lamp(room, lay)
        _cache[(w, h)] = room
    buf = _cache[(w, h)].copy()
    draw_mcu(buf, lay, led_on)
    return buf


if __name__ == "__main__":      # quick preview:  python scene_art.py  -> scene_preview.png
    from PIL import Image
    arr = build_backdrop()
    Image.fromarray(arr).resize((arr.shape[1] * 4, arr.shape[0] * 4), Image.NEAREST).save("scene_preview.png")
    print("wrote scene_preview.png")