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
    STOCK = "stock"             # a STOCK FX2 effect kept in the chooser: no
                                # code, no clone, no words -- its descriptor
                                # and dispatch are already in the image; its
                                # params are read FROM that descriptor for the
                                # remixer and harness, never written back
                                # (tools/remix/stock.py is the whole list)


# The fifteen FX2 ids stock assigns (docs/PARAM_PAGES.md section 2). Both
# dispatch tables (X:0x215 init / X:0x235 process) are indexed by the RAW id
# and are SHARED BETWEEN FX1 AND FX2, so a module that answers to one of
# these hijacks the stock effect on both menus: its descriptor replaces the
# stock one in FX2_IDS and its code replaces the stock code wherever that id
# is selected, FX1 included. Found 2 Sep 2026 by making the stock effects
# first-class: Rungs had shipped on 0x0c (EQUALIZER's id) and Nimbus on 0x0d
# (DJ EQ's), so every image built since 29 Aug 2026 ran Rungs where FX1
# selected EQUALIZER -- and the remixes WITHOUT Rungs aliased 0x0c to SEND,
# which took FX1's EQUALIZER away in the shipping chongbong image too. Only
# a Kind.STOCK module may carry one of these.
STOCK_FX2_IDS = frozenset({0x04, 0x05, 0x08, 0x0c, 0x0d, 0x10, 0x11, 0x12,
                           0x13, 0x14, 0x15, 0x16, 0x18, 0x19, 0x1c})


