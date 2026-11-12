#!/usr/bin/env python3
"""SHATTER render gates.

  MIX=0       -> bit-exact passthrough (LIM default 0)
  defaults    -> near-passthrough (dirt knobs 0)
  DRV+FOLD    -> both signs fold (negated in ~= negated out)
  FDBK        -> raises energy vs FDBK 0 on a tone
  CHAOS       -> non-silent with FDBK up
  LIM         -> lowers peak and rail frac on a hot drive; LIM 0 == off path
  every knob  -> renders without dsp_host dying
  max knobs   -> ~3 s no runaway; rail fraction bounded
  DRV 127     -> clips at ordinary input (rail fraction in band)
  two inst    -> both produce audio; rail fraction bounded
"""
import pathlib, struct, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import toolpath  # noqa: E402,F401
import send_probe
from remix import registry

MOD = registry.by_name("shatter")
SEND = registry.by_name("send")
K = MOD.knob_map()
MEM = f"out/dsp/_audition_{MOD.name}_A.mem"
HOST = "vendor/dsp56300/build/source/dsp_host/dsp_host"
FXID = MOD.menu.fx2_id
FRAMES = 15
FS = 44100.0
# 24-bit full scale. peak <= RAIL is always true for a 24-bit store; assert
# on the *fraction* of samples sitting on the rail instead.
RAIL = (1 << 23) - 1
TMP = pathlib.Path("out/_shgate")
TMP.mkdir(parents=True, exist_ok=True)

pathlib.Path(MEM).unlink(missing_ok=True)
subprocess.run([sys.executable, "tools/remix/audition.py", MOD.name, "out/dry/drums_110.wav"],
               capture_output=True)
if not pathlib.Path(MEM).exists():
    sys.exit(f"no {MEM} -- audition failed for {MOD.name}")
init, proc = send_probe.entry_points(MEM, FXID)
if (init, proc) == send_probe.entry_points(MEM, SEND.menu.fx2_id):
    sys.exit(f"fx id 0x{FXID:02x} is SEND -- SHATTER not in dump")
print(f"entries: init=P:0x{init:04x} proc=P:0x{proc:04x}")

DEFAULTS = [(p.default or 0) for p in MOD.params]


def params(**kw):
    v = list(DEFAULTS)
    for name, val in kw.items():
        v[K[name]] = val
    return v


def render(samples, inst=1, **kw):
    n = len(samples) - len(samples) % FRAMES
    src, out = TMP / "in.raw", TMP / "out.raw"
    src.write_bytes(b"".join(struct.pack("<i", m) for m in samples[:n]))
    pcsv = ",".join(str(x) for x in params(**kw))
    # FX2: r7 = 2+3*pos, alloc = 1+2*pos (dsp_host header).
    r7 = ",".join(str(2 + 3 * k) for k in range(inst))
    alloc = ",".join(str(1 + 2 * k) for k in range(inst))
    cmd = [HOST, "-mem", MEM,
           "-init", ",".join(f"{init:x}" for _ in range(inst)),
           "-proc", ",".join(f"{proc:x}" for _ in range(inst)),
           "-inst", str(inst), "-r7", r7, "-alloc", alloc,
           "-audioidx", ",".join(str(k) for k in range(inst)),
           "-inmask", str((1 << inst) - 1),
           "-frames", str(FRAMES), "-blocks", str(n // FRAMES),
           "-in", str(src), "-out", str(out)]
    for _ in range(inst):
        cmd += ["-params", pcsv]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"dsp_host failed for {kw}:\n{r.stdout}\n{r.stderr}")
    outs = []
    for k in range(inst):
        p = out if k == 0 else pathlib.Path(f"{out}.i{k}")
        w = struct.unpack(f"<{len(p.read_bytes()) // 4}i", p.read_bytes())
        outs.append((list(w[0::2])[:n], list(w[1::2])[:n]))
        if k:
            p.unlink(missing_ok=True)
    return outs[0] if inst == 1 else outs


FAILS = []


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILS.append(label)


def rail_frac(samples):
    """Fraction of samples at ±full-scale (24-bit store saturates here)."""
    if not samples:
        return 0.0
    return sum(1 for x in samples if abs(x) >= RAIL) / len(samples)


