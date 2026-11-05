#!/usr/bin/env python3
"""VIBRATO render gates -- the FX1-ONLY PROMISE, a hand-computable delay,
every shape against its float reference (modules/vibrato/vibrato_ref.py),
and the knob laws measured on the DSP's own output.

Gates:
  FX1 instance  -> MIX=0 is a bit-exact passthrough in every shape
  FX2 instance  -> bit-exact DRY at any setting, in every shape
  FX2 instance  -> dsp_host's -guard sees NO write outside the frame
  DEP 0         -> a pure 2-sample delay at MIX 127 (H = 0, the knot at 2):
                   a full-scale ramp of both signs, to within the MIX run's
                   last LSBs (the negative half proves no mpy became mpysu)
  every shape   -> the DSP render matches the reference on a stereo signal
                   (different L and R): max error and level agreement, at
                   defaults and at harder settings (SLEW, WID, depth caps)
  DEP           -> the pitch swing of a 1 kHz tone is DEP's cents (SINE, SQR)
  SQR           -> a two-note trill: the pitch sits at +-DEP most of the time
  SPD           -> the pitch modulation's period is SPD's law
  SHP change    -> the duck: no step larger than the signal's own (no click)
  every knob    -> renders at both extremes without dsp_host dying

    python3 tools/verify/verify_vibrato.py
"""
import math, pathlib, struct, subprocess, sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import send_probe
from remix import registry

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "modules" / "vibrato"))
import vibrato_ref as REF

MOD = registry.by_name("vibrato")
SEND = registry.by_name("send")
K = MOD.knob_map()
MEM = f"out/dsp/_audition_{MOD.name}_A.mem"
HOST = "vendor/dsp56300/build/source/dsp_host/dsp_host"
FXID = MOD.menu.fx2_id
FRAMES = REF.BLOCK
SR = 44100
FS = 8388607
TMP = pathlib.Path("out/_vbgate")
TMP.mkdir(parents=True, exist_ok=True)

# REBUILD THE DUMP, ALWAYS (a stale scratch image silently measures whatever
# held the id before).
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
SHAPES = REF.SHAPES


def params(**kw):
    v = list(DEFAULTS)
    for name, val in kw.items():
        v[K[name]] = val
    return v


