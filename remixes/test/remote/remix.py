"""REMOTE's event records on the stock effects, with the USB module that answers the read."""
from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="remote", family="mods", evidence=(Evidence(Level.EMULATOR, ref="verify_remote", note="not run on a unit"),),
    doc="Stock effects with REMOTE's event ring, read over USB.",
    modules=("REMOTE", "STORE", "USB", *stock.EFFECTS),
    fallback="NONE",
)
