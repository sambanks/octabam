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

HOW TO READ IT. The readout is HELLO WORLD's GAIN, and GAIN's own value
picks which of the six page-2 slots is shown, so one knob reads the whole
block: 0-20 is slot 0, then 21 per slot up to slot 5. The number printed is
`slot * 256 + value`, so the slot is always visible beside the byte and a
mis-set knob cannot be mistaken for a wrong formula. `-` means no project.

⚠️ MUTUALLY EXCLUSIVE WITH `modules/cfprobe`: both register on HELLO
WORLD's GAIN. `remixes/selprobe.py` carries this one alone.

⚠️ READ-ONLY BY CONSTRUCTION, and that is deliberate. A formatter runs
inside a redraw, and the firmware's select editor ENDS in redraw calls, so
a probe that invoked it would re-enter the drawing code. This one calls
nothing and stores nothing but the caller's sprintf buffer.
"""

from remix.schema import CavePatch, FormatterReg, Kind, Module

PROBE_BYTES = bytes.fromhex(
    "4feffff048d7001c202f001872154c4100007205b2806c0220012400263946c8"
    "2456675e70001039100b14cf223c000018b24c010000d68070001039100b14cc"
    "721e4c010000d68006830008f04a068300000018d6822043720012102002e188"
    "d0814cd7001c4fef00102f004879400b465d2f2f000c4eb940013a084fef000c"
    "4e754cd7001c4fef0010487a00102f2f00084eb940013a08508f4e752d000000"
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
            report_note=" (HELLO WORLD GAIN prints slot*256 + the select "
                        "byte at DB+0x8f04a + track*30 + 24 + slot)",
        ),
    ),
)
