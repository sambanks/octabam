"""warped -- WarpFold on every track, the send bus idle underneath.

The first remix built around an OUTSIDER module: WarpFold is an insert with
no bus role, placed in BOTH payloads, so any of the eight tracks can host
one. SEND is here as the fallback (a saved project's stale id degrades to a
send, per the standing rule) and because a remix without it would leave
nothing to housekeep the bus scratch; nothing consumes its accumulators in
this selection, which is harmless -- the housekeeper clears them each block.

Neither server fits beside a new effect in one donor region, so this remix
carries neither; their ids fall back to SEND like every other absent id.
"""

from remix.schema import Remix

REMIX = Remix(
    name="warped",
    doc="WarpFold insert + send bus only. No servers, no ColdFire caves.",
    modules=("WARPFOLD", "SEND"),
    fallback="SEND",
)
