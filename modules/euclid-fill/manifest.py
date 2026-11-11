"""EUCLID FILL -- TRACK + PAGE opens a standalone Euclidean trig-fill page.

Hold any track key and press PAGE: EUCLID Tn N (length in the title) and
a stock 3x2 dotted grid — A=PULSE B=ROT / D=DEST E=DEPTH; C and F empty.
YES writes sample trigs and locks on one chosen page-1 DEST (LFO-style
DEPTH; PTCH stays in-scale) on the held tracks (or the current track if
none were held). Only that DEST's lock bytes are touched, so fills can
be applied sequentially. Per-track params live in DRAM and in
euclid.work (STORE). CUE places a random k-subset with density PULSE.
NO or TRACK+PAGE again closes; bare PAGE does not.

Independent of PROJECT > SEQUENCER (SCALE QUANTIZER) and of the EUCLID
DSP effect. FUNC + PAGE (SCALE SETUP) stays stock.
"""

import runpy
from pathlib import Path

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof

H = bytes.fromhex

# PAGE opener prologue: lea -16(sp),sp ; movem.l d2-d4/a2,(sp)  (8 B)
PAGE = 0x4004ffc4
PAGE_STOCK = H("4feffff048d7041c")


def _sources(modules, _remix):
    ids = runpy.run_path(str(Path(__file__).parents[1] / "store/manifest.py"))["CLIENT_IDS"]
    return f".set EF_CLIENT, {ids['EUCLID FILL']}\n"


MODULE = Module(
    name="euclid-fill",
    key="EUCLID FILL",
    kind=Kind.CF_PATCH,
    category=Category.MACHINES,
    author="ilia-murzinov",
    author_url="https://github.com/ilia-murzinov",
    proof=Proof.CHECK,
    proof_note="DEST/DEPTH + per-track slots + euclid.work STORE client build "
               "and gate under the port; open/track/select HW-confirmed on "
               "CX EUCL14 (9 Nov 2026) — persistence not yet unit-confirmed.",
    doc="TRACK + PAGE: Euclidean sample-trig fill (title Tn N; 3x2 grid "
        "A/B/D/E = PULSE/ROT/DEST/DEPTH, C/F empty; CUE = random k-subset; "
        "DEST = LFO PMTR targets (0..29 page-1, skip XVOL; CX 30..34 "
        "CAR/MOD/SYMM/FDBK/PWM); DEPTH = LFO-style amount (AMP VOL unipolar "
        "below Part VOL); PTCH stays "
        "in-scale; YES touches only that DEST so fills stack; track select "
        "switches slots; euclid.work persists the bank).",
    linked=(Linked("ef", "modules/euclid-fill/euclid_fill.s", dram=True,
                   include=_sources),),
    detours=(
        Detour(PAGE, PAGE_STOCK, "ef", "ef_page",
               "PAGE: with a track held, toggle the Euclid fill window",
               pad_to=8),
    ),
    requires=("STORE",),
    gates=(Gate("tools/verify/verify_euclid_fill.py", venv=True, stage="image"),),
)
