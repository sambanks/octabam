#!/usr/bin/env python3
"""WAVE (modules/wavecf) through the real sequencer under the port: a signed track plays the engine.

Track 1 is WAVE (signature 'W','V',1, PLAYBACK TUNE FRAM CHRD VOIC ATK REL), a trig on steps 1 5 9 13 of every
pattern, the AMP stock; the port runs the sequencer and writes the main output. Each variant's audio is checked
by spectrum: the pitch of TUNE (raw 64 = C3), the chord's notes for CHRD / VOIC, the frame's harmonics for FRAM.

    OT_PROJECT=<a stock project fixture> WCF_IMAGE=out/mainos_bus.bin python3 tools/verify/verify_wavecf_port.py

Skips without OT_PROJECT or the port (make emu-cf)."""
import os
import pathlib
import re
import shutil
import subprocess
import sys
import wave

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools/hw"), str(ROOT / "tools/harness")]
import ot_project as otp  # noqa: E402
from ab_fixture import prepare  # noqa: E402

OUT = pathlib.Path(os.environ.get("WCF_OUT", ROOT / "out/wavecf/port-gate")).resolve()
C3 = 130.8127826502993
# name, PLAYBACK bytes (TUNE FRAM CHRD VOIC ATK REL), expected semitones above C3 of the strongest peaks (all must sound)
VARIANTS = (
    ("sine-c3", (64, 0, 0, 0, 5, 80), (0,)),
    ("sine-e3", (68, 0, 0, 0, 5, 80), (4,)),
    ("major-c3", (64, 0, 3, 2, 5, 80), (0, 4, 7)),
)
FRAMES = int(os.environ.get("WCF_FRAMES", "3000"))


def peaks(x, sr, n=4):
    x = x - x.mean()
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    freqs = np.fft.rfftfreq(len(x), 1.0 / sr)
    out = []
    for _ in range(n):
        k = int(np.argmax(spec))
        out.append((freqs[k], spec[k]))
        spec[max(0, k - 20):k + 20] = 0
    return out


def run(name, play, fixture_src):
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    fixture = prepare(fixture_src, d / "project")
    for bank in fixture.glob("bank*.work"):
        def mutate(data):
            for pi in range(8):
                base = otp.PART_BASE + pi * otp.PART_STRIDE + 9
                data[base + 0x22] = 1
                data[base + 60:base + 63] = b"WV\x01"
                data[base + 0x30:base + 0x36] = bytes(play)
            for pattern in range(16):
                at = otp.trac_off(pattern, 0)
                data[at:at + 8] = (0x1111).to_bytes(8, "big")
        otp._bank_write(fixture, int(bank.stem[4:]), mutate, guard=False)
    card = d / "card.img"
    subprocess.run([sys.executable, str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(fixture), "OCTABAM", "RIG",
                    "--tree", str(d / "tree"), "--out", str(card)], check=True, cwd=ROOT)
    image = d / "image.bin"
    shutil.copy2(os.environ.get("WCF_IMAGE", ROOT / "out/mainos_bus.bin"), image)
    emu = os.environ.get("WCF_EMU", str(ROOT / "out/emu/ot_emu"))
    wav = d / "audio"
    cmd = [emu, "--image", str(image), "--card", str(card), "--set", "OCTABAM", "--project", "RIG", "--load-ms", "20000",
           "--sequencer", "--internal-clock", "--bank", "0", "--frames", str(FRAMES), "--dsp", "--main-level", "64",
           "--audio-out", str(wav)]
    with (d / "port.log").open("w") as log:
        log.write(" ".join(cmd) + "\n")
        log.flush()
        subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT, check=True, timeout=900)
    log = (d / "port.log").read_text()
    assert "ILLEGAL" not in log, f"{name}: an illegal instruction ({d / 'port.log'})"
    files = sorted(d.glob("audio*.wav"))
    assert files, (name, "no audio written", log[-1500:])
    return files[0]


def main():
    src = os.environ.get("OT_PROJECT")
    if not src:
        print("[SKIP] WAVE port: set OT_PROJECT to a stock project fixture")
        return 0
    if not pathlib.Path(os.environ.get("WCF_EMU", ROOT / "out/emu/ot_emu")).exists():
        print("[SKIP] WAVE port: no port (make emu-cf)")
        return 0
    fails = 0
    for name, play, semis in VARIANTS:
        path = run(name, play, src)
        with wave.open(str(path)) as w:
            sr, ch, width, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
            assert width == 3, (name, "expected 24-bit core audio", width)
            a = np.frombuffer(w.readframes(n), dtype=np.uint8).reshape(-1, ch, 3).astype(np.int32)
        v = a[:, :, 0] | (a[:, :, 1] << 8) | (a[:, :, 2] << 16)
        v = np.where(v & 0x800000, v - (1 << 24), v) / float(1 << 23)
        x = v[:, int(np.argmax(np.sqrt((v ** 2).mean(axis=0))))]       # the core's loudest channel (the track's L)
        act = np.nonzero(np.abs(x) > 1e-4)[0]
        assert len(act) > sr, (name, "less than a second of sound", len(act))
        x = x[act[0]:act[0] + 3 * sr]
        rms = float(np.sqrt(np.mean(x ** 2)))
        pk = peaks(x, sr)
        top = [f for f, _ in pk]
        ok = rms > 1e-3 and all(any(abs(f - C3 * 2 ** (s / 12.0)) < 3.0 + 0.02 * C3 * 2 ** (s / 12.0) for f in top) for s in semis)
        print(("PASS " if ok else "FAIL ") + f"{name}: rms {rms:.4f}, peaks {[round(f, 1) for f in top]} Hz, want "
              f"{[round(C3 * 2 ** (s / 12.0), 1) for s in semis]}")
        fails += not ok
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
