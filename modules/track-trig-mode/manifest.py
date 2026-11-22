"""TRACK TRIG MODE -- each audio track keeps its own CHROMATIC / SLOTS /
SLICES trig mode, saved with the project.

Pick CHROMATIC, SLOTS or SLICES (FUNC + UP / DOWN) on a track and that
track keeps it: changing track shows the new track's own mode. TRACKS,
QUICK MUTE and DELAY CONTROL stay global -- picked, they show on every
track until another mode is picked; stepping out of one lands on the
track's own mode and never overwrites it. A track that never had a mode
picked takes whatever is showing.

The modes are saved in project.work as a comment line in [SETTINGS],
"#TRIG_MODES=dddddddd" (T1..T8; 0 unset, 1 CHROMATIC, 2 SLOTS, 3 SLICES).
Stock skips '#' lines and refuses a project with an unknown key (-51), so
a comment keeps the project loading on stock firmware.

The table is 8 bytes of battery RAM (CS1 0x100f85e8, between KITS' and
P2 LOCKS' claims; stock never touches 0x100f859c..0x100fff00 but its
whole-CS1 init): a power-up restores the project from CS1 and does not
parse project.work, so a DRAM table came back empty (27 Oct 2026, MKI).

Seven detours (trigmode.s), sites read from the disassembly of 1.40C:
  0x40051f18 / 0x40051f88  FUNC + DOWN / UP: the store of the new mode
  0x40083c3a  audio track select (0x40083bf8), after the track is stored
  0x40084d66  after the load's bank read (project load and power-up): show
              the current track's own mode
  0x40088da0  project writer: before "[/SETTINGS]"
  0x400866c4  project parser entry: an applying parse forgets the modes
  0x400867a2  project parser: each line's first-character test
"""

import dataclasses

from remix.schema import Category, Claims, Detour, Gate, Kind, Linked, Module, Override, Proof

H = bytes.fromhex

MODULE = Module(
    name="track-trig-mode",
    key="TRACK TRIG MODE",
    kind=Kind.CF_PATCH,
    category=Category.MACHINES,
    author="Hteah",
    author_url="https://github.com/Hteah",
    proof=Proof.PORT,
    proof_note="verify_track_trig_mode: per-track modes on track change, the "
               "project line written and read back, a power cycle (CS1 kept), under the port",
    doc="Each audio track keeps its own CHROMATIC / SLOTS / SLICES trig mode, "
        "saved with the project.",
    linked=(Linked("tmode", "modules/track-trig-mode/trigmode.s", dram=True),),
    detours=(
        Detour(0x40051f18, H("23d0460d16f0"), "tmode", "tm_down",
               "FUNC + DOWN: keep a CHROMATIC / SLOTS / SLICES pick for the track"),
        Detour(0x40051f88, H("23d0460d16f0"), "tmode", "tm_up",
               "FUNC + UP: keep a CHROMATIC / SLOTS / SLICES pick for the track"),
        Detour(0x40083c3a, H("4eb940097460"), "tmode", "tm_trk",
               "audio track select: show the new track's own mode"),
        Detour(0x40084d66, H("4fef00104a80"), "tmode", "tm_boot",
               "project load / power-up, after the bank read (KITS reads that call's "
               "return address): show the current track's own mode"),
        Detour(0x40088da0, H("4879400b84c2"), "tmode", "tm_save",
               "project writer: the #TRIG_MODES= line before [/SETTINGS]"),
        Detour(0x400866c4, H("4feffa4448d77cfc"), "tmode", "tm_load",
               "project parser entry: an applying parse forgets the modes", pad_to=8),
        Detour(0x400867a2, H("122f048f7101"), "tmode", "tm_line",
               "project parser: read the #TRIG_MODES= line"),
    ),
    select=lambda keys: _select(keys),
    claims=Claims(sram=((0x100F85E8, 8, "TRACK TRIG MODE: each audio track's trig mode"),)),
    gates=(Gate("tools/verify/verify_track_trig_mode.py", venv=True, stage="image"),),
)


# SCALE QUANTIZER reads its own '#' lines with an 8-byte jmp at the same
# parser site 0x400867a2 (8thmyth, 16 Nov 2026, octabam main's octabam
# remix carries it). With it selected this module takes the site: its
# detour writes the same 8 bytes, tm_line reads #TRIG_MODES= and hands
# every other line to qz_ld_line (TM_QZ). Its loader-entry hook at
# 0x400866cc is the join of tm_load's at 0x400866c4: those two chain as
# they are.
_QZ = "SCALE QUANTIZER"


def _select(keys):
    if _QZ not in keys:
        return {}
    unit = dataclasses.replace(MODULE.linked[0], defsyms=(("TM_QZ", 1),))
    detours = tuple(
        Detour(d.site, H("122f048f71017a23"), d.unit, d.symbol,
               d.note + "; other lines on to SCALE QUANTIZER's qz_ld_line", pad_to=8)
        if d.site == 0x400867A2 else d
        for d in MODULE.detours)
    return {"linked": (unit,), "detours": detours, "overrides": (Override(0x400867A2, _QZ),)}
