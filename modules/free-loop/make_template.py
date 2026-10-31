#!/usr/bin/env python3
"""FREE LOOP's template project (and verify_free_loop's fixture): guitar loops on T1/T2,
synth loops on T3/T4, FREE LOOP's pedals.

    python3 modules/free-loop/make_template.py [--image out/mainos_bus.bin] [--out out/templates] [--name FREE_LOOP]

An empty project made by the image itself (tools/hw/ot_fresh.py), then, in
every bank (A-P) and all four Parts (and their saved copies):

  T1  FLEX on R1: the guitar loop    (FREE LOOP role FREE: its first free loop sets the tempo)
  T2  FLEX on R2: the guitar layer   (GRID)
  T3  FLEX on R3: the synth loop     (FREE)
  T4  FLEX on R4: the synth layer    (GRID)
  T5-T8 untouched (the pre-recorded samples; FREE LOOP leaves them stock)
  RECORDING SETUP of T1/T2: INAB = A B, of T3/T4: INCD = C D; SRC3 = the
                  track itself (sound on sound: the input over what the
                  track plays), RLEN = PLEN (an overdub is the pattern's
                  length, the one a free loop sets), FIN = FOUT = 0.063
                  (ladder index 1, RECORDER.md)

and in all 16 patterns of every bank: a trig on step 1 of T1-T4; recorder
trigs on step 1 of T1-T4, the input's (REC AB for T1/T2, REC CD for T3/T4)
and SRC3's. FREE LOOP lets a track's recorder trigs fire only while its
pedal has armed it. Patterns A1-A4 play Part 1 ... A13-A16 Part 4 (and so in
every bank); the Parts are alike, named LIVE<bank><part>.

An image with KITS: the empty library the fresh project carries
(kits.work / kits.strd) is removed, so KITS' first load migrates each
bank's Parts into Kits bank*4 + part (modules/kits/README.md, "First load
of a project").

freeloop.work / .strd (FREE LOOP's settings, modules/free-loop/adapter.c):
T1 and T3 FREE, T2 and T4 GRID, 4/4, BARS AUTO, 70-160 BPM, every pattern's
ENTRY KEEP; UNDO buffers T1 R5, T2 R6, T3 R7, T4 R8 (T5-T8 play samples:
their recorder buffers are free; their RECORDING SETUP is T1-T4's, which
FREE LOOP also keeps in step on the unit).

project.work: CLOCK RECEIVE off (the first free loop is the tempo's master;
ot_fresh turns it on); METRONOME_MAIN_VOLUME 10; PROG CH RECEIVE on, its
channel AUTO (ot_fresh writes 1) (FREE LOOP's
CC 83-89 on the AUTO channel, 11); DIR_AB = DIR_CD = 127 (the guitar and
the synth heard straight from the inputs: no THRU track any more). T1..T4
keep MIDI channels 1..4: their pedals are CC 90 (REC) and CC 91 (PLAY/STOP)
on those channels.

Offsets are tools/hw/ot_project.py's and ot_bank.py's (file Part record = RAM
Part + 9; recorder setup +0x60b + 12 t; slots +0x2d3 + 5 t; step masks 0x00
trig, 0x20 REC AB, 0x28 REC CD, 0x30 REC SRC3; a pattern's Part byte 5
bytes before the next PTRN tag).
"""
import argparse
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import zlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/hw"))
import ot_project as op  # noqa: E402

FLEX = 1
RLEN_PLEN = 65                    # raw: display 1..64 = raw 0..63, MAX 64, PLEN 65 (RLEN PLEN)
FADE_0063 = 1                     # FIN / FOUT ladder 0, 0.063, 0.125 ... 64 (0x400ab63a)
MASK_TRIG, MASK_REC_AB, MASK_REC_CD, MASK_REC_SRC3 = 0x00, 0x20, 0x28, 0x30
LOOPS = (0, 1, 2, 3)              # T1-T4, 0-based; each plays its own recorder buffer
GUITAR = (0, 1)                   # INAB; T3/T4 take INCD
DIR_LEVEL = 127

ROLE_GRID, ROLE_FREE = 1, 2
ROLES = (ROLE_FREE, ROLE_GRID, ROLE_FREE, ROLE_GRID, 0, 0, 0, 0)
FL_MAGIC, FL_VERSION, FL_LEN = 0x464C5057, 4, 1098
UNDO_BUFFERS = (5, 6, 7, 8, 0, 0, 0, 0)
POPUP = 0x0F                         # FREE LOOP POPUP ON for T1-T4 (FlConfig popup, bit t)


def pattern_part(pattern):
    return pattern // 4


def part_name(bank, part):
    return f"LIVE{'ABCDEFGHIJKLMNOP'[bank - 1]}{part + 1}"


