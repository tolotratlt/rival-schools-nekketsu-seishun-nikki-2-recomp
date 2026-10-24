"""Apply localization/en/exe_strings.json to the menu string pool of the boot
EXE (SLPS_021.20) inside a disc image.

The EXE keeps its own copy of the option / memory-card strings (pool
0x8008FD5C-0x80090560, tables 0x80090560-0x80090800). There is no spare room
after it, so the English must fit the stock pool; strings without an entry in
the JSON keep their Japanese codes.

Usage: python patch_exe_strings.py <stock.bin> <target.bin>
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nsn2menu  # noqa: E402
from patch_newopt import iso_files  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
FILE = "/SLPS_021.20"
LOAD = 0x80010000
HEADER = 0x800
POOL = (0x8008FD5C, 0x80090564)  # end = last stock string (0x80090554, 6 glyphs) + 2-byte pad
SLOTS = (0x80090564, 0x80090800)
RECORDS_LIST = 0x80089F4C   # Records screen labels: (col, row, colour, string index); first = title
AUTO_RECORDS = 0x8008FFF8   # the "オート" string used by that list
OFFSCREEN_COL = 0x30


def main(stock, target):
    with open(stock, "rb") as f:
        files, sector = iso_files(f)
        _, lba, size = [x for x in files if x[0] == FILE][0]
        nsec = (size + 2047) // 2048
        image = bytearray(b"".join(sector(lba + k) for k in range(nsec))[:size])
    text = image[HEADER:]
    a, b = (p - LOAD for p in POOL)
    slots = [(o, struct.unpack_from("<I", text, o)[0])
             for o in range(SLOTS[0] - LOAD, SLOTS[1] - LOAD, 4)
             if POOL[0] <= struct.unpack_from("<I", text, o)[0] < POOL[1]]
    with open(os.path.join(REPO, "localization", "en", "exe_strings.json"), encoding="utf-8") as fh:
        en = json.load(fh)["strings"]
    # Records screen: "オート" (col 2) + "セーブ" (col 5) on row 8 would read
    # "AutSave"; give that オート its own "Auto" (the value sits at col 9) and move the second record
    # off screen. The other オート (game-system value 0x80090364) stays "Auto".
    new, used = nsn2menu.rebuild_pool(text, LOAD, [slots], en.get, [(a, b)],
                                      by_address={AUTO_RECORDS: "Auto"})
    rec = RECORDS_LIST - LOAD + 0x10  # 5th record: (5, 8, 7, セーブ)
    assert bytes(new[rec:rec + 4]) == bytes([5, 8, 7, 0x2C]), bytes(new[rec:rec + 4]).hex()
    new[rec] = OFFSCREEN_COL
    image[HEADER:] = new
    with open(target, "r+b") as f:
        for k in range(nsec):
            f.seek((lba + k) * 2352 + 24)
            f.write(bytes(image[k * 2048:(k + 1) * 2048]))
    for s, c, e in used:
        print("pool: %d/%d bytes used, %d slots" % (c - s, e - s, len(slots)))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
