#!/usr/bin/env python3
"""VCA160 render gates: the assembled module against its bit-exact model,
and the model against the dbx 160's own manual.

Renders the module straight through dsp_host (the render-gate shape: the id
and the slots come from the manifest, the entry points are checked against
SEND's). KEY's source, KEYBUS's mean-square word per track, is planted with
-xword (X, as KEYBUS writes it); KEYBUS's own gate (verify_keybus) checks
that its tap writes those words, bit for bit against vca160_ref.tap().

Gates:
  generated     -> vca160.asm is what the template and the manifest make
  bit-exact     -> the dump's code equals modules/vca160/vca160_ref.fixed():
                   defaults, every knob at both ends, the OVER knee, KEY from a
                   planted KEYBUS word, every KEY T1..T8 on eight words that
                   all differ, KEY out of range, a split block,
                   LFO-dirty page words, and two stereo renders (L != R)
  passthrough   -> below threshold at OUT 0 dB: exact; MIX 0: exact
  the manual    -> attack (63 %) for 10 / 20 / 30 dB over threshold at
                   infinity:1 near 15 / 5 / 3 ms; release near 125 dB/s
  the ratios    -> 2:1, 4:1, 120:1 and -1:1 (the 160A) on a steady tone
  the key       -> a planted T1 word above threshold ducks a quiet tone by
                   the float law's amount
  silence       -> silence in, exact zeros out
  every knob    -> renders without dsp_host dying

    python3 tools/verify/verify_vca160.py
"""
import importlib.util
import math
import pathlib
import struct
import subprocess
import tempfile
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401

ROOT = pathlib.Path(__file__).resolve().parents[2]
FRAMES = 16
_spec = importlib.util.spec_from_file_location("vca160_ref", ROOT / "modules/vca160/vca160_ref.py")
REF = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(REF)
FS = int(REF.FS)
DEFAULTS = {"THRS": 96, "RATI": 50, "OUT": 64, "KEY": 0, "MIX": 127, "KNEE": 0}
FAILS = []


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILS.append(label)


def q23(x):
    return [max(-(1 << 23), min((1 << 23) - 1, int(round(s * (1 << 23))))) for s in x]


def knobs(**kw):
    k = dict(DEFAULTS); k.update(kw); return k


def tone(level_dbfs_rms, n, f=1000.0):
    t = np.arange(n) / FS
    return math.sqrt(2) * 10 ** (level_dbfs_rms / 20) * np.sin(2 * np.pi * f * t)


def level_db(x):
    x = np.asarray(x, float) / (1 << 23)
    return 10 * np.log10(max(np.mean(x ** 2), 1e-30))


def env_db(x, period):
    x = np.asarray(x, float) / (1 << 23)
    return 10 * np.log10(np.maximum(np.convolve(x ** 2, np.ones(period) / period, "same"), 1e-30))


