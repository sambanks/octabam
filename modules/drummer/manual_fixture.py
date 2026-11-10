#!/usr/bin/env python3
"""The manual's DRUMMER project: a synthetic drum loop on T1, for tools/site/capture_manual.py's
`drummer` group (no sample of anyone's: the loop is made here, at capture time).

    build(fixture) -> the stage_card --audio arguments

The loop: one bar at 120 BPM (2 s, 44.1 kHz mono 16 bit), sixteen 16th-note hits, each its own
slice -- KICK HATC HATC GHOST SNARE HATC KICK HATC HATC KICK HATC GHOST SNARE HATC KICK HATO --
made so AUTO (autokit.c) hears what they are: a kick is a falling sine, a snare a tone over noise,
a ghost the snare 18 dB down, a hat differentiated noise (open: a long one). The project (a fresh
one, as the manual's other groups use) gets FLEX slot 1 = the loop with its sixteen slices,
TRIM_BARS 1, 120 BPM; T1 FLEX on slot 1 in every Part, no trig; the project at 120 BPM.
"""
import math
import pathlib
import random
import re
import struct
import sys
import wave

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools")); import toolpath  # noqa: E402,F401
from hw import ot_project as otp  # noqa: E402

RATE, TEMPO, STEPS = 44100, 120, 16
STEP = RATE * 60 // TEMPO // 4                        # 5512 frames a 16th
PATTERN = ["K", "H", "H", "G", "S", "H", "K", "H", "H", "K", "H", "G", "S", "H", "K", "O"]
SAMPLE_REL = "AUDIO/DRUMMER_LOOP.wav"
SETUP_OFF, VALUES_OFF, FLEX = 0x1e3, 0x033, 1


def _hit(kind, n, rng):
    """One hit, a little different each time (level, pitch, decay), as a played loop is."""
    out = []
    prev = low = 0.0
    lvl, det, dec = rng.uniform(0.8, 1.0), rng.uniform(0.85, 1.18), rng.uniform(0.6, 1.6)
    for i in range(n):
        t = i / RATE
        if kind == "K":
            f = (45 + 90 * math.exp(-t * 30)) * det
            v = math.sin(2 * math.pi * f * t) * math.exp(-t * 9 * dec)
        elif kind in ("S", "G"):
            low += 0.35 * (rng.uniform(-1, 1) - low)       # the snares' rattle: noise, low-passed
            v = (0.9 * math.sin(2 * math.pi * 170 * det * t) * math.exp(-t * 25 * dec)
                 + 0.9 * low * math.exp(-t * 20 * dec))
            if kind == "G":
                v *= 0.125
        else:                                          # hats: noise, differentiated (highs only)
            noise = rng.uniform(-1, 1)
            v, prev = (noise - prev) * 0.5, noise
            v *= math.exp(-t * (8 if kind == "O" else 60) * dec)
        out.append(v * lvl)
    return out


def loop_wav(path):
    rng = random.Random(78)
    frames = []
    for kind in PATTERN:
        frames += _hit(kind, STEP, rng)
    peak = max(abs(v) for v in frames) or 1.0
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(v / peak * 26000)) for v in frames))
    return len(frames)


def build(fixture):
    fixture = pathlib.Path(fixture)
    wav = fixture / "DRUMMER_LOOP.wav"
    total = loop_wav(wav)
    block = ("[SAMPLE]\r\nTYPE=FLEX\r\nSLOT=001\r\nPATH=../" + SAMPLE_REL + "\r\n"
             "TRIM_BARSx100=100\r\nLOOP_BARSx100=100\r\nBPMx24=" + str(TEMPO * 24) + "\r\n"
             "TSMODE=0\r\nLOOPMODE=0\r\nGAIN=48\r\nTRIGQUANTIZATION=-1\r\n[/SAMPLE]\r\n\r\n").encode()
    for suffix in ("work", "strd"):
        pw = fixture / f"project.{suffix}"
        if not pw.is_file():
            continue
        raw = pw.read_bytes()
        raw = re.sub(rb"\[SAMPLE\]\r\nTYPE=FLEX\r\nSLOT=001\r\n.*?\[/SAMPLE\]\r\n\r\n", b"", raw, flags=re.S)
        at = raw.find(b"[SAMPLE]")
        if at < 0:
            raw = raw.rstrip(b"\r\n") + b"\r\n\r\n"
            at = len(raw)
        pw.write_bytes(raw[:at] + block + raw[at:])
    otp.set_tempo(fixture, TEMPO)
    rec = struct.pack(">III", 0, total, 0xffffffff)
    rec += b"".join(struct.pack(">III", i * STEP, (i + 1) * STEP, 0xffffffff) for i in range(STEPS))
    rec += bytes(12 * (64 - STEPS)) + struct.pack(">I", STEPS)
    assert len(rec) == 784
    for suffix in ("work", "strd"):
        pm = fixture / f"markers.{suffix}"
        if not pm.is_file():
            continue
        data = bytearray(pm.read_bytes())
        data[0x16:0x16 + 784] = rec                     # FLEX slot 1
        data[-2:] = (sum(data[0x10:-2]) & 0xFFFF).to_bytes(2, "big")
        pm.write_bytes(bytes(data))

    def mut(data):
        for p in range(otp.NPARTS_ALL):
            base = otp.PART_BASE + p * otp.PART_STRIDE
            data[base + otp.MTYPE_OFF] = FLEX
            data[base + 0x2d3 + FLEX] = 0                # T1: FLEX slot 1
            setup = base + SETUP_OFF + 6 * FLEX
            data[setup + 0] = 0                          # LOOP off
            data[setup + 1] = 1                          # SLIC on
            data[setup + 4] = 0                          # TSTR off
        off = otp.trac_off(0, 0)
        data[off:off + 64] = bytes(64)                   # no trig on T1
    for bank in sorted(fixture.glob("bank*.work")):
        otp._bank_write(fixture, int(bank.stem[4:]), mut, guard=False)
    return ["--audio", f"{wav}:{SAMPLE_REL}"]
