#!/usr/bin/env python3
"""Prove dsp/burn_probe.asm is the shipping engine plus an inert knob.

The probe exists to return a NUMBER from one flash -- the per-DSP cycle
ceiling, which has never been measured (1080 is a figure stageprobe5 SURVIVED,
not a wall anyone found). A number is only worth the flash if the thing
producing it is the real engine, so this asserts exactly that:

  1. SAME SAMPLE LOOP.   tools/cycle_count.py's span for burn_probe equals
     reverb_server's, to the cycle. The burn sits at the top of proc, outside
     the sample loop, so it must add nothing per-sample. If this drifts, the
     baseline the ceiling is measured against is wrong.

  2. INERT WHEN OFF.     At BURN=0 the probe renders BIT-IDENTICALLY to
     reverb_server at HP=0. Not "sounds the same" -- byte-for-byte. HP=0 is
     the fair comparison because the probe forces the LO coefficient to 0, and
     reverb_server.asm documents HP=0 as that exact bypass ("the state never
     moves, nothing is subtracted, and the filter is bypassed exactly").

  3. INERT WHEN ON.      At BURN=127 the probe still renders bit-identically.
     The burn is nops; if it perturbs the audio it is touching a live register
     and the sweep would be measuring two things at once.

  4. THE HARNESS CAN SEE. reverb_server at HP=0 vs HP=64 must DIFFER. Without
     this, checks 2 and 3 are satisfied by a comparison that is simply blind,
     and "bit-identical" becomes a claim about the test instead of about the
     code -- the exact failure dsp/../octamax-assembler-traps warns about, and
     the reason that memory demands a control alongside any bit-identical test.

Source material is synthesised here, deterministically: a broadband burst then
silence. Nothing musical is needed to compare two renders for equality, and
generating it removes the dependency on the OT card being mounted.

    python3 tools/verify_burn.py
"""
import pathlib
import struct
import subprocess
import sys
import wave

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

SCRATCH = ROOT / "out" / "burnverify"
SR = 44100


def run(cmd, **kw):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, **kw)
    if r.returncode:
        sys.exit(f"FAILED: {' '.join(str(c) for c in cmd)}\n{r.stdout}\n{r.stderr}")
    return r.stdout


def make_source(path):
    """A 1.5 s broadband burst followed by silence.

    Broadband on purpose: a musical source's own harmonics dominate a reverb
    tail (VOICING.md's first measurement trap), and while equality does not
    care about spectrum, check 4 does -- HP=0 vs HP=64 is a low-cut inside the
    feedback path, so the source has to have low content for the difference to
    exist at all.
    """
    n = int(SR * 1.5)
    state = 0x1234567          # fixed seed: the same file every run
    frames = bytearray()
    for i in range(n):
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        v = ((state >> 8) & 0xFFFF) - 0x8000
        env = 1.0 if i < SR // 3 else 0.0
        frames += struct.pack("<h", int(v * 0.5 * env))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(bytes(frames))


def build(env_burn):
    """Build, then dump payload A -- returning the .mem, which is what
    render_reverb --mem consumes. Kept under out/burnverify/ so neither build
    can be mistaken for the flashable out/mainos_bus.bin."""
    import os
    env = dict(os.environ)
    if env_burn:
        env["BURN"] = "1"
    else:
        env.pop("BURN", None)
    run([sys.executable, "tools/build_bus.py"], env=env)
    import dsp_modmap
    SCRATCH.mkdir(parents=True, exist_ok=True)
    mem = SCRATCH / ("burn.mem" if env_burn else "stock.mem")
    dsp_modmap.dumpmem((ROOT / "out/mainos_bus.bin").read_bytes(), ["A", str(mem)])
    return mem


def render(mem, src, out, p3):
    run([sys.executable, "tools/render_reverb.py", str(src),
         "--mem", str(mem), "-p", f"HP={p3}", "-o", str(out)])
    return out.read_bytes()


def main():
    src = SCRATCH / "src.wav"
    make_source(src)

    # ---- 1. the sample loop must be untouched ---------------------------
    import cycle_count
    ref = cycle_count.measure("reverb_server")["words"]
    got = cycle_count.measure("burn_probe")["words"]

    stock_mem = build(False)
    burn_mem = build(True)

    a0 = render(stock_mem, src, SCRATCH / "stock_hp0.wav", 0)
    b0 = render(burn_mem, src, SCRATCH / "burn_0.wav", 0)
    b127 = render(burn_mem, src, SCRATCH / "burn_127.wav", 127)
    a64 = render(stock_mem, src, SCRATCH / "stock_hp64.wav", 64)

    ok = True
    def check(label, cond, detail=""):
        nonlocal ok
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}{detail}")
        ok = ok and cond

    check("sample loop untouched by the burn", ref == got,
          f"  (reverb_server {ref}, burn_probe {got})")
    check("harness is sensitive (reverb_server HP=0 vs HP=64 differ)", a0 != a64,
          "" if a0 != a64 else "  <-- the comparison is BLIND; everything below is meaningless")
    check("probe inert at BURN=0 (bit-identical to reverb_server HP=0)", a0 == b0)
    check("probe inert at BURN=127 (burn perturbs no live register)", a0 == b127)

    print("\nOK" if ok else "\nFAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
