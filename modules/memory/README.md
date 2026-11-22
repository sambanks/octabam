# MEMORY

Platform module. Owns octabam's reserve in stock's audio page arena and sizes it per remix from what the remix's modules claim. Every remix with a DRAM unit carries it; the registry appends it. It has no code.

## The reserve

Stock keeps one arena of 6,144-byte pages for Flex samples and the track recorders: 14,602 pages at `0x40a955e0` (`tools/remix/arena.py`). octabam's platform takes pages off the bottom by moving the arena's base literal at its 23 sites and rewriting the four geometry words. Until 11 Oct 2026 it took a fixed 1,707 pages (10,487,808 B) in every remix with a DRAM unit.

The reserve now holds exactly what is claimed, in whole pages:

| claim | declared by | where |
|---|---|---|
| the linked runtime (code and data) | each `Linked(..., dram=True)` unit, plus the build's descriptor clones and label formatters | from the reserve's base |
| the runtime's `.bss` | the same units (KITS' library, PLOCKS P2's table) | after the runtime |
| the loader stage | the packed runtime, dead after the boot depack | page-aligned after the runtime |
| a `DramRegion` | the module (STEM REC's ring, stack and buffers) | stacked down from the reserve's ceiling, below any fixed claim |
| an `ArenaReserve` | the module, at a fixed address (REMIX SWITCH's image stage `0x41200000..0x41495de0`, Analog BD's pre-boot upload scratch `0x40b00000..0x40c00000`) | the reserve reaches past it |

The build links the runtime once at the largest reserve the arena allows (`arena.MAX_RESERVE`, which leaves `arena.MIN_PAGES_LEFT` pages) to find the runtime's top. It then takes the fewest pages that hold that top, every region and every fixed claim (`platform_build.pages_needed`), and links again at that size. If the packed stage grew past the reserve in that link, it adds a page and links once more. The report prints:

```
=== MEMORY: the platform's arena reserve ===
  <module>    <units>  <code+data>  <.bss>
  (descriptor clones) / (label formatters) / (link alignment) / loader stage
  <module> <region>       DramRegion at <address>
  <module> <claim>        ArenaReserve at <address>
  arena: octabam platform takes N pages at the bottom, <base>..<end> (<bytes>)
  arena: base <new base>, <pages> pages (<MB>) left for samples and recorders (stock 14,602)
```

## Refusals

- The ledger: declared regions and fixed claims past `arena.MAX_RESERVE`; two fixed claims that overlap; a fixed claim in a remix with no DRAM unit.
- The build: a fixed claim under the runtime, its stage or its `.bss`; a reserve that would leave fewer than `arena.MIN_PAGES_LEFT` pages.
- A module that declares a `DramRegion` or an `ArenaReserve` requires MEMORY (STEM REC, REMIX SWITCH, ANALOG BD).

## Declaring a claim

```python
from remix.schema import ArenaReserve, DramRegion

dram_regions=(DramRegion("my_ring", 0x100000),),               # linked by symbol
arena_reserves=(ArenaReserve("my stage", 0x40b00000, 0x40000),),  # fixed address
requires=("MEMORY",),
```

A unit's `.bss` needs no declaration; the link measures it.
