#!/usr/bin/env python3
"""VOID SCRAPE render gates against modules/void/void_ref.py.

  BAL0 DPTH0 FDBK0 DRV0 open -> bit-exact passthrough
  AM/DRV on noise (BAL127)   -> matches float ref
  BAL0 ignores DRV/FDBK/DPTH -> dry immune
  WID0 mono / WID127 stereo  -> L==R vs L≠R; BAL0 ignores WID
  COLR closed vs open        -> audible difference on noise
  every dear knob            -> dsp_host survives
  live neighbour (two-inst)  -> AM from neighbour; RATE ignored; BAL stays this track

    python3 tools/verify/verify_void.py
"""
import importlib.util
import math
import os
import pathlib
import struct
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import toolpath  # noqa: E402,F401
import send_probe  # noqa: E402
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
MOD = registry.by_name("void")
SEND = registry.by_name("send")
K = MOD.knob_map()
MEM = f"out/dsp/_audition_{MOD.name}_A.mem"
HOST = os.environ.get("DSP_HOST", "vendor/dsp56300/build/source/dsp_host/dsp_host")
FXID = MOD.menu.fx2_id
FRAMES = 15
TMP = pathlib.Path("out/_voidgate")
TMP.mkdir(parents=True, exist_ok=True)

_spec = importlib.util.spec_from_file_location(
    "void_ref", ROOT / "modules/void/void_ref.py")
REF = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(REF)
FS = int(REF.FS)

pathlib.Path(MEM).unlink(missing_ok=True)
dry = pathlib.Path("out/dry/drums_110.wav")
if not dry.exists():
    # overlap/shard trees may lack the curated dry set; a short silent wav
    # is enough for audition to dump the DSP payload.
    dry.parent.mkdir(parents=True, exist_ok=True)
    import wave
    with wave.open(str(dry), "w") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 2)
subprocess.run(
    [sys.executable, "tools/remix/audition.py", MOD.name, str(dry)],
    capture_output=True)
if not pathlib.Path(MEM).exists():
    sys.exit(f"no {MEM} -- audition failed for {MOD.name}")
init, proc = send_probe.entry_points(MEM, FXID)
if (init, proc) == send_probe.entry_points(MEM, SEND.menu.fx2_id):
    sys.exit(f"fx id 0x{FXID:02x} resolves to SEND -- {MOD.name} missing from dump")
print(f"entries: init=P:0x{init:04x} proc=P:0x{proc:04x}")

DEFAULTS = [(p.default or 0) for p in MOD.params]


def params(**kw):
    v = list(DEFAULTS)
    for name, val in kw.items():
        v[K[name]] = val
    return v


def q23(xs):
    return [max(-(1 << 23), min((1 << 23) - 1, int(round(s * (1 << 23)))))
            for s in xs]


def render(samples, **kw):
    """Mono Q23 ints fed to both channels (transient/lofi2 shape)."""
    n = len(samples) - len(samples) % FRAMES
    src, out = TMP / "in.raw", TMP / "out.raw"
    src.write_bytes(b"".join(struct.pack("<i", m) for m in samples[:n]))
    cmd = [HOST, "-mem", MEM, "-init", f"{init:x}", "-proc", f"{proc:x}",
           "-inst", "1", "-r7", "1", "-alloc", "0", "-inmask", "1",
           "-audio", "0", "-frames", str(FRAMES), "-blocks", str(n // FRAMES),
           "-in", str(src), "-out", str(out),
           "-params", ",".join(str(x) for x in params(**kw))]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"dsp_host failed for {kw}:\n{r.stdout}\n{r.stderr}")
    w = struct.unpack(f"<{len(out.read_bytes()) // 4}i", out.read_bytes())
    return list(w[0::2])[:n], list(w[1::2])[:n]


FAILS = []


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILS.append(label)


n = FRAMES * 40
ramp = q23([(-0.9 + 1.8 * i / (n - 1)) for i in range(n)])
noise = q23([0.2 * math.sin(i * 12.9898) * math.cos(i * 78.233) for i in range(n)])
silence = [0] * n

