#!/usr/bin/env python3
"""The MAIN/CUE-to-track alignment of the twenty-channel USB stream, under the
ColdFire port.

USB AUDIO OUT TRACKS MAIN CUE reads channels 1-16 from the tracks' read-back
arena (the previous ping-pong bank) and 17-20 from the mixdown buffer (the
current pull), two sources with two timings. On hardware MAIN was heard
lagging the tracks (Bryan T, 25 Sep 2026), the amount unmeasured. This
stages the tone project (tools/harness/usb_sig_project.py: track N's left
channel at 200 + 100 N Hz, its right at +50) on a card, runs the remix under
the port with the sequencer playing, and at the end dumps the producer's
own ring (`aud_ring`, 1,024 frames x 20 channels, the last 23 ms, contiguous
once unwrapped at `aud_produced`) -- no USB bench, whose polls pace nothing
under --sequencer; `aud_force` is poked to 1 after the load so the producer
runs, as it otherwise does only while a host asks for the stream. The lag of MAIN L (channel 17) behind each track's left
channel comes from the phase of that track's tone in both, Goertzel at the
known frequency over the same window: lag = (phase_track - phase_main) /
(2 pi f) samples, modulo the tone's period. Every tone that sounds gives a
residue; the one lag in [-SEARCH, SEARCH] that fits them all is reported, in
samples and in 16-sample blocks; MAIN R against the right channels likewise.

    tools/harness/usb_align.py [--source <project>] [--remix usb-out-tracks-main-cue] [--frames 3000]

The source project is the template usb_sig_project.py needs (a locally saved
Octatrack project; default OT_PROJECT or ~/.octabam_project). The remix must
carry USB AUDIO OUT TRACKS MAIN CUE. Needs the port (make emu-cf) and the .venv.
"""
import argparse
import cmath
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import toolpath  # noqa: E402,F401
from remix import registry, brain  # noqa: E402

EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/usb_align"
FS = 44100
NCH = 20
FRAME_B = 4 * NCH
SEARCH = 4096                       # samples either side


def tone(track):
    """(left Hz, right Hz) of track 1..8, as usb_sig_project.py makes them."""
    f = 200 + 100 * track
    return f, f + 50


def goertzel(x, f):
    w = -2j * math.pi * f / FS
    return sum(v * cmath.exp(w * k) for k, v in enumerate(x))


