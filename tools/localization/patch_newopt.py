"""Apply localization/en/newopt.json to /DAT1/NEWOPT.BIN inside a disc image.

The overlay is loaded at 0x800A2000 by whole sectors, so the unused tail of
its last sector (file end .. sector end) is loaded with it and serves as extra
room for the longer English strings.

Usage: python patch_newopt.py <stock.bin> <target.bin>
  <stock.bin> is read only (the original dump); <target.bin> is modified in
  place (use a copy of the dump).
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nsn2menu  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
FILE = "/DAT1/NEWOPT.BIN"
BASE = 0x800A2000
POOL = (0x036C, 0x0B64)          # stock string pool, file offsets (RAM 0x800A236C-0x800A2B64)
RECORDS = 0x0090                  # 16 label records: col, row, colour, string index
OFFSCREEN_COL = 0x30              # column 48: drawn past the 512-px screen edge


def iso_files(f):
    def sector(lba):
        f.seek(lba * 2352)
        return f.read(2352)[24:24 + 2048]

    def extent(lba, size):
        out = b""
        while len(out) < size:
            out += sector(lba)
            lba += 1
        return out[:size]

    files = []

    def walk(lba, size, path):
        data = extent(lba, size)
        o = 0
        while o < len(data):
            ln = data[o]
            if ln == 0:
                o = (o // 2048 + 1) * 2048
                continue
            rec = data[o:o + ln]
            o += ln
            name = rec[33:33 + rec[32]]
            if name in (b"\x00", b"\x01"):
                continue
            full = path + "/" + name.decode("ascii").split(";")[0]
            elba, esize = struct.unpack_from("<I", rec, 2)[0], struct.unpack_from("<I", rec, 10)[0]
            if rec[25] & 2:
                walk(elba, esize, full)
            else:
                files.append((full, elba, esize))

    root = sector(16)[156:190]
    walk(struct.unpack_from("<I", root, 2)[0], struct.unpack_from("<I", root, 10)[0], "")
    return files, sector


def main(stock, target):
    with open(stock, "rb") as f:
        files, sector = iso_files(f)
        _, lba, size = [x for x in files if x[0] == FILE][0]
        nsec = (size + 2047) // 2048
        image = b"".join(sector(lba + k) for k in range(nsec))  # file + sector tail
    # Every aligned word pointing into the pool is a string slot, including the
    # big-glyph titles (codes >= 0x300) that find_tables cannot decode.
    slots = [(o, struct.unpack_from("<I", image, o)[0]) for o in range(0, size - 3, 4)
             if BASE + POOL[0] <= struct.unpack_from("<I", image, o)[0] < BASE + POOL[1]]
    tables = [slots]
    with open(os.path.join(REPO, "localization", "en", "newopt.json"), encoding="utf-8") as fh:
        en = json.load(fh)["strings"]

    def translate(ja):
        return en.get(ja)

    new, used = nsn2menu.rebuild_pool(image, BASE, tables, translate,
                                      [POOL, (size, nsec * 2048)])
    # Compound labels "マッチ" + "数(CPU)" / "数(VS)": show the full English label
    # from the first record and move the second one off screen.
    for rec, idx in ((RECORDS + 0x10, 0x05), (RECORDS + 0x18, 0x06)):
        assert new[rec:rec + 4] == bytes([2, new[rec + 1], 7, 0x0E]), new[rec:rec + 4].hex()
        new[rec + 3] = idx
        assert new[rec + 7] == idx, new[rec + 4:rec + 8].hex()
        new[rec + 4] = OFFSCREEN_COL
    with open(target, "r+b") as f:
        for k in range(nsec):
            f.seek((lba + k) * 2352 + 24)
            f.write(bytes(new[k * 2048:(k + 1) * 2048]))
    for a, c, b in used:
        print("area %#06x-%#06x: %d/%d bytes used" % (a, b, c - a, b - a))
    print("patched %s (%d sectors at LBA %d)" % (FILE, nsec, lba))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
