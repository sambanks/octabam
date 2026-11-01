"""FREE LOOP -- loop pedals per track: the first free loop sets the tempo.

Two pedals per track on the track's MIDI channel (value > 0 the press, 0
the release): CC 90 REC and CC 91 PLAY/STOP. What REC does is the track's
ROLE (TRACK + UP opens the track's window; saved with the project in
freeloop.work, a STORE client):
  FREE  sequencer stopped and no loop anywhere: the first press starts a
        free recording on the track's recorder (its RECORDING SETUP's
        sources), the second ends it and, from its length, sets the tempo
        (the track's SIGN, BARS AUTO or 1-16, MIN / MAX BPM), the playing
        pattern's length and scale, the loop's end, and starts the
        sequencer. Afterwards the track behaves as GRID.
  GRID  arm / cut the overdub: the track's recorder trigs fire only while
        it is armed.
  OFF   stock.
PLAY/STOP: stopped, PLAY; playing, mute / unmute the track (as a CC 49 on
its channel); released 1 s or more after the press, the track's loop
cleared (a pedal that sends 127 only never clears). CC 93 END: mute at the
loop's end, or back at the next loop start (from the step handler). Each pattern sets per
track how the track enters it
(ENTRY KEEP / ARM / OFF), applied when the pattern starts to play.

On the PROG CH channel: 83 PLAY / STOP, 84 clear R1-R8 (stopped), 85 / 86
next / previous pattern, 88 / 89 next / previous bank; a bank change while
playing clears R1-R8.

Detours (INVESTIGATION.md):
  fl_cc        the stock CC handler's entry 0x4000e79c (`linkw %fp,#-44 ;
               moveml %d2-%d7/%a2-%a5,(%sp)`, 8 bytes, replayed for any other CC)
  fl_gate_stub the step handler's recorder-trig test 0x4009d9a4 (10 bytes),
               REC_TRIG_MUTE's site
  fl_ui_stub   the UI task's toast countdown 0x40056c28: the pattern's entry
               modes, clears, loop ends, toasts
  fl_rec_stub  the recorder routine's setup pointer 0x40006d1a (`adda.l
               #0x80000cf4,%a4`): a free take records with RLEN MAX
  fl_glyph,    the track status icon renderer 0x4004bee2 / 0x4004c00c,
  fl_draw      REC_TRIG_MUTE's sites: a ring while armed, a dot while overdubbing
and the [TRACK]-held key layer's table pointer 0x400d164e (MORPH's site),
pointed at a copy of stock's table with UP added (the window).

Beside REC_TRIG_MUTE and REC THRESHOLD the shared sites go through HOOKS
(modules/hooks): the status icon chain calls fl_glyph last; at the step
handler and the icon drawer this detour stays and, assembled with
HK_REC_GATE / HK_ICON_DRAW (select below), hands on to rtm_gate / rtm_draw
where it replayed stock. MORPH stays a conflict: both want [TRACK]+UP.
"""

import dataclasses

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof, SymbolRef

H = bytes.fromhex

CC_ENTRY = 0x4000e79c
CC_ENTRY_STOCK = H("4e56ffd4" "48d73cfc")     # linkw %fp,#-44 ; moveml %d2-%d7/%a2-%a5,(%sp)
GATE = 0x4009d9a4
GATE_STOCK = H("4a83" "676e" "243c0000091a")  # tst.l %d3 ; beq.s 0x4009da16 ; move.l #0x91a,%d2
TICK = 0x40056c28
TICK_STOCK = H("2039460d1e6c")                # move.l 0x460d1e6c,%d0 (the toast countdown)
REC = 0x40006d1a
REC_STOCK = H("d9fc80000cf4")                 # adda.l #0x80000cf4,%a4 (the recorder's setup pointer)
TRIG = 0x4009d39e
TRIG_STOCK = H("260d" "c083" "67000576")       # move.l %a5,%d3 ; and.l %d3,%d0 ; beq.w 0x4009d91a
GLYPH = 0x4004bee2
GLYPH_STOCK = H("41f9400c0cb8")                 # lea 0x400c0cb8,%a0 (the edge renderer's state cache)
DRAW = 0x4004c00c
DRAW_STOCK = H("7003b08c6618")                  # moveq #3,%d0 ; cmpl %a4,%d0 ; bnes 0x4004c02a
KEYS_FIELD = 0x400D164E                       # the [TRACK]-held layer's keys pointer
KEYS_STOCK = 0x400D1594

