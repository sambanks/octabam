#!/usr/bin/env python3
"""NIMBUS render gates: the grains play at UNITY, and the window sums flat.

The open item on modules/nimbus/README.md (3 Sep 2026): BusDelay v5 took
this engine's read geometry and measured 2x the input frequency at "unity"
-- the write head advances a sample per sample and the distance did not grow
with the grain's phase, so the read position advanced at TWO samples per
sample. The DC gate cannot see rate, which is why it passed.

  unity  -> a 438 Hz tone at MIX=127, FRZE=0 comes back at 438 Hz, not 876
            (dominant FFT bin; the falsifier the README names)
  DC     -> DC in comes back flat: two triangle windows a half period apart
            sum to exactly 1 (the a0 2x trap's gate, kept)

The dump comes from the audition (rebuilt every run -- a stale one silently
measures the stock effect whose id this module holds, see verify_character).
"""
import math, pathlib, struct, subprocess, sys

sys.path.insert(0, "tools")
import send_probe
from remix import registry

MOD = registry.by_name("nimbus")
SEND = registry.by_name("send")
K = MOD.knob_map()
MEM = f"out/dsp/_audition_{MOD.name}_A.mem"
HOST = "vendor/dsp56300/build/source/dsp_host/dsp_host"
FXID = MOD.menu.fx2_id
FRAMES, N, SR = 15, 12000, 44100
TMP = pathlib.Path("out/_nbgate"); TMP.mkdir(parents=True, exist_ok=True)

pathlib.Path(MEM).unlink(missing_ok=True)
subprocess.run([sys.executable, "tools/remix/audition.py", MOD.name,
                "out/dry/drums_110.wav"], capture_output=True)
if not pathlib.Path(MEM).exists():
    sys.exit(f"no {MEM} -- the audition build failed")
init, proc = send_probe.entry_points(MEM, FXID)
if (init, proc) == send_probe.entry_points(MEM, SEND.menu.fx2_id):
    sys.exit(f"fx id 0x{FXID:02x} resolves to SEND's entry points -- {MOD.name} is NOT in this dump")
DEFAULTS = [(p.default or 0) for p in MOD.params]


def render(samples, **kw):
    v = list(DEFAULTS)
    for n, x in kw.items():
        v[K[n]] = x
    src = TMP / "in.raw"; out = TMP / "out.raw"
    src.write_bytes(b"".join(struct.pack("<i", m) for m in samples))
    r = subprocess.run([HOST, "-mem", MEM, "-init", f"{init:x}", "-proc", f"{proc:x}",
                        "-inst", "1", "-r7", "2", "-alloc", "1", "-inmask", "1",
                        "-frames", str(FRAMES), "-blocks", str(len(samples) // FRAMES),
                        "-in", str(src), "-out", str(out),
                        "-params", ",".join(map(str, v))], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"dsp_host failed for {kw}:\n{r.stdout}\n{r.stderr}")
    d = out.read_bytes(); w = struct.unpack(f"<{len(d)//4}i", d)
    return list(w[0::2])[:len(samples)], list(w[1::2])[:len(samples)]


def spectrum(x):
    seg = x[len(x)//2:]
    n = 1 << (len(seg).bit_length() - 1)
    spec = send_probe.fft([float(v) for v in seg[:n]])
    return [abs(c) for c in spec[:n//2]], n


def dominant_hz(x):
    mags, n = spectrum(x)
    k = max(range(20, n//2), key=lambda i: mags[i])
    return k * SR / n


def octave_ratio_db(x, f):
    """the 2f bin against the f bin, in dB (negative = the octave is weaker)"""
    mags, n = spectrum(x)
    def near(hz):
        k = round(hz * n / SR)
        return max(mags[k-2:k+3])
    return 20 * math.log10(max(near(2*f), 1e-9) / max(near(f), 1e-9))


fails = 0
def check(label, ok, detail=""):
    global fails
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")
    fails += 0 if ok else 1


tone = [int(0.4 * 8388607 * math.sin(2 * math.pi * 438.75 * i / SR)) for i in range(N)]
L, _ = render(tone, MIX=127, FRZE=0, DENS=127)
hz = dominant_hz(L)
od = octave_ratio_db(L, 438.75)
check("unity: a 438 Hz tone comes back at 438 Hz, with the octave >20 dB down",
      abs(hz - 438.75) < 30 and od < -20, f"dominant {hz:.0f} Hz, 2f/f {od:+.1f} dB")

dc = [int(0.25 * 8388607)] * N
L, _ = render(dc, MIX=127, FRZE=0, DENS=127)
seg = L[N//2:]
ripple = (max(seg) - min(seg)) / (0.25 * 8388607)
check("DC in comes back flat (the windows sum to 1)", ripple < 0.02,
      f"p-p ripple {20*math.log10(max(ripple,1e-9)):.1f} dB")

print(f"\n{fails} gate(s) failed" if fails else "\nOK")
sys.exit(1 if fails else 0)
