#!/usr/bin/env python3
"""DRUMMER on the host: render the engine with the user's own sliced sample, to listen before any firmware.

    .venv/bin/python3 modules/drummer/render.py --sample DIR/NAME.wav [--kit kit.json] [--out out/drummer/renders]

NAME.ot (the unit's FILE > SAVE SAMPLE SETTINGS) gives the slices. The kit maps slice numbers to a
zone and a role, as DRUMMER's KIT window will: {"0": ["KICK", "ACCENT"], "1": ["COMBO", "NORMAL",
["KICK", "HATC"]], ...}; slices not named are out of the kit. Without --kit, kit.json beside the
renders is used, or written from the default below (the user's 93 BPM loop, 16 grid slices).

The render plays the track as the unit does with DRUMMER v1: one voice, each hit cuts the one before
(a 2 ms fade), the slice from its start to its end, the hit's micro-timing (1/24 step), its level,
and its retrigs. The level law is a placeholder until the unit's AMP VOL curve is measured:
gain = (vel / 100) ** 1.5. Renders go to out/ (never committed): the sample is the user's.

Per style (BREAKBEAT 100 BPM, HIP-HOP 90, FUNK 100):
  1_groove   8 bars, HUMAN 0 (the style's table, DENS 64, CPLX 40)
  2_human    8 bars, HUMAN 100 (every aspect at its default)
  3_brk      16 bars, the crossfader: BRK 0 for 4 bars, up to 127 over 8 bars, back to 0 for 4
and a grid printout of each run (render.txt).
"""
import argparse
import json
import pathlib
import struct
import sys
import wave

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

DEFAULT_KIT = {
    "0": ["KICK", "ACCENT"], "8": ["KICK", "ACCENT"], "5": ["KICK", "NORMAL"], "13": ["KICK", "NORMAL"],
    "3": ["KICK", "SOFT"], "11": ["KICK", "SOFT"],
    "1": ["PERC", "ACCENT"], "9": ["PERC", "ACCENT"],
    "6": ["SNARE", "ACCENT"], "14": ["SNARE", "ACCENT"], "2": ["SNARE", "NORMAL"], "10": ["SNARE", "NORMAL"],
    "4": ["HATC", "NORMAL"], "12": ["HATC", "NORMAL"],
    "7": ["GHOST", "SOFT"], "15": ["PERC", "NORMAL"],
}
TEMPO = {}   # per style below; 100 BPM otherwise
SHORT = {0: "BD", 1: "SD", 2: "gh", 3: "hh", 4: "OH", 5: "RD", 6: "CR", 7: "TM", 8: "pc", 9: "CB"}


def read_sample(wav_path):
    d = wav_path.with_suffix(".ot").read_bytes()
    count, = struct.unpack(">I", d[0x33a:0x33e])
    slices = [struct.unpack(">II", d[0x3a + 12 * i:0x42 + 12 * i]) for i in range(count)]
    with wave.open(str(wav_path)) as w:
        sr, ch, sw = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if sw != 2:
        sys.exit("render: 16-bit WAV only for now")
    x = np.frombuffer(raw, dtype="<i2").reshape(-1, ch).astype(np.float32) / 32768
    if ch == 1:
        x = np.repeat(x, 2, axis=1)
    return x, sr, slices


def render(run, x, sr, slices, bpm):
    step_len = sr * 60 / bpm / 4
    total = int(step_len * 16 * (run[-1][0] + 1) + sr)
    out = np.zeros((total, 2), np.float32)
    starts = []                                      # (time, slice, gain)
    for bar, step, h in run:
        if not h[0]:
            continue
        t = (bar * 16 + step) * step_len + h[3] * step_len / 24
        g = (h[2] / 100) ** 1.5
        starts.append((t, h[1], g))
        for r in range(h[4]):
            starts.append((t + (r + 1) * h[5] * step_len / 24, h[1], g * 0.8 ** (r + 1)))
    starts.sort()
    fade = int(sr * 0.002)
    for i, (t, sl, g) in enumerate(starts):
        a = int(max(0, t))
        s0, s1 = slices[sl]
        seg = x[s0:s1] * g
        stop = int(starts[i + 1][0]) if i + 1 < len(starts) else a + len(seg)
        n = max(0, min(len(seg), stop - a, total - a))
        seg = seg[:n].copy()
        if n < len(x[s0:s1]) and n > fade:           # cut by the next hit
            seg[-fade:] *= np.linspace(1, 0, fade)[:, None]
        out[a:a + n] += seg
    peak = np.abs(out).max() or 1
    return out * (10 ** (-1 / 20) / peak)


def write_wav(path, y, sr):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())


def grid(run, bars=(0, 1)):
    lines = []
    for bar in bars:
        row = []
        for _, step, h in [r for r in run if r[0] == bar]:
            row.append(f"{SHORT.get(h[6], '??')}{h[1]:02d}" if h[0] else " .  ")
        lines.append(f"  bar {bar + 1}: " + " ".join(row))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sample", required=True)
    ap.add_argument("--kit", default="")
    ap.add_argument("--out", default=str(HERE.parents[1] / "out/drummer/renders"))
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    wav = pathlib.Path(a.sample).expanduser().resolve()
    x, sr, slices = read_sample(wav)
    kit_path = pathlib.Path(a.kit) if a.kit else out / "kit.json"
    if not kit_path.is_file():
        kit_path.write_text(json.dumps(DEFAULT_KIT, indent=1))
    spec = json.loads(kit_path.read_text())
    kit = E.make_kit(len(slices), {int(i): tuple(v) for i, v in spec.items()})
    report = [f"sample {wav.name}: {len(slices)} slices; kit {kit_path}"]
    for style, name in enumerate(E.STYLES):
        bpm = TEMPO.get(style, 100)
        runs = {
            "1_groove": E.play(kit, E.params(style=style, human=0, cplx=40, seed=a.seed), 8),
            "2_human": E.play(kit, E.params(style=style, human=100, cplx=40, seed=a.seed), 8),
            "3_brk": E.play(kit, E.params(style=style, human=100, cplx=40, seed=a.seed), 16,
                            brk_curve=lambda bar, st: 0 if bar < 4 or bar >= 12 else
                            min(127, ((bar - 4) * 16 + st) * 127 // 127)),
        }
        for tag, run in runs.items():
            f = out / f"{name.lower().replace('-', '')}_{tag}.wav"
            write_wav(f, render(run, x, sr, slices, bpm), sr)
            shown = (0, 5, 7, 9, 11) if tag == "3_brk" else (0, 1)
            report.append(f"\n{name} {tag} ({bpm} BPM) -> {f.name}\n{grid(run, shown)}")
    (out / "render.txt").write_text("\n".join(report) + "\n")
    print("\n".join(report))
    print(f"\nrenders in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
