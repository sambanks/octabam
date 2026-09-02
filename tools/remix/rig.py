"""What a module IS, in the terms the workbench and the harness need.

Everything below this speaks modules and payloads. This layer answers the
questions a person asks instead: what kind of thing is this, which tracks can
host it, which chooser does it appear on, what does the image on disk
actually offer.

⚠️ The per-TRACK rig this file was named for is GONE (2 Sep 2026). Eight
tracks with an effect on each was a second place to say what a remix already
says, and knob values belong to the EFFECT rather than to a track -- so the
workbench is one page about an image, and `State.knobs_for(mod)` holds the
values. The helpers below survived because they were never about tracks:
they are about modules.

Categories and track ranges are DERIVED from the manifests, never declared
here -- the manifest is the single place a module states what it is
(schema.py's whole reason to exist):

  BUS     harness.is_server -- pays the bus costs, lives in ONE payload, and
          the payload decides its tracks: A serves TRACKS 5-8, B serves
          TRACKS 1-4 (measured 10 Aug 2026 via the MrkVerb32 marker flash,
          INVERTED from every earlier assumption -- test the reverb on
          track 5, not track 1).
  INSERT  a DSP_EFFECT with a menu entry and no server role -- sits in both
          payloads, runs on any track.
  STOCK   a stock FX2 effect the remix keeps in the chooser (Kind.STOCK,
          tools/remix/stock.py) -- code already in both payloads, any
          track. No knobs here: the workbench has no manifest for stock
          params, and no local render yet either.
  SYSTEM  everything else: the SEND client, ColdFire patches. Plumbing the
          image needs, never something you put on a track.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from remix import registry  # noqa: E402
from remix.schema import Kind  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]

TRACKS = range(1, 9)
# Which tracks each payload's core serves. Measured 10 Aug 2026 (MrkVerb32
# marker flash); the inversion from old docs cost two flashes, so this is the
# one place the workbench states it.
PAYLOAD_TRACKS = {"A": range(5, 9), "B": range(1, 5)}

# BUS, not "server". It is the natural opposite of INSERT and the word this
# project already uses for the thing itself (docs/XBUS.md, `make bus`, the
# bus accumulators): an effect either sits IN a track or is fed BY tracks
# over the bus. The module KEYS stay "REVERB SERVER"/"DELAY SERVER" -- they
# are written into saved remixes and the build report -- and `is_server` is
# still what the manifest declares. This is the word the operator reads.
BUS, INSERT, STOCK, SYSTEM = "bus", "insert", "stock", "system"
SERVER = BUS                    # the old name, for anything still saying it


def category(mod) -> str:
    if mod.harness is not None and mod.harness.is_server:
        return SERVER
    if mod.kind is Kind.STOCK:
        return STOCK
    if mod.kind is Kind.DSP_EFFECT and mod.menu is not None:
        return INSERT
    return SYSTEM


def track_range(mod) -> range:
    """Tracks this module can be selected on. Empty range for SYSTEM."""
    cat = category(mod)
    if cat in (INSERT, STOCK):
        return TRACKS
    if cat == SYSTEM:
        return range(0)
    # A server lives in exactly one payload, and the manifest says which.
    # frozenset({"A","B"}) is the field's default, i.e. "never stated" -- a
    # server carrying it would silently show up on all eight tracks, so
    # refuse loudly instead (selftest.py holds this line for every module).
    p = mod.dsp.payloads if mod.dsp is not None else None
    if p is None or len(p) != 1:
        raise ValueError(
            f"{mod.name}: a SERVER must declare its single payload "
            f"(dsp.payloads), got {sorted(p) if p else p}")
    return PAYLOAD_TRACKS[next(iter(p))]


def effects() -> list:
    """Every module that can sit on a track (servers + inserts), by name."""
    return sorted((m for m in registry.modules().values()
                   if category(m) != SYSTEM), key=lambda m: m.name)


def available(track: int) -> list:
    return [m for m in effects() if track in track_range(m)]


# ---- which MENU a module appears on ----------------------------------------
FX1, FX2 = "FX1", "FX2"


def menus(mod, fx1_rows=()) -> tuple[str, ...]:
    """The chooser(s) this module has a row on.

    FX1 and FX2 are two slots on the SAME track -- the payload split decides
    which TRACKS a module can appear on, never which slot -- and stock gives
    them different lists: ten effects on FX1, those ten plus DELAY and the
    three reverbs on FX2.

    Our own modules are FX2-only UNLESS THEY REPLACE A STOCK EFFECT, in
    which case they take that effect's FX1 row as well -- the build repoints
    both FX1 tables (build_bus.py, docs/MODULES.md), confirmed by asking the
    emulated firmware to draw the page. Everything below is about a module
    wanting a NEW row rather than an existing one.

    And since 3 Sep 2026 a REMIX can ask for the row outright: `Remix.fx1`
    lists the modules that also get one, `fx1_rows` here is that set, and the
    build relocates FX1's chooser into the cave and writes FX1's own id and
    cursor tables. It costs no words -- the DSP dispatch is one table indexed
    by the raw id and shared by both menus, so the code already ran from FX1
    the moment FX1 selected its id (that is exactly how Rungs ran wherever
    FX1 chose EQUALIZER); what was missing was only the panel side, and only
    because FX1's list ends at 0x400d608c with FX2's beginning four bytes
    later. What it does cost is cycles: an FX1 effect runs on a track that is
    already running an FX2 one.

    `verify_menu` asserts FX1's list and id lookup are byte-identical to
    stock APART FROM the entries a declared replacement or a declared
    `Remix.fx1` row owns.
    """
    from remix import stock as _stock
    if mod.menu is None:
        return ()
    if mod.is_stock:
        return (FX1, FX2) if mod.menu.fx2_id in _stock.fx1_ids() else (FX2,)
    # A replacement inherits its target's menus, because it inherits its id
    # and the build repoints both of FX1's tables to it.
    if mod.menu.replaces:
        return (FX1, FX2) if mod.menu.fx2_id in _stock.fx1_ids() else (FX2,)
    return (FX1, FX2) if mod.key in fx1_rows else (FX2,)


# ---- what the BUILT IMAGE offers -------------------------------------------
# The rig says what the operator is auditioning; this says what the image on
# disk would actually put in the FX2 chooser, which is not the same thing --
# the composer's live selection can be ahead of the last build, and the emu
# view boots the FILE. Read from the image so the answer is the image's, not
# a re-derivation of what we think we built.
#
# ⚠️ The two constants are copies. `tools/build_bus.py` writes the list and
# `tools/verify_menu.py` checks it, and both spell them out with the same
# provenance note; a third copy is the price of not importing a verify script
# for its globals (verify_menu binds REMIX from the environment at import,
# which is exactly the wrong source of truth here). If the caves ever move,
# they move in three places -- `verify_menu` fails loudly if they disagree.
BUILT_IMAGE = ROOT / "out/mainos_bus.bin"
_LIST_REF = 0x400375f4                  # the operand naming the live list
_LIST_CAVES = (0x400d6b00, 0x400d7bbc)  # short list, or the long one


def built_chooser(image=None) -> list[tuple[int, object]]:
    """The FX2 chooser rows the built image offers, in the panel's own order.

    -> [(fx2_id, module_or_None)], empty if there is no image or its list
    does not land in a known cave. `module_or_None` is None for an id no
    manifest claims, which should not happen in an image we built and is
    surfaced rather than hidden if it does.
    """
    from dsp_modmap import BASE
    img_path = pathlib.Path(image) if image else BUILT_IMAGE
    if not img_path.exists():
        return []
    img = img_path.read_bytes()

    def rd32(a):
        i = a - BASE
        return int.from_bytes(img[i:i + 4], "big") if 0 <= i <= len(img) - 4 else 0

    live = rd32(_LIST_REF)
    if live not in _LIST_CAVES:
        return []
    rows, a = [], live
    while len(rows) < 32:                    # the long cave's capacity
        ptr = rd32(a)
        if not ptr:                          # the list's own terminator
            break
        fx_id = rd32(ptr) & 0xff             # descriptor's own id word, P+0
        rows.append((fx_id, registry.by_id(fx_id)))
        a += 4
    return rows


def default_knobs(mod) -> dict[str, int]:
    """Manifest defaults for every named, drawn slot -- the values a fresh
    part boots with, which is also the honest render baseline (the SHMR=64
    lesson: a stale default pollutes every measurement)."""
    return {p.name.decode(): (p.default or 0)
            for p in mod.params if p.name and p.active}


def knob_doc(mod, name: str) -> str:
    """The manifest's one-line answer to "what is this knob?"."""
    return mod.params[mod.knob_map()[name]].doc or ""


