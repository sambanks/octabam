"""BamSep27 -- the rig with the engines off the chooser (design pass 2).

The second design pass, built one step at a time. What is different from
`bamsep26` today:

  * BusVerb and BusDelay are HIDDEN -- placed, dispatched and cloned, but on
    no chooser row and drawn with no knobs. A track hosts an engine because
    the project says so, not because somebody turned the chooser, and the
    engines' controls belong on the two main-menu screens (docs/MAINMENU.md
    section 6, not built yet).
  * The stock DELAY row is gone. Flash 4 (4 Sep 2026) wedged the unit every
    time a part LOADED with it selected -- a squeal that survived a project
    change and needed a power cycle, where re-selecting the same effect on
    the panel did not. Unexplained, and not worth explaining: the rig does
    not want it.

Still to come before this remix is the rig: the sends move off the stations
and onto the engines' otherwise blank pages, GRAIN drops to two grains (the
cycle lever the delay core needs once the stations are actually turned up),
and the two menu screens.

⚠️ An id dispatches the same code on every track, so hiding an engine does
not stop an old part naming it on some other track. What stops that is the
engine reading its own allocator slot and passing dry off its host, the
idiom modules/modulation already uses. Not built yet either.
"""

from remix.schema import Remix

REMIX = Remix(
    name="bamsep27",
    doc="Design pass 2: the rig with the engines hidden and no stock delay.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "MENU SHORTCUT"),
    hidden=("REVERB SERVER", "DELAY SERVER"),
    fallback="SEND",
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
