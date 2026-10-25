"""Apply localization/en/images.json: redraw text painted into 8 bpp
full-screen images (report cards) inside a disc image.

In every box, pixels far from the paper colours (taken from a blank area,
"paper_box") are ink and
are replaced by the nearest paper pixel on the same row, then the English is drawn centred with the box's
dominant ink colour blended over the paper by glyph coverage, plus an optional
1 px drop shadow in the darkest ink colour. Each colour is mapped to the
nearest entry of the TIM's own palette. The file is recompressed to its stock
size.

Usage: python patch_images.py <stock.bin> <target.bin> [<preview dir>]
"""
import collections
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nsn2lz  # noqa: E402
import psxtim  # noqa: E402
from patch_newopt import iso_files  # noqa: E402
from patch_pause import read_file, write_file  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
FONT = r"C:\Windows\Fonts\timesbd.ttf"
# These files also carry the exam menu atlas; patch_siken.py writes them and
# applies their boxes itself.
OWNED_BY_SIKEN = {"/DAT2/SIKEN1.BIZ", "/DAT2/SIKEN10.BIZ"}
PAPER_SHARE, PAPER_DIST = 0.9, 20   # paper = commonest colours of a blank area (90 %), +/- 20


def lum(c):
    return (c[0] * 3 + c[1] * 6 + c[2]) // 10


def redraw(raw, tim, boxes, paper_box):
    _, _, words, height, pix = tim["image"]
    width = words * 2
    co = tim["clut"][4]
    pal = []
    for k in range(256):
        c = int.from_bytes(raw[co + 2 * k:co + 2 * k + 2], "little")
        pal.append(((c & 31) * 8, (c >> 5 & 31) * 8, (c >> 10 & 31) * 8))
    nearest = {}

    def index(rgb):
        if rgb not in nearest:
            nearest[rgb] = min(range(1, 256), key=lambda k: sum((a - b) ** 2 for a, b in zip(pal[k], rgb)))
        return nearest[rgb]

    def get(x, y):
        return raw[pix + y * width + x]

    def put(x, y, k):
        raw[pix + y * width + x] = k

    # Paper colours: the commonest colours of a blank area of the image.
    px0, py0, pw, ph = paper_box
    blank = collections.Counter(pal[get(x, y)] for y in range(py0, py0 + ph) for x in range(px0, px0 + pw))
    ref, total = [], 0
    for c, n in blank.most_common():
        ref.append(c)
        total += n
        if total >= PAPER_SHARE * pw * ph:
            break

    for b in boxes:
        x0, y0, w, h = b["box"]
        counts = collections.Counter(pal[get(x, y)] for y in range(y0, y0 + h) for x in range(x0, x0 + w))

        def is_paper(c):
            return min(sum((a - b) ** 2 for a, b in zip(c, r)) for r in ref) <= PAPER_DIST ** 2

        inks = collections.Counter({c: n for c, n in counts.items() if lum(c) < 170})
        ink = inks.most_common(1)[0][0]
        dark = min(inks, key=lum)
        common = collections.Counter(get(x, y) for y in range(y0, y0 + h) for x in range(x0, x0 + w)
                                     if is_paper(pal[get(x, y)])).most_common(1)[0][0]
        paper = [[None] * w for _ in range(h)]
        for y in range(h):
            row = [get(x0 + x, y0 + y) for x in range(w)]
            for x in range(w):
                if is_paper(pal[row[x]]):
                    paper[y][x] = row[x]
                    continue
                for d in range(1, w):
                    for xx in (x - d, x + d):
                        if 0 <= xx < w and is_paper(pal[row[xx]]):
                            paper[y][x] = row[xx]
                            break
                    if paper[y][x] is not None:
                        break
                if paper[y][x] is None:   # a row with no paper at all
                    paper[y][x] = common
        face = ImageFont.truetype(FONT, b["size"])
        lines = b["en"].split("\n")
        mask = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(mask)
        line_h = h // len(lines)
        for i, text in enumerate(lines):
            box = d.textbbox((0, 0), text, font=face)
            tw, th = box[2] - box[0], box[3] - box[1]
            if tw > w - 2:
                raise SystemExit("%r is %d px wide, box is %d" % (text, tw, w))
            d.text(((w - tw) // 2 - box[0], i * line_h + (line_h - th) // 2 - box[1]), text, font=face, fill=255)
        shadow = mask.transform(mask.size, Image.AFFINE, (1, 0, -1, 0, 1, -1)) if b.get("shadow") else None
        for y in range(h):
            for x in range(w):
                bg = pal[paper[y][x]]
                c = mask.getpixel((x, y))
                if shadow is not None and c < 128 and shadow.getpixel((x, y)) >= 128:
                    put(x0 + x, y0 + y, index(dark))
                    continue
                if c < 16:
                    put(x0 + x, y0 + y, paper[y][x])
                    continue
                rgb = tuple((ink[k] * c + bg[k] * (255 - c)) // 255 for k in range(3))
                put(x0 + x, y0 + y, index(rgb))


def main(stock, target, preview=None):
    with open(os.path.join(REPO, "localization", "en", "images.json"), encoding="utf-8") as fh:
        spec = json.load(fh)["files"]
    with open(stock, "rb") as f:
        files, sector = iso_files(f)
        data = {n: read_file(f, files, sector, n) for n in spec}
    with open(target, "r+b") as f:
        for name, entry in spec.items():
            if name in OWNED_BY_SIKEN:
                continue
            lba, size, comp = data[name]
            raw = bytearray(nsn2lz.decompress(bytes(comp))[0])
            tim = [t for t in psxtim.scan(raw) if t["offset"] == int(entry["tim_offset"], 16)][0]
            redraw(raw, tim, entry["boxes"], entry["paper_box"])
            if preview:
                _, _, words, height, pix = tim["image"]
                co = tim["clut"][4]
                pal = []
                for k in range(256):
                    c = int.from_bytes(raw[co + 2 * k:co + 2 * k + 2], "little")
                    pal += [(c & 31) * 8, (c >> 5 & 31) * 8, (c >> 10 & 31) * 8]
                im = Image.frombytes("P", (words * 2, height), bytes(raw[pix:pix + words * 2 * height]))
                im.putpalette(pal)
                im.convert("RGB").save(os.path.join(preview, name.split("/")[-1] + ".png"))
            packed = nsn2lz.compress_exact(bytes(raw), size)
            assert nsn2lz.decompress(packed)[0] == bytes(raw)
            write_file(f, lba, packed)
            print("patched %s: %d boxes" % (name, len(entry["boxes"])))


if __name__ == "__main__":
    main(*sys.argv[1:4])