def edit_bank(data, bank):
    for p in range(op.NPARTS_ALL):                          # parts 1-4 and their saved copies
        part = op.PART_BASE + p * op.PART_STRIDE
        for t in LOOPS:
            data[part + op.MTYPE_OFF + t] = FLEX
            data[part + 0x2d3 + t * 5 + op.SLOT_KIND["flex"]] = 0x80 + t
            rec = part + op.REC_SETUP_OFF + t * 12
            data[rec + op.REC_FIELDS.index("INAB")] = 1 if t in GUITAR else 0
            data[rec + op.REC_FIELDS.index("INCD")] = 0 if t in GUITAR else 1
            data[rec + op.REC_FIELDS.index("SRC3")] = 1 + t
            data[rec + op.REC_FIELDS.index("RLEN")] = RLEN_PLEN
            data[rec + op.REC_FIELDS.index("FIN")] = FADE_0063
            data[rec + op.REC_FIELDS.index("FOUT")] = FADE_0063
            undo = part + op.REC_SETUP_OFF + (UNDO_BUFFERS[t] - 1) * 12   # T5-T8: their loop track's
            data[undo:undo + 12] = data[rec:rec + 12]                    # setup (an UNDO pass's RLEN PLEN)
    for p in range(op.NPARTS):                              # ot_project.set_part_name's field
        name = part_name(bank, p)
        off = len(data) - 2 - 4 * 7 + p * 7
        data[off:off + 7] = name.encode("latin1").ljust(7, b"\0")
    for pattern in range(16):
        tail = op.PTRN0 + pattern * op.PTRN_FSTRIDE + op.PTRN_FSTRIDE
        if data[tail:tail + 4] not in (b"PTRN", b"PART"):
            sys.exit(f"make_template: pattern {pattern + 1}: no PTRN/PART tag after it")
        data[tail - 5] = pattern_part(pattern)
        for t in LOOPS:
            trac = op.trac_off(pattern, t)
            for mask in (MASK_TRIG, MASK_REC_AB if t in GUITAR else MASK_REC_CD, MASK_REC_SRC3):
                data[trac + mask + 7] |= 1                  # step 1


def freeloop_work():
    """FREE LOOP's file (adapter.c): the header, then FlConfig big-endian --
    role[8] sig[8] bars[8] popup endmute bpm_lo[8] bpm_hi[8] (u16) mode[256] (u16) ubuf[8] pmode[256] (u16)
    undoto[8]."""
    payload = (bytes(ROLES) + bytes(8) + bytes(8) + bytes((POPUP, 0)) + bytes(16) + bytes(16) + bytes(512)
               + bytes(UNDO_BUFFERS) + bytes(512) + bytes(8))   # pmode, undoto (LAST)
    assert len(payload) == FL_LEN
    head = struct.pack(">IIII", FL_MAGIC, FL_VERSION, FL_LEN, zlib.crc32(payload) & 0xFFFFFFFF)
    return head + payload


def make(image, out, name):
    out = pathlib.Path(out)
    fresh = out / "_fresh"
    r = subprocess.run([str(ROOT / ".venv/bin/python3"), str(ROOT / "tools/hw/ot_fresh.py"),
                        "--image", str(image), "--out", str(fresh)], cwd=ROOT, capture_output=True, text=True)
    src = fresh / "image" / "NOPROJ"
    if r.returncode or not (src / "project.work").is_file():
        sys.exit(f"make_template: ot_fresh failed:\n{(r.stdout + r.stderr)[-1500:]}")
    dest = out / name
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(src, dest)

    for bank in range(1, 17):
        op._bank_write(dest, bank, lambda data, bank=bank: edit_bank(data, bank), guard=False)
    for f in ("kits.work", "kits.strd"):
        (dest / f).unlink(missing_ok=True)
    for f in ("freeloop.work", "freeloop.strd"):
        (dest / f).write_bytes(freeloop_work())
    for suffix in ("work", "strd"):
        p = dest / f"project.{suffix}"
        if not p.is_file():                      # a fresh project may carry no .strd yet
            continue
        raw = p.read_bytes()
        for key, value in ((b"MIDI_PROGRAM_CHANGE_RECEIVE", 1), (b"MIDI_CLOCK_RECEIVE", 0),
                           (b"MIDI_PROGRAM_CHANGE_RECEIVE_CH", -1),
                           (b"METRONOME_MAIN_VOLUME", 10),
                           (b"DIR_AB", DIR_LEVEL), (b"DIR_CD", DIR_LEVEL)):
            raw, n = re.subn(rb"\n" + key + rb"=\d+", b"\n" + key + b"=%d" % value, raw)
            if n != 1:
                sys.exit(f"make_template: no {key.decode()} in {p.name}")
        p.write_bytes(raw)
    for f in [f"bank{b:02d}.{x}" for b in range(1, 17) for x in ("work", "strd")]:
        if not (dest / f).is_file():
            continue
        data = (dest / f).read_bytes()
        if int.from_bytes(data[-2:], "big") != (sum(data[0x10:-2]) & 0xFFFF):
            sys.exit(f"make_template: {f}: checksum did not take")
    return dest


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", default=str(ROOT / "out/mainos_bus.bin"))
    ap.add_argument("--out", default=str(ROOT / "out/templates"))
    ap.add_argument("--name", default="FREE_LOOP")
    a = ap.parse_args()
    dest = make(a.image, a.out, a.name)
    print(f"{dest}: T1-T4 FLEX on R1-R4 (T1/T2 guitar A B, T3/T4 synth C D, SRC3 = itself, RLEN PLEN); "
          f"FREE LOOP T1/T3 FREE, T2/T4 GRID; DIR AB/CD {DIR_LEVEL}; metronome MAIN 10; PROG CH RECEIVE on")
    return 0


if __name__ == "__main__":
    sys.exit(main())
