#!/usr/bin/env python3
"""PROBE (not a gate): a Pickup machine recording and looping under the port, on any image.

    python3 tools/verify/probe_pickup_port.py [--image out/raw/section_3_MAIN_OS.bin] [--bpm 128]
        [--bars 2] [--passes 4] [--trig one2] [--input tones|FILE.wav] [--rec1-at PASSES ...]
        [--watch-mem SPEC] [--watch-pc ADDRS] [--keep]

The fixture is a fresh project made by the image itself (tools/hw/ot_fresh.py),
with T1 a PICKUP on recorder buffer 1 and T1's RECORDING SETUP TRIG set, in
every Part of every bank (TRAPS.md trap-otemu-part), at --bpm. The live script
turns the volume knob (a --live-script run posts no main level:
trap-live-script-level), closes the boot's SET DATE/TIME (NO), presses PLAY,
then REC1 to start the take and REC1 again --bars bars later to end it. With
TRIG = ONE2 the second REC1 ends the take and plays it (trap-pickup-trig); with
ONE it records a new take, and nothing plays.

It prints the recorder mailbox (0x46c7e9fa) and LIMIT (0x46c7fe24) writes, T1's
voice record at the end (0x800049d8: +0 playing, +1 recording, +20 machine,
+21 slot, +0x2c END) and MAIN (TX0 ring words 2 and 3 of core 0's --audio-out)
per pass of the loop: peak level and the largest sample-to-sample step within
64 samples of the loop point against the largest elsewhere in the pass. It
exits 1 unless T1's voice plays the Pickup and MAIN carries it.

Everything it writes is under out/pickup_port/<tag>/ (made from the user's own
OS: never commit it).
"""
import argparse
import contextlib
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
NO, PLAY, REC1 = 0x32, 0x28, 0x2B
TRIG = {"one": 0, "one2": 1, "hold": 2}
FS = 44100


def key(ms, code, hold=60):
    return [f"{ms} key {code:#x} down", f"{ms + hold} key {code:#x} up"]


def fixture(fresh, dest, bpm, trig):
    """T1 PICKUP on R1 with TRIG `trig` in every Part (and its saved copy) of every bank."""
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(fresh, dest)
    otp.guard_backup = lambda: None                 # a project the port made, not a unit's backup
    with contextlib.redirect_stdout(io.StringIO()):
        for b in range(1, 17):
            for p in range(1, 5):
                otp.set_machine_type(dest, b, p, 1, 4)
                otp.set_recorder_setup(dest, b, p, 0, "TRIG", TRIG[trig], guard=False)
                for pp in (p, p + 4):
                    otp.set_track_slot(dest, b, pp, 1, 129, "pickup")
        otp.set_tempo(dest, bpm)


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
        fixture(fresh / "image/PROJECT 000000", out / "proj", a.bpm, a.trig)
        r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(out / "proj"), "OCTABAM", "PUM",
                            "--tree", str(out / "tree"), "--out", str(card)], cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"probe_pickup_port: stage_card failed:\n{(r.stdout + r.stderr)[-1200:]}")

    bar_ms = 4 * 60000 / float(a.bpm)
    t_rec, t_end = 2000, 2000 + round(a.bars * bar_ms)
    lines = ["300 pot 200"] + key(500, NO) + key(1000, PLAY) + key(t_rec, REC1) + key(t_end, REC1)
    for p in a.rec1_at:
        lines += key(t_end + round(p * a.bars * bar_ms), REC1)
    quit_ms = t_end + round((a.passes + 0.5) * a.bars * bar_ms)
    lines = sorted(lines, key=lambda l: int(l.split()[0])) + [f"{quit_ms} quit"]
    (out / "run.script").write_text("\n".join(lines) + "\n")
    watch = ";".join(x for x in (f"{MAILBOX:#x},4", f"{LIMIT:#x},4", f"{VOICE:#x},1", a.watch_mem) if x)
    cmd = [EMU, "--image", a.image, "--card", card, "--set", "OCTABAM", "--project", "PUM", "--load-ms", "90000",
           "--mkii", "--dsp", "--internal-clock", "--audio-in", a.input, "--live-script", out / "run.script",
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
        print(f"    MAIN from sample {start}; per pass of {end} samples (peak, the largest step "
              f"within 64 of the loop point / elsewhere):")
        for k in range((len(left) - start) // end):
            s = start + k * end
            seg = left[s:s + end]
            steps = [abs(seg[i + 1] - seg[i]) for i in range(len(seg) - 1)]
            near = max(steps[:64] + steps[-64:]) if steps else 0
            far = max(steps[64:-64]) if len(steps) > 128 else 0
            print(f"      pass {k}: peak {max(map(abs, seg))}, step {near} / {far}")
    print(f"  [{'ok' if ok else 'FAIL'}] T1 plays the Pickup (voice playing, machine 4, slot R1) and MAIN carries it")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
