"""Text <-> NSN2 glyph-code conversion for dialogue messages.

encode("Line one\\nLine two") -> [codes..., 0x3000, codes..., 0x3001]
decode(words) -> readable string; unknown codes (scene kanji, controls) are
shown as {xxxx}.
"""
import json
import os

LINE_BREAK = 0x3000
END_OF_MESSAGE = 0x3001
COLOUR = 0x3003  # followed by one argument word

_CHARMAP = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "..", "localization", "nsn2_charmap.json")

_ASCII = {" ": 0x0000, "?": 0x0042, "!": 0x004A, ".": 0x004D, ",": 0x00AA,
          "'": 0x00B5, "-": 0x00AF, ":": 0x0056, ";": 0x00AC, "&": 0x0043,
          "%": 0x0041, "#": 0x0040, "@": 0x003F, "+": 0x0045, "*": 0x0046,
          "(": 0x00B8, ")": 0x00B9, "/": 0x00B0, "~": 0x00B2, "\"": 0x00B7}


def encode_char(ch):
    if "1" <= ch <= "9":
        return 0x01 + ord(ch) - ord("1")
    if ch == "0":
        return 0x0A
    if "A" <= ch <= "Z":
        return 0x0B + ord(ch) - ord("A")
    if "a" <= ch <= "z":
        return 0x25 + ord(ch) - ord("a")
    if ch in _ASCII:
        return _ASCII[ch]
    raise ValueError("no glyph for %r" % ch)


def encode(text, end=True):
    """Encode English text; '\\n' becomes the game's line break."""
    out = []
    for line_no, line in enumerate(text.split("\n")):
        if line_no:
            out.append(LINE_BREAK)
        out.extend(encode_char(c) for c in line)
    if end:
        out.append(END_OF_MESSAGE)
    return out


def _load_charmap():
    with open(_CHARMAP, encoding="utf-8") as fh:
        codes = json.load(fh)["codes"]
    return {int(k, 16): (v if v is not None else " ") for k, v in codes.items()}


def decode(words, charmap=None):
    charmap = charmap or _load_charmap()
    names = {LINE_BREAK: "\n", END_OF_MESSAGE: "{END}"}
    out = []
    for w in words:
        if w in names:
            out.append(names[w])
        else:
            out.append(charmap.get(w, "{%04x}" % w))
    return "".join(out)
