"""RECFIX -- the recorder length fix, ALONE: one ColdFire cave, nothing else.

The minimal image for testing RTOS_FORK 10.53's defect in isolation. It
carries `RECORDER SPACING` and no DSP code at all -- no effects, no menu
changes, no FX2 ids, no bus -- so the FX2 list, every stock effect and every
other behaviour are the stock 1.40C ones, and anything that changes in the
recorder is attributable to the cave and nothing else.

WHY A SOLO BUILD. The fix landed on hardware as OCTABAM83, which is 82
(`seekB`: bus + the two seek-bind caves) PLUS this cave, so the three fixes
have only ever been tested stacked:

  * lever A (`FLEX SEEK BIND`)      removed the voice-restart transient
  * lever B (`FLEX SEEK BIND CTR`)  removed the read-pointer seam
  * this cave                       removed the length scuff

Each was measured on its own symptom (10.50/10.51/10.58) so all three are
real, but "is this cave alone enough?" is UNANSWERED -- and it is the
question that decides what the community is asked to flash. One cave is a
much easier ask than three. This remix is how that gets answered, and it is
also the build to hand someone who only wants the recorder fixed.

WHAT IT SHOULD DO. At any tempo whose bar is a whole number of samples
(65.6, 120, 125, 126, 135, 140, 144, 150 -- 46 of the 1401 tempi from 60.0
to 200.0) the cave is a BIT-EXACT no-op: it writes back the length that was
already there, proven for all 11,208 (tempo, RLEN) pairs and observed on
21,000 port calls. At every other tempo it makes each recorder pass exactly
as long as the gap to its next arm.

  docs/firmware/RECORDER_CLICK.md -- the reproduction steps.
"""

from remix.schema import Remix

REMIX = Remix(
    name="recfix",
    doc="Minimal build: the recorder length fix (RECORDER SPACING) alone, no DSP code.",
    modules=("RECORDER SPACING",),
    fallback="NONE",
)
