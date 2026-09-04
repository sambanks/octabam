#!/usr/bin/env python3
"""THE RETURNS: the engines' wet, published to the bus and returned at the
master by a Character station in BUS mode (docs/BUS.md "The returns").

Renders through send_probe.run() against the DEV dump (all three servers
real), so a layout can hold the reverb, the delay and the station at once.
What it proves, and the control that makes each proof mean something:

  host, no return   -> the reverb still comes out of its host, and the
                       station being merely PRESENT (SAT=BUS, levels 0)
                       leaves that output BIT-IDENTICAL: no stamp, no change
  host, return live -> the host's stream goes to digital silence (dry only,
                       and the tone never reaches it)
  the return        -> the station's stream IS the host's old wet, two
                       blocks late (the bus read is two buffers back) and
                       127/128 of it (the knob's own scale) -- matched
                       sample by sample after the lag, not by level alone
  stereo            -> L and R of the return differ (the reverb's width
                       survives; a mono M would have thrown it away)
  not BUS           -> SAT=TAPE with CRSH=127 returns nothing (it crushes),
                       and the host keeps printing
  delay             -> the same four for BusDelay, on the DLY knob (RING)
  both              -> both returns at once = the sum of each alone
  no runaway        -> a station that SENDS ->VRB while RETURNING the reverb
                       does not feed the return back into the bus: the tail
                       after the tone decays

Falsifiers: a host stream that is not silent under a live return (the stamp
never reached the engine, or the print gain is not 0); a return that matches
only in level (wrong rotation or frame doubling reads a stale or torn
buffer -- the sample match would fail); a "no return" case that is not
bit-identical (the station changed the bus while returning nothing).

    REMIX=bamsep26 DEV=1 XBUS=1 python3 tools/build_bus.py
    python3 tools/verify_returns.py
"""
import math, pathlib, sys

sys.path.insert(0, "tools")
import send_probe
from remix import registry

MEM = pathlib.Path("out/dsp/mem_dev_A.mem")
# ⚠️ REBUILD THE DUMP, ALWAYS (verify_character's rule). mem_dev_A.mem is
# whatever the last DEV build left -- verify-bus rebuilds it from the DEFAULT
# remix, which has no station, and then id 0x1c dispatches to STOCK LO-FI:
# the host keeps printing, the "return" is LO-FI processing silence, and
# every case fails for a reason that has nothing to do with the returns
# (3 Sep 2026, the first run of this gate).
import os, subprocess
_r = subprocess.run([sys.executable, "tools/build_bus.py"],
                    env={**os.environ, "REMIX": "bamsep26", "DEV": "1", "XBUS": "1"},
                    capture_output=True, text=True)
if _r.returncode != 0:
    sys.exit("the DEV build failed:\n" + _r.stdout[-2000:] + _r.stderr[-2000:])
if not MEM.exists():
    sys.exit("the DEV build wrote no out/dsp/mem_dev_A.mem")
CH = registry.by_name("character")
L2 = CH.harness.layout_char
K = CH.knob_map_all()
for c in ("R", "D", "S", L2):
    if c not in send_probe.SERVER_ID:
        sys.exit(f"layout letter {c!r} is not in the registry")
# The station must really be in the dump -- an absent id aliases to SEND and
# renders a plausible dry passthrough (CLAUDE.md).
if send_probe.entry_points(str(MEM), send_probe.SERVER_ID[L2]) == \
        send_probe.entry_points(str(MEM), send_probe.SERVER_ID["S"]):
    sys.exit("the Character station is not in this dump (its entry is SEND's)")

FRAMES = send_probe.FRAMES
REV = list(send_probe.REV_PARAMS)          # IN = 0: a pure return
DLY = list(send_probe.DELAY_PARAMS)
SEND_R = [0, 127] + [0] * 10
SEND_D = [127, 0] + [0] * 10
DUR, TAIL = 0.6, 0.6


def station(**kw):
    v = [(p.default or 0) for p in CH.params]
    for n, x in kw.items():
        v[K[n]] = x
    return v


def run(layout, pick, send, st=None, feed=None):
    ins = {L2: st} if st is not None else None
    L, R = send_probe.run(str(MEM), DUR, TAIL, REV, send, layout=layout,
                          delay_params=DLY, pick=pick, insert_params=ins,
                          feed=feed)
    return L, R


def rms_db(x):
    return 20 * math.log10(max(1e-9, math.sqrt(sum((v / 8388607) ** 2 for v in x) / max(1, len(x)))))


