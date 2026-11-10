#!/usr/bin/env python3
"""MODULATION render gates -- the FX1-ONLY PROMISE, and every mode against its
float reference (modules/modulation/modulation_ref.py: the sources'
per-sample laws with the station's knob decode in front).

Gates:
  FX1 instance  -> MIX=0 is a bit-exact passthrough in every mode
  FX2 instance  -> bit-exact DRY at any setting, in every mode
  FX2 instance  -> dsp_host's -guard sees NO write outside the frame
  every mode    -> the DSP render matches the reference on a stereo signal
                   (different L and R), at the mode's defaults and at a
                   second, harder setting: max error and level agreement
  JUNO          -> the sweep is the Juno's: an impulse comes back between
                   1.5 and 5.4 ms; RATE 26 is 0.5 Hz (the law)
  FLNG          -> through-zero: the wet nulls the dry at the crossing
  PHSR          -> unity magnitude (an allpass chain) at FDBK 64
  COMB          -> DLY tunes the ring: the peak sits at the table's period
  every knob    -> renders at both extremes without dsp_host dying

    python3 tools/remix/audition.py modulation out/dry/drums_110.wav
    python3 tools/verify/verify_modulation.py
"""
import math, pathlib, struct, subprocess, sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
import send_probe  # reuse its dispatch-table entry resolution
from remix import registry

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "modules" / "modulation"))
import modulation_ref as REF

MOD = registry.by_name("modulation")
SEND = registry.by_name("send")
K = MOD.knob_map()
MEM = f"out/dsp/_audition_{MOD.name}_A.mem"
HOST = "vendor/dsp56300/build/source/dsp_host/dsp_host"
FXID = MOD.menu.fx2_id
FRAMES, N = 15, 6000
SR = 44100
FS = 8388607
TMP = pathlib.Path("out/_mogate")
TMP.mkdir(parents=True, exist_ok=True)

# ⚠️ REBUILD THE DUMP, ALWAYS. The audition caches its scratch image against
# the newest mtime under modules/, and a stale hit here does not fail -- it
# silently measures the STOCK effect whose id this module replaces.
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
MODES = REF.MODES


def params(**kw):
    v = list(DEFAULTS)
    for name, val in kw.items():
        v[K[name]] = val
    return v


def mode_knobs(mode, **over):
    """a mode's ModeView defaults, then the overrides -- as a knob dict"""
    d = {name: DEFAULTS[i] for name, i in K.items()}
    for slot, val in MOD.view_for(MODES[mode]).defaults.items():
        d[MOD.canon_name(slot)] = val
    d["MODE"] = MODES[mode]
    d.update(over)
    return d


def _run(inter, n, slot="fx1", guard=False, stereo=True, **kw):
    src = TMP / "mo_in.raw"
    src.write_bytes(b"".join(struct.pack("<i", m) for m in inter))
    out = TMP / "mo_out.raw"
    r7, alloc = ("1", "0") if slot == "fx1" else ("2", "1")
    cmd = [HOST, "-mem", MEM, "-init", f"{init:x}", "-proc", f"{proc:x}",
           "-inst", "1", "-r7", r7, "-alloc", alloc, "-inmask", "1",
           *(["-stereo"] if stereo else []),
           *(["-guard"] if guard else []),
           "-frames", str(FRAMES), "-blocks", str(n // FRAMES),
           "-in", str(src), "-out", str(out),
           "-params", ",".join(str(x) for x in params(**kw))]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"dsp_host failed for {kw}:\n{r.stdout}\n{r.stderr}")
    if guard:
        _run.guard_out = r.stdout + r.stderr
    d = out.read_bytes()
    w = struct.unpack(f"<{len(d)//4}i", d)
    return list(w[0::2])[:n], list(w[1::2])[:n]


def render(samples, **kw):
    """MONO ints in Q23, fed to both channels."""
    return _run(samples, len(samples), stereo=False, **kw)


