"""MORPH -- [TRACK]+[UP] / [TRACK]+[DOWN]: a track's scene morph (A -> B -> A) runs by itself.

A morphing track's A/B weight comes from a triangle of one cycle = STEPS x x sequencer 16th steps
(default 16 x 8 = 128; STEPS 0 = the track's length), counted on the sequencer's step word, always
starting on scene A on the step after the keys, instead of from the crossfader; the other tracks
keep the crossfader. MODE SMOOTH or TRIG HOLD. [TRACK]+[DOWN] lets the cycle finish on A and parks
the track there until the crossfader reaches its A end. Inspired by the Korg Electribe's Motion
Sequence. [TRACK]+[UP] opens the window (A STEPS, B x 1..100, C MODE, the stock scene indicator);
it stays open: YES starts the held tracks on the next step, NO closes and starts nothing. Either
way they are ARMED: a track key held ~1 s alone then starts and stops that track's morph (the long
press, v1.1). v1.2: encoders D, E, F set the way back per track: RET (SAME, 1/2 .. 1/16 of the
way up, BAR, BEAT, STEP, CUT), CURV (LIN, HAND, RISE, BOTH) and END (LOOP, ONCE, STAY: held on B
until the long press or [TRACK]+[DOWN], then back over RET); all at their first value = v1.1. The
settings, which tracks morph and which are ARMED are saved with the project in morph.work (a STORE
client, modules/store; version 3 only when a v1.2 setting is used).

Sites, measured from the user's 1.40C (base 0x40000400; modules/morph/README.md):
  * the frame builder at 0x4000cc62 (`move.l #96,%macsr ; lea 12(%sp),%sp`, 10 bytes): once a
    frame, after the per-track loop and before 0x4000cc6c, where every path that reads the
    per-track weights 0x80003c60.. starts. No branch in the image lands inside the 10 bytes.
  * the [TRACK]-held key layer 0x400d164a: its keys field 0x400d164e (stock 0x400d1594) points at
    the unit's copy of the stock table with UP (0x33) and DOWN (0x20) added. Beside
    REC_TRIG_MUTE, which repoints stock's YES/NO records, HOOKS owns the field instead and its
    table carries both (modules/hooks, track_key); MORPH's own copy is then not read. YES and NO
    inside the open window are the window's own layer (MW_KEYS), not this one.
  * the long press: the PRESS field of T1..T8 in the MKI key table 0x400bfc10 and the MKII one
    0x400c01f4 (stock 0x40040250) points at lp_tpress, which calls stock first (TRACK MENU's site,
    measured on the owner's MKI, 24 Oct 2026). Not a HOOKS bridge.
"""

import os

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Evidence, Level, SymbolRef

H = bytes.fromhex
_HERE = os.path.relpath(os.path.dirname(os.path.realpath(__file__)))

FRAME_HOOK = 0x4000CC62
FRAME_STOCK = H("a93c00000060" "4fef000c")          # move.l #96,%macsr ; lea 12(%sp),%sp
KEYS_FIELD = 0x400D164E                              # the [TRACK]-held layer's keys pointer
KEYS_STOCK = 0x400D1594                              # 6 records + the 0xff terminator

STOCK_TKEY = 0x40040250
TABLES = (("MKI", 0x400BFC10, 2), ("MKII", 0x400C01F4, 2))   # index of the T1 record in each


def _press_fields():
    """The PRESS field of T1..T8 in both key tables (records 0x1a bytes, code at +0, press at +2;
    the T1 record is the third of each: 0x400bfc44 and 0x400c0228), measured for TRACK MENU on the
    owner's 1.40C (24 Oct 2026) and run on his MKI."""
    refs = []
    for name, table, first in TABLES:
        for t in range(8):
            addr = table + (first + t) * 0x1A + 2
            refs.append(SymbolRef(addr, STOCK_TKEY, "morph", "lp_tpress",
                                  f"{name} key table, T{t + 1} press: the stock handler, then MORPH's long press"))
    return tuple(refs)


MODULE = Module(
    name="morph",
    key="MORPH",
    kind=Kind.CF_PATCH,
    category=Category.PARTS,
    author="MaMarko",
    author_url="https://github.com/braikomarko-hub",
    doc=("Hold a track key and press UP: the window; YES and from the next step that track's scene "
         "morph runs by itself, A -> B -> A over STEPS x x steps, starting on A; the other tracks keep "
         "the crossfader. Then the track key held ~1 s turns it on and off. Track + DOWN finishes the "
         "cycle on A and parks the track there until the crossfader reaches A. D, E, F: how it comes "
         "back (RET, CURV) and whether it loops, plays once or stays on B (END). Settings saved with "
         "the project. Inspired by the Korg Electribe's Motion Sequence."),
    evidence=(Evidence(Level.UNIT, unit="MKI", who="MaMarko", date="2026-10-23",
        note="image MRPPR1 (BUILD 98, remix morph), 23 Oct 2026: the window, the start on the release, x to 16 and"
             " 41.625, saving (SAVE PROJECT, power cycle, RELOAD, another project and back), stop and parking on "
             "A; before, inside aCiDtRacK (ACIDV74MP, 22 Oct): several tracks at once, SMOOTH and TRIG HOLD"),
        Evidence(Level.UNIT, unit="MKI", who="MaMarko", image="aCiDtRacK ACIDV91..ACIDV97", date="2026-11-22",
                 note="v1.1 (the window stays open, YES / NO, the long press, x to 100, the scene indicator) in "
                      "the owner's live sets with OCTA303: risers over STEPS x x while the rest is prepared"),
        Evidence(Level.BUILD, who="MaMarko", date="2026-11-22", ref="tools/morph/test_morph.py",
                 note="v1.2 (RET, CURV, END on D, E, F): 152 checks in the source simulator (cfsim), every v1.1 "
                      "check unchanged with the defaults; not yet under the port or on the unit"),),
    linked=(
        Linked("morph", os.path.join(_HERE, "morph.s"), dram=True),
    ),
    detours=(
        Detour(FRAME_HOOK, FRAME_STOCK, "morph", "morph_frame",
               "frame builder, before the scene morph reads the per-track weights: write each "
               "morphing or parked track's weight", kind="jmp", pad_to=10),
    ),
    symbol_refs=(
        SymbolRef(KEYS_FIELD, KEYS_STOCK, "morph", "mp_keys",
                  "[TRACK]-held key layer: the stock table plus UP (MORPH ON) and DOWN (MORPH STOP)"),
    ) + _press_fields(),
    requires=("STORE",),
    gates=(
        Gate("tools/morph/test_morph.py", remix_arg=False),
    ),
)