class YBase(Enum):
    """When a module's `$30000` literal is rewritten to the payload's own base.

    Payload A owns 0x30000-0x37FFF of the shared window and payload B owns
    0x38000-0x3FFFF, so a module holding buffers there needs its base rewritten
    per payload. The rule is NOT the same for every module and the difference
    is load-bearing: the delay is substituted in every build, while the reverb
    is substituted only once the bus has been relocated into the shared window.

    ⚠️ The rewrite is a BLANKET string replace over the whole source, comments
    included. A module wanting a shared-window address that must NOT move to
    the other half cannot spell it `$30000`.
    """

    NEVER = "never"      # carries no such literal
    XBUS = "xbus"        # substituted only when the bus is relocated
    ALWAYS = "always"    # substituted in every build


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
    # Display-only, consumed by the remixer and never by the build (the
    # refhash gate proves it): one line saying what the knob DOES, and for a
    # select, what each value means. The unit's panel cannot show either, so
    # this is where a contributor answers "what is this?" once instead of in
    # a comment only readers of the manifest ever see.
    doc: str | None = None             # one line, ~70 chars, for the help row
    labels: tuple[str, ...] | None = None   # one short label per select value

    def __post_init__(self):
        if self.name is not None and len(self.name) > 6:
            raise ValueError(f"param name {self.name!r} exceeds 6 bytes")
        if self.labels is not None:
            if self.count is None or len(self.labels) != self.count:
                raise ValueError(
                    f"param {self.name!r}: {len(self.labels)} labels for a "
                    f"count of {self.count} -- one label per value, and only "
                    f"where a count is declared")
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
    # BOTH NAME FIELDS ARE NUL-TERMINATED, so their usable length is one less
    # than the field: abbr is 5 bytes = FOUR characters, fullname 13 bytes =
    # TWELVE (docs/PARAM_PAGES.md section 2). Filling a field exactly leaves
    # no terminator and the firmware's string read runs off the end of it --
    # see __post_init__.
    abbr: bytes                        # <=4 chars, in a 5-byte field
    fullname: bytes                    # <=12 chars, in a 13-byte field
    build_tag: bool = False            # append the image's build tag
    # ---- taking a STOCK effect's id, on purpose -------------------------
    # The key of the stock effect this module REPLACES, e.g. "LO-FI". Set it
    # and the module may carry that effect's fx2 id; leave it None and a
    # stock id is refused, which is the default and the safe one.
    #
    # WHAT YOU ARE ASKING FOR. The DSP dispatch tables are indexed by the raw
    # id and shared by both menus, so your code runs wherever that id is
    # selected -- FX2 and FX1 alike, and in every saved project that already
    # chose it. That is the POINT of an upgraded stock effect and it is also
    # the whole hazard: Rungs sat on EQUALIZER's 0x0c and Nimbus on DJ EQ's
    # 0x0d from 29 Aug to 2 Sep 2026, in every local image, and the remixes
    # WITHOUT them aliased those ids to SEND, taking FX1's EQUALIZER away
    # too. The difference now is that it is declared and checked rather than
    # accidental: a remix that omits a replacement leaves the stock effect
    # exactly as it found it (build_bus.py), and verify_replaces.py proves
    # both halves.
    #
    # ⚠️ IF YOUR REPLACEMENT ALLOCATES A BUFFER, SIZE IT FOR FX1. The host's
    # allocator keeps SEPARATE tables and they are not the same size
    # (measured, X:0x255 in both payloads): an FX2 slot is 16,384 words,
    # an FX1 slot is 3,072. Your code runs from BOTH menus the moment it
    # takes a stock id, so an effect that asks for a buffer and assumes the
    # FX2 size will overrun its allocation by 13,312 words the first time
    # somebody selects it on FX1. That is the same class as the stock
    # reverbs being FX2-only: they do not fit an FX1 allocation either.
    #
    # ✅ CHECKED SINCE 3 SEP 2026, where it can be. "Nothing checks this"
    # stood while a buffer size was invisible to the schema -- but the three
    # ways a module cannot survive on FX1 are declarable, and `Claims` and
    # `DspSection` already declare them, so `state.fx1_hazard()` decides and
    # build_bus.py refuses a replacement that inherits an FX1 row it cannot
    # take. What is still on you is the SIZE ITSELF: a module that declares
    # `stock_instance_buffer` is refused outright, so if you want the row you
    # must not use the allocator at all.
    #
    # FX1's DESCRIPTOR IS REPOINTED TOO. FX1_IDS (0x400d5f58) and FX2_IDS
    # (0x400d5fdc) are separate tables -- the DSP dispatch is shared, the
    # descriptors are not -- so a replacement that only took FX2 would RUN
    # from FX1 under the stock effect's knob names, which is "a slot can draw
    # a knob and publish nothing" in reverse. The build repoints both of
    # FX1's tables (its id lookup and the row the encoder scrolls), in place,
    # and verify_replaces.py checks both menus in both directions.
    replaces: str | None = None

    def __post_init__(self):
        # 0x00-0x03 are the ids stock treats as bare synonyms for "no effect";
        # the first hardware test used them and got correct names with dead
        # knobs and garbage audio.
        if not 0x04 <= self.fx2_id <= 0x1f:
            raise ValueError(f"fx2 id 0x{self.fx2_id:02x} is out of range "
                             f"(0x00-0x03 are stock's 'no effect' synonyms)")
        # ⚠️ FOUR, not five. The abbr field is 5 bytes NUL-TERMINATED, so a
        # 5-character abbreviation fills it with no terminator and whatever
        # reads the abbreviation as a C string runs past it into `fullname`.
        # Found on hardware 2 Sep 2026 by Bryan T, contributing the HELLO
        # WORLD module: `abbr=b"HELLO"` drew correctly and behaved normally
        # under manual knob use, and threw a line-F exception the moment a
        # parameter was LFO-MODULATED -- faulting PC 0x48454C4C, which is
        # "HELL". It presented as "custom effects cannot be modulated".
        #
        # A faulting PC made of the field's own ASCII is the signature of a
        # SMASHED RETURN ADDRESS, not merely a long read: something copies
        # the abbreviation into a fixed 5-byte destination, and the extra
        # characters land past it. INFERRED -- the copy has not been located
        # in the disassembly. Falsifier: a 5-char abbr whose overrun stays
        # printable but does not fault.
        #
        # What is MEASURED is the rule: all 30 of the firmware's own page
        # descriptors carry an abbr of 4 characters or fewer with byte 5
        # zero, every shipping module already did (WFLD, BODE, RPPL, RNGS,
        # STRM, ...), and hello at 5 was the sole crash. The build used to
        # accept it and silently overrun -- one evening to find, so it is a
        # refusal now.
        if len(self.abbr) > 4:
            raise ValueError(
                f"abbr {self.abbr!r} is {len(self.abbr)} characters -- the "
                f"field is 5 bytes NUL-TERMINATED, so 4 is the maximum. A "
                f"5th character leaves no terminator and the panel's string "
                f"read runs into fullname (crashes on LFO modulation).")
        # Same field shape, same reasoning: 13 bytes NUL-terminated. The
        # build tag is appended LATER, in build_bus.py, which is where the
        # tagged length is checked -- this cannot see it.
        if len(self.fullname) > 12:
            raise ValueError(
                f"fullname {self.fullname!r} is {len(self.fullname)} "
                f"characters -- the field is 13 bytes NUL-TERMINATED, so 12 "
                f"is the maximum.")


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
    ybase: YBase = YBase.NEVER                 # see YBase
    # DEV places this module outside its normal payload but it must keep its
    # SHIPPING shared-window base, or its buffers sweep the other payload's.
    dev_pin_ybase: int | None = None
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
    # Where the cave is planted. None = FLOATING: the build places it at
    # the first free address after whatever precedes it (the descriptor
    # clones, then earlier caves), rounded up to 0x80. A cave may float
    # only if its code is position-independent -- short branches and OS
    # absolutes, no absolute reference to itself -- which both tempo-sync
    # caves are. Pinned addresses stood until 3 Sep 2026, when a remix with
    # more than three descriptor clones ran the clone block straight into
    # the tempo cave at 0x400d7000: three clones end EXACTLY there, so the
    # shipping image had fit by arithmetic coincidence. For that image the
    # floating rule reproduces the old addresses byte for byte.
    cave_addr: int | None                # None = floating; pass it explicitly
    pinned: bytes
    source: str | None = None           # .s re-assembled and compared
    hook_addr: int | None = None        # where the jsr is planted
    hook_stock: bytes = b""             # bytes that MUST be there first
    registers_formatter: FormatterReg | None = None
    # Trailing prose for this cave's line in the build report, separator
    # included. The installer is generic; what a given cave actually DOES is
    # not, and the build report is the only place a human sees it.
    report_note: str = ""


