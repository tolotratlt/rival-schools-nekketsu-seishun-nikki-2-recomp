"""Apply localization/en/testmj.json to the lesson / exam instruction bubbles
inside a disc image.

/DAT2/TESTMJ.TIZ is a container: (offset, size) pairs from byte 0, each entry
an LZ-compressed TIM for VRAM (896,256), one per lesson (0-29) or exam
subject (30-32). Row 0 of a page holds the title, shown as one 160x15 sprite;
the message is a run of 32x16 cells, one stretched glyph each (the fight
screens are 512 px wide with tall pixels). Messages are [first cell][count]
runs, 0xFE = new line, 0xFF = end, listed by pointer tables in the lesson and
exam overlays (MESSAGES below). Cells a message skips, and the cells after
it, hold other words and stay as they are.

For every page this script clears the message cells, renders each English
line (Tahoma Bold, stretched 1.5x to match the stock glyphs; {N} copies stock
cell N, used for button icons) into the next free message cells, redraws the
title within the stock HUD width (lessons: the byte table at SIKEN.BIN 0xCC0;
exams: 160 px), recompresses the entry to its stock size and rewrites the message runs
in place (never longer than the stock bytes).

Usage: python patch_testmj.py <stock.bin> <target.bin> [<preview dir>]
"""
import json
import os
import re
import struct
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nsn2lz  # noqa: E402
import psxtim  # noqa: E402
from patch_newopt import iso_files  # noqa: E402
from patch_pause import read_file, write_bytes  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
CONTAINER = "/DAT2/TESTMJ.TIZ"
# overlay -> (file offset of the pointer table, number of messages, first page)
MESSAGES = {
    "/DAT1/SIKENGO1.BIN": (0x530, 30, 0), "/DAT1/SIKENGO2.BIN": (0x530, 30, 0),
    "/DAT1/SIKENG21.BIN": (0x39C, 3, 30), "/DAT1/SIKENG22.BIN": (0x39C, 3, 30),
}
CELL_W, CELL_H, PER_ROW = 32, 16, 8
MAX_LINE_CELLS = 14
STRETCH = 1.5
FONT, SIZE = r"C:\Windows\Fonts\tahomabd.ttf", 13
TITLE_SIZE, TITLE_H = 11, 15
# Each page has its own palette: the background is its 0x0000 entry, the ink
# its darkest grey, the outline its brightest; edges use the grey nearest in
# brightness (see Style).
TITLE_WIDTHS = ("/DAT1/SIKEN.BIN", 0xCC0)   # lesson HUD title widths (bytes)
EXAM_TITLE_W = 160


class Style:
    def __init__(self, raw, tim):
        co = tim["clut"][4]
        pal = [int.from_bytes(raw[co + 2 * k:co + 2 * k + 2], "little") for k in range(16)]
        self.back = pal.index(0)
        rgb = {k: ((c & 31), (c >> 5 & 31), (c >> 10 & 31)) for k, c in enumerate(pal) if c}
        greys = {k: sum(v) / 3 for k, v in rgb.items() if max(v) - min(v) <= 2}
        self.ink = min(greys, key=greys.get)
        self.outline = max(greys, key=greys.get)
        lo, hi = greys[self.ink], greys[self.outline]
        self.edge = [min(greys, key=lambda k: abs(greys[k] - (hi + (lo - hi) * c / 255))) for c in range(256)]


STYLE = None


def read_runs(data, o):
    runs = []
    while data[o] != 0xFF:
        if data[o] == 0xFE:
            runs.append(None)
            o += 1
        else:
            runs.append((data[o], data[o + 1]))
            o += 2
    return runs, o + 1