def best_lag(ref, got, lo=0, hi=64):
    """the lag (got is ref delayed by it) minimising the residual, and the
    residual in dB relative to ref"""
    best = None
    for lag in range(lo, hi + 1):
        n = min(len(ref) - lag, len(got) - lag)
        if n <= 0:
            continue
        r = ref[:n]
        g = got[lag:lag + n]
        # the knob's own scale: 127/128
        res = sum((gi - ri * 127 / 128) ** 2 for gi, ri in zip(g, r))
        den = sum(ri * ri for ri in r) or 1
        db = 10 * math.log10(max(1e-12, res / den))
        if best is None or db < best[1]:
            best = (lag, db)
    return best


fails = 0
def check(label, ok, detail=""):
    global fails
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")
    fails += 0 if ok else 1


for name, lay, pick, send, knob in (("reverb", "SR", "R", SEND_R, "CRSH"),
                                    ("delay",  "SD", "D", SEND_D, "RING")):
    print(f"\n== {name}: {lay} ==")
    hL, hR = run(lay, pick, send)                                   # host, alone
    check(f"{name} prints on its host with no return in the rig",
          rms_db(hL) > -40, f"rms {rms_db(hL):.1f} dB")
    # present but returning nothing: bit-identical
    pL, pR = run(lay + L2, pick, send, station(SAT=3))
    check(f"{name}: a BUS-mode station with levels 0 leaves the host bit-identical",
          pL == hL and pR == hR)
    # not BUS: the knob crushes, nothing returns, the host prints
    nL, nR = run(lay + L2, L2, send, station(SAT=0, **{knob: 127}))
    check(f"{name}: SAT=TAPE with {knob}=127 returns nothing",
          max(abs(v) for v in nL) == 0, f"peak {max(abs(v) for v in nL)}")
    n2L, _ = run(lay + L2, pick, send, station(SAT=0, **{knob: 127}))
    check(f"{name}: ... and the host still prints, bit-identical", n2L == hL)
    # the return
    live = station(SAT=3, **{knob: 127})
    qL, qR = run(lay + L2, pick, send, live)
    check(f"{name}: host stream is digital silence under a live return",
          max(abs(v) for v in qL + qR) == 0,
          f"peak {max(abs(v) for v in qL + qR)}")
    rL, rR = run(lay + L2, L2, send, live)
    lag, db = best_lag(hL, rL)
    check(f"{name}: the return IS the host's wet, lag {lag} samples "
          f"(2 blocks = {2 * FRAMES}), x127/128",
          lag == 2 * FRAMES and db < -60, f"residual {db:.1f} dB rel")
    lagR, dbR = best_lag(hR, rR)
    check(f"{name}: right channel likewise", lagR == 2 * FRAMES and dbR < -60,
          f"lag {lagR} residual {dbR:.1f} dB")
    check(f"{name}: the return is stereo (L != R)", rL != rR)
    if name == "reverb":
        keep_r = (rL, rR)
    else:
        keep_d = (rL, rR)

print("\n== both engines, one return ==")
bL, bR = run("SRD" + L2, L2, [127, 127] + [0] * 10, station(SAT=3, CRSH=127, RING=127))
# each alone, in the same layout positions, so the rotation history matches
aL, _ = run("SRD" + L2, L2, [127, 127] + [0] * 10, station(SAT=3, CRSH=127))
cL, _ = run("SRD" + L2, L2, [127, 127] + [0] * 10, station(SAT=3, RING=127))
n = min(len(bL), len(aL), len(cL))
res = sum((b - (x + y)) ** 2 for b, x, y in zip(bL[:n], aL[:n], cL[:n]))
den = sum(b * b for b in bL[:n]) or 1
db = 10 * math.log10(max(1e-12, res / den))
check("both returns = reverb return + delay return (linear, to rounding)",
      db < -80, f"residual {db:.1f} dB rel")

print("\n== no runaway: the station sends ->VRB and returns RVRB on one track ==")
fL, _ = run("R" + L2, L2, SEND_R, station(SAT=3, CRSH=127, **{"-VRB": 127}), feed=L2)
tone_end = int(DUR * send_probe.SR)
early = rms_db(fL[tone_end:tone_end + 4000])
late = rms_db(fL[-4000:])
check("the tail after the tone DECAYS (the return is added after the tap)",
      late < early - 6, f"{early:.1f} dB -> {late:.1f} dB")

print(f"\n{fails} gate(s) failed" if fails else "\nOK")
sys.exit(1 if fails else 0)
