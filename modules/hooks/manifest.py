"""HOOKS -- the one owner of a stock site that two selected modules both claim.

The ledger allows one claim on a stock site, so two modules that hook one
instruction or repoint one word could not share an image. A BRIDGE here
joins them: when a remix carries two or more of a bridge's participants,
HOOKS takes the site (schema.Override of each participant's claim there)
and calls each participant's own routine, in an order that respects each
one's protocol. A remix carrying one participant, or none, gets nothing
from HOOKS: that module's own claim stands and its bytes do not move, so a
module proven alone on a unit stays exactly what was proven.

The registry appends HOOKS to a remix whenever a bridge has two
participants in it (registry.remix), as it appends MEMORY; no remix lists
it. The participants' sources are not edited: a submodule's stays its
author's (REC_TRIG_MUTE), an in-tree module's keeps its proven bytes.

docs/proposals/SHARED_HOOKS.md is the design. Bridges:

  * track_key -- the [TRACK]-held key layer 0x400d164a. Its keys field
    0x400d164e points at stock's six records at 0x400d1594 (0x1a bytes
    each: code, 0, press, release, 16 zero bytes; then 0xff, 0). MORPH
    repoints the field at its own copy with UP and DOWN added; REC_TRIG_MUTE
    repoints the YES and NO records' handlers inside stock's table. Together,
    MORPH's copy would carry stock's YES/NO and REC_TRIG_MUTE's mute keys
    would silently stop working. Bridged: HOOKS's table is stock's six
    records with each participant's replacements, then each participant's
    added keys, and the field points at it. REC_TRIG_MUTE's own refs into
    stock's table are still written; nothing reads that table once the field
    is repointed.
  * status_icon -- the track status icon renderer's state-cache load
    0x4004bee2 (`lea 0x400c0cb8,%a0`), d3 the track, a4 the state about to be
    compared and drawn. REC_TRIG_MUTE (rtm_glyph) folds a mute into a4 as
    8 | playing; REC THRESHOLD (blink_gate) ORs 0x10 into a4 on an armed
    track's off phase. Both are `jsr` detours that redo the lea and may
    clobber d0/d1/a0/a1, which the renderer reloads before reading.
    Bridged: one jsr calls rtm_glyph, then blink_gate -- the fold first, so
    the blink bit survives it (in the other order rtm_glyph's `and #1`
    would clear 0x10).
  * frame_tail -- the frame interrupt's epilogue 0x4000d9a6 (`movem.l
    (%sp),%d0-%d7/%a0-%a6 ; lea 252(%sp),%sp ; rte`, every exit path).
    LOAD METER (lm_out), CF METER (m_tail) and BOOT TRACE (tr_frame_end)
    each replay it themselves, so none returns. Bridged, each is built with
    HK_FRAME_TAIL set and ends in `rts` instead (its remix.inc, flags_inc);
    HOOKS jmps here, calls each, then replays the epilogue once. None of the
    three touches the stack frame before its replay, and every register is
    restored by the replay, so each may clobber all of them.
  * frame_entry -- the frame interrupt's entry 0x4000aad0 (`lea
    -252(%sp),%sp ; movem.l %d0-%d7/%a0-%a6,(%sp)`). BOOT TRACE (tr_frame)
    and LOAD METER (lm_in) each replay the prologue and jmp to 0x4000aad8.
    Bridged (HK_FRAME_ENTRY), each enters after its replay and ends in
    `rts`; HOOKS replays the prologue once, calls BOOT TRACE's note, then
    LOAD METER's stamp last, so the duration it measures excludes the note.
  * boot -- 0x40000512, the boot's `jsr 0x4000f938` after the DSP upload.
    BOOT TRACE (tr_dsp_done, a jmp) sends note 3 and replays the call; STORE
    (store_part_resident_activate, a jsr, selected only with a native Part
    client) sets its copy targets and tail-jumps to 0x4000f938. Bridged
    (HK_BOOT), BOOT TRACE's routine sends the note and returns; HOOKS calls
    it, then jmps to store_part_resident_activate, which returns to the boot.
  * chrom_pitch -- the CHROMATIC key handler's key -> pitch at 0x4004fc58
    (`lea (4,%a2,%a2.l*4),%a2 ; mvz.b 0x100b14cf,%d0`): OCTA303 (o3_chrom: on
    a 303 track the key is semitones) and SCALE QUANTIZER (qz_chrom: a synth
    track's key, every other track snapped to the scale). Both are jsr
    replacements of the same 10 bytes with scratch d0, d1, a0, a1. Bridged,
    OCTA303's detour stays and its every-other-track path is built
    (HK_CHROM_PITCH) to tail-jump into qz_chrom instead of the stock lea;
    SCALE QUANTIZER's detour is overridden. HOOKS has no code here.
  * chromatic -- the CHROMATIC octave keys 0x40045918, key index 0x40050254
    and keyboard picture 0x40044968: BLACKPYRAMIDS_303 (Zac Kyoti's submodule,
    not edited: four octaves on its track, and on any other track an octave
    above 1 reset to 0, ot_chrom_sanitize) and SCALE QUANTIZER (a synth
    track's octave -4..+4; every other track stock). Bridged, HOOKS asks
    ot_track_is(the UI track): a BLACKPYRAMIDS track takes its handler (or,
    for the picture, its full-keyboard branch); any other track gets
    ot_chrom_sanitize and then SCALE QUANTIZER's handler. One difference from
    BLACKPYRAMIDS alone: FUNC + LEFT/RIGHT on another track, with an octave
    of 2 or 3 left by a BLACKPYRAMIDS track, lands on 1 (sanitized to 0, then
    stock's toggle) where BLACKPYRAMIDS alone lands on 0. The picture's
    detour spans SCALE QUANTIZER's 8 bytes, so stock's `bne` at 0x40044970,
    which SCALE QUANTIZER's handler returns to, stays in place.
  * machine_rows -- the track's machine list, SRC SETUP and the machine
    hooks behind them: ANALOG BD and OCTA303 are each a sixth row (row 5)
    of a five-row list that never scrolls, each signing a FLEX track in the
    same three Part bytes ('A' 'B' 1 / 'T' 'B' 1) and each taking the FLEX
    kind entry's renderer. Bridged, ANALOG BD keeps row 5 and every one of
    its hooks; built with HK_MACHINE_ROWS, each of its not-ours paths hands
    the hook to OCTA303's routine for it (name, commit, SRC SETUP commit,
    validator, row type), and OCTA303, built with its row as 6, publishes
    its record as UI type 6's from ANALOG BD's tick and chains its renderer
    into ab_render. OCTA303's own copies of those hooks are overridden; its
    page, retrig, CHROMATIC, LFO-name and trig hooks are its alone and
    stay. The lists have seven rows: HOOKS pokes the counts and bounds and
    takes the chooser drawer's two row tests (0x40078678, 0x400786c8) so it
    scrolls, drawing row top + d2 where stock draws row d2.
"""