def knob_labels(mod, name: str):
    """Per-value labels for a select, or None for a plain dial."""
    return mod.params[mod.knob_map()[name]].labels


def knob_max(mod, name: str) -> int:
    """Highest legal value: count-1 where the manifest states a count,
    else the stock 0..127 dial."""
    slot = mod.knob_map()[name]
    count = mod.params[slot].count
    return (count - 1) if count is not None else 127


def resources(mod, words=None, fx1_rows=(), selected=True) -> list[str]:
    """What this effect COSTS, ONE LINE PER MENU.

    Shown while scrolling, because "will this fit beside what I have" is what
    the library pane is really being asked, and every answer used to arrive
    only as a refusal after adding it.

    ⚠️ THE MENUS ARE SEPARATE and running them together was unreadable. FX1
    and FX2 have their OWN allocator tables (measured, X:0x255 in both
    payloads): FX1 hands out 0x1000/0x1c00/0x2800/0x3400 at 3,072 words
    each, FX2 hands out 0x4000/0x8000 plus a shared-window pair at 16,384.
    They do not overlap, so a cost on one is not a cost on the other -- and
    saying so in a subordinate clause ("FX2 rows only, FX1 keeps its 4") made
    a simple fact sound like a caveat. A line each states it instead.

    Derived wherever it can be: private Y is scanned from the module's own
    source, caves counted from the manifest, words taken from a real build,
    the affected stock effects read off their claims.
    """
    from remix import ledger, stock
    from remix.schema import YBase
    out = []

    # ---- the donor region: words ----------------------------------------
    if mod.is_stock:
        if mod.key in stock.CONSUMED:
            at = stock.consumed_at(mod.key)
            out.append("yours overwrite it first" if at == 0 else
                       f"free while your modules stay under {at:,} words")
        else:
            out.append("free — already in the image")
    elif words:
        out.append(f"{words} of 2,724 words")
    elif mod.dsp is not None:
        out.append("measuring…")

    # ---- one line per menu ----------------------------------------------
    allocates = (getattr(mod, "claims", None) is not None
                 and mod.claims.stock_instance_buffer)
    on = menus(mod, fx1_rows)
    pins = (getattr(mod, "claims", None) is not None
            and mod.claims.owns_fx2_buffers)
    window = mod.dsp is not None and mod.dsp.ybase is not YBase.NEVER

    if mod.menu is None:
        pass                    # no chooser row at all: neither menu applies
    elif FX1 in on:
        # ⚠️ AN FX1 ROW IS FREE IN WORDS AND NOT FREE. The code is already
        # placed either way -- the dispatch table is shared -- so the only
        # bill is CYCLES, and it is a big one: FX1 is four more slots on the
        # same four tracks, so listing an effect on both menus can double the
        # worst per-core load. The Budget's cycles row carries the number.
        out.append("FX1  " + ("takes 1 of the 4 slots (3,072 words each)"
                              if allocates else "no buffer")
                   + (" · a row costs no words, 4 slots of cycles"
                      if mod.key in fx1_rows else ""))
    else:
        # Not on FX1 at all, so the FX1 allocator never hands it anything.
        # The `1` hint only where `1` would work: on an effect that is in
        # the image. Offering it beside one you are merely previewing sends
        # you to a refusal.
        out.append("FX1  no row — 1 adds one: no words, 4 slots of cycles"
                   if selected and not mod.is_stock and mod.menu is not None
                   else "FX1  no row — takes nothing")

    if mod.menu is None:
        pass
    elif pins or window:
        # WHAT THIS MODULE PINS, AND WHERE. The list of stock effects it
        # costs you does NOT belong here: it is the same seven for every
        # pinner, so printing it per module made ChonVerb and BongDelay look
        # like two separate bills for one debt. It is a property of the
        # SELECTION -- the ledger refuses an allocating stock effect beside
        # ANY pinner -- so the LOADED pane states it once.
        #
        # What genuinely differs is which slots, on which core, for which
        # tracks, and that is worth saying: ChonVerb is all four of core 0's
        # and BongDelay two of core 1's, and they serve different tracks.
        n = 2 * pins + 2 * window
        which = ("all 4 buffer slots" if n == 4 else
                 "2 core-private buffer slots" if pins else
                 "2 shared-window buffer slots")
        tr = track_range(mod)
        where = (f"on the core serving tracks {tr.start}-{tr.stop - 1}"
                 if len(tr) and len(tr) != len(TRACKS)
                 else "on whichever core hosts it")
        out.append(f"FX2  pins {which} {where}")
    elif allocates:
        out.append("FX2  takes 1 of the 4 slots (16,384 words each)")
    else:
        out.append("FX2  no buffer")

    # ---- everything else -------------------------------------------------
    py = ledger.private_y(mod)
    if py:
        out.append(f"{len(py)} core-private Y word"
                   f"{'s' if len(py) != 1 else ''}")
    caves = list(mod.cf_patches)
    if caves:
        hooks = sum(1 for c in caves if c.hook_addr is not None)
        out.append(f"{len(caves)} ColdFire cave{'s' if len(caves) != 1 else ''}"
                   + (f", {hooks} hooked" if hooks else ""))
    return out


