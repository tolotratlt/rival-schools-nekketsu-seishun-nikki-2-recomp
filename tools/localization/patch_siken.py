"""Apply localization/en/siken.json to the Exam Drills '99 and Basics Review
menus inside a disc image.

/DAT1/SIKEN2.BIN (exam menus) and /DAT1/SIKEN.BIN (Basics Review), both loaded
at 0x800A2000, draw each string as [n] + n records (texture page, u, v, w, h)
over a 3-page atlas TIM (VRAM 768,0; pages 0x0C/0x0D/0x0E) stored in
/DAT2/SIKEN1.BIZ and /DAT2/SIKEN10.BIZ (identical copies).

Every English string is rendered once as a 16 px strip into free lanes of
the atlas: the whole 0x0D page (only the lesson names, all translated) and
the empty lower half of the 0x0E page. A translated string is rewritten in
place as one record (plus the stock digit record for 'Exam N'), which is
never longer than the Japanese, so no pointer moves. The big title strip is
redrawn where it was. The same .BIZ files hold the report card images, so
their boxes from images.json (patch_images.redraw) are applied here too. Both
.BIZ files are recompressed to their stock sizes.

Usage: python patch_siken.py <stock.bin> <target.bin>
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nsn2lz  # noqa: E402
import pausefont  # noqa: E402
import psxtim  # noqa: E402
from patch_newopt import iso_files  # noqa: E402
from patch_pause import read_file, write_file  # noqa: E402
import patch_images  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
ATLAS_FILES = ["/DAT2/SIKEN1.BIZ", "/DAT2/SIKEN10.BIZ"]
PAGES = {0x0C: 0, 0x0D: 256, 0x0E: 512}          # texel x of each page in the TIM
LANE_H = 16
LANES = [(0x0D, v) for v in range(0, 256, LANE_H)] + [(0x0E, v) for v in range(128, 256, LANE_H)]
FONT, SIZE = r"C:\Windows\Fonts\tahoma.ttf", 13
TITLE_FONT, TITLE_SIZE = r"C:\Windows\Fonts\tahomabd.ttf", 24
BUTTON_WORDS = [(56, 72), (56, 96)]            # top-left of 決定 and 戻る
BUTTON_W, BUTTON_H = 46, 20
BUTTON_FONT, BUTTON_SIZE = r"C:\Windows\Fonts\tahomabd.ttf", 14
TITLE_OFFSETS = {"/DAT1/SIKEN2.BIN": 0x158, "/DAT1/SIKEN.BIN": 0xA4}


def render_title(text, width, height):
    """The title style: green fill rising 3..9 from top to bottom, a 2 px dark
    outline (13) and a drop shadow (1)."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    face = ImageFont.truetype(TITLE_FONT, TITLE_SIZE)
    box = face.getbbox(text)
    if box[2] - box[0] + 6 > width:
        raise SystemExit("title %r does not fit in %d px" % (text, width))
    mask = Image.new("L", (width, height), 0)
    left = (width - (box[2] - box[0])) // 2 - box[0]
    top = (height - (box[3] - box[1])) // 2 - box[1] - 1
    ImageDraw.Draw(mask).text((left, top), text, font=face, fill=255)
    solid = mask.point(lambda c: 255 if c >= 112 else 0)
    ring = solid.filter(ImageFilter.MaxFilter(5))
    shadow = ring.transform(ring.size, Image.AFFINE, (1, 0, -1, 0, 1, -1))
    y0, y1 = top + box[1], top + box[3]
    rows = []
    for y in range(height):
        shade = 3 + max(0, min(6, (y - y0) * 7 // max(1, y1 - y0)))
        rows.append([shade if solid.getpixel((x, y)) else 13 if ring.getpixel((x, y))
                     else 1 if shadow.getpixel((x, y)) else 0 for x in range(width)])
    return rows


def records(code, o):
    n = code[o]
    return [tuple(code[o + 1 + 5 * k:o + 6 + 5 * k]) for k in range(n)]


def main(stock, target):
    with open(os.path.join(REPO, "localization", "en", "siken.json"), encoding="utf-8") as fh:
        spec = json.load(fh)
    with open(stock, "rb") as f:
        files, sector = iso_files(f)
        atlases = {n: read_file(f, files, sector, n) for n in ATLAS_FILES}
        codes = {n: read_file(f, files, sector, n) for n in spec["files"]}

    raw = bytearray(nsn2lz.decompress(bytes(atlases[ATLAS_FILES[0]][2]))[0])
    tim = [t for t in psxtim.scan(raw) if t["image"][:2] == (768, 0)][0]
    _, _, words, height, pix = tim["image"]
    stride = words * 2

    def get(x, y):
        return (raw[pix + y * stride + x // 2] >> ((x & 1) * 4)) & 15

    def put(x, y, idx):
        o = pix + y * stride + x // 2
        sh = (x & 1) * 4
        raw[o] = (raw[o] & ~(15 << sh) & 0xFF) | (idx << sh)

    # Free the lanes: the 0x0D page holds only lesson names; the 0x0E lanes
    # must already be empty.
    for tp, v in LANES:
        for y in range(v, v + LANE_H):
            for x in range(256):
                if tp == 0x0E and get(PAGES[tp] + x, y):
                    raise SystemExit("atlas lane %#x/%d is not empty" % (tp, v))
                put(PAGES[tp] + x, y, 0)

    # One strip per distinct English string, first-fit into the lanes.
    texts = sorted({e["en"] for f in spec["files"].values() for e in f.values()},
                   key=lambda t: -pausefont.text_width(t, FONT, SIZE))
    used = [0] * len(LANES)
    strip = {}
    for t in texts:
        w = pausefont.text_width(t, FONT, SIZE)
        lane = next((i for i in range(len(LANES)) if used[i] + w <= 256), None)
        if lane is None:
            raise SystemExit("atlas lanes are full at %r" % t)
        tp, v = LANES[lane]
        img = pausefont.render_aa(t, w, LANE_H, FONT, SIZE)
        for y, row in enumerate(img):
            for x, idx in enumerate(row):
                put(PAGES[tp] + used[lane] + x, v + y, idx)
        strip[t] = (tp, used[lane], v, w, LANE_H)
        used[lane] += w

    # Title strip, redrawn in place (its records stay as they are).
    name = next(iter(TITLE_OFFSETS))
    tp, u, v, w, h = records(codes[name][2], TITLE_OFFSETS[name])[0]
    img = render_title(spec["title"]["en"], w, h)
    for y, row in enumerate(img):
        for x, idx in enumerate(row):
            put(PAGES[tp] + u + x, v + y, idx)

    # Button box (0x0E page, u 0..104, v 64..127): replace 決定 / 戻る with the
    # English words over the box's checker pattern (index 7 where x + y is
    # even); the box draws text with index 1 brightest, 2..5 for the edges.
    for word, (x0, y0) in zip(spec["buttons"]["en"], BUTTON_WORDS):
        for y in range(y0, y0 + BUTTON_H):
            for x in range(x0, x0 + BUTTON_W):
                put(PAGES[0x0E] + x, y, 7 if (x + y) % 2 == 0 else 0)
        img = pausefont.render_aa(word, BUTTON_W, BUTTON_H, BUTTON_FONT, BUTTON_SIZE, lo=5, hi=1)
        for y, row in enumerate(img):
            for x, idx in enumerate(row):
                if idx:
                    put(PAGES[0x0E] + x0 + x, y0 + y, idx)

    for name, entries in spec["files"].items():
        code = codes[name][2]
        for off, e in entries.items():
            o = int(off, 16)
            old = records(code, o)
            new = [strip[e["en"]]] + ([old[-1]] if e.get("keep_last") else [])
            assert len(new) <= len(old), (name, off)
            data = bytes([len(new)]) + b"".join(bytes(r) for r in new)
            code[o:o + 1 + 5 * len(old)] = data.ljust(1 + 5 * len(old), b"\0")

    with open(os.path.join(REPO, "localization", "en", "images.json"), encoding="utf-8") as fh:
        images = json.load(fh)["files"]
    with open(target, "r+b") as f:
        for name in ATLAS_FILES:
            lba, size, _ = atlases[name]
            stock_raw = nsn2lz.decompress(bytes(atlases[name][2]))[0]
            assert stock_raw[pix:pix + stride * height] == nsn2lz.decompress(
                bytes(atlases[ATLAS_FILES[0]][2]))[0][pix:pix + stride * height]
            out = bytearray(stock_raw)
            out[pix:pix + stride * height] = raw[pix:pix + stride * height]
            if name in images:   # the report card painted in the same file
                img = images[name]
                card = [t for t in psxtim.scan(out) if t["offset"] == int(img["tim_offset"], 16)][0]
                patch_images.redraw(out, card, img["boxes"], img["paper_box"])
            packed = nsn2lz.compress_exact(bytes(out), size)
            assert nsn2lz.decompress(packed)[0] == bytes(out)
            write_file(f, lba, packed)
        for name, (lba, _, code) in codes.items():
            write_file(f, lba, code)
    print("patched %s and %s: %d strips in %d lanes" % (", ".join(ATLAS_FILES), ", ".join(codes),
                                                       len(strip), sum(1 for u in used if u)))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
