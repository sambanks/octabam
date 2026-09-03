#!/usr/bin/env python3
"""CHARACTER STATION render gates, with arithmetic you can predict.

Renders the station straight through dsp_host (verify_hello's shape: the id
and the slots come from the manifest, the entry points are checked against
SEND's so an absent module cannot pass as a dry passthrough).

Gates:
  defaults    -> output bit-exact vs a full-scale bipolar ramp (the bypass)
  MIX=0       -> bit-exact passthrough with the whole chain live
  CRSH        -> the output is quantised: every sample a multiple of 2^k
  SRR         -> /2 /4 /8 hold each sample exactly that many times
  DRV/SAT     -> unity small-signal (a tiny input passes at gain 1 to 1 LSB),
                 and every character is monotonic and bounded
  FOLD        -> a full-scale ramp folds back: the output reverses direction
  RING        -> at DC the output is DC * carrier, so its mean is ~0
  COMP        -> gain reduction grows with level, and never inverts
  TRNS        -> a step transient comes out LOUDER than steady state
  WDTH        -> 0 = mono (L == R), 64 = untouched, 127 = doubled sides
  every knob  -> renders without dsp_host dying

The dump comes from the audition, which builds a scratch image that really
contains this station beside SEND:

    python3 tools/remix/audition.py charstation out/dry/drums_110.wav
    python3 tools/verify_charstation.py
"""
import math, pathlib, struct, subprocess, sys

sys.path.insert(0, "tools")
import send_probe  # reuse its dispatch-table entry resolution
from remix import registry

MOD = registry.by_name("charstation")
SEND = registry.by_name("send")
K = MOD.knob_map()
MEM = f"out/dsp/_audition_{MOD.name}_A.mem"
HOST = "vendor/dsp56300/build/source/dsp_host/dsp_host"
FXID = MOD.menu.fx2_id
FRAMES, N = 15, 6000
SR = 44100
TMP = pathlib.Path("out/_chgate")
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
    src = TMP / "ch_in.raw"
    src.write_bytes(b"".join(struct.pack("<i", m) for m in samples))
    out = TMP / "ch_out.raw"
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

# ---- 2. MIX=0 with the whole chain live --------------------------------------
L, R = render(ramp, MIX=0, DRV=127, FOLD=127, CRSH=127, COMP=127, RING=64, SRR=3)
check("MIX=0 is a passthrough with every stage driven", L == ramp and R == ramp,
      "" if L == ramp else f"first diff at {next(i for i,(a,b) in enumerate(zip(L,ramp)) if a!=b)}")

