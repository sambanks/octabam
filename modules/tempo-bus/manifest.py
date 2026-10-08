"""TEMPO BUS -- the TEMPO window carries the bus engines' knobs.

The TEMPO key opens the stock TEMPO window at the menu window's size
(118 x 64) with a stock-style settings screen in place of its big-digit
draw: the header ("TEMPO 121.2" at the left, then a key: the four
arrows, "A" and the font's knob glyph; the rule) and two titled boxes, DELAY and
REVERB, listing each engine's named parameters with the values its own
formatters print. UP/DOWN move the cursor in the focused box, A (or B)
edits (x7 while pushed, as stock),
LEFT / RIGHT switch boxes (each keeps its own cursor); a mode's
"---" slots are left out of the list. C-F are held while the window is open. LEVEL
steps whole BPM (the stock 0x4004b918) and 0.1 BPM with FUNC held (the
stock step 0x4004b824(0, +-1) that UP/DOWN made). YES/NO/TEMPO (close) keep the
stock window's handlers (layer 0x400bb4ec).

Stock routines used, all as the CONTROL INPUT (0x40065674) and MIDI SYNC
(0x4006730c) screens call them: header text 0x40012bd8 / width
0x40012f30 in font 0x400ba876, rule 0x40011910, titled
box 0x4007efd0, invert bar 0x40012254. Input: an extra layer pushed by
0x40031494 over TEMPO's and popped by 0x4003146c. Edits: page 1 through
the page-1 writer 0x40054cd8(track, 24 + slot, value); page 2 with the
FX2 page-2 editor's stores (Part +0x8f084, shadow 0x100a51d2, live lane
+0x38, the four dirty flags; CC MAP's write path), then MODE DEFAULTS'
CC_MODEDEF2 when that module is linked before this one.

Measured under the port: the stock TEMPO window, CONTROL INPUT and MIDI
SYNC drawn from memory dumps (`--mem-dump` of the window planes). The
screen itself: see the PR.
"""

from remix.schema import Gate, Category, Proof, Detour, Kind, Linked, Module, Poke

H = bytes.fromhex
ENGINES = ("DELAY SERVER", "REVERB SERVER")    # box 0, box 1
HOST_SENDS = (0, 1)                            # DEL, REV: on the host page, not the screen
# The rows, top to bottom, by knob name: the four both engines have, in the
# same place in both boxes, then each engine's own from most to least used.
# A slot not named here follows in slot order.
ROW_ORDER = {
    "DELAY SERVER":  ("MODE", "TIME", "WET", "TONE", "FDBK", "PING", "SIZE", "SCTR", "DENS", "PTCH"),
    "REVERB SERVER": ("MODE", "TIME", "WET", "TONE", "SIZE", "DLY", "SHMR", "SHFT", "DIFF", "GATE"),
}


def table_inc(modules):
    """ENGIDS (the two FX2 ids), NAMED (per box, a bit per slot the engine's
    manifest names) and two macros, NAMETAB_0 / NAMETAB_1: each engine's
    twelve 6-byte names, labelled NAMES_<fx2 id>. helpers.s places the
    delay's, tempobus.s the reverb's. The screen reads its labels there;
    with the engine a host_slots module (the remix), its MODE cave renames
    there too (build_bus.py), so the shared descriptor keeps the host
    page's one name. An engine not in the remix has no rows."""
    ids, masks, tabs = [], [], []
    for box, key in enumerate(ENGINES):
        m = modules.get(key)
        # DEL and REV (slots 0, 1) are the host page's own knobs, not listed here
        named = ([i for i, p in enumerate(m.params) if p.name and i not in HOST_SENDS]
                 if m is not None else [])
        fid = m.menu.fx2_id if m is not None else 0xff
        ids.append(fid)
        masks.append(sum(1 << i for i in named))
        rows = []
        for i in range(12):
            nm = (m.params[i].name or b"") if m is not None else b""
            rows.append("        .byte   " + ", ".join(str(c) for c in (nm + bytes(6))[:6]))
        tabs.append(f"        .macro  NAMETAB_{box}\n        .globl  NAMES_{fid:02x}\n"
                    f"NAMES_{fid:02x}:\n" + "\n".join(rows) + "\n        .endm\n")
    order = []
    for key in ENGINES:
        m = modules.get(key)
        names = [(p.name or b"").decode("latin1") for p in m.params] if m is not None else [""] * 12
        slots = [names.index(n) for n in ROW_ORDER.get(key, ()) if n in names]
        order.append(slots + [i for i in range(12) if i not in slots])
    tabs.append("        .macro  ORDERTAB\nORDER:\n" + "".join(
        "        .byte   " + ", ".join(map(str, o)) + "\n" for o in order) + "        .endm\n")
    tabs.append("        .macro  NTABS_LONGS\n        .long   "
                + ", ".join(f"NAMES_{i:02x}" for i in ids) + "\n        .endm\n")
    return ("ENGIDS: .byte   " + ", ".join(map(str, ids)) + "\n"
            "        .even\n"
            "NAMED:  .word   " + ", ".join(f"{m:#x}" for m in masks) + "\n"
            + "".join(tabs))


MODULE = Module(
    name="tempo-bus",
    key="TEMPO BUS",
    kind=Kind.CF_PATCH,
    category=Category.BUS, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.PORT, proof_note="`verify_set`; carried by image 88 on Sam's MKII, not exercised there",
    doc="The TEMPO window lists and edits BusDelay's and BusVerb's knobs "
        "(UP/DOWN = row, A or B = value, LEFT/RIGHT = engine, FUNC + LEVEL = 0.1 BPM).",
    # DRAM units (8 Oct 2026; pinned in the ROM zero runs at 0x400d24d0 and
    # 0x400d64e0 until then). The helpers link first: the screen calls them.
    linked=(Linked("helpers", "modules/tempo-bus/helpers.s",
                   include=table_inc, dram=True),
            Linked("tempobus", "modules/tempo-bus/tempobus.s",
                   include=table_inc, dram=True),),
    detours=(
        Detour(0x40059F2C, H("4ef94004b528"), "tempobus", "tb_open",
               "TEMPO opener: push the bus layer, draw the bus screen"),
        Detour(0x4004B528, H("4e56ffe848d7041c"), "tempobus", "tb_draw",
               "TEMPO draw (every caller, BPM edits included): the bus screen",
               pad_to=8),
        Detour(0x40056930, H("4ab9460d16a0"), "tempobus", "tb_close",
               "TEMPO close: pop the bus layer, then the stock close"),
    ),
    pokes=(
        Poke(0x40059F04, H("48780030"), H("48780040"), note="TEMPO window height 48 -> 64 (the menu window's)"),
        Poke(0x40059F08, H("48780049"), H("48780076"), note="TEMPO window width 73 -> 118 (the menu window's)"),
    ),
    # reads the card verify_set staged: an image-stage gate
    gates=(Gate('tools/verify/verify_tempobus.py', stage='image'),),
)
