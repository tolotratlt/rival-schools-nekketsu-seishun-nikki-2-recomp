"""Apply localization/en/pause.json to the in-battle pause menu inside a disc image.

The EXE draws each pause label (0x80023A58) as a row of 12 px tall sprites cut
from the font page loaded from /DAT2/OVER.TIZ (VRAM 960,256, 4 bpp). The
label table at 0x8008A0B8 points to [width units][piece count] followed by
(col, row, units) triples: u = col * 24 - 64 (mod 256), v = row * 12,
w = units * 24, and the label is centred on the 512 px screen.

The Japanese pieces live in u 192..239, v 0..131 (cols 0-1, rows 0-10). This
script clears that area, renders each English label there (pausefont.py),
cut into 48 px and 24 px pieces, recompresses OVER.TIZ to its exact stock size,
and rewrites the triples and the table in the EXE. Only those EXE bytes are
written, so the other EXE patches can run before or after this one.

Usage: python patch_pause.py <stock.bin> <target.bin>
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nsn2lz  # noqa: E402
import pausefont  # noqa: E402
import psxtim  # noqa: E402
from patch_newopt import iso_files  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
FONT_FILE = "/DAT2/OVER.TIZ"
EXE_FILE = "/SLPS_021.20"
LOAD, HEADER = 0x80010000, 0x800
LABELS = (0x8008A070, 0x8008A0B8)   # stock label data (72 bytes)
TABLE = 0x8008A0B8                  # 4 pointers
AREA_U, AREA_COLS, AREA_ROWS = 192, 2, 11
UNIT, ROW_H = 24, 12


def read_file(f, files, sector, name):
    _, lba, size = [x for x in files if x[0] == name][0]
    nsec = (size + 2047) // 2048
    return lba, size, bytearray(b"".join(sector(lba + k) for k in range(nsec))[:size])


def write_file(f, lba, data):
    for k in range(0, len(data), 2048):
        f.seek((lba + k // 2048) * 2352 + 24)
        f.write(bytes(data[k:k + 2048]))


def main(stock, target):
    with open(os.path.join(REPO, "localization", "en", "pause.json"), encoding="utf-8") as fh:
        labels = [e["en"] for e in json.load(fh)["labels"]]
    with open(stock, "rb") as f:
        files, sector = iso_files(f)
        font_lba, font_size, comp = read_file(f, files, sector, FONT_FILE)
        exe_lba, _, exe = read_file(f, files, sector, EXE_FILE)
    raw = bytearray(nsn2lz.decompress(bytes(comp))[0])
    tim = psxtim.scan(raw)[0]
    _, _, words, height, pix = tim["image"]
    stride = words * 2

    def put(u, v, idx):
        o = pix + v * stride + u // 2
        sh = (u & 1) * 4
        raw[o] = (raw[o] & ~(15 << sh) & 0xFF) | (idx << sh)

    for v in range(AREA_ROWS * ROW_H):
        for u in range(AREA_U, AREA_U + AREA_COLS * UNIT):
            put(u, v, 0)
    blob, ptrs = bytearray(), []
    for pieces, units in pausefont.pack(labels, AREA_COLS, AREA_ROWS):
        ptrs.append(LABELS[0] + len(blob))
        blob += bytes([units, len(pieces)])
        for c, r, n, rows in pieces:
            for y, row in enumerate(rows):
                for x, idx in enumerate(row):
                    put(AREA_U + c * UNIT + x, r * ROW_H + y, idx)
            # u = col * 24 - 64 (mod 256): u 192 is col 0, u 216 is col 1.
            col = (AREA_U + c * UNIT + 64) % 256 // UNIT
            assert (col * UNIT - 64) & 0xFF == AREA_U + c * UNIT
            blob += bytes([col, r, n])
    if len(blob) > LABELS[1] - LABELS[0]:
        raise SystemExit("label data is %d bytes, room for %d" % (len(blob), LABELS[1] - LABELS[0]))
    packed = nsn2lz.compress_exact(bytes(raw), font_size)
    assert nsn2lz.decompress(packed)[0] == bytes(raw)

    o = LABELS[0] - LOAD + HEADER
    exe[o:o + LABELS[1] - LABELS[0]] = bytes(blob).ljust(LABELS[1] - LABELS[0], b"\0")
    struct.pack_into("<4I", exe, TABLE - LOAD + HEADER, *ptrs)
    with open(target, "r+b") as f:
        write_file(f, font_lba, packed)
        # Only the sectors holding the label data and table.
        first, last = (LABELS[0] - LOAD + HEADER) // 2048, (TABLE + 16 - LOAD + HEADER) // 2048
        for k in range(first, last + 1):
            f.seek((exe_lba + k) * 2352 + 24 + 0)
            cur = bytearray(f.read(2048))
            lo, hi = k * 2048, (k + 1) * 2048
            for a in range(max(lo, o), min(hi, TABLE + 16 - LOAD + HEADER)):
                cur[a - lo] = exe[a]
            f.seek((exe_lba + k) * 2352 + 24)
            f.write(bytes(cur))
    print("patched %s and %d pause labels (%d bytes)" % (FONT_FILE, len(labels), len(blob)))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