@dataclass(frozen=True)
class Claims:
    """Resources a module reserves that the ledger cannot see for itself.

    Deliberately tiny. Anything derivable from the module's own source is
    derived rather than declared, because a scan cannot go stale and a
    hand-written claim can. This is only for what a module means to own but
    does not yet reference.
    """

    reserved_private_y: tuple[int, ...] = ()
    # Does this module hold memory in the per-core FX2 INSTANCE BUFFER region
    # Y:0x4000-0xBFFF? ChonVerb's eight tank lines live there and so does
    # Nimbus's granular line, and two such modules on one core silently
    # corrupt each other -- each works perfectly alone, which is the worst
    # shape a defect can have.
    #
    # DECLARED, where private-Y is derived, and the difference is not
    # laziness. A source scan cannot tell an address from a mask or a
    # constant: scanning for this range flags `and #>$7fff` and every
    # coefficient that happens to land in it, and docs/DSP.md 7c records
    # that static scanning could not find even the STOCK reverbs' buffers,
    # because they compute their bases at runtime. A checker that fires on
    # six modules out of eight teaches people to ignore it.
    #
    # ⚠️ This is narrower than "the shared 64K window", which PLAN.md still
    # lists as unledgered: this region's extents are established (DSP.md's
    # load map -- 2 FX2 instances of 16,384 words), so it can be written
    # down honestly. The shared window's are not, and a plausible claim
    # there would read as a guarantee.
    owns_fx2_buffers: bool = False
    # A STOCK effect that allocates an FX2 instance buffer through the host's
    # bump allocator (it reads X:0x213 at init -- docs/DSP.md section 10).
    # The allocator hands the buffer out PER TRACK SLOT: on core 0 the four
    # slots are Y:0x4000, 0x8000, 0x30000 and 0x34000, on core 1 0x4000,
    # 0x8000, 0x38000 and 0x3c000 -- and those are exactly the addresses
    # ChonVerb's tank, Nimbus's line and BongDelay's line hardcode. So a
    # buffered stock effect on the wrong track silently corrupts a server
    # on the same core, and the chooser is one list for all eight tracks,
    # so the build cannot tell which track it will land on. The ledger
    # refuses the pair. Measured 2 Sep 2026 by scanning the payload
    # disassembly for `x:>$213` reads: SPATIALIZER, FLANGER, CHORUS and
    # COMB read it; FILTER, EQ, DJ EQ, PHASER, COMPRESSOR and LO-FI do not.
    # (Falsifier: an effect reaching its base another way -- dsp_host's
    # -guard would show a stray write.)
    stock_instance_buffer: bool = False
    # HOW MUCH of the allocator's buffer the module touches, from its base.
    # None = "sized for an FX2 slot" (16,384 words), the stock reverbs'
    # shape and the reason they are FX2-only. A module that declares
    # buffer_words <= 3072 fits an FX1 slot and may take an FX1 row.
    buffer_words: int | None = None
    # FX1-ONLY BY DESIGN: the module reads its allocator base at init and,
    # when the base is an FX2 slot (>= 0x4000), runs as a dry pass and
    # WRITES NOTHING. That is what lets it sit beside a server: the FX2
    # slots it would otherwise be handed are ChonVerb's tank and
    # BongDelay's line, and the ledger refuses every other allocator
    # reader beside them for exactly that reason. The claim is a promise
    # the module's render gate must prove (an FX2-slot instance renders
    # bit-exact dry and dsp_host's guard sees no write above 0x3fff).
    fx1_only: bool = False

    def __post_init__(self):
        if self.buffer_words is not None and not self.stock_instance_buffer:
            raise ValueError("buffer_words without stock_instance_buffer: "
                             "only an allocator reader has a sized buffer")
        if self.fx1_only:
            if not self.stock_instance_buffer:
                raise ValueError("fx1_only is for allocator readers -- a "
                                 "buffer-free module runs on both menus")
            if self.buffer_words is None or self.buffer_words > 3072:
                raise ValueError("fx1_only needs buffer_words <= 3072: an "
                                 "FX1 slot is 3,072 words (docs/DSP.md 10)")


