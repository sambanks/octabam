#!/usr/bin/env python3
"""VCA160 render gates: the assembled module against its bit-exact model,
and the model against the dbx 160's own manual.

Renders the module straight through dsp_host (the render-gate shape: the id
and the slots come from the manifest, the entry points are checked against
SEND's). The side-chain bus is planted with -pokey (one word per track, as
dbt_tap writes it); the tap itself runs in the dispatcher, which make check
boots under the ColdFire port.

Gates:
  generated     -> vca160.asm is what the template and the manifest make
  bit-exact     -> the dump's code equals modules/vca160/vca160_ref.fixed():
                   defaults, every knob at both ends, OverEasy, KEY from a
                   planted bus word on either half, KEY out of range, a split
                   block, LFO-dirty page words
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
    """render(mono_q23, knobs, split=0, pfrac=0, bus=None) -> (L, R); bus is
    {Y address: word} planted before the run."""
    rng = np.random.default_rng(3)
    N = FRAMES * 900
    noise = q23(rng.uniform(-0.9, 0.9, N))
    sine = q23(0.6 * np.sin(2 * np.pi * 110 * np.arange(N) / FS))
    kickbus = {REF.bus_address(0): 0x200000, REF.bus_address(6): 0x050000}

    print("bit-exact against vca160_ref.fixed():")
    cases = [("defaults, noise", noise, knobs(), 0, 0, None),
             ("THRS 0 RATI 127 OUT 127 KNEE OVER, sine", sine, knobs(THRS=0, RATI=127, OUT=127, KNEE=1), 0, 0, None),
             ("THRS 127 RATI 0 OUT 0 MIX 1, noise", noise, knobs(THRS=127, RATI=0, OUT=0, MIX=1), 0, 0, None),
             ("KEY T1 (payload B's half), sine", sine, knobs(THRS=40, RATI=100, KEY=1), 0, 0, kickbus),
             ("KEY T7 (payload A's half), sine", sine, knobs(THRS=40, RATI=90, KEY=7, KNEE=1), 0, 0, kickbus),
             ("KEY 100 (out of range: OFF), sine", sine, knobs(THRS=40, RATI=90, KEY=100), 0, 0, kickbus),
             ("RATI 110 MIX 70, noise, split 5", noise, knobs(THRS=60, RATI=110, MIX=70), 5, 0, None),
             ("LFO-dirty page words ($a5), noise", noise, knobs(THRS=50, RATI=80, OUT=70), 0, 0xA5, None)]
    for label, sig, kn, split, pfrac, bus in cases:
        if pfrac and not dirty_words:
            print(f"  [info] {label}: skipped -- this dsp_host has no -pword")
            continue
        L, R = render(sig, kn, split=split, pfrac=pfrac, bus=bus)
        words = REF.page_words(**kn, frac=pfrac)
        mL, mR, _ = REF.fixed(sig[:len(L)], sig[:len(R)], words,
                              [bus or {}] * (len(L) // FRAMES + 1))
        d = max(max(abs(a - b) for a, b in zip(L, mL)), max(abs(a - b) for a, b in zip(R, mR)))
        check(f"{label}: max |dsp - model| = {d} LSB", d == 0)

    print("passthroughs:")
    quiet = q23(tone(-40, N))
    L, R = render(quiet, knobs(THRS=127, OUT=64))
    check("below threshold, OUT 0 dB: exact", L == quiet[:len(L)] and R == quiet[:len(R)])
    L, R = render(noise, knobs(MIX=0, THRS=0, RATI=127, OUT=127))
    check("MIX 0: exact with every other knob at an extreme", L == noise[:len(L)])

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
    L, _ = render(xq, knobs(THRS=64, RATI=100, KEY=2), bus=bus)
    check("KEY T2, an empty word: no ducking", L == xq[:len(L)])

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

    def render(samples, kn, split=0, pfrac=0, bus=None):
        n = len(samples) - len(samples) % FRAMES
        src, out = tmp / "in.raw", tmp / "out.raw"
        src.write_bytes(b"".join(struct.pack("<i", m) for m in samples[:n]))
        pv = [0] * 12
        for name, v in kn.items():
            pv[K[name]] = v
        cmd = [host, "-mem", mem, "-init", f"{init:x}", "-proc", f"{proc:x}",
               "-inst", "1", "-r7", "1", "-alloc", "0", "-inmask", "1",
               "-frames", str(FRAMES), "-blocks", str(n // FRAMES),
               "-in", str(src), "-out", str(out),
               "-params", ",".join(str(x) for x in pv)]
        if split:
            cmd += ["-split", str(split)]
        if pfrac:
            cmd += ["-pword", ",".join(f"0:{K[nm]:x}={((kn[nm] & 0x7f) << 16) | (pfrac << 8):x}"
                                       for nm in ("THRS", "RATI", "OUT", "KEY", "MIX"))]
        if bus:
            cmd += ["-pokey", ",".join(f"{a:x}={v & 0xffffff:x}" for a, v in bus.items())]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"dsp_host failed for {kn}:\n{r.stdout}\n{r.stderr}")
        w = struct.unpack(f"<{len(out.read_bytes()) // 4}i", out.read_bytes())
        return list(w[0::2])[:n], list(w[1::2])[:n]
    return render


def tap_gates():
    """The side-chain tap (dbt_tap) and its BEAT/COUNT/LAST handshake, run as
    the proc in dsp_host with the block at X:$00 (-audio 0). dsp_host's setup
    leaves x:$420 = 4, so the tap serves T5's record in payload A's half."""
    from remix import registry
    import send_probe
    mod = registry.by_name("vca160")
    mem = f"out/dsp/_audition_{mod.name}_A.mem"
    host = "vendor/dsp56300/build/source/dsp_host/dsp_host"
    init, _proc = send_probe.entry_points(mem, mod.menu.fx2_id)
    # dbt_tap's offset from init, from the assembled module
    d = pathlib.Path(tempfile.mkdtemp(prefix="dbxtap."))
    src = (pathlib.Path("modules/vca160/vca160.asm").read_text()
           .replace("$fab1e0", "$000400").replace("@ROFF@", "$37fe0"))
    (d / "s.asm").write_text(src)
    r = subprocess.run(["vendor/dsp56300/build/source/dsp_host/dsp_asm", "-in", str(d / "s.asm"), "-org", "0",
                        "-out", str(d / "s.bin"), "-sym", str(d / "s.sym")], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"dsp_asm failed on vca160.asm for the tap's offset:\n{r.stdout}\n{r.stderr}")
    sym = dict((n, int(v, 16)) for n, v in (ln.split() for ln in (d / "s.sym").read_text().splitlines() if ln.strip()))
    tapat = init + sym["dbt_tap"] - sym["init"]
    rec = REF.REC_A + 4 * 0                      # T5 = track 4, the first record of payload A's half
    BEAT, COUNT, LAST, LEVEL = rec, rec + 1, rec + 2, rec + 3
    rng = np.random.default_rng(666)
    frames = q23(rng.uniform(-0.9, 0.9, FRAMES * 12))   # mono: dsp_host puts each sample on L and R

    def run(blocks, poke):
        src_raw = d / "in.raw"
        src_raw.write_bytes(b"".join(struct.pack("<i", m) for m in frames[:FRAMES * blocks]))
        cmd = [host, "-mem", mem, "-init", f"{init:x}", "-proc", f"{tapat:x}", "-inst", "1", "-r7", "1",
               "-alloc", "0", "-inmask", "1", "-audio", "0", "-frames", str(FRAMES), "-blocks", str(blocks),
               "-in", str(src_raw), "-out", str(d / "out.raw"),
               "-pokey", ",".join(f"{a:x}={v & 0xffffff:x}" for a, v in poke.items()),
               "-peeky", ",".join(f"{a:x}" for a in (BEAT, COUNT, LAST, LEVEL))]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"dsp_host failed for the tap:\n{r.stdout}\n{r.stderr}")
        got = {}
        for ln in r.stdout.splitlines():
            ln = ln.strip()
            if ln.startswith("Y:0x"):
                a, v = ln[2:].split(" = ")
                got[int(a, 16)] = int(v, 16)
        return [got[a] for a in (BEAT, COUNT, LAST, LEVEL)]

    last_block = lambda n: REF.tap([w for m in frames[FRAMES * (n - 1):FRAMES * n] for w in (m, m)])
    print(f"the side-chain tap (dbt_tap at P:0x{tapat:04x}, T5's record at Y:0x{rec:05x}):")
    b, c, l, v = run(3, {LEVEL: 0x123456})
    check("nobody keys: asleep, LEVEL written 0, COUNT and LAST untouched", (b, c, l, v) == (0, 0, 0, 0),
          f"BEAT COUNT LAST LEVEL = {b:x} {c:x} {l:x} {v:x}")
    b, c, l, v = run(3, {BEAT: 0x800007, LAST: 0x800007, LEVEL: 0x123456})
    check("the same nonzero beat, COUNT 0 (a sign-extended word): asleep, LAST kept",
          (b, c, l, v) == (0x800007, 0, 0x800007, 0), f"BEAT COUNT LAST LEVEL = {b:x} {c:x} {l:x} {v:x}")
    b, c, l, v = run(1, {BEAT: 5, LEVEL: 0x123456})
    check(f"a new beat: LAST = BEAT, COUNT = {REF.M.WANT_BLOCKS}, LEVEL = vca160_ref.tap() of the block",
          (l, c, v) == (5, REF.M.WANT_BLOCKS, last_block(1)), f"COUNT {c} LAST {l:x} LEVEL {v:06x} model {last_block(1):06x}")
    b, c, l, v = run(9, {BEAT: 5, LEVEL: 0x123456})
    check("the same beat: counts down and keeps summing for WANT_BLOCKS blocks",
          (c, v) == (0, last_block(9)), f"COUNT {c} LEVEL {v:06x} model {last_block(9):06x}")
    b, c, l, v = run(10, {BEAT: 5, LEVEL: 0x123456})
    check("one block more: asleep, LEVEL 0", (c, v) == (0, 0), f"COUNT {c} LEVEL {v:06x}")
    b, c, l, v = run(2, {BEAT: 6, COUNT: 1, LAST: 5, LEVEL: 0x123456})
    check("a beat that changed while counting: refilled", (c, l) == (REF.M.WANT_BLOCKS - 1, 6),
          f"COUNT {c} LAST {l:x}")

    # the effect's side: a VCA160 with KEY T1 writes its heartbeat to T1's BEAT word; OFF writes nothing
    init_, proc_ = send_probe.entry_points(mem, mod.menu.fx2_id)
    K = mod.knob_map()
    t1 = REF.REC_B                                # T1's record (BEAT first)
    t8 = REF.REC_A + 4 * 3                        # T8's: the record an OFF (t = 7) would name

    def run_fx(key, blocks):
        pv = [0] * 12
        for name, v in knobs(KEY=key).items():
            pv[K[name]] = v
        src_raw = d / "in.raw"
        src_raw.write_bytes(b"".join(struct.pack("<i", m) for m in frames[:FRAMES * blocks]))
        cmd = [host, "-mem", mem, "-init", f"{init_:x}", "-proc", f"{proc_:x}", "-inst", "1", "-r7", "1",
               "-alloc", "0", "-inmask", "1", "-frames", str(FRAMES), "-blocks", str(blocks),
               "-in", str(src_raw), "-out", str(d / "out.raw"), "-params", ",".join(str(x) for x in pv),
               "-pokey", f"{t1:x}=abcdef,{t8:x}=abcdef", "-peeky", f"{t1:x},{t8:x}"]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"dsp_host failed for the effect's heartbeat:\n{r.stdout}\n{r.stderr}")
        vals = [int(ln.split(" = ")[1], 16) for ln in r.stdout.splitlines() if ln.strip().startswith("Y:0x")]
        if len(vals) != 2:
            sys.exit(f"dsp_host printed {len(vals)} Y peeks, not 2:\n{r.stdout}")
        return vals
    on3, on5 = run_fx(1, 3), run_fx(1, 5)
    check("KEY T1: the heartbeat goes into T1's BEAT word, one step a block", on3[0] == 3 and on5[0] == 5,
          f"after 3 blocks {on3[0]:x}, after 5 {on5[0]:x}")
    off = run_fx(0, 4)
    check("KEY OFF: no BEAT word is written (T1's and T8's, the one an OFF names, keep a sentinel)",
          off == [0xabcdef, 0xabcdef], " ".join(f"{v:x}" for v in off))


def precedent():
    """Every instruction FORM VCA160 uses (the tap included), looked up in
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
           .replace("$fab1e0", "$000400").replace("@ROFF@", "$3fff0"))
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
    tap_gates()
    fails = FAILS
    print("instruction forms:")
    precedent()
    if fails:
        sys.exit(f"verify_vca160: {len(fails)} gate(s) failed")
    print("verify_vca160: all gates pass")


if __name__ == "__main__":
    main()
