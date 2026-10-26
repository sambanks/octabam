#!/usr/bin/env python3
"""Read EXTPROBE's report out of a capture of the track's audio.

    python3 modules/extprobe/decode.py CAPTURE.raw|CAPTURE.wav [--channels L R] [--invert]

The frames are those of DLPROBE (modules/dlprobe/decode.py: 32 bits per 16-sample frame, only the sign read);
a cycle is 23 frames (layout at the head of extprobe.asm). Prints the last complete cycle: the state, the
generation, the pass count, and the highest word of the slot that no longer matches the pattern, with a
histogram of the 1,024-word buckets.
"""
import argparse
import pathlib
import struct
import sys

CYCLE = 23
MAGIC = 0xE57A01
BASE = 0x34000


def _bits(samples, invert):
    return [(1 if (s > 0) != invert else 0) for s in samples]


def decode_frames(L, R, invert=False):
    """-> (phase, [(i, value)]): the phase where most frames carry a type 0xc0 + i that follows the last."""
    n = min(len(L), len(R))
    best = (-1, 0)
    for ph in range(16):
        hits, prev = 0, None
        for f in range((n - ph) // 16):
            base = ph + 16 * f
            rw = sum(b << i for i, b in enumerate(_bits(R[base: base + 16], invert)))
            t = (rw >> 8) & 0xFF
            ok = 0xC0 <= t < 0xC0 + CYCLE
            if ok and (prev is None or t == prev + 1 or (prev == 0xC0 + CYCLE - 1 and t == 0xC0)):
                hits += 1
            prev = t if ok else None
        if hits > best[0]:
            best = (hits, ph)
    ph = best[1]
    out = []
    for f in range((n - ph) // 16):
        base = ph + 16 * f
        lw = sum(b << i for i, b in enumerate(_bits(L[base: base + 16], invert)))
        rw = sum(b << i for i, b in enumerate(_bits(R[base: base + 16], invert)))
        t = (rw >> 8) & 0xFF
        if 0xC0 <= t < 0xC0 + CYCLE:
            out.append((t - 0xC0, ((rw & 0xFF) << 16) | lw))
    return ph, out


def last_cycle(frames):
    for end in range(len(frames), CYCLE - 1, -1):
        run = frames[end - CYCLE:end]
        if [i for i, _ in run] == list(range(CYCLE)) and run[0][1] == MAGIC:
            return {i: v for i, v in run}
    return None


STATES = {0: "off", 1: "filling", 2: "scanning"}


def report(c):
    lines = [f"state {STATES.get(c[1], c[1])}, generation {c[2]}, cursor {c[3]}, passes {c[4]}",
             f"highest word that is not the pattern: offset {c[5]:#x} (P/X/Y {BASE + c[5]:#x}); "
             f"{c[6]} such words in the last full pass"]
    for b in range(16):
        n = c[7 + b]
        lines.append(f"  {b * 1024:#06x}..{b * 1024 + 1023:#06x}  {n:5d}  " + "#" * min(60, n // 40 + (1 if n else 0)))
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("capture")
    ap.add_argument("--channels", type=int, nargs=2, default=[0, 1])
    ap.add_argument("--invert", action="store_true")
    a = ap.parse_args()
    path = pathlib.Path(a.capture)
    if path.suffix.lower() == ".wav":
        import soundfile
        data, _ = soundfile.read(str(path), dtype="float32", always_2d=True)
        L, R = list(data[:, a.channels[0]]), list(data[:, a.channels[1]])
    elif path.suffix.lower() == ".npy":
        import numpy
        data = numpy.load(str(path))
        L, R = list(data[:, a.channels[0]]), list(data[:, a.channels[1]])
    else:
        raw = path.read_bytes()
        v = struct.unpack(f"<{len(raw) // 4}i", raw[: len(raw) // 4 * 4])
        L, R = list(v[0::2]), list(v[1::2])
    ph, frames = decode_frames(L, R, a.invert)
    cyc = last_cycle(frames)
    print(f"phase {ph}, {len(frames)} frames")
    if cyc is None:
        print("no complete cycle (is EXTPROBE on this track?)")
        return 1
    print("\n".join(report(cyc)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
