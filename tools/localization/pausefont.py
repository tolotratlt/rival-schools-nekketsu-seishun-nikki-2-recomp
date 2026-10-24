"""Render short English labels in the style of the pause-menu kana of
/DAT2/OVER.TIZ: 12 px tall, bright fill over a dark 1 px outline, using the
same 4 bpp indices as the stock glyphs (1 = outline, 5..15 = dark to bright
fill; the yellow and cyan CLUTs at VRAM (96,511) and (448,511) both rise in
brightness over 5..15).

render(text, width, font=..., size=...) -> list of rows (lists of indices),
height 12 (or `height`), text placed in `width` pixels (align "centre", "left" or "right").
Raises ValueError if it does not fit.
pack(labels, cols, rows, align=None) renders labels at the smallest width in 24 px units
and places them in a grid of 24x12 cells, splitting a label into pieces when
no row has room for it whole.
"""
from PIL import Image, ImageFilter, ImageFont, ImageDraw

HEIGHT = 12
FONT = r"C:\Windows\Fonts\verdanab.ttf"
SIZE = 11
TRACK = 1
OUTLINE, FILL_LO, FILL_HI = 1, 5, 15


def render(text, width, font=FONT, size=SIZE, track=TRACK, align="centre", height=HEIGHT):
    face = ImageFont.truetype(font, size)
    # Lay the text out glyph by glyph so letter spacing can be adjusted.
    xs, x = [], 1
    for ch in text:
        xs.append(x)
        x += face.getlength(ch) + track
    w = int(round(x - track)) + 1
    if w > width:
        raise ValueError("%r is %d px wide, slot is %d" % (text, w, width))
    mask = Image.new("L", (width, height), 0)
    d = ImageDraw.Draw(mask)
    left = {"centre": (width - w) // 2, "left": 0, "right": width - w}[align]
    top = (height - 2 - (face.getbbox("A")[3] - face.getbbox("A")[1])) // 2 - face.getbbox("A")[1] + 1
    for ch, cx in zip(text, xs):
        d.text((left + cx, top), ch, font=face, fill=255)
    solid = mask.point(lambda c: 255 if c >= 96 else 0)
    ring = solid.filter(ImageFilter.MaxFilter(3))
    rows = []
    for y in range(height):
        row = []
        for x in range(width):
            c = mask.getpixel((x, y))
            if c >= 96:
                # Brighter towards the top, like the stock glyphs.
                shade = FILL_HI - (2 * y) // height
                row.append(max(FILL_LO, min(FILL_HI, shade - (255 - c) // 64)))
            elif ring.getpixel((x, y)):
                row.append(OUTLINE)
            else:
                row.append(0)
        rows.append(row)
    return rows


UNIT = 24


def pack(labels, cols, rows, align=None):
    """Returns, per label, ([(col, row, units, pixel rows), ...], width units).
    `align` optionally gives a render alignment per label."""
    free = [[True] * cols for _ in range(rows)]

    def take(units):
        for r in range(rows):
            for c in range(cols - units + 1):
                if all(free[r][c:c + units]):
                    free[r][c:c + units] = [False] * units
                    return c, r
        return None

    out = []
    for i, text in enumerate(labels):
        units = 1
        while True:
            try:
                img = render(text, units * UNIT, align=align[i] if align else "centre")
                break
            except ValueError:
                units += 1
        pieces, x = [], 0
        while x < units:
            n = min(cols, units - x)
            spot = take(n)
            while spot is None and n > 1:
                n -= 1
                spot = take(n)
            if spot is None:
                raise SystemExit("font area is full at %r" % text)
            c, r = spot
            pieces.append((c, r, n, [row[x * UNIT:(x + n) * UNIT] for row in img]))
            x += n
        out.append((pieces, units))
    return out


def render_aa(text, width, height, font, size, lo=3, hi=14, align="left"):
    """Plain anti-aliased text without outline: index 0 is transparent and
    lo..hi rise in brightness with glyph coverage (the exam menu atlas style).
    Returns rows of indices; raises ValueError if the text is too wide."""
    face = ImageFont.truetype(font, size)
    w = int(face.getlength(text)) + 2
    if w > width:
        raise ValueError("%r is %d px wide, slot is %d" % (text, w, width))
    mask = Image.new("L", (width, height), 0)
    box = face.getbbox("Ag")
    top = (height - (box[3] - box[1])) // 2 - box[1]
    left = {"centre": (width - w) // 2, "left": 1, "right": width - w}[align]
    ImageDraw.Draw(mask).text((left, top), text, font=face, fill=255)
    rows = []
    for y in range(height):
        row = []
        for x in range(width):
            c = mask.getpixel((x, y))
            row.append(0 if c < 24 else lo + (c * (hi - lo) + 127) // 255)
        rows.append(row)
    return rows


def text_width(text, font, size):
    return int(ImageFont.truetype(font, size).getlength(text)) + 2
