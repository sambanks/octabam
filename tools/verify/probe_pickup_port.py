#!/usr/bin/env python3
"""PROBE (not a gate): a Pickup machine recording and looping under the port, on any image.

    python3 tools/verify/probe_pickup_port.py [--image out/raw/section_3_MAIN_OS.bin] [--bpm 128]
        [--bars 2] [--passes 4] [--trig one2] [--end rec1|rec2] [--input tones|FILE.wav | --sine PERIOD]
        [--rec1-at PASSES ...] [--rec2-at PASSES ...] [--watch-mem SPEC] [--watch-pc ADDRS] [--keep]

The fixture is a fresh project made by the image itself (tools/hw/ot_fresh.py),
with T1 a PICKUP on recorder buffer 1 and T1's RECORDING SETUP TRIG set, in
every Part of every bank (TRAPS.md trap-otemu-part), at --bpm. The live script
turns the volume knob (a --live-script run posts no main level:
trap-live-script-level), closes the boot's SET DATE/TIME (NO), presses PLAY,
then REC1 to start the take and, --bars bars later, REC1 or REC2 to end it.
With TRIG = ONE2 a second REC1 ends the take, plays it and overdubs every pass
(trap-pickup-trig); with ONE it records a new take, and nothing plays. REC2
ends the take and plays it with no overdub.

It prints the recorder mailbox (0x46c7e9fa) and LIMIT (0x46c7fe24) writes, T1's
voice record at the end (0x800049d8: +0 playing, +1 recording, +20 machine,
+21 slot, +0x2c END) and MAIN (TX0 ring words 2 and 3 of core 0's --audio-out)
per pass of the loop. A pass is --bars bars of the sequencer, not END: a
synced Pickup restarts on the bar (165,375 samples for 2 bars at 128 BPM),
before END. For each pass it gives the peak level and the largest
sample-to-sample step within 64 samples of the restart against the largest
elsewhere. With --sine PERIOD the input is a sine of that many samples and the
measure is its residual x[n+1] + x[n-1] - 2 cos(w) x[n], zero for a clean
sine. A synced Pickup plays its take (END samples) resampled into the bars, so
pick a PERIOD that divides END (16 for 2 bars at 128 BPM, END 165,392), not
the pass: then a jump at the restart is the firmware's, not the take's seam.
The input starts on the script's clock (`1000 audio start`); --sine-to-end
silences it when the take ends. It exits 1 unless T1's voice plays the
Pickup and MAIN carries it.

Everything it writes is under out/pickup_port/<tag>/ (made from the user's own
OS: never commit it).
"""
import argparse
import contextlib
import math
import io
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import wave

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools")); import toolpath  # noqa: E402,F401
import ot_project as otp  # noqa: E402

EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
MAILBOX, LIMIT, VOICE = 0x46C7E9FA, 0x46C7FE24, 0x800049D8   # T1's recorder mailbox and LIMIT; T1's voice
NO, PLAY, REC1, REC2 = 0x32, 0x28, 0x2B, 0x2C
TRIG = {"one": 0, "one2": 1, "hold": 2}
FS = 44100


def key(ms, code, hold=60):
    return [f"{ms} key {code:#x} down", f"{ms + hold} key {code:#x} up"]


def fixture(fresh, dest, bpm, trig, setup=()):
    """T1 PICKUP on R1 with TRIG `trig` and any further RECORDING SETUP (field, raw value) pairs,
    in every Part (and its saved copy) of every bank."""
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(fresh, dest)
    otp.guard_backup = lambda: None                 # a project the port made, not a unit's backup
    with contextlib.redirect_stdout(io.StringIO()):
        for b in range(1, 17):
            for p in range(1, 5):
                otp.set_machine_type(dest, b, p, 1, 4)
                otp.set_recorder_setup(dest, b, p, 0, "TRIG", TRIG[trig], guard=False)
                for field, v in setup:
                    otp.set_recorder_setup(dest, b, p, 0, field, v, guard=False)
                for pp in (p, p + 4):
                    otp.set_track_slot(dest, b, pp, 1, 129, "pickup")
        otp.set_tempo(dest, bpm)


