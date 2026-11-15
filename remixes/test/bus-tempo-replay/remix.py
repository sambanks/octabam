"""bus-tempo-replay -- bus with TEMPO SYNC's CAVE at REPLAY: a diagnostic image.

scripts/refhash.sh builds it (case tempocave-replay). BusDelay's panel name
reads BusDlyRPL. Not a remix to flash for playing.
"""

from remix.schema import Pin, Evidence, Level, Remix

REMIX = Remix(
    name="bus-tempo-replay",
    family="reference", evidence=(Evidence(Level.EMULATOR),),
    doc="bus with TEMPO SYNC's CAVE pinned REPLAY (diagnostic).",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND", "TEMPO SYNC"),
    fallback="SEND",
    settings={("octabam.tempo-sync", "CAVE"): Pin("REPLAY")},
)
