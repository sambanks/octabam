#!/usr/bin/env python3
"""FILTER STATION render gates, with arithmetic you can predict.

Renders the station straight through dsp_host (verify_hello's shape: the id
and the slots come from the manifest, the entry points are checked against
SEND's so an absent module cannot pass as a dry passthrough).

Gates:
  defaults    -> output bit-exact vs a full-scale bipolar ramp (the bypass)
  LP slope    -> a low cutoff: 2 kHz vs 4 kHz attenuate by ~12 dB/oct (2-pole)
  HP at DC    -> 0;   BP at DC -> 0;   NOTCH at DC -> DC (lp + hp = x)
  base/width  -> BASE up kills DC through B (SER); WDTH down kills 8 kHz
  RING at DC  -> A*B*2 with A = B = DC: 2*DC^2, to 1 LSB after settling
  VOWEL       -> renders, and differs across FREQ (A vs I)
  every knob  -> renders without dsp_host dying

The dump comes from the audition, which builds a scratch image that really
contains this station beside SEND:

    python3 tools/remix/audition.py filterstation out/dry/drums_110.wav
    python3 tools/verify_filterstation.py
"""
import math, pathlib, struct, subprocess, sys

sys.path.insert(0, "tools")
import send_probe  # reuse its dispatch-table entry resolution
from remix import registry

MOD = registry.by_name("filterstation")
SEND = registry.by_name("send")
K = MOD.knob_map()
MEM = f"out/dsp/_audition_{MOD.name}_A.mem"
HOST = "vendor/dsp56300/build/source/dsp_host/dsp_host"
FXID = MOD.menu.fx2_id
FRAMES, N = 15, 6000
SR = 44100
TMP = pathlib.Path("out/_fsgate")
TMP.mkdir(parents=True, exist_ok=True)

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


fails = 0
def check(label, ok, detail=""):
    global fails
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")
    fails += 0 if ok else 1


# ---- 1. defaults: bit-exact passthrough --------------------------------------
ramp = [int(round(-8388607 + 2 * 8388607 * i / (N - 1))) for i in range(N)]
L, R = render(ramp)
check("defaults are a bit-exact passthrough (the bypass block)",
      L == ramp and R == ramp,
      "" if L == ramp else f"first diff at {next(i for i,(a,b) in enumerate(zip(L,ramp)) if a!=b)}")

# ---- 2. LP slope: low cutoff, 2 kHz vs 4 kHz ---------------------------------
lo = rms_db(render(tone(2000), FREQ=30, RES=0)[0])
hi = rms_db(render(tone(4000), FREQ=30, RES=0)[0])
slope = lo - hi
check("LP is a 2-pole: 2 kHz vs 4 kHz differ by ~12 dB at FREQ=30",
      9 <= slope <= 15, f"{slope:.1f} dB/oct")

# ---- 3. DC through the modes --------------------------------------------------
d_lp = tail_mean(render(dc(), FREQ=64)[0])
d_hp = tail_mean(render(dc(), FREQ=64, MODE=2)[0])
d_bp = tail_mean(render(dc(), FREQ=64, MODE=1)[0])
d_nt = tail_mean(render(dc(), FREQ=64, MODE=3)[0])
dcv = int(0.25 * 8388607)
check("HP at DC -> 0", abs(d_hp) < 64, f"{d_hp:.0f} LSB")
check("BP at DC -> 0", abs(d_bp) < 64, f"{d_bp:.0f} LSB")
check("NOTCH at DC -> DC (lp + hp = x)", abs(d_nt - dcv) < 256, f"{d_nt:.0f} vs {dcv}")
check("LP at DC -> DC", abs(d_lp - dcv) < 256, f"{d_lp:.0f} vs {dcv}")

# ---- 4. filter B: base kills DC, width kills 8 kHz (SER routing) -------------
d_base = tail_mean(render(dc(), BASE=100)[0])
check("BASE=100 kills DC through the pair", abs(d_base) < 64, f"{d_base:.0f} LSB")
w_open = rms_db(render(tone(8000), WDTH=127)[0])
w_shut = rms_db(render(tone(8000), WDTH=30)[0])
check("WDTH=30 attenuates 8 kHz by > 20 dB vs open", w_open - w_shut > 20,
      f"{w_open - w_shut:.1f} dB")

# ---- 5. RING at DC: 2 * A * B, A = B = DC ------------------------------------
d_ring = tail_mean(render(dc(), ROUT=2)[0])
want = 2 * (0.25 ** 2) * 8388607
check("RING at DC -> 2*DC^2", abs(d_ring - want) < 512, f"{d_ring:.0f} vs {want:.0f}")

# ---- 6. VOWEL renders and morphs ---------------------------------------------
va = rms_db(render(tone(1100), MODE=4, FREQ=0, RES=90)[0])     # A: F2 1090
vi = rms_db(render(tone(1100), MODE=4, FREQ=64, RES=90)[0])    # I: F2 2290
check("VOWEL A vs I differ at 1.1 kHz", abs(va - vi) > 3, f"A {va:.1f}  I {vi:.1f} dBFS")

# ---- 7. every knob at its extremes renders -----------------------------------
for name in K:
    for v in (0, 127 if MOD.params[K[name]].count in (None, 128) else MOD.params[K[name]].count - 1):
        render(tone(438, n=600), **{name: v})
check("every knob at both extremes renders", True)

print(f"\n{fails} gate(s) failed" if fails else "\nOK")
sys.exit(1 if fails else 0)