def lag_fit(pairs):
    """pairs: (f, phase_track - phase_main). The lag in [-SEARCH, SEARCH] that
    fits every tone's residue best, the smallest |lag| among equals; returns
    (lag, rms residual in samples)."""
    best = None
    for d in sorted(range(-SEARCH, SEARCH + 1), key=abs):
        err = 0.0
        for f, dphi in pairs:
            period = FS / f
            r = (dphi * period / (2 * math.pi) - d) % period
            r = min(r, period - r)
            err += r * r
        if best is None or err < best[1] - 1e-9:
            best = (d, err)
    return best[0], math.sqrt(best[1] / len(pairs))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default=os.environ.get("OT_PROJECT") or
                    (pathlib.Path("~/.octabam_project").expanduser().read_text().strip()
                     if pathlib.Path("~/.octabam_project").expanduser().is_file() else ""))
    ap.add_argument("--remix", default="usb-out-tracks-main-cue")
    ap.add_argument("--frames", type=int, default=3000, help="DSP frames the port runs after the transport start (the ring holds the last 1,024)")
    ap.add_argument("--image", default="", help="a built image (default: build the remix)")
    a = ap.parse_args()
    if not a.source:
        sys.exit("usb_align: no source project (--source, OT_PROJECT or ~/.octabam_project)")
    if not EMU.exists() or not PY.exists():
        sys.exit("usb_align: needs the port (make emu-cf) and the .venv")
    remix = registry.remix(a.remix)
    if brain.value(remix, registry.modules(), "octabam.usb-audio-out", "LAYOUT") != "TRACKS MAIN CUE":
        sys.exit(f"usb_align: {a.remix} does not carry USB AUDIO OUT with LAYOUT TRACKS MAIN CUE")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    image = OUT / "image.bin"
    if a.image:
        shutil.copy2(a.image, image)
    else:
        env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
        r = subprocess.run([sys.executable, "tools/build/build_bus.py"], cwd=ROOT, env=env, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"usb_align: build failed\n{r.stdout[-800:]}{r.stderr[-800:]}")
        shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    proj = OUT / "project"
    r = subprocess.run([str(PY), "tools/harness/usb_sig_project.py", "--source", a.source, "--out", str(proj)],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"usb_align: usb_sig_project failed\n{r.stdout[-800:]}{r.stderr[-800:]}")
    # MASTER TRACK off, as verify_set runs: MAIN is then the plain mix, and
    # every track's tone reaches it (with it on, MAIN is T8's output alone).
    pw = proj / "project.work"
    pw.write_bytes(pw.read_bytes().replace(b"MASTER_TRACK=1", b"MASTER_TRACK=0"))
    audio = [f"{proj / 'AUDIO' / 'USBSIG' / f'T{t}.wav'}:AUDIO/USBSIG/T{t}.wav" for t in range(1, 9)]
    card = OUT / "card.img"
    cmd = [str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(proj), "OCTABAM", "USBSIG",
           "--tree", str(OUT / "tree"), "--out", str(card), "--image-mb", "64"]
    for x in audio:
        cmd += ["--audio", x]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"usb_align: stage_card failed\n{r.stdout[-800:]}{r.stderr[-800:]}")
    nm = subprocess.run(["m68k-elf-nm", str(ROOT / "out/platform/runtime/runtime.elf")], capture_output=True, text=True).stdout
    sym = {p[2]: int(p[0], 16) for p in (l.split() for l in nm.splitlines()) if len(p) == 3}
    ring_b = 1024 * FRAME_B
    log = OUT / "port.txt"
    with open(log, "w") as lf:
        r = subprocess.run([str(EMU), "--image", str(image), "--card", str(card), "--set", "OCTABAM",
                            "--project", "USBSIG", "--sequencer", "--internal-clock", "--poke-trig", "2",
                            "--frames", str(a.frames), "--load-ms", "90000",
                            # the producer runs only while a host asks for the stream (5 Oct 2026);
                            # aud_force is its harness switch: produce with no bench attached and
                            # EP3 left alone (asking for alt 1 instead spins the bring-up on the
                            # unmodelled controller and the frame interrupt never returns)
                            "--poke", f"{sym['aud_force']:#x}=1",
                            "--dsp", "--main-level", "64",          # both cores live; MAIN volume up (verify_set's run)
                            "--mem-dump", f"{sym['aud_ring']:#x},{ring_b}={OUT / 'ring.bin'};"
                                          f"{sym['aud_produced']:#x},4={OUT / 'produced.bin'}"],
                           cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT)
    if r.returncode:
        sys.exit(f"usb_align: ot_emu exit {r.returncode} -- {log}")
    raw = (OUT / "ring.bin").read_bytes()
    produced = int.from_bytes((OUT / "produced.bin").read_bytes(), "big")
    n = 1024
    print(f"ring: {n} frames, {produced} produced, {log}")
    # unwrap: frame (produced - 1024 + i) sits at slot (produced - 1024 + i) & 1023
    start = produced - n
    ch = [[0] * n for _ in range(NCH)]
    for i in range(n):
        base = ((start + i) & (n - 1)) * FRAME_B
        for c in range(NCH):
            w = int.from_bytes(raw[base + 4 * c:base + 4 * c + 4], "little")
            v = w >> 8
            ch[c][i] = v - (1 << 24) if v & 0x800000 else v
    allpairs = []
    for side, main_ch in (("L", 16), ("R", 17)):
        pairs, rows = [], []
        for t in range(1, 9):
            f = tone(t)[0 if side == "L" else 1]
            xt = goertzel(ch[2 * (t - 1) + (0 if side == "L" else 1)], f)
            xm = goertzel(ch[main_ch], f)
            # only a tone that reaches MAIN near full level is on the direct path;
            # a faint component is the bus engines' wet return (a delay of its
            # own) or leakage, and its phase says nothing about the producer
            if abs(xt) < 1e5 or abs(xm) < 0.3 * abs(xt):
                rows.append(f"    T{t} {f} Hz: track {abs(xt):.3g} main {abs(xm):.3g} -- too weak, skipped")
                continue
            dphi = cmath.phase(xt) - cmath.phase(xm)
            period = FS / f
            rows.append(f"    T{t} {f} Hz: |track| {abs(xt) / n * 2:.0f} |main| {abs(xm) / n * 2:.0f}  "
                        f"lag mod {period:.1f} = {(dphi * period / (2 * math.pi)) % period:.2f} samples")
            pairs.append((f, dphi))
        print(f"MAIN {side} against the tracks' {side} channels:")
        print("\n".join(rows))
        allpairs += pairs
        if len(pairs) >= 2:
            d, res = lag_fit(pairs)
            print(f"  -> MAIN {side} lags the tracks by {d} samples = {d / 16:.3f} blocks (rms residual {res:.2f} samples over {len(pairs)} tones)")
        else:
            print("  -> too few tones on this side to fit a lag")
    if len(allpairs) < 2:
        print("RESULT: no fit"); return 1
    d, res = lag_fit(allpairs)
    print(f"RESULT: MAIN lags the tracks by {d} samples = {d / 16:.3f} blocks (rms residual {res:.2f} samples over {len(allpairs)} tones, both sides)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
