"""busscreen -- the bus image plus the menu-state-table growth (step 1 of the
twelve-row MAIN MENU editor, docs/MAINMENU.md 9e). Same servers as `bus`;
adds BUS SCREEN, which grows the menu-state table from 16 entries to 17."""

from remix.schema import Remix

REMIX = Remix(
    name="busscreen",
    doc="bus + the menu-state table grown to 17 (foundation for the editor screen).",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND", "TEMPO SYNC", "BUS SCREEN"),
    fallback="SEND",
)
