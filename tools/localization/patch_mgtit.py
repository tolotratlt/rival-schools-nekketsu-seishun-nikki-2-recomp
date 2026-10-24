"""Apply localization/en/mgtit.json to /DAT1/MGTIT.BIZ (compressed overlay,
loaded at 0x800A2000) inside a disc image.

Slots are 12-byte records [ptr, 0, x, y] (pixels). Translated lines are
re-centred on the 512-px screen (20 px per glyph) unless "keep_x" is set.

Usage: python patch_mgtit.py <stock.bin> <target.bin>
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nsn2lz  # noqa: E402
import nsn2menu  # noqa: E402
from patch_newopt import iso_files  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
FILE = "/DAT1/MGTIT.BIZ"
BASE = 0x800A2000
SLOTS = range(0x2A4, 0x37C, 12)   # 18 records
POOL = (0x010, 0x208)
SCREEN_W, GLYPH_W = 512, 20


def main(stock, target):
    with open(stock, "rb") as f:
        files, sector = iso_files(f)
        _, lba, size = [x for x in files if x[0] == FILE][0]
        nsec = (size + 2047) // 2048
        comp = b"".join(sector(lba + k) for k in range(nsec))[:size]
    raw, _ = nsn2lz.decompress(comp)
    with open(os.path.join(REPO, "localization", "en", "mgtit.json"), encoding="utf-8") as fh:
        spec = json.load(fh)["by_address"]
    by_addr = {int(k, 16): v["en"] for k, v in spec.items()}
    slots = [(o, struct.unpack_from("<I", raw, o)[0]) for o in SLOTS]
    new, used = nsn2menu.rebuild_pool(raw, BASE, [slots], lambda t: None, [POOL], by_address=by_addr)
    for o, ptr in slots:
        entry = spec.get("0x%08x" % ptr)
        if entry and not entry.get("keep_x"):
            n = len(entry["en"])
            struct.pack_into("<H", new, o + 8, max(0, (SCREEN_W - GLYPH_W * n) // 2))
    packed = nsn2lz.compress_exact(bytes(new), size)
    assert nsn2lz.decompress(packed)[0] == bytes(new)
    with open(target, "r+b") as f:
        for k in range(nsec):
            f.seek((lba + k) * 2352 + 24)
            f.write(packed[k * 2048:(k + 1) * 2048])
    for a, c, b in used:
        print("pool: %d/%d bytes used" % (c - a, b - a))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
