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
import math, pathlib, re, struct, subprocess, sys

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


def _run(inter, n, slot="fx1", guard=False, stereo=True, events=None, pwords=None, **kw):
    src = TMP / "vb_in.raw"
    src.write_bytes(b"".join(struct.pack("<i", m) for m in inter))
    out = TMP / "vb_out.raw"
    r7, alloc = {"fx1": ("1", "0"), "fx2": ("2", "1"), "fx1b": ("4", "2")}[slot]
    cmd = [HOST, "-mem", MEM, "-init", f"{init:x}", "-proc", f"{proc:x}",
           "-inst", "1", "-r7", r7, "-alloc", alloc, "-inmask", "1",
           *(["-stereo"] if stereo else []),
           *(["-guard"] if guard else []),
           "-frames", str(FRAMES), "-blocks", str(-(-n // FRAMES)),
           "-in", str(src), "-out", str(out),
           "-params", ",".join(str(x) for x in params(**kw))]
    if pwords:
        cmd += ["-pword", ",".join(f"0:{off:x}={w:x}" for off, w in pwords)]
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
    m = re.search(r"r7 = X:0x([0-9a-fA-F]+)", r.stdout)
    _run.r7 = int(m.group(1), 16) if m else None
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


# the reference's noise seed is the DSP's: payload A's word eor this
# instance's r7 << 8, with r7 as dsp_host reports it
render([0] * FRAMES)
if _run.r7 is None:
    sys.exit("dsp_host did not report the instance's r7")
REF.DEFAULT_SEED = REF.lfsr_seed(_run.r7, "A")
print(f"instance r7 = X:0x{_run.r7:04x}, LFSR seed 0x{REF.DEFAULT_SEED:06x}")

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

# ---- 8c. two RND instances do not step in lockstep ------------------------------
# track 1's FX1 and track 2's FX1 (r7 0x6100 and 0x6400): different seeds,
# so different random pitches; each the reference with its own seed.
NI = 20000
ti = tone(440, 0.4, NI)
tq = [v / FS for v in ti]
outs = []
for slot in ("fx1", "fx1b"):
    L, _ = render(ti, slot=slot, SHP=3, SPD=110, DEP=127, MIX=127)
    seed = REF.lfsr_seed(_run.r7, "A")
    rL, _ = REF.Vibrato(**{n: params(SHP=3, SPD=110, DEP=127, MIX=127)[i] for n, i in K.items()},
                        seed=seed).process(tq, tq)
    e = max(abs(L[i] / FS - rL[i]) for i in range(NI))
    check(f"RND on r7 X:0x{_run.r7:04x}: matches the reference with its own seed (0x{seed:06x})",
          e < 2.8e-3, f"max err {e:.2e}")
    outs.append(L)
# both sit on the centre until the first half-cycle boundary draws (u = 0
# at init), so count from a full cycle in (SPD 110: ~4,800 samples)
same = sum(1 for a, b in zip(outs[0][8000:], outs[1][8000:]) if a == b) / (NI - 8000)
check("two RND instances step independently (different random pitches)", same < 0.01,
      f"{100 * same:.1f}% of samples identical")

# ---- 8d. knob words with an LFO's fraction (bits 15-8), as the unit sends them --
# dsp_host -params writes clean words; -pword writes the dirty ones. The
# continuous knobs read the fraction (the tables interpolate it, MIX and WID
# scale by it); SHP must mask it (a garbage companion byte too).
DIRTY = [(0x0, (80 << 16) | 0x8000), (0x1, (48 << 16) | 0x4000), (0x2, (40 << 16) | 0xC000),
         (0x3, (64 << 16) | 0x2000), (0x5, (100 << 16) | 0x8000), (0xC, (2 << 16) | 0x5500)]
kfrac = dict(SPD=80.5, DEP=48.25, SLEW=40.75, WID=64.125, MIX=100.5, SHP=2)
L, R = render_stereo(rampx, rampx, pwords=DIRTY)
ref = REF.Vibrato(**kfrac)
qL, qR = ref.process(rampq, rampq)
de = max(max(abs((L[i] / FS - qL[i]) / RSLOPE), abs((R[i] / FS - qR[i]) / RSLOPE)) for i in range(1100, NR))
check("LFO-dirty knob words: the fraction reaches SPD DEP SLEW WID MIX, SHP masks it",
      de < DBAR, f"delay within {de:.4f} samples of the reference at {kfrac}")
L2, _ = render_stereo(rampx, rampx, pwords=DIRTY[:5] + [(0xC, 2 << 16)])
check("LFO-dirty SHP word: the same output as the clean word", L2 == L)

# ---- 9. every knob at both extremes ---------------------------------------------
ok = True
for name, p in K.items():
    hi = (MOD.params[p].count or 128) - 1
    for v in (0, hi):
        L, R = render(tone(440, 0.9, 3000), **{name: v})
        if any(abs(s) > FS for s in L + R):
            ok = False
check("every knob renders at both extremes without dsp_host dying", ok)

# ---- 10. SLOTS = FX1+FX2: an FX2 instance runs live, exactly as FX1 does -------
# The remix vibrato-fx2 pins the build setting. The same input and knobs at
# track 1's FX1 (r7 0x6100, Y:0x1000), track 1's FX2 (r7 0x6200, Y:0x4000)
# and track 3's FX2 (r7 0x6800, the shared window: Y:0x30000 on payload A):
# SINE, TRI and SQR bit-identical across the three and not the dry; RND each
# the reference with its own seed (r7 differs); the guard clean on every
# slot, the shared window policed too.
import os
FX2_MEM = "out/dsp/_vibrato_fx2_A.mem"
env = dict(os.environ, REMIX="vibrato-fx2", XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
r = subprocess.run([sys.executable, "tools/build/build_bus.py"], env=env, capture_output=True, text=True)
if r.returncode:
    sys.exit(f"building vibrato-fx2 failed:\n{(r.stdout + r.stderr)[-1500:]}")
send_probe.dump_mem("out/mainos_bus.bin", FX2_MEM, "A")
i2, p2 = send_probe.entry_points(FX2_MEM, FXID)
SLOTS2 = {"track 1 FX1": ("1", "0"), "track 1 FX2": ("2", "1"), "track 3 FX2": ("8", "5")}


def run_slot(slot, samples, guard=False, **kw):
    r7, alloc = SLOTS2[slot]
    src = TMP / "fx2_in.raw"
    src.write_bytes(b"".join(struct.pack("<i", m) for m in samples))
    out = TMP / "fx2_out.raw"
    cmd = [HOST, "-mem", FX2_MEM, "-init", f"{i2:x}", "-proc", f"{p2:x}", "-inst", "1", "-r7", r7,
           "-alloc", alloc, "-inmask", "1", "-frames", str(FRAMES), "-blocks", str(-(-len(samples) // FRAMES)),
           "-in", str(src), "-out", str(out), "-params", ",".join(str(x) for x in params(**kw)),
           *(["-guard", "-guard-shared"] if guard else [])]
    q = subprocess.run(cmd, capture_output=True, text=True)
    if q.returncode:
        sys.exit(f"dsp_host failed ({slot}, {kw}):\n{q.stdout}\n{q.stderr}")
    m = re.search(r"r7 = X:0x([0-9a-fA-F]+)", q.stdout)
    d = out.read_bytes()
    w = struct.unpack(f"<{len(d)//4}i", d)
    return list(w[0::2])[:len(samples)], int(m.group(1), 16), q.stdout + q.stderr


N10 = 12000
t10 = tone(330, 0.4, N10)
for name in ("SINE", "TRI", "SQR"):
    kw = dict(SHP=SHAPES[name], DEP=127, SPD=110, SLEW=40, WID=64, MIX=127)
    outs = {slot: run_slot(slot, t10, **kw)[0] for slot in SLOTS2}
    a = outs["track 1 FX1"]
    check(f"FX1+FX2 build, {name}: FX2 (Y:0x4000 and the shared window) bit-identical to FX1, and live",
          all(o == a for o in outs.values()) and a != t10,
          f"{sum(1 for o in outs.values() if o == a)}/3 identical, wet differs from dry: {a != t10}")
tq10 = [v / FS for v in t10]
for slot in SLOTS2:
    kw = dict(SHP=3, DEP=127, SPD=110, MIX=127)
    L, r7v, _ = run_slot(slot, t10, **kw)
    rL, _ = REF.Vibrato(**{n: params(**kw)[i] for n, i in K.items()},
                        seed=REF.lfsr_seed(r7v, "A")).process(tq10, tq10)
    e = max(abs(L[i] / FS - rL[i]) for i in range(N10))
    check(f"FX1+FX2 build, RND on {slot} (r7 X:0x{r7v:04x}): the reference with its own seed",
          e < 2.8e-3, f"max err {e:.2e}")
for slot in SLOTS2:
    _, _, g = run_slot(slot, t10, guard=True, SHP=3, DEP=127, SPD=127, SLEW=127, WID=127, MIX=127)
    clean = "nothing written" in g or "0 writes" in g or "guard: ok" in g.lower()
    check(f"FX1+FX2 build, {slot}: -guard (and the shared window) sees no stray write", clean,
          ([l for l in g.strip().splitlines() if "guard" in l.lower()] or ["no guard output"])[-1])

# ---- 11. a full core: eight instances at once (FX1 and FX2 of four tracks) -----
# Four tracks on one core, VIBRATO on both slots of each: eight state blocks
# (r7 0x6100 .. 0x6b00), eight buffers (the four FX1 slots, Y:0x4000/0x8000
# and the shared window's pair), each instance called in turn every block as
# the dispatcher does. SQR at its dearest: every instance bit-identical to the
# single-instance render (no instance reaches another's state or line); RND:
# each the reference with its own seed; the guard clean throughout.
R7S = [1, 2, 4, 5, 7, 8, 10, 11]
ALLOCS = [0, 1, 2, 3, 4, 5, 6, 7]


def run_core(samples, guard=False, **kw):
    src = TMP / "core_in.raw"
    src.write_bytes(b"".join(struct.pack("<i", m) for m in samples))
    out = TMP / "core_out.raw"
    cmd = [HOST, "-mem", FX2_MEM, "-init", f"{i2:x}", "-proc", f"{p2:x}", "-inst", "8",
           "-r7", ",".join(map(str, R7S)), "-alloc", ",".join(map(str, ALLOCS)),
           "-frames", str(FRAMES), "-blocks", str(-(-len(samples) // FRAMES)),
           "-in", str(src), "-out", str(out), "-params", ",".join(str(x) for x in params(**kw)),
           *(["-guard", "-guard-shared"] if guard else [])]
    q = subprocess.run(cmd, capture_output=True, text=True)
    if q.returncode:
        sys.exit(f"dsp_host failed (eight instances, {kw}):\n{q.stdout}\n{q.stderr}")
    r7s = [int(m, 16) for m in re.findall(r"r7 = X:0x([0-9a-fA-F]+)", q.stdout)]
    outs = []
    for k in range(8):
        d = pathlib.Path(str(out) + (f".i{k}" if k else "")).read_bytes()
        w = struct.unpack(f"<{len(d)//4}i", d)
        outs.append(list(w[0::2])[:len(samples)])
    return outs, r7s, q.stdout + q.stderr


kw = dict(SHP=2, DEP=127, SPD=127, SLEW=127, WID=127, MIX=127)
single = run_slot("track 1 FX1", t10, **kw)[0]
outs, r7s, g = run_core(t10, guard=True, **kw)
same = sum(1 for o in outs if o == single)
check("eight instances on one core (FX1 + FX2 of four tracks), SQR dearest: each bit-identical to one alone",
      same == 8 and len(set(r7s)) == 8, f"{same}/8 identical, r7 {', '.join(hex(v) for v in r7s)}")
clean = "nothing written" in g or "0 writes" in g or "guard: ok" in g.lower()
check("eight instances on one core: -guard (and the shared window) sees no stray write", clean,
      ([l for l in g.strip().splitlines() if "guard" in l.lower()] or ["no guard output"])[-1])
kw = dict(SHP=3, DEP=127, SPD=110, MIX=127)
outs, r7s, _ = run_core(t10, **kw)
worst = 0.0
for o, r7v in zip(outs, r7s):
    rL, _ = REF.Vibrato(**{n: params(**kw)[i] for n, i in K.items()},
                        seed=REF.lfsr_seed(r7v, "A")).process(tq10, tq10)
    worst = max(worst, max(abs(o[i] / FS - rL[i]) for i in range(N10)))
distinct = len({tuple(o[6000:]) for o in outs})
check("eight instances on one core, RND: each the reference with its own seed, all eight different",
      worst < 2.8e-3 and distinct == 8, f"max err {worst:.2e}, {distinct}/8 distinct")

print()
print("ALL PASS" if fails == 0 else f"{fails} FAILED")
sys.exit(1 if fails else 0)
