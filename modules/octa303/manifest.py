"""OCTA303 -- a standalone FLEX machine: one circuit-modelled TB-303 voice (v6.5, dEVILish).

A FLEX track whose voice starts on a sample named TB303* (TB303.wav saw, TB303SQ.wav square,
TB303D.wav / TB303SQD.wav with the pedal; any case) plays the 303 instead of the sample, its
PLAYBACK page reading TUNE CUT RES ENV DEC ACC. With the dEVILish module on its FX1 or FX2, the
303 reads that slot's twelve knobs as Robin Whittle's Devil Fish mods (the module is
modules/devilish: its menu row, its knobs and a DSP pass-through); without it, it is the 303 of
v6.1.1, sample for sample. Every other track is stock.

The integration is Tim Hastie's SYNTH MACHINE 2.9 (timhastie/octatrick-modules, MIT), re-done
for one voice: the kind table's FLEX renderer -> sy_render (a SymbolRef); the voice START
resolved from the settings record the voice struct points at; PTCH / RATE neutral (0x4000 /
0x7f00) and the carrier's positions pinned around the stock call; the trig command byte made
clean on a sounding 303 track (po_retrig's fix, a Detour); the PLAYBACK page a runtime clone of
the stock record (a Detour at the resolver's table load -- in DRAM, no ROM cave).
"""
import os

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Poke, Proof, SymbolRef

# This module's own directory relative to octabam's root (the build's cwd), as poly.s's manifest.
_HERE = os.path.relpath(os.path.dirname(os.path.realpath(__file__)))
_TOOLS = os.path.join(os.path.dirname(os.path.dirname(_HERE)), "tools", "octa303")
H = bytes.fromhex

KIND_TABLE_FLEX = 0x400D6438             # the kind table's FLEX entry (kind 1)
STOCK_RENDERER = 0x40004008              # its stock value, the sample renderer
RESOLVER_HOOK = 0x40031ECE               # `move.l 0(a0,d0.l*4),d0; bra.s 0x40031ed6`
RESOLVER_STOCK = H("20300c00" "6002")
# dEVILish (modules/devilish) is a separate FX module; when a
# remix carries it, OCTA303's unit learns its FX id through remix.inc, and without it DEVIL_ID is 0x100,
# which no id byte equals: every 303 track is then the classic one.  0x10 is the id dEVILish claims
# (PHASER's, with replaces); test_octa303 checks the two agree.
DEVIL_ID = 0x10


def remix_inc(modules, remix=None):
    """remix.inc for octa303.s: dEVILish's FX id when the remix carries it.

    The build calls include(modules, remix) (schema.Linked.include); the remix is not needed here."""
    from remix import hooks_flags
    return ("        .set    DEVIL_ID, 0x%x\n" % (DEVIL_ID if "DEVILISH" in modules else 0x100)
            + hooks_flags.inc("OCTA303", modules))


def _render_ref(sym):
    return SymbolRef(KIND_TABLE_FLEX, STOCK_RENDERER, "octa303", sym,
                     "kind table FLEX renderer -> OCTA303 sy_render (TB303*-named samples play the "
                     "303; every other sample the stock renderer)")


def select(modules):
    """Beside another machine (modules/hooks, machine_rows) the renderer is o3_render: CX OSC's
    poly.s exports a sy_render of its own into the same runtime link."""
    from remix import hooks_flags
    if hooks_flags.on("machine_rows", "OCTA303", modules):
        return {"symbol_refs": (_render_ref("o3_render"),)}
    return {}


CHROM_HOOK = 0x4004FC58                  # `lea (4,a2,a2.l*4),a2; mvz.b 0x100b14cf,d0` (quantizer's qz_chrom site)
CHROM_STOCK = H("45f2ac04" "71b9100b14cf")

RETRIG_HOOK = 0x4000C634                 # `movea.l 114(sp),a1; move.b (a0,a1.l),d0`
RETRIG_STOCK = H("226f0072" "10309800")

