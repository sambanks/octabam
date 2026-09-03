"""BamSep26 -- the rig: the bus (BusVerb + BusDelay), three stations, and the stock delay.

The image the set runs on. Design page:
https://claude.ai/code/artifact/1f1bfff2-9d4e-41b6-b0a7-91a3c8989aaf

    BusVerb    the shared reverb, hosted on one of tracks 5-8
    BusDelay   the shared delay (v5: CLEAN / pitched GRAIN / REVERSE),
                hosted on one of tracks 1-4, with its own ->VRB
    Send        the plain two-knob client, for a track with no station
    DELAY       stock Echo Freeze, per track: it runs on the ColdFire and
                costs the DSP nothing, so every track can have its own delay
                IN PARALLEL with the shared reverb -- which the stock box
                cannot do, because only a station's send reaches the bus
    FilterStn   replaces FILTER  (id 0x04)
    Character   replaces LO-FI   (id 0x1c)
    ModStn      replaces CHORUS  (id 0x12), FX1 only
    TEMPO SYNC  the two ColdFire caves: BusDelay's TIME reads 1/8 rather
                than milliseconds
    MENU SHORTCUT  MAIN MENU > CONTROL > REVERB / DELAY jumps to whichever
                track hosts that server, and opens its FX2 page

Seven FX2 rows, which is exactly the in-place chooser list -- no scrolling.
FX1 is NONE plus the three stations: every station takes the FX1 row of the
stock effect it replaces, so a saved part that chose FILTER now runs the
filter station, which is why all three default to a bit-exact passthrough.

⚠️ EVERY OTHER STOCK EFFECT IS HARVESTED. Thirteen effects, 6,158 words per
payload in one contiguous run, and an old project that still names one of
them gets silence rather than noise (the null stub). The three the stations
replace keep their ids and get OUR code instead.

⚠️ The stations are BUS CLIENTS: ->DEL and ->VRB on page 1, scene-lockable,
registered only when the knob is up, and none of them housekeeps. An FX1
participant on the bus has never run on hardware -- docs/FLASHPLAN.md's
flash 4 is where that claim is tested.
"""

from remix.schema import Remix

REMIX = Remix(
    name="bamsep26",
    doc="The rig: bus (BusVerb + BusDelay) + three stations + the stock delay.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND", "DELAY",
             "FILTER STATION", "CHARACTER STATION", "MODULATION STATION",
             "TEMPO SYNC", "MENU SHORTCUT"),
    fallback="SEND",
    fx1=("FILTER STATION", "CHARACTER STATION", "MODULATION STATION"),
)
