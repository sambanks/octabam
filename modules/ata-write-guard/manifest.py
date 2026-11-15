"""ATA WRITE GUARD: keep stock's initial PIO write critical section intact
until its buffer pointer and remaining-sector count describe the sent data.

The stock routine masks interrupts for the command store, restores SR at
0x40014cf2, sends the first sector, then updates its globals. A task switch
after the final data word can let the completion interrupt see the old
count and poll DRQ forever. Measured under the port.
"""
from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Poke, Evidence, Level

MODULE = Module(
    name="ata-write-guard", key="ATA WRITE GUARD", kind=Kind.CF_PATCH,
    category=Category.FIXES, author="sambanks", author_url="https://github.com/sambanks",
    evidence=(Evidence(Level.UNIT, unit="MKII", who="sambanks", date="2026-10-16",
        note="cursory testing on Sam's MKII (owner report, 16 Oct 2026); forced completion interrupt and full DSP-"
             "enabled project load under the port, 15 Oct 2026; not on hardware"),),
    doc="Keeps the first PIO card sector and its pointer/count update atomic against interrupts; restores the caller's interrupt mask before returning.",
    linked=(Linked("ata_write_guard", "modules/ata-write-guard/guard.s", dram=True),),
    pokes=(Poke(0x40014cf2, bytes.fromhex("46c0"), bytes.fromhex("3600"),
                "retain the saved SR in d3; leave stock's interrupt mask raised through first-sector bookkeeping"),),
    detours=(Detour(0x40014d58, bytes.fromhex("2002241f261f"), "ata_write_guard", "ata_write_return",
                    "first PIO sector return: restore SR, return status and the saved d2/d3"),),
    gates=(Gate("tools/verify/verify_ata_write.py", stage="image"),),
)
