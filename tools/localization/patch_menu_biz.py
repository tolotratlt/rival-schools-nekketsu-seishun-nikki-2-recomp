"""Apply the English MODE SELECT textures to /DAT2/MENU.BIZ inside a disc image.

The textures come from prepare_mode_select_images.py: each TIM's packed 4 bpp
pixels (a .4bpp file) replace the stock pixels at the offset given by its
manifest.json; TIM headers and CLUTs are untouched. The stream is recompressed
to the exact stock size and written back to the same sectors.

Usage: python patch_menu_biz.py <stock.bin> <target.bin> [<images dir>]
  <images dir> defaults to localization/work/textures/mode_select/en_v1
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nsn2lz  # noqa: E402
from patch_newopt import iso_files  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
FILE = "/DAT2/MENU.BIZ"
IMAGES = os.path.join(REPO, "localization", "work", "textures", "mode_select", "en_v1")


def main(stock, target, images=IMAGES):
    with open(stock, "rb") as f:
        files, sector = iso_files(f)
        _, lba, size = [x for x in files if x[0] == FILE][0]
        nsec = (size + 2047) // 2048
        comp = b"".join(sector(lba + k) for k in range(nsec))[:size]
    raw, _ = nsn2lz.decompress(comp)
    with open(os.path.join(images, "manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    if hashlib.sha256(raw).hexdigest() != manifest["source_sha256"]:
        raise SystemExit("MENU.BIZ does not match the source the images were made from")
    new = bytearray(raw)
    for img in manifest["images"]:
        with open(os.path.join(images, img["pixels"]), "rb") as fh:
            px = fh.read()
        if len(px) != img["bytes"] or hashlib.sha256(px).hexdigest() != img["payload_sha256"]:
            raise SystemExit("bad pixel payload for TIM #%d" % img["tim"])
        o = img["pixel_offset"]
        new[o:o + len(px)] = px
    if hashlib.sha256(new).hexdigest() != manifest["edited_raw_sha256"]:
        raise SystemExit("edited MENU.BIZ differs from the manifest")
    packed = nsn2lz.compress_exact(bytes(new), size)
    assert nsn2lz.decompress(packed)[0] == bytes(new)
    with open(target, "r+b") as f:
        for k in range(nsec):
            f.seek((lba + k) * 2352 + 24)
            f.write(packed[k * 2048:(k + 1) * 2048])
    print("patched %s: %d TIMs, %d bytes at LBA %d" % (FILE, len(manifest["images"]), size, lba))


if __name__ == "__main__":
    main(*sys.argv[1:4])
