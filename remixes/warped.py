"""warped -- WarpFold on every track, and nothing else in the image.

The first remix built around an OUTSIDER module: WarpFold is an insert with
no bus role, placed in BOTH payloads, so any of the eight tracks can host
one. It carried SEND until 2 Sep 2026 -- as the fallback, and on the theory
that a remix without it would leave nothing to housekeep the bus scratch.
That theory had it backwards: with no server, nothing ever reads those
accumulators, so there is no bus in this image to keep. Unimplemented ids
resolve to the firmware's own NONE instead (schema.NO_FALLBACK), which is
what an unassigned track shows on a stock unit.

Neither server fits beside a new effect in one donor region, so this remix
carries neither; their ids fall back to NONE like every other absent id.
"""

from remix.schema import Remix

REMIX = Remix(
    name="warped",
    doc="The WarpFold insert, alone. No bus, no servers, no ColdFire caves.",
    modules=("WARPFOLD",),
    fallback="NONE",
)
