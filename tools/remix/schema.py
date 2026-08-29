"""What a remix module declares about itself.

A *module* is one contribution to the firmware: an FX2 engine, a bus client,
a ColdFire behaviour patch, or a combination. A *remix* is a named selection
of modules composed into one image. This file is the vocabulary both sides
speak.

The point of a typed manifest here is not tidiness. Almost every expensive
failure this project has had was two mechanisms disagreeing about one effect
-- a descriptor that drew a knob publishing nothing, a formatter inherited
from a donor overriding the value count it was given, a knob-to-slot map
copied into six files and stale in four. A manifest is the one place those
facts are written down, so a contributor states them once and the build,
the checks and the harness all read the same statement.

WHAT IS CONSUMED TODAY. This schema is deliberately narrower than the full
architecture: it declares what the build actually reads right now. Resource
claims (Y regions, r7 slots, cave ranges) and the ColdFire patch type get
their fields when the ledger that checks them exists -- a declared-but-
unchecked claim is worse than no claim, because it reads like a guarantee.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Kind(Enum):
    """What sort of contribution this is."""

    DSP_EFFECT = "dsp_effect"   # an FX2 engine: menu entry + DSP code
    DSP_CLIENT = "dsp_client"   # DSP code + menu entry, but serves no bus
    CF_PATCH = "cf_patch"       # ColdFire behaviour only, no DSP code
    HYBRID = "hybrid"           # both, e.g. an engine plus a display cave


class BusRole(Enum):
    """How the module relates to the cross-core send bus."""

    NONE = "none"
    CLIENT = "client"   # writes an accumulator (SEND)
    SERVER = "server"   # owns an accumulator and consumes it


class Formatter(Enum):
    """How the panel DRAWS a parameter -- which outranks its value count.

    A cloned descriptor inherits the donor's formatter for every slot, and
    the formatter decides how the value is rendered regardless of the count
    written beside it. That is not a subtlety: it shipped on the 17 Aug 2026
    flash, where BongDelay cloned SPRING REV and three of six page-2 slots
    drew wrong -- WOW drew no knob at all (an enumerated renderer with three
    labels asked to draw 0..127), MODE drew as a bipolar balance dial reading
    -64..-60. Every field those checks knew about was correct.

    So a module states the renderer per slot rather than inheriting one by
    accident.
    """

    INHERIT = "inherit"   # leave the donor's formatter untouched
    PLAIN = "plain"       # stock numeric knob: both formatter words zero
    STEPPED = "stepped"   # enumerated selector (the CHORUS.TAPS renderer)


@dataclass(frozen=True)
class Param:
    """One of the twelve parameter slots on an effect's two pages.

    `None` means "do not write this field", which leaves the donor's value in
    place. That is a real and different thing from writing a zero.

    Page 1 is slots 0-5 (r6+0..5). Page 2 is slots 6-11, and is THREE KNOBS
    AND THREE SELECTS by hardware budget: knob, select, knob, select, knob,
    select. The selects are the companion byte fields, which is why any
    stepped slot lands on 7, 9 or 11 by construction.
    """

    name: bytes | None = None          # 6-byte panel label; b"" blanks it
    default: int | None = None         # u8 written at P+0x5e+idx
    count: int | None = None           # value count; None leaves the donor's
    active: bool = False               # drawn at all (the enable bitmap)
    formatter: Formatter = Formatter.INHERIT

    def __post_init__(self):
        if self.name is not None and len(self.name) > 6:
            raise ValueError(f"param name {self.name!r} exceeds 6 bytes")
        # A default outside its own count is used as an INDEX. That shipped
        # once -- slot 7 defaulted to 64 with a count of 5 -- and stalled the
        # sequencer on hardware after two steps.
        if self.count is not None and self.default is not None:
            if not 0 <= self.default < self.count:
                raise ValueError(
                    f"default {self.default} is outside its value count "
                    f"{self.count} -- the panel uses it as an index")


@dataclass(frozen=True)
class MenuEntry:
    """The module's presence in the FX2 chooser.

    Every field here is written into a descriptor CLONED from a stock donor,
    and anything not written stays the donor's. That inheritance is the whole
    hazard: see Formatter.
    """

    fx2_id: int
    donor_desc: int                    # E address of the stock donor
    abbr: bytes                        # 5-byte short name
    fullname: bytes                    # 13-byte panel name, before any tag
    build_tag: bool = False            # append the image's build tag

    def __post_init__(self):
        # 0x00-0x03 are the ids stock treats as bare synonyms for "no effect";
        # the first hardware test used them and got correct names with dead
        # knobs and garbage audio.
        if not 0x04 <= self.fx2_id <= 0x1f:
            raise ValueError(f"fx2 id 0x{self.fx2_id:02x} is out of range "
                             f"(0x00-0x03 are stock's 'no effect' synonyms)")
        if len(self.abbr) > 5:
            raise ValueError(f"abbr {self.abbr!r} exceeds 5 bytes")
        if len(self.fullname) > 13:
            raise ValueError(f"fullname {self.fullname!r} exceeds 13 bytes")


@dataclass(frozen=True)
class DspSection:
    """The module's DSP56300 code.

    `priority` is the placement order within the donor region and it is
    BYTE-LOAD-BEARING: the region is packed in this order, so changing it
    moves every module after it and changes the image. Lowest goes first;
    the highest number gets the region's trailing free words.
    """

    asm: str                                   # default source, repo-relative
    priority: int
    payloads: frozenset[str] = frozenset({"A", "B"})
    bus_role: BusRole = BusRole.NONE
    ybase_substituted: bool = False            # rewrite $30000 to the payload's
    r7_latch_slot: int | None = None           # rotation-latch state word
    gate_label: str | None = None              # where the housekeeping gate jumps
    override_markers: tuple[str, ...] = ()     # ";_OVERRIDE" hooks it honours


@dataclass(frozen=True)
class FormatterReg:
    """A cave installing itself as some module's per-parameter display formatter.

    Cross-module by nature: the cave belongs to one module and the slot it
    draws belongs to another. Naming the target here is what lets a remix
    that omits the target skip the registration instead of writing a pointer
    into a descriptor that was never cloned.
    """

    module: str        # target module KEY, e.g. "DELAY SERVER"
    slot: int          # which of its twelve parameters this formatter draws


@dataclass(frozen=True)
class CavePatch:
    """ColdFire machine code planted in free space, optionally hooked.

    This is how a module changes the firmware's BEHAVIOUR rather than adding
    an effect -- how parts, kits, menus or formatters get new logic. The
    pattern is always the same: assert the hook site still holds the stock
    bytes, plant a `jsr` to the cave, and have the cave replay what it
    displaced before doing its own work.

    `pinned` is the hardware-ratified machine code and is what actually gets
    written. `source` is re-assembled and compared against it when an m68k
    toolchain is present, so the build needs no toolchain but a source that
    has drifted from the bytes we ship cannot pass unnoticed.

    ⚠️ A cave that filters on effect ids has those ids compiled INTO `pinned`.
    Changing a module's fx2 id therefore does not change the cave, and the
    two fall out of agreement silently. The tempo cave is the live example.
    """

    label: str                          # name used in the build report
    cave_addr: int
    pinned: bytes
    source: str | None = None           # .s re-assembled and compared
    hook_addr: int | None = None        # where the jsr is planted
    hook_stock: bytes = b""             # bytes that MUST be there first
    registers_formatter: FormatterReg | None = None


@dataclass(frozen=True)
class Harness:
    """Metadata the local test tools need, so they stop keeping their own copy.

    The knob-name to slot map is NOT here: it is derived from `Module.params`,
    because that map existing in more than one place is precisely the defect
    this is meant to end.
    """

    layout_char: str | None = None    # its letter in send_probe layout strings
    is_server: bool = False


@dataclass(frozen=True)
class Module:
    """One contribution, as declared by modules/<name>/manifest.py."""

    name: str                    # directory slug, e.g. "chonverb"
    key: str                     # build/report identifier, e.g. "REVERB SERVER"
                                 # -- REPORT-VISIBLE: verify_delay and
                                 # verify_roll parse it out of build stdout,
                                 # so it is API, not a label
    kind: Kind
    doc: str                     # one line for the module index
    menu: MenuEntry | None = None
    params: tuple[Param, ...] = ()
    dsp: DspSection | None = None
    cf_patches: tuple[CavePatch, ...] = ()
    harness: Harness | None = None

    def __post_init__(self):
        if self.params and len(self.params) != 12:
            raise ValueError(f"{self.name}: expected 12 param slots, "
                             f"got {len(self.params)}")
        # Page 2's three selects ARE the three companion byte fields, so a
        # stepped control can only physically live on 7, 9 or 11.
        for i, p in enumerate(self.params):
            if p.formatter is Formatter.STEPPED and i not in (7, 9, 11):
                raise ValueError(
                    f"{self.name}: slot {i} is stepped, but the companion "
                    f"byte fields are slots 7, 9 and 11")

    @property
    def active_params(self) -> list[int]:
        """Slots the panel draws -- the enable bitmap, in index order."""
        return [i for i, p in enumerate(self.params) if p.active]

    @property
    def stepped_slots(self) -> tuple[int, ...]:
        return tuple(i for i, p in enumerate(self.params)
                     if p.formatter is Formatter.STEPPED)

    def knob_map(self) -> dict[str, int]:
        """Panel label -> slot index, for the test harness.

        THE single source of this map. It used to be hand-copied into
        send_probe, render_reverb, verify_delay, verify_bus, the build tables
        and the docs; four of those carry a comment about a time they drifted.
        """
        return {p.name.decode(): i for i, p in enumerate(self.params)
                if p.name}
