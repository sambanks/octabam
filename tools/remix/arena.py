"""The audio page arena, and how a remix takes pages of it for DRAM.

Stock keeps one arena of 6,144-byte pages for Flex samples and the track
recorders -- 14,602 pages plus an unused index 0, 89,720,832 B, Elektron's
"85.5 MB available to a project":

    0x40a955e0 .. 0x46025de0     base + (14,602 + 1) x 6,144

Its geometry is four literals in the pool's cold init (`0x40096f24`,
run at main init and again inside LOAD PROJECT) and one base address in
24 instructions across the engine. Every DRAM mod with a hardware record
lives here by shrinking it: Octakit takes the TOP 528 pages (her four
recipe writes cut the count to 14,074 and the clear to match -- her
RUNTIME_START..END exactly), octamax 2.0 takes the BOTTOM 64 pages by
moving the base. This module does both, for any number of reservations
at once: bottom reservations stack upward from the stock base (the base
literal moves past them), top reservations stack downward from the end
(the count shrinks), and the four geometry literals are computed from the
total. With Octakit alone the result is byte-identical to her own writes.

The cost is linear and honest: N pages = N x 6 KB of sample/recorder
memory, off the recorder share by default (Flex keeps its 64 MB cap).
Nothing else changes. The region a reservation yields is never touched by
the OS again: the arena clear starts at the new base, the boot-time
copies at the base follow the literal, and the page allocator can only
hand out indexes below the new count (docs/remixer/PLACEMENT.md).
"""

from __future__ import annotations

from dataclasses import dataclass

BASE = 0x40A955E0
PAGE = 6144
PAGES = 14602                         # usable pages; index 0 is a header slot
END = BASE + (PAGES + 1) * PAGE       # 0x46025de0

# The 23 instructions whose 32-bit immediate/absolute operand IS the base
# (operand at instruction + 2), and one derived use, base + one page.
BASE_SITES = (
    0x4000045C, 0x4000046A, 0x400004C6, 0x400072A6, 0x40007642, 0x4000D5C0,
    0x400254F8, 0x4006C106, 0x40093432, 0x40094A0A, 0x40094A3C, 0x40094A9C,
    0x40095B28, 0x40095BBA, 0x40095C18, 0x40095C78, 0x40095CC2, 0x4009618C,
    0x400963C4, 0x4009700C, 0x4009761E, 0x40097748, 0x40098650,
)
DERIVED_SITES = ((0x40094A62, PAGE),)          # lea base+6144 (page 1)
# (OPERAND address, stock value, what it is) -- these are the 32-bit
# immediates of `movel #14602,%d6` (0x40096f80), `cmpil #14603,%d0`
# (0x40096faa), `movel #0x05590800,%sp@-` (0x40097006) and `movel
# #14602,%d0` (0x40097124); Octakit's guards name the same four words.
COUNT_SITE = (0x40096F82, PAGES, "page count")
FILL_SITE = (0x40096FAC, PAGES + 1, "free-list fill limit")
CLEAR_SITE = (0x40097008, (PAGES + 1) * PAGE, "arena clear length")
CAP_SITE = (0x40097126, PAGES, "recorder page cap")
# Octakit's four recipe writes ARE these four literals; her module names
# them so the build computes them instead of applying hers verbatim.
OCTAKIT_RECIPE_WRITES = ("reserve-audio-page-free-list-tail",
                         "shorten-audio-page-free-list-initializer",
                         "shorten-audio-page-arena-clear",
                         "cap-recorder-page-allocation")
# The platform's own reservation when a remix carries DRAM units: 1,707
# pages = 10,487,808 B (10 MiB + 2 KB), Sam's call, 10 Sep 2026.
PLATFORM_PAGES = 1707
MIN_PAGES_LEFT = 2048                 # 12 MB for the unit; below this, refuse


@dataclass(frozen=True)
class Placed:
    owner: str
    where: str
    pages: int
    start: int
    end: int


def layout(reservations):
    """reservations: [(owner, where, pages)] -> (placed list, new base, count).
    Bottom reservations in the given order from the stock base upward; top
    ones from the end downward (the first top reservation is the topmost,
    which is where Octakit's link.ld puts hers)."""
    placed = []
    lo = BASE
    for owner, where, pages in reservations:
        if where == "bottom":
            placed.append(Placed(owner, where, pages, lo, lo + pages * PAGE))
            lo += pages * PAGE
    hi = END
    for owner, where, pages in reservations:
        if where == "top":
            placed.append(Placed(owner, where, pages, hi - pages * PAGE, hi))
            hi -= pages * PAGE
    count = (hi - lo) // PAGE - 1
    if count < MIN_PAGES_LEFT:
        raise SystemExit(f"arena: {PAGES - count} pages reserved leaves {count} "
                         f"({count * PAGE // 1048576} MB) for samples and recorders; "
                         f"the floor is {MIN_PAGES_LEFT}")
    return placed, lo, count


def pokes(reservations):
    """Every OS-image write the reservations need, as (addr, expect, write,
    note) on the 4-byte operands: the base at its 24 sites, then the four
    geometry literals. Empty when nothing is reserved."""
    if not reservations:
        return []
    placed, base, count = layout(reservations)
    out = []
    if base != BASE:
        for s in BASE_SITES:
            out.append((s + 2, BASE.to_bytes(4, "big"), base.to_bytes(4, "big"),
                        "arena base"))
        for s, off in DERIVED_SITES:
            out.append((s + 2, (BASE + off).to_bytes(4, "big"),
                        (base + off).to_bytes(4, "big"), f"arena base + {off}"))
    for (operand, stock, what), new in ((COUNT_SITE, count), (FILL_SITE, count + 1),
                                        (CLEAR_SITE, (count + 1) * PAGE), (CAP_SITE, count)):
        if new != stock:
            out.append((operand, stock.to_bytes(4, "big"), new.to_bytes(4, "big"), what))
    return out