import os
import runpy
from pathlib import Path

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Override, Poke, Proof, SymbolRef

H = bytes.fromhex
_HERE = os.path.relpath(os.path.dirname(os.path.realpath(__file__)))

# ---- track_key -----------------------------------------------------------
KEYS_FIELD = 0x400D164E                 # the [TRACK]-held layer's keys pointer
KEYS_STOCK = 0x400D1594                 # stock's six records + the 0xff terminator
# Stock's records, in stock's order (code, press, release): STOP, PLAY, BANK,
# YES (ARM REC TRK), NO (DISARM REC TRK), 0x18. tools/verify/verify_hooks.py
# compares them with the user's 1.40C.
STOCK_KEYS = (
    (0x27, 0x40083A7C, 0),
    (0x28, 0x40083A30, 0),
    (0x2F, 0x40083CE0, 0),
    (0x31, 0x400834D8, 0x400834D8),
    (0x32, 0x40083488, 0x40083488),
    (0x18, 0x400839DC, 0),
)
# (module key, records it replaces, records it adds, its claim on KEYS_FIELD).
# A record is (code, press symbol, release symbol or None). Table order is
# participant order; a code may be replaced or added by one participant only.
TRACK_KEY = (
    ("REC_TRIG_MUTE", ((0x31, "rtm_yes", "rtm_yes"), (0x32, "rtm_no", "rtm_no")), (), False),
    ("MORPH", (), ((0x33, "morph_up", None), (0x20, "morph_down", None)), True),
)

