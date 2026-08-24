#!/usr/bin/env python3
"""Local verification of the MIDI branch's two DSP paths (24 Aug 2026):
note -> BongDelay PITCH interval (r6+$9) and crossfader -> FREEZE (r6+$8).
dsp_host has no ColdFire cave, so the words are forced with the DNOTE= /
DFADER= build overrides and the result compared with the knob select that
should produce the same thing.

  EXACT (bit-identical):
    no note (DNOTE=0)          == the PTCH select      (nothing changes)
    fader 128 (fully A) clean  == clean                (never engages)
    fader 30 from cold         == clean                (hysteresis dead band)
    fader 1 (fully B)          == FRZE select 1
  WITHIN 15 CENTS OF THE SELECT PATH, 30 of nominal (spectral peak of the wet, the heads decorrelate so a
  waveform diff is meaningless):
    note 96 ~ +12, note 91 ~ +7, note 72 ~ -12, note 84 ~ unison (CLEAN's pitch)

Slow (13 DEV builds + renders, ~1 min); not part of make check.
"""
import array, cmath, math, os, pathlib, subprocess, sys, wave

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out" / "midiverify"; OUT.mkdir(parents=True, exist_ok=True)


def render(name, env, *probe):
    e = dict(os.environ, DEV="1", XBUS="1")
    for k in ("DMODE", "DINT", "DFRZ", "DNOTE", "DFADER", "NOSHIM"):
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


P = ("--dmode", "1", "--dptch", "0")
sel12 = render("sel_p12", {}, *P)
check("DNOTE=0 == PTCH select (no note ever: unchanged)", same(sel12, render("note0", {"DNOTE": "0"}, *P)))
clean = render("clean", {}, "--dmode", "0")
check("DFADER=128 (fully A) == clean", same(clean, render("fader128", {"DFADER": "128"}, "--dmode", "0")))
check("DFADER=30 from cold == clean (dead band)", same(clean, render("fader30", {"DFADER": "30"}, "--dmode", "0")))
frz = render("frz_sel", {}, "--dmode", "0", "--dfrz", "1")
check("DFADER=1 (fully B) == FRZE select", same(frz, render("fader1", {"DFADER": "1"}, "--dmode", "0")))
check("FRZE select differs from clean (the control)", not same(frz, clean))

uni = peak_hz(clean)
for note, want, ref in ((96, 1200, sel12), (91, 700, render("sel_p7", {}, "--dmode", "1", "--dptch", "1")),
                        (72, -1200, render("sel_m12", {}, "--dmode", "1", "--dptch", "2")), (84, 0, clean)):
    got = 1200 * math.log2(peak_hz(render(f"note{note}", {"DNOTE": str(note)}, *P)) / uni)
    refc = 1200 * math.log2(peak_hz(ref) / uni)
    check(f"note {note} -> {want:+5d} cents", abs(got - want) < 30 and abs(got - refc) < 15,
          f"got {got:+.1f}, select path {refc:+.1f}")
print(f"{fails} check(s) failed" if fails else "all MIDI checks passed")
sys.exit(1 if fails else 0)
