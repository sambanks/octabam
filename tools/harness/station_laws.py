#!/usr/bin/env python3
"""Read a station's control laws off noise: the transfer function per knob value.

    python3 tools/harness/station_laws.py --station SPECTRUM --knob FREQ=0,16,32,48,64,80,96,112,127 \\
        --fixed MODE=0 --fixed RES=0 --out out/laws/spec_lp

Renders white noise (2 s, -12 dBFS) through the station on T1's FX1 (SEND on
FX2, AUX 0) once per value, divides the output spectrum by the input's
(Welch-averaged, 4,096-point) and reports, per value: the -3 dB corner
(where |H| first drops 3 dB below its level at 100 Hz, or rises for a
high-pass), the peak of |H| and its frequency and -3 dB bandwidth (a
resonance readout), and the level at 100 Hz / 1 kHz / 10 kHz. Lets a taper
be read as a table -- "FREQ 64 = 1.2 kHz" -- which is what a first-guess law
needs before anyone listens. Requires numpy (.venv/bin/python3).
"""
import argparse, json, math, os, pathlib, shutil, subprocess, sys, wave
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
SR = 44100
N = 4096


def write_noise(path, seconds=2.0, amp=0.25, seed=7):
    rng = np.random.default_rng(seed)
    x = (rng.uniform(-1, 1, int(SR * seconds)) * amp * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(x.tobytes())


def read_mono(path):
    with wave.open(str(path), "rb") as w:
        nch, sw, n = w.getnchannels(), w.getsampwidth(), w.getnframes(); raw = w.readframes(n)
    a = np.frombuffer(raw, dtype=np.uint8).reshape(n, nch, sw)
    v = a[:, :, 0].astype(np.int32) | (a[:, :, 1].astype(np.int32) << 8) | (a[:, :, 2].astype(np.int32) << 16) if sw == 3 else None
    if sw == 2:
        v = np.frombuffer(raw, dtype="<i2").reshape(n, nch).astype(np.int32) << 8
    v = np.where(v >= 1 << 23, v - (1 << 24), v)
    return v.mean(axis=1) / 8388608.0


def welch(x):
    seg = x[:len(x) // N * N].reshape(-1, N) * np.hanning(N)
    return (np.abs(np.fft.rfft(seg, axis=1)) ** 2).mean(axis=0)


AMP = (64 / 127) ** 2          # the mixer model's AMP VOL 64 on the stem, divided out of every readout


def write_wav16(path, x):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def write_sine(path, hz, amp, seconds=1.0):
    t = np.arange(int(SR * seconds)) / SR
    write_wav16(path, amp * np.sin(2 * np.pi * hz * t))


def write_burst(path, hz, loud, quiet, seconds=0.5):
    """quiet - LOUD - quiet: a step up then a step down, for attack / release and ratio."""
    t = np.arange(int(SR * seconds)) / SR
    tone = np.sin(2 * np.pi * hz * t)
    write_wav16(path, np.concatenate([quiet * tone, loud * tone, quiet * tone]))


def render(a, stem, knob, v):
    d = pathlib.Path(a.out) / f"_r_{v:03d}"
    cmd = [sys.executable, str(ROOT / "tools/harness/rig_render.py"), "--image", a.image, "--remix", a.remix,
           "--tracks", f"T1={a.station}+SEND", "--stem", f"T1={stem}", "--tail", "0", "--frames", "16",
           "--set", f"T1:FX1:{knob}={v}", "--out", str(d)]
    for fx in a.fixed:
        cmd += ["--set", f"T1:FX1:{fx}"]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"rig_render failed for {knob}={v}:\n{r.stdout[-1500:]}{r.stderr[-1500:]}")
    y = read_mono(d / "T1.wav"); yl = read_mono(d / "T1.wav") if False else None
    shutil.rmtree(d, ignore_errors=True)
    return y


def sine_probe(a, knob, vals):
    """A 440 Hz sine at --amp: output level, THD (harmonics 2..10), the even/odd
    balance (TUBE's asymmetry), DC. Levels are relative to the INPUT after
    the AMP stage, so 0 dB = unity through the station."""
    out = pathlib.Path(a.out)
    stem = out / "sine.wav"; write_sine(stem, a.hz, a.amp)
    x = read_mono(stem) * AMP
    rows = []
    for v in vals:
        y = render(a, stem, knob, v)[:len(x)]
        seg = slice(SR // 4, len(x) - 256)
        Y = np.abs(np.fft.rfft(y[seg] * np.hanning(len(y[seg]))))
        f = np.fft.rfftfreq(len(y[seg]), 1 / SR)
        binw = lambda hz: int(round(hz * len(y[seg]) / SR))
        mag = lambda hz: float(Y[binw(hz) - 2:binw(hz) + 3].max())
        fund = mag(a.hz)
        harm = [mag(a.hz * k) for k in range(2, 11)]
        even = math.sqrt(sum(h * h for h in harm[0::2])); odd = math.sqrt(sum(h * h for h in harm[1::2]))
        thd = math.sqrt(sum(h * h for h in harm)) / fund if fund else 0
        gain = 20 * math.log10(np.sqrt(np.mean(y[seg] ** 2)) / np.sqrt(np.mean(x[seg] ** 2)))
        dc = float(np.mean(y[seg]))
        rows.append(dict(value=v, gain_db=gain, thd_pct=100 * thd, even_db=20 * math.log10(even / fund) if fund and even else -200,
                         odd_db=20 * math.log10(odd / fund) if fund and odd else -200, dc=dc, h2_db=20 * math.log10(harm[0] / fund) if fund and harm[0] else -200,
                         h3_db=20 * math.log10(harm[1] / fund) if fund and harm[1] else -200))
        print(f"{knob}={v:3d}: gain {gain:+6.2f} dB  THD {100 * thd:6.2f} %  H2 {rows[-1]['h2_db']:+6.1f}  H3 {rows[-1]['h3_db']:+6.1f}  "
              f"even {rows[-1]['even_db']:+6.1f}  odd {rows[-1]['odd_db']:+6.1f} dB  DC {dc:+.4f}")
    return rows


def burst_probe(a, knob, vals):
    """quiet-LOUD-quiet at --hz: gain at each level (the ratio), and the time
    for the gain to travel 63 % of the way after each step (attack, release)."""
    out = pathlib.Path(a.out)
    stem = out / "burst.wav"; write_burst(stem, a.hz, a.amp, a.amp * 10 ** (-20 / 20))
    x = read_mono(stem) * AMP
    n3 = len(x) // 3
    rows = []
    win = SR // 100
    env = lambda z: np.sqrt(np.convolve(z * z, np.ones(win) / win, mode="same"))
    ex = env(x)
    for v in vals:
        y = render(a, stem, knob, v)[:len(x)]
        ey = env(y)
        g = ey / np.maximum(ex, 1e-9)                       # instantaneous gain
        gq = float(np.median(g[n3 // 2:n3 - win]))          # quiet, settled
        gl = float(np.median(g[n3 + n3 // 2:2 * n3 - win]))  # loud, settled
        g2 = float(np.median(g[2 * n3 + n3 // 2:3 * n3 - win]))
        def t63(seg, g0, g1):
            tgt = g0 + 0.63 * (g1 - g0)
            idx = np.where((seg - tgt) * np.sign(g1 - g0) >= 0)[0]
            return float(idx[0]) / SR * 1000 if len(idx) else None
        att = t63(g[n3 + win:2 * n3], gq, gl)
        rel = t63(g[2 * n3 + win:3 * n3], gl, g2)
        ratio = 20 / (20 + 20 * math.log10(gl / gq)) if gl > 0 and gq > 0 and (20 + 20 * math.log10(gl / gq)) > 0 else None
        rows.append(dict(value=v, gain_quiet_db=20 * math.log10(gq), gain_loud_db=20 * math.log10(gl),
                         ratio=ratio, attack_ms=att, release_ms=rel))
        print(f"{knob}={v:3d}: quiet {20 * math.log10(gq):+6.2f} dB  loud {20 * math.log10(gl):+6.2f} dB  "
              f"ratio {ratio if ratio is None else round(ratio, 2)!s:>5}:1  attack {att if att is None else round(att, 1)!s:>6} ms  release {rel if rel is None else round(rel, 1)!s:>6} ms")
    return rows


def laws(a):
    knob, vals = a.knob.split("="); vals = [int(v) for v in vals.split(",")]
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    if a.probe == "sine":
        rows = sine_probe(a, knob, vals)
        (out / "laws.json").write_text(json.dumps(dict(station=a.station, knob=knob, fixed=a.fixed, probe="sine", rows=rows), indent=1)); return
    if a.probe == "burst":
        rows = burst_probe(a, knob, vals)
        (out / "laws.json").write_text(json.dumps(dict(station=a.station, knob=knob, fixed=a.fixed, probe="burst", rows=rows), indent=1)); return
    noise = out / "noise.wav"; write_noise(noise)
    nin = read_mono(noise); pin = welch(nin); f = np.fft.rfftfreq(N, 1 / SR)
    rows = []
    for v in vals:
        y = render(a, noise, knob, v)[:len(nin)]
        H = np.sqrt(welch(y) / np.maximum(pin, 1e-30))
        # the mixer model puts the stem through AMP VOL (64/127)^2: divide it out
        H = H / AMP
        Hdb = 20 * np.log10(np.maximum(H, 1e-9))
        at = lambda hz: float(Hdb[int(round(hz * N / SR))])
        ref = at(100)
        # -3 dB corner: first bin above 100 Hz where H drops 3 dB under the 100 Hz level (LP) or the first
        # bin from the bottom where it is within 3 dB of the 10 kHz level (HP)
        i100 = int(round(100 * N / SR)); i10k = int(round(10000 * N / SR))
        lp = next((float(f[i]) for i in range(i100, len(f)) if Hdb[i] < ref - 3), None)
        hp_ref = at(10000)
        hp = next((float(f[i]) for i in range(1, i10k) if Hdb[i] > hp_ref - 3), None)
        ip = int(np.argmax(Hdb[1:]) + 1)
        half = Hdb[ip] - 3
        lo = ip
        while lo > 1 and Hdb[lo] > half:
            lo -= 1
        hi = ip
        while hi < len(f) - 1 and Hdb[hi] > half:
            hi += 1
        i20 = int(round(20 * N / SR)); i15k = int(round(15000 * N / SR))
        imin = int(np.argmin(Hdb[i20:i15k]) + i20)
        rows.append(dict(value=v, corner_lp_hz=lp, corner_hp_hz=hp, peak_db=float(Hdb[ip]), peak_hz=float(f[ip]),
                         peak_bw_hz=float(f[hi] - f[lo]), h100=ref, h1k=at(1000), h3k=at(3000), h5k=at(5000),
                         h10k=at(10000), h15k=at(15000), min_db=float(Hdb[imin]), min_hz=float(f[imin])))
        fmt = lambda x: f"{'  none':>6}" if x is None else f"{round(x):6d}"
        print(f"{knob}={v:3d}: LP corner {fmt(lp)}  HP corner {fmt(hp)}  "
              f"peak {rows[-1]['peak_db']:+5.1f} dB @ {rows[-1]['peak_hz']:6.0f} Hz (bw {rows[-1]['peak_bw_hz']:5.0f})  "
              f"|H| 100 {ref:+5.1f}  1k {rows[-1]['h1k']:+5.1f}  3k {rows[-1]['h3k']:+5.1f}  5k {rows[-1]['h5k']:+5.1f}  "
              f"10k {rows[-1]['h10k']:+5.1f}  15k {rows[-1]['h15k']:+5.1f} dB  min {rows[-1]['min_db']:+5.1f} @ {rows[-1]['min_hz']:5.0f}")
    (out / "laws.json").write_text(json.dumps(dict(station=a.station, knob=knob, fixed=a.fixed, rows=rows), indent=1))
    print(f"-> {out}/laws.json")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--station", required=True); ap.add_argument("--knob", required=True)
    ap.add_argument("--fixed", action="append", default=[])
    ap.add_argument("--image", default="out/mainos_bus.bin"); ap.add_argument("--remix", default=os.environ.get("REMIX", "bamsep26"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--probe", choices=("noise", "sine", "burst"), default="noise")
    ap.add_argument("--hz", type=float, default=440.0); ap.add_argument("--amp", type=float, default=0.5, help="probe amplitude before the AMP stage (0.5 = -6 dBFS)")
    return laws(ap.parse_args())


if __name__ == "__main__":
    sys.exit(main() or 0)
