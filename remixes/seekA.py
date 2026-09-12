"""seekA -- bus + the FLEX seek-bind cave (lever A). Hardware test image for RTOS_FORK 10.48/10.49; unflashed."""

from remix.schema import Remix

REMIX = Remix(
    name="seekA",
    doc="bus + the FLEX seek-bind cave (lever A).",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND", "TEMPO SYNC", "FLEX SEEK BIND"),
    fallback="SEND",
)