_UNIT = Linked("fl", "modules/free-loop/free_loop.s", cpu="5475", dram=True)


def select(modules):
    """Beside REC_TRIG_MUTE (modules/hooks rec_gate / icon_draw) the unit is assembled
    with HK_REC_GATE / HK_ICON_DRAW: its not-ours paths jump to rtm_gate / rtm_draw."""
    from remix import hooks_flags
    defs = tuple((flag, 1) for bridge, flag in (("rec_gate", "HK_REC_GATE"), ("icon_draw", "HK_ICON_DRAW"))
                 if hooks_flags.on(bridge, "FREE LOOP", modules))
    return {"linked": (dataclasses.replace(_UNIT, defsyms=defs),)} if defs else {}


MODULE = Module(
    name="free-loop",
    key="FREE LOOP",
    kind=Kind.CF_PATCH,
    category=Category.MIDI_USB,
    author="djib",
    author_url="https://github.com/Djibdjib",
    proof=Proof.HARDWARE,
    proof_note="the owner's MKII, OCTABAM8-OCTABAM17 (a rig remix, with REC MUTE), 26-28 Oct 2026: free take and tempo, "
               "overdub, PLAY/STOP and clear, UNDO / REDO, END, PLAY entries, the popup; "
               "tools/verify/verify_free_loop.py",
    doc="Loop pedals per track on its channel: CC 90 REC (a FREE track's first free loop sets the tempo, "
        "the pattern length and starts the sequencer; then arm / cut the overdub; held: clear a muted or stopped loop), "
        "CC 91 PLAY/STOP (play, mute / unmute, held: END), CC 92 UNDO / REDO, CC 93 END (mute / unmute at the loop's start). "
        "TRACK + UP: the track's ROLE, SIGN, BARS, BPM range and the pattern's ENTRY mode. "
        "CC 83-89 on PROG CH: PLAY/STOP, clear, pattern and bank steps.",
    linked=(_UNIT,),
    detours=(
        Detour(CC_ENTRY, CC_ENTRY_STOCK, "fl", "fl_cc",
               "CC handler entry: CC 90 / 91 / 93 (a track's pedals), CC 83-89, else stock", pad_to=8),
        Detour(GATE, GATE_STOCK, "fl", "fl_gate_stub",
               "step handler: a FREE / GRID track's recorder trig fires only when armed; END at the loop start",
               pad_to=10),
        Detour(TICK, TICK_STOCK, "fl", "fl_ui_stub",
               "UI task's toast countdown: entry modes, clears, loop ends, toasts"),
        Detour(REC, REC_STOCK, "fl", "fl_rec_stub",
               "recorder routine: a free take reads its track's setup with RLEN MAX"),
        Detour(TRIG, TRIG_STOCK, "fl", "fl_trig_stub",
               "record builder's machine-trig test: a PLAY STOP track's trigs dropped (a stock empty step)",
               pad_to=8),
        Detour(GLYPH, GLYPH_STOCK, "fl", "fl_glyph",
               "edge renderer: armed / overdubbing folded into the cached state (REC_TRIG_MUTE's site)", kind="jsr"),
        Detour(DRAW, DRAW_STOCK, "fl", "fl_draw",
               "edge renderer: a ring while armed, a dot while overdubbing (REC_TRIG_MUTE's site)"),
    ),
    symbol_refs=(
        SymbolRef(KEYS_FIELD, KEYS_STOCK, "fl", "fl_keys",
                  "[TRACK]-held key layer: the stock table plus UP (the FREE LOOP window)"),
    ),
    requires=("STORE",),
    conflicts=(
        ("MORPH", "both replace the [TRACK]-held key table 0x400d1594"),
    ),
    gates=(Gate("modules/free-loop/verify.py", remix_arg=False),
           Gate("tools/verify/verify_free_loop.py", venv=True)),
    select=select,
)