def run_gates(render, dirty_words=True):
    """render(mono_q23, knobs, split=0, pfrac=0, bus=None, right=None) -> (L, R); bus is
    {X address: word} planted before the run (KEYBUS's words); right, when given, is the R input (L != R)."""
    rng = np.random.default_rng(3)
    N = FRAMES * 900
    noise = q23(rng.uniform(-0.9, 0.9, N))
    sine = q23(0.6 * np.sin(2 * np.pi * 110 * np.arange(N) / FS))
    kickbus = {REF.bus_address(0): 0x200000, REF.bus_address(6): 0x050000}

    print("bit-exact against vca160_ref.fixed():")
    cases = [("defaults, noise", noise, knobs(), 0, 0, None),
             ("THRS 0 RATI 127 OUT 127 KNEE OVER, sine", sine, knobs(THRS=0, RATI=127, OUT=127, KNEE=1), 0, 0, None),
             ("THRS 127 RATI 0 OUT 0 MIX 1, noise", noise, knobs(THRS=127, RATI=0, OUT=0, MIX=1), 0, 0, None),
             ("KEY T1, sine", sine, knobs(THRS=40, RATI=100, KEY=1), 0, 0, kickbus),
             ("KEY T7, sine", sine, knobs(THRS=40, RATI=90, KEY=7, KNEE=1), 0, 0, kickbus),
             ("KEY 100 (out of range: OFF), sine", sine, knobs(THRS=40, RATI=90, KEY=100), 0, 0, kickbus),
             ("RATI 110 MIX 70, noise, split 5", noise, knobs(THRS=60, RATI=110, MIX=70), 5, 0, None),
             ("LFO-dirty page words ($a5), noise", noise, knobs(THRS=50, RATI=80, OUT=70), 0, 0xA5, None)]
    # every KEY on a bus whose eight words all differ: a KEY that reads the wrong track's record fails here
    allbus = {REF.bus_address(t): 0x030000 + 0x0b0000 * t for t in range(8)}
    cases += [(f"KEY T{k}, eight different bus words, sine", sine, knobs(THRS=40, RATI=100, KEY=k), 0, 0, allbus)
              for k in range(1, 9)]
    # L != R: a channel read from the wrong side (R from L's word) fails here; every case above has L = R
    cases += [("stereo: noise L, sine R, compressing", (noise, sine), knobs(THRS=50, RATI=90), 0, 0, None),
              ("stereo: sine L, noise R, KEY T3, KNEE OVER", (sine, noise), knobs(THRS=40, RATI=100, KEY=3, KNEE=1),
               0, 0, allbus)]
    for label, sig, kn, split, pfrac, bus in cases:
        if pfrac and not dirty_words:
            print(f"  [info] {label}: skipped -- this dsp_host has no -pword")
            continue
        sl, sr = sig if isinstance(sig, tuple) else (sig, None)
        L, R = render(sl, kn, split=split, pfrac=pfrac, bus=bus, right=sr)
        words = REF.page_words(**kn, frac=pfrac)
        mL, mR, _ = REF.fixed(sl[:len(L)], (sr if sr is not None else sl)[:len(R)], words,
                              [bus or {}] * (len(L) // FRAMES + 1))
        d = max(max(abs(a - b) for a, b in zip(L, mL)), max(abs(a - b) for a, b in zip(R, mR)))
        check(f"{label}: max |dsp - model| = {d} LSB", d == 0)

    print("passthroughs:")
    quiet = q23(tone(-40, N))
    L, R = render(quiet, knobs(THRS=127, OUT=64))
    check("below threshold, OUT 0 dB: exact", L == quiet[:len(L)] and R == quiet[:len(R)])
    L, R = render(noise, knobs(MIX=0, THRS=0, RATI=127, OUT=127))
    check("MIX 0: exact with every other knob at an extreme", L == noise[:len(L)] and R == noise[:len(R)])

    print("the dbx 160 manual:")
    T = REF.threshold_db(30)
    n = FRAMES * 1500
    t = np.arange(n) / FS
    a0 = math.sqrt(2) * 10 ** (T / 20)
    for X, lo, hi, want in ((10, 10.0, 22.0, 15), (20, 3.5, 9.0, 5), (30, 2.0, 4.5, 3)):
        x = np.where(t < 0.2, a0, a0 * 10 ** (X / 20)) * np.sin(2 * np.pi * 1000 * t)
        xq = q23(x)
        L, _ = render(xq, knobs(THRS=30, RATI=100))
        g = env_db(L, 44) - env_db(xq[:len(L)], 44)
        i0 = int(0.2 * FS)
        gfin = float(np.median(g[i0 + int(0.25 * FS):i0 + int(0.3 * FS)]))
        k = int(np.argmax(g[i0:] <= 0.632 * gfin))
        ms = k / FS * 1e3
        check(f"attack, {X} dB over threshold at inf:1: 63 % of {gfin:.1f} dB in {ms:.1f} ms "
              f"(the manual: {want} ms)", lo <= ms <= hi)
    x = np.where(t < 0.3, a0 * 10 ** (25 / 20), a0 * 10 ** (-5 / 20)) * np.sin(2 * np.pi * 1000 * t)
    xq = q23(x)
    L, _ = render(xq, knobs(THRS=30, RATI=100))
    g = env_db(L, 44) - env_db(xq[:len(L)], 44)
    i0 = int(0.3 * FS)
    seg = g[i0 + 200:i0 + int(0.12 * FS)]
    idx = np.nonzero((seg < -3) & (seg > -20))[0]
    rate = float(np.polyfit(idx / FS, seg[idx], 1)[0])
    check(f"release: {rate:.0f} dB/s (the manual: 125 dB/s)", 110 <= rate <= 140)

    print("the ratios (a 1 kHz tone 10 dB over THRS 76):")
    T = REF.threshold_db(76)
    xq = q23(tone(T + 10, FRAMES * 1500))
    for rati, name, want in ((50, "2:1", 5.0), (75, "4:1", 2.6), (100, "120:1", 0.1), (127, "-1:1", -10.0)):
        L, _ = render(xq, knobs(THRS=76, RATI=rati))
        o = level_db(L[-8000:]) - T
        check(f"RATI {rati} ({name}): +10 dB in -> {o:+.2f} dB out (want {want:+.1f})", abs(o - want) < 0.3)

    print("the key:")
    word = 0x200000                           # mean square 1/4: -6 dBFS RMS
    xq = q23(tone(-30, FRAMES * 1500))
    bus = {REF.bus_address(0): word}
    L, _ = render(xq, knobs(THRS=64, RATI=100, KEY=1), bus=bus)
    duck = level_db(L[-8000:]) - level_db(xq[-8000:])
    ref = REF.VCA160(THRS=64, RATI=100)
    ref.S = word / (1 << 23)
    want = ref.gain_db(ref.S)
    check(f"KEY T1, a planted -6 dBFS word: a -30 dBFS tone ducked {duck:+.2f} dB (the law: {want:+.2f})",
          abs(duck - want) < 0.3)
    L, R = render(xq, knobs(THRS=64, RATI=100, KEY=2), bus=bus)
    check("KEY T2, an empty word: no ducking", L == xq[:len(L)] and R == xq[:len(R)])

    L, R = render([0] * (FRAMES * 300), knobs(THRS=0, RATI=127, OUT=127))
    check("silence in -> exact zeros out", max(abs(v) for v in L + R) == 0)

    ok = True
    for name in ("THRS", "RATI", "OUT", "MIX"):
        for v in (0, 1, 63, 64, 126, 127):
            try:
                render(noise[:FRAMES * 40], knobs(**{name: v}))
            except SystemExit:
                ok = False
    for v in range(9):
        try:
            render(noise[:FRAMES * 40], knobs(KEY=v), bus=kickbus)
        except SystemExit:
            ok = False
    check("every knob at its ends, every KEY", ok)
    return FAILS


def dsp_host_render():
    from remix import registry
    import send_probe
    mod = registry.by_name("vca160")
    send = registry.by_name("send")
    K = mod.knob_map()
    mem = f"out/dsp/_audition_{mod.name}_A.mem"
    host = "vendor/dsp56300/build/source/dsp_host/dsp_host"
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="dbxgate."))   # per process (TRAPS: trap-tmp-race)
    pathlib.Path(mem).unlink(missing_ok=True)
    subprocess.run([sys.executable, "tools/remix/audition.py", mod.name, "out/dry/drums_110.wav"],
                   capture_output=True)
    if not pathlib.Path(mem).exists():
        sys.exit(f"no {mem} -- build it first:\n  python3 tools/remix/audition.py {mod.name} out/dry/drums_110.wav")
    init, proc = send_probe.entry_points(mem, mod.menu.fx2_id)
    if (init, proc) == send_probe.entry_points(mem, send.menu.fx2_id):
        sys.exit(f"fx id 0x{mod.menu.fx2_id:02x} resolves to SEND's entry points -- vca160 is NOT in this dump")
    print(f"entries from dispatch tables: init=P:0x{init:04x} proc=P:0x{proc:04x}")

    def render(samples, kn, split=0, pfrac=0, bus=None, right=None):
        n = len(samples) - len(samples) % FRAMES
        src, out = tmp / "in.raw", tmp / "out.raw"
        if right is None:
            src.write_bytes(b"".join(struct.pack("<i", m) for m in samples[:n]))
        else:                                       # interleaved L, R (dsp_host -stereo)
            src.write_bytes(b"".join(struct.pack("<ii", a, b) for a, b in zip(samples[:n], right[:n])))
        pv = [0] * 12
        for name, v in kn.items():
            pv[K[name]] = v
        cmd = [host, "-mem", mem, "-init", f"{init:x}", "-proc", f"{proc:x}",
               "-inst", "1", "-r7", "1", "-alloc", "0", "-inmask", "1",
               "-frames", str(FRAMES), "-blocks", str(n // FRAMES),
               "-in", str(src), "-out", str(out),
               "-params", ",".join(str(x) for x in pv)]
        if right is not None:
            cmd += ["-stereo"]
        if split:
            cmd += ["-split", str(split)]
        if pfrac:
            cmd += ["-pword", ",".join(f"0:{K[nm]:x}={((kn[nm] & 0x7f) << 16) | (pfrac << 8):x}"
                                       for nm in ("THRS", "RATI", "OUT", "KEY", "MIX"))]
        if bus:
            cmd += ["-xword", ",".join(f"{a:x}={v & 0xffffff:x}" for a, v in bus.items())]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"dsp_host failed for {kn}:\n{r.stdout}\n{r.stderr}")
        w = struct.unpack(f"<{len(out.read_bytes()) // 4}i", out.read_bytes())
        return list(w[0::2])[:n], list(w[1::2])[:n]
    return render