def _run(inter, n, slot="fx1", guard=False, stereo=True, events=None, **kw):
    src = TMP / "vb_in.raw"
    src.write_bytes(b"".join(struct.pack("<i", m) for m in inter))
    out = TMP / "vb_out.raw"
    r7, alloc = ("1", "0") if slot == "fx1" else ("2", "1")
    cmd = [HOST, "-mem", MEM, "-init", f"{init:x}", "-proc", f"{proc:x}",
           "-inst", "1", "-r7", r7, "-alloc", alloc, "-inmask", "1",
           *(["-stereo"] if stereo else []),
           *(["-guard"] if guard else []),
           "-frames", str(FRAMES), "-blocks", str(-(-n // FRAMES)),
           "-in", str(src), "-out", str(out),
           "-params", ",".join(str(x) for x in params(**kw))]
    if events:
        # per-block automation: {sample: {knob: value}} -> block,p0..p11 lines,
        # each line the whole knob set from that block on (dsp_host -paramfile)
        cur = dict(kw)
        lines = []
        for at in sorted(events):
            cur.update(events[at])
            lines.append(f"{at // FRAMES}," + ",".join(str(x) for x in params(**cur)))
        pf = TMP / "vb_params.txt"
        pf.write_text("\n".join(lines) + "\n")
        cmd += ["-paramfile", str(pf)]
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


fails = 0
def check(label, ok, detail=""):
    global fails
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")
    fails += 0 if ok else 1


def tone(hz, amp, n):
    return [int(amp * FS * math.sin(2 * math.pi * hz * i / SR)) for i in range(n)]


def inst_freq(x, start):
    """(time, Hz) at each rising zero crossing, linearly interpolated"""
    out, last = [], None
    for i in range(max(start, 1), len(x)):
        if x[i - 1] < 0 <= x[i]:
            t = i - 1 + (-x[i - 1]) / (x[i] - x[i - 1])
            if last is not None:
                out.append(((t + last) / 2, SR / (t - last)))
            last = t
    return out


def cents(f, f0=1000.0):
    return 1200 * math.log2(f / f0)


# ---- 1. FX1: MIX=0 is a bit-exact passthrough in every shape -----------------
N = 6000
ramp = [int(round(-FS + 2 * FS * i / (N - 1))) for i in range(N)]
ok = True
for name, s in SHAPES.items():
    L, R = render(ramp, SHP=s, MIX=0, DEP=127, SLEW=60, WID=90)
    if L != ramp or R != ramp:
        ok = False
        check(f"FX1 MIX=0 passthrough in {name}", False,
              f"first diff at {next(i for i,(a,b) in enumerate(zip(L,ramp)) if a!=b)}")
check("FX1: MIX=0 is a bit-exact passthrough in all four shapes", ok)

# ---- 2. THE FX1-ONLY PROMISE: an FX2 instance is dry, whatever the knobs -----
ok = True
for name, s in SHAPES.items():
    L, R = render(ramp, slot="fx2", SHP=s, MIX=127, DEP=127, SPD=127, SLEW=127, WID=127)
    if L != ramp or R != ramp:
        ok = False
        check(f"FX2 instance is dry in {name}", False, "it processed the frame")
check("FX2 instance is a bit-exact DRY PASS in all four shapes, at any setting", ok)

# ---- 3. ... and writes nothing: dsp_host's guard --------------------------------
render(ramp, slot="fx2", guard=True, SHP=3, MIX=127, DEP=127)
g = _run.guard_out
check("FX2 instance: -guard reports nothing written over a loaded module",
      "nothing written" in g or "0 writes" in g or "guard: ok" in g.lower(),
      g.strip().splitlines()[-1] if g.strip() else "no guard output")
render(ramp, slot="fx1", guard=True, SHP=0, MIX=127, DEP=127, SPD=0)
g = _run.guard_out
check("FX1 instance: -guard reports nothing written over a loaded module",
      "nothing written" in g or "0 writes" in g or "guard: ok" in g.lower(),
      g.strip().splitlines()[-1] if g.strip() else "no guard output")

# ---- 4. DEP 0: a pure 2-sample delay ------------------------------------------
# H = 0, so every knot is 2 samples and the read's fraction is 0: the wet is
# the input two samples late. MIX 127 glides to 1.0 behind the 16-block
# fade-in and snaps onto it (verify the run sits on $7ffffe, m (1 - e) with
# e = 0), so once it has the output is the delayed input to a few LSBs.
N2 = 8000
saw = [int(round(FS * (2 * ((i * 7) % 300) / 299 - 1))) for i in range(N2)]
L, R = render(saw, DEP=0, MIX=127)
start = 5000
err = max(abs(L[i] - saw[i - 2]) for i in range(start, N2))
errR = max(abs(R[i] - saw[i - 2]) for i in range(start, N2))
check("DEP 0: the wet is the input exactly 2 samples late, both signs at full scale",
      err <= 32 and errR <= 32, f"max |out - in[n-2]| {max(err, errR)} LSB (bar 32)")

# ---- 5. every shape against its float reference -------------------------------
# Two measures. The DELAY: a slow full-scale ramp (both signs) through MIX
# 127 comes out as in[n - d(n)] exactly (a linear read of a straight line),
# so d(n) = (in - out) / slope, on the DSP's output and on the reference's;
# they must agree to 0.02 samples (80 Q11.12 LSBs: the slope's rounding and
# the per-block walk). The AUDIO: a stereo signal (different L and R); the
# bar scales with the signal's steepest slope, since a delay difference d
# costs d times the slope in amplitude.
N5 = 30000
def burst(n):
    out = [0.0] * n
    for i in range(500, 560):
        out[i] = 0.5 * math.sin(2 * math.pi * 2000 * i / SR)
    return out
Lf = [0.3 * math.sin(2 * math.pi * 1000 * i / SR) for i in range(N5)]
Rf = [0.2 * math.sin(2 * math.pi * 330 * i / SR) + b for i, b in enumerate(burst(N5))]
Li = [int(v * FS) for v in Lf]
Ri = [int(v * FS) for v in Rf]
Lq = [v / FS for v in Li]
Rq = [v / FS for v in Ri]

CASES = [
    ("SINE", {}),
    ("SINE", dict(SPD=127, DEP=127, WID=64)),
    ("SINE", dict(SPD=10, DEP=127, WID=127)),          # slow and deep: H at its cap
    ("TRI", {}),
    ("TRI", dict(SPD=110, DEP=100, SLEW=127, WID=32)),
    ("SQR", {}),
    ("SQR", dict(SPD=80, DEP=127, SLEW=40, WID=127)),
    ("RND", {}),
    ("RND", dict(SPD=120, DEP=127, WID=64)),
    ("RND", dict(SPD=100, DEP=90, SLEW=90, WID=127)),
    ("SINE", dict(MIX=64, DEP=40, SLEW=20)),
]
NR = 20000
RSLOPE = 1.6 / NR
rampx = [int((-0.8 + RSLOPE * i) * FS) for i in range(NR)]
rampq = [v / FS for v in rampx]
# the steepest slope in the signals, per sample: R's 2 kHz burst at 0.5
SLOPE = 0.5 * 2 * math.pi * 2000 / SR
DBAR = 0.02
BAR = DBAR * SLOPE
for name, over in CASES:
    kw = dict(SHP=SHAPES[name], **over)
    pv = params(**kw)
    dL, dR = render_stereo(rampx, rampx, **kw)
    ref = REF.Vibrato(**{n: pv[i] for n, i in K.items()})
    qL, qR = ref.process(rampq, rampq)
    de = max(max(abs((dL[i] / FS - qL[i]) / RSLOPE), abs((dR[i] / FS - qR[i]) / RSLOPE))
             for i in range(1100, NR))            # past the line's first fill
    L, R = render_stereo(Li, Ri, **kw)
    pv = params(**kw)
    ref = REF.Vibrato(**{n: pv[i] for n, i in K.items()})
    rL, rR = ref.process(Lq, Rq)
    e = max(max(abs(L[i] / FS - rL[i]), abs(R[i] / FS - rR[i])) for i in range(N5))
    lvl = lambda x: 20 * math.log10(max(1e-12, math.sqrt(sum(v * v for v in x) / len(x))))
    dl = [lvl([v / FS for v in L]), lvl([v / FS for v in R])]
    rl = [lvl(rL), lvl(rR)]
    check(f"{name} matches the reference ({', '.join(f'{k}={v}' for k, v in over.items()) or 'defaults'})",
          de < DBAR and e < BAR and max(abs(dl[0] - rl[0]), abs(dl[1] - rl[1])) < 0.05,
          f"delay within {de:.4f} samples (bar {DBAR}), audio max err {e:.2e} (bar {BAR:.1e}), "
          f"level {dl[0]:.2f}/{dl[1]:.2f} dB vs ref {rl[0]:.2f}/{rl[1]:.2f}")

# ---- 6. DEP and SQR: the pitch swing in cents, measured on the DSP's output ----
N6 = 44100
t1k = tone(1000, 0.5, N6)
for name, dep in (("SINE", 70), ("SINE", 127), ("SQR", 64), ("SQR", 127), ("TRI", 100)):
    L, _ = render(t1k, SHP=SHAPES[name], DEP=dep, SPD=94, MIX=127)
    fr = inst_freq(L, 8000)
    cs = [cents(f) for _, f in fr]
    want = REF.dep_cents(dep)
    down, up = REF.extremes(want)
    lo, hi = min(cs), max(cs)
    # a zero-crossing estimate averages over one 1 ms period, so a sine's peak
    # reads a little under; a square's plateau reads exactly
    tol = 0.04 * want + 0.5
    check(f"{name} DEP {dep}: the extremes are {2 * want:.1f} cents apart ({down:+.1f} .. {up:+.1f})",
          abs(hi - up) < tol and abs(lo - down) < tol and abs((hi - lo) - 2 * want) < 2 * tol,
          f"measured {lo:+.1f} .. {hi:+.1f} cents, {hi - lo:.1f} apart")
    if name == "SQR":
        near = sum(1 for c in cs if min(abs(c - up), abs(c - down)) < 0.1 * want + 0.5) / len(cs)
        check(f"SQR DEP {dep}: a two-note trill (the pitch sits at +-DEP)", near > 0.8,
              f"{100 * near:.0f}% of periods within 10% of +-{want:.1f} cents")

# ---- 7. SPD: the modulation's period ------------------------------------------
t1k3 = tone(1000, 0.5, 3 * N6)
for spd in (64, 94, 120):
    L, _ = render(t1k3, SHP=0, DEP=100, SPD=spd, MIX=127)
    fr = inst_freq(L, 4000)
    ts = [t for t, _ in fr]
    cs = [cents(f) for _, f in fr]
    ups = [ts[i] for i in range(1, len(cs)) if cs[i - 1] < 0 <= cs[i]]
    per = (ups[-1] - ups[0]) / (len(ups) - 1) if len(ups) > 2 else float("nan")
    hz = SR / per
    inc = int(REF.lookup(REF.INC, spd, floor=True))
    want = inc / REF.Q23 * SR
    check(f"SPD {spd}: the rate is the law's {want:.3f} Hz", abs(hz - want) < 0.01 * want,
          f"measured {hz:.3f} Hz over {len(ups) - 1} cycles")

# ---- 8. a SHP change ducks: no click -------------------------------------------
# a 200 Hz tone through SQR at full depth, switched to SINE then RND then TRI
# mid-render by -pword? dsp_host takes one parameter set per run, so the
# switch is checked on the reference (the same arithmetic) and the DSP's
# fade-in at init is checked here: the first block is the dry, the wet fades
# in over 16 blocks with no step larger than the tone's own.
t200 = tone(200, 0.5, 4000)
L, _ = render(t200, SHP=2, DEP=127, MIX=127)
steps = max(abs(L[i] - L[i - 1]) for i in range(1, 4000))
own = max(abs(t200[i] - t200[i - 1]) for i in range(1, 4000))
check("init: the wet fades in (no step larger than the tone's own)", steps <= 1.5 * own,
      f"largest step {steps / FS:.4f} vs the tone's {own / FS:.4f}")
ref = REF.Vibrato(SHP=2, DEP=127, MIX=127)
x = [0.5 * math.sin(2 * math.pi * 200 * i / SR) for i in range(20000)]
oL, _ = ref.process(x, x, changes={6000: dict(SHP=0), 11000: dict(SHP=3), 15000: dict(SHP=1)})
steps = max(abs(oL[i] - oL[i - 1]) for i in range(1, 20000))
own = max(abs(x[i] - x[i - 1]) for i in range(1, 20000))
check("SHP change (reference): the duck crosses with no step larger than the tone's own",
      steps <= 1.5 * own, f"largest step {steps:.4f} vs the tone's {own:.4f}")
# ... and on the DSP, with the knobs automated per block (-paramfile): SHP
# switched three times, then every continuous knob moved mid-render. The
# render must match the reference fed the same changes, and click nowhere.
N8 = 30000
x8L = [0.5 * math.sin(2 * math.pi * 200 * i / SR) for i in range(N8)]
x8R = [0.4 * math.sin(2 * math.pi * 330 * i / SR) for i in range(N8)]
i8L = [int(v * FS) for v in x8L]; i8R = [int(v * FS) for v in x8R]
q8L = [v / FS for v in i8L]; q8R = [v / FS for v in i8R]
EV = {4500: dict(SHP=0), 9000: dict(SHP=3), 13500: dict(SHP=1),
      18000: dict(SPD=120, DEP=110), 21000: dict(WID=100, SLEW=60),
      24000: dict(DEP=20, SPD=60), 27000: dict(MIX=60, SLEW=0)}
base = dict(SHP=2, DEP=127, MIX=127)
L, R = render_stereo(i8L, i8R, events=EV, **base)
pv = params(**base)
ref = REF.Vibrato(**{n: pv[i] for n, i in K.items()})
rL, rR = ref.process(q8L, q8R, changes={at: kw for at, kw in EV.items()})
slope8 = 0.4 * 2 * math.pi * 330 / SR
e = max(max(abs(L[i] / FS - rL[i]), abs(R[i] / FS - rR[i])) for i in range(N8))
check("knobs automated per block (SHP x3, SPD DEP WID SLEW MIX): the DSP matches the reference",
      e < DBAR * slope8, f"max err {e:.2e} (bar {DBAR * slope8:.1e})")
steps = max(max(abs(L[i] - L[i - 1]), abs(R[i] - R[i - 1])) for i in range(1, N8)) / FS
own = max(max(abs(x8L[i] - x8L[i - 1]), abs(x8R[i] - x8R[i - 1])) for i in range(1, N8))
check("knobs automated per block: no step larger than the tones' own (no click)",
      steps <= 1.5 * own, f"largest step {steps:.4f} vs the tones' {own:.4f}")

# ---- 8b. a knob jump cannot spike the pitch: the walk's limit ------------------
# SPD and DEP stepped in one block (a p-lock, a scene): H, and with it the
# centre 2 + H, moves by tens of samples. The delay, read off a ramp, must
# never move faster than the limit, 1.5 dev a sample (at least 0.006): the
# pitch stays within 1.5 DEP through the jump instead of spiking (61 % before
# the limit, at SPD 80 -> 120). And it must settle on the new shape.
NJ = 20000
RS = 1.6 / NJ
rj = [int((-0.8 + RS * i) * FS) for i in range(NJ)]
for label, base, ev in (("SPD 80 -> 120, DEP 127 -> 110", dict(SHP=2, SPD=80, DEP=127), {6000: dict(SPD=120, DEP=110)}),
                        ("SPD 120 -> 20 at DEP 127", dict(SHP=0, SPD=120, DEP=127), {6000: dict(SPD=20)}),
                        ("DEP 127 -> 10 at SPD 60", dict(SHP=1, SPD=60, DEP=127), {6000: dict(DEP=10)})):
    L, _ = render_stereo(rj, rj, events=ev, MIX=127, **base)
    d = [(rj[i] - L[i]) / FS / RS for i in range(NJ)]
    after = {**base, **ev[6000]}
    lim = max(1.5 * REF.dev_of(REF.dep_cents(max(base["DEP"], after["DEP"]))), REF.SLOPE_FLOOR)
    worst = max(abs(d[i] - d[i - 1]) for i in range(6000, 12000))
    check(f"knob jump {label}: the pitch stays within 1.5 DEP (the walk's limit)",
          worst <= lim * 1.05 + 0.002, f"largest delay step {worst:.4f} samples/sample (limit {lim:.4f})")
    pv = params(**base)
    ref = REF.Vibrato(**{n: pv[i] for n, i in K.items()})
    qL, _ = ref.process([v / FS for v in rj], [v / FS for v in rj], changes=ev)
    dq = [(rj[i] / FS - qL[i]) / RS for i in range(NJ)]
    de = max(abs(d[i] - dq[i]) for i in range(1100, NJ))
    check(f"knob jump {label}: the DSP's walk matches the reference", de < DBAR,
          f"delay within {de:.4f} samples (bar {DBAR})")

# ---- 9. every knob at both extremes ---------------------------------------------
ok = True
for name, p in K.items():
    hi = (MOD.params[p].count or 128) - 1
    for v in (0, hi):
        L, R = render(tone(440, 0.9, 3000), **{name: v})
        if any(abs(s) > FS for s in L + R):
            ok = False
check("every knob renders at both extremes without dsp_host dying", ok)

print()
print("ALL PASS" if fails == 0 else f"{fails} FAILED")
sys.exit(1 if fails else 0)
