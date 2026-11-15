"""tapeecho -- the Spring Reverb replacement, alone.

Tape Echo runs on the ColdFire in the stock per-track delay rings and owns
no DSP tape buffer. Select it in FX2 where SPRING REV normally appears.
This minimal remix contains the CPU engine in isolation. Stock DELAY remains
available for the verifier's patched-firmware baseline comparison.
"""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="tapeecho",
    family="effects", evidence=(Evidence(Level.UNIT,
        note="the author's unit (OCTACLID4): six instances; a seventh freezes it, open"),),
    doc="Tape Echo replacing Spring Reverb, alone.",
    modules=("TAPE ECHO",),
    fallback="NONE",
)