def _allocating_on_fx1() -> int:
    """How many of the allocating stock effects FX1 also lists -- the ones a
    remix does NOT take away from you. The reverbs are not among them, which
    is why this is counted rather than assumed to be all of them."""
    from remix import stock
    return sum(1 for m in stock.MODULES
               if m.claims is not None and m.claims.stock_instance_buffer
               and FX1 in menus(m))


def allocating_names() -> str:
    """WHICH stock effects a buffer-pinning module costs you, by name.

    It is a fixed set, so naming it beats counting it -- "blocks 7 stock
    effects" makes you go and find out which seven, and the answer never
    changes. The three reverbs collapse to a phrase because they always go
    together (their code IS the donor region) and spelling all three out
    doubles the line for nothing.

    ⚠️ WHAT IS LOST IS THE FX2 ROW, NOT THE EFFECT. Leaving a stock effect
    out of a remix takes its chooser row and nothing else -- its code,
    descriptor and dispatch stay stock on both cores -- so FLANGER, CHORUS,
    SPATIALIZER and COMB are still there on FX1, and still work.

    And the collision cannot follow them there. The allocator keeps SEPARATE
    tables: FX1 hands out 0x1000/0x1c00/0x2800/0x3400 at 3,072 words each,
    topping out at 0x3fff, while every FX2 buffer a module of ours pins
    starts at 0x4000 or in the shared window (measured, X:0x255 in both
    payloads). An FX1 allocation physically cannot reach them. The three
    reverbs are the exception only because FX1 never listed them.

    Derived from the manifests, not written down: it went from four to seven
    the day the reverbs became listable.
    """
    from remix import stock
    names = [m for m in stock.MODULES
             if m.claims is not None and m.claims.stock_instance_buffer]
    revs = [m for m in names if m.key in stock.CONSUMED]
    rest = [m.menu.fullname.decode("latin1").title()
            for m in names if m.key not in stock.CONSUMED]
    if len(revs) == len(stock.CONSUMED) and revs:
        rest.append(f"the {len(revs)} reverbs")
    elif revs:
        rest += [m.menu.fullname.decode("latin1").title() for m in revs]
    return ", ".join(rest[:-1]) + " and " + rest[-1] if len(rest) > 1 else \
        (rest[0] if rest else "nothing")


