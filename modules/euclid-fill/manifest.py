"""EUCLID FILL -- TRACK + PAGE opens a standalone Euclidean trig-fill page.

Hold any track key and press PAGE: title EUCLID, LEN gutter, stock 3x2
grid A=PULSE B=ROT C=LANE / D=DEST E=DEPTH (F empty). LANE focuses TRIG
or PLOCK; YES writes sample trigs and DEST locks (write-only — never
re-reads live trigs). Per-track / per-DEST params in euclid.work (STORE).
CUE places a random k-subset with density PULSE. NO or TRACK+PAGE closes;
bare PAGE does not.

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
    proof=Proof.HARDWARE,
    proof_note="author's MKII, CX EUCL92, 11 Nov 2026: dual LANE TRIG/PLCK, "
               "write-only bake, LOCK_COLL + floor, PLCK YES overwrites "
               "TRIG-baked DEST on note trigs; also verify_euclid_fill.",
    doc="TRACK + PAGE: Euclidean sample-trig + p-lock fill (title EUCLID; "
        "A/B=PULSE/ROT of focused LANE, C=TRIG|PLCK, D/E=DEST/DEPTH; "
        "CUE = focused-lane random k-subset; DEST = LFO PMTR 0..29 + CX "
        "30..34; per-DEST depth/plock + per-track LANE in euclid.work; "
        "write-only — YES overwrites, never re-reads live trigs).",
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
