#!/usr/bin/env python3
"""A/B kits for voicing a station: render a knob sweep on one track, level-match,
measure, and play pairs the way the listening protocol wants.

    python3 tools/harness/abkit.py sweep --station SPECTRUM --stem out/test_audio/loop.wav \\
        --knob FREQ=20,40,60,80,100,127 --fixed MODE=0 --fixed RES=60 --out out/ab/spec_freq
    python3 tools/harness/abkit.py measure out/ab/spec_freq          # active RMS, centroid, peak Hz per file
    python3 tools/harness/abkit.py play out/ab/spec_freq/FREQ_040.wav out/ab/spec_freq/FREQ_100.wav
                                                                     # A/B/A/B, one afplay at a time

SWEEP renders the station on T1's FX1 with SEND on FX2 (AUX 0: the bus is
present but idle) through rig_render -- the real image, the mixer model on,
whole 16-sample blocks -- once per value, and keeps T1.wav as
<KNOB>_<value>.wav. A second station or an engine can be put on other tracks
with --tracks (rig_render's syntax) when the bus matters.

LEVEL MATCHING is the protocol's (docs: the voicing rules): every file is
scaled to the same ACTIVE RMS (-20 dBFS over 100 ms windows louder than
-60 dBFS, so tails and silences do not vote), then the whole kit is trimmed
by ONE gain so its loudest peak sits at -1 dBFS -- a joint trim, so relative
levels inside the kit survive. --no-match keeps the rendered levels (for
judging a level law rather than a character).

PLAY is one file per afplay, A B A B (--repeats), and prints what to listen
for if the kit's listen.txt names it. MEASURE prints per file: active RMS
before matching, the applied gain, spectral centroid, the strongest peak,
crest factor -- the numbers a taper or a resonance law can be read from.
"""
import argparse, json, math, os, pathlib, shutil, subprocess, sys, wave
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401

ROOT = pathlib.Path(__file__).resolve().parents[2]
SR = 44100
TARGET_DB = -20.0
PEAK_DB = -1.0


def read(path):
    with wave.open(str(path), "rb") as w:
        nch, sw, n = w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(n)
    full = 1 << (8 * sw - 1)
    ch = [[int.from_bytes(raw[(i * nch + c) * sw:(i * nch + c + 1) * sw], "little", signed=True) / full
           for i in range(n)] for c in range(nch)]
    return ch


def write(path, ch):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(len(ch)); w.setsampwidth(3); w.setframerate(SR)
        n = len(ch[0])
        w.writeframes(b"".join(int(max(-8388608, min(8388607, round(ch[c][i] * 8388607)))).to_bytes(3, "little", signed=True)
                               for i in range(n) for c in range(len(ch))))


def db(x):
    return 20 * math.log10(x) if x > 0 else -200.0


def active_rms(ch, win=4410, floor_db=-60.0):
    n = len(ch[0]); vals = []
    for s in range(0, n - win, win):
        e = sum(sum(c[i] * c[i] for c in ch) for i in range(s, s + win)) / (win * len(ch))
        if e > 0 and db(math.sqrt(e)) > floor_db:
            vals.append(e)
    return math.sqrt(sum(vals) / len(vals)) if vals else 0.0


def peak(ch):
    return max(abs(v) for c in ch for v in c)


