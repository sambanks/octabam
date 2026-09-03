"""restored -- `bus` plus every stock FX2 effect that can sit beside it.

The shipping trio and tempo sync, then the seven stock effects the build
had been hiding for no resource reason: FILTER, EQUALIZER, DJ EQ, PHASER,
COMPRESSOR, LO-FI and the Echo Freeze DELAY. They cost nothing -- no code
is placed, no descriptor cloned, no words spent; each is one chooser row
pointing at the descriptor stock already ships (tools/remix/stock.py).

The four stock effects NOT here -- SPATIALIZER, FLANGER, CHORUS, COMB --
allocate an instance buffer per track, on exactly the addresses BusVerb's
tank and BusDelay's line hardcode, so the ledger refuses them beside a
server. They are legal in an insert-only remix (`mutables` could carry all
eleven).

Ten chooser rows, so this is also the remix that exercises the LONG list
cave and the scrolling viewport (build_bus.py LONG_LIST) -- the first
image with more than seven rows. ⚠️ Unflashed: scrolling past row seven on
the real panel is inferred from stock's own fifteen-row list, not measured
on ours.
"""

from remix.schema import Remix

REMIX = Remix(
    name="restored",
    doc="`bus` + the seven stock FX2 effects that coexist with the servers.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "COMPRESSOR", "LO-FI",
             "DELAY", "TEMPO SYNC"),
    fallback="SEND",
)
