"""SELECT PROBE -- read back the byte our select-array formula addresses.

WHAT IT SETTLES. `docs/MAINMENU.md` 9c-ii decoded where a page-2 SELECT's
value lives -- `DB + part*6322 + 0x8f04a + track*30 + page*6 + slot` -- and
drove the firmware's own two-phase editor into writing that array. But on a
machine with no project loaded the write landed at offset ZERO, so the
track, page and slot terms are decoded and UNCONFIRMED. Three separate
attempts to confirm them locally hit the same wall: the emulator boots with
no CF card, so the project database and everything hanging off it is empty.

This settles it from the other side, on hardware, and writes nothing. It
PRINTS the byte the formula addresses. Turn a page-2 select on the panel:
if this number follows it, the formula is right; if it does not, the value
shown says how far off it is.

HOW TO READ IT -- fourth build, designed around how the panel behaves. A
knob's value is shown ONLY WHILE IT TURNS, so the readout is visible only
while GAIN moves; GAIN is also what picks the row, so the row bands are TEN
values wide and a wiggle stays inside one. GAIN 0-59 reads FX1 (page 3),
60-119 reads FX2 (page 4), ten values per slot. The number is
`byte*100 + page*10 + slot`: hundreds = the byte, tens = page, units = slot.
FX1's MODE (page 3, slot 1) therefore reads 31, 131, 231, 331 or 431 for
its five positions. `-` means no project.

Three flashes went into learning that: build 80 read a page nothing in the
image could turn; build 81 put the byte in the last digit and needed GAIN
wiggled to refresh, which moved the row; build 82 added a "refresh" knob
that could not refresh anything, because a turning knob redraws only its
own label. This one reads while GAIN wiggles inside a wide band, on BOTH
FX pages, with the byte leading.

⚠️ MUTUALLY EXCLUSIVE WITH `modules/cfprobe`: both register on HELLO
WORLD's GAIN. `remixes/selprobe.py` carries this one alone.

⚠️ READ-ONLY BY CONSTRUCTION, and that is deliberate. A formatter runs
inside a redraw, and the firmware's select editor ENDS in redraw calls, so
a probe that invoked it would re-enter the drawing code. This one calls
nothing and stores nothing but the caller's sprintf buffer.
"""

from remix.schema import CavePatch, FormatterReg, Kind, Module

PROBE_BYTES = bytes.fromhex(
    "4feffff048d7001c202f00187277b2806c0220017803723bb2806c0804800000"
    "003c7804720a4c4100002400263946c82456677070001039100b14cf223c0000"
    "18b24c010000d68070001039100b14cc721e4c010000d68006830008f04a2004"
    "72064c010000d680d68220437200121070644c0010002004760a4c030000d280"
    "d28220014cd7001c4fef00102f004879400b465d2f2f000c4eb940013a084fef"
    "000c4e754cd7001c4fef0010487a00102f2f00084eb940013a08508f4e752d00"
)

MODULE = Module(
    name="selprobe",
    key="SELECT PROBE",
    kind=Kind.CF_PATCH,
    doc="Prints the page-2 select byte our formula addresses, to confirm it "
        "on hardware.",
    cf_patches=(
        CavePatch(
            label="select probe cave",
            cave_addr=None,               # floats: pc-relative, OS absolutes
            pinned=PROBE_BYTES,
            source="modules/selprobe/selprobe.s",
            registers_formatter=FormatterReg(module="HELLO WORLD", slot=0),
            report_note=" (HELLO WORLD GAIN: 0-59 FX1, 60-119 FX2, ten per "
                        "slot; prints byte*100 + page*10 + slot)",
        ),
    ),
)
