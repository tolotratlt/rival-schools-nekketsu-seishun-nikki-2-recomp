"""Menu strings drawn from the common MENU.BIZ glyph atlas (see menu_atlas.json).

A string is u16 little-endian: [count][code] * count, with
code = block * 0x100 + row * 0x10 + col.

decode(words) / encode(text) convert between codes and text;
find_tables(buf, base) lists pointer tables that point at such strings.
"""
import json
import os
import struct

_ATLAS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "..", "..", "localization", "menu_atlas.json")


def _load():
    with open(_ATLAS, encoding="utf-8") as fh:
        blocks = json.load(fh)["blocks"]
    code2ch, ch2code = {}, {}
    for b, rows in enumerate(blocks):
        for r, row in enumerate(rows):
            for c, ch in enumerate(row):
                code = b * 0x100 + r * 0x10 + c
                code2ch[code] = ch
                ch2code.setdefault(ch, code)
    return code2ch, ch2code


CODE2CH, CH2CODE = _load()
SPACE = 0x18B  # empty cell (block 1, row 8, col 11): renders as a blank
# ASCII punctuation that has no half-width glyph maps to the closest atlas cell.
_ALIASES = {":": "：", "-": "ー", ",": "、"}


def decode(codes):
    return "".join(CODE2CH.get(c, "{%03x}" % c) for c in codes)


def encode(text):
    out = []
    for ch in text:
        if ch == " ":
            out.append(SPACE)
            continue
        ch = _ALIASES.get(ch, ch)
        if ch not in CH2CODE:
            raise ValueError("no menu glyph for %r" % ch)
        out.append(CH2CODE[ch])
    return out


def rebuild_pool(buf, base, tables, translate, areas, by_address=None):
    """Rewrite every string referenced by `tables` (lists of (offset, ptr) from
    find_tables) into `areas` [(start_off, end_off), ...] of `buf`, translated
    by `translate(japanese_text) -> text or None` (None keeps the original
    codes). Each distinct source string is written once; every pointer slot is
    updated. `by_address` {stock_ptr: text} overrides the translation of one
    particular stock string (when two identical Japanese strings need
    different English). Returns the new bytearray and a report of used bytes
    per area."""
    by_address = by_address or {}
    buf = bytearray(buf)
    src_strings = {}
    for t in tables:
        for off, ptr in t:
            src_strings.setdefault(ptr, read_string(buf, ptr - base))
    # Clear the areas first so no stale Japanese remains.
    for a, b in areas:
        buf[a:b] = b"\x00" * (b - a)
    cursor = [a for a, _ in areas]
    new_addr = {}
    by_content = {}  # identical output strings are stored once
    for ptr in sorted(src_strings):
        codes = src_strings[ptr]
        text = by_address.get(ptr) or translate(decode(codes))
        out = codes if text is None else encode(text)
        blob = struct.pack("<H%dH" % len(out), len(out), *out)
        if blob in by_content:
            new_addr[ptr] = by_content[blob]
            continue
        need = (len(blob) + 3) & ~3  # keep strings 4-byte aligned like the stock pool
        for k, (a, b) in enumerate(areas):
            if cursor[k] + need <= b:
                buf[cursor[k]:cursor[k] + len(blob)] = blob
                new_addr[ptr] = base + cursor[k]
                by_content[blob] = new_addr[ptr]
                cursor[k] += need
                break
        else:
            raise ValueError("string pool full while placing %r" % decode(codes))
    for t in tables:
        for off, ptr in t:
            struct.pack_into("<I", buf, off, new_addr[ptr])
    used = [(a, cursor[k], b) for k, (a, b) in enumerate(areas)]
    return buf, used


def read_string(buf, off):
    if off < 0 or off + 2 > len(buf):
        return None
    n = struct.unpack_from("<H", buf, off)[0]
    if not 0 < n < 64 or off + 2 + 2 * n > len(buf):
        return None
    return list(struct.unpack_from("<%dH" % n, buf, off + 2))


def plausible(codes):
    if not codes or not all(c in CODE2CH for c in codes):
        return False
    # Real menu text is mostly kana/kanji; random data decodes to Latin noise.
    japanese = sum(1 for c in codes if c >= 0x074)  # past the Latin/punctuation rows
    return japanese * 2 >= len(codes) or len(codes) <= 4 and codes[0] < 0x074


def find_tables(buf, base, min_len=3):
    """Runs of u32 pointers (into buf) whose targets decode as menu strings."""
    tables = []
    run = []
    for o in range(0, len(buf) - 3, 4):
        p = struct.unpack_from("<I", buf, o)[0]
        ok = False
        if base <= p < base + len(buf) - 2:
            s = read_string(buf, p - base)
            ok = s is not None and plausible(s)
        if ok:
            run.append((o, p))
        else:
            if len(run) >= min_len:
                tables.append(run)
            run = []
    if len(run) >= min_len:
        tables.append(run)
    return tables