@dataclass(frozen=True)
class Harness:
    """Metadata the local test tools need, so they stop keeping their own copy.

    The knob-name to slot map is NOT here: it is derived from `Module.params`,
    because that map existing in more than one place is precisely the defect
    this is meant to end.
    """

    layout_char: str | None = None    # its letter in send_probe layout strings
    is_server: bool = False
    # Does this module take part in the cross-core bus as a CLIENT -- write
    # the shared accumulators and carry the housekeeping block? Declared, not
    # inferred: `is_server` is the other half and neither is derivable from
    # the kind (SEND is a DSP_CLIENT, but so would a non-bus utility be).
    #
    # It exists for ONE decision, and it is a safety one: an image with no
    # bus participant at all has no rotation to flip and no accumulator to
    # clear, which is the only condition under which unimplemented ids may
    # fall back to the firmware's own NONE rather than to SEND. See
    # NO_FALLBACK below.
    bus_client: bool = False


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
    claims: Claims | None = None
    harness: Harness | None = None

    def __post_init__(self):
        if self.params and len(self.params) != 12:
            raise ValueError(f"{self.name}: expected 12 param slots, "
                             f"got {len(self.params)}")
        if (self.menu is not None and self.kind is not Kind.STOCK
                and self.menu.fx2_id in STOCK_FX2_IDS
                and not self.menu.replaces):
            raise ValueError(
                f"{self.name}: fx2 id 0x{self.menu.fx2_id:02x} belongs to a "
                f"STOCK effect -- the dispatch tables are shared with FX1, so "
                f"this id would hijack that effect on both menus (see "
                f"STOCK_FX2_IDS). Declare MenuEntry(replaces=\"<KEY>\") if "
                f"that is what you mean. Free ids: "
                f"{', '.join(f'0x{i:02x}' for i in range(0x04, 0x20) if i not in STOCK_FX2_IDS)}")
        if self.menu is not None and self.menu.replaces:
            if self.kind is Kind.STOCK:
                raise ValueError(f"{self.name}: a STOCK entry cannot replace "
                                 f"anything -- it IS the stock effect")
            if self.menu.fx2_id not in STOCK_FX2_IDS:
                raise ValueError(
                    f"{self.name}: replaces={self.menu.replaces!r} but fx2 id "
                    f"0x{self.menu.fx2_id:02x} is not a stock effect's -- a "
                    f"replacement must carry the id it replaces, or the stock "
                    f"effect stays and yours is a separate row")
        if self.kind is Kind.STOCK and (self.dsp is not None or self.cf_patches):
            raise ValueError(f"{self.name}: a STOCK entry carries no code or "
                             f"caves -- they are already in the image (its "
                             f"params are READ from the stock descriptor, "
                             f"never written)")
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

    @property
    def is_cf_patch(self) -> bool:
        return bool(self.cf_patches)

    @property
    def is_stock(self) -> bool:
        """A stock FX2 effect kept in the chooser: nothing is cloned, placed
        or measured for it; the build only writes its list row and cursor
        position."""
        return self.kind is Kind.STOCK

    def knob_map(self) -> dict[str, int]:
        """Panel label -> slot index, for the test harness.

        THE single source of this map. It used to be hand-copied into
        send_probe, render_reverb, verify_delay, verify_bus, the build tables
        and the docs; four of those carry a comment about a time they drifted.
        """
        return {p.name.decode(): i for i, p in enumerate(self.params)
                if p.name}


