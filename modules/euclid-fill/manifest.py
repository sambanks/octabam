"""EUCLID FILL -- TRACK + PAGE opens a standalone Euclidean trig-fill page.

Hold any track key and press PAGE: a window with STEPS / PULSE / ROT /
RAND VEL / RAND PTCH. STEPS is the pattern (or PER-TRACK) length — not editable.
Encoder A = PULSE, B = ROT, C = RAND VEL, D = RAND PTCH. YES writes sample trigs
(and optional AMP VOL / in-scale PTCH locks) on the held tracks (or the
current track if none were held when the window opened). CUE places a
random k-subset with density PULSE. NO or TRACK+PAGE again closes.

Independent of PROJECT > SEQUENCER (SCALE QUANTIZER) and of the EUCLID
DSP effect. FUNC + PAGE (SCALE SETUP) stays stock.
"""

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof

H = bytes.fromhex

# PAGE opener prologue: lea -16(sp),sp ; movem.l d2-d4/a2,(sp)  (8 B)
PAGE = 0x4004ffc4
PAGE_STOCK = H("4feffff048d7041c")

MODULE = Module(
    name="euclid-fill",
    key="EUCLID FILL",
    kind=Kind.CF_PATCH,
    category=Category.MACHINES,
    author="iliamurzinov",
    author_url="https://github.com/iliamurzinov",
    proof=Proof.CHECK,
    proof_note="builds and boots under the port; fill math gated in verify_euclid_fill",
    doc="TRACK + PAGE: Euclidean sample-trig fill (STEPS=pattern len / PULSE / ROT / RAND VEL / RAND PTCH; CUE = random k-subset; RAND VEL/RAND PTCH = optional VOL/PTCH locks).",
    linked=(Linked("ef", "modules/euclid-fill/euclid_fill.s", dram=True),),
    detours=(
        Detour(PAGE, PAGE_STOCK, "ef", "ef_page",
               "PAGE: with a track held, toggle the Euclid fill window",
               pad_to=8),
    ),
    gates=(Gate("tools/verify/verify_euclid_fill.py", venv=True, stage="image"),),
)
