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
    Spectrum    the Spectrum station, on FILTER's old id 0x04, FX1 only
    Character   replaces LO-FI   (id 0x1c), FX1 only (and the return on T8)
    Modulation  on CHORUS's old id 0x12, FX1 only
    TEMPO SYNC  the two ColdFire caves: BusDelay's TIME reads 1/8 rather
                than milliseconds
    MENU SHORTCUT  MAIN MENU > CONTROL > REVERB / DELAY jumps to whichever
                track hosts that server, and opens its FX2 page

FOUR FX2 rows (the two engines, SEND, the stock DELAY) and FX1 = NONE plus
the three stations. THE STATIONS ARE FX1-ONLY (12 Sep 2026): each takes the
FX1 row of the stock effect it replaces, so a saved part that chose FILTER
runs the Spectrum station -- which is why all three default to a bit-exact
passthrough -- and none takes an FX2 row: a station named on FX2 (the id is
the stock effect's, shared by both menus) runs as a dry pass, decided from
the allocator base at init (Claims.fx1_only, proven by each station's gate).
That is what closes the rig's cycle envelope: with a station on both slots
of four tracks a core priced 4,830 against 3,120 usable; FX1-only the worst
core is 3,567 (four Characters beside the delay) -- over the flat line by
the counter's own error margin and under the FILTER-credited one, which the
burn sweep on hardware is to settle (tools/harness/pressure.py).

⚠️ EVERY OTHER STOCK EFFECT IS HARVESTED. Thirteen effects, 6,158 words per
payload in one contiguous run, and an old project that still names one of
them gets silence rather than noise (the null stub). The three the stations
replace keep their ids and get OUR code instead.

The stations carry NO SENDS since the one-aux rig (7 Sep 2026): every
track's AUX is on its FX2 (SEND, or an engine's own slot 0), the chain is
delay -> reverb, and the return is Character in SAT=BUS on T8's FX1. The
stations' former send slots (page 1, 4-5) are blank.
"""

from remix.schema import Remix

REMIX = Remix(
    name="bamsep26",
    doc="The rig: bus (BusVerb + BusDelay) + three stations + the stock delay.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND", "DELAY",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "MENU SHORTCUT"),
    fallback="SEND",
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
