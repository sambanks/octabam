"""verbonly -- ChonVerb and the send bus, with no delay and no ColdFire caves.

A deliberately reduced selection, and the smallest thing that proves a remix
is a real choice rather than a label: BongDelay is not built, not placed and
not listed, its id falls back to the send client, and neither tempo cave is
installed.
"""

from remix.schema import Remix

REMIX = Remix(
    name="verbonly",
    doc="ChonVerb + send bus only. No delay, no ColdFire caves.",
    modules=("REVERB SERVER", "SEND"),
    fallback="SEND",
)
