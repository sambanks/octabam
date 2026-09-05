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

THE HOSTS CARRY THEIR OWN SEND PAIR (5 Sep 2026, Sam: "the plan was real
send knobs"). Design pass 2 first found the arithmetic refused -- both
engines used all twelve slots -- so each gave one up: BusVerb's HP and LP
became one TONE knob (slot 3) and slot 4 is its -DEL; BusDelay dropped the
drive and slot 10 is its -DEL. With IN / -VRB already on the pages, each
host now has its send into its own engine and into the other. Every other
track's sends are on its station. SEND is kept as the FALLBACK, so a fresh
or unassigned track still dispatches to real code, and it is the one row
the FX2 chooser carries.

BUS SCREEN IS IN THE RIG (5 Sep 2026): CONTROL -> REVERB / DELAY opens the
twelve-row editor. It fits because (a) the screen is now three caves -- its
menu-state table floats first in the clone window, its handler and data are
pinned into the second zero run where MENU SHORTCUT used to sit; (b) a
BLANKED module gets no label formatters and no TIME formatter (build rule),
which freed ~800 B; (c) the dormant 13th return-row code was stripped. The
tag-91 lesson stands: nothing is pinned at or above 0x400d8000.

SEND IS VISIBLE (5 Sep 2026): hidden, it was blanked with the hosts and every
non-host FX2 page drew no knobs. It is the FX2 chooser's one row and the
labelled ->DEL / ->VRB pair on every station track. Only the two hosts are
blank-named; the bus screen (and CC 62-67, modules/ccpage2) edit them.
"""

from remix.schema import Remix

REMIX = Remix(
    name="bamsep27",
    doc="Design pass 2: the rig with the engines hidden and no stock delay.",
    # BUS SCREEN replaces MENU SHORTCUT (5 Sep 2026): CONTROL -> REVERB / DELAY
    # opens the twelve-row editor. It is listed BEFORE TEMPO SYNC so its
    # floating menu-state table is placed first in the clone window; its
    # handler and data are pinned into the second zero run.
    modules=("REVERB SERVER", "DELAY SERVER", "SEND",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "BUS SCREEN", "TEMPO SYNC", "CC PAGE 2"),
    # SEND is NOT hidden any more (5 Sep 2026): hiding it blanked its two knob
    # names, so every non-host track's FX2 page drew no knobs at all. Visible,
    # it is the labelled send pair (->DEL / ->VRB) the design asked for, and
    # the one row the FX2 chooser carries.
    hidden=("REVERB SERVER", "DELAY SERVER",
            "SPECTRUM", "CHARACTER", "MODULATION"),
    grains=2,          # the cycle lever: four stations beside the delay
    fallback="SEND",
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
