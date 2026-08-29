"""mutables -- the Mutable-Instruments-flavoured insert collection.

Five inserts on one card: WarpFold (ring mod / wavefolder), Ripple (driven
SVF filter), Rungs (8-mode modal resonator), Streamz (a vactrol lowpass
gate) and BodeShift (a frequency shifter). Inserts stack, unlike the
servers -- each is in both payloads, any track can host any of them, several
at once -- so this remix carries the whole set where `warped` carries one.

SEND is the fallback and the housekeeper, as everywhere; both servers' ids
degrade to it. No ColdFire caves.
"""

from remix.schema import Remix

REMIX = Remix(
    name="mutables",
    doc="Five MI-flavoured inserts: WarpFold, Ripple, Rungs, Streamz, BodeShift.",
    modules=("WARPFOLD", "RIPPLE", "RUNGS", "STREAMZ", "BODESHIFT", "SEND"),
    fallback="SEND",
)