# ---- status_icon ---------------------------------------------------------
ICON_SITE = 0x4004BEE2
ICON_STOCK = H("41f9400c0cb8")          # lea 0x400c0cb8,%a0
# (module key, its jsr routine at ICON_SITE), in call order.
STATUS_ICON = (
    ("REC_TRIG_MUTE", "rtm_glyph"),
    ("REC THRESHOLD", "blink_gate"),
)


# ---- frame_tail, frame_entry, boot -----------------------------------------
TAIL_SITE = 0x4000D9A6
TAIL_STOCK = H("4cd77fff4fef00fc4e73")  # movem.l (%sp),%d0-%d7/%a0-%a6 ; lea 252(%sp),%sp ; rte
ENTRY_SITE = 0x4000AAD0
ENTRY_STOCK = H("4fefff0448d77fff")     # lea -252(%sp),%sp ; movem.l %d0-%d7/%a0-%a6,(%sp)
BOOT_SITE = 0x40000512
BOOT_STOCK = H("4eb94000f938")          # jsr 0x4000f938
# (module key, its routine), in call order. A routine built with its flag
# set (flags_inc) returns instead of replaying the stock instructions.
FRAME_TAIL = (
    ("LOAD METER", "lm_out"),
    ("CF METER", "m_tail"),
    ("BOOT TRACE", "tr_frame_end"),
)
FRAME_ENTRY = (
    ("BOOT TRACE", "tr_frame"),
    ("LOAD METER", "lm_in"),
)
BOOT = (
    ("BOOT TRACE", "tr_dsp_done"),
    ("STORE", "store_part_resident_activate"),   # last: it tail-jumps to the stock call
)

# ---- chrom_pitch, chromatic -------------------------------------------------
PITCH_SITE = 0x4004FC58
CHROM_PITCH = (
    ("OCTA303", "o3_chrom"),            # first: a 303 track's own; every other track ->
    ("SCALE QUANTIZER", "qz_chrom"),
)
CHROMATIC_SITES = (                     # (site, stock bytes, HOOKS's routine)
    (0x40045918, H("7401b5b9460d16fc"), "hk_octkey"),   # moveq #1,%d2 ; eor.l %d2,0x460d16fc
    (0x40050254, H("2039460d16fc2200"), "hk_keyidx"),   # move.l 0x460d16fc,%d0 ; move.l %d0,%d1
    (0x40044968, H("7201b2b9460d16fc"), "hk_octdraw"),  # moveq #1,%d1 ; cmp.l 0x460d16fc,%d1
)
CHROMATIC = (
    ("BLACKPYRAMIDS_303", "ot_track_is"),
    ("SCALE QUANTIZER", "qz_octkey"),
)

# ---- machine_rows -----------------------------------------------------------
# The machines on the track's list after the stock five, in row order: each
# present one takes the next row (5, 6, 7). The first present is the HEAD: its
# hooks keep every shared site and hand each row but its own on through the
# chain; each machine's not-mine path jumps to the next one's routine for the
# same hook, entered as at the site (MC_NEXT_*, flags_inc), and the last one's
# replays stock. (module key, its row-type routine.)
MACHINE_ROWS = (
    ("ANALOG BD", "ab_row_type"),
    ("OCTA303", "o3_type"),
    ("CX OSC", "fm_type"),
)
# PB_TABLE (0x400d5f38) has slots 0..6 and a spare zero word at 0x400d5f54 that
# no code reads; the FX1 table starts at 0x400d5f58: three rows at most.
MC_MAX = 3
# Each machine's routine for each chained hook. A routine is entered as at its
# hook's site; None: the machine has no such hook. `publish` (its PLAYBACK
# record into PB_TABLE[its row], called from the head's tick) and `title` (its
# name, a word of the head's SRC SETUP name table) are needed of a non-head only.
MACHINES = {
    "ANALOG BD": dict(TYPE="ab_row_type", NAME="ab_machine_name", MAIN_COMMIT="ab_main_commit",
                      SRC_COMMIT="ab_src_commit", SRC_COMMIT2="ab_src_commit2",
                      VALIDATE="ab_validate", RENDER="ab_render", PAGE=None, RETRIG=None,
                      publish=None, title=None),
    "OCTA303": dict(TYPE="o3_type", NAME="o3_machine_name", MAIN_COMMIT="o3_main_commit",
                    SRC_COMMIT="o3_src_commit", SRC_COMMIT2="o3_src_commit2",
                    VALIDATE="o3_validate", RENDER="o3_render", PAGE="o3_page", RETRIG="o3_retrig",
                    publish="o3_publish", title="o3_title"),
    # CX OSC's commit is at 0x40079816, before the others' 0x4007981c: fm_main_commit_hk
    # undoes the stock `adda` the chain's head site follows (modules/cxosc/machine.s)
    "CX OSC": dict(TYPE="fm_type", NAME="fm_machine_name", MAIN_COMMIT="fm_main_commit_hk",
                   SRC_COMMIT="fm_src_commit", SRC_COMMIT2="fm_src_commit2",
                   VALIDATE="fm_validate", RENDER="sy_render", PAGE="pg_resolve", RETRIG="po_retrig",
                   publish="fm_publish", title="fm_name"),
}
# The hooks whose chain is not the row order. CX OSC heads the render chain:
# its page code and SCALE QUANTIZER find its records in the words before the
# renderer the FLEX kind entry names (`movea.l 0x400d6438,%a0 ; movea.l
# -4(%a0),%a0`), so the entry must be its sy_render. ANALOG BD's renderer (C)
# calls stock's 0x40004008 itself, so it is the last. CX OSC's STATIC entry
# chains the same way: OCTA303 claims a voice only by a FLEX signature or a
# TB303* sample's settings record (o3_marker), and stock renders the rest.
MC_ORDER = {"RENDER": ("CX OSC", "OCTA303", "ANALOG BD"),
            "PAGE": ("OCTA303", "CX OSC"), "RETRIG": ("OCTA303", "CX OSC")}
