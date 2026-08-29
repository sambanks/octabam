#!/usr/bin/env python3
"""Read (and carefully write) Octatrack project/bank files on the CF card.

Format knowledge (reverse-engineered 25 Aug 2026 on ChongBongolo 26, OS 1.40B
image R58; anchors verified against values we wrote over MIDI and Sam's own
"A03 is part 3" statement):

  project.work    plain text, CRLF, [SECTION] KEY=VALUE.
                  [SAMPLE] sections: TYPE/SLOT/PATH/GAIN/... GAIN is 0..96,
                  48 = 0 dB, 0.5 dB per step (so 72 = +12 dB).
  bank##.work     FORM/DPS1BANK chunks: 16x PTRN (each 8 TRAC + 8 MTRA),
                  then 8x PART (parts 1-4 current, then parts 1-4 saved),
                  PART stride 0x18bb from 0x8eed6.
                  PART+0x009: FX1 effect id per track (8 bytes)
                  PART+0x011: FX2 effect id per track (8 bytes)
                             (BongDelay=0x06, ChonVerb=0x07, SEND=0x09)
                  PART+0x01b: 8 pairs (track LEVEL, cue level)
                  PART+0x2d3 + 5*track: static slot, 0-based (5-byte/track blocks)
                  PTRN tail byte at (next_chunk - 5): part assignment 0-3
                             (NOT -6 -- that mistake cost a measurement pass)
                  trailer: 4 part names, 7-byte NUL-terminated fields, at
                             (end - 2 - 4*7); **last u16 BE = additive checksum
                             sum(bytes[0x10:-2]) & 0xFFFF -- MUST recompute on
                             any bank edit** (verified on 4 files, 28 Aug).
                  AMP VOL: not located -- do not guess.

    python3 tools/ot_project.py report PROJECT_DIR
    python3 tools/ot_project.py set-gain PROJECT_DIR SLOT DB      # e.g. 12 -3.5
    python3 tools/ot_project.py apply PROJECT_DIR PLAN.json       # {"12": -3.5, ...}

Writes edit GAIN= lines only, preserve CRLF and byte length discipline of the
rest of the file, and refuse to run without a same-day backup directory
matching /Users/sambanks/octa/backups/*pregain*.
"""
import json, pathlib, re, sys, glob

PART_BASE, PART_STRIDE, NPARTS = 0x8eed6, 0x18bb, 4
FX_NAMES = {0x06: "BongDelay", 0x07: "ChonVerb", 0x09: "SEND", 0x00: "-"}

def read_project(pdir):
    raw = (pdir / "project.work").read_bytes().decode("latin1")
    slots = []
    for m in re.finditer(r"\[SAMPLE\](.*?)\[/SAMPLE\]", raw, re.S):
        sec = m.group(1)
        g = lambda k, d=None: (re.search(rf"{k}=(.*?)\r?\n", sec) or [None, d])[1]
        slots.append(dict(type=g("TYPE"), slot=int(g("SLOT")), path=(g("PATH") or "").strip(),
                          gain=int(g("GAIN", "48")), span=(m.start(1), m.end(1))))
    return raw, slots

def bank_info(pdir, banknum):
    data = (pdir / f"bank{banknum:02d}.work").read_bytes()
    ptrns = [m.start() for m in re.finditer(rb"PTRN", data)] + [PART_BASE]
    pat_part = [data[ptrns[i+1]-5] for i in range(16)]
    parts = []
    for p in range(NPARTS):
        c = data[PART_BASE + p*PART_STRIDE:][:PART_STRIDE]
        fx1 = list(c[0x009:0x011]); fx2 = list(c[0x011:0x019])
        levels = list(c[0x01b:0x02b:2])
        parts.append(dict(fx1=fx1, fx2=fx2, levels=levels))
    return pat_part, parts

def cmd_report(pdir):
    _, slots = read_project(pdir)
    print("== sample slots (STATIC with files) ==")
    for s in slots:
        if s["type"] == "STATIC" and s["path"]:
            db = (s["gain"] - 48) / 2
            print(f"  slot {s['slot']:3d}  gain {db:+5.1f} dB  {s['path'].split('/')[-1]}")
    for b in range(1, 9):
        pat_part, parts = bank_info(pdir, b)
        used = pat_part[:16]
        print(f"\n== bank {chr(64+b)} == pattern->part: "
              + " ".join(f"{i+1}:{pp+1}" for i, pp in enumerate(used)))
        for i, part in enumerate(parts):
            fx2 = "/".join(FX_NAMES.get(v, hex(v)) for v in part["fx2"])
            print(f"  part {i+1}: LEVELs {part['levels']}  FX2 {fx2}")

def guard_backup():
    if not glob.glob("/Users/sambanks/octa/backups/*pregain*"):
        sys.exit("no pregain backup found -- refusing to write")

def apply_gains(pdir, changes):
    guard_backup()
    path = pdir / "project.work"
    raw = path.read_bytes().decode("latin1")
    n = 0
    for slot, db in changes.items():
        val = max(0, min(96, round(48 + 2*float(db))))
        pat = rf"(\[SAMPLE\][^\[]*?TYPE=STATIC[^\[]*?SLOT={int(slot):03d}[^\[]*?GAIN=)(\d+)"
        new, k = re.subn(pat, lambda m: m.group(1) + str(val), raw, count=1, flags=re.S)
        if k != 1:
            print(f"WARN slot {slot}: no unique match, skipped"); continue
        raw = new; n += 1
        print(f"slot {int(slot):3d} -> GAIN={val} ({float(db):+.1f} dB)")
    path.write_bytes(raw.encode("latin1"))
    print(f"{n} gains written to {path}")

def _bank_write(pdir, banknum, mutate):
    """Read bank, apply mutate(bytearray), fix checksum, write."""
    guard_backup()
    path = pdir / f"bank{banknum:02d}.work"
    data = bytearray(path.read_bytes())
    mutate(data)
    ck = sum(data[0x10:-2]) & 0xFFFF
    data[-2:] = ck.to_bytes(2, "big")
    path.write_bytes(bytes(data))

def set_part_name(pdir, banknum, part, name):
    name = name.upper()[:6]
    def mut(data):
        off = len(data) - 2 - 4*7 + (part-1)*7
        field = name.encode("latin1") + b"\x00" * (7 - len(name))
        data[off:off+7] = field
    _bank_write(pdir, banknum, mut)
    print(f"bank{banknum:02d} part{part} name -> {name}")

def set_track_slot(pdir, banknum, part, track, slot_1based):
    def mut(data):
        off = PART_BASE + (part-1)*PART_STRIDE + 0x2d3 + (track-1)*5
        data[off] = slot_1based - 1
    _bank_write(pdir, banknum, mut)
    print(f"bank{banknum:02d} part{part} T{track} slot -> {slot_1based}")

if __name__ == "__main__":
    cmd = sys.argv[1]; pdir = pathlib.Path(sys.argv[2])
    if cmd == "report": cmd_report(pdir)
    elif cmd == "set-gain": apply_gains(pdir, {sys.argv[3]: sys.argv[4]})
    elif cmd == "apply": apply_gains(pdir, json.loads(pathlib.Path(sys.argv[3]).read_text()))
    elif cmd == "part-name": set_part_name(pdir, int(sys.argv[3]), int(sys.argv[4]), sys.argv[5])
    elif cmd == "track-slot": set_track_slot(pdir, int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]))
