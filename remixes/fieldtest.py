"""fieldtest -- one image that puts three never-flashed claims on the unit.

Built to be FLASHED, and shaped so that a failure says which claim broke:

1. **The insert card.** Five inserts of ours on the FX2 chooser, so four
   copies of the dearest can be put on one core's four tracks -- the cycle
   test `tools/cycle_count.py` can only bound. A wedge there is the cliff
   PLAN.md section 2 describes; a wrong SOUND is a module's own bug.
2. **A module on FX1.** WarpFold takes an FX1 row, which needs FX1's chooser
   list relocated into the cave, its three `lea` references repointed, and
   FX1's own id and cursor tables written. Emulator-verified only. A failure
   here is a MENU failure -- a missing row, a wrong page, a cursor on the
   wrong line -- and cannot be confused with (1).
3. **A donor region beyond the three reverbs.** CHORUS and FLANGER are on
   neither chooser, so their words join the region: 3,342 rather than 2,724,
   and our code is placed at FLANGER's address. Nothing has EVER overwritten
   a non-reverb stock effect on hardware. The measurement says every effect
   is self-contained (tools/dsp_reach.py, both payloads); what it cannot say
   is whether anything outside the DSP cares. A failure here is anything
   ELSE misbehaving -- an unrelated stock effect, a crash on part load --
   and is the reason CHORUS and FLANGER are dropped rather than, say, FILTER
   (the default FX1 effect, which every project touches).

⚠️ SPATIALIZER and COMB FILTER stay listed on FX1 deliberately. They
allocate an instance buffer at the addresses our servers pin, so keeping
them is what proves the ledger's coexistence rule the right way round -- and
this image carries no server, so there is nothing for them to collide with.

⚠️ NO SERVER, so no bus: the fallback is the firmware's own NONE, and an
unimplemented id is silence rather than a send.
"""

from remix.schema import Remix

REMIX = Remix(
    name="fieldtest",
    doc="Five inserts, one of them on FX1, placed in a region beyond the reverbs.",
    modules=("WARPFOLD", "RIPPLE", "RUNGS", "STREAMZ", "BODESHIFT"),
    fallback="NONE",
    # FX1 without CHORUS or FLANGER -- with neither on the FX2 chooser
    # either, that is what gives up their words.
    fx1=("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "SPATIALIZER",
         "COMB FILTER", "COMPRESSOR", "LO-FI", "WARPFOLD"),
)
