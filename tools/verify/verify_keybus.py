#!/usr/bin/env python3
"""KEYBUS's tap under dsp_host: each track's block peak of |(L + R) / 2| lands at X:$37F60 + track, on both payloads.

    python3 tools/verify/verify_keybus.py [REMIX]       (default test/keybus)

The image is built and each payload's dump read. The hook at the dispatcher's per-track site (payload A P:$4a7,
payload B P:$29c) must be a `jsr` (a demand module's bridged stub where SC KEYBUS BRIDGE is in the remix, which
jumps on to the tap); the tap's address is read from it, or from the stub's last branch. The tap is then run as an
instance's proc with the input block at X:$00 (`-audio 0`, where the dispatcher leaves it) and x:$420 planted as
each track 0..7 in turn, and the eight key words are read back (`-peekx`). Checked: the track's word holds the
peak of the last block's |(L + R) / 2| (within dsp_host's input shaping, 1 %), every other word stays 0, and a
silent block publishes 0.

Not covered here: that the dispatcher reaches the site for every track (the site is stock's per-track path,
read by SIDECHAIN_COMPRESSOR's sctap on the unit), that no stock code writes X:$37F60..$37F67 (Claims.dsp_ranges
and the ledger's stock owners say none; no write watch under the port yet), and the timing between the cores.
"""
import math
import pathlib
import re
import struct
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import dlbuild  # noqa: E402
import send_probe  # noqa: E402

KEY_WORDS = 0x37F60
SITE = {"A": 0x4A7, "B": 0x29C}
HOST = "vendor/dsp56300/build/source/dsp_host/dsp_host"
FRAMES, BLOCKS = 16, 8
TMP = pathlib.Path("out/_keybus")
TMP.mkdir(parents=True, exist_ok=True)
fails = 0


def check(label, ok, detail=""):
    global fails
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")
    fails += 0 if ok else 1


def records(path):
    blob, pos, out = pathlib.Path(path).read_bytes(), 0, []
    while pos + 9 <= len(blob):
        sp, addr, cnt = struct.unpack_from("<BII", blob, pos)
        pos += 9
        if sp == 0xFF:
            break
        out.append((sp, addr, list(struct.unpack_from(f"<{cnt}I", blob, pos))))
        pos += 4 * cnt
    return out


def write_records(path, recs):
    path.write_bytes(b"".join(struct.pack("<BII", sp, a, len(w)) + struct.pack(f"<{len(w)}I", *w) for sp, a, w in recs)
                     + struct.pack("<BII", 0xFF, 0, 0))


def p_word(recs, addr):
    for sp, a, w in recs:
        if sp == 0 and a <= addr < a + len(w):
            return w[addr - a]
    return None


def tap_of(recs, tag):
    """The tap's address from the hook: `jsr >t` (0bf080 t) to the tap, or to a bridged stub whose last branch
    (its displacement in the stub's tenth word, written by the build as target - (stub + 8)) lands on it. Either
    way the address must hold the tap's first instruction, `move #0,r0` (300000)."""
    w0, w1 = p_word(recs, SITE[tag]), p_word(recs, SITE[tag] + 1)
    if w0 != 0x0BF080:
        return None, f"P:0x{SITE[tag]:05x} holds {w0:06x}, not a jsr"
    if p_word(recs, w1) == 0x300000:
        return w1, f"jsr P:0x{w1:05x}"
    disp = p_word(recs, w1 + 9)
    tap = None if disp is None else (w1 + 8 + disp) & 0xFFFFFF
    if tap is not None and p_word(recs, tap) == 0x300000:
        return tap, f"jsr to the bridged stub P:0x{w1:05x}, which branches to P:0x{tap:05x}"
    return None, f"jsr P:0x{w1:05x} reaches no tap"


