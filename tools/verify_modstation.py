#!/usr/bin/env python3
"""MODULATION STATION render gates -- and the FX1-ONLY PROMISE.

The station takes a per-track line from the host's bump allocator, which is
only safe in an FX1 slot: every FX2 instance buffer is a server's ground.
`Claims(fx1_only=True)` is the promise that an FX2 instance writes nothing,
and the ledger admits the module beside a server on that basis -- so the
first two gates here are what that claim rests on.

Gates:
  FX1 instance  -> MIX=0 is a bit-exact passthrough; every mode renders
  FX2 instance  -> bit-exact DRY at any setting, in every mode
  FX2 instance  -> dsp_host's -guard sees NO write outside the frame
  LFO           -> the sweep rate follows RATE (measured on the wet)
  CHOR/VIB      -> the line is really read: an impulse comes back delayed
  PHSR          -> unity magnitude (an allpass chain changes phase, not level)
  TREM/PAN      -> amplitude moves, and PAN moves the two channels apart
  every knob    -> renders without dsp_host dying

    python3 tools/remix/audition.py modstation out/dry/drums_110.wav
    python3 tools/verify_modstation.py
"""
import math, pathlib, struct, subprocess, sys

sys.path.insert(0, "tools")
import send_probe  # reuse its dispatch-table entry resolution
from remix import registry

MOD = registry.by_name("modstation")
SEND = registry.by_name("send")
K = MOD.knob_map()
MEM = f"out/dsp/_audition_{MOD.name}_A.mem"
HOST = "vendor/dsp56300/build/source/dsp_host/dsp_host"
FXID = MOD.menu.fx2_id
FRAMES, N = 15, 6000
SR = 44100
TMP = pathlib.Path("out/_mogate")
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


def render(samples, slot="fx1", guard=False, **kw):
    """samples: MONO ints in Q23 -- dsp_host feeds one stream to both
    channels (verify_hello's shape). Returns (L, R) lists."""
    src = TMP / "mo_in.raw"
    src.write_bytes(b"".join(struct.pack("<i", m) for m in samples))
    out = TMP / "mo_out.raw"
    r7, alloc = ("1", "0") if slot == "fx1" else ("2", "1")
    cmd = [HOST, "-mem", MEM, "-init", f"{init:x}", "-proc", f"{proc:x}",
           "-inst", "1", "-r7", r7, "-alloc", alloc, "-inmask", "1",
           *(["-guard"] if guard else []),
           "-frames", str(FRAMES), "-blocks", str(len(samples) // FRAMES),
           "-in", str(src), "-out", str(out),
           "-params", ",".join(str(x) for x in params(**kw))]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"dsp_host failed for {kw}:\n{r.stdout}\n{r.stderr}")
    if guard:
        render.guard_out = r.stdout + r.stderr
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


MODES = {"CHOR": 0, "FLNG": 1, "PHSR": 2, "COMB": 3, "TREM": 4, "VIB": 5, "PAN": 6}

# ---- 1. FX1: MIX=0 is a bit-exact passthrough in every mode ------------------
ramp = [int(round(-8388607 + 2 * 8388607 * i / (N - 1))) for i in range(N)]
ok = True
for name, m in MODES.items():
    L, R = render(ramp, MODE=m, MIX=0)
    if L != ramp or R != ramp:
        ok = False
        check(f"FX1 MIX=0 passthrough in {name}", False,
              f"first diff at {next(i for i,(a,b) in enumerate(zip(L,ramp)) if a!=b)}")
check("FX1: MIX=0 is a bit-exact passthrough in all seven modes", ok)

# ---- 2. THE FX1-ONLY PROMISE: an FX2 instance is dry, whatever the knobs -----
ok = True
for name, m in MODES.items():
    L, R = render(ramp, slot="fx2", MODE=m, MIX=127, DPTH=127, FDBK=100, RATE=90)
    if L != ramp or R != ramp:
        ok = False
        check(f"FX2 instance is dry in {name}", False, "it processed the frame")
check("FX2 instance is a bit-exact DRY PASS in all seven modes, at any setting",
      ok)

# ---- 3. ... and it writes nothing outside the frame --------------------------
render(ramp, slot="fx2", guard=True, MODE=0, MIX=127, DPTH=127, FDBK=100)
# dsp_host prints "guard armed: ..." on arming and "guard clean: ..." when
# nothing was written over a loaded module; a violation prints neither.
g = getattr(render, "guard_out", "")
check("FX2 instance trips no write guard (it never touches the line)",
      "guard clean" in g,
      next((ln.strip() for ln in reversed(g.splitlines()) if "guard" in ln), ""))

