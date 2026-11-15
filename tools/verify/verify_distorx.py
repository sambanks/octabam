#!/usr/bin/env python3
"""DISTORX render gates: the assembled module against its bit-exact model,
the SD-1 against the 1981 service notes, the RAT against its
own circuit and ElectroSmash's analysis.

Renders the module straight through dsp_host (the render-gate shape: the id
and the slots come from the manifest, and the entry points are checked
against SEND's so an absent module cannot pass as a dry passthrough).

Gates:
  generated      -> distorx.asm is what the template and the manifest make
  bit-exact      -> the dump's code equals distorx_ref.fixed() word for word:
                    every MODE at its defaults and its extremes, a split
                    block, page words dirtied the way an LFO leaves them,
                    MODE changes mid-render (the fade and the switch), MODE
                    knob values past TURB
  MIX 0          -> exact passthrough, every MODE, every other knob extreme
  service notes  -> SD-1: the 1981 WAVEFORM CHECKING page, +-20 %
  the analysis   -> RAT: ElectroSmash's clipping-amplifier curve (64 dB near
                    700 Hz at full DISTORTION; 24 dB at 1.5 kHz with 1 k), the
                    FILTER's corner at full left (475 Hz), the diodes' level
                    (1N914 ~ 0.65 V, red LED ~ 1.8 V), symmetric clipping
  the circuit    -> RAT/TURBO track the float circuit (exact diode law),
                    within -40 dB; and its 8x ground truth (aliasing)
  v8             -> MODE OFF (0, the default) is an exact passthrough; OFF and the
                    pedals switched back and forth, and the knob cache (DRIV TONE LEVL
                    moving every few blocks), bit-exact against the model
  silence        -> silence in, exact zeros out after 100 ms, every MODE; after
                    a loud burst: SD-1 exact zeros after 0.5 s, RAT/TURBO
                    under -90 dBFS after 2 s (C7 keeps a charge; README)
  the fade       -> a MODE change makes no step larger than the signal's own
  every knob     -> renders without dsp_host dying, every MODE

    python3 tools/verify/verify_distorx.py
"""
import importlib.util
import pathlib
import struct
import subprocess
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401

ROOT = pathlib.Path(__file__).resolve().parents[2]
FRAMES = 16

_spec = importlib.util.spec_from_file_location("distorx_ref", ROOT / "modules/distorx/distorx_ref.py")
REF = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(REF)
FS = int(REF.FS)
KNOBS = ("LEVL", "TONE", "DRIV", "IN", "MIX", "MODE")
DEFAULTS = {"LEVL": 64, "TONE": 64, "DRIV": 64, "IN": 64, "MIX": 127, "MODE": 0}
FADE = 128          # samples: the start-up fade-in (d from -1 to 0, 1/128 a sample)

FAILS = []


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILS.append(label)


def q23(x):
    return [max(-(1 << 23), min((1 << 23) - 1, int(round(s * (1 << 23))))) for s in x]


OFF = -1            # v8: the MODE knob reads 0 OFF, 1 SD-1, 2 RAT, 3 TURB; the gates keep the
                    # pedal index (0 SD-1, 1 RAT, 2 TURB) and knobs() writes the knob's value


def knobs(**kw):
    k = dict(DEFAULTS)
    k.update(kw)
    k["MODE"] = 0 if k["MODE"] == OFF else min(127, k["MODE"] + 1)
    return k


