"""bothslots -- the WarpFold insert on BOTH effect slots, and nothing else.

The first remix to use `Remix.fx1`, and the point of it: until 3 Sep 2026 a
module of ours could only be reached from the FX2 slot. Not for any DSP
reason -- the dispatch tables are indexed by the raw id and shared by both
menus, so WarpFold's code already ran the moment FX1 selected 0x0a -- but
because FX1's chooser list ends at 0x400d608c and FX2's begins four bytes
later, so it could not grow where it sat. It moves into the cave instead,
exactly as the FX2 list already does when it outgrows its own.

It costs no words: 68 bytes of cave for the relocated list, and FX1's own id
and cursor tables written for the one new row. What it DOES cost is cycles.
FX1 is four more slots on the same four tracks, so the worst per-core load
goes from 4x WarpFold to 8x -- 404 to 808 of the 3,120 our code may spend
(`make cycles`). That trade is the whole reason this is a per-remix choice
rather than a property of the module.

⚠️ UNFLASHED. The FX1 chooser has been seen only in the local ColdFire
emulator, which draws it with the firmware's own code: `WarpFold78` appears
as row 11 of a twelve-entry list, the page draws its own knob names
(DRV/FREQ/TONE/MODE/MIX), and the cursor opens on that row rather than on
row 0 -- which is what FX1's cursor table being written looks like.
"""

from remix.schema import Remix

REMIX = Remix(
    name="bothslots",
    doc="WarpFold, listed on FX1 as well as FX2. No bus, no servers.",
    modules=("WARPFOLD",),
    fallback="NONE",
    fx1=("WARPFOLD",),
)
