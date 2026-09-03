#!/usr/bin/env python3
"""Local verification of the MIDI note path (24 Aug 2026; v5 3 Sep 2026):
note -> BusDelay GRAIN pitch (r6+$9, latched). dsp_host has no ColdFire
cave, so the word is forced with the DNOTE= build override and the result
compared with the PTCH knob, which drives the same 2^x law.

  EXACT (bit-identical):
    no note (DNOTE=0)  == PTCH 64         (nothing changes)
    note 84 (unison)   == PTCH 64         (f = 0 on both paths)
  WITHIN 40 CENTS OF NOMINAL (the grain-rate comb), 15 of the knob path (spectral peak of the wet):
    note 96 ~ +12 (PTCH 96), note 91 ~ +7, note 72 ~ -12 (PTCH 32)

Slow (8 DEV builds + renders, ~1 min); not part of make check.
"""
import array, cmath, math, os, pathlib, subprocess, sys, wave

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out" / "midiverify"; OUT.mkdir(parents=True, exist_ok=True)


def render(name, env, *probe):
    e = dict(os.environ, DEV="1", XBUS="1")
    for k in ("DMODE", "DINT", "DFRZ", "DNOTE", "NOSHIM"):
        e.pop(k, None)
    e.update(env)
    subprocess.run([sys.executable, "tools/build_bus.py"], cwd=ROOT, env=e,
                   check=True, capture_output=True)
    wav = OUT / f"{name}.wav"
    subprocess.run([sys.executable, "tools/send_probe.py", "--mem",
                    "out/dsp/mem_dev_A.mem", "--layout", "DS", "--pick", "D",
                    "--dur", "1.0", *probe, "--wav", str(wav)],
                   cwd=ROOT, check=True, capture_output=True)
    return wav


def read(path):
    w = wave.open(str(path)); a = array.array('h' if w.getsampwidth() == 2 else 'i')
    a.frombytes(w.readframes(w.getnframes()))
    return a, w.getframerate(), w.getnchannels()


def fft(x):
    n = len(x)
    if n == 1: return x
    e, o = fft(x[0::2]), fft(x[1::2])
    t = [cmath.exp(-2j * math.pi * k / n) * o[k] for k in range(n // 2)]
    return [e[k] + t[k] for k in range(n // 2)] + [e[k] - t[k] for k in range(n // 2)]


def peak_hz(path, lo=150, hi=1400):
    a, sr, ch = read(path); x = a[::ch]; N = 16384
    seg = x[len(x) // 2:len(x) // 2 + N]
    X = fft([v * (0.5 - 0.5 * math.cos(2 * math.pi * i / N)) for i, v in enumerate(seg)])
    mag = [abs(c) for c in X[:N // 2]]
    k = max(range(int(lo * N / sr), int(hi * N / sr)), key=lambda i: mag[i])
    a0, b0, c0 = mag[k - 1], mag[k], mag[k + 1]
    d = a0 - 2 * b0 + c0
    return (k + (0.5 * (a0 - c0) / d if d else 0)) * sr / N


fails = 0
def check(label, ok, detail=""):
    global fails
    print(f"  [{'ok' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")
    fails += 0 if ok else 1


def same(a, b):
    return read(a)[0] == read(b)[0]


# v5 (3 Sep 2026): the note drives GRAIN's continuous pitch (MODE 1), the
# same law the PTCH knob uses -- so the knob path is the reference, and two
# of the cases are BIT-IDENTICAL rather than spectral: no note ever == the
# knob, and note 84 (the OT's unison) == PTCH 64, because both feed the same
# 2^x arithmetic with f = 0.
G = ("--set", "MODE=1", "--set", "MRAT=127", "--set", "MDEP=0", "--set", "DRV=0",
     "--set", "FDBK=0", "--set", "PING=0", "--set", "TIME=127", "--set", "SIZE=1")
knob64 = render("knob64", {}, *G, "--set", "PTCH=64")
check("DNOTE=0 == the PTCH knob (no note ever: unchanged)",
      same(knob64, render("note0", {"DNOTE": "0"}, *G, "--set", "PTCH=64")))
check("note 84 (unison) == PTCH 64, bit-identical (one 2^x law, f = 0)",
      same(knob64, render("note84", {"DNOTE": "84"}, *G, "--set", "PTCH=64")))
clean = render("clean", {}, "--set", "MODE=0", "--set", "MDEP=0", "--set", "FDBK=0",
               "--set", "PING=0", "--set", "TIME=127")
uni = peak_hz(clean, 80, 3000)
for note, want, rate in ((96, 1200, 96), (91, 700, None), (72, -1200, 32)):
    got = 1200 * math.log2(peak_hz(render(f"note{note}", {"DNOTE": str(note)}, *G,
                                          "--set", "PTCH=64"), 80, 3000) / uni)
    detail = f"got {got:+.1f}"
    # 40 cents of NOMINAL: the peak is read off a comb at the grain rate
    # (10.8 Hz at 93 ms), so a line's worth of error is the finder's, and
    # -12 at 219 Hz reads 223 (+33 cents) on both paths. The 15-cent
    # agreement with the knob path is the gate that is about the engine.
    ok = abs(got - want) < 40
    if rate is not None:
        refc = 1200 * math.log2(peak_hz(render(f"rate{rate}", {}, *G, "--set",
                                               f"PTCH={rate}"), 80, 3000) / uni)
        ok = ok and abs(got - refc) < 15
        detail += f", PTCH={rate} knob path {refc:+.1f}"
    check(f"note {note} -> {want:+5d} cents", ok, detail)
print(f"{fails} check(s) failed" if fails else "all MIDI checks passed")
sys.exit(1 if fails else 0)
