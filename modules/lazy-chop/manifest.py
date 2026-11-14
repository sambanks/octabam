"""LAZY CHOP -- slice a sample (a recorder take) by tapping the trig keys while it plays.

Audio editor > SLICE page > the slice menu > LAZY CHOP opens a window:
TRIG 1 starts the take from the trim start (slice 1 starts there); TRIG 2
ends slice 1 and starts slice 2 at the playhead, and so on to TRIG 16;
after TRIG 16 the page turns by itself and TRIG 1 starts slice 17. Four
pages, 64 slices. Only the next key in order places a marker. YES writes
the slices, NO restores the ones that were there.

After YES (or NO) the mode ends and the keys are stock's again: the new
slices are edited like any others. A key layer of its own (the firmware's
keymap list) holds the trig keys, YES and NO only while chopping; the
page's encoders and drawing are stock. lazychop.s has the detail.
"""

from remix.schema import (Apply, Binary, Category, Detour, Gate, Kind, Linked, Module, Poke, Proof, Scope,
                          Setting, Store, SymbolRef, TableGrow)

# The audio editor's SLICE menu (FUNC+BANK or YES on the SLICE page), opener
# 0x40072c10 (key records 0x400cec62, 0x400cef2e). It tests 0x400ceb3c (the
# slice under the marker, < 0 = none) and calls the LISTPOP 0x4006d94c with
# one of two row sets. Read statically from 1.40C, 4 Nov 2026.
OFF_HANDLERS, OFF_LABELS, OFF_COUNT = 0x400CEB74, 0x400CEB8C, 6   # ADD SLICE HERE .. CHANGE VIEW
ON_HANDLERS, ON_LABELS, ON_COUNT = 0x400CEBA4, 0x400CEBC8, 9      # DISABLE LOOP .. CHANGE VIEW
OFF_PEA_HANDLERS, OFF_PEA_LABELS, OFF_COUNT_IMM = 0x40072C5E, 0x40072C64, 0x40072C76
ON_PEA_HANDLERS, ON_PEA_LABELS, ON_COUNT_IMM = 0x40072C40, 0x40072C46, 0x40072C58
# LAZY CHOP is the first row of both slice menus (8thmyth, 10 Nov 2026; until then just above CREATE SLICE GRID). Inserting
# renumbers the rows after it; only the opener 0x40072c10 reads these tables
# and the selection words 0x460e5f54/58, and every row has its own handler,
# so nothing stock indexes them by a constant.
OFF_AT, ON_AT = 0, 0
# Stock's trig-LED pass 0x40043fdc is called through this slot (the u32 at
# 0x400c0936, after the MKII key layer). On the unit the editor's own trig
# display painted over LAZY CHOP's red while the sequencer was stopped
# (8thmyth's MKI, F4, 10 Nov 2026); lc_ledpass runs stock's, then puts ids
# 0-31 back while LAZY CHOP is open. No direct caller exists (0 jsr/bsr).
TRIGLED_SLOT, TRIGLED_PASS = 0x400C0936, 0x40043FDC
# The LED task's loop (0x4005595c: wait 0x46c7e0e2, jsr (a2)) loads the 120
# Hz countdown tick with `lea 0x4001387c,%a2` at 0x40055956; its operand
# (0x40055958) points at lc_tick instead. CC FEEDBACK's detour is the next
# instruction (0x4005595c), not these bytes.
LEDTICK_OPERAND, LEDTICK = 0x40055958, 0x4001387C
# The frame path reads each track's pending command (0x46c80354 + 4t: 0x1d
# plays) at 0x4000b54a: move.l (a0,d3*4),d0 / btst #0,d0, then beq. With the
# sequencer running, a step trig on the chopped track restarted the take, and
# with SLIC on (the slice count follows the taps) played slice 1 only, so no
# tap past it landed (8thmyth's MKI, F5, 10 Nov 2026). lc_cmdgate drops the
# sequencer's play for that track while chopping; LAZY CHOP's own goes through.
CMDGATE = 0x4000B54A
# Stock's step-LED painter (the function around 0x400341d2..0x4003445e)
# loads set_led 0x40013784 into an address register five times (lea abs.l,An;
# the long at +2). While LAZY CHOP is open it flashed a p-locked step's trig
# LED for 3 ticks, which lc_tick turned off again: a flicker (8thmyth, H5;
# found under the port with a write watch on LED row 0). lc_ledflt drops ids
# 0-31 while LAZY CHOP is open and passes every other call to stock's.
LEDPAINT_LEAS, LEDON = (0x400341D4, 0x400341EE, 0x400342CE, 0x400343B2, 0x4003445A), 0x40013784

STORE_ID = "octabam.lazy-chop"


