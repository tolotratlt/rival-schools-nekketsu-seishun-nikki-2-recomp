"""NSN2 16-bit-word LZ codec, reimplemented from FUN_80015EAC (SLPS_021.20).

Stream of u16 little-endian words:
  flag word F, then 16 items, MSB of F first:
    bit 0 -> literal: next word copied to output
    bit 1 -> W = next word; length = W >> 11, distance = W & 0x7FF (in words)
             if length == 0: length = next word
             if length == 0 and distance == 0: end of stream
             copy `length` words from (output - distance)
"""
import struct


def decompress(data, start=0, limit=None):
    """Return (words_out_bytes, end_offset). Stops at the end marker or `limit`."""
    end = len(data) if limit is None else min(len(data), limit)
    i = start
    out = []

    def rd():
        nonlocal i
        w = struct.unpack_from("<H", data, i)[0]
        i += 2
        return w

    while i + 2 <= end:
        flags = rd()
        for _ in range(16):
            if i + 2 > end:
                break
            if not (flags & 0x8000):
                out.append(rd())
            else:
                w = rd()
                length, dist = w >> 11, w & 0x7FF
                if length == 0:
                    length = rd()
                    if length == 0 and dist == 0:
                        return struct.pack("<%dH" % len(out), *out), i
                src = len(out) - dist
                if src < 0:
                    raise ValueError("bad back-reference at 0x%x" % (i - 2))
                for k in range(length):
                    out.append(out[src + k])
            flags = (flags << 1) & 0xFFFF
    return struct.pack("<%dH" % len(out), *out), i


def compress(raw, window=0x7FF, max_len=31):
    """Greedy encoder producing a stream the game's decoder accepts.

    `raw` must have an even length. Ends with the explicit end marker.
    Only one-word references (length <= 31) are emitted, so a 16-item group is
    at most 34 bytes: below the 0x40-byte look-ahead the streaming driver
    (FUN_80015D04) mirrors at the 0x801F9000 ring wrap.
    """
    assert len(raw) % 2 == 0
    words = list(struct.unpack("<%dH" % (len(raw) // 2), raw))
    n = len(words)
    items = []  # each item: list of words; bool flag
    pos = 0
    # index of word positions for faster match search
    table = {}
    while pos < n:
        best_len, best_dist = 0, 0
        key = tuple(words[pos:pos + 2])
        for cand in reversed(table.get(key, [])):
            dist = pos - cand
            if dist > window:
                break
            ln = 0
            while pos + ln < n and words[cand + ln] == words[pos + ln] and ln < max_len:
                ln += 1
            if ln > best_len:
                best_len, best_dist = ln, dist
                if ln == max_len:
                    break
        if best_len >= 2:
            items.append((True, [(best_len << 11) | best_dist]))
            step = best_len
        else:
            items.append((False, [words[pos]]))
            step = 1
        for p in range(pos, pos + step):
            if p + 1 < n:
                table.setdefault((words[p], words[p + 1]), []).append(p)
        pos += step
    items.append((True, [0, 0]))  # end marker: W=0 (len 0, dist 0) then length word 0
    out = []
    for g in range(0, len(items), 16):
        group = items[g:g + 16]
        flags = 0
        for k, (is_ref, _) in enumerate(group):
            if is_ref:
                flags |= 0x8000 >> k
        out.append(flags)
        for _, ws in group:
            out.extend(ws)
    return struct.pack("<%dH" % len(out), *out)


def _items(raw, window=0x7FF, max_len=31):
    """Greedy parse into (is_ref, words) items, without the end marker."""
    words = list(struct.unpack("<%dH" % (len(raw) // 2), raw))
    n = len(words)
    items, table, pos = [], {}, 0
    while pos < n:
        best_len, best_dist = 0, 0
        for cand in reversed(table.get(tuple(words[pos:pos + 2]), [])):
            dist = pos - cand
            if dist > window:
                break
            ln = 0
            while pos + ln < n and words[cand + ln] == words[pos + ln] and ln < max_len:
                ln += 1
            if ln > best_len:
                best_len, best_dist = ln, dist
                if ln == max_len:
                    break
        if best_len >= 2:
            items.append([True, [(best_len << 11) | best_dist], best_len, pos])
            step = best_len
        else:
            items.append([False, [words[pos]], 1, pos])
            step = 1
        for p in range(pos, pos + step):
            if p + 1 < n:
                table.setdefault((words[p], words[p + 1]), []).append(p)
        pos += step
    return words, items


def _serialize(items):
    allitems = items + [[True, [0, 0], 0, -1]]
    out = []
    for g in range(0, len(allitems), 16):
        group = allitems[g:g + 16]
        flags = 0
        for k, it in enumerate(group):
            if it[0]:
                flags |= 0x8000 >> k
        out.append(flags)
        for it in group:
            out.extend(it[1])
    return struct.pack("<%dH" % len(out), *out)


def compress_exact(raw, target_size):
    """Encode `raw` into exactly `target_size` bytes (the stock file size), with
    the end marker in the final bytes, by turning references back into
    literals (from the end of the stream) until the stream is long enough.
    Sizes are tracked incrementally, so this stays linear on large files."""
    assert len(raw) % 2 == 0 and target_size % 2 == 0
    words, items = _items(raw)
    target_words = target_size // 2

    def total(nwords, nitems):
        # data words + end marker (2 words) + one flag word per 16 items
        return nwords + 2 + (nitems + 1 + 15) // 16

    nwords = sum(len(it[1]) for it in items)
    nitems = len(items)
    if total(nwords, nitems) > target_words:
        raise ValueError("does not fit: %d > %d bytes"
                         % (2 * total(nwords, nitems), target_size))
    split = {}  # item index -> number of trailing words turned into literals
    k = len(items) - 1
    while total(nwords, nitems) < target_words and k >= 0:
        it = items[k]
        if it[0]:
            length = it[2]
            # Full expansion: the ref word becomes `length` literals.
            if total(nwords + length - 1, nitems + length - 1) <= target_words:
                split[k] = length
                nwords += length - 1
                nitems += length - 1
            else:
                # Peel literals off the end, keeping a reference of length >= 2.
                j = 0
                while (length - j - 1 >= 2 and
                       total(nwords + 1, nitems + 1) <= target_words):
                    j += 1
                    nwords += 1
                    nitems += 1
                if j:
                    split[k] = j
        k -= 1
    if total(nwords, nitems) != target_words:
        raise ValueError("could not hit exact size: %d vs %d"
                         % (2 * total(nwords, nitems), target_size))
    out_items = []
    for idx, it in enumerate(items):
        j = split.get(idx, 0)
        if not j:
            out_items.append(it)
            continue
        length, dist, pos = it[2], it[1][0] & 0x7FF, it[3]
        keep = length - j
        if keep:
            out_items.append([True, [(keep << 11) | dist], keep, pos])
        for q in range(keep, length):
            out_items.append([False, [words[pos + q]], 1, pos + q])
    out = _serialize(out_items)
    if len(out) != target_size:
        raise ValueError("size bookkeeping mismatch: %d vs %d" % (len(out), target_size))
    return out
