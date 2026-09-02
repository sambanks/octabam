#!/usr/bin/env python3
"""HELLO WORLD render gates, at the raw Q23 level.

Input: a full-scale bipolar ramp -- every magnitude, both signs, so a silent
mpysu mis-encoding (wrong on negative samples) cannot hide.

Gates:
  GAIN=127 -> output bit-exact vs input (both channels)
  GAIN=0   -> output all-zero
  GAIN in {32,64,96,126} -> per-sample |out - (in*g)>>23| <= 1 LSB
     (also reports the factor-2 alternative, settling the mpy-scaling question)

The dump comes from the audition, which builds a scratch image that really
contains this insert:

    python3 tools/remix/audition.py hello out/dry/drums_110.wav
    python3 tools/verify_hello.py

⚠️ NOTHING HERE IS HARDCODED ABOUT WHICH EFFECT IS MEASURED. The id and the
GAIN slot come from the manifest, and the resolved entry points are checked
against SEND's, because an id this image does not implement ALIASES TO THE
FALLBACK and dsp_host then renders a perfectly plausible dry passthrough
(CLAUDE.md, 12 Aug 2026). That is not hypothetical here: this file shipped
with `FXID = 0x17` after hello moved to 0x1b, ran SEND for all six gains,
and the GAIN=127 bit-exact gate PASSED -- because a dry passthrough is
exactly what unity gain looks like. Only the gain-law gates dissented.
"""
import pathlib, struct, subprocess, sys

sys.path.insert(0, "tools")
import send_probe  # reuse its dispatch-table entry resolution
from remix import registry

MOD = registry.by_name("hello")
SEND = registry.by_name("send")
GAIN_SLOT = MOD.knob_map()["GAIN"]
NSLOTS = 6                              # page 1: r6+0..5

MEM = f"out/dsp/_audition_{MOD.name}_A.mem"
HOST = "vendor/dsp56300/build/source/dsp_host/dsp_host"
FXID = MOD.menu.fx2_id
FRAMES, N = 15, 4200

if not pathlib.Path(MEM).exists():
    sys.exit(f"no {MEM} -- build it first:\n"
             f"  python3 tools/remix/audition.py {MOD.name} out/dry/drums_110.wav")

init, proc = send_probe.entry_points(MEM, FXID)
print(f"entries from dispatch tables: init=P:0x{init:04x} proc=P:0x{proc:04x} "
      f"(fx id 0x{FXID:02x}, GAIN at r6+${GAIN_SLOT:x})")

# The SEND-alias guard. An absent id resolves to the fallback and renders a
# dry pass; measuring that and calling it a null gate is the failure this
# tool exists to avoid.
if (init, proc) == send_probe.entry_points(MEM, SEND.menu.fx2_id):
    sys.exit(f"fx id 0x{FXID:02x} resolves to the SAME entry points as SEND "
             f"(0x{SEND.menu.fx2_id:02x}) -- {MOD.name} is NOT in this dump, "
             f"so every gate below would measure the send client. Rebuild:\n"
             f"  python3 tools/remix/audition.py {MOD.name} out/dry/drums_110.wav")

# full-scale bipolar ramp, exact endpoints
ramp = [int(round(-8388607 + (2 * 8388607) * i / (N - 1))) for i in range(N)]
assert min(ramp) == -8388607 and max(ramp) == 8388607
pathlib.Path("/tmp/ramp.raw").write_bytes(b"".join(struct.pack("<i", s) for s in ramp))

def render(gain):
    out = f"/tmp/hello_g{gain}.raw"
    cmd = [HOST, "-mem", MEM, "-init", f"{init:x}", "-proc", f"{proc:x}",
           "-inst", "1", "-r7", "2", "-alloc", "1", "-inmask", "1",
           "-frames", str(FRAMES), "-blocks", str(N // FRAMES),
           "-in", "/tmp/ramp.raw", "-out", out,
           "-params", ",".join(str(gain if i == GAIN_SLOT else 0)
                                for i in range(NSLOTS))]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"dsp_host failed for GAIN={gain}:\n{r.stdout}\n{r.stderr}")
    d = pathlib.Path(out).read_bytes()
    w = struct.unpack(f"<{len(d)//4}i", d)
    L, R = w[0::2], w[1::2]
    return L[:N], R[:N]

fails = 0
def gate(name, ok, detail=""):
    global fails
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not ok: fails += 1

# --- GAIN=127: bit-exact null ---------------------------------------------
L, R = render(127)
same = all(L[i] == ramp[i] and R[i] == ramp[i] for i in range(N))
gate("GAIN=127 bit-exact passthrough", same,
     "" if same else f"first diff at {next(i for i in range(N) if L[i]!=ramp[i] or R[i]!=ramp[i])}")

# --- GAIN=0: exact silence -------------------------------------------------
L, R = render(0)
gate("GAIN=0 exact silence", all(v == 0 for v in L + R))

# --- gain law --------------------------------------------------------------
for g in (32, 64, 96, 126):
    L, R = render(g)
    gq = g << 16
    exp  = [(s * gq) >> 23 for s in ramp]          # engine as written (no asl)
    exp2 = [(s * gq) >> 24 for s in ramp]          # the factor-2 alternative
    err  = max(abs(L[i] - exp[i])  for i in range(N))
    err2 = max(abs(L[i] - exp2[i]) for i in range(N))
    lr   = max(abs(L[i] - R[i]) for i in range(N))
    ok = err <= 1 and lr == 0
    gate(f"GAIN={g:3d} law (in*g)>>23", ok,
         f"max|err|={err} LSB (factor-2 alt: {err2})  L/R match: {lr==0}")
    # negative-sample spot check: worst error on the negative half alone
    neg = [i for i in range(N) if ramp[i] < 0]
    errn = max(abs(L[i] - exp[i]) for i in neg)
    gate(f"GAIN={g:3d} negative-sample half", errn <= 1, f"max|err|={errn} LSB")

print("\nALL GATES PASSED" if fails == 0 else f"\n{fails} GATE(S) FAILED")
sys.exit(1 if fails else 0)
