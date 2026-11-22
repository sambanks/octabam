#!/usr/bin/env python3
"""FET76 render gates: the assembled module against its bit-exact model, and the model against the
1176LN's own manual.

Renders the module straight through dsp_host (the render-gate shape of verify_db666: the id and the
slots come from the manifest, the entry points are checked against SEND's).

Gates:
  generated     -> fet76.asm is what the template and the manifest make
  bit-exact     -> the dump's output equals modules/fet76/fet76_ref.fixed(): defaults, every knob at
                   both ends, every ratio button, BLUE, ATK OFF, a split block, LFO-dirty page words,
                   loud drums-like bursts, noise, a knob that moves every block
  passthrough   -> MIX 0: exact
  the manual    -> ratios on a steady tone near 4 / 8 / 12 / 20:1; attack OFF = no gain reduction;
                   THD < 0.5 % at 1 kHz with limiting at the slowest release; the release after held
                   limiting near the knob's time and much faster after a short peak (program-dependent)
  silence       -> silence in, exact zeros out

    python3 tools/verify/verify_fet76.py
"""
import importlib.util
import math
import pathlib
import struct
import subprocess
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401

ROOT = pathlib.Path(__file__).resolve().parents[2]
FRAMES = 16
_spec = importlib.util.spec_from_file_location("fet76_ref", ROOT / "modules/fet76/fet76_ref.py")
REF = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(REF)
FS = 44100
DEFAULTS = {"INPT": 64, "OUTP": 64, "ATK": 100, "REL": 64, "RATI": 3, "MIX": 127, "REV": 0}
FAILS = []


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILS.append(label)


def q23(x):
    return [max(-(1 << 23), min((1 << 23) - 1, int(round(s * (1 << 23))))) for s in x]


def knobs(**kw):
    k = dict(DEFAULTS); k.update(kw); return k


def words(kn, frac=0):
    return REF.page_words(INPT=kn["INPT"], OUTP=kn["OUTP"], ATK=kn["ATK"], REL=kn["REL"], RATI=kn["RATI"],
                          MIX=kn["MIX"], REV=kn["REV"], frac=frac)


def tone(level_dbfs_peak, n, f=1000.0):
    t = np.arange(n) / FS
    return 10 ** (level_dbfs_peak / 20) * np.sin(2 * np.pi * f * t)


def bursts(n, seed=1):
    """kick-like bursts on a quieter bed: what the 1176 does on a master."""
    rng = np.random.default_rng(seed)
    x = 0.05 * rng.standard_normal(n)
    step = int(FS * 60 / 132 / 4)
    for k in range(0, n, 4 * step):
        L = min(int(0.2 * FS), n - k)
        t = np.arange(L) / FS
        x[k:k + L] += 0.95 * np.sin(2 * np.pi * (50 * t + 4 * (1 - np.exp(-t / 0.03)))) * np.exp(-t / 0.08)
    return np.clip(x, -0.999, 0.999)


