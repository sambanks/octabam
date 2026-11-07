"""WAVE (ColdFire) -- a 4-voice wavetable machine, a row of the track's machine list.

A FLEX track chosen as WAVE (the machine list or SRC SETUP, signature 'W','V',1 in the Part) plays
modules/wavecf's engine instead of a sample: 4 voices over 8 generated frames (sine, triangle, saw, square,
four pulses), no filter. PLAYBACK: TUNE FRAM CHRD VOIC ATK REL. CHRD picks one of 32 chord shapes and VOIC how
many of its four notes sound; FRAM morphs between neighbouring frames. The Octatrack's own AMP envelope,
FX and LFOs act on it as on any track.

The engine is a fixed-point port of CHOMPI WAVE's voice (MIT, Copyright (c) 2026 CHOMPI Club,
LICENSE-CHOMPI), reduced to what the Octatrack does not already have. The machine scaffold -- the list row,
SRC SETUP, the Part validator, the page clone and the render call -- is modules/octa303's, copied; beside
OCTA303 the two share the sites through HOOKS (machine_rows, chrom_pitch) and one limit,
MC_LIMIT machines in a Part.
"""
import os

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Poke, Proof, SymbolRef

_HERE = os.path.relpath(os.path.dirname(os.path.realpath(__file__)))
H = bytes.fromhex

KIND_TABLE_FLEX = 0x400D6438             # the kind table's FLEX entry (kind 1)
STOCK_RENDERER = 0x40004008              # its stock value, the sample renderer
RESOLVER_HOOK = 0x40031ECE               # `move.l 0(a0,d0.l*4),d0; bra.s 0x40031ed6`
RESOLVER_STOCK = H("20300c00" "6002")
CHROM_HOOK = 0x4004FC58
CHROM_STOCK = H("45f2ac04" "71b9100b14cf")
RETRIG_HOOK = 0x4000C634
RETRIG_STOCK = H("226f0072" "10309800")


def remix_inc(modules, remix=None):
    from remix import hooks_flags
    return hooks_flags.inc("WAVE CF", modules)


def _render_ref():
    return SymbolRef(KIND_TABLE_FLEX, STOCK_RENDERER, "wavecf", "wc_render",
                     "kind table FLEX renderer -> WAVE's wc_render (a WAVE track plays the engine; every other "
                     "track the stock renderer)")