# ---- the fallback that is not a module -------------------------------------
# An unimplemented id has to dispatch SOMEWHERE, and the answer has always
# been a module of ours -- SEND, which passes the audio through and only taps
# it. That costs 215-250 words, and an INSERT-ONLY remix was paying them for
# a client nothing reads: with no server in the image, nothing ever consumes
# the bus accumulators SEND writes. restock.py says so in its own docstring
# -- PLATE REV is missing from it ONLY because SEND's words land on PLATE's.
#
# So a remix may name this sentinel instead, and unimplemented ids resolve to
# the FIRMWARE's own NONE: its descriptor (the one at list position 0 of a
# stock FX2 chooser, which our rebuilt list otherwise drops) and, on the DSP
# side, the per-payload null stub the build already points silenced donor ids
# at. It costs one list row -- four bytes of cave -- and no words at all.
#
# ⚠️ IT IS REFUSED BESIDE ANY BUS PARTICIPANT, and that is the whole safety
# argument. Housekeeping -- flipping the rotation word and clearing the
# accumulators, once per block -- is gated to payload A and done by the FIRST
# CORE-0 PARTICIPANT DISPATCHED that block (send_client.asm's `bus_seen`
# election). Today every unassigned track runs SEND, so core 0 always has
# one. Under this fallback an unassigned track runs nothing, so a project
# with tracks 5-8 all unassigned has no housekeeper -- and a server on the
# OTHER core then reads an accumulator that is never rotated and never
# cleared. With no server and no client in the image there is no bus, no
# rotation and nothing to clear, so the question does not arise. That is the
# only case this is allowed in; registry.remix() enforces it.
#
# ⚠️ AND IT CANNOT BE SETTLED LOCALLY EITHER WAY: dsp_host is single-core, so
# no local test can reproduce a bus timing defect (CLAUDE.md). The refusal is
# what keeps the question off the table rather than answered by inference.
NO_FALLBACK = "NONE"


def on_the_bus(mod) -> bool:
    """Does this module take part in the cross-core bus, either end?"""
    h = getattr(mod, "harness", None)
    return h is not None and (h.is_server or h.bus_client)


# The three the project has always harvested, and what `x` offers when a
# selection has nowhere to place: the biggest stock effects, and FX2-only, so
# taking them costs FX1 nothing.
#
# ⚠️ THIS IS NOT A FIELD ANY MORE. Which effects a remix gives up is DERIVED
# from its two choosers -- an effect on neither is one it does not want, and
# "remove from the chooser" and "harvest" were the same act described twice
# (stock.harvested). It reproduces every shipped remix exactly, because FX1
# lists ten of the thirteen and the reverbs are FX2-only.
DEFAULT_HARVEST = ("PLATE REV", "SPRING REV", "DARK REV")