MC_CHAINED = ("TYPE", "NAME", "MAIN_COMMIT", "SRC_COMMIT", "SRC_COMMIT2", "VALIDATE",
              "RENDER", "PAGE", "RETRIG")
# The row chain's head-owned sites, and the machines that claim each (CX OSC
# has no second name lookup and commits at 0x40079816).
_ALL3, _AO = ("ANALOG BD", "OCTA303", "CX OSC"), ("ANALOG BD", "OCTA303")
MC_HEAD_SITES = {
    0x400334D8: _ALL3, 0x4003C928: _ALL3, 0x4003D718: _ALL3, 0x4004C36A: _AO,
    0x4003C980: _ALL3, 0x400585DC: _ALL3, 0x4005221E: _ALL3, 0x40078886: _ALL3,
    0x4007981C: _AO, 0x4005A616: _ALL3, 0x4005A850: _ALL3, 0x4003A52E: _ALL3,
    0x4003CD98: _ALL3, 0x40002318: _ALL3,
}
# Their own chains' heads keep these; the rest are overridden.
MC_KIND_FLEX = 0x400D6438               # the FLEX kind entry: the render chain's head
MC_PAGE_SITE = 0x40031ECE               # the PLAYBACK page resolver (CX OSC: PLACE=DRAM's)
MC_RETRIG_SITE = 0x4000C634
MC_CX_COMMIT = 0x40079816               # CX OSC's machine-window commit, never a head
# The list's count and bound sites, HOOKS's for any number of rows: each
# machine's own six-row pokes (CX OSC: detours, and five cursor clamps).
MC_POKE_SITES = (0x40079248, 0x400585FA, 0x4003C950, 0x40078678, 0x400786CE, 0x40079904)
MC_CLAMPS = (0x40078C22, 0x40078CB0, 0x40078D2E, 0x40078DEE, 0x40078E7C)
MC_DRAW = (                             # (site, stock bytes, HOOKS's routine, pad)
    (0x40078678, H("7004b0826d24"), "hk_mc_name", 6),               # moveq #4,%d0 ; cmp.l %d2,%d0 ; blt.s
    (0x400786C8, H("7110b480662e7004b0826d28"), "hk_mc_box", 12),   # the stored machine's box test
)
MC_BOX = 0x400786C8                     # each machine's own row-box detour, HOOKS's


