"""VERB PARTS -- a Part saved with a stock reverb opens on its VERBERATION row at that row's defaults.

octabam-verbs puts VERB PLATE, VERB ROOM and VERB HALL on PLATE, SPRING and DARK REV's ids. A Part saved with a
stock reverb then opens on the row but with the stock reverb's knob values, read as VERBERATION's. This module
converts such a Part just before the firmware applies it: two detours inside the Part apply (0x40009094)
and the pattern-change apply (0x40009e00), every route a Part reaches the engine by, after the arguments are
in registers and before the Part is read. The sign of a
stock reverb's Part is FX2 page-2 slots 9 and 10 both 0: the stock reverbs never draw them.
"""
from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof

ROWS = ("VERB PLATE", "VERB ROOM", "VERB HALL")      # ids 0x14, 0x15, 0x16, in that order: vp_tab's rows


def table_inc(modules, remix):
    """vp_tab: per row, page 1's six default bytes, then page 2's (slots 6-11), from the rows' manifests."""
    rows = ["        .data", "vp_tab:"]
    for i, key in enumerate(ROWS):
        m = modules[key]
        if m.menu.fx2_id != 0x14 + i:
            raise ValueError(f"VERB PARTS: {key} is on id 0x{m.menu.fx2_id:02x}, not 0x{0x14 + i:02x}")
        vals = [p.default or 0 for p in m.params]
        if vals[9] == 0 and vals[10] == 0:
            raise ValueError(f"VERB PARTS: {key}'s defaults hold 0 in slots 9 and 10, the stock-Part sign")
        rows.append(f"        .byte   {', '.join(str(v) for v in vals[:12])}    | {key}")
    return "\n".join(rows) + "\n"


MODULE = Module(
    name="verb-parts", key="VERB PARTS", kind=Kind.CF_PATCH,
    category=Category.PARTS, author="sambanks", author_url="https://github.com/sambanks",
    doc="A Part saved with PLATE, SPRING or DARK REV opens on its VERBERATION row (VERB PLATE, ROOM, HALL) at that row's defaults.",
    proof=Proof.PORT, proof_note="verify_verb_parts (the port); not run on a unit",
    requires=ROWS,
    linked=(Linked("verbparts", "modules/verb-parts/verbparts.s", cpu="5475", include=table_inc, dram=True),),
    gates=(Gate("tools/verify/verify_verb_parts.py", venv=True),),
    detours=(
        # A few instructions in, not at the entries: those are VARISPEED's (rp_apply1, rp_apply2), whose stubs
        # replay the prologue and come back. Nothing before these reads the Part.
        Detour(0x400090aa, bytes.fromhex("13c080001828"), "verbparts", "vp_apply",
               "Part apply (bank in a5, p in a6): convert a stock-reverb Part's FX2 pages before it is read", kind="jmp"),
        Detour(0x40009e10, bytes.fromhex("13c680001828"), "verbparts", "vp_patapply",
               "pattern-change apply (bank in d6, p in d5): the same", kind="jmp"),
    ),
)