def sine_wav(path, period, level, secs, until=None):
    """A stereo 24-bit sine of `period` samples (a whole number of them in a loop that is a multiple of it),
    silent from sample `until` on."""
    amp = round(level * 0x7FFFFF)
    frame = b"".join(struct.pack("<i", round(amp * math.sin(2 * math.pi * n / period)))[:3] * 2
                     for n in range(period))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(3); w.setframerate(FS)
        n = secs * FS // period + 1
        if until is None:
            w.writeframes(frame * n)
        else:
            w.writeframes((frame * (until // period + 1))[:6 * until] + bytes(6 * (n * period - until)))


def main_out(prefix):
    """MAIN L/R (ring words 2, 3) of core 0's 24-bit --audio-out WAV."""
    with wave.open(f"{prefix}_core0.wav") as w:
        ch, raw = w.getnchannels(), w.readframes(w.getnframes())
    n = len(raw) // (3 * ch)
    out = ([], [])
    for i in range(n):
        for k, c in enumerate((2, 3)):
            o = 3 * (i * ch + c)
            v = raw[o] | raw[o + 1] << 8 | raw[o + 2] << 16
            out[k].append(v - (1 << 24) if v & 0x800000 else v)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--image", default=str(ROOT / "out/raw/section_3_MAIN_OS.bin"))
    ap.add_argument("--bpm", default="128")
    ap.add_argument("--bars", type=float, default=2, help="the take's length, from the first REC1 to the second")
    ap.add_argument("--passes", type=int, default=4, help="passes of the loop to run after the take")
    ap.add_argument("--trig", choices=sorted(TRIG), default="one2")
    ap.add_argument("--input", default="tones", help="'tones' or a 16/24-bit WAV fed to the inputs from the transport start")
    ap.add_argument("--end", choices=("rec1", "rec2"), default="rec1",
                    help="end the take with REC1 (ONE2: plays and overdubs), or with REC2 "
                         "(plays, no overdub)")
    ap.add_argument("--qrec", type=int, default=None, help="T1's QREC, raw: -1 OFF (stock's default), 0 PLEN, "
                    "1-16 the step ladder 1 2 3 4 6 8 12 16 24 32 48 64 96 128 192 256")
    ap.add_argument("--qpl", type=int, default=None, help="T1's QPL, raw, as --qrec")
    ap.add_argument("--src3", type=int, default=0, help="T1's SRC3, raw: 0 '-' (the default here), 1-8 T1-T8, "
                    "9 MAIN (a fresh project's: an overdub then records the loop again, through MAIN), 10 CUE")
    ap.add_argument("--sine", type=int, default=0, metavar="PERIOD",
                    help="feed a sine of PERIOD samples (256 divides 2 bars at 128 BPM) and report its residual")
    ap.add_argument("--sine-to-end", action="store_true",
                    help="the sine stops when the take ends: an overdub then records silence")
    ap.add_argument("--level", type=float, default=0.06, help="the --sine level, of full scale")
    ap.add_argument("--rec2-at", type=float, action="append", default=[],
                    help="a REC2 press (play / stop; while overdubbing, stops the overdub), in passes after the take ends")
    ap.add_argument("--rec1-at", type=float, action="append", default=[],
                    help="a further REC1 press, in passes after the take ends (repeatable)")
    ap.add_argument("--watch-mem", default="", help="more ranges for --watch-mem, ';'-joined")
    ap.add_argument("--watch-pc", default="")
    ap.add_argument("--tag", default="run")
    ap.add_argument("--keep", action="store_true", help="reuse this tag's project and card")
    a = ap.parse_args()
    if not EMU.is_file():
        sys.exit("probe_pickup_port: no port binary (make emu-cf)")
    out = ROOT / "out/pickup_port" / a.tag
    out.mkdir(parents=True, exist_ok=True)
    card = out / "card.img"
    if not (a.keep and card.is_file()):
        fresh = ROOT / "out/pickup_port/fresh"
        if not (fresh / "image/PROJECT 000000").is_dir():
            r = subprocess.run([str(PY), str(ROOT / "tools/hw/ot_fresh.py"), "--image", a.image, "--out", str(fresh)],
                               cwd=ROOT, capture_output=True, text=True)
            if r.returncode:
                sys.exit(f"probe_pickup_port: ot_fresh failed:\n{(r.stdout + r.stderr)[-1200:]}")
        setup = [(f, v) for f, v in (("QREC", a.qrec), ("QPL", a.qpl), ("SRC3", a.src3)) if v is not None]
        fixture(fresh / "image/PROJECT 000000", out / "proj", a.bpm, a.trig, setup)
        r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(out / "proj"), "OCTABAM", "PUM",
                            "--tree", str(out / "tree"), "--out", str(card)], cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"probe_pickup_port: stage_card failed:\n{(r.stdout + r.stderr)[-1200:]}")

    bar_ms = 4 * 60000 / float(a.bpm)
    t_rec, t_end = 2000, 2000 + round(a.bars * bar_ms)
    lines = ["300 pot 200", "1000 audio start"] + key(500, NO) + key(1000, PLAY) + key(t_rec, REC1) + key(t_end, REC1 if a.end == "rec1" else REC2)
    for p in a.rec1_at:
        lines += key(t_end + round(p * a.bars * bar_ms), REC1)
    for p in a.rec2_at:
        lines += key(t_end + round(p * a.bars * bar_ms), REC2)
    quit_ms = t_end + round((a.passes + 0.5) * a.bars * bar_ms)
    if a.sine:
        a.input = str(out / "sine.wav")
        # the input starts on the script's clock, at its `1000 audio start` (TRAPS.md trap-two-clocks)
        until = round((t_end - 1000) * FS / 1000) if a.sine_to_end else None
        sine_wav(out / "sine.wav", a.sine, a.level, quit_ms // 1000 + 2, until)
    lines = sorted(lines, key=lambda l: int(l.split()[0])) + [f"{quit_ms} quit"]
    (out / "run.script").write_text("\n".join(lines) + "\n")
    watch = ";".join(x for x in (f"{MAILBOX:#x},4", f"{LIMIT:#x},4", f"{VOICE:#x},1", a.watch_mem) if x)
    cmd = [EMU, "--image", a.image, "--card", card, "--set", "OCTABAM", "--project", "PUM", "--load-ms", "90000",
           "--mkii", "--dsp", "--internal-clock", "--audio-in", a.input, "--audio-in-on-cue", "--live-script", out / "run.script",
           "--watch-mem", watch, "--audio-out", out / "run", "--mem-dump", f"{VOICE:#x},168={out / 'voice.bin'}"]
    if a.watch_pc:
        cmd += ["--watch-pc", a.watch_pc]
    with open(out / "run.txt", "w") as f:
        rc = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
    log = (out / "run.txt").read_text(errors="replace")
    if rc or not (out / "voice.bin").is_file():
        sys.exit(f"probe_pickup_port: ot_emu exit {rc} -- {out / 'run.txt'}")

    writes = re.findall(r"\[\s*([\d.]+)\] \[(0x[0-9a-f]+)\] <- (\S+) \(\d\) at pc (0x[0-9a-f]+)", log)
    print(f"  {out}")
    for t, addr, v, pc in writes:
        if int(addr, 16) in (MAILBOX, LIMIT) and int(v, 0):
            print(f"    {float(t):>10.1f}  [{addr}] <- {v}  at {pc}")
    vb = (out / "voice.bin").read_bytes()
    end = struct.unpack_from(">I", vb, 0x2C)[0]
    playing, machine, slot = vb[0], vb[20], vb[21]
    print(f"    T1 voice: playing {vb[0]:#04x} recording {vb[1]:#04x} flag {vb[2]:#04x} machine {machine} "
          f"slot {slot:#04x} END {end}")

    left, _ = main_out(out / "run")
    start = next((i for i, x in enumerate(left) if x), None)
    ok = playing != 0 and machine == 4 and slot == 0x80 and start is not None and end > 0
    if start is not None and end > 0:
        what = "sine residual" if a.sine else "step"
        period = round(a.bars * 4 * 60 * FS / float(a.bpm))
        print(f"    MAIN from sample {start}; per pass of {period} samples (peak, the largest {what} "
              f"within 64 of the loop point / elsewhere, and where the largest is):")
        c2 = 2 * math.cos(2 * math.pi / a.sine) if a.sine else 0
        # over the whole of MAIN first, so a jump on a pass's first or last sample is not cut off
        x = left[start:]
        if a.sine:                  # zero for a clean sine of that period, whatever its level and phase
            d = [0.0] + [abs(x[i + 1] + x[i - 1] - c2 * x[i]) for i in range(1, len(x) - 1)] + [0.0]
        else:
            d = [0.0] + [abs(x[i] - x[i - 1]) for i in range(1, len(x))]
        for k in range(len(x) // period):
            lo, hi = k * period, (k + 1) * period
            near = max(d[max(lo - 64, 0):lo + 64] + d[max(hi - 64, 0):hi + 64])
            far = max(d[lo + 64:hi - 64])
            worst = max(range(lo, hi), key=d.__getitem__) - lo
            print(f"      pass {k}: peak {max(map(abs, x[lo:hi]))}, {what} {near:.0f} / {far:.0f}, largest at +{worst}")
    print(f"  [{'ok' if ok else 'FAIL'}] T1 plays the Pickup (voice playing, machine 4, slot R1) and MAIN carries it")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
