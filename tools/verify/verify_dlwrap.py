#!/usr/bin/env python3
"""The reverb guard (modules/dlcopy/dlwrap.asm) under dsp_host: a stock reverb runs unchanged where its buffer is clear of loaded code, and stays off it where not.

    python3 tools/verify/verify_dlwrap.py [REMIX]       (default test/dlspike)

PLATE REV is rendered directly and through the wrapper, on each payload, on the allocator slots that put its buffer
at Y:0x4000, 0x8000 and the two window slots, with and without code published inside one window slot (BOUND and
the span words are written into a copy of the dump). Clear of the code the wrapper's output and its Y writes equal the direct render's.
On the 0x34000 slot with code loaded the instance passes the audio through and writes nothing to Y. dsp_host keeps P
and Y apart, so what this proves is the wrapper's decision, not an overwrite on the chip.
"""
import json
import math
import pathlib
import struct
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import dlbuild  # noqa: E402
import send_probe  # noqa: E402
from remix import registry  # noqa: E402

MAGIC = 0xB0A5ED
IDX = (0x6100 >> 8) & 0x3F               # the instance dsp_host runs (-r7 1): r7 = X:0x6100, the guard's per-instance index
HOST = "vendor/dsp56300/build/source/dsp_host/dsp_host"
FRAMES, BLOCKS = 16, 120
TMP = pathlib.Path("out/_dlwrap")
TMP.mkdir(parents=True, exist_ok=True)
fails = 0


def check(label, ok, detail=""):
    global fails
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")
    fails += 0 if ok else 1


REMIX = sys.argv[1] if len(sys.argv) > 1 else "test/dlspike"
R = registry.remix(REMIX)
IMAGE = dlbuild.build(REMIX, "dlwrap")
g_all = json.loads(pathlib.Path("out/dsp/guard_records.json").read_text())
d_all = json.loads(pathlib.Path("out/dsp/demand_records.json").read_text())
# every home of every demand effect: its first and each of Remix.window_homes (a freeze on a unit, 28 Oct 2026, came with the
# code published in the second home, which the first-home spans never reached)
SPANS = [(f"{k}.{h}", hm["addr"], hm["addr"] + len(hm["words"]), k)
         for k, key in enumerate(R.window_demand) for h, hm in enumerate(d_all[key]["homes"])]
