#!/usr/bin/env python3
"""VOID SCRAPE render gates against modules/void/void_ref.py.

  BAL0 DPTH0 FDBK0 DRV0 open -> bit-exact passthrough
  AM law (BAL0, FDBK0)       -> matches float ref within 64 LSB on a sine
  FDBK through DRV           -> matches float ref within 256 LSB
  NTYP PINK/BRWN (BAL127)    -> diverge from WHT; match ref
  COLR closed vs open        -> audible difference on noise
  every dear knob            -> dsp_host survives

    python3 tools/verify/verify_void.py
"""
import importlib.util
import math
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
HOST = "vendor/dsp56300/build/source/dsp_host/dsp_host"
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

sine = [0.5 * math.sin(2 * math.pi * 220 * i / FS) for i in range(n)]
kw = dict(BAL=0, RATE=90, SHPE=0, DPTH=127, DRV=0, FDBK=0, COLR=127, HPF=0, NTYP=0)
L, R = render(q23(sine), **kw)
ref_l, _ = REF.process_block(sine, sine, bal=0, rate=90, shape=0, depth=127,
                             drive=0, fdbk=0, color=127, hpf=0, ntyp=0)
err = max(abs(a - b) for a, b in zip(L, q23(ref_l)))
check("AM sine vs ref", err <= 64, f"max|LSB|={err}")

kw_fb = dict(BAL=0, RATE=60, SHPE=0, DPTH=80, DRV=40, FDBK=64, COLR=127, HPF=0, NTYP=0)
L, R = render(q23(sine), **kw_fb)
ref_l, _ = REF.process_block(sine, sine, bal=0, rate=60, shape=0, depth=80,
                             drive=40, fdbk=64, color=127, hpf=0, ntyp=0)
err = max(abs(a - b) for a, b in zip(L, q23(ref_l)))
check("FDBK through DRV vs ref", err <= 256, f"max|LSB|={err}")

base = dict(BAL=127, RATE=40, SHPE=0, DPTH=0, DRV=0, FDBK=0, COLR=127, HPF=0)
Lw, _ = render(silence, **base, NTYP=0)
Lp, _ = render(silence, **base, NTYP=1)
Lb, _ = render(silence, **base, NTYP=2)
dw = max(abs(a - b) for a, b in zip(Lw, Lp))
db = max(abs(a - b) for a, b in zip(Lw, Lb))
check("NTYP pink ≠ white", dw > 1000, f"max|d|={dw}")
check("NTYP brown ≠ white", db > 1000, f"max|d|={db}")

ref_p, _ = REF.process_block([0.0] * n, [0.0] * n, bal=127, rate=40, shape=0,
                             depth=0, drive=0, fdbk=0, color=127, hpf=0, ntyp=1)
err = max(abs(a - b) for a, b in zip(Lp, q23(ref_p)))
check("NTYP pink vs ref", err <= 128, f"max|LSB|={err}")

ref_b, _ = REF.process_block([0.0] * n, [0.0] * n, bal=127, rate=40, shape=0,
                             depth=0, drive=0, fdbk=0, color=127, hpf=0, ntyp=2)
err = max(abs(a - b) for a, b in zip(Lb, q23(ref_b)))
check("NTYP brown vs ref", err <= 128, f"max|LSB|={err}")

Lo, _ = render(silence, BAL=127, RATE=40, DPTH=0, DRV=0, FDBK=0, COLR=127, HPF=0, NTYP=0)
Lc, _ = render(silence, BAL=127, RATE=40, DPTH=0, DRV=0, FDBK=0, COLR=0, HPF=0, NTYP=0)
dc = max(abs(a - b) for a, b in zip(Lo, Lc))
check("COLR closed ≠ open", dc > 1000, f"max|d|={dc}")

sine = [0.3 * math.sin(2 * math.pi * 220 * i / FS) for i in range(n)]
L, R = render(q23(sine), BAL=0, RATE=60, SHPE=0, DPTH=80, DRV=80, FDBK=80,
              COLR=127, HPF=0, NTYP=0)
tail = L[n // 2:]
mean = sum(tail) / len(tail)
peak = max(abs(x) for x in tail)
check("FDBK+DRV not DC-silent", abs(mean) < peak * 0.35 and peak > (1 << 20),
      f"mean={mean:.0f} peak={peak}")

dear = {k: MOD.dear[k] for k in MOD.dear}
L, R = render(noise, **dear)
check("dear render", len(L) == n and max(abs(x) for x in L + R) < (1 << 23),
      f"peak={max(abs(x) for x in L + R)}")

# max knobs ~3 s: stay off the rails (no runaway)
n_long = FRAMES * 200  # ~3 s at 44.1 kHz / 15-frame blocks
long_in = q23([0.2 * math.sin(2 * math.pi * 110 * i / FS) for i in range(n_long)])
max_kw = {}
for p in MOD.params:
    if not p.name:
        continue
    max_kw[p.name.decode("latin1")] = (p.count - 1) if p.count else 0
L, R = render(long_in, **max_kw)
peak = max(abs(x) for x in L + R)
check("max-knob bounded ~3s", peak < (1 << 23), f"peak={peak}")

# two FX2 instances (r7=1 and r7=5) both run without host failure
src, out = TMP / "in2.raw", TMP / "out2.raw"
src.write_bytes(b"".join(struct.pack("<i", m) for m in silence[:n]))
cmd = [HOST, "-mem", MEM, "-init", f"{init:x},{init:x}", "-proc", f"{proc:x},{proc:x}",
       "-inst", "2", "-r7", "1,5", "-alloc", "1,3", "-inmask", "3",
       "-audio", "0", "-frames", str(FRAMES), "-blocks", str(n // FRAMES),
       "-in", str(src), "-out", str(out),
       "-params", ",".join(str(x) for x in params(BAL=64, DPTH=80, DRV=40, FDBK=40)),
       "-params", ",".join(str(x) for x in params(BAL=127, NTYP=1, DPTH=100, DRV=20))]
r = subprocess.run(cmd, capture_output=True, text=True)
check("two FX2 instances", r.returncode == 0 and out.exists(),
      f"rc={r.returncode}")

if FAILS:
    sys.exit(f"{len(FAILS)} void gate(s) failed: {FAILS}")
print("verify_void: all gates passed")