L, R = render(ramp, BAL=0, DPTH=0, DRV=0, FDBK=0, HPF=0, COLR=127, RATE=40)
d0 = max(abs(a - b) for a, b in zip(L, ramp))
check("BAL0 DPTH0 open passthrough", d0 <= 1, f"max|d|={d0}")

L, R = render(noise, BAL=0, DPTH=0, DRV=0, FDBK=0, HPF=0, COLR=127, RATE=40)
d1 = max(abs(a - b) for a, b in zip(L, noise))
check("BAL0 noise passthrough", d1 <= 1, f"max|d|={d1}")

# AM/DRV live on the noise leg — use BAL=127 so they are audible.
sine = [0.5 * math.sin(2 * math.pi * 220 * i / FS) for i in range(n)]
kw = dict(BAL=127, RATE=90, SHPE=0, DPTH=127, DRV=0, FDBK=0, COLR=127, HPF=0, WID=0)
L, R = render(q23(sine), **kw)
ref_l, _ = REF.process_block(sine, sine, bal=127, rate=90, shape=0, depth=127,
                             drive=0, fdbk=0, color=127, hpf=0, wid=0)
err = max(abs(a - b) for a, b in zip(L, q23(ref_l)))
check("AM noise vs ref", err <= 64, f"max|LSB|={err}")

kw_drv = dict(BAL=127, RATE=60, SHPE=0, DPTH=80, DRV=40, FDBK=0, COLR=127, HPF=0, WID=0)
L, R = render(q23(sine), **kw_drv)
ref_l, _ = REF.process_block(sine, sine, bal=127, rate=60, shape=0, depth=80,
                             drive=40, fdbk=0, color=127, hpf=0, wid=0)
# feedback loops diverge sample-to-sample; DRV-only stays near the float law
err = max(abs(a - b) for a, b in zip(L, q23(ref_l)))
check("DRV on noise vs ref", err <= (1 << 19), f"max|LSB|={err}")
L_fb, _ = render(q23(sine), BAL=127, RATE=60, SHPE=0, DPTH=80, DRV=40, FDBK=64,
                 COLR=127, HPF=0, WID=0)
check("FDBK changes noise path",
      max(abs(a - b) for a, b in zip(L, L_fb)) > (1 << 12),
      f"maxd={max(abs(a-b) for a,b in zip(L, L_fb))}")

# BAL=0: dry immune to DRV/FDBK/DPTH
L_d, _ = render(q23(sine), BAL=0, DPTH=127, DRV=127, FDBK=127, COLR=0, HPF=127, RATE=90)
check("BAL0 ignores DRV/FDBK/DPTH",
      max(abs(a - b) for a, b in zip(L_d, q23(sine))) <= 4,
      f"maxd={max(abs(a-b) for a,b in zip(L_d, q23(sine)))}")

# WID: mono copy vs stereo grit on noise; 0→1 continuous on L
Lw0, Rw0 = render(silence, BAL=127, RATE=40, DPTH=0, DRV=0, FDBK=0, COLR=127, HPF=0, WID=0)
d_mono = max(abs(a - b) for a, b in zip(Lw0, Rw0))
check("WID0 L==R", d_mono == 0, f"maxd={d_mono}")
Lw1, Rw1 = render(silence, BAL=127, RATE=40, DPTH=0, DRV=0, FDBK=0, COLR=127, HPF=0, WID=127)
d_st = max(abs(a - b) for a, b in zip(Lw1, Rw1))
check("WID127 L≠R", d_st > 1000, f"maxd={d_st}")
# WID0 vs WID1: both channels leave mid by ~w·side (balanced, tiny)
Lw_a, Rw_a = render(silence, BAL=127, RATE=40, DPTH=0, DRV=0, FDBK=0, COLR=127, HPF=0, WID=0)
Lw_b, Rw_b = render(silence, BAL=127, RATE=40, DPTH=0, DRV=0, FDBK=0, COLR=127, HPF=0, WID=1)
d_l01 = max(abs(a - b) for a, b in zip(Lw_a, Lw_b))
d_r01 = max(abs(a - b) for a, b in zip(Rw_a, Rw_b))
check("WID 0→1 L tiny open", d_l01 < (1 << 20), f"maxdL={d_l01}")
check("WID 0→1 R tiny open", d_r01 < (1 << 20), f"maxdR={d_r01}")
# mono fold must keep mid energy (old ±w·side nulling killed LFO in mono)
mono0 = [a + b for a, b in zip(Lw0, Rw0)]
mono1 = [a + b for a, b in zip(Lw1, Rw1)]
e0 = sum(abs(x) for x in mono0) + 1
e1 = sum(abs(x) for x in mono1)
check("WID127 mono keeps mid", e1 * 2 > e0, f"e0={e0} e1={e1}")
L_ign, R_ign = render(q23(sine), BAL=0, DPTH=0, DRV=0, FDBK=0, COLR=127, HPF=0, WID=127)
check("BAL0 ignores WID",
      max(abs(a - b) for a, b in zip(L_ign, R_ign)) == 0
      and max(abs(a - b) for a, b in zip(L_ign, q23(sine))) <= 4,
      f"LRd={max(abs(a-b) for a,b in zip(L_ign, R_ign))}")