def run(memfile, init, proc, tag):
    out = TMP / f"{tag}.raw"
    cmd = [HOST, "-mem", str(memfile), "-init", f"{init:x}", "-proc", f"{proc:x}", "-inst", "1", "-r7", "1",
           "-alloc", "0", "-audio", "0", "-inmask", "1", "-frames", str(FRAMES), "-blocks", str(BLOCKS),
           "-in", str(TMP / "in.raw"), "-out", str(out),
           "-peekx", ",".join(f"{a:x}" for a in list(range(0x20)) + [KEY_WORDS + i for i in range(8)])]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"dsp_host failed ({tag}):\n{r.stdout[-600:]}\n{r.stderr[-600:]}")
    got = {int(a, 16): int(v, 16) for a, v in re.findall(r"X:0x([0-9a-f]+) = 0x([0-9a-f]+)", r.stdout)}
    block = [s24(got[i]) for i in range(0x20)]
    peak = max(abs((block[2 * f] + block[2 * f + 1]) >> 1) for f in range(FRAMES))   # the input dsp_host left at X:$00
    return [got.get(KEY_WORDS + i) for i in range(8)], peak


def s24(v):
    return v - (1 << 24) if v & 0x800000 else v


CELL = 0x37F5F                          # a planted track index, read in place of x:$420 (patched copies only)
REMIX = sys.argv[1] if len(sys.argv) > 1 else "test/keybus"
IMAGE = dlbuild.build(REMIX, "keybus")
OWN = {"A": 4, "B": 0}                  # the track dsp_host's setup leaves in x:$420: each core's first


def judge(words, peak, t, what):
    mine, rest = words[t], [w for i, w in enumerate(words) if i != t]
    ok = mine is not None and abs(s24(mine) - peak) <= 1 and all(w == 0 for w in rest)
    check(what, ok, f"0x{mine or 0:06x} (the block's peak 0x{peak:06x}), others {sorted(set(rest))}")


for amp, name in ((0.4, "tone"), (0.0, "silence")):
    samples = []
    for i in range(FRAMES * BLOCKS):
        v = int(amp * 8388607 * math.sin(2 * math.pi * 330 * i / 44100))
        samples += [v, -v // 3]
    (TMP / "in.raw").write_bytes(b"".join(struct.pack("<i", v) for v in samples))
    print(f"{name} (amplitude {amp}):")
    for tag in ("A", "B"):
        mem = send_probe.dump_mem(str(IMAGE), TMP / f"{tag}.mem", tag)
        recs = records(mem)
        tap, how = tap_of(recs, tag)
        check(f"payload {tag}: the hook at P:0x{SITE[tag]:05x} reaches the tap", tap is not None, how)
        if tap is None:
            continue
        init_n, _ = send_probe.entry_points(mem, 0x08)          # the stock null stub's init
        m = TMP / f"{tag}.own.mem"
        write_records(m, recs + [(1, KEY_WORDS, [0] * 8)])
        words, peak = run(m, init_n, tap, f"{name}{tag}own")
        if amp:
            check(f"payload {tag}: a tone's block publishes a nonzero peak", peak > 0x100000, f"0x{peak:06x}")
        judge(words, peak, OWN[tag], f"payload {tag}, as built: x:$420 = {OWN[tag]}, its word holds the peak, the rest 0")
        hook = p_word(recs, SITE[tag] + 1)
        if hook != tap:
            # the hook's own target, a bridged stub, with the demand module not loaded (its BOUND word clear in
            # the boot dump): it skips the module's body and branches to the tap
            words, peak = run(m, init_n, hook, f"{name}{tag}stub")
            judge(words, peak, OWN[tag], f"payload {tag}: through the bridged stub P:0x{hook:05x}, demand module "
                                         f"not loaded: the same word")
        # every track index: the tap's `move x:>$420,r1` (2nd word at tap + 11) reads CELL instead, in a copy
        if p_word(recs, tap + 11) != 0x000420:
            check(f"payload {tag}: the tap's track read is at tap + 10", False, f"{p_word(recs, tap + 11):06x}")
            continue
        for t in range(8):
            m = TMP / f"{tag}{t}.mem"
            write_records(m, recs + [(0, tap + 11, [CELL]), (1, CELL, [t]), (1, KEY_WORDS, [0] * 8)])
            words, peak = run(m, init_n, tap, f"{name}{tag}{t}")
            judge(words, peak, t, f"payload {tag}, track {t}: its word holds the peak, the rest 0")

print("PASS" if not fails else f"{fails} FAIL")
sys.exit(1 if fails else 0)
