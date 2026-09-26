"""bamsep26 -- the rig: the bus, three stations, the stock delay.

FX2: one chooser row, SEND (the fallback: one AUX knob). BusVerb (T5) and
BusDelay (T1) have no row: `ot_project.py host <project>` hosts them, their
pages draw their twelve knobs, and either is a dry pass on any other track
(22 Sep 2026; until then both were rows, BusVerb ran on any of T5-8,
BusDelay on T1-4, and the stock DELAY had a row). FX1 rows: NONE + the three stations, each on the id of the stock
effect it replaces (Spectrum = FILTER 0x04, Character = LO-FI 0x1c,
Modulation = CHORUS 0x12) and FX1-only; a station named on FX2 runs dry.
Each station defaults to a bit-exact passthrough, so a saved part that
chose the stock effect still plays.

The bus is one aux: SEND -> BusDelay -> BusVerb, each engine's wet printed
on the track that hosts it (20 Sep 2026; until then a return on T8 through
Character). TEMPO SYNC makes BusDelay's TIME read divisions; CC
PAGE 2 puts CC 62-67 on the host engine's page-2 slots; MODE DEFAULTS
re-defaults a mode's knobs when MODE is turned on the panel.

Every other stock effect is harvested: 13 effects, 6,158 words per payload
in one run; a saved part naming one gets silence (the null stub).

On Sam's unit. Worst core priced 3,657 cycles (four Characters beside the
reverb, `make cycles`, 20 Sep 2026) against 3,120 usable -- inside the
counter's error margin, settled by the hardware burn sweep.
"""

from remix.schema import Remix

REMIX = Remix(
    name="bamsep26",
    doc="The rig: bus (BusVerb on T5 + BusDelay on T1) + three stations.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "CC MAP", "MODE DEFAULTS", "RIG HOSTS", "TEMPO BUS",
             "SCENES P2"),
    fallback="SEND",
    # 22 Sep 2026: the engines have NO chooser row (hidden) and run on their
    # host slots only (BusDelay on T1, BusVerb on T5; the HOSTGUARD body: a
    # dry pass anywhere else). The FX2 chooser is SEND alone; `ot_project.py
    # host <project>` puts the engines on T1/T5 and SEND everywhere else.
    # Sam: nothing else selectable. 26 Sep 2026: the host pages draw DEL and
    # REV (slots 0/1, the host's own sends), as the SEND tracks do; every
    # other engine knob is on the TEMPO window (TEMPO BUS).
    hidden=("REVERB SERVER", "DELAY SERVER"),
    host_slots=(("DELAY SERVER", 2), ("REVERB SERVER", 2)),
    locked=("REVERB SERVER", "DELAY SERVER"),
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