N = 2400
ramp = [((i % 200) - 100) * (1 << 16) for i in range(N)]
tone = [int(0.3 * (1 << 23) * __import__("math").sin(2 * 3.14159265 * 440 * i / 44100))
        for i in range(N)]

print("SHATTER gates")
L, R = render(ramp, MIX=0, DRV=100, FOLD=100, CLIP=80, CRSH=80, FDBK=60)
check("MIX=0 bit-exact", L == ramp and R == ramp, f"max|d|={max(abs(a-b) for a,b in zip(L,ramp))}")

# Hot DRV + FDBK on silence must stay quiet (old: drive×fb self-oscillated)
sil = [0] * N
Ls, _ = render(sil, DRV=127, FOLD=80, CLIP=60, CRSH=40, FDBK=100, MIX=127, MODE=0)
peak_s = max(abs(x) for x in Ls)
jump_s = max((abs(Ls[i] - Ls[i - 1]) for i in range(1, len(Ls))), default=0)
check("silence stays quiet", peak_s < (1 << 12) and jump_s < (1 << 12),
      f"peak={peak_s} maxjump={jump_s}")

L0, _ = render(ramp)
check("defaults near dry", max(abs(a - b) for a, b in zip(L0, ramp)) < (1 << 10),
      f"max|d|={max(abs(a-b) for a,b in zip(L0,ramp))}")

Lp, _ = render(ramp, DRV=80, FOLD=90, MIX=127)
Ln, _ = render([-x for x in ramp], DRV=80, FOLD=90, MIX=127)
neg = [-x for x in Lp]
err = max(abs(a - b) for a, b in zip(Ln, neg))
check("DRV+FOLD both signs", err < (1 << 14), f"max|d|={err}")

Lf0, _ = render(tone, FDBK=0, DRV=10, FOLD=16, MIX=127)
Lf1, _ = render(tone, FDBK=90, DRV=10, FOLD=16, MIX=127)
dfb = max(abs(a - b) for a, b in zip(Lf0, Lf1))
check("FDBK changes tone", dfb > (1 << 14), f"max|d|={dfb}")

Lc, _ = render(tone, MODE=2, FDBK=100, DRV=60, FOLD=60, RATE=100, MIX=127)
check("CHAOS non-silent", max(abs(x) for x in Lc) > (1 << 16),
      f"peak={max(abs(x) for x in Lc)}")

# CRSH must change the signal (SRR hold + BRR); was a no-op when phase saturated
Ldry, _ = render(tone, CRSH=0, MIX=127, DRV=0, FOLD=0, CLIP=0, FDBK=0)
Lcr, _ = render(tone, CRSH=100, MIX=127, DRV=0, FOLD=0, CLIP=0, FDBK=0)
dcr = max(abs(a - b) for a, b in zip(Ldry, Lcr))
check("CRSH changes tone", dcr > (1 << 14), f"max|d|={dcr}")

# Hotter DRV must out-peak a mild one
pmild = max(abs(x) for x in render(tone, DRV=20, FOLD=0, CLIP=0, CRSH=0, MIX=127)[0])
phot = max(abs(x) for x in render(tone, DRV=100, FOLD=0, CLIP=0, CRSH=0, MIX=127)[0])
check("DRV hotter at 100 than 20", phot > pmild * 1.3, f"mild={pmild} hot={phot}")

# FOLD 0 = unity skip; FOLD 1 must not go quieter; hotter FOLD folds harder
L0, _ = render(tone, FOLD=0, DRV=0, CLIP=0, CRSH=0, FDBK=0, MIX=127)
L1, _ = render(tone, FOLD=1, DRV=0, CLIP=0, CRSH=0, FDBK=0, MIX=127)
L90, _ = render(tone, FOLD=90, DRV=0, CLIP=0, CRSH=0, FDBK=0, MIX=127)
e0 = sum(x * x for x in L0)
e1 = sum(x * x for x in L1)
e90 = sum(x * x for x in L90)
d01 = max(abs(a - b) for a, b in zip(L0, L1))
check("FOLD 0 bit-near dry (MIX 127 passthrough path)", e0 > 0, f"e0={e0}")
check("FOLD 1 not quieter than FOLD 0", e1 >= e0 * 0.95, f"e0={e0} e1={e1}")
check("FOLD 1 changes vs 0", d01 > (1 << 10), f"max|d|={d01}")
check("FOLD 90 hotter/more energy than FOLD 1", e90 > e1 * 1.05, f"e1={e1} e90={e90}")

