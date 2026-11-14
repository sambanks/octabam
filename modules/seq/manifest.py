"""SEQ -- TRACK + PAGE opens a Euclidean sample-trig + p-lock window.

Hold a track key and press PAGE: title SEQ, LEN gutter, stock 3x2 grid
A=PULSE B=ROT C=LANE / D=DEST E=DEPTH (F empty). LANE focuses TRIG or
PLOCK; YES writes sample trigs and DEST locks (write-only - never
re-reads live trigs). Per-track / per-DEST params in euclid.work (STORE).
CUE hold is stock; bare CUE release places a random k-subset with density
PULSE; CUE+TRACK cues that track. TRACK keys forward to stock (QUICK
ASSIGN, mute, PLAY/STOP/BANK) then retarget SEQ. FUNC+BANK opens a clear
LISTPOP over SEQ (CLEAR DEST / ALL DEST / ALL+TRIGS). NO closes and
restores SEQ; bare PAGE does not.

Independent of PROJECT > SEQUENCER (SCALE QUANTIZER) and of the EUCLID
DSP effect. FUNC + PAGE (SCALE SETUP) stays stock.
"""

import runpy
from pathlib import Path

from remix.schema import (
    Category, Detour, Gate, Kind, Linked, Module, Proof, SymbolRef,
)

H = bytes.fromhex

# PAGE opener prologue: lea -16(sp),sp ; movem.l d2-d4/a2,(sp)  (8 B)
PAGE = 0x4004ffc4
PAGE_STOCK = H("4feffff048d7041c")

# FUNC+BANK / TRACK TRIG EDIT (PARTS.md MKI 0x40058a64; MKII opens via
# 0x4007c0d0). BRAIN SymbolRefs the MKII FUNC keys pointer to a DRAM clone
# (brain_func_keys), so a ROM press patch at 0x400bf7fe never runs on CX —
# Detour the handler. MKI ROM table SymbolRef still covers non-BRAIN remixes.
FUNC_BANK_PRESS_MKI = 0x400bf4a4
FUNC_BANK_STOCK_MKI = 0x40058a64
MKII_TRIG_EDIT = 0x4007c0d0
MKII_TRIG_EDIT_STOCK = H("60ee00004ab9460e")  # bra.b 0x4007c0c0; ...


def _sources(modules, _remix):
    ids = runpy.run_path(str(Path(__file__).parents[1] / "store/manifest.py"))["CLIENT_IDS"]
    return f".set EF_CLIENT, {ids['SEQ']}\n"


MODULE = Module(
    name="seq",
    key="SEQ",
    kind=Kind.CF_PATCH,
    category=Category.MACHINES,
    author="ilia-murzinov",
    author_url="https://github.com/ilia-murzinov",
    proof=Proof.PORT,
    proof_note="verify_seq, verify_seq_func_bank and verify_seq_scenarios: "
               "MKII clear menu, dialog ordering, lock writes and stock "
               "TRACK/CUE gestures under the port. Current changes not flashed.",
    doc="TRACK + PAGE: Euclidean sample-trig + p-lock window (title SEQ; "
        "A/B=PULSE/ROT of focused LANE, C=TRIG|PLCK, D/E=DEST/DEPTH; "
        "CUE = focused-lane random k-subset; DEST = LFO PMTR 0..29 + CX "
        "30..34; per-DEST depth/plock + per-track LANE in euclid.work; "
        "write-only - YES overwrites, never re-reads live trigs).",
    linked=(Linked("ef", "modules/seq/seq.s", dram=True,
                   include=_sources),),
    detours=(
        Detour(PAGE, PAGE_STOCK, "ef", "ef_page",
               "PAGE: with a track held, open the SEQ window",
               pad_to=8),
        Detour(MKII_TRIG_EDIT, MKII_TRIG_EDIT_STOCK, "ef", "ef_fb_mkii",
               "MKII FUNC+BANK / TRACK TRIG EDIT: clear LISTPOP while SEQ open",
               pad_to=8),
    ),
    symbol_refs=(
        SymbolRef(FUNC_BANK_PRESS_MKI, FUNC_BANK_STOCK_MKI, "ef", "ef_fb_mki",
                  "MKI FUNC+BANK: clear LISTPOP while SEQ open, else stock/KITS"),
    ),
    requires=("STORE",),
    gates=(
        Gate("tools/verify/verify_seq.py", venv=True, stage="image"),
        Gate("tools/verify/verify_seq_func_bank.py", venv=True, stage="image"),
        Gate("tools/verify/verify_seq_scenarios.py", venv=True, stage="image"),
    ),
)
