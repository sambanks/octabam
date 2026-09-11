"""seekB-seam -- lever B plus the recorder-length cave.

⚠️ FALSIFIED BEFORE FLASHING (RTOS_FORK 10.55): on the self-loop geometry
(RLEN 16, one recorder trig per bar) the seam cave's lane lookahead resolves
to a PAST event, its L' comes out 0, and the ±1 guard refuses on all 1,200
calls in a 1,200-frame port run -- the image is SAFE but INERT here. Kept as
the demonstration that the composition is legal (ledger-clean, check-green).
Do not flash it expecting the scuff to go. Lever D (§10.16.6: end a fixed-RLEN
recording AT the next arm) is the remaining candidate.

OCTABAM82 (`seekB`) removed the restart transient and the play-side seam
and left one residual: a -26 dB, ~1 ms scuff on every OTHER bar at 128 BPM,
absent at 65.6 (RTOS_FORK 10.52). That parity is the length converter's
arithmetic, not the bind's: at 128 BPM / RLEN 16 the converter returns a
CONSTANT 82,688 samples while the sequencer arms alternately 82,687 and
82,688 samples apart, so on every short pass the recorder is re-armed one
sample before it finishes and the buffer's last sample is a pass-old
leftover -- which 82's free-running read head now walks straight through.
At 65.6 / 120 / 125 the converter's quotient is an exact integer, the
spacing does not alternate, and there is no leftover.

`RECORDER SEAM` is the cave that re-derives the length per pass from the
sequencer's own next step event, so the recording ends exactly where the
next one begins. It was flashed once (tag 21, 7-8 Sep) and falsified -- but
against the restart-dominated click, which was 30 dB louder than anything
it could fix. On 82 it is the only thing left above the floor.

Score it on the self-loop at 128 BPM, FX off, internal clock, tone amp 0.05,
>= 60 s (the beat is 37 s), with `out/hw/softretrig/gaps.py` and a per-bar
maximum -- and at 65.6 as the no-change control.
"""

from remix.schema import Remix

REMIX = Remix(
    name="seekB-seam",
    doc="bus + seek-bind + counter hold + the recorder-length cave (RTOS_FORK 10.52's next lever).",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND", "TEMPO SYNC",
             "FLEX SEEK BIND", "FLEX SEEK BIND CTR", "RECORDER SEAM"),
    fallback="SEND",
)