def mc_pokes(n):
    """HOOKS's pokes for 5 + n rows."""
    rows, last = 5 + n, 4 + n
    return (
        Poke(0x40079248, H("48780005"), H(f"487800{rows:02x}"), f"the machine list has {rows} rows"),
        Poke(0x400585FA, H("48780005"), H(f"487800{rows:02x}"), f"SRC SETUP's selector has {rows} rows"),
        Poke(0x4003C950, H("7204"), H(f"72{last:02x}"), f"SRC SETUP's name lookup admits rows 5..{last}"),
        Poke(0x40079904, H("7604"), H(f"76{last:02x}"), f"the machine list's commit persists rows 5..{last}"),
    ) + tuple(
        # the list's five key handlers (UP, DOWN, their FUNC pages, the encoder) clamp the cursor
        # to 0..5 after moving (`moveq #5,%d1 ; cmp.l %d0,%d1 ; bge.s ; moveq #5,%d0`): one past
        # stock's last row, which is why one added machine fitted without them
        Poke(at + off, H(f"{op}05"), H(f"{op}{last:02x}"), f"the machine list's cursor reaches row {last}")
        for at in MC_CLAMPS for off, op in ((0, "72"), (6, "70")))


def machines(modules):
    """The machines on the list for a selection, in row order."""
    return tuple(k for k, _t in _present(MACHINE_ROWS, modules))


def _chain(hook, modules):
    """The present machines that have `hook`, in its chain's order."""
    order = MC_ORDER.get(hook, tuple(k for k, _t in MACHINE_ROWS))
    on = machines(modules)
    return tuple(k for k in order if k in on and MACHINES[k][hook])


def machine_inc(key, modules):
    """The machine_rows lines of a machine's remix.inc: its row, the list's end,
    and per chained hook whether a next machine has it (MC_HAS_*) and its
    routine (MC_NEXT_*); the head's names-table tail and tick publishes."""
    on = machines(modules)
    if "machine_rows" not in bridged(modules) or key not in on:
        return ""
    if len(on) > MC_MAX:
        raise ValueError(f"HOOKS machine_rows: {', '.join(on)} need {len(on)} rows "
                         f"after the stock five; PB_TABLE has room for {MC_MAX}")
    out = [f".set MC_ROW, {5 + on.index(key)}", f".set MC_ROWS_END, {5 + len(on)}"]
    for hook in MC_CHAINED:
        chain = _chain(hook, modules)
        nxt = chain[chain.index(key) + 1:] if key in chain else ()
        out.append(f".set MC_HAS_{hook}, {int(bool(nxt))}")
        if nxt:
            out.append(f".set MC_NEXT_{hook}, {MACHINES[nxt[0]][hook]}")
    head = on[0] == key
    out.append(".macro mc_names_tail")
    out += [f"    .long {MACHINES[k]['title']}" for k in on[1:]] if head else []
    out += [".endm", ".macro mc_publish"]
    out += [f"    jsr {MACHINES[k]['publish']}" for k in on[1:]] if head else []
    out.append(".endm")
    return "\n".join(out) + "\n"


def _mc_overrides(modules):
    """Every machine's claim the chain or HOOKS stands in for."""
    on = machines(modules)
    head, out = on[0], []
    for site, owners in MC_HEAD_SITES.items():
        out += [Override(site, k) for k in on if k != head and k in owners]
    for site in MC_POKE_SITES + (MC_BOX,):
        out += [Override(site, k) for k in on]
    if "CX OSC" in on:
        out += [Override(site, "CX OSC") for site in MC_CLAMPS + (MC_CX_COMMIT,)]
    for hook, site in (("RENDER", MC_KIND_FLEX), ("PAGE", MC_PAGE_SITE), ("RETRIG", MC_RETRIG_SITE)):
        out += [Override(site, k) for k in _chain(hook, modules)[1:]]
    return out


BRIDGES = {"track_key": TRACK_KEY, "status_icon": STATUS_ICON, "frame_tail": FRAME_TAIL,
           "frame_entry": FRAME_ENTRY, "boot": BOOT, "chrom_pitch": CHROM_PITCH,
           "chromatic": CHROMATIC, "machine_rows": MACHINE_ROWS}
# The flag each bridge sets in its participants' remix.inc (flags_inc).
FLAGS = {"frame_tail": "HK_FRAME_TAIL", "frame_entry": "HK_FRAME_ENTRY", "boot": "HK_BOOT",
         "chrom_pitch": "HK_CHROM_PITCH", "machine_rows": "HK_MACHINE_ROWS"}
# Bridges that need no code of HOOKS's own: a participant's flagged build does it.
CODELESS = {"chrom_pitch"}