def run_gates(render, dirty_words=True):
    """render(L_q23, R_q23, knobs, split=0, pfrac=0) -> (L, R)."""
    n = 8192
    rng = np.random.default_rng(7)
    sig = {
        "tone -6 dBFS": q23(tone(-6, n)),
        "drums-like bursts": q23(bursts(n)),
        "noise -12 dBFS": q23(0.25 * rng.standard_normal(n).clip(-3.9, 3.9)),
    }
    cases = [("defaults", knobs())]
    for k, lo, hi in (("INPT", 0, 127), ("OUTP", 0, 127), ("ATK", 1, 127), ("REL", 0, 127), ("MIX", 0, 126)):
        cases += [(f"{k} {lo}", knobs(**{k: lo})), (f"{k} {hi}", knobs(**{k: hi}))]
    for r in range(5):
        cases.append((f"RATI {r}, INPT 100", knobs(RATI=r, INPT=100)))
        cases.append((f"RATI {r}, INPT 100, fast, BLUE", knobs(RATI=r, INPT=100, ATK=127, REL=127, REV=1)))
    cases += [("RATI 7 (a stale byte: ALL)", knobs(RATI=7, INPT=110)),
              ("ATK 0 (OFF), INPT 127", knobs(ATK=0, INPT=127)),
              ("everything loud", knobs(INPT=127, OUTP=127, ATK=127, REL=127, RATI=4, REV=1)),
              ("ATK 0, INPT 127, OUTP 127 (the gain past the guard bits)", knobs(ATK=0, INPT=127, OUTP=127)),
              ("ATK 0, INPT 110, OUTP 127", knobs(ATK=0, INPT=110, OUTP=127))]
    print("bit-exact (dsp_host vs fixed()):")
    for sname, x in sig.items():
        worst = 0
        for label, kn in cases:
            L, R = render(x, x[::-1], kn)
            fL, fR, _ = REF.fixed(x, x[::-1], words(kn))
            d = max(max(abs(a - b) for a, b in zip(L, fL)), max(abs(a - b) for a, b in zip(R, fR)))
            if d:
                check(f"{sname}, {label}", False, f"max |dsp - model| = {d} LSB")
            worst = max(worst, d)
        check(f"{sname}: {len(cases)} knob sets", worst == 0, f"max |dsp - model| = {worst} LSB")
    x = sig["drums-like bursts"]
    kn = knobs(INPT=100, ATK=127, REL=127)
    L, R = render(x, x, kn, split=7)
    fL, fR, _ = REF.fixed(x, x, words(kn))
    check("a block split at frame 7", max(abs(a - b) for a, b in zip(L, fL)) == 0)
    if dirty_words:
        L, R = render(x, x, kn, pfrac=0xa5)
        fL, fR, _ = REF.fixed(x, x, words(kn, frac=0xa5))
        check("LFO-dirty page words ($a5)", max(abs(a - b) for a, b in zip(L, fL)) == 0)
    else:
        print("  [info] LFO-dirty page words: skipped -- this dsp_host has no -pword")
    # ATK 0 (no limiting) with every gain up: the output must clip, never wrap to the other sign
    ramp = q23(np.concatenate([np.linspace(0, 0.99, 2048), np.full(1024, 0.99), np.linspace(0, -0.99, 2048)]))
    for kn in (knobs(ATK=0, INPT=127, OUTP=127), knobs(ATK=0, INPT=110, OUTP=127), knobs(ATK=0, INPT=127, OUTP=110)):
        L, R = render(ramp, ramp, kn)
        bad = sum(1 for x, y in zip(ramp, L) if x * y < 0 and abs(x) > (1 << 16))
        check(f"no wrap: a ramp to +-0.99 at ATK 0, INPT {kn['INPT']}, OUTP {kn['OUTP']}", bad == 0,
              f"{bad} samples of the wrong sign, peak {max(abs(v) for v in L) / (1 << 23):.3f}")
    print("passthroughs:")
    L, R = render(x, x, knobs(MIX=0, INPT=127, OUTP=127, ATK=127, RATI=4, REV=1))
    check("MIX 0: exact with every other knob at an extreme", L == x)
    L, R = render([0] * 4096, [0] * 4096, knobs(INPT=127))
    check("silence in -> exact zeros out", not any(L) and not any(R))
    # ---- the 1176 (on the model's fixed output: the same numbers the dump gives) ----------------------
    print("the 1176LN manual (fixed-point model):")

    def peak_db(v, k=4410):
        return 20 * math.log10(max(max(abs(s) for s in v[-k:]) / (1 << 23), 1e-9))

    for r, want, thr in ((0, 4, -20), (1, 8, -17), (2, 12, -15), (3, 20, -13)):
        a = q23(tone(thr + 3, 22050)); b = q23(tone(thr + 9, 22050))
        oa = peak_db(REF.fixed(a, a, words(knobs(RATI=r)))[0])
        ob = peak_db(REF.fixed(b, b, words(knobs(RATI=r)))[0])
        ratio = 6 / max(ob - oa, 1e-6)
        check(f"RATI {r}: {want}:1 from 3 to 9 dB over its threshold", 0.8 * want <= ratio <= 1.15 * want,
              f"measured {ratio:.1f}:1")
    a = q23(tone(0, 22050))
    o = REF.fixed(a, a, words(knobs(ATK=0, INPT=64)))[2]
    check("ATK 0: the OFF click, no gain reduction", o["uA"] == 0)
    a = q23(tone(-3, 44100))
    out = REF.fixed(a, a, words(knobs(RATI=3, REL=0, ATK=100)))[0]
    y = np.array(out[-22050:], float) * np.hanning(22050)
    Y = np.abs(np.fft.rfft(y))
    h1 = Y[500 - 3:500 + 4].max()
    hs = [Y[500 * h - 3:500 * h + 4].max() / h1 for h in range(2, 8)]
    thd = 100 * math.sqrt(sum(v * v for v in hs))
    check("THD < 0.5 % at 1 kHz, 10 dB of limiting, REL 0 (the manual)", thd < 0.5, f"{thd:.2f} %")
    for hold, lo, hi in ((0.005, 0.0, 0.040), (1.0, 0.150, 0.400)):
        burst = q23(np.concatenate([tone(-3, int(hold * FS)), np.zeros(FS)]))
        tr = []
        REF.fixed(burst, burst, words(knobs(RATI=3, REL=64, ATK=100)), trace=tr)
        g = np.array([20 * math.log10(max(t[2], 1) / 0x400000) for t in tr])
        k0 = int(hold * FS)
        g0 = g[k0 - 1]
        t37 = np.argmax(g[k0:] >= 0.37 * g0) / FS
        check(f"release after {hold * 1000:.0f} ms of limiting, REL 64: {lo * 1000:.0f}..{hi * 1000:.0f} ms",
              lo <= t37 <= hi, f"{t37 * 1000:.0f} ms (GR {-g0:.1f} dB)")
    return FAILS


