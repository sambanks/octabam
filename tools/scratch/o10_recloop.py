#!/usr/bin/env python3
"""O10: the recorder loop under the port -- what T2 plays back from R1.

  o10_recloop.py DUMP [bpm] [rlen_steps]
Extracts T2's chain input (its 84-word record audio: what the FLEX voice plays)
and prints, per sequencer step, the level and the dominant frequency (from
zero crossings; `--audio-in tones` puts 500*(k+1) Hz on RX0 slot k, so the
frequency says WHICH input pair the recorder captured), then the largest
sample-to-sample jump in each pass relative to the tone's own slope -- a seam
click shows as a jump far above the slope (Bryan's 128/RLEN4 case: PR #157's
follow-on, RTOS_FORK 10.18).
"""
import sys, math, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import blockdump as bd

def words(w):
    out = []
    for i in range(0, len(w), 2):
        v = (w[i] << 8) | (w[i + 1] >> 8); out.append(v - (1 << 24) if v >= 1 << 23 else v)
    return out

def record_audio(rec, right=False):
    """One 84-word track record -> its 16 audio samples (L, or R).
    Measured 8 Sep 2026 (O9d/O10): the record is a sequence of SEGMENTS, each
    a 4-word header (count, 0, 0x40000, tag) followed by `count` stereo pairs,
    16 pairs in all -- a THRU voice ships two empty headers then 16 pairs; a
    FLEX voice ships e.g. (15 pairs)(1 pair), (14)(2), ... the split moving one
    sample per frame with the header's first word. Parsed, not assumed: a
    wrong layout shows as a frame-periodic glitch against a fitted sine."""
    o = 1 if right else 0
    pairs = []; i = 0
    while len(pairs) < 16 and i + 4 <= len(rec):
        if rec[i + 1] == 0 and rec[i + 2] == 0x40000 and 0 <= rec[i] <= 16:
            cnt = rec[i]; i += 4
            if cnt:
                pairs += [rec[i + 2 * k + o] for k in range(cnt)]; i += 2 * cnt
            continue
        take = 16 - len(pairs)
        pairs += [rec[i + 2 * k + o] for k in range(take)]; i += 2 * take
    return pairs[:16]

def track_audio(c, track, right=False):
    core = 0 if track >= 5 else 1; pos = (track - 1) % 4
    addrs = {1: (0x80001c90, 0x80002710), 0: (0x800021d0, 0x80002c50)}[core]
    rec = sorted(sum((c.get(('>', 0, core, a), []) for a in addrs), []))
    out = []
    for _, w in rec:
        ws = words(w); out += record_audio(ws[pos * 84:(pos + 1) * 84], right)
    return out

def readback_audio(c, track, right=False):
    """The track's slot of its core's 256-halfword read-back: the per-track
    chain OUTPUT before the master mix (32 words per track, (L,R) pairs)."""
    core = 0 if track >= 5 else 1; pos = (track - 1) % 4; o = 1 if right else 0
    addrs = {1: (0x80003190, 0x80003590), 0: (0x80003390, 0x80003790)}[core]
    rb = sorted(sum((c.get(('<', 1, core, a), []) for a in addrs), []))
    out = []
    for _, w in rb:
        ws = words(w); out += ws[pos * 32 + o: pos * 32 + 32: 2]
    return out

def db(x): return 20 * math.log10(x / 8388608) if x > 0 else -200

def main():
    dump = sys.argv[1]; bpm = float(sys.argv[2]) if len(sys.argv) > 2 else 128.0
    rlen = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    step = 60.0 / bpm / 4 * 44100                     # samples per 16th step
    c = bd.classes(bd.read(dump))
    for t in (1, 2):
        x = track_audio(c, t)
        print(f"T{t}: {len(x)} samples ({len(x) / step:.1f} steps of {step:.1f})")
        rows = []
        for s in range(int(len(x) / step)):
            seg = x[int(s * step): int((s + 1) * step)]
            if not seg: continue
            rms = math.sqrt(sum(v * v for v in seg) / len(seg))
            zc = sum(1 for i in range(1, len(seg)) if (seg[i - 1] < 0) != (seg[i] < 0))
            f = zc / 2 / (len(seg) / 44100)
            rows.append((s + 1, db(rms), f))
        print("   step: level dBFS / dominant Hz  " + "  ".join(f"{s}:{l:.0f}/{f:.0f}" for s, l, f in rows))
        # seams: largest jump per RLEN-step pass, relative to the median slope of that pass
        if any(l > -60 for _, l, _ in rows):
            for p in range(int(len(x) / (step * rlen))):
                a, b = int(p * step * rlen), int((p + 1) * step * rlen)
                seg = x[a:b]
                d = [abs(seg[i] - seg[i - 1]) for i in range(1, len(seg))]
                if not d or max(seg, key=abs) == 0: continue
                med = sorted(d)[len(d) // 2] or 1
                i = max(range(len(d)), key=lambda k: d[k])
                print(f"   pass {p + 1} (samples {a}..{b}): max jump {d[i]} at +{i + 1} = {d[i] / med:.1f}x the median slope")

if __name__ == '__main__':
    main()