def acid_line(n, seed=1):
    """A 303-like line: a saw through a resonant 4-pole low-pass whose
    cutoff falls after every note, at -6 dBFS."""
    rng = np.random.default_rng(seed)
    step = int(FS * 60 / 132 / 4)
    notes = rng.choice([36, 36, 39, 43, 48, 46, 41], size=n // step + 1)
    out = np.zeros(n)
    ph, s = 0.0, np.zeros(4)
    for i in range(n):
        k, j = divmod(i, step)
        f = 440 * 2 ** ((notes[k] - 69) / 12)
        ph = (ph + f / FS) % 1.0
        env = np.exp(-j / (0.12 * FS))
        fc = 300 * 2 ** (4 * env)
        g = 1 - np.exp(-2 * np.pi * fc / FS)
        x = np.tanh((2 * ph - 1) - 3.2 * s[3])
        s[0] += g * (x - s[0]); s[1] += g * (s[0] - s[1])
        s[2] += g * (s[1] - s[2]); s[3] += g * (s[2] - s[3])
        out[i] = s[3] * min(1.0, j / 40) * (1.0 if j < 0.8 * step else 0.0)
    return 0.5 * out / max(1e-9, np.max(np.abs(out)))


def tone_db(y, f, start=0):
    """the level of the f component of y (one bin, Hann), dB re 1.0"""
    y = np.asarray(y, float)[start:]
    w = np.hanning(len(y))
    t = np.arange(len(y)) / FS
    c = np.sum(y * w * np.exp(-2j * np.pi * f * t)) / np.sum(w) * 2
    return 20 * np.log10(max(abs(c), 1e-30))


def run_gates(render, dirty_words=True):
    """render(samples_q23_mono, knobs: dict | [dict per block], split=0, pfrac=0) -> (L, R) int lists.
    dirty_words=False skips the LFO-word case (a dsp_host without -pword)."""
    rng = np.random.default_rng(11)
    N = FRAMES * 600
    acid = q23(acid_line(N))
    noise = q23(rng.uniform(-0.99, 0.99, N))
    t = np.arange(N) / FS
    square = q23(0.999 * np.sign(np.sin(2 * np.pi * 97 * t)))

    def model(sig, kn, split=0, pfrac=0):
        if isinstance(kn, list):
            words = [REF.knob_words(**k, frac=pfrac) for k in kn]
        else:
            words = REF.knob_words(**kn, frac=pfrac)
        return REF.fixed(sig, sig, words, frames=FRAMES, split=split)[:2]

    # ---- bit-exact against the model ----------------------------------------
    print("bit-exact against distorx_ref.fixed():")
    cases = []
    for m, name in ((0, "SD-1"), (1, "RAT"), (2, "TURBO")):
        cases += [(f"{name} defaults, acid", acid, knobs(MODE=m), 0, 0),
                  (f"{name} all max, acid", acid, knobs(MODE=m, LEVL=127, TONE=127, DRIV=127, IN=127), 0, 0),
                  (f"{name} all min, noise", noise, knobs(MODE=m, LEVL=0, TONE=0, DRIV=0, IN=0, MIX=1), 0, 0),
                  (f"{name} DRIV 127 TONE 0 IN 127, full-scale square", square,
                   knobs(MODE=m, DRIV=127, TONE=0, IN=127, LEVL=127), 0, 0),
                  (f"{name} MIX 50, noise, split 7", noise, knobs(MODE=m, MIX=50, DRIV=90, TONE=30), 7, 0),
                  (f"{name} LFO-dirty page words (bits 8-15 = $a5), acid", acid,
                   knobs(MODE=m, DRIV=77, TONE=99, LEVL=33, IN=20), 0, 0xA5)]
    nb = N // FRAMES
    seq = [knobs(MODE=0)] * 60 + [knobs(MODE=1)] * 80 + [knobs(MODE=2, DRIV=110)] * 120 \
        + [knobs(MODE=0, TONE=10)] * 90 + [knobs(MODE=1, MIX=90)] * 3 + [knobs(MODE=0)] * (nb - 353)
    seq_off = [knobs(MODE=OFF)] * 50 + [knobs(MODE=0)] * 100 + [knobs(MODE=OFF)] * 60 \
        + [knobs(MODE=1, DRIV=120)] * 100 + [knobs(MODE=OFF, DRIV=120)] * 40 + [knobs(MODE=2)] * (nb - 350)
    rk = np.random.default_rng(5)
    seq_kn = []
    for b in range(nb):
        if b % 3 == 0:
            cur = dict(DRIV=int(rk.integers(0, 128)), TONE=int(rk.integers(0, 128)), LEVL=int(rk.integers(0, 128)))
        seq_kn.append(knobs(MODE=0 if b < nb // 2 else 1, **cur))
    cases += [("v8 knob cache: DRIV TONE LEVL changed every 3 blocks, SD-1 then RAT", acid, seq_kn, 0, 0),
              ("v8 knob cache: one knob held, then moved, held, split 9", noise,
               [knobs(MODE=2, DRIV=40)] * 100 + [knobs(MODE=2, DRIV=41)] + [knobs(MODE=2, DRIV=40)] * (nb - 101), 9, 0),
              ("v8 OFF -> SD-1 -> OFF -> RAT -> OFF -> TURB, split 6", acid, seq_off, 6, 0),
              ("v8 OFF, every other knob at an extreme", noise, knobs(MODE=OFF, DRIV=127, TONE=0, LEVL=127, IN=127, MIX=1), 0, 0),
              ("MODE changes mid-render: SD-1 RAT TURB SD-1, a short RAT, split 5", acid, seq, 5, 0),
              ("MODE knob past TURB (5, 64, 127 read as TURB)", acid,
               [knobs(MODE=5)] * 200 + [knobs(MODE=64)] * 200 + [knobs(MODE=127)] * (nb - 400), 0, 0)]
    for label, sig, kn, split, pfrac in cases:
        if pfrac and not dirty_words:
            print(f"  [info] {label}: skipped -- this dsp_host has no -pword (AGENTS.md, 5 Oct 2026)")
            continue
        L, R = render(sig, kn, split=split, pfrac=pfrac)
        mL, mR = model(sig[:len(L)], kn, split=split, pfrac=pfrac)
        d = max(max(abs(a - b) for a, b in zip(L, mL)), max(abs(a - b) for a, b in zip(R, mR)))
        check(f"{label}: max |dsp - model| = {d} LSB", d == 0)

    # ---- MIX 0 ------------------------------------------------------------------
    for m in (0, 1, 2):
        ok = True
        for sig in (noise, square):
            L, R = render(sig, knobs(MODE=m, MIX=0, DRIV=127, TONE=0, LEVL=127, IN=127))
            ok &= L == sig[:len(L)] and R == sig[:len(R)]
        check(f"MIX 0: exact passthrough with the pedal at its extremes (MODE {m}, noise and square)", ok)
    ok = True
    for sig in (noise, square, acid):
        L, R = render(sig, knobs(MODE=OFF, MIX=127, DRIV=127, TONE=0, LEVL=127, IN=127))
        ok &= L == sig[:len(L)] and R == sig[:len(R)]
    check("v8 MODE OFF (the default): exact passthrough, every other knob at an extreme (noise, square, acid)", ok)

    # ---- the SD-1's service notes ----------------------------------------------------
    print("SD-1: the 1981 service notes (WAVEFORM CHECKING), 150 Hz square, 200 mVp-p:")
    n = FRAMES * 900
    tt = np.arange(n) / FS
    sq = q23(0.1 * np.sign(np.sin(2 * np.pi * 150 * tt)))
    mk = REF.M.MAKEUP
    for label, kn, want in (("DRIVE min, TONE max", knobs(DRIV=0, TONE=127, LEVL=127), 1.2),
                            ("DRIVE max, TONE max", knobs(DRIV=127, TONE=127, LEVL=127), 1.2),
                            ("DRIVE max, TONE min", knobs(DRIV=127, TONE=0, LEVL=127), 0.8)):
        L, _ = render(sq, kn)
        y = np.asarray(L[n // 2:], float) / (1 << 23) / mk
        vpp = float(y.max() - y.min())
        check(f"{label}: {vpp:.2f} Vp-p at the jack (the notes: {want} Vp-p, +-20 %)",
              abs(vpp / want - 1) < 0.2)

    # ---- the RAT against ElectroSmash's analysis -----------------------------------
    print("RAT: ElectroSmash's analysis:")
    # (1) the clipping amplifier, small signal: the float circuit's own LM308 stage
    #     (the DSP tracks that circuit, below). The analysis plots it with C4;
    #     the module leaves C4 out (README), worth <= 0.5 dB here.
    def amp_db(f, rd, fs=2 * FS):
        c = REF.RATCircuit(fs, 1)
        P = 1 + rd * (1 / (REF.RAT.R4 + 1 / (2 * fs * REF.RAT.C5)) + 1 / (REF.RAT.R5 + 1 / (2 * fs * REF.RAT.C6)))
        c2 = REF.RATCircuit(fs, 1, DRIV=0)
        # rebuild the stage for this exact Rd
        import math as _m
        W = c.W
        c2.q = 1 / P
        th = max(0.5, 1 / (1 + REF.RAT.THETA_C) - P / W)
        r = P / (P + th * W)
        c2.c_vo, c2.c_d1, c2.c_e = r, (1 - th) * r, th * W * r
        c2.SRT, c2.VS = 1e9, 1e9
        nn = int(fs * 0.4)
        x = 1e-6 * np.sin(2 * np.pi * f * np.arange(nn) / fs)
        y = np.empty(nn)
        for i, v in enumerate(x):
            Hn = c2.lam * c2.vh5 + (1 - c2.lam) * c2.vh6
            c0 = (1 - c2.q) * Hn
            vo = c2.c_vo * c2.vo + c2.c_d1 * c2.d1 + c2.c_e * (v - c0)
            vm = c2.q * vo + c0
            c2.d1 = c2.W * (v - vm)
            c2.vh5 += c2.k5 * (vm - c2.vh5)
            c2.vh6 += c2.k6 * (vm - c2.vh6)
            c2.vo = vo
            y[i] = vo
        seg = slice(nn // 2, None)
        tt_ = np.arange(nn)[seg] / fs
        e = np.exp(-2j * np.pi * f * tt_)
        return 20 * np.log10(abs(np.sum(y[seg] * e)) / abs(np.sum(x[seg] * e)))
    ff = np.array([400, 500, 600, 700, 800, 900, 1000, 1200])
    hh = np.array([amp_db(f, 100e3) for f in ff])
    pk, fpk = hh.max(), ff[hh.argmax()]
    check(f"the clipping amplifier at full DISTORTION peaks at {pk:.1f} dB near {fpk} Hz "
          f"(the analysis: ~64 dB near 700 Hz, +-1.5 dB, 500..1000 Hz)", abs(pk - 64) < 1.5 and 500 <= fpk <= 1000)
    a15, a60 = amp_db(1500, 1e3), amp_db(60, 1e3)
    check(f"DISTORTION 1 k: {a15:.1f} dB at 1.5 kHz, {a60:.1f} dB at 60 Hz "
          f"(the analysis: 24 dB and 8 dB, +-1.5 dB)", abs(a15 - 24) < 1.5 and abs(a60 - 8) < 1.5)
    # (2) FILTER at full left: the corner, small signal, through the DSP
    nn = FRAMES * 2400
    tt2 = np.arange(nn) / FS

    def lvl(f, **kn):
        x = q23(0.002 * np.sin(2 * np.pi * f * tt2))
        L, _ = render(x, knobs(MODE=1, DRIV=0, LEVL=127, **kn))
        return tone_db(L, f, nn // 2) - tone_db(x, f, nn // 2)
    # The analysis's 475 Hz is R7 + 100 k against C8 alone; the circuit also
    # has R6's 1 k in series (the diodes off) and C9 into R8's 1 M across C8.
    # The expectation is that whole network's own -3 dB point, analog.
    def net(f):
        s_ = 2j * np.pi * f
        z9 = REF.RAT.R8 + 1 / (s_ * REF.RAT.C9)
        zx = 1 / (s_ * REF.RAT.C8 + 1 / z9)
        return abs(zx / (REF.RAT.R6 + REF.RAT.R7 + REF.RAT.RTONE + zx) * REF.RAT.R8 / z9)
    fg = np.geomspace(150, 1500, 4000)
    want = fg[np.argmax(20 * np.log10([net(f) / net(100) for f in fg]) < -3)]
    ref100 = lvl(100, TONE=0)
    lo_, hi_ = 300.0, 1200.0
    for _ in range(14):
        mid = (lo_ * hi_) ** 0.5
        if lvl(mid, TONE=0) < ref100 - 3.0:
            hi_ = mid
        else:
            lo_ = mid
    fc = (lo_ * hi_) ** 0.5
    check(f"FILTER full left: -3 dB at {fc:.0f} Hz (the network R6 + R7 + 100 k, C8, C9/R8: "
          f"{want:.0f} Hz, +-5 %; the analysis's R7 + 100 k against C8 alone: 475 Hz)",
          abs(fc / want - 1) < 0.05)
    # (3) the diodes' level, (4) symmetric clipping
    nn = FRAMES * 1800
    tt3 = np.arange(nn) / FS
    sine = q23(0.5 * np.sin(2 * np.pi * 220 * tt3))
    # 0.85 V, not 0.80: at 1x the float circuit itself peaks at 0.80 V on this
    # bright square (0.73 V at 8x): the sampled peak, not the diodes' law.
    for m, lo, hi_, nm in ((1, 0.55, 0.85, "1N914"), (2, 1.5, 2.2, "red LED")):
        L, _ = render(sine, knobs(MODE=m, DRIV=127, TONE=127, LEVL=127))
        y = np.asarray(L[nn // 2:], float) / (1 << 23) / REF.M.MAKEUP_RAT[m]
        pk = (y.max() - y.min()) / 2
        check(f"MODE {m}: the clipped wave's peak {pk:.2f} V at the gate ({nm}: {lo}..{hi_} V)", lo <= pk <= hi_)
        h2 = tone_db(L, 440, nn // 2) - tone_db(L, 220, nn // 2)
        check(f"MODE {m}: symmetric clipping, the 2nd harmonic {h2:.1f} dB re the fundamental "
              f"(the SD-1: about -33 dB)", h2 < -45)

    # ---- the circuit ---------------------------------------------------------------
    print("RAT/TURBO against the float circuit (exact diode law):")
    x = np.asarray(acid, float) / (1 << 23)
    for kn in (dict(MODE=1), dict(MODE=1, DRIV=127), dict(MODE=1, DRIV=0), dict(MODE=1, TONE=0),
               dict(MODE=1, TONE=127), dict(MODE=2), dict(MODE=2, DRIV=127, TONE=20)):
        L, _ = render(acid, knobs(**kn))
        y = np.asarray(L, float) / (1 << 23)
        kf = {k: v for k, v in kn.items() if k != "MODE"}
        ref = REF.rat_module_float(x[:len(y)], x[:len(y)], mode=kn["MODE"], **kf)[0]
        sl = slice(FS // 5, None)
        e = 10 * np.log10(np.mean((y[sl] - ref[sl]) ** 2) / np.mean(ref[sl] ** 2))
        check(f"{kn}: the module vs the float circuit at 1x: {e:.1f} dB", e < -40)
    try:
        import scipy  # noqa: F401
        for kn in (dict(MODE=1), dict(MODE=1, DRIV=127), dict(MODE=2)):
            L, _ = render(acid, knobs(**kn))
            y = np.asarray(L, float) / (1 << 23)
            kf = {k: v for k, v in kn.items() if k != "MODE"}
            tr = REF.rat_oversampled(x[:len(y)], x[:len(y)], mode=kn["MODE"], **kf)
            D = 0                       # the core at 1x: no halfband delay
            sl = slice(FS // 5, len(y) - D)
            e = 10 * np.log10(np.mean((y[D:][sl] - tr[sl]) ** 2) / np.mean(tr[sl] ** 2))
            check(f"{kn}: the module vs the circuit at 8x, band-limited (aliasing): {e:.1f} dB "
                  f"(the 2x core: -40 .. -56)", e < -31)
    except ImportError:
        print("  [SKIP] the 8x ground truth needs scipy")

    # ---- silence ------------------------------------------------------------------
    for m in (0, 1, 2):
        L, R = render([0] * (FRAMES * 600), knobs(MODE=m, DRIV=127, TONE=127, LEVL=127, IN=127))
        tail = max(map(abs, L[FS // 10:] + R[FS // 10:]))
        check(f"MODE {m}: silence in -> exact zeros out after 100 ms: max {tail} LSB", tail == 0)
    # After a loud burst the SD-1's output HP (10.8 Hz) settles to exact zeros;
    # the RAT's C7 keeps a charge the diodes bleed off over seconds, a
    # subsonic drift the 1.6 Hz output HP passes at a low level (README).
    burst = q23(0.9 * np.sign(np.sin(2 * np.pi * 55 * np.arange(FS // 2) / FS)))
    for m, after, limit in ((0, FS // 2, 0), (1, 2 * FS, 256), (2, 2 * FS, 256)):
        s = burst + [0] * (FRAMES * ((after + FS // 2) // FRAMES))
        L, R = render(s, knobs(MODE=m, DRIV=127, TONE=127, LEVL=127, IN=127))
        tail = max(abs(v) for v in L[len(burst) + after:] + R[len(burst) + after:])
        check(f"MODE {m}: a loud burst, then silence: max {tail} LSB "
              f"({20 * np.log10(max(tail, 1) / 2 ** 23):.0f} dBFS) after {after / FS:.1f} s "
              f"(limit {limit} LSB)", tail <= limit)

    # ---- the fade -------------------------------------------------------------------
    nn = FRAMES * 1200
    tone = q23(0.4 * np.sin(2 * np.pi * 110 * np.arange(nn) / FS))
    nb = nn // FRAMES
    seq = [knobs(MODE=0)] * 300 + [knobs(MODE=1)] * 300 + [knobs(MODE=2)] * 300 + [knobs(MODE=0)] * (nb - 900)
    L, _ = render(tone, seq)
    y = np.asarray(L, float)
    dy = np.abs(np.diff(y))
    steady = max(dy[200 * FRAMES:290 * FRAMES].max(), dy[500 * FRAMES:590 * FRAMES].max(),
                 dy[800 * FRAMES:890 * FRAMES].max())
    sw = dy[295 * FRAMES:].max()
    check(f"MODE changes on a 110 Hz tone: the largest step {sw / 2 ** 23:.4f} FS, "
          f"the pedals' own {steady / 2 ** 23:.4f} FS", sw <= steady * 1.05)

    # ---- every knob -------------------------------------------------------------------
    ok = True
    for m in (0, 1, 2):
        for name in KNOBS[:5]:
            for v in (0, 1, 63, 64, 126, 127):
                try:
                    render(noise[:FRAMES * 40], knobs(MODE=m, **{name: v}))
                except SystemExit:
                    ok = False
    check("every knob at 0/1/63/64/126/127 renders, in every MODE", ok)
    return FAILS


# ---- the dsp_host render (make check) --------------------------------------------------
def dsp_host_render():
    from remix import registry
    import send_probe
    mod = registry.by_name("distorx")
    send = registry.by_name("send")
    K = mod.knob_map()
    mem = f"out/dsp/_audition_{mod.name}_A.mem"
    host = "vendor/dsp56300/build/source/dsp_host/dsp_host"
    tmp = pathlib.Path("out/_dtxgate")
    tmp.mkdir(parents=True, exist_ok=True)
    pathlib.Path(mem).unlink(missing_ok=True)
    subprocess.run([sys.executable, "tools/remix/audition.py", mod.name, "out/dry/drums_110.wav"],
                   capture_output=True)
    if not pathlib.Path(mem).exists():
        sys.exit(f"no {mem} -- build it first:\n  python3 tools/remix/audition.py {mod.name} out/dry/drums_110.wav")
    init, proc = send_probe.entry_points(mem, mod.menu.fx2_id)
    if (init, proc) == send_probe.entry_points(mem, send.menu.fx2_id):
        sys.exit(f"fx id 0x{mod.menu.fx2_id:02x} resolves to SEND's entry points -- distorx is NOT in this dump")
    print(f"entries from dispatch tables: init=P:0x{init:04x} proc=P:0x{proc:04x}")

    def render(samples, kn, split=0, pfrac=0):
        n = len(samples) - len(samples) % FRAMES
        src, out = tmp / "in.raw", tmp / "out.raw"
        src.write_bytes(b"".join(struct.pack("<i", m) for m in samples[:n]))
        per_block = isinstance(kn, list)
        first = kn[0] if per_block else kn
        pv = [0] * 12
        for name, v in first.items():
            pv[K[name]] = v
        cmd = [host, "-mem", mem, "-init", f"{init:x}", "-proc", f"{proc:x}",
               "-inst", "1", "-r7", "1", "-alloc", "0", "-inmask", "1",
               "-frames", str(FRAMES), "-blocks", str(n // FRAMES),
               "-in", str(src), "-out", str(out),
               "-params", ",".join(str(x) for x in pv)]
        if per_block:
            sched = []
            for b in range(1, n // FRAMES):
                if kn[b] != kn[b - 1]:
                    for name, v in kn[b].items():
                        if kn[b - 1].get(name) != v:
                            sched.append(f"{b}:0:{K[name]}={v}")
            if sched:
                cmd += ["-sched", ",".join(sched)]
        if split:
            cmd += ["-split", str(split)]
        if pfrac:
            cmd += ["-pword", ",".join(f"0:{K[nm]:x}={((first[nm] & 0x7f) << 16) | (pfrac << 8):x}"
                                       for nm in KNOBS)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"dsp_host failed for {first}:\n{r.stdout}\n{r.stderr}")
        w = struct.unpack(f"<{len(out.read_bytes()) // 4}i", out.read_bytes())
        return list(w[0::2])[:n], list(w[1::2])[:n]
    return render


def loop_ends():
    """No DO loop of DISTORX ends (its LA) on a change of flow. The chip decides
    the loop-back when it reaches LA; a bsr there rendered one junk block every
    few seconds on the MK1 (14 Oct 2026, image ACIDDTX1: a 16-sample block of
    noise passing through the state, clusters at one phase of the pattern; the
    harness, which runs the call and the loop-back in order, never shows it).
    Every module proven on a unit ends its loops on a plain instruction."""
    import re
    lines = [l.split(";")[0].rstrip()
             for l in pathlib.Path("modules/distorx/distorx.asm").read_text().splitlines()]
    at = {m.group(1): i for i, l in enumerate(lines) if (m := re.match(r"^(\w+):", l))}
    bad, n = [], 0
    for i, l in enumerate(lines):
        m = re.match(r"^\s+do\s+[^,]+,>?(\w+)", l)
        if not m:
            continue
        n += 1
        body = [x.strip() for x in lines[i + 1:at[m.group(1)]] if x.strip() and not re.match(r"^\w+:", x)]
        last = body[-1].split()[0] if body else ""
        if re.match(r"^(bsr|jsr|bra|jmp|rts|rti|do|dor|rep|enddo|brk..|b(cc|cs|ec|eq|es|ge|gt|lc|le|ls|lt|mi|ne|nn|nr|pl|se)|j(cc|cs|ec|eq|es|ge|gt|lc|le|ls|lt|mi|ne|nn|nr|pl|se)|movem|movep)$", last):
            bad.append(f"{m.group(1)}: {body[-1]}")
        elif last == "move" and "p:" in body[-1]:
            bad.append(f"{m.group(1)}: {body[-1]} (P-space at LA)")
    check(f"no DO loop ends on a change of flow or a P-space move ({n} loops)", not bad, "; ".join(bad))


def main():
    r = subprocess.run([sys.executable, "modules/distorx/generate_asm.py", "--check"],
                       capture_output=True, text=True)
    check("distorx.asm is generated from the template and the manifest", r.returncode == 0,
          (r.stdout + r.stderr).strip())
    loop_ends()
    src = pathlib.Path("tools/harness/dsp_host/dsp_host.cpp")
    dirty = src.exists() and "-pword" in src.read_text()
    fails = run_gates(dsp_host_render(), dirty_words=dirty)
    if fails:
        sys.exit(f"verify_distorx: {len(fails)} gate(s) failed")
    print("verify_distorx: all gates pass")


if __name__ == "__main__":
    main()