def spectrum(x, n=8192):
    """A crude magnitude spectrum (numpy if present, else a slow DFT on a decimated window)."""
    try:
        import numpy as np
        seg = np.array(x[:len(x) // n * n]).reshape(-1, n)
        win = np.hanning(n)
        mag = np.abs(np.fft.rfft(seg * win, axis=1)).mean(axis=0)
        freqs = np.fft.rfftfreq(n, 1 / SR)
        return freqs, mag
    except ImportError:
        return None, None


def measure_file(path):
    ch = read(path)
    mono = [sum(c[i] for c in ch) / len(ch) for i in range(len(ch[0]))]
    out = dict(file=path.name, active_rms_db=db(active_rms(ch)), peak_db=db(peak(ch)))
    out["crest_db"] = out["peak_db"] - out["active_rms_db"]
    f, m = spectrum(mono)
    if f is not None:
        import numpy as np
        p = m * m
        out["centroid_hz"] = float((f * p).sum() / p.sum()) if p.sum() > 0 else 0.0
        i = int(np.argmax(m[1:]) + 1)
        out["peak_hz"] = float(f[i])
        # -3 dB bandwidth of the strongest peak, as a resonance readout
        half = m[i] / math.sqrt(2)
        lo = i
        while lo > 1 and m[lo] > half:
            lo -= 1
        hi = i
        while hi < len(m) - 1 and m[hi] > half:
            hi += 1
        out["peak_bw_hz"] = float(f[hi] - f[lo])
    return out


def sweep(a):
    knob, vals = a.knob.split("=")
    vals = [int(v) for v in vals.split(",")]
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    tracks = a.tracks or f"T1={a.station}+SEND"
    sets = []
    for fx in a.fixed:
        sets += ["--set", f"T1:FX1:{fx}"]
    rendered = []
    for v in vals:
        d = out / f"_r_{knob}_{v:03d}"
        cmd = [sys.executable, str(ROOT / "tools/harness/rig_render.py"), "--image", a.image, "--remix", a.remix,
               "--tracks", tracks, "--stem", f"T1={a.stem}", "--tail", str(a.tail), "--frames", "16",
               "--set", f"T1:FX1:{knob}={v}", "--out", str(d)] + sets + (["--seconds", str(a.seconds)] if a.seconds else [])
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"rig_render failed for {knob}={v}:\n{r.stdout[-1500:]}{r.stderr[-1500:]}")
        src = d / "T1.wav"
        dst = out / f"{knob}_{v:03d}.wav"
        shutil.move(str(src), str(dst))
        shutil.rmtree(d, ignore_errors=True)
        rendered.append(dst)
        print(f"  {dst.name}")
    if not a.no_match:
        match(rendered, out)
    (out / "kit.json").write_text(json.dumps(dict(station=a.station, stem=a.stem, knob=knob, values=vals,
                                                   fixed=a.fixed, tracks=tracks, matched=not a.no_match), indent=1))
    print(f"-> {out} ({len(rendered)} files{', level-matched' if not a.no_match else ''})")


def match(files, out):
    """Every file to TARGET_DB active RMS, then one joint trim to PEAK_DB."""
    gains = {}
    data = {}
    for p in files:
        ch = read(p); r = active_rms(ch)
        g = (10 ** (TARGET_DB / 20)) / r if r > 0 else 1.0
        gains[p.name] = g; data[p] = ch
    worst = max(peak(data[p]) * gains[p.name] for p in files)
    trim = (10 ** (PEAK_DB / 20)) / worst if worst > 0 else 1.0
    for p in files:
        g = gains[p.name] * trim
        write(p, [[v * g for v in c] for c in data[p]])
    (out / "match.json").write_text(json.dumps({k: dict(gain_db=db(g * trim)) for k, g in gains.items()}, indent=1))
    print(f"  level-matched to {TARGET_DB} dBFS active RMS, joint trim {db(trim):+.1f} dB")


def measure(a):
    d = pathlib.Path(a.dir)
    files = sorted(d.glob("*.wav"))
    rows = [measure_file(p) for p in files]
    keys = ["active_rms_db", "peak_db", "crest_db", "centroid_hz", "peak_hz", "peak_bw_hz"]
    print(f"{'file':22} " + " ".join(f"{k:>13}" for k in keys if k in rows[0]))
    for r in rows:
        print(f"{r['file']:22} " + " ".join(f"{r[k]:13.1f}" for k in keys if k in r))
    (d / "measure.json").write_text(json.dumps(rows, indent=1))


def play(a):
    order = []
    for _ in range(a.repeats):
        order += [a.a, a.b]
    listen = pathlib.Path(a.a).parent / "listen.txt"
    if listen.is_file():
        print(listen.read_text().strip())
    for i, f in enumerate(order):
        print(f"[{'AB'[i % 2]}] {pathlib.Path(f).name}")
        subprocess.run(["afplay", f])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sweep")
    s.add_argument("--station", required=True, help="module KEY, on T1's FX1")
    s.add_argument("--stem", required=True)
    s.add_argument("--knob", required=True, help="NAME=v1,v2,...")
    s.add_argument("--fixed", action="append", default=[], help="NAME=v held for every render")
    s.add_argument("--tracks", help="override the layout (rig_render syntax); T1 must carry the station on FX1")
    s.add_argument("--image", default="out/mainos_bus.bin")
    s.add_argument("--remix", default=os.environ.get("REMIX", "bamsep26"))
    s.add_argument("--seconds", type=float)
    s.add_argument("--tail", type=float, default=1.0)
    s.add_argument("--no-match", action="store_true")
    s.add_argument("--out", required=True)
    m = sub.add_parser("measure"); m.add_argument("dir")
    p = sub.add_parser("play"); p.add_argument("a"); p.add_argument("b"); p.add_argument("--repeats", type=int, default=2)
    a = ap.parse_args()
    return {"sweep": sweep, "measure": measure, "play": play}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main() or 0)
