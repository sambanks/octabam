"""WarpFold -- a Mutable-Instruments-Warps-flavoured ring modulator / wavefolder.

The first OUTSIDER module: an effect built entirely against the manifest
contract, with no build_bus.py knowledge of its own. Unlike the two servers it
is a plain per-track INSERT -- no bus role, no shared-window buffers, placed in
BOTH payloads -- so it runs on any of the eight tracks, and several tracks can
run their own instance at once.

Algorithm (modules/warpfold/warp_fold.asm):
  FOLD  -- drive the input 1..8x and reflect it back through +/-1 with the
           wrap-and-reflect identity fold(v) = 2*|wrap((v+1)/2)| - 1, computed
           from an A1 extraction so no logical op ever leaves A2 stale.
  RING  -- multiply by an internal carrier (triangle phase accumulator shaped
           to a parabolic sine), ~20 Hz..3 kHz on a squared taper.
  BOTH  -- fold first, then ring the folded signal.
All state lives in the instance's own r7 block; persistent words are masked on
load AND save per the two-track-freeze discipline.

DRV=0 makes FOLD an exact identity and MIX=0 is an exact passthrough, so the
effect nulls against its input at either extreme -- the render harness uses
both as correctness gates.
"""

from remix.schema import (BusRole, DspSection, Formatter, Harness, Kind,
                          MenuEntry, Module, Param, YBase)

_PLAIN = Formatter.PLAIN
_STEP = Formatter.STEPPED

MODULE = Module(
    name="warpfold",
    key="WARPFOLD",
    kind=Kind.DSP_EFFECT,
    doc="Warps-style insert: wavefolder + ring mod, FOLD/RING/BOTH.",
    menu=MenuEntry(
        fx2_id=0x0a,
        donor_desc=0x400d58b8,        # DARK REV, same donor as ChonVerb
        abbr=b"WFLD",
        fullname=b"WarpFold",
        build_tag=True,
    ),
    params=(
        # ---- page 1 -------------------------------------------------------
        # DRV 0 is an exact identity through the folder (gain 1x never
        # reaches the reflection), so a fresh instance in FOLD mode passes
        # audio untouched until the knob moves -- deliberate, after SHMR's
        # lesson about defaults that were never revisited.
        Param(b"DRV", 0, active=True, formatter=_PLAIN),
        Param(b"FREQ", 48, active=True, formatter=_PLAIN),
        # TONE 127 is the filter nearly wide open (one-pole coefficient
        # ~0.98); it exists to tame fold harshness, not to be a filter.
        Param(b"TONE", 127, active=True, formatter=_PLAIN),
        Param(b"MIX", 127, active=True, formatter=_PLAIN),
        Param(), Param(),
        # ---- page 2: knob, select, knob, select, knob, select -------------
        Param(),
        Param(b"MODE", 0, 3, active=True, formatter=_STEP),   # FOLD/RING/BOTH
        Param(), Param(), Param(), Param(),
    ),
    dsp=DspSection(
        asm="modules/warpfold/warp_fold.asm",
        priority=5,                   # after every shipping module
        bus_role=BusRole.NONE,
        ybase=YBase.NEVER,            # no shared-window buffers at all
        r7_latch_slot=None,
        gate_label=None,
    ),
    harness=Harness(layout_char="W", is_server=False),
)