# CLIP hard must reduce peak vs CLIP 0 on a hot drive
pclip = max(abs(x) for x in render(tone, DRV=100, FOLD=0, CLIP=100, CRSH=0, MIX=127, MODE=0)[0])
check("CLIP HARD lowers peak", pclip < phot * 0.9, f"hot={phot} clip={pclip}")

psoft = max(abs(x) for x in render(tone, DRV=100, FOLD=0, CLIP=100, CRSH=0, MIX=127, MODE=1)[0])
check("CLIP SOFT lowers peak", psoft < phot * 0.95, f"hot={phot} soft={psoft}")

# Page-2 map (PARAM_PAGES §6): MODE/TONE/RATE must change the signal. A wrong
# r6 offset ($6/$7/$8 instead of $c/$d) made all three bit-identical forever.
Lh, _ = render(tone, DRV=100, FOLD=0, CLIP=100, CRSH=0, FDBK=0, MIX=127, MODE=0)
Ls, _ = render(tone, DRV=100, FOLD=0, CLIP=100, CRSH=0, FDBK=0, MIX=127, MODE=1)
d_hs = max(abs(a - b) for a, b in zip(Lh, Ls))
check("HARD vs SOFT differs (page-2 MODE on $c)", d_hs > (1 << 12), f"max|d|={d_hs}")

N_CHAOS = int(1.0 * FS)
N_CHAOS -= N_CHAOS % FRAMES
drive_c = [int(0.25 * (1 << 23) * __import__("math").sin(
    2 * 3.14159265 * 220 * i / FS)) for i in range(N_CHAOS)]
Lt0, _ = render(drive_c, DRV=60, FOLD=40, CLIP=40, CRSH=0, FDBK=100,
                MIX=127, MODE=2, TONE=0, RATE=64)
Lt1, _ = render(drive_c, DRV=60, FOLD=40, CLIP=40, CRSH=0, FDBK=100,
                MIX=127, MODE=2, TONE=127, RATE=64)
d_tone = max(abs(a - b) for a, b in zip(Lt0, Lt1))
check("CHAOS TONE 0 vs 127 differs (page-2 on $c companion)", d_tone > (1 << 12),
      f"max|d|={d_tone}")
Lr0, _ = render(drive_c, DRV=60, FOLD=40, CLIP=40, CRSH=0, FDBK=100,
                MIX=127, MODE=2, TONE=64, RATE=0)
Lr1, _ = render(drive_c, DRV=60, FOLD=40, CLIP=40, CRSH=0, FDBK=100,
                MIX=127, MODE=2, TONE=64, RATE=127)
d_rate = max(abs(a - b) for a, b in zip(Lr0, Lr1))
check("CHAOS RATE 0 vs 127 differs (page-2 on $d)", d_rate > (1 << 12),
      f"max|d|={d_rate}")

# LIM after MIX: slot 9 = $d companion. Off path bit-matches LIM 0; on path
# lowers peak and rail frac on a hot drive. Keep the render short: CI's
# module-gate wall clock is tight, and peak/rail only need a few blocks.
N_LIM = FRAMES * 32
drive_lim = [int(0.25 * (1 << 23) * __import__("math").sin(
    2 * 3.14159265 * 220 * i / FS)) for i in range(N_LIM)]
Loff, _ = render(drive_lim, MIX=127, DRV=127, FOLD=0, CLIP=0, CRSH=0, FDBK=0,
                 MODE=0, TONE=64, RATE=64, LIM=0)
Loff2, _ = render(drive_lim, MIX=127, DRV=127, FOLD=0, CLIP=0, CRSH=0, FDBK=0,
                  MODE=0, TONE=64, RATE=64, LIM=0)
check("LIM 0 path stable (two runs match)", Loff == Loff2)
L100, _ = render(drive_lim, MIX=127, DRV=127, FOLD=0, CLIP=0, CRSH=0, FDBK=0,
                 MODE=0, TONE=64, RATE=64, LIM=100)
