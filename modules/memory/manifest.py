"""MEMORY -- the platform's reserve in stock's audio page arena, sized per
remix from what its modules claim.

Every remix with a DRAM unit carries it (tools/remix/registry.remix
appends it). It has no code. The build (tools/build/build_bus.py, the
MEMORY section) sizes the reserve, octabam's platform pages at the
bottom of the arena (tools/remix/arena.py):
  - the linked runtime of every `dram=True` unit, its packed loader stage
    and its .bss (a sizing link at the largest reserve finds the top);
  - every DramRegion, stacked down from the reserve's ceiling;
  - every ArenaReserve, a fixed-address claim the reserve reaches past
    (REMIX SWITCH's image stage, Analog BD's pre-boot upload scratch).
The build report prints the per-module table and the pages left for
samples and recorders. The ledger refuses declared claims past the floor
(arena.MIN_PAGES_LEFT pages stay), two overlapping fixed claims, and a
fixed claim in a remix with no DRAM unit. A module that declares a
DramRegion or an ArenaReserve requires MEMORY.

Until 11 Oct 2026 the reserve was a fixed 1,707 pages (10 MiB) in every
remix with a DRAM unit.
"""

from remix.schema import Category, Gate, Kind, Module, Evidence, Level

MODULE = Module(
    name="memory",
    key="MEMORY",
    kind=Kind.CF_PATCH,
    category=Category.SETTINGS, author="Sam Banks", author_url="https://github.com/sambanks",
    evidence=(Evidence(Level.UNIT, unit="MKII", who="sambanks", date="2026-10-16",
        note="cursory testing on Sam's MKII (owner report, 16 Oct 2026); the reserve's size per remix in the build"
             " report; `verify_dram_boot` under the port"),),
    doc="Platform: the DRAM reserve in stock's audio page arena, sized from what the remix's modules claim.",
    # nothing but stock writes the pages the reserve gave back, under the
    # gate project, on bottleservice and bus (gate.py)
    gates=(Gate("modules/memory/gate.py", venv=True, once=True),),
)
