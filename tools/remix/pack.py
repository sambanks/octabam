"""The packer for the platform loader's payloads: the firmware's own aPLib
variant (GKA3), ported from Em's Octakit encoder (emuyia/ems-octakit,
patcher/src/lib.rs), deterministic and memoised. Moved here from
runtime_build.py when Octakit was removed (6 Oct 2026); the bytes it
produces are unchanged.
"""

from __future__ import annotations

import hashlib
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]

# The build's memo. Every entry is keyed by the sha256 of its COMPLETE input
# (the bytes handed to the packer) and holds the stream the packer's own
# determinism pins, so a hit is what a cold run would have produced. A
# build that cannot write here builds cold. OCTABAM_NO_CACHE=1 builds cold;
# OCTABAM_CACHE=<dir> names the directory (check_shards.py hands its
# worktrees the parent's). (28 Sep 2026: the packer was 55% of every build;
# a warm build is 1.7 s where a cold one was 9.) The memo holds packed
# firmware, so CI does not carry it between runs (ci.yml: the bytes are not
# cached); a runner's build is always cold.
CACHE = pathlib.Path(os.environ.get("OCTABAM_CACHE") or ROOT / "out/cache")


def _cache_on():
    return os.environ.get("OCTABAM_NO_CACHE", "") not in ("1", "yes", "true")


def _cache_read(kind, key):
    if not _cache_on():
        return None
    p = CACHE / kind / key
    try:
        return p.read_bytes() if p.is_file() else None
    except OSError:
        return None


def _cache_write(kind, key, data):
    if not _cache_on():
        return
    try:
        d = CACHE / kind
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / f"{key}.{os.getpid()}.tmp"
        tmp.write_bytes(data)
        tmp.replace(d / key)
    except OSError:
        pass

# ---- the firmware's aPLib variant, ported from Em's encoder ---------------
# (emuyia/ems-octakit patcher/src/lib.rs), bit-identical to it
MAX_OFFSET_FOR_LEN2 = 0x0D00
MAX_MATCH_LEN = 0x8000
HASH3_BITS = 20
HASH3_SIZE = 1 << HASH3_BITS
HASH3_MASK = HASH3_SIZE - 1
HASH2_SIZE = 1 << 16
PACKED_MAGIC = b"GKA3"


# The greedy parse is the encoder's, in the form that is fast in pure Python (16 Nov 2026): on octabam the build
# packs its 812 KB runtime four times and the DSP tail once, and the parse as first ported (a call and a byte loop
# per candidate, 13.1 million calls) was about 100 s of a 119 s cold build -- in every CI job that builds an image.
# The same inputs now parse in 1.4-1.8 s each. The stream is unchanged: tools/verify/tests/test_pack.py holds the
# first port as the reference and compares the two.
def _greedy_parse(data, max_candidates):
    if not data:
        return []
    n = len(data)
    head3 = [-1] * HASH3_SIZE
    head2 = [-1] * HASH2_SIZE
    chain3 = [-1] * n
    chain2 = [-1] * n
    shift = 32 - HASH3_BITS
    ops = []
    pos = 0
    while pos < n:
        best_off = best_len = 0
        if pos + 2 < n:
            cand = head3[((((data[pos] << 16) | (data[pos + 1] << 8) | data[pos + 2]) * 2654435761) & 0xFFFFFFFF) >> shift & HASH3_MASK]
            limit = n - pos
            if limit > MAX_MATCH_LEN:
                limit = MAX_MATCH_LEN
            tried = 0
            while cand >= 0 and tried < max_candidates:
                # a candidate is taken only when its match is longer than the best so far, so it must
                # match at index best_len; one that does not is passed without measuring it
                if data[cand + best_len] == data[pos + best_len]:
                    # the match length: the common prefix of data[cand:] and data[pos:], which may overlap
                    # (the encoder's `cand + (k % offset)` reads the same bytes: k >= offset is reached only
                    # when the first `offset` bytes matched, and then data[pos + k - offset] is that byte)
                    k = 0
                    step = 16
                    while k < limit:
                        s = step if k + step <= limit else limit - k
                        if data[cand + k:cand + k + s] == data[pos + k:pos + k + s]:
                            k += s
                            if step < 4096:
                                step <<= 1
                        elif s == 1:
                            break
                        else:
                            step = s >> 1
                    if k > best_len and k >= (3 if pos - cand > MAX_OFFSET_FOR_LEN2 else 2):
                        best_off, best_len = pos - cand, k
                        if k == limit:
                            # nothing is longer than the limit. (The encoder stops here only at
                            # MAX_MATCH_LEN and tries the rest otherwise; none of them can be taken.)
                            break
                cand = chain3[cand]
                tried += 1
        if best_len < 2 and pos + 1 < n:
            cand = head2[(data[pos] << 8) | data[pos + 1]]
            if cand >= 0 and pos - cand <= MAX_OFFSET_FOR_LEN2:
                best_off, best_len = pos - cand, 2
        if best_len >= 2:
            ops.append((best_off, best_len))
            end = pos + best_len
        else:
            ops.append(data[pos])
            end = pos + 1
        while pos < end:
            if pos + 1 < n:
                k = (data[pos] << 8) | data[pos + 1]; chain2[pos] = head2[k]; head2[k] = pos
                if pos + 2 < n:
                    k = ((((data[pos] << 16) | (data[pos + 1] << 8) | data[pos + 2]) * 2654435761) & 0xFFFFFFFF) >> shift & HASH3_MASK
                    chain3[pos] = head3[k]; head3[k] = pos
            pos += 1
    return ops