# ---- 4. the LFO rate follows RATE -------------------------------------------
# ⚠️ MEASURED IN TREM ON A DC INPUT, where the output IS the LFO: an envelope
# follower on a tone tracks the TONE, which is what two earlier versions of
# this gate measured (446 "cycles" at every rate -- the 438 Hz carrier).
LONG = 30000
def lfo_cycles(rate):
    L, _ = render([int(0.4 * 8388607)] * LONG, MODE=4, MIX=127, DPTH=127, RATE=rate)
    seg = L[LONG//4:]
    mid = sum(seg) / len(seg)
    return sum(1 for a, b in zip(seg, seg[1:]) if (a < mid) != (b < mid)) / 2
slow_n, fast_n = lfo_cycles(20), lfo_cycles(110)
check("the LFO is square-law in RATE: the top of the knob is many times the bottom",
      fast_n > slow_n * 4 and fast_n > 2,
      f"RATE 20 -> {slow_n:.1f} cycles in 0.68 s, RATE 110 -> {fast_n:.1f}")

# ---- 4b. the shapes are four, not three (3 Sep 2026: SAW fell through to TRI)
# TREM on DC again: the output IS the LFO, so the fraction of the cycle spent
# RISING tells the shapes apart -- a triangle rises half the time, a saw
# nearly all of it, a square (steps) almost never.
def shape_stats(shpe):
    """-> (fraction of MOVING samples that rise, fraction of samples FLAT)"""
    L, _ = render([int(0.4 * 8388607)] * LONG, MODE=4, MIX=127, DPTH=127, RATE=60, SHPE=shpe)
    seg = L[LONG//4:]
    up = sum(1 for a, b in zip(seg, seg[1:]) if b > a)
    dn = sum(1 for a, b in zip(seg, seg[1:]) if b < a)
    flat = sum(1 for a, b in zip(seg, seg[1:]) if b == a)
    return up / max(1, up + dn), flat / (len(seg) - 1)
(tri_r, tri_fl), (saw_r, saw_fl), (sqr_r, sqr_fl) = (shape_stats(0), shape_stats(3), shape_stats(2))
check("SHPE: TRI rises half the time and is never flat; SAW rises nearly always; "
      "SQR sits on its plateaus most of the time",
      0.4 < tri_r < 0.6 and tri_fl < 0.05 and saw_r > 0.9 and sqr_fl > 0.7,
      f"rising TRI {tri_r:.2f} SAW {saw_r:.2f} SQR {sqr_r:.2f}; "
      f"flat TRI {tri_fl:.2f} SAW {saw_fl:.2f} SQR {sqr_fl:.2f}")

# ---- 5. the line is really read: an impulse comes back delayed ---------------
imp = [0] * N
imp[100] = 6000000
L, _ = render(imp, MODE=5, MIX=127, DPTH=0, DLY=60, RATE=0)   # VIB, no sweep
late = [i for i, v in enumerate(L) if abs(v) > 100000 and i > 110]
check("VIB reads the line: the impulse comes back later", bool(late),
      f"first echo at sample {late[0] - 100} after the input" if late else "no echo")

# ---- 6. the phaser is unity magnitude ---------------------------------------
dryref, _ = render(tone(438), MIX=0)
ph, _ = render(tone(438), MODE=2, MIX=127, DPTH=90, RATE=30)
check("PHSR is unity magnitude (it moves phase, not level)",
      abs(rms_db(ph) - rms_db(dryref)) < 3.0,
      f"{rms_db(ph) - rms_db(dryref):+.2f} dB against the dry")

# ---- 7. TREM moves the amplitude; PAN moves the channels apart --------------
tr, _ = render(tone(438), MODE=4, MIX=127, DPTH=127, RATE=90)
env = [abs(v) for v in tr[N//4:]]
check("TREM modulates the amplitude", max(env) > min(env) * 3,
      f"envelope {min(env)} .. {max(env)}")
pl, pr = render(tone(438), MODE=6, MIX=127, DPTH=127, RATE=90)
diff = max(abs(a - b) for a, b in zip(pl[N//4:], pr[N//4:]))
check("PAN drives the two channels apart", diff > 400000, f"max |L-R| {diff}")

# ---- 8. every knob at its extremes renders ----------------------------------
for name in K:
    for v in (0, 127 if MOD.params[K[name]].count in (None, 128) else MOD.params[K[name]].count - 1):
        render(tone(438, n=600), **{name: v})
check("every knob at both extremes renders", True)

print(f"\n{fails} gate(s) failed" if fails else "\nOK")
sys.exit(1 if fails else 0)
