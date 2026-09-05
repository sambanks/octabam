"""CC -> FX2 PAGE-2 (shipped ... UNFLASHED).

Stock incoming CC reaches only FX2 page 1 (CC 40-45; the handler admits
cc-16 < 30, so slots 6-11 are unrepresentable -- docs/midi_re_cc.md 2). This
module adds CC 62-67 -> the host bus engine's page-2 slots 6-11, so the
voicing round can drive every control of BusVerb / BusDelay over MIDI, not
just page 1.

HOW: the MIDI dispatch table 0x400d6474[0xB] (the CC vector) is repointed
from the stock handler 0x4000e79c to the cave. The cave reads the CC number;
anything but 62-67 tail-calls stock (jmp 0x4000e79c) with the argument
intact, so no stock CC behaviour changes. For 62-67 it rebuilds the
channel->track map, gates on AUDIO CC IN, and writes page-2 slot (cc-62) on
every audio track whose trig channel matches -- Part, live byte and mirror,
count-clamped, generalised over track. It does NOT call the page-2 editor
0x4003a474 and does NOT touch TRACKB: that editor writes the same live byte +
mirror directly and nothing in 0x40171xxx (traced 5 Sep 2026,
docs/midi_re_cc.md), so a direct write reproduces its stores without the
cross-task TRACKB race.

The clamp is mandatory: a select's over-count value becomes the stored index
that stalls the sequencer (CLAUDE.md). Counts come from the same per-engine
select layout the busscreen uses (VERB/DLY page-2 selects at slots 6/9/11).

tools/verify_ccpage2.py (in make check) re-assembles cc_page2.s, compares it
to the pinned code, and proves the write for all eight tracks in the
emulator against the firmware editor 0x4003a474.
"""

import pathlib

from remix.schema import CavePatch, Kind, Module

# Page-2 clamp counts, slot2 order (slots 6..11). Selects carry their real
# count; knobs are 128 (0..127). Must match modules/busverb / modules/busdelay
# and the busscreen's VERB_SELECTS/DLY_SELECTS ({6,9,11}).
VERB_COUNTS = bytes((3, 128, 128, 4, 128, 4))   # MODE, SHMR, DIFF, SHFT, GATE, RATE
DLY_COUNTS = bytes((3, 128, 128, 4, 128, 2))    # MODE, MRAT, SIZE(select), DRV, FRZE

# The CC dispatch vector (status>>4 == 0xB) and its stock target.
DISPATCH_CC = 0x400d64a0
STOCK_CC = 0x4000e79c

# cc_page2.s assembled with m68k-elf-as -mcpu=5407; the two count-table
# references are placeholders 0x40bad000 (VCOUNT) / 0x40bad004 (DCOUNT) that
# emit() rewrites to the tables it appends. verify_ccpage2 re-assembles the
# source and compares, so drifted source cannot pass unnoticed.
CODE = bytes.fromhex(
    "206f000470001028000104800000003e7205b280650260064ef94000e79c4fefffe4"
    "48d704fc280024487a001a2a000202850000007f263946104cf44eb94000185410398000"
    "004902800000000167287000101202800000000f41f946c7febe2e300c007c007001eda8"
    "c0876702611252867008b0866eee4cd704fc4fef001c4e7541f980000ecc700010306800"
    "7206b28067107207b28067024e7543f940bad000600643f940bad00472001231480053812405"
    "b4816f022401203946c824567200123980000003263c000018b24c031000d0812040d1fc0008"
    "ef5a2206761e4c031000d1c1d1fc00000012d1c410822040d1fc0008f084d1c1d1fc00000006"
    "d1c41082220676484c03100041f980000810d1c1d1fc00000020d1c410822206761e4c031000"
    "41f9100a50c0d1c1d1c410824e75")

VCOUNT_MARK = bytes.fromhex("40bad000")
DCOUNT_MARK = bytes.fromhex("40bad004")


def emit(addr):
    """Cave = code, then the two 6-byte count tables. The code carries the
    tables' placeholders; patch them to the appended tables' addresses."""
    code = bytearray(CODE)
    vcount_at = addr + len(code)
    dcount_at = vcount_at + len(VERB_COUNTS)

    for mark, target in ((VCOUNT_MARK, vcount_at), (DCOUNT_MARK, dcount_at)):
        i = code.find(mark)
        assert i >= 0, "placeholder %s missing" % mark.hex()
        assert code.find(mark, i + 4) < 0, "placeholder %s not unique" % mark.hex()
        code[i:i + 4] = target.to_bytes(4, "big")

    blob = bytes(code) + VERB_COUNTS + DLY_COUNTS
    pokes = ((DISPATCH_CC, STOCK_CC.to_bytes(4, "big"), addr.to_bytes(4, "big")),)
    return blob, pokes


MODULE = Module(
    name="ccpage2",
    key="CC PAGE 2",
    kind=Kind.CF_PATCH,
    doc="MIDI CC 62-67 drive the host bus engine's FX2 page-2 slots 6-11.",
    cf_patches=(CavePatch(
        label="CC->FX2 page-2 cave + dispatch repoint",
        # FLOATS in the decoded ColdFire free region, like the busscreen.
        cave_addr=None,
        pinned=b"",                     # bytes depend on the float address
        source="modules/ccpage2/cc_page2.s",
        emit=emit,
        report_note=" (CC 62-67 reach FX2 page 2)",
    ),),
)