MODULE = Module(
    name="wavecf",
    key="WAVE CF",
    kind=Kind.CF_PATCH,
    category=Category.MACHINES,
    author="sambanks", author_url="https://github.com/sambanks",
    doc=("WAVE: a 4-voice wavetable machine, a row of the track's machine list. PLAYBACK: TUNE FRAM CHRD VOIC "
         "ATK REL: FRAM morphs eight frames, CHRD one of 32 chords, VOIC 1-4 of its notes. No filter: the "
         "Octatrack's own FX and AMP follow."),
    proof=Proof.PORT,
    proof_note=("the engine and the note layer: Python model == host == ColdFire under Unicorn "
                "(modules/wavecf/test_wavecf.py); the machine under the port: not yet. Not flashed"),
    linked=(Linked("wavecf", os.path.join(_HERE, "wavecf.s"), dram=True, include=remix_inc),),
    symbol_refs=(_render_ref(),),
    detours=(
        Detour(RESOLVER_HOOK, RESOLVER_STOCK, "wavecf", "wc_page",
               "page resolver PLAYBACK table load: a signed FLEX track gets WAVE's page", kind="jmp"),
        Detour(RETRIG_HOOK, RETRIG_STOCK, "wavecf", "wc_retrig",
               "the frame builder's DSP command-byte copy: a START on a sounding WAVE track is posted as the "
               "clean 0x30 (no DSP crossfade of the one continuous stream)", kind="jmp", pad_to=8),
        Detour(CHROM_HOOK, CHROM_STOCK, "wavecf", "wc_chrom",
               "CHROMATIC key -> pitch: on a WAVE track TUNE is semitones (raw = 52 + key index), every other "
               "track the stock 5 * index + 4", kind="jsr", pad_to=10),
        Detour(0x400334D8, H("2f02222f0008"), "wavecf", "wc_machine_name", "format the WAVE row's name"),
        Detour(0x4003C928, H("4bf9400a78c8"), "wavecf", "wc_src_names",
               "point SRC SETUP at the machine names", kind="lea"),
        Detour(0x4003D718, H("41f9400a78c8"), "wavecf", "wc_name_a", "main page name lookup for a signed track"),
        Detour(0x4004C36A, H("41f9400a78c8"), "wavecf", "wc_name_b", "second main page name lookup"),
        Detour(0x4003C980, H("71104fef0018"), "wavecf", "wc_setup_row",
               "SRC SETUP row highlights WAVE on a signed FLEX track"),
        Detour(0x400786C8, H("7110b480662e"), "wavecf", "wc_chooser_row",
               "main chooser row highlights WAVE on a signed FLEX track"),
        Detour(0x400585DC, H("161079034879400bb704"), "wavecf", "wc_setup_open",
               "SRC SETUP opens on WAVE for the signed track", pad_to=10),
        Detour(0x4005221E, H("4ebaff1c4eb94007e940"), "wavecf", "wc_tick",
               "publish WAVE's record as its row's UI type", pad_to=10),
        Detour(0x40078886, H("71102f004879460e7386"), "wavecf", "wc_chooser_open",
               "the track's machine list opens on WAVE for the signed track", pad_to=10),
        Detour(0x4007981C, H("77101084d081"), "wavecf", "wc_main_commit",
               "admit WAVE at main chooser commit (stored as FLEX, signed)"),
        Detour(0x4005A616, H("2239460d5c30"), "wavecf", "wc_src_commit", "admit WAVE at SRC SETUP commit"),
        Detour(0x4005A850, H("2239460d5c30"), "wavecf", "wc_src_commit2",
               "the same at SRC SETUP's second commit path"),
        Detour(0x4003A52E, H("2002e788d4829082"), "wavecf", "wc_setup_edit6",
               "SRC SETUP's editor stores WAVE's row in the track's FLEX slot", pad_to=8),
        Detour(0x4003CD98, H("2e06e78fdc869e86"), "wavecf", "wc_setup_draw6",
               "SRC SETUP's drawer reads WAVE's row from the track's FLEX slot", pad_to=8),
        Detour(0x40002318, H("4fefffa048d77cfc"), "wavecf", "wc_validate",
               "the Part validator keeps a WAVE track's six PLAYBACK bytes", pad_to=8),
    ),
    pokes=(
        Poke(0x40079248, H("48780005"), H("48780006"), "machine chooser has six rows, WAVE the last"),
        Poke(0x400585FA, H("48780005"), H("48780006"), "SRC SETUP selector has six rows"),
        Poke(0x4003C950, H("7204"), H("7205"), "SRC SETUP name lookup admits WAVE"),
        Poke(0x40078678, H("7004"), H("7005"), "machine chooser draws WAVE"),
        Poke(0x400786CE, H("7004"), H("7005"), "machine chooser highlights WAVE"),
        Poke(0x40079904, H("7604"), H("7605"), "machine chooser persists WAVE"),
    ),
    conflicts=(
        ("SYNTH MACHINE", "both own the FLEX renderer entry 0x400d6438, the PLAYBACK resolver load "
                          "0x40031ece and the command-byte copy 0x4000c634"),
        ("BLACKPYRAMIDS_303", "both are a machine on row 5: shared detour sites (the machine chooser, SRC "
                              "SETUP, the Part validator) and pokes (the chooser's row count)"),
    ),
    gates=(Gate("modules/wavecf/test_wavecf.py", remix_arg=False),),
)