@dataclass(frozen=True)
class Remix:
    """A named selection of modules, composed into one firmware image.

    `modules` is ordered, and for modules that appear in the FX2 chooser that
    order IS their row on the panel. Modules with no menu entry (a ColdFire
    patch, say) may sit anywhere in the list; they are filtered out where a
    chooser order is wanted.

    STOCK effects are listed by the same keys ("FILTER", "CHORUS", ...):
    tools/remix/stock.py. A stock effect NOT listed is not removed from the
    image -- its code, descriptor and dispatch stay stock, so an old project
    that selects it still runs it -- it just has no chooser row, which is
    what every remix did to all fourteen of them before 2 Sep 2026. Only
    the three reverbs are actually consumed (their code is the donor region
    every module packs into) and they cannot be listed.

    THE FALLBACK IS NOT OPTIONAL, and it is the question a selective build
    forces. The FX2 chooser is one list shared by all eight tracks, and a
    saved project can carry an id this image does not implement -- because
    the remix left that module out, or because specialization put its engine
    on the other core. That id must still dispatch to SOMETHING; left alone
    it runs whatever code now occupies the address. Pointing it at a module
    that passes audio degrades in the useful direction, which is why the
    default is the send client: a track that selects a missing effect becomes
    a send rather than silence or noise.
    """

    name: str
    doc: str
    modules: tuple[str, ...]
    fallback: str                # module KEY that unimplemented ids alias to,
                                 # or NO_FALLBACK for the firmware's own NONE
    # ---- which of them ALSO get a row on FX1 ------------------------------
    # THE OTHER HALF OF "BOTH SLOTS", and it belongs to the REMIX rather than
    # to the module: which menu an effect appears on is a composition choice,
    # like the chooser order beside it, not a property of the code. The DSP
    # dispatch is ONE table indexed by the raw id and shared by both menus,
    # so a listed module's code ALREADY runs from FX1 -- what this adds is
    # the panel side, which stock keeps in FX1's own tables.
    #
    # IT COSTS NO WORDS. Four bytes of cave per row, plus FX1's chooser list
    # relocated into the cave (it ends at 0x400d608c with FX2's beginning at
    # 0x400d6090, so it cannot grow in place -- tools/build_fx1.py proved the
    # move standalone against the stock image). What it does cost is CYCLES:
    # an FX1 effect runs on a track that is already running an FX2 one, so
    # the worst per-core load can gain four more copies of it. cycle_count.py
    # prices that, and the remixer's Budget row is where to look first.
    #
    # ⚠️ A `replaces` MODULE IS ALREADY ON FX1 and must not be listed here:
    # it inherits the stock effect's row and has both of FX1's tables
    # repointed in place, so a second row would list it twice.
    #
    # ⚠️ ONLY A BUFFER-FREE INSERT MAY TAKE ONE. `state.fx1_hazard()` is the
    # single statement of why, read by both the remixer and build_bus.py, and
    # it refuses three classes:
    #
    #   * A module that reads the host's allocator (`x:>$213`). FX1 and FX2
    #     keep SEPARATE allocator tables at different sizes (measured, X:0x255
    #     in both payloads): an FX2 slot is 16,384 words, an FX1 slot 3,072.
    #     ⚠️ This is not theoretical and it is not new -- docs/DSP.md's "wrong
    #     claim 1" is this exact failure, bisected on hardware: a 16K layout
    #     at an FX1 base "runs to 0x53ff, through the other FX1 buffers and
    #     into FX2 slot 0". NIMBUS LITE reads the allocator and IS exposed;
    #     an earlier draft of this comment claimed nothing was, which was
    #     wrong -- it had checked only the fixed-base modules.
    #   * A module with FIXED buffers in the FX2 region (ChonVerb, Nimbus,
    #     BongDelay). An FX1 instance still writes to Y:0x4000 and up, i.e.
    #     into some other track's FX2 buffer. The hazard exists on FX2 too --
    #     it is why Nimbus is documented "one per core" -- but an FX1 row
    #     doubles the slots it can be reached from, a second instance on the
    #     SAME track included.
    #   * A bus SERVER, which is one per core by design (SPEC places one
    #     engine per payload). A second instance on a core is the open
    #     "duplicate instances corrupt audio after ~5.45 s" item.
    #
    # What is left is exactly the INSERT class: WarpFold, Ripple, Rungs,
    # Streamz, BodeShift, Hello World -- and SEND, which is buffer-free
    # (untested there, but nothing measured argues against it).
    fx1: tuple[str, ...] = ()

    def __post_init__(self):
        if self.fallback != NO_FALLBACK and self.fallback not in self.modules:
            raise ValueError(
                f"remix {self.name!r}: fallback {self.fallback!r} is not in "
                f"the remix, so ids aliased to it would dispatch nowhere")
        if len(set(self.modules)) != len(self.modules):
            raise ValueError(f"remix {self.name!r}: duplicate module keys")
        # ⚠️ NO PER-KEY CHECK HERE. An fx1 key may be a STOCK effect,
        # which need not be in `modules` at all -- FX1's list and FX2's
        # are independent. What each key may be is decided where the
        # registry is in scope: build_bus.py refuses, selftest pins it.
        if len(set(self.fx1)) != len(self.fx1):
            raise ValueError(f"remix {self.name!r}: duplicate fx1 keys")

