"""stations -- the BamSep26 stations beside the reverb bus, as they land.

A station is a bus client, so it needs a bus to render into: the reverb
server and SEND (the fallback). FILTER is replaced by the station, so its
727 words are ground; every other stock effect keeps its code.
"""
from remix.schema import Remix
REMIX = Remix(name="stations", doc="the stations so far (FILTER STATION) + ChonVerb + SEND",
              modules=("REVERB SERVER", "SEND", "FILTER STATION"), fallback="SEND",
              fx1=("FILTER STATION", "DJ EQ", "COMPRESSOR", "LO-FI"))
