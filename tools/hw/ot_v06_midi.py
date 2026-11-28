#!/usr/bin/env python3
"""#1266 MIDI LOOPBACK with MIDI SCENES, over USB MIDI (image `octabam`).

    .venv/bin/python3 tools/hw/ot_v06_midi.py build DEST [--src out/v06c/V06_OCT_01]   # MID_EXT, MID_INT, MID_BOTH
    .venv/bin/python3 tools/hw/ot_v06_midi.py run DEST                                   # load each, play, count what the unit sends

A variant is a project with MIDI track 1 on channel 11, trigs on steps 4, 8, 12 and 16 of pattern A01 and a CC 1 scene lock
(40 in scene A, 100 in scene B; ot_scenes.py stamp), and DEST (bits 2 and 3 of byte 12 of the MIDI SETUP record in every Part
of bank A: EXT 0, INT 4, BOTH 8; modules/midi-loopback/upstream settings.s) set to the variant's. A run plays 8 s with the
crossfader swept A to B and back and counts the note-ons and CCs on channel 11 that arrive on the unit's USB MIDI output.
PR #1266: with INT the notes and the scene CCs stay inside; EXT and BOTH send them out.
"""
import argparse
import pathlib
import shutil
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools"))
import ot_project as P  # noqa: E402

PORT = "Elektron Octatrack DPS-1"
DEST = {"EXT": 0, "INT": 4, "BOTH": 8}
FLAGS_OFF = 0x4E2 + 12             # MIDI track 1's SETUP record starts at Part + 0x4e2 (ot_scenes.py MIDI_SETUP); byte 12 is the flags


def build(a):
    dest = pathlib.Path(a.dest)
    dest.mkdir(parents=True, exist_ok=True)
    for name, v in DEST.items():
        d = dest / f"MID_{name}"
        if d.exists():
            shutil.rmtree(d)
        shutil.copytree(a.src, d)
        r = subprocess.run([sys.executable, str(HERE / "ot_scenes.py"), "stamp", str(d), "--banks", "1", "--trigs", "grid4"],
                           capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"ot_scenes.py stamp failed:\n{r.stdout}{r.stderr}")

        def mut(data, v=v):
            for part in range(8):                          # the four Parts and their saved copies
                data[P.PART_BASE + part * P.PART_STRIDE + 9 + FLAGS_OFF] = v

        P._bank_write(d, 1, mut, guard=False)
        got = (d / "bank01.work").read_bytes()[P.PART_BASE + 9 + FLAGS_OFF]
        print(f"{d}: DEST {name} ({v}), Part 1 flags byte reads {got}")


def classify(msgs):
    out = {"note_on": 0, "cc": 0, "other": 0}
    ccs = []
    for _t, m in msgs:
        i = 0
        while i < len(m):
            b = m[i]
            if b in (0xF8, 0xFE):
                i += 1
            elif b == 0x9A and i + 2 < len(m):
                out["note_on"] += 1
                i += 3
            elif b == 0xBA and i + 2 < len(m):
                out["cc"] += 1
                ccs.append((m[i + 1], m[i + 2]))
                i += 3
            else:
                out["other"] += 1
                i += 1
    return out, ccs


def run(a):
    import ot_midi
    import ot_ladder as L
    results = {}
    for name in DEST:
        d = pathlib.Path(a.dest) / f"MID_{name}"
        r = subprocess.run([sys.executable, str(HERE / "ot_card.py"), "load", str(d)], capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"ot_card.py load {d} failed:\n{r.stdout}{r.stderr}")
        # a second process per variant: CoreMIDI keeps a stale device list across a re-enumeration
        time.sleep(10.0)                  # the first START after a load is silent: the sequencer is not ready for a few seconds
        out = subprocess.run([sys.executable, __file__, "play", name], capture_output=True, text=True)
        print(out.stdout.strip(), out.stderr.strip()[-300:], flush=True)
        results[name] = out.stdout


def play(a):
    import ot_midi
    import ot_ladder as L
    msgs = []
    inp = ot_midi.In(PORT, lambda data: msgs.append((time.monotonic(), bytes(data))))
    c = L.Clock(120.0, PORT)
    try:
        c.pc(1, 0)
        ot_midi.In.pump(2.0)
        c.start(); ot_midi.In.pump(3.0); c.stop(); ot_midi.In.pump(1.0)     # the first START after a load is silent
        msgs.clear()
        c.pc(1, 0)
        ot_midi.In.pump(2.0)
        c.cc(1, 48, 0)
        t0 = time.monotonic()
        c.start()
        while time.monotonic() - t0 < 8.0:
            ph = (time.monotonic() - t0) / 8.0
            c.cc(1, 48, int(127 * (1 - abs(2 * ph - 1))))              # A to B and back
            ot_midi.In.pump(0.1)
        c.stop()
        ot_midi.In.pump(0.5)
    finally:
        c.close()
        inp.close()
    cnt, ccs = classify(msgs)
    print(f"{a.dest}: note-ons on ch 11: {cnt['note_on']}  CCs on ch 11: {cnt['cc']} (values seen {sorted(set(v for _c, v in ccs))[:6]}...)  other bytes: {cnt['other']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("build"); p.add_argument("dest"); p.add_argument("--src", default="out/v06c/V06_OCT_01")
    p = sub.add_parser("run"); p.add_argument("dest")
    p = sub.add_parser("play"); p.add_argument("dest")
    a = ap.parse_args()
    {"build": build, "run": run, "play": play}[a.cmd](a)


if __name__ == "__main__":
    main()
