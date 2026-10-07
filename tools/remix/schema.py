"""What a remix module declares about itself.

A module is one contribution to the firmware: an FX2 engine, a bus client, a
ColdFire behaviour patch, or a combination. A remix is a named selection of
modules composed into one image. This file is the vocabulary both sides
speak: a manifest is the one place a module's facts are written, and the
build, the checks and the harness all read the same statement.

The schema declares what the build reads. A declared-but-unchecked claim is
worse than none, so a field exists only where a check consumes it.
"""

from __future__ import annotations

from collections.abc import Mapping
import dataclasses
from dataclasses import dataclass, field
from types import MappingProxyType
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


class Category(Enum):
    """Where a module sits in the module table, the index and the remixer's
    AVAILABLE pane. A display grouping, not a placement class: rig.category()
    derives the placement role (server / insert / mod / system) from the
    declaration and decides track ranges; this says what the module is FOR."""

    BUS = "bus"                 # the aux bus and its plumbing
    TRACK = "track"             # an effect on a track: stations, inserts, replacements
    MACHINES = "machines"       # machines and the sequencer
    PARTS = "parts"             # Parts, Kits and scenes, and the bridges between them
    MIDI_USB = "midi-usb"       # MIDI and USB
    FIXES = "fixes"             # a fix to stock behaviour
    SETTINGS = "settings"       # the settings store and what it carries
    REFERENCE = "reference"     # the canaries
    STOCK = "stock"             # a stock effect kept in the chooser


CATEGORY_TITLE = {
    Category.BUS: "Effects: the bus",
    Category.TRACK: "Effects: on a track",
    Category.MACHINES: "Machines and the sequencer",
    Category.PARTS: "Parts, Kits and scenes",
    Category.MIDI_USB: "MIDI and USB",
    Category.FIXES: "Fixes",
    Category.SETTINGS: "Settings",
    Category.REFERENCE: "Reference",
    Category.STOCK: "Stock effects",
}


class Proof(Enum):
    """How far a module or a remix has been proven. The vocabulary of the
    module table's last column and the remix index's; `proof_note` names the
    unit, image and date for HARDWARE, or the gate for the rest."""

    CHECK = "check"             # builds and boots under the port (make check)
    RENDER = "render"           # heard or measured in a local render, never flashed
    PORT = "port"               # a gate under the ColdFire port pins its behaviour
    HARDWARE = "hardware"       # ran on a unit


PROOF_TEXT = {Proof.CHECK: "`make check`", Proof.RENDER: "local render",
              Proof.PORT: "port-gated", Proof.HARDWARE: "on hardware"}


STOCK_FX2_IDS = frozenset({0x04, 0x05, 0x08, 0x0c, 0x0d, 0x10, 0x11, 0x12,
                           0x13, 0x14, 0x15, 0x16, 0x18, 0x19, 0x1c})


