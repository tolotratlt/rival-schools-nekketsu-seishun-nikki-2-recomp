"""Apply localization/en/labels.json: redraw pre-drawn label rectangles of a
TIM in place inside a disc image.

For each compressed file, the TIM whose VRAM origin matches "tim" gets every
"rect" ([x, y, w, h] in 4 bpp texels from the TIM origin) cleared and the
English drawn centred in it with the plain anti-aliased style (index 0
transparent, 3..14 rising with coverage). A label with "pieces" is instead
rendered once in the outlined style (pausefont.render) and cut into the
listed sprite rectangles ([x, y, w, h, x in the text]). Sizes never change,
so the code that draws the label needs no edit. The file is recompressed to
its stock size.

Usage: python patch_labels.py <stock.bin> <target.bin>
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

REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
FONT, SIZE = r"C:\Windows\Fonts\tahomabd.ttf", 14


def main(stock, target):
    with open(os.path.join(REPO, "localization", "en", "labels.json"), encoding="utf-8") as fh:
        spec = json.load(fh)["files"]
    with open(stock, "rb") as f:
        files, sector = iso_files(f)
        data = {n: read_file(f, files, sector, n) for n in spec}
    with open(target, "r+b") as f:
        for name, entry in spec.items():
            lba, size, comp = data[name]
            raw = bytearray(nsn2lz.decompress(bytes(comp))[0])
            tim = [t for t in psxtim.scan(raw) if list(t["image"][:2]) == entry["tim"]][0]
            _, _, words, _, pix = tim["image"]
            stride = words * 2
            def put(x, y, idx):
                o = pix + y * stride + x // 2
                sh = (x & 1) * 4
                raw[o] = (raw[o] & ~(15 << sh) & 0xFF) | (idx << sh)

            for label in entry["labels"]:
                if "pieces" in label:
                    # One outlined text cut into sprites: [x, y, w, h, x in the text].
                    w, h = label["size"]
                    img = pausefont.render(label["en"], w, height=h, align="left")
                    for x0, y0, pw, ph, sx in label["pieces"]:
                        for y in range(ph):
                            for x in range(pw):
                                put(x0 + x, y0 + y, img[y][sx + x] if y < h and sx + x < w else 0)
                    continue
                x0, y0, w, h = label["rect"]
                img = pausefont.render_aa(label["en"], w, h, FONT, SIZE, align="centre")
                for y in range(h):
                    for x in range(w):
                        put(x0 + x, y0 + y, img[y][x])
            packed = nsn2lz.compress_exact(bytes(raw), size)
            assert nsn2lz.decompress(packed)[0] == bytes(raw)
            write_file(f, lba, packed)
            print("patched %s: %d labels" % (name, len(entry["labels"])))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
