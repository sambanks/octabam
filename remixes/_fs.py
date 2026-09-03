"""_fs -- scratch: the FILTER STATION beside the reverb bus, for its gates.

A station is a bus client, so it needs a bus to render into: the reverb
server and SEND (the fallback). FILTER is replaced by the station, so its
727 words are ground; every other stock effect keeps its code.
"""
from remix.schema import Remix
REMIX = Remix(name="_fs", doc="scratch: FILTER STATION + ChonVerb + SEND",
              modules=("REVERB SERVER", "SEND", "FILTER STATION"), fallback="SEND",
              fx1=("FILTER STATION", "DJ EQ", "COMPRESSOR", "LO-FI"))