STEPPED_ONLY = (6, 7, 8, 9, 10, 11)


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
    written beside it. That is not a subtlety: it shipped on the
    flash, where BusDelay cloned SPRING REV and three of six page-2 slots
    drew wrong -- WOW drew no knob at all (an enumerated renderer with three
    labels asked to draw 0..127), MODE drew as a bipolar balance dial reading
    -64..-60. Every field those checks knew about was correct.

    So a module states the renderer per slot rather than inheriting one by
    accident.
    """

    INHERIT = "inherit"   # leave the donor's formatter untouched
    PLAIN = "plain"       # stock numeric knob: both formatter words zero
    STEPPED = "stepped"   # enumerated selector (the CHORUS.TAPS renderer)
    WIDE_STEPPED = "wide-stepped"  # labelled select whose >5 values fill the plain dial arc
    BIPOLAR = "bipolar"   # a 0..127 knob DRAWN -64..+63 (SPRING BAL's dial: A = 0x4003c7a0, 0x12a = the signed number; 14 Sep 2026)


@dataclass(frozen=True)
class Param:
    """One of the twelve parameter slots on an effect's two pages.

    `None` means "do not write this field", which leaves the donor's value in
    place. That is a real and different thing from writing a zero. The
    exception is `active`: None keeps the donor's enable nibble only on a
    `MenuEntry(stock_dsp=True)` clone, and is written as not drawn on every
    other clone.

    Page 1 is slots 0-5 (r6+0..5). Page 2 is slots 6-11: even slots are
    delivered in the KNOB field (bits 16-23) of r6+$c/$d/$e, odd slots in the
    COMPANION field (bits 8-15) of the same word. Any slot may carry any
    count -- stock puts 5-way selects on slot 6 and 128-value knobs on 9 --
    and a MODE goes on an EVEN slot -- the proven place for the panel's own
    page-2 knob editor to reach it. Whether that editor also reaches the odd slots is unresolved
    (docs/firmware/MAINMENU.md 9e); an even slot does not depend on the answer.
    """

    name: bytes | None = None          # <=5 chars in a 6-byte NUL-terminated field; b"" blanks it
    default: int | None = None         # u8 written at P+0x5e+idx
    count: int | None = None           # value count; None leaves the donor's
    # Drawn at all (the slot's nibble in the enable bitmap). None on a
    # MenuEntry(stock_dsp=True) clone keeps the donor's nibble, link bit
    # included; everywhere else None is written as not drawn, as False is.
    active: bool | None = None
    formatter: Formatter = Formatter.INHERIT
    # Display-only, consumed by the remixer and never by the build (the
    # refhash gate proves it): one line saying what the knob DOES, and for a
    # select, what each value means. The unit's panel cannot show either, so
    # this is where a contributor answers "what is this?" once instead of in
    # a comment only readers of the manifest ever see.
    doc: str | None = None             # one line, ~70 chars, for the help row
    labels: tuple[str, ...] | None = None   # one short label per select value
    # The panel's link element: bit 1 of this slot's enable nibble draws the
    # bracket tying this knob to the one on its LEFT (stock: STRT/LEN,
    # BASE/WDTH, RATE/TSTR, SHVG/SHVF; PARAM_PAGES.md 3b). Display only --
    # the two knobs stay independent. The pair must sit in one row of three
    # (slots 0-1, 1-2, 3-4, 4-5 and the page-2 equivalents); stock never
    # links across 2-3.
    link: bool = False
    # The slot's three descriptor words written as declared, for a drawing
    # no Formatter names: P+0x0ca formatter A, P+0x0fa widget B, P+0x12a
    # (docs/firmware/PARAM_PAGES.md section 7). Each is None (the donor's
    # word), an int (a stock address or a literal; 0 included), or a
    # (unit, symbol) pair resolved like a Detour's: a Linked or CavePatch
    # label in this remix and a symbol it exports. A slot with any of the
    # three set takes no `formatter` and is checked by verify_menu against
    # these words instead of the count rule.
    formatter_word: int | tuple[str, str] | None = None
    widget_word: int | tuple[str, str] | None = None
    word_12a: int | tuple[str, str] | None = None
    # The knob's stable identity in a stored default or template
    # (docs/proposals/BRAIN.md section 4.1): 1..65535, never reused, so a
    # renamed or moved knob keeps its stored value. A module that keys one
    # drawn slot keys every drawn slot; brain.lock holds the released keys.
    key: int | None = None

    @property
    def raw_words(self) -> tuple:
        """(formatter_word, widget_word, word_12a)."""
        return (self.formatter_word, self.widget_word, self.word_12a)

    @property
    def has_raw_words(self) -> bool:
        return any(w is not None for w in self.raw_words)

    @property
    def prints_labels(self) -> bool:
        """The build emits a label formatter for this slot. A slot with raw
        descriptor words is drawn by those words, which take P+0x0ca: its
        labels are display-only (the remixer's help row, the BCR map)."""
        return bool(self.active and self.labels) and not self.has_raw_words

    def __post_init__(self):
        for _f, _w in zip(("formatter_word", "widget_word", "word_12a"), self.raw_words):
            if _w is None or (isinstance(_w, int) and not isinstance(_w, bool)
                              and 0 <= _w <= 0xFFFFFFFF):
                continue
            if (isinstance(_w, tuple) and len(_w) == 2
                    and all(isinstance(x, str) and x for x in _w)):
                continue
            raise ValueError(f"param {self.name!r}: {_f} is {_w!r} -- an int "
                             f"(u32) or a (unit, symbol) pair")
        if self.has_raw_words and self.formatter is not Formatter.INHERIT:
            raise ValueError(
                f"param {self.name!r}: formatter={self.formatter.value} and raw "
                f"descriptor words together -- the raw words are the drawing")
        if self.link and not self.active:
            raise ValueError(f"param {self.name!r}: link on a slot that is not drawn")
        if self.key is not None and (isinstance(self.key, bool) or not 1 <= self.key <= 0xFFFF):
            raise ValueError(f"param {self.name!r}: key {self.key!r} is not 1..65535")
        if self.name is not None and len(self.name) > 5:
            raise ValueError(
                f"param name {self.name!r} exceeds 5 characters; the panel "
                f"field is 6 bytes including its NUL terminator")
        if self.labels is not None:
            if self.count is None or len(self.labels) != self.count:
                raise ValueError(
                    f"param {self.name!r}: {len(self.labels)} labels for a "
                    f"count of {self.count} -- one label per value, and only "
                    f"where a count is declared")
        if self.formatter is Formatter.WIDE_STEPPED:
            if self.count is None or self.count <= 5 or self.labels is None:
                raise ValueError(
                    f"param {self.name!r}: WIDE_STEPPED needs labels and at "
                    f"least six values")
        # A default outside its own count is used as an INDEX. That shipped
        # once -- slot 7 defaulted to 64 with a count of 5 -- and stalled the
        # sequencer on hardware after two steps.
        if self.count is not None and self.default is not None:
            if not 0 <= self.default < self.count:
                raise ValueError(
                    f"default {self.default} is outside its value count "
                    f"{self.count} -- the panel uses it as an index")


def enable_words(active, linked=(), inherited=(), donor=(0, 0)):
    """A descriptor's two enable words (P+0x18e slots 0-7, P+0x18a slots
    8-11, one nibble each): bit 0 draws the slot, bit 1 draws the link
    element to its left neighbour (PARAM_PAGES.md 3b). A slot in `inherited`
    takes its whole nibble from `donor`, the donor's (lo, hi)."""
    lo = hi = 0
    for i in active:
        bits = 3 if i in linked else 1
        if i < 8:
            lo |= bits << (4 * i)
        else:
            hi |= bits << (4 * (i - 8))
    for i in inherited:
        sh = 4 * (i if i < 8 else i - 8)
        m = 0xf << sh
        if i < 8:
            lo = (lo & ~m) | (donor[0] & m)
        else:
            hi = (hi & ~m) | (donor[1] & m)
    return lo, hi


# ---- settings (docs/proposals/BRAIN.md section 4) -------------------------
# A module's settings, resolved through four layers: the manifest's default,
# the remix's (`Remix.settings`, a value or a Pin), the card's and the
# project's. Without the BRAIN module in the remix only the first two exist
# and every value is a build-time constant (tools/remix/brain.py).

BRAIN_KEY = "BRAIN"                # the module that carries the run-time layers
STORE_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789.-_")


class Scope(Enum):
    CARD = "card"                # layers 1, 2, 3: shared by every project on the card
    PROJECT = "project"          # layers 1, 2, 4: stored with the project


class Apply(Enum):
    LIVE = "live"                # the module reads the value table
    CALLBACK = "callback"        # its routine runs after a load and after an edit
    NEXT_BOOT = "next_boot"      # read once at boot
    BUILD = "build"              # selects code: layers 1 and 2 only


@dataclass(frozen=True)
class Binary:
    """0 or 1, stored as one byte (brain file type 1)."""

    def check(self, v) -> str | None:
        return None if v in (0, 1) and not isinstance(v, float) else f"{v!r} is not 0 or 1"

    def zero(self):
        return 0


@dataclass(frozen=True, init=False)
class Option:
    """An index into append-only labels, stored as one byte (brain file type 2).
    A label is never removed, renamed or moved: brain.lock refuses it."""
    labels: tuple[str, ...]

    def __init__(self, *labels: str):
        if not 1 <= len(labels) <= 256:
            raise ValueError(f"Option takes 1..256 labels, got {len(labels)}")
        if any(not isinstance(x, str) or not x for x in labels):
            raise ValueError(f"Option labels are non-empty strings: {labels!r}")
        if len(set(labels)) != len(labels):
            raise ValueError(f"Option labels repeat: {labels!r}")
        object.__setattr__(self, "labels", tuple(labels))

    def index(self, v) -> int | None:
        """A label or an index -> the index, or None when it names nothing."""
        if isinstance(v, str):
            return self.labels.index(v) if v in self.labels else None
        if isinstance(v, int) and not isinstance(v, bool) and 0 <= v < len(self.labels):
            return v
        return None

    def check(self, v) -> str | None:
        return None if self.index(v) is not None else \
            f"{v!r} is not one of {len(self.labels)} labels {self.labels!r}"

    def zero(self):
        return 0


@dataclass(frozen=True)
class Number:
    """A signed 16-bit integer, stored as two bytes (brain file type 3)."""
    min: int
    max: int
    step: int = 1
    unit: str = ""

    def __post_init__(self):
        if not -0x8000 <= self.min <= self.max <= 0x7FFF:
            raise ValueError(f"Number bounds {self.min}..{self.max} are not "
                             f"ordered inside -32768..32767")
        if self.step < 1:
            raise ValueError(f"Number step {self.step} is not positive")

    def check(self, v) -> str | None:
        if isinstance(v, bool) or not isinstance(v, int):
            return f"{v!r} is not an integer"
        if not self.min <= v <= self.max:
            return f"{v} is outside {self.min}..{self.max}"
        if (v - self.min) % self.step:
            return f"{v} is not on a step of {self.step} from {self.min}"
        return None

    def zero(self):
        return self.min if self.min > 0 else self.max if self.max < 0 else 0


@dataclass(frozen=True)
class Trigger:
    """An action; never stored and never defaulted."""

    def check(self, v) -> str | None:
        return None if v is None else "a Trigger holds no value"

    def zero(self):
        return None


@dataclass(frozen=True)
class Blob:
    """Bytes the module packs and unpacks, at most `max_bytes` (brain file type 4)."""
    max_bytes: int

    def __post_init__(self):
        if not 1 <= self.max_bytes <= 0xFFFF:
            raise ValueError(f"Blob max_bytes {self.max_bytes} is not 1..65535")

    def check(self, v) -> str | None:
        if not isinstance(v, (bytes, bytearray)):
            return f"{v!r} is not bytes"
        return None if len(v) <= self.max_bytes else \
            f"{len(v)} bytes exceed the declared {self.max_bytes}"

    def zero(self):
        return b""


KINDS = (Binary, Option, Number, Trigger, Blob)


@dataclass(frozen=True)
class Store:
    """The id a module's settings and stored defaults are filed under.
    ASCII, 1..63 bytes; the build refuses two modules with one id."""
    id: str
    major: int = 1
    minor: int = 0

    def __post_init__(self):
        if not 1 <= len(self.id) <= 63 or not set(self.id) <= STORE_ID_CHARS \
                or self.id[0] in ".-_":
            raise ValueError(f"store id {self.id!r}: 1..63 of [a-z0-9.-_], "
                             f"starting with a letter or digit")
        if not 1 <= self.major <= 0xFFFF or not 0 <= self.minor <= 0xFFFF:
            raise ValueError(f"store {self.id}: schema {self.major}.{self.minor} "
                             f"is not u16.u16 with a major of at least 1")


@dataclass(frozen=True)
class Setting:
    """One setting of a module (docs/proposals/BRAIN.md section 4.1).

    `default` None takes the kind's zero (0, the first label, b"" or, for a
    Number whose range excludes 0, its nearer bound). An Option takes a
    label or an index; it is kept as the index. `early` copies a CARD
    setting into the CS1 block, read before the card mounts."""

    key: int
    name: str
    kind: object                 # Binary() | Option(...) | Number(...) | Trigger() | Blob(n)
    default: object = None
    scope: Scope = Scope.CARD
    apply: Apply = Apply.LIVE
    early: bool = False
    doc: str | None = None

    def __post_init__(self):
        where = f"setting {self.key} {self.name!r}"
        if isinstance(self.key, bool) or not isinstance(self.key, int) \
                or not 1 <= self.key <= 0xFFFF:
            raise ValueError(f"{where}: key is not 1..65535")
        if not self.name or not self.name.isascii() or not self.name.isprintable():
            raise ValueError(f"{where}: the name is printable ASCII")
        if not isinstance(self.kind, KINDS):
            raise ValueError(f"{where}: kind {self.kind!r} is not one of "
                             f"{', '.join(k.__name__ for k in KINDS)}")
        if self.default is None:
            object.__setattr__(self, "default", self.kind.zero())
        why = self.kind.check(self.default)
        if why:
            raise ValueError(f"{where}: default {why}")
        if isinstance(self.kind, Option):
            object.__setattr__(self, "default", self.kind.index(self.default))
        if self.early:
            if self.scope is not Scope.CARD:
                raise ValueError(f"{where}: early is for a CARD setting; a "
                                 f"PROJECT value has no meaning before a project loads")
            if isinstance(self.kind, (Blob, Trigger)):
                raise ValueError(f"{where}: early takes a fixed-size value, "
                                 f"not a {type(self.kind).__name__}")
        if self.apply is Apply.BUILD and isinstance(self.kind, (Blob, Trigger)):
            raise ValueError(f"{where}: Apply.BUILD selects code from a "
                             f"Binary, Option or Number, not a {type(self.kind).__name__}")

    @property
    def size(self) -> int:
        """Bytes of the value: the value table's slot and the CS1 block's."""
        k = self.kind
        return k.max_bytes if isinstance(k, Blob) else \
            {Binary: 1, Option: 1, Number: 2, Trigger: 0}[type(k)]


@dataclass(frozen=True)
class Pin:
    """A remix's fixed value for a setting: no menu row, nothing stored,
    a stored value on the card preserved and not applied."""
    value: object


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
    # TWELVE (docs/firmware/PARAM_PAGES.md section 2). Filling a field exactly leaves
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
    # 0x0d from 29 Aug to, in every local image, and the remixes
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
    # The replaced effect's own DSP stays its dispatch entry: init/proc are
    # stock's, and the module's DspSection is code reached from its
    # DspHooks only (SIDECHAIN_COMPRESSOR: stock COMPRESSOR plus a detector
    # tap). Requires `replaces`; the build leaves both dispatch words of
    # the id as the pristine image has them and verify_replaces checks it.
    stock_dsp: bool = False

    def __post_init__(self):
        if self.stock_dsp and not self.replaces:
            raise ValueError(f"stock_dsp keeps the donor's dispatch entry, so "
                             f"it needs replaces=<the stock effect's key>")
        # 0x00-0x03 are the ids stock treats as bare synonyms for "no effect";
        # the first hardware test used them and got correct names with dead
        # knobs and garbage audio.
        if not 0x04 <= self.fx2_id <= 0x1f:
            raise ValueError(f"fx2 id 0x{self.fx2_id:02x} is out of range "
                             f"(0x00-0x03 are stock's 'no effect' synonyms)")
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
class DspHook:
    """A `jsr` planted in STOCK DSP code, into a placed section.

    The two stock words at `site` (one two-word instruction) become
    `jsr >label`; the section replays the displaced instruction itself. The
    build asserts `stock` before it writes, on every payload the section is
    placed on, and the ledger refuses two modules hooking one site. This is
    how DSP code with no chooser row is reached at all: USB AUDIO IN's RX
    inject at the frame head, P:0x88.
    """

    # P address of the displaced instruction: one int for every payload,
    # or {"A": addr, "B": addr} naming exactly the section's payloads when
    # the stock code sits at a different address on each (the two payloads
    # are linked separately; AGENTS.md "payload-relative addresses").
    site: int | Mapping[str, int]
    # its two words, as the image has them: one pair for every payload, or
    # {"A": (w0, w1), "B": (w0, w1)} when they differ (a branch or loop
    # target inside the instruction: each payload's own address)
    stock: tuple[int, int] | Mapping[str, tuple[int, int]]
    label: str                                 # the section's entry for this site
    note: str = ""

    def __post_init__(self):
        if isinstance(self.site, Mapping):
            object.__setattr__(self, "site", MappingProxyType(dict(self.site)))
            if not self.site or set(self.site) - {"A", "B"}:
                raise ValueError(f"DspHook {self.label!r}: site keys are payload "
                                 f"tags A/B, got {sorted(self.site)}")
        if isinstance(self.stock, Mapping):
            object.__setattr__(self, "stock", MappingProxyType(
                {k: tuple(v) for k, v in self.stock.items()}))
            if not isinstance(self.site, Mapping) or set(self.stock) != set(self.site):
                raise ValueError(f"DspHook {self.label!r}: per-payload stock words "
                                 f"need a per-payload site naming the same payloads")

    def site_on(self, payload: str) -> int:
        """The hook's P address on one payload."""
        return self.site[payload] if isinstance(self.site, Mapping) else self.site

    def stock_on(self, payload: str) -> tuple[int, int]:
        """The two stock words at the hook's site on one payload."""
        return tuple(self.stock[payload] if isinstance(self.stock, Mapping) else self.stock)


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
    # A TABLE the module reads with p:(rN) -- the source's one `$fab1e0`
    # literal is rewritten by the build to wherever it put the words, the
    # reverb's LFOTAB mechanism made declarative (12 Sep 2026: Spectrum's
    # exponential FREQ taper is the first). dsp_asm has no dc directive,
    # hence words here. Where it goes: in the stock curve
    # bank X:0x4840 -- a 4,096-word data record at the same address in
    # both payloads whose only stock reader is DJ EQ -- with the module's
    # `p:(` table reads rewritten to `x:(`, costing the module's run
    # nothing; or, when a reader of that record survives in the image, in
    # P immediately BEFORE the module's code, out of its own budget, as it
    # always was (build_bus.py XTABLE; stock.CURVE_BANK for the scan and
    # its limits); or, when neither fits, in the exclusive X data of a
    # stock effect on neither chooser (stock.x_exclusive_runs), read through
    # `x:(` the same way. ⚠️ So a module with a table may read P for NOTHING
    # ELSE: every `p:(` in its code is the table.
    ptable: tuple[int, ...] = ()
    # A SECOND table block with its own `$fab2e0` base literal. In P and in
    # the curve bank it follows `ptable` directly; in a given-up effect's
    # X data each block goes into the first run it fits, so a table larger
    # than any one run is declared as two blocks. Requires `ptable`.
    ptable2: tuple[int, ...] = ()
    # Entries into this section from STOCK code (schema.DspHook). A section
    # with hooks and no MenuEntry is placed on `payloads` only and takes no
    # dispatch entry; one with a menu may carry hooks as well.
    hooks: tuple[DspHook, ...] = ()
    # Per-payload text substitutions applied to the source before anything
    # else the build does to it: {"A": {"@SBASE@": "$33e00"}, "B":
    # {"@SBASE@": "$3be00"}}. dsp_asm has no equ and no expressions, so a
    # value that differs per core is written per core. Both payloads name
    # the same keys; every key occurs in the source (refused at build); no
    # key may overlap a marker the build substitutes itself (SUBST_RESERVED).
    subst: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    # Declared ceiling on instances of this module per core, 1..4 (a core has
    # four FX2 slots). None = unlimited: the cycle counter prices four copies.
    # With a value, `tools/build/cycle_count.py` prices that many copies. The
    # unit does not enforce it: nothing stops a fifth..third selection, so the
    # remix README must state the ceiling.
    max_per_core: int | None = None

    def __post_init__(self):
        if self.max_per_core is not None and not 1 <= self.max_per_core <= 4:
            raise ValueError(f"{self.asm}: max_per_core {self.max_per_core} "
                             f"outside 1..4 (a core has four FX2 slots)")
        if self.ptable2 and not self.ptable:
            raise ValueError(f"{self.asm}: ptable2 without ptable -- the "
                             f"second block follows the first")
        object.__setattr__(self, "subst", MappingProxyType(
            {pl: MappingProxyType(dict(kv)) for pl, kv in self.subst.items()}))
        for h in self.hooks:
            if isinstance(h.site, Mapping) and set(h.site) != set(self.payloads):
                raise ValueError(
                    f"DspHook {h.label!r}: site names payloads {sorted(h.site)}, "
                    f"the section is placed on {sorted(self.payloads)}")
        if self.subst:
            if set(self.subst) != set(self.payloads):
                raise ValueError(f"subst names payloads {sorted(self.subst)}, "
                                 f"the section is placed on {sorted(self.payloads)}")
            keys = [frozenset(kv) for kv in self.subst.values()]
            if len(set(keys)) != 1:
                raise ValueError("subst: every payload names the same keys "
                                 + "; ".join(f"{pl}: {sorted(kv)}" for pl, kv
                                             in sorted(self.subst.items())))
            for k in keys[0]:
                if not k.strip():
                    raise ValueError(f"subst: empty key {k!r}")
                hit = [r for r in SUBST_RESERVED if r in k or k in r]
                if hit:
                    raise ValueError(f"subst key {k!r} overlaps the build's own "
                                     f"marker {hit[0]!r}")
            for pl, kv in self.subst.items():
                for k, v in kv.items():
                    if any(r in v for r in SUBST_RESERVED):
                        raise ValueError(f"subst {pl} {k!r}: value {v!r} carries "
                                         f"a marker the build substitutes")

    def source_for(self, payload: str, src: str) -> str:
        """`src` with this payload's subst applied (refuses a key the source
        does not carry)."""
        for k, v in self.subst.get(payload, {}).items():
            if k not in src:
                raise ValueError(f"{self.asm}: subst key {k!r} does not occur "
                                 f"in the source")
            src = src.replace(k, v)
        return src


# Text the build substitutes in DSP sources itself (build_bus.py), which a
# DspSection.subst key or value may not overlap. AGENTS.md "build-time
# markers and base literals count when they appear in COMMENTS".
SUBST_RESERVED = ("$30000", "$facade", "$fab1e0", "$fab2e0", "; ROTLATCH", "; ROTINIT",
                  "_OVERRIDE", "XBUS_GATE", "; HOSTGUARD",
                  "LFO lines 0-1: ROLLED TOO")


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
    # Byte offset of the formatter's entry INSIDE the cave. 0 (the default)
    # is a cave that is nothing but a formatter, the tempo-sync shape. A
    # cave that is also a HOOK target keeps its hook entry at +0 (the
    # installer's jsr lands there) and puts the formatter further in --
    # modules/cfprobe puts it at +0x100 with an `.org`, so one cave, one
    # address and one pc-relative state block serve both callers.
    offset: int = 0
    # On a Linked unit (Linked.registers_formatter): the formatter's entry
    # symbol in that unit; `offset` is added to it.
    symbol: str = ""


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
    cave_addr: int | None                # None = floating; pass it explicitly
    pinned: bytes
    source: str | None = None           # .s re-assembled and compared
    hook_addr: int | None = None        # where the jsr is planted
    hook_stock: bytes = b""             # bytes that MUST be there first
    registers_formatter: FormatterReg | None = None
    # ---- a cave whose CONTENT depends on where it lands -------------------
    emit: object | None = None
    # Trailing prose for this cave's line in the build report, separator
    # included. The installer is generic; what a given cave actually DOES is
    # not, and the build report is the only place a human sees it.
    report_note: str = ""
    # 32-bit words in the cave equal to the stock audio-arena base
    # (0x40a955e0, tools/remix/arena.py). The build checks the count and,
    # when a remix moves the base (any DRAM runtime, octamax), rewrites them
    # to the moved base like the firmware's own base sites.
    pool_base_literals: int = 0
    # ---- SOURCE IS THE TRUTH ---------------------------------
    # With the m68k-elf toolchain now a standard dependency (`make setup`),
    # a cave with a `source` is assembled and LINKED by the build at the
    # address it lands on, and THOSE bytes are what is written; `pinned` is
    # the ratified reference and must match, or the build refuses. A source
    # may therefore hold absolute references to itself, and symbols it needs
    # from the build (the address of a data field, a clone's slot) arrive as
    # `defsyms` -- `--defsym NAME=value` to both the assembler (so `.ifdef`
    # sees it) and the linker -- instead of placeholder words patched into
    # hand-assembled hex (busscreen's MARKS, cc-map's VCOUNT). A name the
    # source itself defines is refused.
    # An emit() that returns b"" for its bytes says "the source is the only
    # truth"; an emit() that still returns bytes takes the legacy path,
    # unlinked and unchecked, exactly as before. Without a toolchain the
    # reference bytes are written, as before.
    defsyms: tuple[tuple[str, int], ...] = ()
    cpu: str = "5475"                   # m68k-elf-as -mcpu=; 5407 and 5475
                                        # encode this ISA subset identically
    # A FLOATING source-linked cave has no fixed `pinned` to be held against
    # (its bytes depend on where it lands), so it may supply the oracle as a
    # callable instead: reference(addr) -> the ratified bytes AT that
    # address -- cc-map keeps its hand-patched legacy form for exactly this.
    # Checked on every build; a drift refuses.
    reference: object | None = None
    # Bytes the cave may occupy when `pinned` is empty (its bytes come from
    # the link at build time). The ledger sizes the claim by the larger of
    # this and len(pinned); the build refuses a linked cave past it.
    reserve: int = 0

    @property
    def claim_len(self) -> int:
        return max(len(self.pinned), self.reserve)


SHARED_WINDOW = (0x30000, 0x40000)      # Y:0x30000-0x3FFFF, both cores; X, Y and P alias
HALF_BASE = {"A": 0x30000, "B": 0x38000}  # each payload's half of the shared window


@dataclass(frozen=True)
class DspRange:
    """DSP data words a module writes, on every payload its section runs on.

    `space` is "x" or "y". `start` is an absolute address, or with
    `half_relative` an offset from the payload's own half of the shared
    window (`HALF_BASE`: 0x30000 on A, 0x38000 on B -- the per-payload
    `$30000` rewrite, schema.YBase). A range lies wholly inside the shared
    window or wholly below it. Inside it, X, Y and P are one memory shared
    by both cores, so the ledger compares the range against every module's
    on either payload; below it, only against the same space on the same
    payload (each core has its own).
    """

    space: str
    start: int
    length: int
    what: str
    half_relative: bool = False

    def __post_init__(self):
        if self.space not in ("x", "y"):
            raise ValueError(f"DspRange({self.what!r}): space must be 'x' or 'y', not {self.space!r}")
        if self.length <= 0:
            raise ValueError(f"DspRange({self.what!r}): length must be positive")
        if self.half_relative:
            if not (0 <= self.start and self.start + self.length <= 0x8000):
                raise ValueError(f"DspRange({self.what!r}): a half-relative range lies "
                                 f"inside one half, 0x0000-0x7FFF")
            return
        lo, hi = SHARED_WINDOW
        end = self.start + self.length
        if self.start < 0 or end > hi or (self.start < lo < end):
            raise ValueError(f"DspRange({self.what!r}): 0x{self.start:05x}..0x{end - 1:05x} "
                             f"must lie wholly below 0x{lo:05x} or wholly in the shared window")

    def resolve(self, payload: str) -> tuple[str, int, int]:
        """(domain, start, end) on `payload`: domain "shared" in the window,
        else "<payload>:<space>"."""
        start = self.start + (HALF_BASE[payload] if self.half_relative else 0)
        end = start + self.length
        if start >= SHARED_WINDOW[0]:
            return "shared", start, end
        return f"{payload}:{self.space}", start, end


@dataclass(frozen=True)
class Claims:
    """Resources a module reserves that the ledger cannot see for itself.

    Deliberately tiny. Anything derivable from the module's own source is
    derived rather than declared, because a scan cannot go stale and a
    hand-written claim can. This is only for what a module means to own but
    does not yet reference.
    """

    reserved_private_y: tuple[int, ...] = ()
    owns_fx2_buffers: bool = False
    # A STOCK effect that allocates an FX2 instance buffer through the host's
    # bump allocator (it reads X:0x213 at init -- docs/firmware/DSP.md section 10).
    # The allocator hands the buffer out PER TRACK SLOT: on core 0 the four
    # slots are Y:0x4000, 0x8000, 0x30000 and 0x34000, on core 1 0x4000,
    # 0x8000, 0x38000 and 0x3c000 -- and those are exactly the addresses
    # BusVerb's tank and BusDelay's line hardcode. So a
    # buffered stock effect on the wrong track silently corrupts a server
    # on the same core, and the chooser is one list for all eight tracks,
    # so the build cannot tell which track it will land on. The ledger
    # refuses the pair. Measured by scanning the payload
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
    # WRITES NOTHING. Two reasons a module says so, one claim:
    #   * an allocator reader (stock_instance_buffer): the FX2 slots it
    #     would be handed are BusVerb's tank and BusDelay's line, and the
    #     ledger refuses every other allocator reader beside them;
    #   * a buffer-free station: the
    #     rig's cycle envelope only closes with the stations on FX1 -- a
    #     station on both slots of four tracks priced a core at 4,830
    #     against 3,120 usable (tools/harness/pressure.py) -- so an FX2
    #     instance costs nothing and the FX2 chooser hides the row.
    # Either way the claim is a promise the module's render gate must
    # prove (an FX2-slot instance renders bit-exact dry and dsp_host's
    # guard sees no write above 0x3fff), and the pricer takes it at its
    # word: an fx1_only module is priced on FX1 slots only.
    fx1_only: bool = False
    # BYTES OF THE PART WINDOW a module stores its own data in: (offset from
    # the window's base 0x8ed80, length, what). The window (0x18b2 bytes a
    # part) is dense and has no run known free: 0x90492..0x905b2, which
    # MIDI SCENES claims (freeze twin, then sparse blob), is the LFO designer
    # records of audio and MIDI tracks 2-8 (docs/firmware/PARTS.md section
    # 9). SCENES P2 claims bytes 30 and 31 of each scene block, which the
    # frame builder skips. The ledger refuses an overlap between two modules.
    part_window: tuple[tuple[int, int, str], ...] = ()
    # ON-CHIP SRAM a module's DMA engine reads or writes: (address, length,
    # what). 32 KB at 0x80000000; stock's highest static use ends at
    # 0x80007874 (a 768-byte buffer at 0x80007574). USB AUDIO IN keeps its
    # dTDs and packet buffers in the top 1 KB. The ledger refuses an overlap
    # between two modules; the stock extent is the author's census. The
    # check is on address overlap, so a range in CS1 (battery SRAM at
    # 0x10000000) is declared here too: PLOCKS P2 keeps the current bank's
    # page 2 in 0x100f8600..0x100fbdf0.
    sram: tuple[tuple[int, int, str], ...] = ()
    # DSP DATA a module writes outside its r7 block and the regions the
    # fields above cover (schema.DspRange): shared-window buffers, fixed X
    # or Y tables. The ledger compares them with every other module's
    # ranges, FX2 buffer region and core-private Y words, the bus scratch
    # and stock's per-frame staging; with a project, verify_set holds every
    # shared-window write the port measures against them
    # (tools/remix/dsp_ranges.py).
    dsp_ranges: tuple[DspRange, ...] = ()

    def __post_init__(self):
        if self.buffer_words is not None and not self.stock_instance_buffer:
            raise ValueError("buffer_words without stock_instance_buffer: "
                             "only an allocator reader has a sized buffer")
        if self.fx1_only and self.stock_instance_buffer:
            if self.buffer_words is None or self.buffer_words > 3072:
                raise ValueError("fx1_only needs buffer_words <= 3072: an "
                                 "FX1 slot is 3,072 words (docs/firmware/DSP.md 10)")


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
    # THE STATE BLOCK A LOCAL RENDER RUNS THE MODULE AT: dsp_host's -r7
    # index n (X:0x6000 + 0x100 n; R7_ALLOC gives its allocator entry).
    # None = the default, FX2 position 0 (n = 2), or FX1 (n = 1) for an
    # fx1_only module. A module that runs at some positions only and is a
    # dry pass elsewhere names one it runs at, or `send_probe --direct`,
    # the audition and verify_dirtystate measure its dry pass (VOCODER:
    # 5, 0x6500, a core's second FX2 slot).
    render_r7: int | None = None


# dsp_host's -r7 index (X:0x6000 + 0x100 n) -> the allocator's base-table
# entry for that slot: FX1 at 1, 4, 7, 10; FX2 at 2, 5, 8, 11.
R7_ALLOC = {1: 0, 2: 1, 4: 2, 5: 3, 7: 4, 8: 5, 10: 6, 11: 7}


def render_slot(mod) -> tuple[int, int]:
    """(dsp_host -r7 index, -alloc entry) a local render of `mod` uses."""
    h = getattr(mod, "harness", None)
    if h is not None and h.render_r7 is not None:
        return h.render_r7, R7_ALLOC[h.render_r7]
    c = getattr(mod, "claims", None)
    return (1, 0) if (c is not None and c.fx1_only) else (2, 1)


@dataclass(frozen=True)
class Gate:
    """One check `make check` runs because this module is in the remix.

    `make verify` used to list every module's verifier by hand, each one
    written to SKIP when the remix lacked its module; a new module meant a
    Makefile edit and every remix ran all of them. The module names its
    own now (tools/verify/module_gates.py collects the selection's, runs
    each once, and refuses a script that does not exist).

    `stage` says what the script expects on disk: "isolated" gates build
    their own scratch image (or none) and run before the selected image is
    restored; "image" gates read out/mainos_bus.bin and run after
    `make bus REMIX=<name>` and the shared set gates (a gate that needs
    verify_set's staged card is an image gate). The runner exports REMIX
    and BUILD to every gate.

    `once` is for a gate whose subject is the module's own code, the same
    in every carrier (a ColdFire module's panel scenarios under the port):
    it takes a remix name but runs once per run, in the shared half, on
    the named remix with the fewest modules that carries the module,
    instead of once per carrying remix (KITS: 29 port scenarios, 371 s
    emulated, on bottleservice AND ok-ms, 6 Oct 2026).
    """

    script: str                      # repo-relative
    remix_arg: bool = True           # pass the remix name as argv[1]
    venv: bool = False               # prefer .venv/bin/python3 (the port's python) when present
    stage: str = "isolated"          # "isolated" | "image"
    once: bool = False               # once per run, on one carrying remix of the selection (the shared half)

    def __post_init__(self):
        if self.stage not in ("isolated", "image"):
            raise ValueError(f"Gate({self.script!r}): stage must be 'isolated' or 'image', not {self.stage!r}")
        if self.once and (not self.remix_arg or self.stage != "isolated"):
            raise ValueError(f"Gate({self.script!r}): once=True needs remix_arg=True and the isolated stage "
                             "(it runs in the shared half, which has no image)")
        if not self.script.startswith("tools/") and not self.script.startswith("modules/"):
            raise ValueError(f"Gate({self.script!r}): a repo-relative path under tools/ or modules/")


@dataclass(frozen=True)
class ModeView:
    """What ONE position of a module's MODE select renames and re-defaults.

    A multi-mode effect reuses knobs: BusDelay's MDEP is the tape modulation
    depth in CLEAN and the grain scatter in GRAIN, and a panel that prints
    MDEP in both is telling the operator the wrong thing half the time (Sam,
   : "it's only got four settings ... just feels a lil confusing").

    `names` renames slots for this mode -- up to 5 characters plus the field's
    terminator. `defaults` is what the OTHER knobs should
    be when the operator lands on this mode; the remixer applies them the
    moment MODE changes, and on the unit the same table drives the cave.

    Both are SPARSE: a slot absent from `names` keeps the name its Param
    declares, and a slot absent from `defaults` keeps whatever the operator
    had. Only name a slot whose meaning actually changes.
    """

    mode: int                                   # the select value
    names: dict[int, bytes] = field(default_factory=dict)
    defaults: dict[int, int] = field(default_factory=dict)

    def __post_init__(self):
        for slot, nm in self.names.items():
            if not 0 <= slot <= 11:
                raise ValueError(f"mode {self.mode}: slot {slot} is not 0..11")
            if len(nm) > 5:
                raise ValueError(
                    f"mode {self.mode}: name {nm!r} is {len(nm)} characters; "
                    f"the field holds FIVE plus a terminator")
        for slot, val in self.defaults.items():
            if not 0 <= slot <= 11:
                raise ValueError(f"mode {self.mode}: slot {slot} is not 0..11")
            if not 0 <= val <= 127:
                raise ValueError(f"mode {self.mode}: default {val} for slot "
                                 f"{slot} is outside 0..127")


@dataclass(frozen=True)
class NameSelect:
    """An additional stepped select that only renames parameter fields.

    `Module.mode_slot` remains the selector that can also apply defaults.
    NameSelect covers independent display relationships, such as Euclid TYPE
    changing FREQ to LEVEL while OUTPUT continues to rename DECAY/ATTACK.
    """

    slot: int
    views: tuple[ModeView, ...]


@dataclass(frozen=True)
class Linked:
    """One GNU-as source unit, assembled and LINKED BY THE BUILD at whatever
    address it lands -- placement by the build, not by the author's memory
    map, so two authors who picked the same free run stop colliding.

    `cave_addr=None` floats it exactly like a floating CavePatch (first free
    address after what precedes it, rounded to 0x80); a unit that other
    code names by ABSOLUTE address (mxldyn/octamax's `patch.s`, which
    `patch_scene2.s` reaches through `.equ SAVE_STUB, 0x400d64e0`) is
    pinned instead, and stays pinned until that upstream constant becomes
    a linker symbol. Detours, table entries and pokes name the unit's
    symbols (`m68k-elf-nm` after the link), never its addresses.

    `reference` = (address, sha256) of the unit as the AUTHOR'S OWN build
    linked it: the build links a second copy at that address every time
    and compares, so a source or toolchain drift from the bytes the author
    ratified fails loudly, even though the unit the image carries is
    linked somewhere else. The oracle links with the declared `defsyms`
    and this remix's `remix.inc`. A unit whose bytes depend on the remix
    (its `include`) gives a callable instead: reference(modules) ->
    (address, sha256), given the same modules `include` gets, naming the
    variant the author ratified for that selection.
    """

    label: str
    source: str                          # .s, repo-relative
    cave_addr: int | None = None         # None = floating
    cpu: str = "5407"                    # m68k-elf-as -mcpu= for the ROM-cave form; a DRAM unit is assembled for the chip (54455)
    reference: object | None = None      # (address, sha256), or a callable (see above)
    # DRAM: the unit is linked into octabam's PLATFORM RUNTIME -- one image
    # of every such unit in the remix, linked together (cross-unit symbols
    # resolve in the one link), packed, appended after the OS with the
    # loader (tools/remix/loader.S) and depacked at boot into the
    # platform's reserve at the bottom of the audio page arena (10 MiB,
    # tools/remix/arena.py; docs/remixer/PLACEMENT). `cave_addr` is
    # ignored. This is where anything bigger than a few hundred bytes
    # belongs; the ~8 KB of zero runs inside the OS image are for what
    # must be ROM.
    dram: bool = False
    # Assembler text generated PER REMIX -- include(modules) -> str, given
    # the remix's modules by key -- written beside the unit as `remix.inc`
    # and reachable by `.include "remix.inc"`. A unit whose data depends
    # on which modules are in the image (mode-defaults' view table) is
    # otherwise unlinkable: the source cannot know the remix.
    include: object | None = None
    # (name, value) pairs passed to both `m68k-elf-as --defsym` (so
    # `.ifdef NAME` sees them) and `m68k-elf-ld --defsym`, as
    # CavePatch.defsyms. Each value resolves to a global of a unit or cave
    # linked before this one, else the declared value; the `reference`
    # oracle uses the declared values. A name the source itself defines is
    # refused. DRAM units share one link, so two declaring one name must
    # resolve it to one value.
    # ARENA_BASE, declared, resolves to the remix's audio arena base (stock
    # 0x40a955e0, moved up by the platform reserve).
    defsyms: tuple[tuple[str, int], ...] = ()
    # A DRAM unit that is some module's label formatter, as
    # CavePatch.registers_formatter: the build writes the unit's
    # `registers_formatter.symbol` into that module's descriptor clone.
    registers_formatter: FormatterReg | None = None

    def __post_init__(self):
        if self.registers_formatter is not None and not (
                self.dram and self.registers_formatter.symbol):
            raise ValueError(f"Linked({self.label!r}): registers_formatter needs "
                             f"dram=True and a FormatterReg.symbol")
        names = [n for n, _v in self.defsyms]
        if len(names) != len(set(names)):
            raise ValueError(f"Linked({self.label!r}): a defsym name declared twice")
        if self.reference is not None and not callable(self.reference):
            reference_shape(self.label, self.reference)

    def reference_for(self, modules) -> tuple[int, str] | None:
        """(address, sha256) of the author's build for this selection."""
        if self.reference is None:
            return None
        ref = self.reference(modules) if callable(self.reference) else self.reference
        return reference_shape(self.label, ref)


def reference_shape(label: str, ref) -> tuple[int, str]:
    """`ref` as (address, sha256), or ValueError naming the unit."""
    if not (isinstance(ref, tuple) and len(ref) == 2 and isinstance(ref[0], int)
            and isinstance(ref[1], str) and len(ref[1]) == 64
            and all(c in "0123456789abcdef" for c in ref[1])):
        raise ValueError(f"Linked({label!r}): reference must be (address, sha256 hex), "
                         f"got {ref!r}")
    return ref


@dataclass(frozen=True)
class Detour:
    """A stock instruction rewritten to reach a linked unit's symbol.

    `kind`: "jmp" (the stub replays what it displaced and jumps back or on;
    the common case), "jsr" (the stub returns), or "lea" (the six-byte
    `lea abs.l,An` at `site` keeps its opcode and gets the symbol as its
    operand -- midisc's SAVE_ALL). `expect` is stock bytes at `site`, whole
    instructions. `pad_to` = total bytes to overwrite: the six-byte
    instruction then `nop`s, so a displaced span longer than six is not
    left half-rewritten (midisc's 8/10-byte sites); None writes six.
    `target` names a STOCK address instead of a symbol (midisc's
    TRACK_GATE/PAGE_GATE jump straight to stock code)."""

    site: int
    expect: bytes
    unit: str = ""                       # Linked.label ("" with `target`)
    symbol: str = ""
    note: str = ""
    kind: str = "jmp"
    target: int | None = None
    pad_to: int | None = None

    def __post_init__(self):
        written = self.pad_to or 6
        if len(self.expect) < written:
            raise ValueError(
                f"Detour at 0x{self.site:08x} ({self.note or self.symbol}): "
                f"expect is {len(self.expect)} bytes, the detour writes "
                f"{written}; the build asserts only `expect`, so the other "
                f"{written - len(self.expect)} would be overwritten unchecked")


@dataclass(frozen=True)
class TableGrow:
    """A stock pointer array relocated into free space with entries added,
    and every reference to the old array repointed -- busscreen's
    menu-state-table move, generalised. `old` is the stock array (`count`
    u32 entries), `symbols` the (unit, symbol) pairs to add, `refs` the
    (address, expected old-array u32) sites rewritten to the new address.
    The new array floats.

    `insert_at` places the symbols, as one block in declared order, before
    stock entry `insert_at`; None (or `count`) appends them. An insert
    renumbers every stock entry from `insert_at` up: stock code that
    indexes the array by a constant, and an index stored in a Part or a
    project, then names a different entry. The ledger refuses two modules
    growing one stock array."""

    label: str
    old: int
    count: int
    symbols: tuple[tuple[str, str], ...]
    refs: tuple[tuple[int, int], ...]
    insert_at: int | None = None

    def __post_init__(self):
        if self.insert_at is not None and not 0 <= self.insert_at <= self.count:
            raise ValueError(f"TableGrow({self.label!r}): insert_at {self.insert_at} is "
                             f"outside 0..{self.count}")

    def entries(self, stock: list[int], added: list[int]) -> list[int]:
        """The grown array: `stock` (the `count` entries read from the
        image) with `added` (the resolved symbols) placed at `insert_at`."""
        at = self.count if self.insert_at is None else self.insert_at
        return list(stock[:at]) + list(added) + list(stock[at:])


@dataclass(frozen=True)
class Poke:
    """A fixed-address rewrite of existing bytes, asserted first."""

    addr: int
    expect: bytes
    write: bytes
    note: str = ""


@dataclass(frozen=True)
class Keep:
    """Bytes this module relies on staying stock, claimed without writing.

    The ledger refuses any other module's write that overlaps them (a
    poke, detour, hook, cave, table or symbol ref, emit poke or runtime
    write); two modules keeping overlapping bytes compose when their
    `expect` agrees. The build asserts `expect` against the stock image and
    again against the finished image, so a write the ledger cannot see --
    a floating cave or grown table landing here, a menu clone, an arena
    literal -- is refused too. Writes made at run time by DRAM code are
    not in the image and are not checked."""

    addr: int
    expect: bytes
    note: str = ""


@dataclass(frozen=True)
class SymbolRef:
    """Rewrite one stock u32 data pointer to a linked symbol.

    Unlike a Detour this emits no opcode: descriptor tables and callback
    slots contain the address itself. The stock value is asserted before
    the symbol (plus an optional byte addend) is written.
    """

    addr: int
    expect: int
    unit: str
    symbol: str
    note: str = ""
    addend: int = 0


@dataclass(frozen=True)
class DramRegion:
    """Uninitialised DRAM a module's DRAM units name by `symbol`.

    Placed by the platform build at the TOP of the platform's arena reserve
    (arena.PLATFORM_PAGES, which any remix with DRAM units already pays
    for), stacked downward in declaration order, and handed to the link as
    `--defsym symbol=address`. The build refuses when the runtime, its
    loader stage or its .bss reach the lowest region. The loader never
    writes these bytes and nothing clears them: a region must not need
    initial contents. STEM REC's ring (8 MiB since piece 5) and its task's
    stack are the first users (git show 4d2d6456:docs/superpowers/specs/
    2026-09-10-stem-rec-poc-design.md, section 5)."""

    symbol: str
    size: int
    align: int = 16

    def __post_init__(self):
        if self.size <= 0:
            raise ValueError(f"DramRegion {self.symbol}: size must be positive")
        if self.align <= 0 or self.align & (self.align - 1):
            raise ValueError(f"DramRegion {self.symbol}: align must be a power of two")


@dataclass(frozen=True)
class Override:
    """This module's own claim at `site` stands in for another module's
    Detour there -- the way two mods that hook one stock instruction get to
    share it. A BRIDGE module carries a stub that does what both hooks did,
    in an order that respects each one's protocol, and declares an
    Override per detour it replaces: `module` is the other module's key.
    The build skips the overridden detour; the ledger treats the site as
    the bridge's; the overridden module must be in the remix, or the
    override is refused.
    """

    site: int
    module: str


@dataclass(frozen=True)
class Module:
    """One contribution, as declared by modules/<name>/manifest.py."""

    name: str                    # directory slug, e.g. "busverb"
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
    # Linker-backed ColdFire code (schema.Linked): units the build assembles
    # and links where it places them, wired in by symbol (Detour), plus
    # relocated-and-grown stock tables and plain asserted pokes.
    linked: tuple[Linked, ...] = ()
    # Uninitialised DRAM this module's linked units name by symbol
    # (schema.DramRegion) -- requires at least one dram=True Linked unit,
    # since a region with no unit to name it can never be referenced.
    dram_regions: tuple[DramRegion, ...] = ()
    detours: tuple[Detour, ...] = ()
    tables: tuple[TableGrow, ...] = ()
    symbol_refs: tuple[SymbolRef, ...] = ()
    pokes: tuple[Poke, ...] = ()
    # Stock bytes this module relies on and does not write (schema.Keep).
    keeps: tuple[Keep, ...] = ()
    # Claims of OTHER modules this module's own stand in for
    # (schema.Override) -- a bridge chaining two mods' hooks at one site.
    overrides: tuple[Override, ...] = ()
    # Module KEYS this one is meaningless without -- a bridge whose overrides
    # skip another module's writes on the promise that a third module's
    # stubs stand at those sites (scenes-p2-kits). The ledger refuses a
    # remix that selects it without them.
    requires: tuple[str, ...] = ()
    # (module KEY, why) for modules this one must never share an image with
    # although no byte overlaps -- two designs of one behaviour. The ledger
    # refuses the pair by name with the reason; the registry refuses a key
    # no module has.
    conflicts: tuple[tuple[str, str], ...] = ()
    # Which slot carries the MODE select, and what each of its positions
    # renames and re-defaults. Empty for a single-engine module.
    mode_slot: int | None = None
    mode_views: tuple[ModeView, ...] = ()
    name_selects: tuple[NameSelect, ...] = ()
    # ---- the module table (README.md, `make docs`) ------------------------
    # The selftest requires all four on every non-stock module; the README's
    # table is rendered from them (tools/remix/index.py --write) and
    # verify_docs refuses a stale copy.
    category: Category | None = None
    author: str = ""             # a GitHub handle or a name, as the table credits it
    author_url: str = ""         # the author's repository or profile
    proof: Proof | None = None
    proof_note: str = ""         # the unit, image and date; or the gate
    # ---- the checks (make check, make accept) ------------------------------
    # The verifiers `make check` runs when a remix carries this module
    # (schema.Gate). Shared gates -- the ledger selftest, the menu, the
    # dirty-state render, the set under the port -- stay in the Makefile.
    gates: tuple[Gate, ...] = ()
    # Every knob at its DEAREST setting, by the Param's own name: the modes
    # the pricer calls the worst loop, and the knobs that gate work (a send
    # at 0 registers nothing, MIX 0 short-circuits a stage) at their
    # maximum. The pressure render (tools/harness/pressure.py) and the
    # stress fixture (tools/harness/stress_project.py) read it; a DSP
    # module without one BLOCKS `make accept` for every remix that carries
    # it, by name, rather than being rendered at defaults. Validated
    # against `params` at load, so a knob rename refuses the build instead
    # of failing a fixture after the merge (PR #396 on #415).
    dear: dict[str, int] = field(default_factory=dict)
    # DSP work outside the FX pricer (for example a CF-registered source).
    # An explicit gap must block pressure qualification, never report N/A.
    pressure_blocker: str = ""
    # ---- settings (docs/proposals/BRAIN.md section 4.1) --------------------
    # The id the module's settings and stored defaults are filed under, and
    # the settings themselves. tools/remix/brain.py resolves them for a
    # remix; modules/<name>/brain.lock holds the released keys.
    store: Store | None = None
    settings: tuple[Setting, ...] = ()
    # The module's function is stored state: the build refuses it in a
    # remix without the BRAIN module, by name.
    requires_brain: bool = False
    # CODE CHOSEN BY A SETTING: variant(values) -> {field: value}, given the
    # module's Apply.BUILD settings resolved for the remix ({name: value},
    # an Option as its label). registry.bound() applies it once per remix,
    # so every reader of `linked`, `dsp`, `detours` or `gates` sees the
    # chosen code without asking (modules/usb-audio-out is the first).
    variant: object | None = None
    # The values a bound module was built with ({name: value}); empty on an
    # unbound one. An `include` callable reads them from the selection.
    build_values: Mapping = field(default_factory=dict, hash=False, compare=False)

    def bind(self, values: Mapping) -> "Module":
        """This module with its Apply.BUILD settings fixed to `values`."""
        over = self.variant(dict(values)) if self.variant is not None else {}
        bad = set(over) - {f.name for f in dataclasses.fields(self)} | ({"key", "name", "store", "settings"} & set(over))
        if bad:
            raise ValueError(f"{self.name}: variant returns {sorted(bad)}, which a variant may not set")
        return dataclasses.replace(self, build_values=MappingProxyType(dict(values)), **over)

    def write_spans(self):
        """Every fixed-address write this module declares, as (kind, start,
        length, label): pinned caves (`len(pinned)`), cave hooks
        (`len(hook_stock)`, at least the six-byte jsr), detours (the
        larger of `expect` and `pad_to` or six), table refs and symbol refs
        (four bytes), plain pokes. Floating caves and emit() pokes depend on
        placement and are the ledger's to evaluate."""
        for c in self.cf_patches:
            if c.cave_addr is not None:
                yield "cave", c.cave_addr, c.claim_len, c.label
            if c.hook_addr is not None:
                yield "hook", c.hook_addr, max(len(c.hook_stock), 6), c.label
        for d in self.detours:
            yield "detour", d.site, max(len(d.expect), d.pad_to or 6), d.note or d.symbol
        for t in self.tables:
            for addr, _old in t.refs:
                yield "table ref", addr, 4, t.label
        for r in self.symbol_refs:
            yield "symbol ref", r.addr, 4, f"{r.unit}:{r.symbol} ({r.note or hex(r.addr)})"
        for p in self.pokes:
            yield "poke", p.addr, len(p.expect), p.note or hex(p.addr)

    def __post_init__(self):
        for need in self.requires:
            if need in {k for k, _why in self.conflicts}:
                raise ValueError(f"{self.name}: {need!r} is in both requires and conflicts")
        for other, _why in self.conflicts:
            if other == self.key:
                raise ValueError(f"{self.name}: declares a conflict with itself")
        for k in self.keeps:
            for kind, start, length, label in self.write_spans():
                if start < k.addr + len(k.expect) and k.addr < start + length:
                    raise ValueError(
                        f"{self.name}: keeps 0x{k.addr:08x} ({k.note or 'kept bytes'}) "
                        f"and writes it ({kind} {label} at 0x{start:08x})")
        if self.params and len(self.params) != 12:
            raise ValueError(f"{self.name}: expected 12 param slots, "
                             f"got {len(self.params)}")
        if self.settings and self.store is None:
            raise ValueError(f"{self.name}: settings without a Store to file them under")
        if self.variant is not None and not any(s.apply is Apply.BUILD for s in self.settings):
            raise ValueError(f"{self.name}: a variant with no Apply.BUILD setting to choose it")
        for attr in ("key", "name"):
            seen = [getattr(s, attr) for s in self.settings]
            dup = sorted({v for v in seen if seen.count(v) > 1}, key=str)
            if dup:
                raise ValueError(f"{self.name}: two settings with {attr} {dup[0]!r}")
        pkeys = [p.key for p in self.params if p.key is not None]
        dup = sorted({k for k in pkeys if pkeys.count(k) > 1})
        if dup:
            raise ValueError(f"{self.name}: two params with key {dup[0]}")
        if pkeys:
            bare = [i for i, p in enumerate(self.params) if p.active and p.key is None]
            if bare:
                raise ValueError(f"{self.name}: drawn slot{'s' if len(bare) > 1 else ''} "
                                 f"{', '.join(map(str, bare))} carr{'y' if len(bare) > 1 else 'ies'} "
                                 f"no key while others do: key every drawn slot")
        if self.mode_views and self.mode_slot is None:
            raise ValueError(f"{self.name}: mode_views without a mode_slot")
        if self.mode_slot is not None:
            if self.mode_slot not in STEPPED_ONLY:
                raise ValueError(
                    f"{self.name}: mode_slot {self.mode_slot} -- a select can "
                    f"only sit on slot {', '.join(map(str, STEPPED_ONLY))}")
            _cnt = self.params[self.mode_slot].count if self.params else None
            _seen = set()
            for v in self.mode_views:
                if v.mode in _seen:
                    raise ValueError(f"{self.name}: two views for mode {v.mode}")
                _seen.add(v.mode)
                if _cnt is not None and v.mode >= _cnt:
                    raise ValueError(
                        f"{self.name}: a view for mode {v.mode}, but the "
                        f"select has {_cnt} positions")
                for slot, val in v.defaults.items():
                    _c = self.params[slot].count if self.params else None
                    if _c is not None and val >= _c:
                        raise ValueError(
                            f"{self.name}: mode {v.mode} defaults slot {slot} "
                        f"to {val}, past its {_c} positions")
        _name_slots = set()
        for select in self.name_selects:
            if select.slot in _name_slots or select.slot == self.mode_slot:
                raise ValueError(f"{self.name}: duplicate name selector on slot "
                                 f"{select.slot}")
            _name_slots.add(select.slot)
            if select.slot not in STEPPED_ONLY:
                raise ValueError(
                    f"{self.name}: name selector {select.slot} -- a select can "
                    f"only sit on slot {', '.join(map(str, STEPPED_ONLY))}")
            _cnt = self.params[select.slot].count if self.params else None
            _seen = set()
            for v in select.views:
                if v.defaults:
                    raise ValueError(
                        f"{self.name}: name selector {select.slot} view {v.mode} "
                        f"has defaults; only mode_slot may apply defaults")
                if v.mode in _seen:
                    raise ValueError(
                        f"{self.name}: name selector {select.slot} has two views "
                        f"for value {v.mode}")
                _seen.add(v.mode)
                if _cnt is not None and v.mode >= _cnt:
                    raise ValueError(
                        f"{self.name}: name selector {select.slot} has a view "
                        f"for value {v.mode}, but the select has {_cnt} positions")
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
        if self.menu is not None and self.menu.stock_dsp and (
                self.dsp is None or not self.dsp.hooks):
            raise ValueError(f"{self.name}: stock_dsp keeps {self.menu.replaces}'s "
                             f"dispatch entry, so its DspSection is reached only "
                             f"through DspHooks and must declare at least one")
        if self.dsp is not None and self.menu is None and not self.dsp.hooks:
            raise ValueError(f"{self.name}: DSP code with no menu entry and no "
                             f"DspHook is unreachable -- nothing dispatches it")
        if self.kind is Kind.STOCK and (self.dsp is not None or self.cf_patches):
            raise ValueError(f"{self.name}: a STOCK entry carries no code or "
                             f"caves -- they are already in the image (its "
                             f"params are READ from the stock descriptor, "
                             f"never written)")
        if self.dram_regions and not any(u.dram for u in self.linked):
            raise ValueError(f"{self.name}: declares DRAM regions but has no "
                             f"DRAM unit to name them")
        # A stepped select on page 1 was refused until 16 Sep 2026 (no module
        # had drawn one there; stock's selects are all on page 2). BusVerb's
        # SHFT is the first (page-1 slot 4, linked to SHMR); image 29 drew it
        # with its words on the unit.
        if self.dear:
            if self.dsp is None:
                raise ValueError(f"{self.name}: dear settings on a module with no DSP code")
            km = self.knob_map()
            for nm, val in self.dear.items():
                if nm not in km:
                    raise ValueError(f"{self.name}: dear names knob {nm!r}; its knobs are "
                                     f"{', '.join(km) or 'none'}")
                cnt = self.params[km[nm]].count or 128
                if not isinstance(val, int) or not 0 <= val < cnt:
                    raise ValueError(f"{self.name}: dear {nm}={val!r} is outside 0..{cnt - 1}")
        seen_scripts = set()
        for g in self.gates:
            if not isinstance(g, Gate):
                raise ValueError(f"{self.name}: gates holds {g!r}, not a schema.Gate")
            if g.script in seen_scripts:
                raise ValueError(f"{self.name}: gate {g.script} listed twice")
            seen_scripts.add(g.script)

    def view_for(self, mode: int):
        """The ModeView for a MODE value, or None. Unknown values fall back
        to the declared names, the same way every mode decode on the DSP side
        treats an unexpected select as its default engine."""
        for v in self.mode_views:
            if v.mode == mode:
                return v
        return None

    def name_views_for(self, slot: int) -> tuple[ModeView, ...]:
        """Rename views driven by `slot`, including the primary MODE slot."""
        if slot == self.mode_slot:
            return self.mode_views
        for select in self.name_selects:
            if select.slot == slot:
                return select.views
        return ()

    def knob_map_in(self, mode: int | None = None) -> dict[str, int]:
        """knob_map(), but with this MODE's renames applied. The remixer draws
        from here and the ColdFire cave is emitted from the same table, so the
        panel and the bench cannot drift apart."""
        base = self.knob_map()
        v = self.view_for(mode) if mode is not None else None
        if v is None:
            return base
        by_slot = {sl: nm for nm, sl in base.items()}
        by_slot.update({sl: nm.decode("latin1") for sl, nm in v.names.items()})
        return {nm: sl for sl, nm in by_slot.items()}

    def knob_map_all(self) -> dict[str, int]:
        """Every name a slot answers to: its own, plus each MODE view's alias.
        The test harness resolves `--set SCTR=40` through this, so a name the
        panel prints is a name the bench accepts."""
        out = dict(self.knob_map())
        for v in self.mode_views:
            for slot, nm in v.names.items():
                out.setdefault(nm.decode("latin1"), slot)
        return out

    def canon_name(self, slot: int) -> str:
        """The Param's OWN name for a slot -- what knob values are stored
        under, whatever the current mode calls it."""
        for nm, sl in self.knob_map().items():
            if sl == slot:
                return nm
        return ""

    @property
    def active_params(self) -> list[int]:
        """Slots the manifest declares drawn (active=True), in index order.
        A slot in inherited_enable is drawn or not as its donor's is."""
        return [i for i, p in enumerate(self.params) if p.active]

    @property
    def inherited_enable(self) -> tuple[int, ...]:
        """Slots whose enable nibble (draw and link bits) is the donor's:
        active=None on a MenuEntry(stock_dsp=True) clone. Empty params are
        twelve Param()s."""
        if self.menu is None or not self.menu.stock_dsp:
            return ()
        if not self.params:
            return tuple(range(12))
        return tuple(i for i, p in enumerate(self.params) if p.active is None)

    @property
    def linked_params(self) -> list[int]:
        """Slots whose enable nibble carries the link element (bit 1): the
        knob is bracketed to the one on its left."""
        out = []
        for i, p in enumerate(self.params):
            if not p.link:
                continue
            if i % 6 in (0, 3) or not self.params[i - 1].active:
                raise ValueError(f"{self.key}: slot {i} ({p.name!r}) links to "
                                 f"the left but has no drawn knob there in its row")
            out.append(i)
        return out

    @property
    def stepped_slots(self) -> tuple[int, ...]:
        return tuple(i for i, p in enumerate(self.params)
                     if p.formatter in (Formatter.STEPPED, Formatter.WIDE_STEPPED))

    @property
    def plain_slots(self) -> tuple[int, ...]:
        """Knobs drawn as the stock numeric dial: the build zeroes both
        formatter words whatever the donor's slot drew. Until 5 Oct 2026 the
        zeroing ran only for a module with a stepped slot; CF METER's SRC on
        FILTER's bipolar slot 3 drew as a balance dial."""
        return tuple(i for i, p in enumerate(self.params)
                     if p.formatter is Formatter.PLAIN)

    @property
    def wide_stepped_slots(self) -> tuple[int, ...]:
        """Labelled selects whose values use the full 128-position dial arc.

        The build installs one shared renderer hook for every such slot in a
        remix; modules do not own or duplicate the stock dial detour.
        """
        return tuple(i for i, p in enumerate(self.params)
                     if p.formatter is Formatter.WIDE_STEPPED)

    @property
    def bipolar_slots(self) -> tuple[int, ...]:
        """Knobs drawn as a balance dial, -64..+63 around 64 (the DSP still
        reads 0..127): SPRING BAL's renderer triple, verified only as
        build-time bytes until the first flash shows it."""
        return tuple(i for i, p in enumerate(self.params)
                     if p.formatter is Formatter.BIPOLAR)

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
# the bus accumulators SEND writes.
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
# no local test can reproduce a bus timing defect (AGENTS.md). The refusal is
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
    what every remix did to all fourteen of them before. An effect on
    neither chooser gives up its words (stock.harvested); the three reverbs
    are the default room, and a listed effect the placer reaches is refused
    by the build.

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
    # ---- the remix index (remixes/README.md, `make docs`) -----------
    family: str = ""             # "rig", "effects", "mods", "reference"
    proof: Proof | None = None   # schema.Proof; as a module's
    proof_note: str = ""
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
    # 0x400d6090, so it cannot grow in place -- tools/build/build_fx1.py proved the
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
    #     ⚠️ This is not theoretical and it is not new -- docs/firmware/DSP.md's "wrong
    #     claim 1" is this exact failure, bisected on hardware: a 16K layout
    #     at an FX1 base "runs to 0x53ff, through the other FX1 buffers and
    #     into FX2 slot 0".
    #   * A module with FIXED buffers in the FX2 region (BusVerb,
    #     BusDelay). An FX1 instance still writes to Y:0x4000 and up, i.e.
    #     into some other track's FX2 buffer. The hazard exists on FX2 too --
    #     it is why such a module is one per core -- but an FX1 row
    #     doubles the slots it can be reached from, a second instance on the
    #     SAME track included.
    #   * A bus SERVER, which is one per core by design (SPEC places one
    #     engine per payload). A second instance on a core is the open
    #     "duplicate instances corrupt audio after ~5.45 s" item.
    #
    # What is left is exactly the INSERT class (Spectrum, Character) -- and
    # SEND, which is buffer-free (untested there, but nothing measured
    # argues against it).
    # PLACED BUT NOT LISTED. Each key here is carried by the image -- code,
    # id, descriptor clone -- and takes NO CHOOSER ROW, with its twelve
    # parameter names blanked so the track page it lands on draws no knobs.
    #
    # This is how an effect stops being a per-track choice and becomes part
    # of the instrument: the two bus engines are hosted by the project stamp,
    # not by turning a chooser, and their controls live on a main-menu screen
    # instead of a track page (docs/firmware/MAINMENU.md section 6). Blanking the
    # NAMES is what empties the page: the parameter COUNTS and enable bits
    # stay, so the stock parameter writer still clamps and commits every slot
    # and the frame builder still carries it to the DSP -- measured in the
    # emulator, both halves (the page drew nothing; the writer
    # landed a value in the Part).
    #
    # ⚠️ IT BELONGS TO THE REMIX, NOT THE MODULE, and the bit-identity gate
    # is what said so: declared on the module, hiding the engines emptied
    # the plain `bus` image's chooser too, from three rows to one. A remix
    # hides an engine only when it also carries the screen that edits it.
    #
    # ⚠️ IT DOES NOT MAKE THE ID PRIVATE. Dispatch is per id and shared by
    # every track and both menus, so a saved part that names this id ANYWHERE
    # runs this code. A module that must run on one track only has to detect
    # that itself, the way modules/modulation does with its allocator slot.
    hidden: tuple[str, ...] = ()
    named: tuple[str, ...] = ()
    # THE HOST PAGE DRAWS ITS FIRST SLOTS ONLY (26 Sep 2026, Sam: "want
    # all the tracks to look the same"): (key, n) pairs. The hidden
    # module's page draws slots 0..n-1 under their manifest names (the rig:
    # DEL and REV, SEND's two knobs); the rest are blank-named. Unlike a
    # blanked module it keeps its label formatters, and its MODE rename
    # cave writes into the names table a linked unit exports as
    # `NAMES_<fx2 id, 2 hex digits>` (TEMPO BUS), never into the shared
    # descriptor, so a MODE turn puts no name back on the host page.
    host_slots: tuple[tuple[str, int], ...] = ()
    # LOCKED TO THE HOST SLOT (22 Sep 2026): a listed module runs only at
    # r7 == 0x6200, its core's position 0 (T1 on core 1, T5 on core 0), and
    # is an exact dry pass anywhere else -- the HOSTGUARD body hidden
    # engines already take, applied to a module that stays in the chooser.
    # Sam, 22 Sep 2026: the bus hosts on T1 and T5 as planned, every other
    # FX2 a SEND; a known working combination over a free one.
    locked: tuple[str, ...] = ()

    @property
    def blanked(self) -> tuple[str, ...]:
        """The hidden modules drawn EMPTY: hidden, nowhere on FX1 (one
        descriptor serves both menus) and not `named`. The ONE definition
        the build and every verifier share."""
        return tuple(k for k in self.hidden
                     if k not in self.fx1 and k not in self.named
                     and k not in dict(self.host_slots))
    # GRAINS PER LINE in BusDelay's GRAIN mode: 4 (the source's own) or 2.
    #
    # A CYCLE LEVER, not a voicing choice. The delay's core cannot carry four
    # active stations beside a four-grain GRAIN -- 3,294 of 3,120 usable by
    # the pricer -- and at two grains it fits with room. The cost is half the
    # simultaneous grain voices.
    #
    # build_bus.py substitutes at three markers in the engine: the two rolled
    # loops count 2, the grain-to-grain phase offset doubles (G/4 -> G/2, so
    # two grains still tile the cycle), and the makeup doubles, because four
    # triangle windows at quarter offsets sum to exactly 2 while two at half
    # offsets sum to exactly 1.
    #
    # ⚠️ The two-grain build is the BETTER-CHECKED one: two triangle windows
    # a half period apart sum to exactly 1, so DC in must come back flat --
    # the gate that caught a double-rate window (AGENTS.md, the a0 trap).
    # Four at quarter
    # offsets have no such exact identity.
    grains: int = 4
    fx1: tuple[str, ...] = ()
    # LAYER 2 OF EACH SETTING (docs/proposals/BRAIN.md section 4.2):
    # (store id, setting name) -> a value (a new default the card and the
    # project may still change) or Pin(value) (fixed: no row, nothing stored).
    # An Option takes a label or an index. tools/remix/brain.py checks every
    # entry against the selected modules.
    settings: Mapping = field(default_factory=dict, hash=False)
    # LAYER 2 OF EACH KNOB DEFAULT (docs/proposals/BRAIN.md section 4.2):
    # (module key, mode, knob) -> byte. `mode` is the MODE select's label or
    # value, or None for the knob's own default (Param.default); `knob` is the
    # Param's name, or the name the mode's view gives it. It replaces that
    # default in this image's descriptor or MODE DEFAULTS table.
    defaults: Mapping = field(default_factory=dict, hash=False)

    def __post_init__(self):
        if self.grains not in (2, 4):
            raise ValueError(f"grains={self.grains}: BusDelay's GRAIN reader "
                             f"is built for 4 or 2 per line, nothing else")
        if self.fallback != NO_FALLBACK and self.fallback not in self.modules:
            raise ValueError(
                f"remix {self.name!r}: fallback {self.fallback!r} is not in "
                f"the remix, so ids aliased to it would dispatch nowhere")
        bad = [k for k in self.locked if k not in self.modules]
        if bad:
            raise ValueError(f"remix {self.name!r}: locked={bad} are not in the remix")
        bad = [k for k in self.hidden if k not in self.modules]
        if bad:
            raise ValueError(f"remix {self.name!r}: hidden={bad} are not in the remix")
        bad = [k for k in self.named if k not in self.hidden]
        if bad:
            raise ValueError(
                f"remix {self.name!r}: named={bad} are not in hidden -- "
                f"`named` only says which HIDDEN modules keep their names")
        bad = [k for k, _ in self.host_slots if k not in self.hidden or k in self.named]
        if bad:
            raise ValueError(
                f"remix {self.name!r}: host_slots={bad} must be hidden and not named")
        bad = [n for _, n in self.host_slots if not 0 < n < 12]
        if bad:
            raise ValueError(f"remix {self.name!r}: host_slots counts {bad}: 1..11")
        if len(set(self.modules)) != len(self.modules):
            raise ValueError(f"remix {self.name!r}: duplicate module keys")
        # ⚠️ NO PER-KEY CHECK HERE. An fx1 key may be a STOCK effect,
        # which need not be in `modules` at all -- FX1's list and FX2's
        # are independent. What each key may be is decided where the
        # registry is in scope: build_bus.py refuses, selftest pins it.
        if len(set(self.fx1)) != len(self.fx1):
            raise ValueError(f"remix {self.name!r}: duplicate fx1 keys")
