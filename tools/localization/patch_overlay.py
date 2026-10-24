"""Generic menu-string patcher for screen overlays loaded at 0x800A2000.

Each config names the file, the string areas (file offsets) that hold the
stock pool, whether the file is LZ-compressed, whether the unused tail of the
last sector may receive overflow, and the translation JSON (keyed by stock
string address under "by_address"). Every aligned word pointing into the
areas is treated as a string pointer and relocated.

Usage: python patch_overlay.py <config> <stock.bin> <target.bin>
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
BASE = 0x800A2000

CONFIGS = {
    # EDIT character registration. String areas sit between record blocks.
    "kanri": {"file": "/DAT1/KANRI.BIN", "compressed": False, "use_tail": True,
              # Each area ends exactly where its last stock string ends: the
              # following bytes belong to the record blocks.
              "areas": [(0x2D0, 0x4CC), (0x64C, 0x824), (0x92C, 0x95C),
                        (0x9A4, 0x9D4), (0xA1C, 0xA42)],
              "json": "kanri.json"},
}


def main(name, stock, target):
    cfg = CONFIGS[name]
    with open(stock, "rb") as f:
        files, sector = iso_files(f)
        _, lba, size = [x for x in files if x[0] == cfg["file"]][0]
        nsec = (size + 2047) // 2048
        disk = b"".join(sector(lba + k) for k in range(nsec))
    raw = nsn2lz.decompress(disk[:size])[0] if cfg["compressed"] else disk
    end = len(raw) if cfg["compressed"] else size
    areas = list(cfg["areas"])
    if cfg["use_tail"] and not cfg["compressed"]:
        areas.append((size, nsec * 2048))

    def in_areas(p):
        return any(BASE + a <= p < BASE + b for a, b in cfg["areas"])

    slots = [(o, struct.unpack_from("<I", raw, o)[0]) for o in range(0, end - 3, 4)
             if in_areas(struct.unpack_from("<I", raw, o)[0])
             and not any(a <= o < b for a, b in cfg["areas"])]
    with open(os.path.join(REPO, "localization", "en", cfg["json"]), encoding="utf-8") as fh:
        spec = json.load(fh)["by_address"]
    by_addr = {int(k, 16): v["en"] for k, v in spec.items()}
    # Debugging switches: ONLY=<addr,...> translates just those strings;
    # SKIP_AREA=<i,...> leaves those string areas untouched.
    skip = os.environ.get("SKIP_AREA")
    only = os.environ.get("ONLY")
    if only:
        keep = {int(x, 16) for x in only.split(",")}
        by_addr = {k: v for k, v in by_addr.items() if k in keep}
    for idx in filter(None, (skip or "").split(",")):
        a0, b0 = cfg["areas"][int(idx)]
        by_addr = {k: v for k, v in by_addr.items() if not BASE + a0 <= k < BASE + b0}
    new, used = nsn2menu.rebuild_pool(raw, BASE, [slots], lambda t: None, areas, pin_untranslated=True,
                                      by_address=by_addr)
    if cfg["compressed"]:
        blob = nsn2lz.compress_exact(bytes(new), size)
        assert nsn2lz.decompress(blob)[0] == bytes(new)
    else:
        blob = bytes(new)
    with open(target, "r+b") as f:
        for k in range(nsec):
            f.seek((lba + k) * 2352 + 24)
            f.write(blob[k * 2048:(k + 1) * 2048])
    for a, c, b in used:
        print("area %#06x-%#06x: %d/%d bytes" % (a, b, c - a, b - a))
    print("%s: %d slots, %d translated" % (cfg["file"], len(slots), len(by_addr)))


if __name__ == "__main__":
    main(*sys.argv[1:4])
