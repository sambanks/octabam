#!/usr/bin/env python3
"""TUNED COMB render gates -- the FX1-ONLY PROMISE, the DSP against its float
reference (modules/tuned-comb/tuned_comb_ref.py) on both payloads, and the
point of the module measured on the DSP's own output: the pitch.

Gates:
  FX1 instance  -> MIX=0 is a bit-exact passthrough at any setting
  FX2 instance  -> bit-exact DRY at any setting
  FX1 and FX2   -> dsp_host's -guard sees NO write outside the instance's
                   lines (both FX1 bases the gates use, and the FX2 slot)
  reference     -> the DSP render matches the reference on a stereo signal
                   (different L and R), at defaults and harder settings, FB
                   both sides of 64, FINE with an LFO fraction, on payload A
                   and payload B (the stock sine's address in each)
  pitch         -> an impulse's ring is the note PTCH and FINE name, in tune
                   to 0.5 cents (FB < 64: an octave down), at every LP that
                   leaves it ringing; and the uncompensated loop (stock's)
                   would have been flat by what the module removes
  knob moves    -> PTCH, FINE, LP and FB jumping and held: the DSP follows
                   the reference block by block (the change gate, the cold
                   start, the warm steps, the freeze)
  decay         -> FB is a decay time: an impulse's ring has the law's T60
                   at every note, with LP open and closed (where the gain is
                   not capped)
  DC            -> after a note dies, what is left is at most 40 LSB (the
                   loop's rounding floor), no DC the loop holds; and a DC at
                   the input never reaches the loop (its blocker)
  every knob    -> renders at both extremes without dsp_host dying
  SLOTS=FX1+FX2 -> an FX2 instance runs live, bit-identical to FX1; eight
                   instances on one core each bit-identical to one alone,
                   the guard clean throughout

    python3 tools/verify/verify_tuned_comb.py
"""
import math, os, pathlib, re, struct, subprocess, sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import send_probe
from remix import registry

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "modules" / "tuned-comb"))
import tuned_comb_ref as REF

MOD = registry.by_name("tuned-comb")
SEND = registry.by_name("send")
K = MOD.knob_map()
HOST = "vendor/dsp56300/build/source/dsp_host/dsp_host"
FXID = MOD.menu.fx2_id
FRAMES = REF.BLOCK
SR = 44100
FS = 8388607
TMP = pathlib.Path("out/_tcgate")
TMP.mkdir(parents=True, exist_ok=True)
MEMS = {p: f"out/dsp/_audition_{MOD.name}_{p}.mem" for p in ("A", "B")}

# REBUILD THE DUMPS, ALWAYS (a stale scratch image silently measures whatever
# held the id before). audition.py builds both payloads' dumps; its render
# needs a wav, and the dumps are what the gates read.
for m in MEMS.values():
    pathlib.Path(m).unlink(missing_ok=True)
subprocess.run([sys.executable, "tools/remix/audition.py", MOD.name,
                "out/dry/drums_110.wav"], capture_output=True)
for m in MEMS.values():
    if not pathlib.Path(m).exists():
        sys.exit(f"no {m} -- build it first:\n"
                 f"  python3 tools/remix/audition.py {MOD.name} out/dry/drums_110.wav")

ENTRY = {}
for p, m in MEMS.items():
    ENTRY[p] = send_probe.entry_points(m, FXID)
    if ENTRY[p] == send_probe.entry_points(m, SEND.menu.fx2_id):
        sys.exit(f"fx id 0x{FXID:02x} resolves to SEND's entry points in payload {p} -- "
                 f"{MOD.name} is NOT in this dump")
    print(f"payload {p}: init=P:0x{ENTRY[p][0]:04x} proc=P:0x{ENTRY[p][1]:04x}")

DEFAULTS = [(p.default or 0) for p in MOD.params]
SLOTS = {"fx1": ("1", "0"), "fx2": ("2", "1"), "fx1b": ("4", "2")}


def params(**kw):
    v = list(DEFAULTS)
    for name, val in kw.items():
        v[K[name]] = int(val)
    return v


def kword(v):
    """a knob value with an LFO fraction as its word (dsp_host -pword)"""
    return int(round(v * 65536)) & 0x7FFF00