samples = []
for i in range(FRAMES * BLOCKS):
    v = int(0.4 * 8388607 * math.sin(2 * math.pi * 220 * i / 44100))
    samples += [v, -v // 2]
(TMP / "in.raw").write_bytes(b"".join(struct.pack("<i", v) for v in samples))


def published(mem, name, lo, hi, k=0):
    """A copy of the dump with the shared words DLCOPY would have written for effect k: BOUND, the span."""
    blob = mem.read_bytes()
    end = blob.rindex(b"\xff")
    e = 0x33DA3 + 8 * k                                     # the effect's entry (modules/dlcopy/dlcopy.asm)
    words = {e + 3: lo, e + 4: hi, e: MAGIC}
    rec = b"".join(struct.pack("<BII", 1, a, 1) + struct.pack("<I", w) for a, w in words.items())
    (TMP / f"{name}.mem").write_bytes(blob[:end] + rec + blob[end:])
    return TMP / f"{name}.mem"


def run(memfile, init, proc, alloc, tag):
    out, ydump = TMP / f"{tag}.raw", TMP / f"{tag}.y"
    cmd = [HOST, "-mem", str(memfile), "-init", f"{init:x}", "-proc", f"{proc:x}", "-inst", "1", "-alloc", str(alloc),
           "-r7", "1", "-inmask", "1", "-frames", str(FRAMES), "-blocks", str(BLOCKS), "-in", str(TMP / "in.raw"),
           "-out", str(out), "-params", "64,64,64,64,64,64", "-dumpy", f"4000,40000,{ydump}"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"dsp_host failed ({tag}):\n{r.stdout[-600:]}\n{r.stderr[-600:]}")
    d, y = out.read_bytes(), ydump.read_bytes()
    return list(struct.unpack(f"<{len(d) // 4}i", d)), struct.unpack(f"<{len(y) // 4}I", y)


def wrote(y, lo, hi):
    """Non-zero Y words in [lo, hi): what the instance wrote there."""
    return sum(1 for a in range(lo, hi) if y[a - 0x4000])


# the code is published inside the slot at 0x34000 (payload A) or 0x38000 (payload B): the allocator's fifth and
# seventh entries are those slots' bases on the payload that has them
for key, sid, tag, bases, (lo, hi) in [(k, i, t, b, w) for k, i in (("PLATE REV", 0x14), ("SPRING REV", 0x15), ("DARK REV", 0x16))
                                       for t, b, w in (("A", (0x4000, 0x8000, 0x30000, 0x34000), (0x35000, 0x35619)),
                                                       ("B", (0x4000, 0x8000, 0x38000, 0x3C000), (0x39000, 0x39619)))]:
    print(f"{key}, payload {tag}:")
    mem = send_probe.dump_mem(str(IMAGE), TMP / f"{tag}.mem", tag)
    g = g_all[f"{key}:{tag}"]
    init_p, proc_p = g["stock_init"], g["stock_proc"]             # the stock reverb
    init_w, proc_w = send_probe.entry_points(mem, sid)            # its id now dispatches to the wrapper
    init_n, proc_n = send_probe.entry_points(mem, 0x08)           # the null stub
    # the published spans to try: each demand effect's own, and a synthetic one inside this payload's window slot
    cases = list(SPANS) + [("syn", lo, hi, 0)]
    dry_out, _ = run(mem, init_n, proc_n, 1, f"null{tag}")
    for alloc, base in zip((1, 3, 5, 7), bases):
        d_out, d_y = run(mem, init_p, proc_p, alloc, f"direct{key[:2]}{tag}{alloc}")
        w_out, w_y = run(mem, init_w, proc_w, alloc, f"clear{key[:2]}{tag}{alloc}")
        check(f"no code loaded, buffer at Y:0x{base:05x}: the wrapper equals the stock render", w_out == d_out and w_y == d_y)
        check(f"no code loaded, buffer at Y:0x{base:05x}: the reverb really wrote its buffer", wrote(d_y, base, base + 0x400) > 0)
        # a dry instance whose init never ran resumes when the range is clear: seed state 2 and the base,
        # skip the init (the null stub's), and the proc must run the stock init itself, then the stock proc
        seeded = TMP / f"seed{key[:2]}{tag}{alloc}.mem"
        blob = mem.read_bytes()
        end = blob.rindex(b"\xff")
        rec = b"".join(struct.pack("<BII", 1, a_, 1) + struct.pack("<I", v_) for a_, v_ in ((0x3DC0 + IDX, 2), (0x3E00 + IDX, base)))
        seeded.write_bytes(blob[:end] + rec + blob[end:])
        r_out, r_y = run(seeded, init_n, proc_w, alloc, f"resume{key[:2]}{tag}{alloc}")
        check(f"dry before its init, range clear, buffer at Y:0x{base:05x}: the proc runs the stock init and then equals the stock render",
              r_out == d_out and r_y == d_y)
        for cname, c_lo, c_hi, c_k in cases:
            loaded = published(mem, f"loaded{key[:2]}{tag}{cname}", c_lo, c_hi, c_k)
            w_out, w_y = run(loaded, init_w, proc_w, alloc, f"loaded{key[:2]}{tag}{alloc}{cname}")
            covers = base < c_hi and base + g["extent"] > c_lo
            what = f"span {cname} (P:0x{c_lo:05x}..0x{c_hi:05x})"
            if covers:
                check(f"{what} loaded, buffer at Y:0x{base:05x} covers it: the instance passes the audio through", w_out == dry_out)
                check(f"{what} loaded, buffer at Y:0x{base:05x} covers it: nothing is written to the buffer",
                      wrote(w_y, base, base + g["extent"]) == 0)
            else:
                check(f"{what} loaded, buffer at Y:0x{base:05x} clear of it: the wrapper equals the stock render",
                      w_out == d_out and w_y == d_y)

print("PASS" if not fails else f"{fails} FAIL")
sys.exit(1 if fails else 0)
