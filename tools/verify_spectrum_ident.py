#!/usr/bin/env python3
"""Prove a rewritten Spectrum renders BIT-IDENTICALLY to a saved reference.
Setup and render helpers are lifted from tools/verify_spectrum.py (which has
no main guard, so it cannot be imported). See the block at the bottom.
"""
import math, pathlib, struct, subprocess, sys

sys.path.insert(0, "tools")
import send_probe  # reuse its dispatch-table entry resolution
from remix import registry

MOD = registry.by_name("spectrum")
SEND = registry.by_name("send")
K = MOD.knob_map()
MEM = f"out/dsp/_audition_{MOD.name}_A.mem"
HOST = "vendor/dsp56300/build/source/dsp_host/dsp_host"
FXID = MOD.menu.fx2_id
FRAMES, N = 15, 6000
SR = 44100
TMP = pathlib.Path("out/_fsgate")
TMP.mkdir(parents=True, exist_ok=True)

# ⚠️ REBUILD THE DUMP, ALWAYS. The audition caches its scratch image against
# the newest mtime under modules/, and a stale hit here does not fail -- it
# silently measures the STOCK effect whose id this module replaces. That cost
# an hour on 3 Sep 2026: every mode read as a dry pass, because the dump's
# dispatch still pointed at stock CHORUS, and the emulator eventually died on
# a stock instruction it does not implement.
pathlib.Path(MEM).unlink(missing_ok=True)
subprocess.run([sys.executable, "tools/remix/audition.py", MOD.name,
                "out/dry/drums_110.wav"], capture_output=True)

if not pathlib.Path(MEM).exists():
    sys.exit(f"no {MEM} -- build it first:\n"
             f"  python3 tools/remix/audition.py {MOD.name} out/dry/drums_110.wav")

init, proc = send_probe.entry_points(MEM, FXID)
if (init, proc) == send_probe.entry_points(MEM, SEND.menu.fx2_id):
    sys.exit(f"fx id 0x{FXID:02x} resolves to SEND's entry points -- {MOD.name} "
             f"is NOT in this dump")
print(f"entries from dispatch tables: init=P:0x{init:04x} proc=P:0x{proc:04x}")

DEFAULTS = [(p.default or 0) for p in MOD.params]


def params(**kw):
    v = list(DEFAULTS)
    for name, val in kw.items():
        v[K[name]] = val
    return v


def render(samples, **kw):
    """samples: MONO ints in Q23 -- dsp_host feeds one stream to both
    channels (verify_hello's shape). Returns (L, R) lists."""
    src = TMP / "fs_in.raw"
    src.write_bytes(b"".join(struct.pack("<i", m) for m in samples))
    out = TMP / "fs_out.raw"
    cmd = [HOST, "-mem", MEM, "-init", f"{init:x}", "-proc", f"{proc:x}",
           "-inst", "1", "-r7", "2", "-alloc", "1", "-inmask", "1",
           "-frames", str(FRAMES), "-blocks", str(len(samples) // FRAMES),
           "-in", str(src), "-out", str(out),
           "-params", ",".join(str(x) for x in params(**kw))]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"dsp_host failed for {kw}:\n{r.stdout}\n{r.stderr}")
    d = out.read_bytes()
    w = struct.unpack(f"<{len(d)//4}i", d)
    return list(w[0::2])[:len(samples)], list(w[1::2])[:len(samples)]


def tone(hz, amp=0.4, n=N):
    return [int(amp * 8388607 * math.sin(2 * math.pi * hz * i / SR)) for i in range(n)]


def dc(level=0.25, n=N):
    return [int(level * 8388607)] * n


def rms_db(x, start=N // 2):
    seg = x[start:]
    return 20 * math.log10(max(1e-9, math.sqrt(sum((s / 8388607) ** 2 for s in seg) / len(seg))))


def tail_mean(x, start=N * 3 // 4):
    seg = x[start:]
    return sum(seg) / len(seg)



# ============================================================================
# BIT-IDENTITY across a knob matrix -- the gate for a cycle pass (4 Sep 2026)
#   python3 tools/verify_spectrum_ident.py ref     # capture from the current build
#   python3 tools/verify_spectrum_ident.py check   # compare the current build
# ============================================================================
import hashlib, json
REF = pathlib.Path("out/spectrum_ident_ref.json")
NAMES = [p.name.decode() for p in MOD.params]
def signal():
    a = tone(440, 0.30); b = tone(2500, 0.15)
    return [max(-8388608, min(8388607, x + y + (838860 if i > N // 2 else 0)))
            for i, (x, y) in enumerate(zip(a, b))]
def settings():
    base = {k: v for k, v in dict(FREQ=64, RES=90, BASE=40, WDTH=100, DRV=60,
                                  DPTH=90, RATE=70, SRC=2).items() if k in NAMES}
    out = {"defaults": {}}
    for mode in range(5):
        for rout in range(4):
            out[f"mode{mode}_rout{rout}"] = dict(base, MODE=mode, ROUT=rout)
    for src in range(3):
        out[f"src{src}"] = dict(base, MODE=1, ROUT=1, SRC=src)
    out["zeros"] = {n: 0 for n in NAMES if n}
    out["max"] = {n: ((MOD.params[NAMES.index(n)].count or 128) - 1) for n in NAMES if n}
    return out
def hashes():
    sig = signal(); out = {}
    h = lambda v: hashlib.sha1(b"".join(int(x).to_bytes(4, "little", signed=True) for x in v)).hexdigest()[:16]
    for label, kw in settings().items():
        L, R = render(sig, **kw)
        out[label] = [h(L), h(R)]
    return out
if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    got = hashes()
    if mode == "ref":
        REF.write_text(json.dumps(got, indent=1))
        print(f"reference saved: {len(got)} settings -> {REF}")
    else:
        ref = json.loads(REF.read_text())
        bad = [k for k in ref if got.get(k) != ref[k]]
        for k in ref:
            print(f"  [{'PASS' if k not in bad else 'FAIL'}] {k}")
        print(f"\n{'IDENTICAL' if not bad else 'DIFFERS'}: {len(ref)-len(bad)}/{len(ref)} settings bit-identical")
        sys.exit(1 if bad else 0)
