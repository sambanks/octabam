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


def laws(a):
    knob, vals = a.knob.split("="); vals = [int(v) for v in vals.split(",")]
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    noise = out / "noise.wav"; write_noise(noise)
    nin = read_mono(noise); pin = welch(nin); f = np.fft.rfftfreq(N, 1 / SR)
    rows = []
    for v in vals:
        d = out / f"_r_{v:03d}"
        cmd = [sys.executable, str(ROOT / "tools/harness/rig_render.py"), "--image", a.image, "--remix", a.remix,
               "--tracks", f"T1={a.station}+SEND", "--stem", f"T1={noise}", "--tail", "0", "--frames", "16",
               "--set", f"T1:FX1:{knob}={v}", "--out", str(d)]
        for fx in a.fixed:
            cmd += ["--set", f"T1:FX1:{fx}"]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"rig_render failed for {knob}={v}:\n{r.stdout[-1500:]}{r.stderr[-1500:]}")
        y = read_mono(d / "T1.wav")[:len(nin)]
        shutil.rmtree(d, ignore_errors=True)
        H = np.sqrt(welch(y) / np.maximum(pin, 1e-30))
        # the mixer model puts the stem through AMP VOL (64/127)^2: divide it out
        H = H / (64 / 127) ** 2
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
    return laws(ap.parse_args())


if __name__ == "__main__":
    sys.exit(main() or 0)
