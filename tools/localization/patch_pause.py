"""Apply localization/en/pause.json to the battle pause menus inside a disc image.

The EXE draws each pause label (0x80023A58) as a row of 12 px tall sprites cut
from the font page loaded from /DAT2/OVER.TIZ (VRAM 960,256, 4 bpp). A label
is [width units][piece count] followed by (col, row, units) triples:
u = col * 24 - 64 (mod 256), v = row * 12, w = units * 24, and the label is
centred on the 512 px screen from its width units.

The EXE keeps four labels at 0x8008A070 with their table at 0x8008A0B8
(1P / 2P title, continue, back to the mode menu). The exam and mini-game
overlays (OVERLAYS below) carry their own copy: the same three first labels,
a 戻る label, and a four-pointer table right after the 52-byte block.

The Japanese pieces live in u 192..239, v 0..131 (cols 0-1, rows 0-10). This
script clears that area, renders every English label there once
(pausefont.py), recompresses OVER.TIZ to its exact stock size and rewrites
the label blocks. Only those bytes of the EXE are written, so the other EXE
patches can run before or after this one.

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
EXE_LABELS = (0x8008A070, 0x8008A0B8)   # stock label data (72 bytes), table follows
EXE_ORDER = ["1Pポーズ", "2Pポーズ", "つづける", "モードメニューに戻る"]
OVERLAYS = ["/DAT1/MGAME01.BIN", "/DAT1/MGAME02.BIN", "/DAT1/MGAME03.BIN", "/DAT1/MGAME05.BIN",
            "/DAT1/MGAME06.BIN", "/DAT1/SIKENG21.BIN", "/DAT1/SIKENG22.BIN",
            "/DAT1/SIKENGO1.BIN", "/DAT1/SIKENGO2.BIN", "/DAT1/SKHAY.BIN"]
OVERLAY_ORDER = ["1Pポーズ", "2Pポーズ", "つづける", "戻る"]
OVERLAY_BLOCK = 0x34
# First bytes of the stock label block, used to find it in each overlay.
STOCK_BLOCK = bytes.fromhex("0504000001000901000202000301000005040100010009010002020003010000")
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


def write_bytes(f, lba, start, data):
    """Write `data` at byte `start` of a file without touching its other bytes."""
    pos = 0
    while pos < len(data):
        k, o = divmod(start + pos, 2048)
        n = min(2048 - o, len(data) - pos)
        f.seek((lba + k) * 2352 + 24 + o)
        f.write(bytes(data[pos:pos + n]))
        pos += n


def build_block(order, encoded, base, room):
    """Label data for `order` at address `base`; returns (bytes, pointers)."""
    blob, ptrs = bytearray(), []
    for ja in order:
        ptrs.append(base + len(blob))
        blob += encoded[ja]
    if len(blob) > room:
        raise SystemExit("label data is %d bytes, room for %d" % (len(blob), room))
    return bytes(blob).ljust(room, b"\0"), ptrs


def main(stock, target):
    with open(os.path.join(REPO, "localization", "en", "pause.json"), encoding="utf-8") as fh:
        en = {e["ja"]: e["en"] for e in json.load(fh)["labels"]}
    with open(stock, "rb") as f:
        files, sector = iso_files(f)
        font_lba, font_size, comp = read_file(f, files, sector, FONT_FILE)
        exe_lba, _, exe = read_file(f, files, sector, EXE_FILE)
        overlays = {n: read_file(f, files, sector, n) for n in OVERLAYS}
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
    names = list(en)
    encoded = {}
    for ja, (pieces, units) in zip(names, pausefont.pack([en[j] for j in names], AREA_COLS, AREA_ROWS)):
        data = bytearray([units, len(pieces)])
        for c, r, n, rows in pieces:
            for y, row in enumerate(rows):
                for x, idx in enumerate(row):
                    put(AREA_U + c * UNIT + x, r * ROW_H + y, idx)
            # u = col * 24 - 64 (mod 256): u 192 is col 0, u 216 is col 1.
            col = (AREA_U + c * UNIT + 64) % 256 // UNIT
            assert (col * UNIT - 64) & 0xFF == AREA_U + c * UNIT
            data += bytes([col, r, n])
        encoded[ja] = bytes(data)
    packed = nsn2lz.compress_exact(bytes(raw), font_size)
    assert nsn2lz.decompress(packed)[0] == bytes(raw)

    exe_block, exe_ptrs = build_block(EXE_ORDER, encoded, EXE_LABELS[0], EXE_LABELS[1] - EXE_LABELS[0])
    with open(target, "r+b") as f:
        write_file(f, font_lba, packed)
        write_bytes(f, exe_lba, EXE_LABELS[0] - LOAD + HEADER,
                    exe_block + struct.pack("<4I", *exe_ptrs))
        for name, (lba, _, data) in overlays.items():
            o = data.find(STOCK_BLOCK)
            if o < 0 or data.find(STOCK_BLOCK, o + 1) >= 0:
                raise SystemExit("%s: stock pause labels not found once" % name)
            base = struct.unpack_from("<I", data, o + OVERLAY_BLOCK)[0]   # table entry 0 = block start
            if base & 0xFFF != (o & 0xFFF) or base >> 24 != 0x80:
                raise SystemExit("%s: no label table after the block (%#x)" % (name, base))
            block, ptrs = build_block(OVERLAY_ORDER, encoded, base, OVERLAY_BLOCK)
            write_bytes(f, lba, o, block + struct.pack("<4I", *ptrs))
    print("patched %s, the EXE and %d overlays (%d labels)" % (FONT_FILE, len(OVERLAYS), len(en)))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