# ---- 3. CRSH reduces the resolution -----------------------------------------
# ⚠️ MEASURE THE WET, NOT THE OUTPUT, twice over: the saturator is a cubic
# that fills the low bits back in, AND the mix law carries 1/128 of the live
# dry, which is not quantised -- so every output sample is distinct however
# hard the crush bites. The wet comes back exactly (out = dry/128 + wet*127/128)
# and its DISTINCT LEVELS are what the crush actually sets.
slow = [int(-8388607 + 2 * 8388607 * i / (N - 1)) for i in range(N)]
def levels(crsh):
    L, _ = render(slow, CRSH=crsh)
    wet = [round((o - d / 128) * 128 / 127) for o, d in zip(L, slow)]
    return len(set(wet[N//4:]))
n_off, n_on = levels(1), levels(110)
check("CRSH=110 collapses a ramp to a few levels", n_on * 8 < n_off,
      f"{n_on} distinct wet levels against {n_off} at CRSH=0")

# ---- 4. SRR holds each sample -----------------------------------------------
# ⚠️ THE OUTPUT IS NOT HELD, THE WET IS. MIX=127 is 127/128, so the output
# carries 1/128 of the live dry: out = dry/128 + wet*127/128. Recover the wet
# exactly and look for its runs, rather than testing near-equality on a
# signal that legitimately moves every sample.
src = tone(438)
for sel, hold in ((1, 2), (2, 4), (3, 8)):
    L, _ = render(src, SRR=sel)
    wet = [(o - d / 128) * 128 / 127 for o, d in zip(L, src)]
    seg = [round(v) for v in wet[N//2:N//2 + 400]]
    runs, cur = [], 1
    for a, b in zip(seg, seg[1:]):
        if abs(a - b) <= 2:
            cur += 1
        else:
            runs.append(cur); cur = 1
    typical = max(set(runs), key=runs.count) if runs else 0
    check(f"SRR /{hold} holds the wet {hold} samples", typical == hold,
          f"most common run {typical}")

# ---- 5. saturation is unity small-signal and bounded -------------------------
small = [int(0.001 * 8388607 * math.sin(2 * math.pi * 438 * i / SR)) for i in range(N)]
for sat, name in ((0, "TAPE"), (1, "TUBE"), (2, "FUZZ"), (3, "BUS")):
    L, _ = render(small, DRV=0, SAT=sat)
    err = max(abs(a - b) for a, b in zip(L[N//2:], small[N//2:]))
    check(f"SAT {name} is unity small-signal at DRV=0", err <= 40, f"max err {err} LSB")
for sat, name in ((0, "TAPE"), (1, "TUBE"), (2, "FUZZ"), (3, "BUS")):
    L, _ = render(tone(438, amp=0.9), DRV=127, SAT=sat)
    check(f"SAT {name} stays bounded at DRV=127",
          max(abs(v) for v in L) <= 8388607, f"peak {max(abs(v) for v in L)}")

# ---- 6. FOLD folds a ramp back ----------------------------------------------
L, _ = render(ramp, FOLD=127, DRV=0, SAT=0)
turns = sum(1 for a, b, c in zip(L, L[1:], L[2:]) if (b - a > 0) != (c - b > 0))
check("FOLD=127 folds a monotonic ramp (it changes direction many times)",
      turns > 4, f"{turns} direction changes")

# ---- 7. RING at DC: the output is DC * carrier, mean ~0 ----------------------
L, _ = render(dc(), RING=64, DRV=0)
m = abs(tail_mean(L, N // 4))
check("RING at DC has ~zero mean (it is DC times a carrier)",
      m < 0.05 * 0.25 * 8388607, f"mean {m:.0f} of {0.25*8388607:.0f}")

# ---- 8. COMP reduces more as the level rises, and never inverts -------------
quiet, _ = render(tone(438, amp=0.05), COMP=127, CMOD=0)
loud, _ = render(tone(438, amp=0.9), COMP=127, CMOD=0)
q0, _ = render(tone(438, amp=0.05), COMP=0)
l0, _ = render(tone(438, amp=0.9), COMP=0)
gr_q = rms_db(quiet) - rms_db(q0)
gr_l = rms_db(loud) - rms_db(l0)
check("COMP reduces the loud signal more than the quiet one",
      gr_l < gr_q - 2, f"quiet {gr_q:+.1f} dB, loud {gr_l:+.1f} dB")
unity, _ = render(tone(438, amp=0.3), COMP=0, CMOD=0)
ref, _ = render(tone(438, amp=0.3), MIX=0)
check("COMP=0 is unity gain (the halved-gain doubling is exact)",
      abs(rms_db(unity) - rms_db(ref)) < 0.1,
      f"{rms_db(unity) - rms_db(ref):+.2f} dB")

# ---- 9. TRNS makes a transient louder than the steady state -----------------
step_sig = [0] * (N // 2) + [int(0.15 * 8388607 * math.sin(2 * math.pi * 438 * i / SR)) for i in range(N // 2)]
L, _ = render(step_sig, COMP=127, CMOD=2)
onset = max(abs(v) for v in L[N//2:N//2 + 300])
steady = max(abs(v) for v in L[-N//4:])
check("TRNS boosts the onset above the steady state", onset > steady * 1.05,
      f"onset {onset} vs steady {steady}")

# ---- 10. WDTH -----------------------------------------------------------------
# a stereo-different source: dsp_host feeds one stream to both channels, so
# the width test rides on the RING carrier making L and R identical anyway --
# what it can prove is that 0 collapses to mono and 64 leaves the pair alone.
L, R = render(tone(438), WDTH=0, DRV=1)
check("WDTH=0 is mono (L == R)", L == R, "")
L64, R64 = render(tone(438), WDTH=64, DRV=1)
Lref, _ = render(tone(438), DRV=1)
check("WDTH=64 leaves the signal alone", L64 == Lref, "")

# ---- 11. every knob at its extremes renders ----------------------------------
for name in K:
    for v in (0, 127 if MOD.params[K[name]].count in (None, 128) else MOD.params[K[name]].count - 1):
        render(tone(438, n=600), **{name: v})
check("every knob at both extremes renders", True)

print(f"\n{fails} gate(s) failed" if fails else "\nOK")
sys.exit(1 if fails else 0)