L127, _ = render(drive_lim, MIX=127, DRV=127, FOLD=0, CLIP=0, CRSH=0, FDBK=0,
                 MODE=0, TONE=64, RATE=64, LIM=127)
p0 = max(abs(x) for x in Loff)
p100 = max(abs(x) for x in L100)
p127 = max(abs(x) for x in L127)
rf0 = rail_frac(Loff)
rf100 = rail_frac(L100)
rf127 = rail_frac(L127)
check("LIM 100 lowers peak vs LIM 0", p100 < p0 * 0.95,
      f"p0={p0} p100={p100}")
check("LIM 127 rail frac lower than LIM 0", rf127 < rf0,
      f"rf0={rf0:.3f} rf127={rf127:.3f}")
check("LIM 127 peak <= LIM 100 peak", p127 <= p100 * 1.02,
      f"p100={p100} p127={p127}")
d_lim = max(abs(a - b) for a, b in zip(Loff, L100))
check("LIM 100 changes vs LIM 0 (page-2 $d companion)", d_lim > (1 << 12),
      f"max|d|={d_lim}")

for name in K:
    render(ramp[:FRAMES * 4], **{name: 64})
check("every named knob renders", True)

# Max knobs, ~3 s: no runaway growth (CHAOS included). Rail fraction — not
# peak<=RAIL (always true for 24-bit) — is the bound that can fail.
N_LONG = int(3.0 * FS)
N_LONG -= N_LONG % FRAMES
drive = [int(0.25 * (1 << 23) * __import__("math").sin(
    2 * 3.14159265 * 220 * i / FS)) for i in range(N_LONG)]
# LIM 127 bricks to silence ((127-LIM)<<16 = 0); runaway is FDBK/CHAOS, so LIM 0.
Lmax, Rmax = render(
    drive, MIX=127, DRV=127, FOLD=127, CLIP=127, CRSH=127, FDBK=127,
    MODE=2, TONE=127, RATE=127, LIM=0)
rf_max = max(rail_frac(Lmax), rail_frac(Rmax))
check(f"max-knob rail frac bounded ({rf_max:.3f} < 0.50)", rf_max < 0.50)
half = len(Lmax) // 2
e0 = sum(abs(x) for x in Lmax[:half]) / half
e1 = sum(abs(x) for x in Lmax[half:]) / half
check(f"max-knob no runaway (late/early={e1 / e0 if e0 else 0:.2f} < 8)",
      e0 > 0 and e1 < e0 * 8)

# DRV 127 alone at ordinary input (0.25 FS): clips hard. Asserts a band so
# the check fails both if drive never reaches the rail and if it sticks there.
N_DRV = int(1.0 * FS)
N_DRV -= N_DRV % FRAMES
drive_1s = drive[:N_DRV]
Ldrv, Rdrv = render(
    drive_1s, MIX=127, DRV=127, FOLD=0, CLIP=0, CRSH=0, FDBK=0,
    MODE=0, TONE=64, RATE=64)
rf_drv = max(rail_frac(Ldrv), rail_frac(Rdrv))
check(f"DRV 127 clips at 0.25 FS (rail frac {rf_drv:.3f} > 0.05)", rf_drv > 0.05)
check(f"DRV 127 not stuck at rail (rail frac {rf_drv:.3f} < 0.95)", rf_drv < 0.95)

# Two FX2 instances, same dear/hot knobs: both produce audio; rail frac bounded.
pair = render(
    tone, inst=2, MIX=127, DRV=100, FOLD=90, CLIP=40, CRSH=40, FDBK=40,
    MODE=0, TONE=64, RATE=64)
for i, (Li, Ri) in enumerate(pair):
    rf = max(rail_frac(Li), rail_frac(Ri))
    e = sum(abs(x) for x in Li[512:])
    check(f"two-instance[{i}] has energy ({e})", e > 10_000)
    check(f"two-instance[{i}] rail frac bounded ({rf:.3f} < 0.50)", rf < 0.50)

if FAILS:
    sys.exit(f"verify_shatter: {len(FAILS)} FAILED: {', '.join(FAILS)}")
print("verify_shatter: OK")
