"""tools/remix/pack.py: the greedy parse against the encoder's parse as first ported (the reference below, the form
of emuyia/ems-octakit's patcher/src/lib.rs), on inputs that reach every branch: no firmware."""
import pathlib
import random
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from remix import pack  # noqa: E402


def _hash3(b, i):
    key = (b[i] << 16) | (b[i + 1] << 8) | b[i + 2]
    return ((key * 2654435761) & 0xFFFFFFFF) >> (32 - pack.HASH3_BITS) & pack.HASH3_MASK


def _hash2(b, i):
    return (b[i] << 8) | b[i + 1]


def _match_length(data, cand, pos):
    offset = pos - cand
    limit = min(len(data) - pos, pack.MAX_MATCH_LEN)
    direct = min(offset, limit)
    n = 0
    while n < direct and data[cand + n] == data[pos + n]:
        n += 1
    if n == direct and n < limit:
        while n < limit and data[cand + (n % offset)] == data[pos + n]:
            n += 1
    return n


def reference_parse(data, max_candidates):
    """pack._greedy_parse until 16 Nov 2026, unchanged."""
    if not data:
        return []
    head3 = [-1] * pack.HASH3_SIZE
    head2 = [-1] * pack.HASH2_SIZE
    chain3 = [-1] * len(data)
    chain2 = [-1] * len(data)
    ops = []
    pos = 0
    n = len(data)
    while pos < n:
        best_off = best_len = 0
        if pos + 2 < n:
            cand = head3[_hash3(data, pos)]
            tried = 0
            while cand >= 0 and tried < max_candidates:
                off = pos - cand
                length = _match_length(data, cand, pos)
                minimum = 3 if off > pack.MAX_OFFSET_FOR_LEN2 else 2
                if length >= minimum and length > best_len:
                    best_off, best_len = off, length
                    if best_len == pack.MAX_MATCH_LEN:
                        break
                cand = chain3[cand]
                tried += 1
        if best_len < 2 and pos + 1 < n:
            cand = head2[_hash2(data, pos)]
            if cand >= 0 and pos - cand <= pack.MAX_OFFSET_FOR_LEN2:
                best_off, best_len = pos - cand, 2
        if best_len >= 2:
            ops.append((best_off, best_len))
            advance = best_len
        else:
            ops.append(data[pos])
            advance = 1
        end = pos + advance
        while pos < end:
            if pos + 1 < n:
                k = _hash2(data, pos); chain2[pos] = head2[k]; head2[k] = pos
            if pos + 2 < n:
                k = _hash3(data, pos); chain3[pos] = head3[k]; head3[k] = pos
            pos += 1
    return ops


def inputs():
    rnd = random.Random(1)
    for t in range(240):
        n = rnd.randrange(0, 2500)
        kind = t % 4
        if kind == 0:                     # noise: literals, hash collisions
            yield bytes(rnd.randrange(256) for _ in range(n))
        elif kind == 1:                   # three symbols: many candidates, short and long matches
            yield bytes(rnd.randrange(3) for _ in range(n))
        elif kind == 2:                   # one byte: the match overlaps its source at offset 1
            yield bytes([rnd.randrange(256)]) * n
        else:                             # a period with edits: overlapping matches that end inside the data
            base = bytes(rnd.randrange(4) for _ in range(rnd.randrange(1, 40)))
            d = bytearray((base * (n // len(base) + 1))[:n])
            for _ in range(n // 50):
                d[rnd.randrange(n)] = rnd.randrange(256)
            yield bytes(d)
    yield b""
    yield b"a"
    yield b"ab"
    yield b"abc" * 3
    # a match of MAX_MATCH_LEN and one past it; a 2-byte match beyond MAX_OFFSET_FOR_LEN2 (refused) and inside it
    yield bytes(pack.MAX_MATCH_LEN + 300)
    far = bytes(rnd.randrange(256) for _ in range(pack.MAX_OFFSET_FOR_LEN2 + 40))
    yield b"\x01\x02\x03" + far + b"\x01\x02\x09" + b"\x01\x02\x03\x04"
    yield b"\x01\x02\x03" + far[:200] + b"\x01\x02\x09"


class ParseTests(unittest.TestCase):
    def test_the_parse_is_the_reference_parse(self):
        for i, data in enumerate(inputs()):
            for candidates in (1, 4, 4096):
                self.assertEqual(pack._greedy_parse(data, candidates), reference_parse(data, candidates),
                                 f"input {i} ({len(data)} B), {candidates} candidates")


if __name__ == "__main__":
    unittest.main()