MODULE = Module(
    name="octa303",
    key="OCTA303",
    kind=Kind.CF_PATCH,
    category=Category.MACHINES,
    author="MaMarko",
    author_url="https://github.com/braikomarko-hub",
    doc=("A FLEX track whose sample is named TB303* plays a circuit-modelled TB-303 (diode "
         "ladder, accent-sweep capacitor, RC slide; TB303D*/TB303SQD* add a pedal). PLAYBACK: "
         "TUNE (-24..+24 semitones: four octaves) CUT RES ENV DEC ACC; dEVILish on FX1/FX2 = the Devil Fish mods (Whittle). "
         "Accent = an ACC lock, slide = a trigless PTCH lock. v7.0: OCTA-303 is also its own machine (row 5 "
         "of the machine list, no sample needed) with a SETUP page WAVE GATE FINE SLID DRIV ACCV; "
         "GATE 303 = the 303's own gate, 3.5 of the step's 6 clocks (Whittle). v7.1: held trig + UP / DOWN = "
         "an octave, a new slide takes the note it slides from."),
    proof=Proof.HARDWARE,
    proof_note=("v7.1 on the author's MKI, image O3V71 (BUILD A0, remix octa303), 23 Oct 2026: held trig + UP / DOWN an octave (several trigs at once, C5 stays), FUNC + TRIG's slide tied into the previous note, then turned to another note and an octave up, a FLEX track's TRIG + UP stock, LFO SETUP's names, save / power-cycle / reload; v7.0 on the author's MKI, image ACIDV70 (BUILD 87, remix acidtrack), 19 Oct 2026: the OCTA-303 "
                "machine chosen from the list, its SETUP page, save / power-cycle / reload, the 303 gate; "
                "v6.3-v6.9 played for hours (two or three tracks, with dEVILish and DisTorX). The engine is "
                "bit-exact against tools/octa303/ref303.py (test_octa303); the panel under the port in "
                "verify_octa303_ui. The ColdFire load is not measured on the unit."),
    linked=(
        Linked("octa303", os.path.join(_HERE, "octa303.s"), dram=True, include=remix_inc),
    ),
    symbol_refs=(_render_ref("sy_render"),),
    select=select,
    detours=(
        Detour(RESOLVER_HOOK, RESOLVER_STOCK, "octa303", "o3_page",
               "page resolver PLAYBACK table load: a FLEX track whose slot holds a TB303* sample "
               "gets the TB-303 clone of the FLEX descriptor", kind="jmp"),
        Detour(RETRIG_HOOK, RETRIG_STOCK, "octa303", "o3_retrig",
               "the frame builder's DSP command-byte copy: a START on a sounding OCTA303 track is "
               "posted as the clean 0x30 (no DSP crossfade of the one continuous stream)",
               kind="jmp", pad_to=8),
        Detour(CHROM_HOOK, CHROM_STOCK, "octa303", "o3_chrom",
               "CHROMATIC key -> pitch: on a 303 track TUNE is semitones (v6.4, raw = 52 + key "
               "index = -12..+12), every other track the stock 5 * index + 4",
               kind="jsr", pad_to=10),
        # v7.0: the TB-303 machine, row 5 of the track's machine list -- ANALOG BD's measured seams
        # (modules/analog-bassdrum/machine.s), the same sites and displaced bytes, without its engine pool.
        Detour(0x400334D8, H("2f02222f0008"), "octa303", "o3_machine_name",
               "format machine row 5 as OCTA-303"),
        Detour(0x4003C928, H("4bf9400a78c8"), "octa303", "o3_src_names",
               "point SRC SETUP at six machine names", kind="lea"),
        Detour(0x4003D718, H("41f9400a78c8"), "octa303", "o3_name_a",
               "main page name lookup for the signed TB-303 track"),
        Detour(0x4003BFF0, H("711041f9400d5f38"), "octa303", "o3_lfo_name",
               "LFO SETUP's destination names: an OCTA-303 track's PLAYBACK row from the machine's record"),
        Detour(0x400434D8, H("4fefffe448d704fc"), "octa303", "o3_octave",
               "held trig + UP / DOWN: on an OCTA-303 track the held steps' TUNE an octave up / down "
               "(stock: the sample-lock list, which a track without samples has no use for)"),
        Detour(0x40060B58, H("4feffff448d7001c"), "octa303", "o3_trig_in",
               "trig-key dispatcher (key, event): at a press, an OCTA-303 track's trigless masks kept for "
               "o3_trig_out"),
        Detour(0x40060B3E, H("4cef3cfc00044fef002c"), "octa303", "o3_trig_out",
               "trig-key handler tail: a new trigless trig or lock on an OCTA-303 track gets the TUNE "
               "lock of the note it slides from"),
        Detour(0x4004C36A, H("41f9400a78c8"), "octa303", "o3_name_b",
               "second main page name lookup for the signed TB-303 track"),
        Detour(0x4003C980, H("71104fef0018"), "octa303", "o3_setup_row",
               "SRC SETUP row highlights TB-303 on a signed FLEX track"),
        Detour(0x400786C8, H("7110b480662e"), "octa303", "o3_chooser_row",
               "main chooser row highlights TB-303 on a signed FLEX track"),
        Detour(0x400585DC, H("161079034879400bb704"), "octa303", "o3_setup_open",
               "SRC SETUP opens on TB-303 for the signed track", pad_to=10),
        Detour(0x4005221E, H("4ebaff1c4eb94007e940"), "octa303", "o3_tick",
               "publish the TB-303 record as UI type 5's", pad_to=10),
        Detour(0x40078886, H("71102f004879460e7386"), "octa303", "o3_chooser_open",
               "the track's machine list opens on TB-303 for the signed track", pad_to=10),
        Detour(0x4007981C, H("77101084d081"), "octa303", "o3_main_commit",
               "admit TB-303 at main chooser commit (stored as FLEX, signed)"),
        Detour(0x4005A616, H("2239460d5c30"), "octa303", "o3_src_commit",
               "admit TB-303 at SRC SETUP commit"),
        Detour(0x4005A850, H("2239460d5c30"), "octa303", "o3_src_commit2",
               "the same at SRC SETUP's second commit path"),
        Detour(0x4003A52E, H("2002e788d4829082"), "octa303", "o3_setup_edit6",
               "SETUP's editor stores TB-303's row in the track's FLEX slot", pad_to=8),
        Detour(0x4003CD98, H("2e06e78fdc869e86"), "octa303", "o3_setup_draw6",
               "SETUP's drawer reads TB-303's row from the track's FLEX slot", pad_to=8),
        Detour(0x40002318, H("4fefffa048d77cfc"), "octa303", "o3_validate",
               "the Part validator reads a TB-303 track's FLEX bytes as FLEX defaults", pad_to=8),
    ),
    pokes=(
        Poke(0x40079248, H("48780005"), H("48780006"), "machine chooser has six rows, TB-303 the last"),
        Poke(0x400585FA, H("48780005"), H("48780006"), "SRC SETUP selector has six rows"),
        Poke(0x4003C950, H("7204"), H("7205"), "SRC SETUP name lookup admits TB-303"),
        Poke(0x40078678, H("7004"), H("7005"), "machine chooser draws TB-303"),
        Poke(0x400786CE, H("7004"), H("7005"), "machine chooser highlights TB-303"),
        Poke(0x40079904, H("7604"), H("7605"), "machine chooser persists TB-303"),
    ),
    conflicts=(
        ("SYNTH MACHINE", "both own the FLEX renderer entry 0x400d6438, the PLAYBACK resolver "
                          "load 0x40031ece and the command-byte copy 0x4000c634"),
        ("BLACKPYRAMIDS_303", "both are a TB-303 on machine row 5: 16 shared detour sites (the machine "
                              "chooser, SRC SETUP, the Part validator 0x40002318, the LFO PMTR names "
                              "0x4003bff0 among them) and 7 shared "
                              "pokes (the chooser's row count, draw, highlight and persistence, SRC SETUP's "
                              "row count and name lookup, the FLEX renderer entry 0x400d6438)"),
    ),
    gates=(
        Gate(os.path.join(_TOOLS, "sim", "test_octa303.py"), remix_arg=False),
        Gate("tools/verify/verify_octa303_ui.py", remix_arg=False, stage="image"),
    ),
)
