"""STEMS -- STEM REC alone.

Every track to the card while the sequencer plays, one file each, from
MAIN MENU > CONTROL > STEM REC, streamed while it records (docs/superpowers/
specs/2026-09-22-stem-rec-streaming-design.md). Nothing else, so a first
flash can only fail in one module's ways.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="stems",
    family="mods", proof=Proof.PORT, proof_note="`verify_stems` under the ColdFire port; never flashed",
    doc="STEM REC alone: every track to the card while the sequencer plays, streamed.",
    modules=("STEM REC",),
    fallback="NONE",
)