def precedent():
    """Every instruction FORM VCA160 uses, looked up in
    stock's own payloads (AGENTS.md: "an instruction form the chip has never
    run is not proven by the port"); after verify_distorx. A form with no
    stock site is REPORTED, not failed."""
    import re
    stock = pathlib.Path("out/dsp/payload_A.asm")
    if not stock.exists():
        subprocess.run([sys.executable, "tools/build/dsp_disasm_all.py"], capture_output=True)
    if not stock.exists():
        print("  [SKIP] precedent: out/dsp/payload_A.asm missing (tools/build/dsp_disasm_all.py)")
        return

    def norm(line):
        m = re.match(r"^[0-9a-f]{6}: (\S+)(?:\s+(.*?))?\s*;", line)
        if not m:
            return None
        ops = (m.group(2) or "")
        ops = re.sub(r"\$[0-9a-f]+|\b\d+\b", "#", ops)
        ops = re.sub(r"\br[0-7]\b", "rN", ops)
        ops = re.sub(r"\bn[0-7]\b", "nN", ops)
        ops = re.sub(r"\bm[0-7]\b", "mN", ops)
        return f"{m.group(1)} {ops}".strip()
    have = set()
    for tag in ("A", "B"):
        f = pathlib.Path(f"out/dsp/payload_{tag}.asm")
        if f.exists():
            have |= {n for n in map(norm, f.read_text().splitlines()) if n}
    src = (pathlib.Path("modules/vca160/vca160.asm").read_text()
           .replace("$fab1e0", "$000400"))
    d = pathlib.Path(tempfile.mkdtemp(prefix="dbxprec."))
    (d / "s.asm").write_text(src)
    r = subprocess.run(["vendor/dsp56300/build/source/dsp_host/dsp_asm", "-in", str(d / "s.asm"),
                        "-org", "800", "-out", str(d / "s.bin"), "-sym", str(d / "s.sym"), "-list"],
                       capture_output=True, text=True)
    ours = {n for n in map(norm, r.stdout.splitlines()) if n}
    missing = sorted(ours - have)
    print(f"  [info] instruction forms: {len(ours)} used, {len(ours) - len(missing)} with a stock site"
          + ("" if not missing else "; WITHOUT one (watch these on the first flash):"))
    for m in missing:
        print(f"           {m}")


def main():
    r = subprocess.run([sys.executable, "modules/vca160/generate_asm.py", "--check"],
                       capture_output=True, text=True)
    check("vca160.asm is generated from the template and the manifest", r.returncode == 0,
          (r.stdout + r.stderr).strip())
    src = pathlib.Path("tools/harness/dsp_host/dsp_host.cpp")
    dirty = src.exists() and "-pword" in src.read_text()
    fails = run_gates(dsp_host_render(), dirty_words=dirty)
    print("instruction forms:")
    precedent()
    if fails:
        sys.exit(f"verify_vca160: {len(fails)} gate(s) failed")
    print("verify_vca160: all gates pass")


if __name__ == "__main__":
    main()
