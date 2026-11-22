"""SEQ is a Euclidean rhythm and parameter-lock window for audio and MIDI.

Hold [TRACK] and press [PAGE] to open it. The rhythm page has A=PULS,
B=ROT, C=LANE, D=page and parameter, E=DPTH, and empty F. The Harmony page
has A=SCAL, B=ROOT, D=PHRS, and E=JUMP on audio and MIDI tracks. PHRS starts
at RAND, then UP, DOWN, ALT and TRI. MIDI also
has C=VOIC and F=CHRD. Fresh audio settings select SRC PTCH; MIDI settings
select NOTE. [LEFT] and [RIGHT] switch pages without hiding the step grid.

TRIG writes audio sample trigs or MIDI note trigs and the selected
destination's locks. PLCK rewrites only that destination's locks. SEQ keeps
its scale and root separate from the PROJECT SCALE QUANTIZER. Bare [CUE]
release randomizes the focused lane's hit positions; PHRS RAND generates
new in-scale pitches on each fill. [CUE]+[TRACK] keeps stock cue behavior.
TRACK key shortcuts remain stock. [FUNC]+[BANK] opens the clear menu; [NO]
closes SEQ or returns from the menu. Bare [PAGE] keeps its stock function.
Settings are stored per track and destination in euclid.work through STORE.
"""

import runpy
from pathlib import Path

from remix.schema import (
    Category, Detour, Evidence, Gate, Kind, Level, Linked, Module, SymbolRef,
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
    evidence=(
        Evidence(Level.UNIT, unit="MKII", who="ilia-murzinov", image="OCTA S3.RMX", date="2026-11-16",
                 commit="854ea9c055d9dea89a91763ed43f065e3a24de10",
                 note="Author confirmed the OCTA S3 handoff checklist: loads in BRAIN, PTCH opens Harmony, "
                      "and THRU INAB has no RIGHT hint. No audio or timing measurements reported."),
        Evidence(Level.UNIT, unit="MKII", who="ilia-murzinov", image="SEQ 83.RMX", date="2026-11-15",
                 note="Author confirmed SEQ 83 works on the unit, including empty unused "
                      "NOTE3/4 slots after a VOIC 2 fill. No separate audio or timing measurements."),
        Evidence(Level.UNIT, unit="MKII", who="ilia-murzinov", date="2026-11-11",
                 note="CX EUCL93, 11 Nov 2026: dual LANE, write-only, LOCK_COLL + floor, PLCK overwrites TRIG-placed locks,"
                      " TRIG reshape keeps other DEST locks (TL promote); also verify_seq."),
        Evidence(Level.UNIT, unit="MKII", who="ilia-murzinov", image="CX CJ.RMX", date="2026-11-14",
                 note="all six reported device checks passed: PLCK PULS 0 clearing; all FUNC+BANK "
                      "clear rows and NO cancel; ARE YOU SURE? layering and lock; "
                      "stock TRACK shortcuts; CUE chord vs bare tap; SCALE-off "
                      "Part PTCH. Does not claim audio testing."),
    ),
    doc="TRACK+PAGE opens SEQ for audio and MIDI: A=PULS B=ROT C=LANE, "
        "D=page/parameter E=DPTH; Harmony A=SCAL B=ROOT D=PHRS E=JUMP. "
        "PHRS defaults to RAND, then UP/DOWN/ALT/TRI. "
        "MIDI adds C=VOIC and F=CHRD. Fresh audio DEST is SRC PTCH; MIDI "
        "DEST is NOTE. TRIG writes track trigs and selected DEST locks; "
        "PLCK rewrites only that DEST. CUE randomizes hit positions; PHRS "
        "RAND rerolls pitches on each fill. Per-track settings persist via STORE.",
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
        Gate("tools/verify/verify_seq_tonal.py", venv=True, stage="image"),
        Gate("tools/verify/verify_seq_tonal_port.py", venv=True, stage="image"),
        Gate("tools/verify/verify_seq_func_bank.py", venv=True, stage="image"),
        Gate("tools/verify/verify_seq_scenarios.py", venv=True, stage="image"),
    ),
)
