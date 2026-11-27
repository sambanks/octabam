"""The first-sector PIO write guard on the stock effects."""
from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="ata-write-guard", family="mods", evidence=(Evidence(Level.EMULATOR,
        note="forced completion-interrupt gate under the port; not on hardware"),),
    doc="Stock effects with the first PIO card write guarded through bookkeeping.",
    modules=("ATA WRITE GUARD", *stock.EFFECTS),
    fallback="NONE",
)