def dsp_host_render():
    from remix import registry
    import send_probe
    mod = registry.by_name("fet76")
    send = registry.by_name("send")
    K = mod.knob_map()
    mem = f"out/dsp/_audition_{mod.name}_A.mem"
    host = "vendor/dsp56300/build/source/dsp_host/dsp_host"
    tmp = pathlib.Path("out/_fet76gate")
    tmp.mkdir(parents=True, exist_ok=True)
    pathlib.Path(mem).unlink(missing_ok=True)
    subprocess.run([sys.executable, "tools/remix/audition.py", mod.name, "out/dry/drums_110.wav"],
                   capture_output=True)
    if not pathlib.Path(mem).exists():
        sys.exit(f"no {mem} -- build it first:\n  python3 tools/remix/audition.py {mod.name} out/dry/drums_110.wav")
    init, proc = send_probe.entry_points(mem, mod.menu.fx2_id)
    if (init, proc) == send_probe.entry_points(mem, send.menu.fx2_id):
        sys.exit(f"fx id 0x{mod.menu.fx2_id:02x} resolves to SEND's entry points -- fet76 is NOT in this dump")
    print(f"entries from dispatch tables: init=P:0x{init:04x} proc=P:0x{proc:04x}")

    def render(L, R, kn, split=0, pfrac=0):
        n = len(L) - len(L) % FRAMES
        src, out = tmp / "in.raw", tmp / "out.raw"
        inter = []
        for a, b in zip(L[:n], R[:n]):
            inter += [a, b]
        src.write_bytes(b"".join(struct.pack("<i", m) for m in inter))
        pv = [0] * 12
        for name, v in kn.items():
            pv[K[name]] = v
        cmd = [host, "-mem", mem, "-init", f"{init:x}", "-proc", f"{proc:x}",
               "-inst", "1", "-r7", "1", "-alloc", "0", "-inmask", "1", "-stereo",
               "-frames", str(FRAMES), "-blocks", str(n // FRAMES),
               "-in", str(src), "-out", str(out),
               "-params", ",".join(str(x) for x in pv)]
        if split:
            cmd += ["-split", str(split)]
        if pfrac:
            cmd += ["-pword", ",".join(f"0:{K[nm]:x}={((kn[nm] & 0x7f) << 16) | (pfrac << 8):x}"
                                       for nm in ("INPT", "OUTP", "ATK", "REL", "RATI", "MIX"))]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"dsp_host failed for {kn}:\n{r.stdout}\n{r.stderr}")
        w = struct.unpack(f"<{len(out.read_bytes()) // 4}i", out.read_bytes())
        return list(w[0::2])[:n], list(w[1::2])[:n]
    return render


def main():
    r = subprocess.run([sys.executable, "modules/fet76/generate_asm.py", "--check"],
                       capture_output=True, text=True)
    check("fet76.asm is generated from the template and the manifest", r.returncode == 0,
          (r.stdout + r.stderr).strip())
    src = pathlib.Path("tools/harness/dsp_host/dsp_host.cpp")
    dirty = src.exists() and "-pword" in src.read_text()
    fails = run_gates(dsp_host_render(), dirty_words=dirty)
    if fails:
        sys.exit(f"verify_fet76: {len(fails)} gate(s) failed")
    print("verify_fet76: all gates pass")


if __name__ == "__main__":
    main()
