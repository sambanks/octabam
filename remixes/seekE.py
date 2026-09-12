"""seekE -- OCTABAM82 plus the recorder-spacing cave: the candidate fix for the last residual.

82 (`seekB`) removed the restart transient and the play-side seam and left a
-26 dB, ~1 ms scuff on ALTERNATE BARS at 128 BPM, absent at 65.6 -- the length
converter's constant length against the sequencer's alternating arm spacing
(RTOS_FORK 10.53, confirmed on the unit by the tempo test). `RECORDER SPACING`
makes each pass exactly as long as the gap to its next arm, derived from the
current arm with no lane and no stored state (10.56) -- where `RECORDER SEAM`
asked the lane and was falsified (10.55).

UNFLASHED. Gate it under the port first: the cave's substitute path must be
taken with L' alternating 82,687/82,688 on `out/n128_card.img` (the same site
scored 0/1,200 for recorder-seam), and the golden card must be byte-identical
to stock. Then the self-loop at 128, FX off, internal clock, tone amp 0.05,
>= 60 s, `out/hw/softretrig/gaps.py` with the per-bar maximum; 65.6 control.
"""

from remix.schema import Remix

REMIX = Remix(
    name="seekE",
    doc="bus + seek-bind + counter hold + the recorder-spacing cave (RTOS_FORK 10.56).",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND", "TEMPO SYNC",
             "FLEX SEEK BIND", "FLEX SEEK BIND CTR", "RECORDER SPACING"),
    fallback="SEND",
)
