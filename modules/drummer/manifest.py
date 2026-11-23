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
import runpy
from pathlib import Path

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Evidence, Level, SymbolRef

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
    """HAVE_PAGELOCKS: KIT BALANCE takes PAGES' locks (pages/manifest.py: its locks unit linked)."""
    pages = runpy.run_path(str(Path(__file__).parents[1] / "pages/manifest.py"))
    have = any(entry[0] == "DRUMMER" for entry in pages["lock_clients"](modules))
    return f".set HAVE_PAGELOCKS, {int(have)}\n"


MODULE = Module(
    name="drummer",
    key="DRUMMER",
    kind=Kind.CF_PATCH,
    category=Category.MACHINES,
    author="djib", author_url="https://github.com/Djibdjib",
    evidence=(Evidence(Level.UNIT, unit="MKII", who="djib", date="2026-11-09",
        note="images 52-78 (Nov 2026; REDRUM images 77-78, 9 Nov 2026); verify_port.py (12 cases, the firmware "
             "plays what the engine says, step by step), verify_store.py (drummer.work saved and read back), "
             "verify_drk.py (the kit file beside the sample), verify_kitmaker.py, verify_autokit.py, "
             "verify_live2.py, verify_next.py (NEXT's orders on the beat)"),),
    doc="DRUMMER machine: a sliced FLEX drum loop played as a drummer (styles, humanisation, BRK breaks on the crossfader).",
    requires=("STORE", "MACHINES", "PAGES"),   # drummer.work (store.c), client 8; the machine row; KIT BALANCE and NEXT
    linked=(Linked("drummer", "modules/drummer/drummer_unit.s", cpu="5475", dram=True, include=drummer_inc),),
    # The machine row is MACHINES's (modules/machines): DRUMMER is a client (CLIENTS there),
    # with its page, its tick and the KIT BALANCE bytes the validator must not see (adapter.c).
    detours=DETOURS + (
        Detour(0x40084854, H("4eb940000d002440588f"), "drummer", "dr_on_job",
               "the engine task's receive runs a DRUMMER job (the kit file, type 0x42)", pad_to=10),
    ),
    symbol_refs=(
        SymbolRef(0x400D6458, 0x4000F450, "drummer", "dr_start_stub",
                  "voice-start table, FLEX entry: the hit's slice and VOL"),
    ),
    conflicts=(
        ("DRUMMER PROBE", "the probe takes the same sites"),
        ("CX OSC", "both replace the FLEX start entry 0x400d6458 (a chain is needed)"),
    ),
    gates=(Gate("modules/drummer/verify.py", remix_arg=False),
           # PAGES' locks on KIT BALANCE: the panel, the steps' life, SAVE PROJECT and a boot
           # (its own synthetic card; SKIPs without PAGES' locks)
           Gate("modules/pages/verify_locks.py", venv=True, stage="image"),),
)