def text_pixels(text, height, size, stretch=STRETCH):
    """Rows of indices for `text`, stretched horizontally like the stock glyphs."""
    face = ImageFont.truetype(FONT, size)
    w = int(face.getlength(text)) + 3
    mask = Image.new("L", (w, height), 0)
    box = face.getbbox("Ag")
    ImageDraw.Draw(mask).text((1, (height - (box[3] - box[1])) // 2 - box[1]), text, font=face, fill=255)
    mask = mask.resize((max(1, round(w * stretch)), height), Image.LANCZOS)
    ring = mask.point(lambda c: 255 if c >= 96 else 0).filter(ImageFilter.MaxFilter(3))
    rows = []
    for y in range(height):
        row = []
        for x in range(mask.width):
            c = mask.getpixel((x, y))
            if c >= 200:
                row.append(STYLE.ink)
            elif c >= 48:
                row.append(STYLE.edge[c])
            elif ring.getpixel((x, y)):
                row.append(STYLE.outline)
            else:
                row.append(STYLE.back)
        rows.append(row)
    return rows


def build_line(line, stock_cell):
    """Columns of a line: text pieces and copied stock cells ({N})."""
    rows = [[] for _ in range(CELL_H)]
    for part in re.split(r"(\{\d+\})", line):
        if not part:
            continue
        if part.startswith("{"):
            img = stock_cell(int(part[1:-1]))
        else:
            img = text_pixels(part, CELL_H, SIZE)
        for y in range(CELL_H):
            rows[y] += img[y]
    return rows


def redraw_page(raw, runs, lines, title, title_w):
    global STYLE
    tim = psxtim.scan(raw)[0]
    STYLE = Style(raw, tim)
    _, _, words, _, pix = tim["image"]
    stride = words * 2

    def get(x, y):
        return (raw[pix + y * stride + x // 2] >> ((x & 1) * 4)) & 15

    def put(x, y, idx):
        o = pix + y * stride + x // 2
        sh = (x & 1) * 4
        raw[o] = (raw[o] & ~(15 << sh) & 0xFF) | (idx << sh)

    def cell_xy(c):
        return (c % PER_ROW) * CELL_W, (c // PER_ROW) * CELL_H

    stock = {}

    def stock_cell(c):
        if c not in stock:
            x0, y0 = cell_xy(c)
            stock[c] = [[get(x0 + x, y0 + y) for x in range(CELL_W)] for y in range(CELL_H)]
        return stock[c]

    cells = [c for r in runs if r for c in range(r[0], r[0] + r[1])]
    for line in lines:                       # read the icons before clearing
        for n in re.findall(r"\{(\d+)\}", line):
            stock_cell(int(n))
    for c in cells:
        x0, y0 = cell_xy(c)
        for y in range(CELL_H):
            for x in range(CELL_W):
                put(x0 + x, y0 + y, STYLE.back)

    new_runs, free = [], list(cells)
    for i, line in enumerate(lines):
        img = build_line(line, stock_cell)
        n = -(-len(img[0]) // CELL_W)
        if n > MAX_LINE_CELLS:
            raise SystemExit("line %r needs %d cells, max %d" % (line, n, MAX_LINE_CELLS))
        if n > len(free):
            raise SystemExit("message runs out of cells at %r" % line)
        use, free = free[:n], free[n:]
        if i:
            new_runs.append(None)
        for k, c in enumerate(use):
            x0, y0 = cell_xy(c)
            for y in range(CELL_H):
                for x in range(CELL_W):
                    sx = k * CELL_W + x
                    put(x0 + x, y0 + y, img[y][sx] if sx < len(img[0]) else STYLE.back)
            if new_runs and new_runs[-1] and new_runs[-1][0] + new_runs[-1][1] == c:
                new_runs[-1] = (new_runs[-1][0], new_runs[-1][1] + 1)
            else:
                new_runs.append((c, 1))

    # Title: the HUD shows u 0..title_w-1, v 0..14 of row 0; stay left of the
    # first message cell.
    limit = min(title_w, min(cells) * CELL_W) if min(cells) < PER_ROW else title_w
    for stretch in (STRETCH, 1.25, 1.0):     # narrower if the title is long
        timg = text_pixels(title, TITLE_H, TITLE_SIZE, stretch)
        if len(timg[0]) <= limit:
            break
    else:
        raise SystemExit("title %r is %d px, room for %d" % (title, len(timg[0]), limit))
    for y in range(TITLE_H + 1):
        for x in range(limit):
            put(x, y, timg[y][x] if y < TITLE_H and x < len(timg[0]) else STYLE.back)
    return new_runs


def encode_runs(runs):
    out = bytearray()
    for r in runs:
        out += b"\xFE" if r is None else bytes(r)
    return bytes(out + b"\xFF")


def main(stock, target, preview=None):
    with open(os.path.join(REPO, "localization", "en", "testmj.json"), encoding="utf-8") as fh:
        pages = json.load(fh)["pages"]
    with open(stock, "rb") as f:
        files, sector = iso_files(f)
        c_lba, c_size, cont = read_file(f, files, sector, CONTAINER)
        overlays = {n: read_file(f, files, sector, n) for n in MESSAGES}
        widths = read_file(f, files, sector, TITLE_WIDTHS[0])[2][TITLE_WIDTHS[1]:TITLE_WIDTHS[1] + 30]

    # Stock runs per page, from the first overlay of each kind.
    page_runs = {}
    for name, (table, count, first) in MESSAGES.items():
        data = overlays[name][2]
        for k in range(count):
            p = struct.unpack_from("<I", data, table + 4 * k)[0]
            o = p - (p & ~0xFFF)
            runs, _ = read_runs(data, o)
            if first + k in page_runs:
                assert page_runs[first + k] == runs, (name, k)
            page_runs[first + k] = runs

    entries = []
    k = 0
    while struct.unpack_from("<I", cont, 8 * k)[0]:
        entries.append(struct.unpack_from("<II", cont, 8 * k))
        k += 1
    new_runs = {}
    for i, page in enumerate(pages):
        off, size = entries[i]
        raw = bytearray(nsn2lz.decompress(bytes(cont[off:off + size]))[0])
        title_w = widths[i] if i < len(widths) else EXAM_TITLE_W
        new_runs[i] = redraw_page(raw, page_runs[i], page["en"], page["title"], title_w)
        if preview:
            tim = psxtim.scan(raw)[0]
            pix = tim["image"][4]
            im = Image.new("L", (256, 256))
            im.putdata([255 - ((raw[pix + y * 128 + x // 2] >> ((x & 1) * 4)) & 15) * 17
                        for y in range(256) for x in range(256)])
            im.save(os.path.join(preview, "testmj_%02d.png" % i))
        packed = nsn2lz.compress_exact(bytes(raw), size)
        assert nsn2lz.decompress(packed)[0] == bytes(raw)
        cont[off:off + size] = packed

    with open(target, "r+b") as f:
        write_bytes(f, c_lba, 0, cont)
        for name, (table, count, first) in MESSAGES.items():
            lba, _, data = overlays[name]
            for k in range(count):
                p = struct.unpack_from("<I", data, table + 4 * k)[0]
                o = p - (p & ~0xFFF)
                _, end = read_runs(data, o)
                blob = encode_runs(new_runs[first + k])
                if len(blob) > end - o:
                    raise SystemExit("%s message %d: %d bytes, room for %d" % (name, k, len(blob), end - o))
                data[o:end] = blob.ljust(end - o, b"\xFF")
            write_bytes(f, lba, 0, data)
    print("patched %s (%d pages) and %d overlays" % (CONTAINER, len(pages), len(MESSAGES)))


if __name__ == "__main__":
    main(*sys.argv[1:4])
