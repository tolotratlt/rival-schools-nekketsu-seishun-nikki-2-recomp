"""Parse and rebuild the dialogue script block of a decompressed NSN2 scene file.

Layout observed in /DAT2/MGK04.BIZ (decompressed, loaded at 0x800D0000):

    0x31000  master table: one u32 pointer per group, then 0x00000000
    0x31020  group 0 messages (u16 glyph codes, each ends with 0x3001)
             group 0 table: one u32 pointer per message, then 0xFFFFFFFF
             group 1 messages ... group 1 table ... (and so on)
             zero padding up to the next block

Every message is referenced individually, so messages may change length as
long as all pointers are rebuilt. All pointers are absolute RAM addresses.
"""
import struct

LOAD_ADDR = 0x800D0000


def u32(buf, off):
    return struct.unpack_from("<I", buf, off)[0]


def parse(raw, script_off, load_addr=LOAD_ADDR):
    """Return {"groups": [[message_words, ...], ...], "end": offset after the
    last table, "limit": offset of the next non-zero byte}."""
    master = []
    o = script_off
    while True:
        p = u32(raw, o)
        o += 4
        if p == 0:
            break
        master.append(p - load_addr)
    first_msg = o
    groups = []
    cursor = first_msg
    for tab in master:
        # Messages run from `cursor` up to the group table; the table has one
        # entry per message, and every entry must point inside that span.
        ptrs = []
        t = tab
        while True:
            p = u32(raw, t)
            if not (load_addr + cursor <= p < load_addr + tab):
                break
            ptrs.append(p - load_addr)
            t += 4
        if not ptrs or ptrs[0] != cursor:
            raise ValueError("group table 0x%x does not start at 0x%x" % (tab, cursor))
        if ptrs != sorted(ptrs):
            raise ValueError("group table 0x%x is not in ascending order" % tab)
        bounds = ptrs + [tab]
        msgs = []
        for a, b in zip(bounds, bounds[1:]):
            if (b - a) % 2:
                raise ValueError("odd message length at 0x%x" % a)
            msgs.append(list(struct.unpack_from("<%dH" % ((b - a) // 2), raw, a)))
        groups.append(msgs)
        if u32(raw, t) != 0xFFFFFFFF:
            raise ValueError("group table 0x%x is not closed by 0xFFFFFFFF" % tab)
        cursor = t + 4
    end = cursor
    limit = end
    while limit < len(raw) and raw[limit] == 0:
        limit += 1
    return {"groups": groups, "start": script_off, "end": end, "limit": limit}


def build(groups, script_off, load_addr=LOAD_ADDR):
    """Serialize groups into script bytes laid out like the original."""
    out = bytearray(4 * (len(groups) + 1))  # master table, filled in at the end
    master = []
    for msgs in groups:
        ptrs = []
        for words in msgs:
            ptrs.append(load_addr + script_off + len(out))
            out += struct.pack("<%dH" % len(words), *words)
            if len(out) % 4:
                # Every stock message starts 4-byte aligned; the pad word is
                # read back by parse() as the tail of this message.
                out += b"\x00\x00"
        master.append(load_addr + script_off + len(out))
        out += struct.pack("<%dI" % (len(ptrs) + 1), *(ptrs + [0xFFFFFFFF]))
    struct.pack_into("<%dI" % (len(master) + 1), out, 0, *(master + [0]))
    return bytes(out)


def replace(raw, script_off, groups, load_addr=LOAD_ADDR):
    """Return `raw` with the script block rebuilt from `groups`; the rest of
    the file is untouched. Raises if the new block does not fit its slot."""
    info = parse(raw, script_off, load_addr)
    blob = build(groups, script_off, load_addr)
    if script_off + len(blob) > info["limit"]:
        raise ValueError("script block too large: %d bytes, slot %d"
                         % (len(blob), info["limit"] - script_off))
    out = bytearray(raw)
    out[script_off:info["limit"]] = blob + b"\x00" * (info["limit"] - script_off - len(blob))
    return bytes(out)
