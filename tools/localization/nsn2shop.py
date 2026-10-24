"""Shop strings (KOUBAI.BIN): 3-byte glyphs (block, col, row) over the shop
atlas (localization/shop_atlas.json); 0x80 = line break, 0x81 = end.

decode(buf, off) -> (text with '\\n', end offset after the 0x81/0x80 code)
encode(text) -> bytes ('\\n' -> 0x80, terminated by 0x81)
"""
import json
import os

_ATLAS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "..", "..", "localization", "shop_atlas.json")
with open(_ATLAS, encoding="utf-8") as _fh:
    _BLOCKS = json.load(_fh)["blocks"]

CODE2CH, CH2CODE = {}, {}
for _b, _rows in enumerate(_BLOCKS):
    for _r, _row in enumerate(_rows):
        for _c, _ch in enumerate(_row):
            CODE2CH[(_b, _c, _r)] = _ch
            CH2CODE.setdefault(_ch, (_b, _c, _r))
LINE, END = 0x80, 0x81
_ALIASES = {":": "：", "-": "ー", ",": "、"}


def decode(buf, off):
    out = []
    while off < len(buf):
        b = buf[off]
        if b == LINE:
            out.append("\n")
            off += 1
            continue
        if b & 0x80:
            return "".join(out), off + 1, b
        c, r = buf[off + 1], buf[off + 2]
        out.append(CODE2CH.get((b, c, r), "{%d,%d,%d}" % (b, c, r)))
        off += 3
    return "".join(out), off, None


def encode(text, space=None):
    """`space` is the (block, col, row) cell drawn for ' ' (an empty cell)."""
    out = bytearray()
    for ch in text:
        if ch == "\n":
            out.append(LINE)
            continue
        if ch == " ":
            out += bytes(space)
            continue
        ch = _ALIASES.get(ch, ch)
        if ch not in CH2CODE:
            raise ValueError("no shop glyph for %r" % ch)
        out += bytes(CH2CODE[ch])
    out.append(END)
    return bytes(out)
