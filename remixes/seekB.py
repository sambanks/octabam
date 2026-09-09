"""seekB -- bus + seek-bind + its counter half (lever B). Hardware test image for RTOS_FORK 10.48/10.49; unflashed."""

from remix.schema import Remix

REMIX = Remix(
    name="seekB",
    doc="bus + seek-bind + its counter half (lever B).",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND", "TEMPO SYNC", "FLEX SEEK BIND", "FLEX SEEK BIND CTR"),
    fallback="SEND",
)