def pins_fx2(mod) -> bool:
    """Does this module hold FX2 instance buffers at fixed addresses? The
    ledger's own `fixed` test, in one place so the workbench cannot drift
    from it (it did: BongDelay declares owns_fx2_buffers=False because its
    lines are in the shared window, and the pane said nothing about buffers
    for it while the ledger refused it beside all seven)."""
    from remix.schema import YBase
    c = getattr(mod, "claims", None)
    return bool((c is not None and c.owns_fx2_buffers)
                or (mod.dsp is not None and mod.dsp.ybase is not YBase.NEVER))


def pinned_slots(mod) -> int:
    """How many of a core's FOUR FX2 buffer slots this module holds fixed.

    owns_fx2_buffers is the two CORE-PRIVATE slots (0x4000/0x8000); a
    substituted ybase is the two SHARED-WINDOW ones (0x30000/0x34000 on core
    0, 0x38000/0x3c000 on core 1 -- measured, X:0x255 in both payloads).
    ChonVerb has both and so holds all four; Nimbus the first pair;
    BongDelay the second.
    """
    from remix.schema import YBase
    c = getattr(mod, "claims", None)
    return (2 * bool(c is not None and c.owns_fx2_buffers)
            + 2 * bool(mod.dsp is not None and mod.dsp.ybase is not YBase.NEVER))