def _gamma_bits(value):
    assert value >= 2
    highest = value.bit_length() - 1
    bits = []
    for i in range(highest - 1, -1, -1):
        bits.append((value >> i) & 1)
        bits.append(1 if i == 0 else 0)
    return bits


def _length_bits(length_read):
    if length_read == 1:
        return [0, 1]
    if length_read == 2:
        return [1, 0]
    if length_read == 3:
        return [1, 1]
    assert length_read > 3
    return [0, 0] + _gamma_bits(length_read - 2)


def pack(data: bytes, max_candidates: int) -> bytes:
    """Deterministic aPLib-variant stream, bit-identical to her encoder.
    Memoised on the input's sha256 (out/cache/pack): the same bytes pack to
    the same stream, and the greedy parse is pure Python."""
    key = f"{hashlib.sha256(data).hexdigest()}-{max_candidates}"
    hit = _cache_read("pack", key)
    if hit is not None and hit[:32] == hashlib.sha256(hit[32:]).digest():
        return hit[32:]
    out = _pack(data, max_candidates)
    _cache_write("pack", key, hashlib.sha256(out).digest() + out)
    return out


def _pack(data: bytes, max_candidates: int) -> bytes:
    tag_bits: list[int] = []
    emissions: list[tuple[int, int]] = []
    last_offset = None
    for op in _greedy_parse(data, max_candidates):
        if isinstance(op, int):
            tag_bits.append(1)
            emissions.append((len(tag_bits) - 1, op))
            continue
        offset, length = op
        tag_bits.append(0)
        if last_offset == offset:
            tag_bits.extend(_gamma_bits(2))
        else:
            raw = offset - 1
            tag_bits.extend(_gamma_bits((raw + 0x300) // 0x100))
            emissions.append((len(tag_bits) - 1, (raw + 0x300) % 0x100))
        tag_bits.extend(_length_bits(length - (2 if offset > MAX_OFFSET_FOR_LEN2 else 1)))
        last_offset = offset
    tag_bits.append(0)
    tag_bits.extend(_gamma_bits(0x01000002))
    emissions.append((len(tag_bits) - 1, 0xFF))
    while len(tag_bits) % 8:
        tag_bits.append(0)
    out = bytearray()
    ei = 0
    for g in range(0, len(tag_bits), 8):
        tag = 0
        for i in range(8):
            tag |= tag_bits[g + i] << (7 - i)
        out.append(tag)
        while ei < len(emissions) and emissions[ei][0] < g + 8:
            out.append(emissions[ei][1])
            ei += 1
    assert ei == len(emissions)
    return bytes(out)