Lo, _ = render(silence, BAL=127, RATE=40, DPTH=0, DRV=0, FDBK=0, COLR=127, HPF=0, WID=0)
Lc, _ = render(silence, BAL=127, RATE=40, DPTH=0, DRV=0, FDBK=0, COLR=0, HPF=0, WID=0)
dc = max(abs(a - b) for a, b in zip(Lo, Lc))
check("COLR closed ≠ open", dc > 1000, f"max|d|={dc}")

sine = [0.3 * math.sin(2 * math.pi * 220 * i / FS) for i in range(n)]
L, R = render(q23(sine), BAL=127, RATE=60, SHPE=0, DPTH=80, DRV=80, FDBK=80,
              COLR=127, HPF=0, WID=0)
tail = L[n // 2:]
mean = sum(tail) / len(tail)
peak = max(abs(x) for x in tail)
check("FDBK+DRV not DC-silent", abs(mean) < peak * 0.35 and peak > (1 << 20),
      f"mean={mean:.0f} peak={peak}")

dear = {k: MOD.dear[k] for k in MOD.dear}
L, R = render(noise, **dear)
check("dear render", len(L) == n and max(abs(x) for x in L + R) < (1 << 23),
      f"peak={max(abs(x) for x in L + R)}")

RAIL = 1 << 23  # ± full-scale; positive peak saturates at RAIL-1


def rail_hits(samples):
    """Count samples at either rail (pos = RAIL-1, neg = -RAIL)."""
    return sum(1 for x in samples if x <= -RAIL or x >= RAIL - 1)


# max knobs, true 3 s: under 1% of samples at either rail (no runaway)
n_long = int(3.0 * FS)
n_long -= n_long % FRAMES
long_in = q23([0.2 * math.sin(2 * math.pi * 110 * i / FS) for i in range(n_long)])
max_kw = {}
for p in MOD.params:
    if not p.name:
        continue
    max_kw[p.name.decode("latin1")] = (p.count - 1) if p.count else 0
max_kw["SRC"] = 0  # NBR needs keybus; rail budget is the LFO scrape
L, R = render(long_in, **max_kw)
hits = rail_hits(L + R)
n_samp = len(L) + len(R)
check("max-knob rail hits <1% ~3s",
      hits * 100 < n_samp,
      f"hits={hits}/{n_samp} peak={max(abs(x) for x in L + R)}")

# two FX2 instances: each out file has energy and stays off the rail
src, out = TMP / "in2.raw", TMP / "out2.raw"
tone2 = q23([0.25 * math.sin(2 * math.pi * 220 * i / FS) for i in range(n)])
src.write_bytes(b"".join(struct.pack("<i", m) for m in tone2))
cmd = [HOST, "-mem", MEM, "-init", f"{init:x},{init:x}", "-proc", f"{proc:x},{proc:x}",
       "-inst", "2", "-r7", "1,5", "-alloc", "1,3", "-inmask", "3",
       "-audio", "0", "-frames", str(FRAMES), "-blocks", str(n // FRAMES),
       "-in", str(src), "-out", str(out),
       "-params", ",".join(str(x) for x in params(BAL=64, DPTH=80, DRV=40, FDBK=40)),
       "-params", ",".join(str(x) for x in params(BAL=127, WID=64, DPTH=100, DRV=20))]
r = subprocess.run(cmd, capture_output=True, text=True)
check("two FX2 instances host ok", r.returncode == 0 and out.exists(),
      f"rc={r.returncode}")
if r.returncode == 0 and out.exists():
    for i in range(2):
        p = out if i == 0 else pathlib.Path(f"{out}.i{i}")
        if not p.exists():
            check(f"two-instance[{i}] out file", False, f"missing {p.name}")
            continue
        w = struct.unpack(f"<{len(p.read_bytes()) // 4}i", p.read_bytes())
        Li, Ri = list(w[0::2])[:n], list(w[1::2])[:n]
        if i:
            p.unlink(missing_ok=True)
        pk = max(abs(x) for x in Li + Ri)
        energy = sum(abs(x) for x in Li[n // 4:])
        check(f"two-instance[{i}] has energy", energy > 10_000, f"e={energy}")
        check(f"two-instance[{i}] peak under rail",
              pk < RAIL and rail_hits(Li + Ri) == 0,
              f"peak={pk} rail_hits={rail_hits(Li + Ri)}")

# SRC=NBR: previous-track KEYBUS AM. Seed the published X:$37f60 word for
# track 0; r7 position 5 models the following FX2 slot (track 1). SRC=LFO on
# that same slot still responds to RATE.
carrier = [0.5 * math.sin(2 * math.pi * 220 * i / FS) for i in range(n)]
src1 = TMP / "nbr1.raw"
out_nbr = TMP / "out_nbr.raw"
src1.write_bytes(b"".join(struct.pack("<i", m) for m in q23(carrier)))
_qw = q23([0.6])[0] & 0xFFFFFF
_keybus_on = f"{0x37f60:x}={_qw:x}"
_keybus_off = f"{0x37f60:x}=0"


def _src_render(keybus, **kw):
    cmd = [HOST, "-mem", MEM, "-init", f"{init:x}", "-proc", f"{proc:x}",
           "-inst", "1", "-r7", "5", "-alloc", "3", "-inmask", "1",
           "-audio", "0", "-frames", str(FRAMES), "-blocks", str(n // FRAMES),
           "-in", str(src1), "-out", str(out_nbr),
           "-xword", keybus,
           "-params", ",".join(str(x) for x in params(**kw))]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not out_nbr.exists():
        return None, r.returncode
    w = struct.unpack(f"<{len(out_nbr.read_bytes()) // 4}i", out_nbr.read_bytes())
    L1 = list(w[0::2])[:n]
    out_nbr.unlink(missing_ok=True)
    return L1, 0


def _auto_nbr(**kw):
    return _src_render(_keybus_on, SRC=1, **kw)


L_lfo10, rcl = _src_render(_keybus_on, SRC=0, BAL=127, DPTH=127, DRV=0, FDBK=0,
                           COLR=127, HPF=0, RATE=10, SHPE=0)
L_lfo100, rcl2 = _src_render(_keybus_on, SRC=0, BAL=127, DPTH=127, DRV=0, FDBK=0,
                             COLR=127, HPF=0, RATE=100, SHPE=0)
check("SRC=LFO RATE still works",
      rcl == 0 and rcl2 == 0 and L_lfo10 is not None and L_lfo100 is not None
      and max(abs(a - b) for a, b in zip(L_lfo10, L_lfo100)) > (1 << 16),
      f"rc={rcl}/{rcl2} maxd="
      f"{None if not (L_lfo10 and L_lfo100) else max(abs(a-b) for a,b in zip(L_lfo10, L_lfo100))}")

# BAL0 DPTH0: exact dry. RATE idle under SRC=NBR (check with BAL=127 too).
L_slow, rc = _auto_nbr(BAL=0, DPTH=0, DRV=0, FDBK=0, COLR=127, HPF=0, RATE=10, SHPE=0)
check("SRC=NBR host ok", rc == 0 and L_slow is not None, f"rc={rc}")
if L_slow is not None:
    L_r10, _ = _auto_nbr(BAL=127, DPTH=127, DRV=0, FDBK=0, COLR=127, HPF=0,
                         RATE=10, SHPE=0)
    L_r100, rc2 = _auto_nbr(BAL=127, DPTH=127, DRV=0, FDBK=0, COLR=127, HPF=0,
                            RATE=100, SHPE=0)
    check("SRC=NBR RATE ignored",
          rc2 == 0 and L_r10 is not None and L_r100 is not None
          and max(abs(a - b) for a, b in zip(L_r10, L_r100)) <= 2,
          f"rc={rc2} maxd="
          f"{None if not (L_r10 and L_r100) else max(abs(a-b) for a,b in zip(L_r10, L_r100))}")
    energy = sum(abs(x) for x in L_slow)
    check("SRC=NBR keeps this track", energy > (1 << 20), f"energy={energy}")
    _keybus_z = _keybus_off
    car_q = q23(carrier)

    # Quiet keybus → AM≈0 → noise stops (no LFO free-run).
    L_q, rcq = _src_render(_keybus_z, SRC=1, BAL=127, DPTH=127, DRV=0, FDBK=0,
                           COLR=127, HPF=0, RATE=10, SHPE=0)
    _bleed = max(abs(x) for x in car_q) // 64 + 8
    check("SRC=NBR quiet BAL127 ≈ silence",
          rcq == 0 and L_q is not None
          and max(abs(x) for x in L_q) <= _bleed,
          f"rc={rcq} peak={None if not L_q else max(abs(x) for x in L_q)} bleed={_bleed}")
    check("SRC=NBR BAL0 DPTH0 ≈ dry",
          max(abs(a - b) for a, b in zip(L_slow, car_q)) <= 4,
          f"maxd={max(abs(a-b) for a,b in zip(L_slow, car_q))}")
    L_n, rcn = _auto_nbr(BAL=127, DPTH=0, DRV=0, FDBK=0, COLR=127, HPF=0,
                         RATE=10, SHPE=0)
    if L_n is not None:
        corr_dry = sum(a * b for a, b in zip(L_n, car_q))
        corr0 = sum(a * b for a, b in zip(L_slow, car_q))
    else:
        corr_dry = corr0 = 0
    check("SRC=NBR BAL127 DPTH0 ≠ dry",
          rcn == 0 and L_n is not None and abs(corr_dry) < abs(corr0) // 4,
          f"rc={rcn} corr_n={corr_dry} corr0={corr0}")
    L_xf, rcx = _auto_nbr(BAL=100, DPTH=0, DRV=0, FDBK=0, COLR=127, HPF=0,
                          RATE=10, SHPE=0)
    if L_xf is not None:
        corrx = sum(a * b for a, b in zip(L_xf, car_q))
    else:
        corrx = 0
    check("SRC=NBR BAL mid ducks dry corr",
          rcx == 0 and L_xf is not None and corrx < corr0 - (1 << 30),
          f"rc={rcx} corr0={corr0} corrx={corrx}")
    L_d0, _ = _auto_nbr(BAL=127, DPTH=0, DRV=0, FDBK=0, COLR=127, HPF=0,
                        RATE=10, SHPE=0)
    L_d1, rd1 = _auto_nbr(BAL=127, DPTH=0, DRV=1, FDBK=0, COLR=127, HPF=0,
                          RATE=10, SHPE=0)
    if L_d0 and L_d1:
        maxd = max(abs(a - b) for a, b in zip(L_d0, L_d1))
    else:
        maxd = 1 << 30
    check("DRV 0→1 no click",
          rd1 == 0 and L_d1 is not None and maxd < (1 << 16),
          f"rc={rd1} maxd={maxd}")
    L_safe, rcs = _auto_nbr(BAL=0, DPTH=127, DRV=127, FDBK=100, COLR=0, HPF=127,
                            RATE=10, SHPE=0)
    check("SRC=NBR BAL0 hot DRV ≈ dry",
          rcs == 0 and L_safe is not None
          and max(abs(a - b) for a, b in zip(L_safe, car_q)) <= 4,
          f"rc={rcs} maxd={None if not L_safe else max(abs(a-b) for a,b in zip(L_safe, car_q))}")

if FAILS:
    sys.exit(f"{len(FAILS)} void gate(s) failed: {FAILS}")
print("verify_void: all gates passed")