_STORE_PARTS = runpy.run_path(str(Path(__file__).resolve().parents[1] / "store" / "parts.py"))


def _present(participants, modules):
    # STORE owns the boot site only when a registered native Part client is selected.
    return tuple(p for p in participants if p[0] in modules
                 and (p[0] != "STORE" or _STORE_PARTS["layout"](modules)[0]))


def bridged(modules) -> tuple[str, ...]:
    """The bridges a selection of module keys needs: those with two or more
    participants in it."""
    return tuple(b for b, parts in BRIDGES.items() if len(_present(parts, modules)) >= 2)


def flags_inc(key, modules) -> str:
    """The lines a participant's remix.inc carries: each flag 1 when that
    bridge is on and `key` is in it, else 0 (its own bytes, unchanged); a
    machine on a shared list also gets its place in the chain (machine_inc)."""
    on = bridged(modules)
    return "".join(f".set {flag}, {int(b in on and any(p[0] == key for p in BRIDGES[b]))}\n"
                   for b, flag in FLAGS.items()) + machine_inc(key, modules)


def track_key_records(modules):
    """HOOKS's [TRACK]-layer table for a selection: [(code, press, release)],
    each handler a stock address or a participant's symbol."""
    recs = [list(r) for r in STOCK_KEYS]
    codes = {r[0] for r in STOCK_KEYS}
    owner = {}
    for key, replaces, adds, _field in _present(TRACK_KEY, modules):
        for code, press, release in replaces:
            if code not in codes:
                raise ValueError(f"HOOKS track_key: {key} replaces key 0x{code:02x}, "
                                 f"which stock's layer does not have")
            if code in owner:
                raise ValueError(f"HOOKS track_key: {key} and {owner[code]} both "
                                 f"replace key 0x{code:02x}")
            owner[code] = key
            r = next(r for r in recs if r[0] == code)
            r[1], r[2] = press, release or 0
        for code, press, release in adds:
            if code in codes or code in owner:
                raise ValueError(f"HOOKS track_key: {key} adds key 0x{code:02x}, "
                                 f"which the layer already has")
            owner[code] = key
            recs.append([code, press, release or 0])
    return [tuple(r) for r in recs]


def _handler(v):
    return f"0x{v:08x}" if isinstance(v, int) else v


def hooks_inc(modules, remix=None):
    """remix.inc for bridge.s: which bridges are on and their tables."""
    on = bridged(modules)
    out = [f".set hk_{b}, {int(b in on)}" for b in BRIDGES if b not in CODELESS]
    out += [".macro hk_track_key_records"]
    if "track_key" in on:
        out += [f"    HKREC 0x{c:02x}, {_handler(p)}, {_handler(r)}"
                for c, p, r in track_key_records(modules)]
    out += [".endm", ".macro hk_status_icon_chain"]
    if "status_icon" in on:
        out += [f"    jsr {sym}" for _key, sym in _present(STATUS_ICON, modules)]
    out += [".endm"]
    for b in ("frame_tail", "frame_entry", "boot"):
        out += [f".macro hk_{b}_chain"]
        if b in on:
            parts = _present(BRIDGES[b], modules)
            out += [f"    jsr {sym}" for _key, sym in parts[:-1]]
            last = parts[-1][1]
            # boot's last participant tail-jumps to the stock call and returns
            # to the boot itself; the others' last is called like the rest
            out += [f"    jmp {last}" if b == "boot" else f"    jsr {last}"]
        out += [".endm"]
    # the machine list's row box: the head's type routine answers every machine's row
    out += [".macro hk_mc_type"]
    if "machine_rows" in on:
        out += [f"    jsr {MACHINES[machines(modules)[0]]['TYPE']}"]
    out += [".endm"]
    return "\n".join(out) + "\n"


UNIT = Linked("hooks", os.path.join(_HERE, "bridge.s"), dram=True, include=hooks_inc)

# Participants' routines placed in ROM caves, not the platform runtime: the
# runtime's link reaches them through the unit's defsyms, which the build
# resolves from the ROM units' exports (build_bus._defs_for). verify_hooks
# checks this list against each participant's Linked.dram.
ROM_ROUTINES = {"tr_frame", "tr_frame_end", "tr_dsp_done", "store_part_resident_activate"}


