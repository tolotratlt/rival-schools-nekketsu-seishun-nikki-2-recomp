"""Render short English labels in the style of the pause-menu kana of
/DAT2/OVER.TIZ: 12 px tall, bright fill over a dark 1 px outline, using the
same 4 bpp indices as the stock glyphs (1 = outline, 5..15 = dark to bright
fill; the yellow and cyan CLUTs at VRAM (96,511) and (448,511) both rise in
brightness over 5..15).

render(text, width, font=..., size=...) -> list of rows (lists of indices),
height 12, text centred in `width` pixels. Raises ValueError if it does not fit.
"""
from PIL import Image, ImageFilter, ImageFont, ImageDraw

HEIGHT = 12
FONT = r"C:\Windows\Fonts\verdanab.ttf"
SIZE = 11
TRACK = 1
OUTLINE, FILL_LO, FILL_HI = 1, 5, 15


def render(text, width, font=FONT, size=SIZE, track=TRACK):
    face = ImageFont.truetype(font, size)
    # Lay the text out glyph by glyph so letter spacing can be adjusted.
    xs, x = [], 1
    for ch in text:
        xs.append(x)
        x += face.getlength(ch) + track
    w = int(round(x - track)) + 1
    if w > width:
        raise ValueError("%r is %d px wide, slot is %d" % (text, w, width))
    mask = Image.new("L", (width, HEIGHT), 0)
    d = ImageDraw.Draw(mask)
    left = (width - w) // 2
    top = (HEIGHT - 2 - (face.getbbox("A")[3] - face.getbbox("A")[1])) // 2 - face.getbbox("A")[1] + 1
    for ch, cx in zip(text, xs):
        d.text((left + cx, top), ch, font=face, fill=255)
    solid = mask.point(lambda c: 255 if c >= 96 else 0)
    ring = solid.filter(ImageFilter.MaxFilter(3))
    rows = []
    for y in range(HEIGHT):
        row = []
        for x in range(width):
            c = mask.getpixel((x, y))
            if c >= 96:
                # Brighter towards the top, like the stock glyphs.
                shade = FILL_HI - (2 * y) // HEIGHT
                row.append(max(FILL_LO, min(FILL_HI, shade - (255 - c) // 64)))
            elif ring.getpixel((x, y)):
                row.append(OUTLINE)
            else:
                row.append(0)
        rows.append(row)
    return rows