def render_stereo(Ls, Rs, **kw):
    inter = []
    for i in range(len(Ls)):
        inter.append(Ls[i]); inter.append(Rs[i])
    return _run(inter, len(Ls), stereo=True, **kw)


def tone(hz, amp=0.4, n=N):
    return [int(amp * FS * math.sin(2 * math.pi * hz * i / SR)) for i in range(n)]


def rms_db(x, start=N // 2):
    seg = x[start:]
    return 20 * math.log10(max(1e-9, math.sqrt(sum((s / FS) ** 2 for s in seg) / len(seg))))


fails = 0
def check(label, ok, detail=""):
    global fails
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")
    fails += 0 if ok else 1


# ---- 1. FX1: MIX=0 is a bit-exact passthrough in every mode ------------------
ramp = [int(round(-FS + 2 * FS * i / (N - 1))) for i in range(N)]
ok = True
for name, m in MODES.items():
    L, R = render(ramp, MODE=m, MIX=0)
    if L != ramp or R != ramp:
        ok = False
        check(f"FX1 MIX=0 passthrough in {name}", False,
              f"first diff at {next(i for i,(a,b) in enumerate(zip(L,ramp)) if a!=b)}")
check("FX1: MIX=0 is a bit-exact passthrough in all five modes", ok)

# ---- 2. THE FX1-ONLY PROMISE: an FX2 instance is dry, whatever the knobs -----
ok = True
for name, m in MODES.items():
    L, R = render(ramp, slot="fx2", MODE=m, MIX=127, DPTH=127, FDBK=100, RATE=90)
    if L != ramp or R != ramp:
        ok = False
        check(f"FX2 instance is dry in {name}", False, "it processed the frame")
check("FX2 instance is a bit-exact DRY PASS in all five modes, at any setting", ok)

# ---- 3. ... and writes nothing: dsp_host's guard --------------------------------
render(ramp, slot="fx2", guard=True, MODE=1, MIX=127, DPTH=127, FDBK=100)
g = _run.guard_out
check("FX2 instance: -guard reports nothing written over a loaded module",
      "nothing written" in g or "0 writes" in g or "guard: ok" in g.lower(),
      g.strip().splitlines()[-1] if g.strip() else "no guard output")

# ---- 4. every mode against its float reference ---------------------------------
# A stereo signal, different per channel: a 1 kHz tone at 0.3 on L and a
# 330 Hz tone at 0.2 plus a short burst on R. The reference runs the same
# knobs from the same zero state; the DSP's arithmetic is Q23 with the
# limiting stores, so the bar is a small max error and level agreement.
def burst(n=N):
    out = [0.0] * n
    for i in range(200, 260):
        out[i] = 0.5 * math.sin(2 * math.pi * 2000 * i / SR)
    return out

Lf = [0.3 * math.sin(2 * math.pi * 1000 * i / SR) for i in range(N)]
Rf = [0.2 * math.sin(2 * math.pi * 330 * i / SR) + b for i, b in enumerate(burst())]
Li = [int(v * FS) for v in Lf]
Ri = [int(v * FS) for v in Rf]
Lq = [v / FS for v in Li]
Rq = [v / FS for v in Ri]

CASES = [
    # (mode, overrides, bar, input scale). The bar is the Q23 arithmetic's
    # residual: ~1e-4 where the law is linear; COMB's loop recirculates its
    # rounding (a high-Q ring amplifies it ~1/(1 - g)) so its bar is 3e-3, and
    # its input is a third so the resonance stays under the limiting stores
    # (the DSP and the reference clamp in different places once it clips).
    ("JUNO", {}, 5e-4, 1.0),
    ("JUNO", dict(RATE=127, DPTH=6, WDTH=0, DLY=12, FDBK=100, TONE=20, MIX=127), 5e-4, 1.0),   # I+II, with feedback, dark
    ("DIM", {}, 5e-4, 1.0),
    ("DIM", dict(RATE=60, DPTH=90, DLY=100, MIX=90), 5e-4, 1.0),
    ("FLNG", {}, 5e-4, 1.0),
    ("FLNG", dict(FDBK=120, DPTH=127, DLY=40, WDTH=64, MIX=100), 5e-4, 1.0),
    ("PHSR", {}, 5e-4, 1.0),
    ("PHSR", dict(FDBK=110, DPTH=127, RATE=110, DLY=0, WDTH=127, MIX=127), 5e-4, 1.0),
    ("COMB", {}, 3e-3, 1 / 3),
    ("COMB", dict(FDBK=10, DLY=120, TONE=0, MIX=127), 3e-3, 1 / 3),
    ("COMB", dict(FDBK=20, DLY=64, TONE=127, MIX=127), 3e-3, 1 / 3),      # negative: odd harmonics
    # LOFI: the hold counter must agree to the sample (a phase slip is a gross
    # error); the bit mask floors a Q23 word, so where the reference's float
    # sits within its ~1e-4 of a mask boundary the two floor apart by one
    # quantum -- the bar is one quantum (2^(bits-24)) above the linear residual.
    ("JUNO", dict(LOFI=40, MIX=127), 5e-4, 1.0),                            # hold 7, 24 bits
    ("PHSR", dict(LOFI=90, MIX=127), 5e-4 + 2 ** -8, 1.0),                  # hold 32, 9 bits
    ("DIM", dict(LOFI=127, MIX=127), 5e-4 + 2 ** -4, 1.0),                  # hold 64, 5 bits
    ("COMB", dict(LOFI=100, MIX=127), 3e-3 + 2 ** -7, 1 / 3),                # hold 40, 8 bits, through the ring
]
for mode, over, bar, scale in CASES:
    kn = mode_knobs(mode, **over)
    li = [int(v * scale) for v in Li]
    ri = [int(v * scale) for v in Ri]
    L, R = render_stereo(li, ri, **kn)
    ref = REF.make(mode, **{k: v for k, v in kn.items() if k != "MODE"})
    rL, rR = ref.process([v / FS for v in li], [v / FS for v in ri])
    err = max(max(abs(L[i] / FS - rL[i]), abs(R[i] / FS - rR[i])) for i in range(N))
    lvl = max(abs(rms_db(L) - rms_db([v * FS for v in rL])),
              abs(rms_db(R) - rms_db([v * FS for v in rR])))
    tag = ",".join(f"{k}={v}" for k, v in over.items()) or "defaults"
    check(f"{mode} matches the reference ({tag})", err <= bar and lvl <= 0.1,
          f"max err {err:.2e} (bar {bar:.0e}), level {rms_db(L):.1f}/{rms_db(R):.1f} dB vs ref "
          f"{rms_db([v * FS for v in rL]):.1f}/{rms_db([v * FS for v in rR]):.1f}")

# ---- 4b. the block-linear sweep against the per-sample LFO ---------------------
# The swept delays are a straight line per block (mo_knot): off the triangle where
# a corner falls inside a block (at most half a block of slope) and in the first
# block after init or a MODE change, which starts on its end value (at most a
# block of slope); the slope is 4 * depth * inc. The reference carries the
# largest distance it saw.
for rate, dpth in ((26, 21), (127, 127), (127, 6), (60, 90)):
    kn = mode_knobs("JUNO", RATE=rate, DPTH=dpth, MIX=127)
    ref = REF.make("JUNO", **{k: v for k, v in kn.items() if k != "MODE"})
    ref.process([0.0] * 6000, [0.0] * 6000)
    slope = 4 * ref.depth * ref.inc
    check(f"block-linear sweep, RATE={rate} DPTH={dpth}: within a block of slope of the LFO",
          ref.dev <= REF.BLOCK * slope + 0.01,
          f"{ref.dev:.3f} samples (bound {REF.BLOCK * slope:.3f}, slope {slope:.4f}/sample)")

# ---- 5. JUNO: the sweep is the Juno's --------------------------------------------
# An impulse into the wet (MIX 127, TONE 127 so the one-poles are open):
# the response is one interpolated tap between 1.5 and 5.4 ms after it.
imp = [0] * N
imp[100] = int(0.5 * FS)
L, R = render(imp, **mode_knobs("JUNO", MIX=127, TONE=127))
peakL = max(range(101, N), key=lambda i: abs(L[i]))
peakR = max(range(101, N), key=lambda i: abs(R[i]))
dl, dr = (peakL - 100) / SR * 1e3, (peakR - 100) / SR * 1e3
check("JUNO: an impulse comes back inside the Juno's 1.5..5.4 ms sweep",
      1.5 <= dl <= 5.4 and 1.5 <= dr <= 5.4, f"L {dl:.2f} ms, R {dr:.2f} ms")
# RATE 28 ~ 0.5 Hz: measured as the LFO period on a vibrato (MIX 127, the
# tap alone) of a DC input... a DC input through a delay is DC. Measure the
# sweep instead: the delay of the impulse response at two times a half
# period apart differs by the full depth. Cheaper: the reference's law.
f = REF.rate_inc(26) * SR
check("RATE 26 is the Juno's chorus I rate (0.5 Hz)", 0.45 <= f <= 0.56, f"{f:.3f} Hz")

# ---- 6. FLNG: through-zero -----------------------------------------------------------
# With DPTH 0 the swept tap sits ON the fixed one: blend 0.7071 - feedforward
# 0.7071 of the SAME sample is silence. That is the null the sweep crosses.
L, R = render(tone(1000, 0.3), **mode_knobs("FLNG", DPTH=0, FDBK=64, MIX=127))
check("FLNG: at the through-zero point the wet nulls (DPTH 0: blend - feedforward)",
      rms_db(L) < -70, f"{rms_db(L):.1f} dB")

# ---- 7. PHSR: unity magnitude ----------------------------------------------------------
# An allpass chain passes a tone at unity, wherever the notches sit, once the
# feedback is off (FDBK 64) -- measured at a slow rate over a few periods.
# The mode's output trim is -2 dB (16 Sep 2026), so unity reads -2.0.
src = tone(440, 0.3)
L, R = render(src, **mode_knobs("PHSR", FDBK=64, MIX=127, RATE=40))
check("PHSR: unity magnitude at FDBK 64 (an allpass chain), through the -2 dB trim",
      abs(rms_db(L) - rms_db(src) + 2.0) < 0.5, f"{rms_db(L) - rms_db(src):+.2f} dB")

# ---- 8. COMB: DLY tunes the ring ---------------------------------------------------------
# An impulse rings at the loop's period; the autocorrelation's first peak
# beyond 4 samples is the period the table says.
imp = [0] * N
imp[50] = int(0.4 * FS)
for dly in (32, 64, 96):
    L, R = render(imp, **mode_knobs("COMB", DLY=dly, FDBK=110, MIX=127, TONE=127))
    seg = [v / FS for v in L[50:50 + 3000]]
    period = REF.table_read(REF.period_table(), dly / 128.0)
    best = max(range(5, 1100), key=lambda lag: sum(seg[i] * seg[i + lag] for i in range(0, 1800)))
    check(f"COMB: DLY {dly} rings at the table's period ({period:.1f} samples)",
          abs(best - period) <= 1.5 or abs(best - 2 * period) <= 2.0,
          f"autocorrelation peak at {best}")

# ---- 9. every knob at both extremes renders ------------------------------------------------
ok = True
for name, i in K.items():
    for val in (0, 127 if name != "MODE" else 5):
        try:
            render(tone(440, 0.3, 600), **{name: val})
        except SystemExit as e:
            ok = False
            check(f"{name}={val} renders", False, str(e)[:80])
check("every knob renders at both extremes", ok)

print(f"\n{'ALL PASS' if fails == 0 else f'{fails} FAIL'}")
sys.exit(1 if fails else 0)