def lc_inc(modules, remix):
    """remix.inc: get_snap reads the ZERO SNAP setting; put_snap stores it
    and asks BRAIN to write the card. Without BRAIN, ZERO SNAP is kept until
    power-off only, as before."""
    import sys, pathlib
    from remix import schema
    sys.path.insert(0, str(pathlib.Path(schema.__file__).resolve().parents[1]))
    from remix import brain
    mods = modules if isinstance(modules, dict) else {}
    out = ["| remix.inc -- LAZY CHOP (modules/lazy-chop/manifest.py)"]
    for key, name, mac, var in ((1, "ZERO SNAP", "snap", "lc_snap"), (2, "LIVE CHOP", "live", "lc_live")):
        get = brain.read_macro(remix, mods, STORE_ID, name, f"get_{mac}").rstrip("\n")
        held = "brain_v_" in get
        if not held:                   # no BRAIN: keep it for the session
            get = f"        .macro  get_{mac} reg\n        move.l  {var},\\reg\n        .endm"
        sym = brain.value_symbol(STORE_ID, key)
        put = (f"        .macro  put_{mac} reg\n        move.l  \\reg,{sym}\n        jsr     brain_post_settings\n        .endm"
               if held else f"        .macro  put_{mac} reg\n        .endm")
        out += [get, put]
    return "\n".join(out) + "\n"


MODULE = Module(
    name="lazy-chop",
    key="LAZY CHOP",
    kind=Kind.CF_PATCH,
    category=Category.UTILITIES, author="8thmyth", author_url="https://github.com/8thmyth",
    proof=Proof.HARDWARE, proof_note="8thmyth's MKI, image OCTABAMHC (remix test/octabam-lazy-chop), 14 Nov 2026: STUDIO and LIVE chopping, ZERO SNAP, pattern recording, timestretched slice 1; verify_lazy_chop under the port (MKI and MKII)",
    doc="Slice a sample by tapping TRIG 1..16 (four pages, 64 slices) while it plays, from the audio editor's slice menu.",
    linked=(Linked("lazychop", "modules/lazy-chop/lazychop.s", dram=True, include=lc_inc),),
    store=Store(STORE_ID),
    settings=(Setting(1, "ZERO SNAP", Binary(), default=0, scope=Scope.CARD, apply=Apply.LIVE,
                      doc="ZERO SNAP when LAZY CHOP opens; [SCALE] while chopping changes it and it is kept across power-off"),
              Setting(2, "LIVE CHOP", Binary(), default=0, scope=Scope.CARD, apply=Apply.LIVE,
                      doc="LIVE CHOP (TRIG 1 starts the recorder, silent cuts at the record head) or STUDIO CHOP (TRIG 1 plays the take); [CUE] while LAZY CHOP is open changes it")),
    detours=(
        Detour(0x40071BB2, bytes.fromhex("4eb94003146c"), "lazychop", "lc_leave",
               "SLICE page leave: LAZY CHOP's key layer goes down with the page's map", kind="jsr"),
        Detour(CMDGATE, bytes.fromhex("20303c0008000000"), "lazychop", "lc_cmdgate",
               "frame path, a track's pending command: the sequencer's play held off for the chopped track while chopping",
               kind="jsr", pad_to=8),
    ),
    symbol_refs=(
        SymbolRef(TRIGLED_SLOT, TRIGLED_PASS, "lazychop", "lc_ledpass",
                  "trig-LED pass slot: stock's pass, then LAZY CHOP's green/red while it is open"),
        SymbolRef(LEDTICK_OPERAND, LEDTICK, "lazychop", "lc_tick",
                  "LED task tick: stock's countdowns, then ids 0-31 checked while LAZY CHOP is open"),
        *(SymbolRef(a, LEDON, "lazychop", "lc_ledflt",
                    "step-LED painter's set_led: the trig LEDs left to LAZY CHOP while it is open")
          for a in LEDPAINT_LEAS),
    ),
    tables=(
        TableGrow("SLICE menu (off a slice) handlers + LAZY CHOP", old=OFF_HANDLERS, count=OFF_COUNT,
                  symbols=(("lazychop", "lc_open"),), refs=((OFF_PEA_HANDLERS, OFF_HANDLERS),), insert_at=OFF_AT),
        TableGrow("SLICE menu (off a slice) labels + LAZY CHOP", old=OFF_LABELS, count=OFF_COUNT,
                  symbols=(("lazychop", "lc_label"),), refs=((OFF_PEA_LABELS, OFF_LABELS),), insert_at=OFF_AT),
        TableGrow("SLICE menu (on a slice) handlers + LAZY CHOP", old=ON_HANDLERS, count=ON_COUNT,
                  symbols=(("lazychop", "lc_open"),), refs=((ON_PEA_HANDLERS, ON_HANDLERS),), insert_at=ON_AT),
        TableGrow("SLICE menu (on a slice) labels + LAZY CHOP", old=ON_LABELS, count=ON_COUNT,
                  symbols=(("lazychop", "lc_label"),), refs=((ON_PEA_LABELS, ON_LABELS),), insert_at=ON_AT),
    ),
    pokes=(
        Poke(OFF_COUNT_IMM, expect=(6).to_bytes(2, "big"), write=(7).to_bytes(2, "big"),
             note="SLICE menu off a slice: LISTPOP count 6 -> 7"),
        Poke(ON_COUNT_IMM, expect=(9).to_bytes(2, "big"), write=(10).to_bytes(2, "big"),
             note="SLICE menu on a slice: LISTPOP count 9 -> 10"),
    ),
    gates=(Gate("tools/verify/verify_lazy_chop.py", venv=True, stage="image"),),
)
