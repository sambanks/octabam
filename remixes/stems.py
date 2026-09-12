"""STEMS -- the STEM REC proof of concept, alone.

T1 to the card while the sequencer plays, from MAIN MENU > CONTROL > STEM
REC (docs/superpowers/specs/2026-09-10-stem-rec-poc-design.md). Nothing
else, so a first flash can only fail in one module's ways.
"""

from remix.schema import Remix

REMIX = Remix(
    name="stems",
    doc="STEM REC proof of concept: T1 to the card, alone.",
    modules=("STEM REC",),
    fallback="NONE",
)
