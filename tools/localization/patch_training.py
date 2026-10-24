"""Apply localization/en/training.json to the Training pause menu inside a disc image.

The overlay /DAT1/TRAIN.BIN (loaded at 0x800A2000) draws each label as a row
of 12 px tall sprites cut from the atlas TIM of /DAT2/CEFT3.BIZ (VRAM 768,256,
4 bpp). The table at 0x800A2130 (15 pointers, read at 0x800A3768) points to
[piece count] followed by (col, row, units) triples: u = col * 24, v = row * 12,
w = units * 24; the overlay centres the label from the sum of the units.

The Japanese glyphs fill u 0..239, v 0..71 and v 72..95 is empty, so this
script clears u 0..239, v 0..95, renders the English there (pausefont.py),
recompresses CEFT3.BIZ to its exact stock size and rewrites the labels in the
stock string area 0x800A2084..0x800A212F (the unreferenced コマンド表を表示
string there is dropped). The rest of the atlas (HUD digits and kana) is kept.
The label x positions (tables at 0x800A2040 and 0x800A2054) are recomputed so
menu labels stay centred and the sub-menu values stay right-aligned.

Usage: python patch_training.py <stock.bin> <target.bin>
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
from patch_pause import read_file, write_file  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
ATLAS_FILE = "/DAT2/CEFT3.BIZ"
CODE_FILE = "/DAT1/TRAIN.BIN"
BASE = 0x800A2000
STRINGS = (0x800A2084, 0x800A2130)
TABLE, SLOTS = 0x800A2130, 15
COLS, ROWS = 10, 8
# (x, y) shorts the callers pass as the label start. Stock x values are the
# centre / right edge minus the stock width, so they are recomputed from the
# English widths: address -> (table slot, how the x is anchored).
POSITIONS = {
    0x800A2040: (0, "centre"), 0x800A2044: (1, "centre"), 0x800A2048: (2, "centre"),
    0x800A204C: (3, "centre"), 0x800A2050: (4, "centre"),        # pause menu
    0x800A2054: (2, "centre"), 0x800A2064: (9, "centre"),        # sub-menu title, back
    0x800A2068: (10, "right"), 0x800A206C: (11, "right"), 0x800A2070: (12, "right"),
    0x800A2074: (13, "right"), 0x800A2078: (14, "right"),        # dummy state, guard
    0x800A207C: (13, "right"), 0x800A2080: (14, "right"),        # ukemi
}
CENTRE_X, RIGHT_X = 256, 376
UNIT, ROW_H = 24, 12
# Stock atlas rows 0-5, read from the TIM; used to name the stock labels.
STOCK_ROWS = ["メニュートレング続行", "ャコマドを表示シチエ", "変更ョ設定キラクモに",
              "戻る敵の状態カ受け身", "立ちしゃがみジプすな", "いタ"]


def decode(code, o):
    out = ""
    for k in range(code[o]):
        c, r, n = code[o + 1 + 3 * k:o + 4 + 3 * k]
        out += STOCK_ROWS[r][c:c + n]
    return out


def align_of(ja, stock_ja):
    """Left for the sub-menu row labels, right for the values, else centred."""
    slots = [k for k, j in enumerate(stock_ja) if j == ja]
    if any(k in (6, 7, 8) for k in slots):
        return "left"
    if any(k >= 10 for k in slots):
        return "right"
    return "centre"


def main(stock, target):
    with open(os.path.join(REPO, "localization", "en", "training.json"), encoding="utf-8") as fh:
        en = json.load(fh)["labels"]
    with open(stock, "rb") as f:
        files, sector = iso_files(f)
        atlas_lba, atlas_size, comp = read_file(f, files, sector, ATLAS_FILE)
        code_lba, _, code = read_file(f, files, sector, CODE_FILE)
    ptrs = struct.unpack_from("<%dI" % SLOTS, code, TABLE - BASE)
    stock_ja = [decode(code, p - BASE) for p in ptrs]
    labels = sorted(set(stock_ja), key=stock_ja.index)

    raw = bytearray(nsn2lz.decompress(bytes(comp))[0])
    tim = [t for t in psxtim.scan(raw) if t["image"][:2] == (768, 256)][0]
    _, _, words, _, pix = tim["image"]
    stride = words * 2

    def put(u, v, idx):
        o = pix + v * stride + u // 2
        sh = (u & 1) * 4
        raw[o] = (raw[o] & ~(15 << sh) & 0xFF) | (idx << sh)

    for v in range(ROWS * ROW_H):
        for u in range(COLS * UNIT):
            put(u, v, 0)
    blob, at, width = bytearray(), {}, {}
    for ja, (pieces, units) in zip(labels, pausefont.pack([en[j] for j in labels], COLS, ROWS,
                                                             [align_of(j, stock_ja) for j in labels])):
        at[ja] = STRINGS[0] + len(blob)
        width[ja] = units * UNIT
        blob += bytes([len(pieces)])
        for c, r, n, rows in pieces:
            for y, row in enumerate(rows):
                for x, idx in enumerate(row):
                    put(c * UNIT + x, r * ROW_H + y, idx)
            blob += bytes([c, r, n])
        blob += bytes(-len(blob) % 4)   # keep the stock 4-byte alignment
    if len(blob) > STRINGS[1] - STRINGS[0]:
        raise SystemExit("labels need %d bytes, room for %d" % (len(blob), STRINGS[1] - STRINGS[0]))
    packed = nsn2lz.compress_exact(bytes(raw), atlas_size)
    assert nsn2lz.decompress(packed)[0] == bytes(raw)

    o = STRINGS[0] - BASE
    code[o:STRINGS[1] - BASE] = bytes(blob).ljust(STRINGS[1] - STRINGS[0], b"\0")
    struct.pack_into("<%dI" % SLOTS, code, TABLE - BASE, *[at[j] for j in stock_ja])
    for addr, (slot, anchor) in POSITIONS.items():
        w = width[stock_ja[slot]]
        x = CENTRE_X - w // 2 if anchor == "centre" else RIGHT_X - w
        struct.pack_into("<h", code, addr - BASE, x)
    with open(target, "r+b") as f:
        write_file(f, atlas_lba, packed)
        write_file(f, code_lba, code)
    print("patched %s and %s: %d labels, %d/%d bytes" % (ATLAS_FILE, CODE_FILE, len(labels),
                                                         len(blob), STRINGS[1] - STRINGS[0]))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
