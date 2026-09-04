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
picks BOTH the page and the slot -- `slot = value mod 6`, `page = value div
6` -- so one knob reads the whole parameter space: 0-5 is page 0, 6-11 page
1, 12-17 page 2, **18-23 page 3 (FX1)**, **24-29 page 4 (FX2)**, and
anything above 29 pins to page 4 slot 5. The number printed is **`byte * 256 + page * 16 + slot`** -- the BYTE
LEADS, because printed the other way round a MODE step moved the number by
one in five digits (12544 to 12545) and was unreadable on the unit. A MODE
step is now a jump of 256. The row is still in the last two digits, so a
knob that slipped is still distinguishable from a byte that changed. `-`
means no project.

⚠️ **REFRESH WITH HELLO WORLD'S SECOND KNOB, `RDRW`, NOT WITH GAIN.** A
formatter runs only when the page redraws, and GAIN's value is what selects
the row -- so wiggling GAIN to force a redraw MOVES WHAT YOU ARE LOOKING AT.
That made the first hardware attempt unreadable: "it did not move" could not
be told from "I could not see it move". `RDRW` changes no audio and exists
purely to redraw the page with GAIN untouched.

⚠️ THE FIRST BUILD READ FX2 ONLY, and shipped in an image that HIDES every
effect with an FX2 page-2 select -- so there was nothing on the unit to turn
and nothing the probe could ever see move. The stations on FX1 do have
selects (Spectrum's MODE, ROUT and SRC), which is why the page is now part
of what the knob chooses rather than an assumption baked into the cave.

⚠️ MUTUALLY EXCLUSIVE WITH `modules/cfprobe`: both register on HELLO
WORLD's GAIN. `remixes/selprobe.py` carries this one alone.

⚠️ READ-ONLY BY CONSTRUCTION, and that is deliberate. A formatter runs
inside a redraw, and the firmware's select editor ENDS in redraw calls, so
a probe that invoked it would re-enter the drawing code. This one calls
nothing and stores nothing but the caller's sprintf buffer.
"""

from remix.schema import CavePatch, FormatterReg, Kind, Module

PROBE_BYTES = bytes.fromhex(
    "4feffff048d7001c202f0018721db2806c02200172064c410000262f0018721d"
    "b2836c02260172064c4130032803220376064c031000242f0018761db6826c02"
    "24039481263946c82456676670001039100b14cf223c000018b24c010000d680"
    "70001039100b14cc721e4c010000d68006830008f04a200472064c010000d680"
    "d6822043720012102001e988d084e988d0824cd7001c4fef00102f004879400b"
    "465d2f2f000c4eb940013a084fef000c4e754cd7001c4fef0010487a00102f2f"
    "00084eb940013a08508f4e752d000000"
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
            report_note=" (HELLO WORLD GAIN picks page+slot and prints "
                        "byte*256 + page*16 + slot; RDRW refreshes)",
        ),
    ),
)