def _run(Ls, Rs, slot="fx1", guard=False, events=None, payload="A", mem=None, entry=None, track=None, **kw):
    n = len(Ls)
    src = TMP / "tc_in.raw"
    src.write_bytes(b"".join(struct.pack("<ii", a, b) for a, b in zip(Ls, Rs)))
    out = TMP / "tc_out.raw"
    r7, alloc = SLOTS[slot]
    init, proc = entry or ENTRY[payload]
    frac = {k: v for k, v in kw.items() if float(v) != int(v)}
    cmd = [HOST, "-mem", mem or MEMS[payload], "-init", f"{init:x}", "-proc", f"{proc:x}",
           "-inst", "1", "-r7", r7, "-alloc", alloc, "-inmask", "1", "-stereo",
           *(["-guard"] if guard else []),
           "-frames", str(FRAMES), "-blocks", str(-(-n // FRAMES)),
           "-in", str(src), "-out", str(out),
           "-params", ",".join(str(x) for x in params(**kw))]
    if frac:
        cmd += ["-pword", ",".join(f"0:{K[k]:x}={kword(v):x}" for k, v in frac.items())]
    if events:
        cur = {k: int(v) for k, v in kw.items()}
        lines = []
        for at in sorted(events):
            cur.update(events[at])
            lines.append(f"{at // FRAMES}," + ",".join(str(x) for x in params(**cur)))
        pf = TMP / "tc_params.txt"
        pf.write_text("\n".join(lines) + "\n")
        cmd += ["-paramfile", str(pf)]
    if track:
        cmd += ["-track", ",".join(f"{o:x}" for o in track), "-trackout", str(TMP / "tc_track.txt")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"dsp_host failed for {kw}:\n{r.stdout}\n{r.stderr}")
    _run.log = r.stdout + r.stderr
    if track:
        _run.track = [[int(v) for v in l.split()[1:]] for l in (TMP / "tc_track.txt").read_text().splitlines()]
    d = out.read_bytes()
    w = struct.unpack(f"<{len(d)//4}i", d)
    return list(w[0::2])[:n], list(w[1::2])[:n]


fails = 0
def check(label, ok, detail=""):
    global fails
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")
    fails += 0 if ok else 1


def guard_clean(log):
    return "nothing written" in log or "0 writes" in log or "guard: ok" in log.lower()


def guard_line(log):
    return ([l for l in log.strip().splitlines() if "guard" in l.lower()] or ["no guard output"])[-1]


def noise(n, seed, amp=0.3):
    x, out = seed, []
    for _ in range(n):
        x = (1103515245 * x + 12345) & 0x7FFFFFFF
        out.append(int(amp * FS * (x / 0x3FFFFFFF - 1)))
    return out


def ref_render(Ls, Rs, events=None, **kw):
    k = dict(REF.TunedComb().k)
    k.update(kw)
    c = REF.TunedComb(**k)
    ch = None
    if events:
        ch = {at: dict(v) for at, v in events.items()}
    return c.process([v / FS for v in Ls], [v / FS for v in Rs], changes=ch)


def max_err(dsp, ref):
    return max(abs(a / FS - b) for a, b in zip(dsp, ref))


# ---- 1. FX1: MIX=0 is a bit-exact passthrough --------------------------------
N = 4500
ramp = [int(round(-FS + 2 * FS * i / (N - 1))) for i in range(N)]
ok = True
for kw in (dict(), dict(PTCH=95, LP=0, FB=127), dict(PTCH=0, LP=127, FB=0, FINE=0)):
    L, R = _run(ramp, ramp[::-1], MIX=0, **kw)
    if L != ramp or R != ramp[::-1]:
        ok = False
check("FX1: MIX=0 is a bit-exact passthrough (three settings, L and R different)", ok)

# ---- 2. THE FX1-ONLY PROMISE: an FX2 instance is dry, whatever the knobs -----
L, R = _run(ramp, ramp[::-1], slot="fx2", MIX=127, PTCH=60, LP=40, FB=127)
check("FX2 instance is a bit-exact DRY PASS at any setting", L == ramp and R == ramp[::-1])

# ---- 3. ... and nothing is written outside the lines -------------------------
for slot in ("fx2", "fx1", "fx1b"):
    _run(ramp, ramp, slot=slot, guard=True, MIX=127, PTCH=0, LP=60, FB=127)
    check(f"{slot.upper()} instance: -guard reports nothing written over a loaded module",
          guard_clean(_run.log), guard_line(_run.log))

# ---- 4. the DSP against the reference, both payloads -------------------------
N4 = 15 * 200
nl, nr = noise(N4, 1), noise(N4, 2)
# short decays: over a long ring a 1e-3-sample difference in L becomes a large
# sample error (the block's L and g are compared directly below)
CASES = [dict(PTCH=26, LP=127, FB=67, MIX=127),
         dict(PTCH=38, LP=60, FB=68, MIX=127),
         dict(PTCH=62, LP=90, FB=61, MIX=127),
         dict(PTCH=0, FINE=0, LP=10, FB=80, MIX=127),
         dict(PTCH=86, FINE=127, LP=110, FB=63, MIX=127),
         dict(PTCH=50, FINE=80.5, LP=75.25, FB=66.75, MIX=64)]
for payload in ("A", "B"):
    worst = 0.0
    for kw in CASES:
        L, R = _run(nl, nr, payload=payload, **kw)
        rL, rR = ref_render(nl, nr, **kw)
        worst = max(worst, max_err(L, rL), max_err(R, rR))
    check(f"payload {payload}: the DSP render matches the reference (six settings, stereo, LFO fractions)",
          worst < 3e-3, f"max err {worst:.2e}")


# ---- 4b. the block's L, g and cap: the DSP's solve is the reference's ---------
def s24(v):
    return v - (1 << 24) if v & 0x800000 else v


def state_compare(events, first, n):
    """per block: L (Q12.11 at $1a, clamped as the loop does), g ($06), the
    cap flag ($2d), against the reference's block; -> (dL max, dg max, flags equal)"""
    x = noise(n, 7, 0.05)
    _run(x, x, events=events, track=(0x1a, 0x06, 0x2d), **first)
    rows = _run.track
    c = REF.TunedComb(**{**REF.TunedComb().k, **first})
    trace = []
    for b in range(len(rows)):
        if events and b * FRAMES in events:
            c.set(**events[b * FRAMES])
        c.block()
        trace.append((c.trace[-1], c.g, int(c.capped)))
    dL = dg = 0.0
    same = True
    for (Lw, gw, cw), (Lr, gr, cr) in zip(rows, trace):
        Ld = min(REF.LMAX, max(REF.LMIN, s24(Lw) / 2048))
        # samples or cents, whichever is looser (1 LSB is 1/2048 sample; at
        # A#0 a thousandth of a sample is 0.001 cent)
        dL = max(dL, min(abs(Ld - Lr) / 0.004, abs(Ld - Lr) / Lr * 1731.2 / 0.1))
        dg = max(dg, abs(s24(gw) / 2 ** 23 - gr))
        same &= (cw == cr)
    return dL, dg, same


rnd0 = __import__("random").Random(3)
dLw = dgw = 0.0
allsame = True
for _ in range(40):
    kw = dict(PTCH=rnd0.randrange(96), FINE=rnd0.randrange(128), LP=rnd0.randrange(128),
              FB=rnd0.randrange(128), MIX=127)
    dL, dg, same = state_compare(None, kw, FRAMES * 12)
    dLw, dgw, allsame = max(dLw, dL), max(dgw, dg), allsame and same
check("40 random settings: the DSP's loop length, gain and cap are the reference's, block by block",
      dLw < 1 and dgw < 3e-4 and allsame,
      f"L within {dLw:.2f} of the bound (0.004 samples or 0.1 c), g within {dgw:.1e}, "
      f"iterating flags equal: {allsame}")

# ---- 5. the pitch: an impulse's ring is the named note -----------------------
def ring_cents(x, f_target):
    """the ring's fundamental against f_target: the Hann-windowed spectrum's
    peak within a third of an octave of it, found by a grid of 48 points and
    a golden-section search (pure Python: one DFT bin per evaluation)"""
    # the ring only, to 80 dB under its peak: once it has died, the loop's
    # rounding floor (a few LSB, at the loop's own resonance) is all that is
    # left, and over a long window that coherent line pulls the peak
    top = max(abs(v) for v in x)
    last = max(i for i, v in enumerate(x) if abs(v) > top * 1e-4)
    x = x[:max(last + 1, 2048)]
    n = len(x)
    win = [v * (0.5 - 0.5 * math.cos(2 * math.pi * i / (n - 1))) for i, v in enumerate(x)]

    def mag(f):
        w = 2 * math.pi * f / SR
        c, s_ = math.cos(w), math.sin(w)
        re = im = 0.0
        cr, ci = 1.0, 0.0
        for v in win:
            re += v * cr
            im -= v * ci
            cr, ci = cr * c - ci * s_, ci * c + cr * s_
        return re * re + im * im

    lo, hi = f_target * 2 ** (-1 / 6), f_target * 2 ** (1 / 6)
    grid = [lo * (hi / lo) ** (i / 47) for i in range(48)]
    k = max(range(48), key=lambda i: mag(grid[i]))
    a, b = grid[max(0, k - 1)], grid[min(47, k + 1)]
    g = (math.sqrt(5) - 1) / 2
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = mag(c), mag(d)
    for _ in range(40):
        if fc > fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = mag(c)
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = mag(d)
    return 1200 * math.log2((a + b) / 2 / f_target)


def alive(s, lk, fk):
    g = REF.settle(s, lk, fk)[2]
    b = REF.knob_b(lk)
    w = 2 * math.pi * REF.F_A_SHARP_0 * 2 ** (s / 12) / SR / (2 if g < 0 else 1)
    return abs(g) * b / abs(1 - (1 - b) * complex(math.cos(w), -math.sin(w)))


N5 = 20000
imp = [0] * N5
imp[0] = FS // 2
worst, flat, n5 = 0.0, [], 0
for pk, tk, lk, fk in [(2, 64, 60, 126), (14, 64, 30, 127), (26, 64, 40, 127), (26, 64, 50, 1),
                       (38, 64, 70, 127), (38, 40, 70, 127), (50, 64, 60, 124), (62, 64, 90, 124),
                       (62, 90, 90, 3), (74, 64, 100, 126), (86, 64, 110, 127), (92, 64, 127, 127),
                       (95, 64, 120, 127), (95, 64, 127, 0), (47, 64, 127, 100), (47, 127, 127, 10)]:
    s = pk + (tk - 64) / 64
    if alive(s, lk, fk) < 0.5:
        continue
    L, _ = _run(imp, imp, PTCH=pk, FINE=tk, LP=lk, FB=fk, MIX=127)
    f0 = REF.F_A_SHARP_0 * 2 ** (s / 12) / (2 if fk < 64 else 1)
    c = ring_cents(L, f0)
    if os.environ.get("TC_VERBOSE"):
        print(f"    PTCH {pk} FINE {tk} LP {lk} FB {fk}: {c:+.2f} c")
    worst = max(worst, abs(c))
    n5 += 1
    # what stock's loop (SR/f0 with the lowpass inside, no correction) would sound
    c0 = REF.setup(s, lk, fk)
    psi = REF.atan2c(c0["a"] * c0["sn"], 1 - c0["a"] * c0["cs"])   # cycles, on the circle
    flat.append(1200 * math.log2(1 / (1 + c0["kk"] * psi)))       # SR/f0 + the lowpass's lag
check(f"an impulse rings at the named note, within 0.5 cents ({n5} settings, both FB polarities, "
      f"A#0 to A8, FINE off centre)", worst < 0.5,
      f"worst {worst:.2f} c; stock's loop would be flat by up to {-min(flat):.0f} c here")

# ---- 6. knob moves: the change gate, the cold start, the warm steps ----------
import random
rnd = random.Random(11)
events, at = {}, 0
for _ in range(14):
    events[at] = dict(PTCH=rnd.randrange(96), FINE=rnd.randrange(128), LP=rnd.randrange(128),
                      FB=rnd.randrange(128), MIX=127)
    at += FRAMES * rnd.randrange(1, 12)
N6 = at + FRAMES * 8
dL, dg, same = state_compare(events, events[0], N6)
check("PTCH, FINE, LP and FB jumping and held (14 moves): the DSP's solve follows the reference block by block "
      "(the closed form, the iteration's cold start and warm steps, the freeze)",
      dL < 1 and dg < 3e-4 and same,
      f"L within {dL:.2f} of the bound (0.004 samples or 0.1 c), g within {dg:.1e}, iterating flags equal: {same}")

# ---- 6c. knobs under modulation: the warm change ------------------------------
# An LFO or a slide moves a knob a little every block: a small change from a
# block that was iterating takes one warm step from the last lr (not a cold
# start and two). The DSP follows the reference; the pitch tracks the settled
# loop.
def lfo_events(nb, f):
    ev = {}
    for b in range(nb):
        ev[b * FRAMES] = f(b)
    return ev
NB = 160
mods = {
    "LP swept (8 Hz, LP 4..124, FB 96)": lambda b: dict(PTCH=30, FINE=64, LP=64 + 60 * math.sin(2 * math.pi * 8 * b * FRAMES / 44100), FB=96, MIX=127),
    "FINE swept (6 Hz, +-40, LP 40, FB 120)": lambda b: dict(PTCH=55, FINE=64 + 40 * math.sin(2 * math.pi * 6 * b * FRAMES / 44100), LP=40, FB=120, MIX=127),
    "FB swept across 64 (LP 30)": lambda b: dict(PTCH=40, FINE=64, LP=30, FB=64 + 20 * math.sin(2 * math.pi * 5 * b * FRAMES / 44100), MIX=127),
    "PTCH sliding a semitone every other block (LP 20, FB 20)": lambda b: dict(PTCH=60 - abs(40 - (b // 2) % 80), FINE=64, LP=20, FB=20, MIX=127),
}
worst_c, dLm, dgm, samem = {}, 0.0, 0.0, True
for name, f in mods.items():
    ev = lfo_events(NB, f)
    for b in list(ev):
        ev[b] = {k: int(round(v)) for k, v in ev[b].items()}   # (a paramfile carries whole knobs)
    dL, dg, same = state_compare(ev, ev[0], NB * FRAMES)
    dLm, dgm, samem = max(dLm, dL), max(dgm, dg), samem and same
    c = REF.TunedComb(**ev[0])
    w = m = 0.0
    for b in range(NB):
        c.set(**ev[b * FRAMES]); c.block()
        if b < 4:
            continue
        k = c.Lk                       # the knobs this block's L is solved for (a split lags a block)
        s = min(REF.NOTES - 1, k["PTCH"]) + (k["FINE"] - 64) / 64
        Lt = REF.settle(s, k["LP"], k["FB"])[0]
        e = abs(1200 * math.log2(Lt / c.trace[-1]))
        w, m = max(w, e), m + e / (NB - 4)
    worst_c[name] = (w, m)
check("knobs modulated every block (LP, FINE and FB swept, PTCH sliding): the DSP's warm changes follow the "
      "reference block by block", dLm < 1 and dgm < 3e-4 and samem,
      f"L within {dLm:.2f} of the bound, g within {dgm:.1e}, iterating flags equal: {samem}")
smooth = max(w for n, (w, m) in worst_c.items() if not n.startswith("PTCH"))
check("... the loop tracks the settled one under a swept LP, FINE or FB", smooth < 1, f"worst {smooth:.2f} c")
(w, m), = [v for n, v in worst_c.items() if n.startswith("PTCH")]
check("... and under PTCH sliding by semitones (LP 20, FB 20: the slowest iteration) the block after a step is "
      "as the cold start's (21 c there), the mean under 1.5 c", w < 25 and m < 1.5, f"worst {w:.1f} c, mean {m:.2f} c")

# ---- 6b. FB is a decay time: T60 = 0.05 s x 600^(|FB - 64|/63) at every note -
def t60(x, period):
    """the ring's T60 from its envelope: block RMS in dB over two periods (at
    least 512 samples), a least-squares line from 15 dB to 55 dB under the
    peak block (late enough that the partials LP takes faster have gone)"""
    w = max(512, int(2 * period))
    db = []
    for i in range(0, len(x) - w, w):
        e = sum(v * v for v in x[i:i + w]) / w
        db.append(10 * math.log10(e + 1e-30))
    top = max(db)
    k0 = db.index(top)
    pts = [(i * w / SR, d) for i, d in enumerate(db) if i > k0 and top - 55 < d < top - 15]
    n = len(pts)
    if n < 4:
        return None
    mt = sum(p[0] for p in pts) / n
    md = sum(p[1] for p in pts) / n
    slope = sum((p[0] - mt) * (p[1] - md) for p in pts) / sum((p[0] - mt) ** 2 for p in pts)
    return -60 / slope


def ring_t60(pk, lk, fk):
    want = REF.T60_MIN * REF.T60_SPAN ** min(1, abs(fk - 64) / 63)
    n = int(SR * want * 1.3) + 16384
    x = [0] * n
    x[0] = FS // 2
    L, _ = _run(x, x, PTCH=pk, LP=lk, FB=fk, MIX=127)
    period = SR / (REF.F_A_SHARP_0 * 2 ** (pk / 12)) * (2 if fk < 64 else 1)
    got = t60([v / FS for v in L], period)
    if os.environ.get("TC_VERBOSE"):
        print(f"    PTCH {pk} LP {lk} FB {fk}: T60 {got} s, the law {want:.3f} s")
    return got, want


# LP open: the law at every note (where the gain is not at G_MAX)
worst, n6b = 0.0, 0
# A#0 to C7: at C8 and above, with short decays, the Hermite's loss off the
# unit circle (the ring's pole is inside it) leaves the decay up to 20 % long
for pk, fk in [(14, 90), (38, 90), (62, 90), (74, 75), (26, 40), (50, 80), (74, 50), (2, 100)]:
    _, _, g, _ = REF.settle(pk, 127, fk)
    if abs(g) >= REF.G_MAX:
        continue
    got, want = ring_t60(pk, 127, fk)
    if got is None:
        continue
    worst = max(worst, abs(got / want - 1))
    n6b += 1
check(f"FB is a decay time: with LP open the ring's T60 is the law's at every note to C7 "
      f"({n6b} settings, both polarities)", worst < 0.1 and n6b >= 6, f"worst {100 * worst:.1f} %")
# LP closed only ever shortens it
longest = 0.0
for pk, lk, fk in [(38, 70, 85), (62, 100, 46), (26, 40, 100), (74, 90, 80)]:
    got, want = ring_t60(pk, lk, fk)
    if got is not None:
        longest = max(longest, got / want)
check("LP closed shortens the decay and never lengthens it (the DC mode never outlasts the note)",
      longest < 1.05, f"longest {longest:.2f} x the law")

# ---- 7. DC: nothing the loop holds once a note has died ----------------------
worst = 0
for kw in (dict(PTCH=50, LP=127, FB=75), dict(PTCH=86, LP=110, FB=66), dict(PTCH=74, LP=100, FB=60),
           dict(PTCH=26, LP=127, FB=56)):
    L, _ = _run(imp + [0] * 10000, imp + [0] * 10000, MIX=127, **kw)
    worst = max(worst, max(abs(v) for v in L[-4000:]))
check("after a note dies, at most 16 LSB remain (the loop's sum truncated toward zero: no limit cycle)", worst <= 16,
      f"largest {worst} LSB")
# LP closed with the gain near G_MAX: the gain is the law's with LP open, so the
# comb's DC mode (which LP leaves alone) dies with the note: a second on, under -70 dBFS
worst = 0
for kw in (dict(PTCH=50, LP=60, FB=85), dict(PTCH=26, LP=40, FB=90), dict(PTCH=86, LP=110, FB=80)):
    want = REF.T60_MIN * REF.T60_SPAN ** min(1, abs(kw["FB"] - 64) / 63)
    n = int(SR * (2 * want + 0.6))
    x = [0] * n
    x[0] = FS // 2
    L, _ = _run(x, x, MIX=127, **kw)
    worst = max(worst, max(abs(v) for v in L[int(SR * (2 * want + 0.3)):]))
check("LP closed: two T60s after an impulse, under -80 dBFS (no subsonic ring outlasting the note)",
      worst < FS * 10 ** (-80 / 20), f"largest {20 * math.log10(max(worst, 1) / FS):.1f} dBFS")

# the input's DC never reaches the loop: a positive loop's gain at DC is
# 1/(1 - g), up to 500 at G_MAX, and a source's DC of -60 dBFS came out near
# -10 dBFS (the waveform pushed against one rail, a mastering limiter pinned).
# A constant -60 dBFS in L (and half of it, inverted, in R): after 1.5 s the
# wet holds under -45 dBFS (the blocker's start dying in the comb's DC mode)
worst = 0
n = int(SR * 2)
for kw in (dict(PTCH=26, LP=127, FB=127), dict(PTCH=50, LP=60, FB=120), dict(PTCH=74, LP=100, FB=110)):
    L, R = _run([FS // 1000] * n, [-(FS // 2000)] * n, MIX=127, **kw)
    worst = max(worst, max(abs(v) for v in L[-SR // 2:]), max(abs(v) for v in R[-SR // 2:]))
check("a -60 dBFS DC at the input: the wet under -45 dBFS after 1.5 s (the loop never sees the DC)",
      worst < FS * 10 ** (-45 / 20), f"largest {20 * math.log10(max(worst, 1) / FS):.1f} dBFS")

# ---- 8. every knob at both extremes ------------------------------------------
x8 = noise(15 * 40, 9, 0.9)
for name in ("PTCH", "FINE", "LP", "FB", "MIX"):
    for v in (0, 95 if name == "PTCH" else 127):
        _run(x8, x8, **{name: v, "MIX": 127 if name != "MIX" else v})
check("every knob renders at both extremes without dsp_host dying", True)

# ---- 9. SLOTS = FX1+FX2: an FX2 instance runs live, exactly as FX1 does ------
FX2_MEM = "out/dsp/_tuned-comb_fx2_A.mem"
env = dict(os.environ, REMIX="tuned-comb-fx2", XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
r = subprocess.run([sys.executable, "tools/build/build_bus.py"], env=env, capture_output=True, text=True)
if r.returncode:
    sys.exit(f"building tuned-comb-fx2 failed:\n{(r.stdout + r.stderr)[-1500:]}")
send_probe.dump_mem("out/mainos_bus.bin", FX2_MEM, "A")
E2 = send_probe.entry_points(FX2_MEM, FXID)
SLOTS2 = {"track 1 FX1": ("1", "0"), "track 1 FX2": ("2", "1"), "track 3 FX2": ("8", "5")}
N9 = 15 * 300
t9 = noise(N9, 3, 0.3)
kw9 = dict(PTCH=40, FINE=70, LP=80, FB=120, MIX=127)
outs = {}
for slot, (r7, alloc) in SLOTS2.items():
    SLOTS[slot] = (r7, alloc)
    outs[slot] = _run(t9, t9, slot=slot, mem=FX2_MEM, entry=E2, guard=True, **kw9)
    check(f"FX1+FX2 build, {slot}: -guard sees no stray write", guard_clean(_run.log), guard_line(_run.log))
a = outs["track 1 FX1"]
check("FX1+FX2 build: FX2 bit-identical to FX1, and live",
      all(o == a for o in outs.values()) and a[0] != t9,
      f"{sum(1 for o in outs.values() if o == a)}/3 identical")

R7S = [1, 2, 4, 5, 7, 8, 10, 11]
ALLOCS = [0, 1, 2, 3, 4, 5, 6, 7]
src = TMP / "core_in.raw"
src.write_bytes(b"".join(struct.pack("<ii", m, m) for m in t9))
out = TMP / "core_out.raw"
cmd = [HOST, "-mem", FX2_MEM, "-init", f"{E2[0]:x}", "-proc", f"{E2[1]:x}", "-inst", "8",
       "-r7", ",".join(map(str, R7S)), "-alloc", ",".join(map(str, ALLOCS)), "-stereo",
       "-frames", str(FRAMES), "-blocks", str(-(-N9 // FRAMES)),
       "-in", str(src), "-out", str(out), "-params", ",".join(str(x) for x in params(**kw9)),
       "-guard", "-guard-shared"]
q = subprocess.run(cmd, capture_output=True, text=True)
if q.returncode:
    sys.exit(f"dsp_host failed (eight instances):\n{q.stdout}\n{q.stderr}")
same = 0
for k in range(8):
    d = pathlib.Path(str(out) + (f".i{k}" if k else "")).read_bytes()
    w = struct.unpack(f"<{len(d)//4}i", d)
    same += list(w[0::2])[:N9] == a[0]
check("eight instances on one core (FX1 + FX2 of four tracks): each bit-identical to one alone",
      same == 8, f"{same}/8 identical")
check("eight instances on one core: -guard sees no stray write", guard_clean(q.stdout + q.stderr),
      guard_line(q.stdout + q.stderr))

print()
print("ALL PASS" if fails == 0 else f"{fails} FAILED")
sys.exit(1 if fails else 0)