def _unit(modules):
    """HOOKS's unit for a selection, naming each ROM-placed routine it calls."""
    used = {sym for b in bridged(modules) if b in FLAGS and b not in CODELESS
            for _k, sym in _present(BRIDGES[b], modules)}
    defs = tuple((s, 0) for s in sorted(used & ROM_ROUTINES))
    return Linked("hooks", UNIT.source, dram=True, include=hooks_inc, defsyms=defs)


def select(modules):
    """Only the bridges this selection needs enter the bound module: its
    unit, its claims and its overrides of the participants' claims."""
    on = bridged(modules)
    detours, refs, overrides, pokes = [], [], [], []
    if "track_key" in on:
        refs.append(SymbolRef(KEYS_FIELD, KEYS_STOCK, "hooks", "hk_track_keys",
                              "[TRACK]-held key layer: stock's records with each "
                              "participant's replacements and added keys"))
        overrides += [Override(KEYS_FIELD, key)
                      for key, _r, _a, field in _present(TRACK_KEY, modules) if field]
    if "status_icon" in on:
        detours.append(Detour(ICON_SITE, ICON_STOCK, "hooks", "hk_status_icon",
                              "track status icons: each participant's state fold, in order",
                              kind="jsr"))
        overrides += [Override(ICON_SITE, key) for key, _sym in _present(STATUS_ICON, modules)]
    for b, site, stock, sym, kind, pad, note in (
            ("frame_tail", TAIL_SITE, TAIL_STOCK, "hk_frame_tail", "jmp", 10,
             "the frame interrupt's epilogue: each participant, then the epilogue once"),
            ("frame_entry", ENTRY_SITE, ENTRY_STOCK, "hk_frame_entry", "jmp", 8,
             "the frame interrupt's entry: the prologue once, then each participant"),
            ("boot", BOOT_SITE, BOOT_STOCK, "hk_boot", "jsr", None,
             "the boot after the DSP upload: each participant, the last into the stock call")):
        if b in on:
            detours.append(Detour(site, stock, "hooks", sym, note, kind=kind, pad_to=pad))
            overrides += [Override(site, key) for key, _sym in _present(BRIDGES[b], modules)]
    if "chrom_pitch" in on:
        overrides.append(Override(PITCH_SITE, "SCALE QUANTIZER"))   # OCTA303's detour stays
    if "chromatic" in on:
        for site, stock, sym in CHROMATIC_SITES:
            detours.append(Detour(site, stock, "hooks", sym,
                                  "CHROMATIC: a BLACKPYRAMIDS track its own, another SCALE QUANTIZER's",
                                  kind="jmp", pad_to=8))
            overrides += [Override(site, key) for key, _s in _present(CHROMATIC, modules)]
    if "machine_rows" in on:
        for site, stock, sym, pad in MC_DRAW:
            detours.append(Detour(site, stock, "hooks", sym,
                                  "the machine list scrolls: row top + d2 on screen row d2",
                                  kind="jmp", pad_to=pad))
        pokes += mc_pokes(len(machines(modules)))
        overrides += _mc_overrides(modules)
    coded = [b for b in on if b not in CODELESS]
    return {"linked": (_unit(modules),) if coded else (), "detours": tuple(detours),
            "symbol_refs": tuple(refs), "overrides": tuple(overrides), "pokes": tuple(pokes)}


# The unbound declaration carries every bridge, so the matrix and the
# remixer see HOOKS as the bridge that joins each pair (index.py, app.py);
# ledger.check and registry.bound apply select() to any real selection.
_ALL = select({p[0] for parts in BRIDGES.values() for p in parts} | set(_STORE_PARTS["PART_CLIENTS"]))

MODULE = Module(
    name="hooks",
    key="HOOKS",
    kind=Kind.CF_PATCH,
    category=Category.SETTINGS, author="Sam Banks", author_url="https://github.com/sambanks",
    proof=Proof.PORT, proof_note="verify_hooks: the bridged tables and chains under Unicorn, and each bridged image's sites",
    doc="Platform: owns a stock site two selected modules both claim, and calls each one's routine there.",
    linked=_ALL["linked"], detours=_ALL["detours"], symbol_refs=_ALL["symbol_refs"],
    overrides=_ALL["overrides"], pokes=_ALL["pokes"],
    select=select,
    gates=(Gate("tools/verify/verify_hooks.py", once=True, venv=True),),
)
