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
    literals until the stream is long enough."""
    assert len(raw) % 2 == 0 and target_size % 2 == 0
    words, items = _items(raw)

    def size(its):
        return 2 * (sum(len(it[1]) for it in its) + 2 + (len(its) + 1 + 15) // 16)

    if size(items) > target_size:
        raise ValueError("does not fit: %d > %d" % (size(items), target_size))
    # Expand references (from the end, so earlier refs stay valid) into literals.
    k = len(items) - 1
    while size(items) < target_size and k >= 0:
        it = items[k]
        if it[0]:
            lits = [[False, [words[it[3] + j]], 1, it[3] + j] for j in range(it[2])]
            trial = items[:k] + lits + items[k + 1:]
            if size(trial) <= target_size:
                items = trial
            else:
                # Split one word off this reference at a time.
                while size(items) < target_size and items[k][0] and items[k][2] > 2:
                    ref = items[k]
                    ln = ref[2] - 1
                    dist = ref[1][0] & 0x7FF
                    shorter = [True, [(ln << 11) | dist], ln, ref[3]]
                    lit = [False, [words[ref[3] + ln]], 1, ref[3] + ln]
                    trial = items[:k] + [shorter, lit] + items[k + 1:]
                    if size(trial) > target_size:
                        break
                    items = trial
        k -= 1
    out = _serialize(items)
    if len(out) != target_size:
        raise ValueError("could not hit exact size: %d vs %d" % (len(out), target_size))
    return out
