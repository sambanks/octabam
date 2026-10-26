#!/usr/bin/env python3
"""Put one WAV in a project as a FLEX slot on one track, with the records the unit needs to play it.

    python3 tools/hw/ot_sampleslot.py PROJECT_DIR WAV [--track 8] [--slot 128] [--bpm 120]
                                      [--trig-every 4] [--transport-receive]

A project made by `ot_project.py` from a template has no sample of its own. A STATIC slot copied from a song
project, with no trim record in `markers.work`, drew the trim markers together at the left edge, jumped the
playhead, and one effect on another track then corrupted the probe's output
(docs/contributing/FAILURE_MODES.md, "A generated test project plays a sample wrongly").
What the unit accepts is what `ot_matrix.py` writes for a stimulus: a FLEX slot with `TSMODE=0`, `LOOPMODE=1`,
`BPMx24`, a `[SAMPLE]` block, and a `markers.work` record of (0, frames, 0) at 0x16 + (slot - 1) * 784 with
the file checksum refreshed. This writes those, sets the track's machine to FLEX on that slot in every part of
every bank, optionally trigs every Nth step of pattern A01, and writes the `.strd` twins.

--transport-receive sets MIDI_TRANSPORT_RECEIVE=1 in `project.work` and `project.strd`; the templates have 0, so
MIDI Start does nothing until it is set.
"""
import argparse
import pathlib
import re
import shutil
import struct
import sys
import wave

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ot_project as op

SLOT_REC = 784                      # a markers.work record; FLEX slot n is record n - 1 from 0x16
FLEX_SLOTS = 128


def _one_block(kind, slot):
    """One [SAMPLE] block of the given type and slot. Blocks in a cloned project have no blank line between
    them, so the match must not run past the first [/SAMPLE]."""
    return re.compile(rb"\[SAMPLE\]\r?\nTYPE=%s\r?\nSLOT=%03d\r?\n(?:(?!\[/SAMPLE\]).)*\[/SAMPLE\]\r?\n"
                      % (kind, slot), re.S)


def add_flex_sample(pdir, wav, track=8, slot=128, bpm=120, trig_every=None, transport_receive=False):
    pdir, wav = pathlib.Path(pdir), pathlib.Path(wav)
    if not 1 <= track <= 8 or not 1 <= slot <= FLEX_SLOTS:
        sys.exit("track is 1..8, slot 1..128")
    with wave.open(str(wav)) as w:
        frames, rate = w.getnframes(), w.getframerate()
    bars100 = frames * 100 * bpm // (rate * 60 * 4)
    block = (f"[SAMPLE]\r\nTYPE=FLEX\r\nSLOT={slot:03d}\r\nPATH={wav.name}\r\nTRIM_BARSx100={bars100}"
             f"\r\nLOOP_BARSx100={bars100}\r\nBPMx24={bpm * 24}\r\nTSMODE=0\r\nLOOPMODE=1\r\nGAIN=48"
             f"\r\nTRIGQUANTIZATION=-1\r\n[/SAMPLE]\r\n").encode()
    if wav.parent.resolve() != pdir.resolve():
        shutil.copyfile(wav, pdir / wav.name)
    for suffix in ("work", "strd"):
        f = pdir / f"project.{suffix}"
        if not f.is_file():
            continue
        raw = _one_block(b"FLEX", slot).sub(b"", f.read_bytes(), count=1)
        at = raw.find(b"[SAMPLE]")
        if at < 0:
            sys.exit(f"{f}: no [SAMPLE] block to put the slot before")
        raw = raw[:at] + block + raw[at:]
        if transport_receive:
            raw = raw.replace(b"MIDI_TRANSPORT_RECEIVE=0", b"MIDI_TRANSPORT_RECEIVE=1")
        f.write_bytes(raw)
    for suffix in ("work", "strd"):
        f = pdir / f"markers.{suffix}"
        if not f.is_file():
            continue
        data = bytearray(f.read_bytes())
        off = 0x16 + (slot - 1) * SLOT_REC
        data[off:off + SLOT_REC] = struct.pack(">III", 0, frames, 0) + bytes(SLOT_REC - 12)
        data[-2:] = (sum(data[0x10:-2]) & 0xFFFF).to_bytes(2, "big")
        f.write_bytes(data)

    def mut(data):
        for p in range(op.NPARTS_ALL):
            base = op.PART_BASE + p * op.PART_STRIDE
            data[base + op.MTYPE_OFF + track - 1] = 1                                  # FLEX
            data[base + 0x2d3 + (track - 1) * 5 + op.SLOT_KIND["flex"]] = slot - 1
    for bank in sorted(pdir.glob("bank*.work")):
        op._bank_write(pdir, int(bank.name[4:6]), mut, guard=False)
    if trig_every:
        for step in range(1, 65, trig_every):
            op.set_pattern_trig(pdir, 1, 0, track - 1, step, guard=False)
    op.write_stored(pdir)
    print(f"{pdir.name}: T{track} FLEX slot {slot} = {wav.name} ({frames} frames, {bars100 / 100:.2f} bars at {bpm} BPM)"
          + (f", trig every {trig_every} steps of A01" if trig_every else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("wav")
    ap.add_argument("--track", type=int, default=8)
    ap.add_argument("--slot", type=int, default=128)
    ap.add_argument("--bpm", type=int, default=120)
    ap.add_argument("--trig-every", type=int, default=None)
    ap.add_argument("--transport-receive", action="store_true")
    a = ap.parse_args()
    add_flex_sample(a.project, a.wav, a.track, a.slot, a.bpm, a.trig_every, a.transport_receive)


if __name__ == "__main__":
    main()
