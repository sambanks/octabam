"""M6e: build a project with a track's machine set to a recorder (PICKUP1),
the fixture RTOS_FORK.md section 9.4 and EMU.md's M5 section both flagged
as missing -- neither REC-arm nor a recorder-type trig had ever been
exercised because no such project existed.

Usage:
    cp -R <a real project dir> out/_recproj
    .venv/bin/python3 tools/scratch/make_recorder_testproj.py out/_recproj

Patches bank02.work (the bank `out/_testproj`'s BANK=1 project setting
selects) in place: track 1's machine-type byte, part 1 (current) and part 5
(its saved mirror -- ot_project.py's "eight part records, not four" note),
2 -> 4 (PICKUP1). Nothing else changes -- track 1 keeps its existing trig
(pattern 1 step 2, the one M6c/M6d's fidelity gate already fires at frame
344, byte 0xd3 cold), so `press_play_live()` + `poke_trig(2)` is enough to
exercise it; no on-disk trig-mask edit needed.

File-offset math (RAM offsets from EMU.md/EXTERNAL.md section 6, cross-
checked against tools/ot_project.py's FX1_OFF/FX2_OFF, both file offsets
exactly 9 higher than their RAM-relative ones -- a 9-byte IFF chunk header,
tag+len+pad, per PART chunk):

    RAM   machine-type byte = PART_PTR + part*0x18b2 + 0x8eda2 + track
    file  machine-type byte = PART_BASE + part*PART_STRIDE + 0x2b + track
          (PART_BASE=0x8eed6, PART_STRIDE=0x18bb, matching ot_project.py)

Verified 6 Sep 2026 by loading the patched project through the real M6b
LOAD PROJECT path and reading the RAM byte back: all 8 tracks' machine
types read [4, 2, 0, 0, 0, 0, 0, 1] where the source project read
[2, 2, 0, 0, 0, 0, 0, 1] -- only track 1 changed, exactly as patched.

What changed, measured against `press_play_live()` + `poke_trig(2)` + 400
frames: the ordinary FW_LIVE_NIBBLE write (0x46104d15[track], the one that
lands at frame 344 byte 0xd3 for every other machine type) DISAPPEARS
entirely for a PICKUP-type track -- confirms ARCHITECTURE.md's "trig -> voice
dispatched by machine type" claim, the first empirical sign machine type 4
takes a genuinely different runtime path. What's still open: watch_calls on
every candidate arm/record function this session could name from
docs/EXTERNAL.md section 6 and docs/ARCHITECTURE.md (FUN_400977cc
0x400977cc, FUN_40097168 0x40097168, the recorder TRIG branch 0x40083544,
the QREC scheduler FUN_40005178 0x40005178, the arm caller 0x40005ff0, and
even the per-frame trig gate 0x4000b800 EMU.md's M5 section names) logged
ZERO calls for this trig in a 400-frame window -- including 0x4000b800 on
the UNMODIFIED project's own successful trig, so that address is not
reached via `jsr` the way EMU.md assumed, independent of the recorder
question. The real per-step machine-type branch point is still unlocated;
whatever it is, it isn't reached by simply flipping the raw machine-type
byte with no other per-track field changed -- a PICKUP machine likely also
needs a recorder buffer (object id 128-135, EXTERNAL.md section 6) assigned
to it, the way a STATIC track needs a sample slot (ot_project.py's
`set_track_slot`), and that assignment field has not been located yet.
"""
import pathlib
import sys

PART_BASE, PART_STRIDE = 0x8eed6, 0x18bb
MTYPE_OFF = 0x2b  # + track (0-based)
PICKUP1 = 4


def patch(pdir, bank=2, track=1, part=1, mirror_part=5):
    path = pathlib.Path(pdir) / f"bank{bank:02d}.work"
    data = bytearray(path.read_bytes())
    for p in (part, mirror_part):
        off = PART_BASE + (p - 1) * PART_STRIDE + MTYPE_OFF + (track - 1)
        old = data[off]
        data[off] = PICKUP1
        print(f"bank{bank:02d} part{p} T{track}: machine type {old} -> {PICKUP1} "
              f"(file offset {off:#x})")
    ck = sum(data[0x10:-2]) & 0xFFFF
    data[-2:] = ck.to_bytes(2, "big")
    path.write_bytes(bytes(data))
    print(f"checksum -> {ck:#06x}, written")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} <project dir already copied there>")
    patch(sys.argv[1])
