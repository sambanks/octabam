"""DRUMMER -- one FLEX track playing its sliced drum sample as a drummer.

Phase 4a (test images only): the engine runs live on the DRUMMER tracks
(dr_on in hooks.s: T1), with a built-in kit. Its knobs are the track's
PLAYBACK page (A STYLE, B DENS, C CPLX, D HUMAN, E BRK, F SEED), read with
scenes and LFOs applied. The machine row, the pages' own labels, the KIT
window and drummer.work come in phases 4b-4d (INVESTIGATION.md).

  0x400a2d82  sequencer tick, after the step builder: the engine decides the
              step (adds a trig, moves it, or plays the track's own)
  0x4000d3ae  the packer, once its page-record pointer is set: the knobs are
              copied out, the page record gets the playback values
  0x400d6458  voice-start table, FLEX entry (SymbolRef): the hit's slice
              before the stock start 0x4000f450, its VOL after

All three were measured under the port (INVESTIGATION.md, phases 2 and 4).
"""
from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Poke, Proof, SymbolRef

H = bytes.fromhex

DETOURS = (
        Detour(0x400A2D82, H("71b98000668d"), "drummer", "dr_step_stub",
               "sequencer tick, after the step builder 0x4009d1e8: the engine's step"),
        Detour(0x4009DCA2, H("4fef0014206f006a"), "drummer", "dr_rebuild_stub",
               "rebuild (transport start, edits), after the step builder: the same decision", pad_to=8),
        Detour(0x4000D3AE, H("a93c00000020"), "drummer", "dr_frame_stub",
               "packer, page records set: DRUMMER knobs out, playback values in"),
)


def drummer_inc(modules, remix=None):
    """HAVE_PAGELOCKS: KIT BALANCE takes PAGES' locks (PAGES and EVENTS in the remix)."""
    return f".set HAVE_PAGELOCKS, {int('PAGES' in modules and 'EVENTS' in modules)}\n"


MODULE = Module(
    name="drummer",
    key="DRUMMER",
    kind=Kind.CF_PATCH,
    category=Category.MACHINES,
    author="djib", author_url="https://github.com/Djibdjib",
    proof=Proof.HARDWARE,
    proof_note="the author's MKII, images 52-78 (Nov 2026; REDRUM images 77-78, 9 Nov 2026); "
               "verify_port.py (12 cases, the firmware plays what the engine "
               "says, step by step), verify_store.py (drummer.work saved and read back), verify_drk.py (the kit file beside the sample), "
               "verify_kitmaker.py, verify_autokit.py, verify_live2.py, verify_next.py (NEXT's orders on the beat)",
    doc="DRUMMER machine: a sliced FLEX drum loop played as a drummer (styles, humanisation, BRK breaks on the crossfader).",
    requires=("STORE",),                # drummer.work (store.c), client 8
    linked=(Linked("drummer", "modules/drummer/drummer_unit.s", cpu="5475", dram=True, include=drummer_inc),),
    # The machine row (machine.s; ANALOG BD's seams, measured on the unit by repeat98)
    detours=DETOURS + (
        Detour(0x400334D8, H("2f02222f0008"), "drummer", "dr_machine_name", "format machine row 5 as DRUMMER"),
        Detour(0x4003C928, H("4bf9400a78c8"), "drummer", "dr_src_names", "SRC SETUP's six machine names",
               kind="lea"),
        Detour(0x4003D718, H("41f9400a78c8"), "drummer", "dr_name_a", "main page name of a DRUMMER track"),
        Detour(0x4004C36A, H("41f9400a78c8"), "drummer", "dr_name_b", "second main page name lookup"),
        Detour(0x4003C980, H("71104fef0018"), "drummer", "dr_setup_row", "SRC SETUP highlights DRUMMER"),
        Detour(0x400786C8, H("7110b480662e"), "drummer", "dr_chooser_row", "machine list highlights DRUMMER"),
        Detour(0x400585DC, H("161079034879400bb704"), "drummer", "dr_setup_open", "SRC SETUP opens on DRUMMER",
               pad_to=10),
        Detour(0x4005221E, H("4ebaff1c4eb94007e940"), "drummer", "dr_tick_hook",
               "publish DRUMMER's page as row 5's", pad_to=10),
        Detour(0x40078886, H("71102f004879460e7386"), "drummer", "dr_chooser_open",
               "the machine list opens on DRUMMER", pad_to=10),
        Detour(0x40031E74, H("710541f9400d5f386050"), "drummer", "dr_resolve_pb",
               "a DRUMMER track's PLAYBACK pages are DRUMMER's", pad_to=10),
        Detour(0x4003BFF0, H("711041f9400d5f38605a"), "drummer", "dr_lfo_pb",
               "an LFO destination on a DRUMMER track's SRC page names DRUMMER's knobs", pad_to=10),
        Detour(0x4007981C, H("77101084d081"), "drummer", "dr_main_commit", "machine list commit signs DRUMMER"),
        Detour(0x4005A616, H("2239460d5c30"), "drummer", "dr_src_commit", "SRC SETUP commit signs DRUMMER"),
        Detour(0x4005A850, H("2239460d5c30"), "drummer", "dr_src_commit2", "SRC SETUP's second commit path"),
        Detour(0x4003D1C0, H("2f02202f00082239460d1a48"), "drummer", "dr_setup_key",
               "SRC SETUP: RIGHT on DRUMMER's row opens FLEX's slot list (the sample)"),
        Detour(0x4003A52E, H("2002e788d4829082"), "drummer", "dr_setup_edit6",
               "SETUP's editor stores DRUMMER's row in the FLEX slot", pad_to=8),
        Detour(0x4003CD98, H("2e06e78fdc869e86"), "drummer", "dr_setup_draw6",
               "SETUP's drawer reads DRUMMER's row from the FLEX slot", pad_to=8),
        Detour(0x40002318, H("4fefffa048d77cfc"), "drummer", "dr_validate",
               "the Part validator keeps a DRUMMER track's knob bytes", pad_to=8),
        Detour(0x40084854, H("4eb940000d002440588f"), "drummer", "dr_on_job",
               "the engine task's receive runs a DRUMMER job (the kit file, type 0x42)", pad_to=10),
    ),
    pokes=(
        Poke(0x40079248, H("48780005"), H("48780006"), "machine list has six rows, DRUMMER the last"),
        Poke(0x400585FA, H("48780005"), H("48780006"), "SRC SETUP selector has six rows"),
        Poke(0x4003C950, H("7204"), H("7205"), "SRC SETUP name lookup admits DRUMMER"),
        Poke(0x40078678, H("7004"), H("7005"), "machine list draws DRUMMER"),
        Poke(0x400786CE, H("7004"), H("7005"), "machine list highlights DRUMMER"),
        Poke(0x40079904, H("7604"), H("7605"), "machine list persists DRUMMER"),
    ),
    symbol_refs=(
        SymbolRef(0x400D6458, 0x4000F450, "drummer", "dr_start_stub",
                  "voice-start table, FLEX entry: the hit's slice and VOL"),
    ),
    conflicts=(
        ("DRUMMER PROBE", "the probe takes the same sites"),
        ("CX OSC", "both replace the FLEX start entry 0x400d6458 (a HOOKS chain is needed); both row 5"),
        ("ANALOG BD", "row 5 of the machine list and its seams, until DRUMMER joins HOOKS machine_rows"),
        ("OCTA303", "row 5 of the machine list and its seams, until DRUMMER joins HOOKS machine_rows"),
    ),
    gates=(Gate("modules/drummer/verify.py", remix_arg=False),),
)
