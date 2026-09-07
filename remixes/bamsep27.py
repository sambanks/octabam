"""BamSep27 -- the ONE-AUX rig (7 Sep 2026; design pass 2 before that).

Every track is the same shape: a STATION on FX1 (processing only -- the
stations have no sends since the one-aux rig), and on FX2 either SEND (one
knob, AUX) or an engine whose slot 0 is that same AUX. The bus is ONE aux:
AUX -> BusDelay (T1) -> BusVerb (T5) -> the return on T8 (Character, SAT=BUS,
RET). docs/BUS.md "The one aux bus". What differs from `bamsep26`:

  * NOTHING IS ON THE FX2 CHOOSER -- zero rows. The two engines, the SEND
    client and the three stations are all placed, dispatched and cloned, and
    none of them is listed. A track hosts an engine because the project says
    so; a station is chosen on FX1; and an FX2 slot is simply empty.
  * The engines are NAMED (tag 17, 6 Sep 2026): off the chooser, but the
    host's FX2 page draws all twelve knobs, labelled, sends among them, so T5
    and T1 read like any track. (Tags 15-16 drew them BLANK -- dials with no
    labels, "the worst result possible" -- for a bus screen whose CONTROL
    rows never appeared on the unit.) The stations keep their names too:
    one descriptor serves both menus.
  * Each engine also gets the HOST GUARD: it runs on the bank's first FX2
    state block and passes dry on every other, so an old part naming its id
    on another track cannot start a second instance writing the host's tank.
  * The stock DELAY row is gone. Flash 4 (4 Sep 2026) wedged the unit every
    time a part LOADED with it selected -- a squeal that survived a project
    change and needed a power cycle, where re-selecting the same effect on
    the panel did not. Unexplained, and not worth explaining: the rig does
    not want it.

THE HOSTS CARRY ONE SEND, AUX, AT SLOT 0 (the one-aux rig, 7 Sep 2026): the
same knob every track has, so a host page reads like any track's. The slot
came from IN / -VRB (retired: the chain is hardwired) and MIX took slot 5 as
each engine's stage crossfade; TONE stays merged and the delay's DRV stays
dropped (the recovered slot went to MIX). SEND is the FALLBACK, so a fresh or
unassigned track still dispatches to real code, and it is the one row the
FX2 chooser carries. The SEND is refused on T8 by construction.

BUS SCREEN IS OUT OF THE RIG (6 Sep 2026, tag 17): on tag 16 the CONTROL
menu showed its stock six rows although the image carried eight (count and
pointer patched at 0x400cbd54) -- the firmware reads that menu from somewhere
the patch does not reach. It goes back when the ColdFire emulator's own menu
shows the rows. When it was in (5 Sep 2026) it fit because (a) the screen is now three caves -- its
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
             "TEMPO SYNC", "CC PAGE 2"),
    # SEND is NOT hidden any more (5 Sep 2026): hiding it blanked its two knob
    # names, so every non-host track's FX2 page drew no knobs at all. Visible,
    # it is the labelled send pair (->DEL / ->VRB) the design asked for, and
    # the one row the FX2 chooser carries.
    hidden=("REVERB SERVER", "DELAY SERVER",
            "SPECTRUM", "CHARACTER", "MODULATION"),
    # THE HOSTS ARE NAMED (6 Sep 2026, tag 17): off the chooser, but T5's and
    # T1's FX2 pages draw all twelve knobs, labelled, sends among them. Tag
    # 16 shipped them BLANK (dials, no labels -- "the worst result possible",
    # Sam) because the bus screen was to edit them, and its CONTROL rows
    # never appeared on the unit. BUS SCREEN is out of the rig until it draws
    # in the emulator's own menu; its module and verifier stay in the tree.
    named=("REVERB SERVER", "DELAY SERVER"),
    grains=2,          # the cycle lever: four stations beside the delay
    fallback="SEND",
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
