"""Render MODE SELECT image replacements without modifying a disc or TIM header.

Requires the local MENU_BIZ.dec extraction, Windows Tahoma and Pillow.
Run with the gameport Python environment. Outputs contain game data and must
remain under the ignored localization/work directory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import nsn2lz
import psxtim


REPO = Path(__file__).resolve().parents[2]
# Texture coordinates, not screen coordinates. Existing GP0 captures confirm
# the selected-label slots for entries 0, 1, 3, 5, 9, 10, 11, 12 and 13.
# The remaining slots follow the visible source atlas boundaries.
LARGE = [
    (304, 48, 112, 32), (304, 80, 112, 32), (416, 48, 64, 32),
    (416, 144, 96, 32), (416, 176, 96, 32), (304, 176, 112, 32),
    (680, 136, 88, 32), (304, 112, 112, 32), (304, 144, 112, 32),
    (680, 168, 88, 32), (568, 136, 112, 32), (424, 112, 80, 32),
    (416, 80, 64, 32), (568, 168, 112, 32),
]
SMALL = [(888, 64 + i * 24, 104, 24) for i in range(8)] + [
    (1024, i * 24, 96, 24) for i in range(6)
]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pixels(raw, tim):
    _, _, words, height, offset = tim["image"]
    data = raw[offset:offset + words * height * 2]
    return bytes(n for b in data for n in (b & 15, b >> 4))


def palette(raw, clut):
    x, y = (clut & 63) * 16, clut >> 6
    # TIM #2 CLUT is 512 words wide, two rows, beginning at VRAM (0,482).
    offset = psxtim.scan(raw)[2]["clut"][4] + ((y - 482) * 512 + x) * 2
    return [psxtim._rgb(c) for c in struct.unpack_from("<16H", raw, offset)]


def indexed(data, size, colors):
    im = Image.frombytes("P", size, data)
    im.putpalette([c for rgba in colors for c in rgba[:3]] + [0] * (768 - 48))
    im.info["transparency"] = bytes(rgba[3] for rgba in colors)
    return im


def pack(im):
    data = im.tobytes()
    if im.mode != "P" or max(data) > 15 or len(data) % 2:
        raise ValueError("Expected an even number of 4-bit palette indices")
    return bytes(data[i] | (data[i + 1] << 4) for i in range(0, len(data), 2))


def draw_label(im, rect, text, font, fill, outline, align="center"):
    x, y, w, h = rect
    bbox = font.getbbox(text)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    if tw + 8 > w or th + 4 > h:
        raise ValueError("Text does not fit comfortably: %r in %s" % (text, rect))
    mask = Image.new("1", (w, h))
    dx = (w - tw) // 2 if align == "center" else 4
    ImageDraw.Draw(mask).text((dx - bbox[0], (h - th) // 2 - bbox[1]), text,
                              font=font, fill=1)
    im.paste(0, (x, y, x + w, y + h))
    if outline is not None:
        border = mask.convert("L").filter(ImageFilter.MaxFilter(3))
        im.paste(outline, (x, y), border)
    im.paste(fill, (x, y), mask)


def preview(im, colors, background):
    view = indexed(im.tobytes(), im.size, colors).convert("RGBA")
    result = Image.new("RGBA", im.size, background)
    result.alpha_composite(view)
    return result.convert("RGB")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path,
                        default=REPO / "localization/work/menu/MENU_BIZ.dec")
    parser.add_argument("--out", type=Path,
                        default=REPO / "localization/work/textures/mode_select/en_v1")
    parser.add_argument("--font-dir", type=Path, default=Path("C:/Windows/Fonts"))
    args = parser.parse_args()
    work = (REPO / "localization/work").resolve()
    out = args.out.resolve()
    if not out.is_relative_to(work):
        parser.error("Output must remain in localization/work")
    if out.exists() and any(out.iterdir()):
        parser.error("Output directory is not empty; choose a new version")
    raw = args.source.read_bytes()
    tims = psxtim.scan(raw)
    if len(tims) != 45 or len(raw) != 653312:
        raise ValueError("Unexpected MENU.BIZ extraction")
    if (tims[2]["image"][:4] != (512, 256, 320, 256) or
            tims[2]["bpp"] != 4 or tims[2]["clut"][:4] != (0, 482, 512, 2)):
        raise ValueError("Unexpected label TIM geometry or CLUT")
    spec = json.loads((REPO / "localization/en/menus.json").read_text("utf-8"))
    spec = spec["screens"]["MODE_SELECT"]
    fonts = {n: ImageFont.truetype(str(args.font_dir / "tahomabd.ttf"), n)
             for n in (11, 12, 13)}
    bodyfont = ImageFont.truetype(str(args.font_dir / "tahoma.ttf"), 12)
    original = pixels(raw, tims[2])
    labels = indexed(original, (1280, 256), palette(raw, 0x7880))
    allowed = Image.new("1", labels.size)
    regions = []
    for i, entry in enumerate(spec["labels"]["items"][:14]):
        for variant, rect, font, fill, stroke in (
                ("large", LARGE[i], fonts[13], 1, 5),
                ("small", SMALL[i], fonts[11], 12, 7)):
            text = entry["en"]
            bounds = font.getbbox(text)
            if bounds[2] - bounds[0] + 8 > rect[2]:
                text = entry.get("fallback", text)
            draw_label(labels, rect, text, font, fill, stroke)
            x, y, w, h = rect
            allowed.paste(1, (x, y, x + w, y + h))
            regions.append(dict(variant=variant, entry=i, text=text, rect=rect))
    points = (536, 224, 96, 20)
    draw_label(labels, points, spec["labels"]["items"][14]["en"], fonts[12], 1, 3)
    allowed.paste(1, (536, 224, 632, 244))
    regions.append(dict(variant="points", text="Points", rect=points))
    if any(a != b and not permitted for a, b, permitted in
           zip(original, labels.tobytes(), allowed.convert("L").tobytes())):
        raise ValueError("A pixel outside the permitted labels changed")
    images = {2: labels}
    layouts = {}
    for entry in spec["descriptions"]["items"]:
        i = entry["tim"]
        if tims[i]["image"][:4] != (832, 256, 44, 112) or tims[i]["bpp"] != 4:
            raise ValueError("Unexpected description TIM geometry")
        im = indexed(bytes(176 * 112), (176, 112), palette(raw, 0x7888))
        lines = entry["en"].splitlines()
        step = 18
        top = (112 - len(lines) * step) // 2
        for row, text in enumerate(lines):
            # Captured description quads sample only the first 166 columns.
            draw_label(im, (0, top + row * step, 166, step), text,
                       bodyfont, 1, None, align="left")
        images[i] = im
        layouts[str(i)] = dict(text=entry["en"], line_step=step, top=top,
                               visible_width=166, font="Tahoma 12")
    modified = bytearray(raw)
    permitted_bytes = bytearray(len(raw))
    entries = []
    out.mkdir(parents=True, exist_ok=True)
    for i, im in sorted(images.items()):
        t = tims[i]
        offset = t["image"][4]
        payload = pack(im)
        if len(payload) != t["image"][2] * t["image"][3] * 2:
            raise ValueError("Pixel payload length changed")
        name = "MENU_BIZ_%02d" % i
        png_path = out / (name + ".png")
        im.save(png_path, bits=4)
        reread = Image.open(png_path)
        if (reread.mode != "P" or reread.size != im.size or
                reread.tobytes() != im.tobytes() or
                reread.getpalette()[:48] != im.getpalette()[:48] or
                reread.convert("RGBA").tobytes() != im.convert("RGBA").tobytes()):
            raise ValueError("PNG round-trip changed indices or palette")
        # PNG IHDR bit-depth byte: exact 4-bit indexed PNG, not just <=16 colors.
        if png_path.read_bytes()[24:26] != bytes((4, 3)):
            raise ValueError("PNG must use indexed color and four bits")
        (out / (name + ".4bpp")).write_bytes(payload)
        modified[offset:offset + len(payload)] = payload
        permitted_bytes[offset:offset + len(payload)] = bytes([1]) * len(payload)
        entries.append(dict(tim=i, png=png_path.name, pixels=name + ".4bpp",
                            size_px=im.size, bpp=4, pixel_offset=offset,
                            vram=t["image"][:2], bytes=len(payload),
                            payload_sha256=digest(payload)))
    if any(a != b and not allowed for a, b, allowed in
           zip(raw, modified, permitted_bytes)):
        raise ValueError("TIM header, CLUT or unrelated data changed")
    compressed = nsn2lz.compress_exact(bytes(modified), 383296)
    if len(compressed) != 383296 or nsn2lz.decompress(compressed)[0] != bytes(modified):
        raise ValueError("Exact-size compression round-trip failed")
    report = dict(source_sha256=digest(raw), source_bytes=len(raw),
                  edited_raw_sha256=digest(modified), font="Tahoma Bold 11/13; Tahoma 12",
                  description_preview_clut="0x7888 from original TIM #2",
                  label_preview_cluts=["0x7881", "0x789b"], images=entries,
                  regions=regions, descriptions=layouts,
                  validation=dict(png_indices_roundtrip=True, png_4bit=True,
                                  palette_unchanged=True, headers_unchanged=True,
                                  unrelated_pixels_unchanged=True,
                                  compressed_bytes=len(compressed),
                                  compression_roundtrip=True, tested_in_game=False),
                  note="Images only. Disc and original extraction were not modified.")
    (out / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    # Preview enlargements are separate from the native-sized replacement assets.
    sheet = Image.new("RGB", (640, 14 * 40), (32, 32, 32))
    d = ImageDraw.Draw(sheet)
    for i, entry in enumerate(spec["labels"]["items"][:14]):
        d.text((8, i * 40 + 12), "%02d %s" % (i, entry["en"]), font=fonts[12], fill="white")
        for rect, colors, x0 in ((SMALL[i], palette(raw, 0x7881), 230),
                                  (LARGE[i], palette(raw, 0x789b), 420)):
            x, y, w, h = rect
            tile = labels.crop((x, y, x + w, y + h))
            sheet.paste(preview(tile, colors, (232, 240, 208)), (x0, i * 40 + 4))
    sheet.save(out / "labels_preview.png")
    sheet = Image.new("RGB", (4 * 352, 4 * 244), (32, 32, 32))
    d = ImageDraw.Draw(sheet)
    for k, i in enumerate(range(3, 17)):
        x, y = (k % 4) * 352, (k // 4) * 244
        d.text((x + 4, y + 2), "TIM %02d" % i, font=fonts[12], fill="white")
        tile = preview(images[i], palette(raw, 0x7888), (255, 240, 104))
        sheet.paste(tile.resize((352, 224), Image.Resampling.NEAREST), (x, y + 20))
    sheet.save(out / "descriptions_preview_2x.png")
    print("Prepared %d indexed textures in %s" % (len(entries), out))
    print("Exact-size compression verified: %d bytes" % len(compressed))


if __name__ == "__main__":
    main()
