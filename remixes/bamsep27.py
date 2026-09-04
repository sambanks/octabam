"""BamSep27 -- the rig with an empty FX2 chooser (design pass 2).

Every track is the same shape: a STATION on FX1, carrying that track's two
bus sends, and NOTHING on FX2. What differs from `bamsep26`:

  * NOTHING IS ON THE FX2 CHOOSER -- zero rows. The two engines, the SEND
    client and the three stations are all placed, dispatched and cloned, and
    none of them is listed. A track hosts an engine because the project says
    so; a station is chosen on FX1; and an FX2 slot is simply empty.
  * The engines and SEND are drawn BLANK: their twelve names are cleared, so
    the host's FX2 page shows nothing at all. The stations keep their names,
    because one descriptor serves both menus and blanking them would empty
    their FX1 page too.
  * Each engine also gets the HOST GUARD: it runs on the bank's first FX2
    state block and passes dry on every other, so an old part naming its id
    on another track cannot start a second instance writing the host's tank.
  * The stock DELAY row is gone. Flash 4 (4 Sep 2026) wedged the unit every
    time a part LOADED with it selected -- a squeal that survived a project
    change and needed a power cycle, where re-selecting the same effect on
    the panel did not. Unexplained, and not worth explaining: the rig does
    not want it.

⚠️ THE SENDS STAY ON THE STATIONS. Design pass 2 first moved them to FX2,
and the arithmetic refused: both engines already use all twelve parameter
slots, and putting their controls on a menu screen frees none of them --
the screen edits those same twelve. Sends on the stations are uniform
anyway, since every track has one. SEND is kept only as the FALLBACK, so a
fresh or unassigned track still dispatches to real code, and it is hidden
too: its knobs default to 0, so such a track is inert and looks like every
other empty FX2.

⚠️ BUS SCREEN (the twelve-row editor) is NOT in the rig yet. It floats its
cave in the decoded free band, and the rig's clones + label formatters fill
that band, so it does not fit. Pinning it into the image tail crashed on
[PROJ] (tag 91: that tail is OS bss, not free space). The rig keeps MENU
SHORTCUT for now; screen-in-rig waits on a split cave or a trimmed rig. The
plain `busscreen` remix carries the screen and floats it safely.
"""

from remix.schema import Remix

REMIX = Remix(
    name="bamsep27",
    doc="Design pass 2: the rig with the engines hidden and no stock delay.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "MENU SHORTCUT"),
    hidden=("REVERB SERVER", "DELAY SERVER", "SEND",
            "SPECTRUM", "CHARACTER", "MODULATION"),
    grains=2,          # the cycle lever: four stations beside the delay
    fallback="SEND",
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
