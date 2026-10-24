"""Find and decode PSX TIM images inside a byte buffer.

scan(buf) -> list of dicts {offset, bpp, clut (x, y, w, h) | None,
                            image (x, y, w_words, h), size}
to_png(buf, tim, path, clut_index=0) renders one TIM (4/8/15 bpp) to PNG.
"""
import struct

_BPP = {0: 4, 1: 8, 2: 16, 3: 24}


def _tim_at(buf, o):
    if o + 8 > len(buf) or struct.unpack_from("<I", buf, o)[0] != 0x10:
        return None
    flags = struct.unpack_from("<I", buf, o + 4)[0]
    if flags & ~0xF:
        return None
    bpp = _BPP[flags & 3]
    p = o + 8
    clut = None
    if flags & 8:
        if p + 12 > len(buf):
            return None
        ln, cx, cy, cw, ch = struct.unpack_from("<IHHHH", buf, p)
        if ln != 12 + cw * ch * 2 or not (0 < cw <= 1024 and 0 < ch <= 512):
            return None
        clut = (cx, cy, cw, ch, p + 12)
        p += ln
    if p + 12 > len(buf):
        return None
    ln, ix, iy, iw, ih = struct.unpack_from("<IHHHH", buf, p)
    if ln != 12 + iw * ih * 2 or not (0 < iw <= 1024 and 0 < ih <= 512):
        return None
    if ix >= 1024 or iy >= 512 or p + ln > len(buf):
        return None
    return {"offset": o, "bpp": bpp, "clut": clut,
            "image": (ix, iy, iw, ih, p + 12), "size": p + ln - o}


def scan(buf):
    out = []
    o = 0
    while o + 8 <= len(buf):
        t = _tim_at(buf, o)
        if t:
            out.append(t)
            o += t["size"]
            o = (o + 3) & ~3
        else:
            o += 4
    return out


def _rgb(c):
    return ((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3,
            0 if c == 0 else 255)


def to_png(buf, tim, path, clut_index=0):
    from PIL import Image
    ix, iy, iw, ih, ip = tim["image"]
    bpp = tim["bpp"]
    n = 16 if bpp == 4 else 256
    # No CLUT in the file (the game supplies one in VRAM): use a grey ramp.
    pal = [(k * 255 // (n - 1),) * 3 + (255,) for k in range(n)]
    if tim["clut"]:
        cx, cy, cw, ch, cp = tim["clut"]
        base = cp + clut_index * n * 2
        pal = [_rgb(struct.unpack_from("<H", buf, base + 2 * k)[0]) for k in range(n)]
    data = buf[ip:ip + iw * ih * 2]
    if bpp == 4:
        w = iw * 4
        px = []
        for b in data:
            px += [pal[b & 15], pal[b >> 4]]
    elif bpp == 8:
        w = iw * 2
        px = [pal[b] for b in data]
    else:
        w = iw
        px = [_rgb(struct.unpack_from("<H", data, 2 * k)[0]) for k in range(iw * ih)]
    im = Image.new("RGBA", (w, ih))
    im.putdata(px)
    im.save(path)
    return im
