"""What a module IS, in the terms the remixer and the harness need.

Everything below this speaks modules and payloads. This layer answers the
questions a person asks instead: what kind of thing is this, which tracks can
host it, which chooser does it appear on, what does the image on disk
actually offer.

⚠️ The per-TRACK rig this file was named for is GONE (2 Sep 2026). Eight
tracks with an effect on each was a second place to say what a remix already
says, and knob values belong to the EFFECT rather than to a track -- so the
remixer is one page about an image, and `State.knobs_for(mod)` holds the
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
          track. No knobs here: the remixer has no manifest for stock
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
# one place the remixer states it.
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
    # ⚠️ CAPABILITY, NOT CURRENT ROWS -- deliberately, after trying the other
    # way on 3 Sep 2026. Gating the FX2 half on "is it in the image" is more
    # literally true (an unlisted FLANGER really has no FX2 row) and it made
    # the LIBRARY worse: every module you had not added yet read `—`, which
    # the missing ✓ beside it already said, in place of the one thing the
    # library is for -- what this effect COULD be. The consequence of leaving
    # a stock effect out belongs on its resource line, where there is room to
    # say it in words; see resources().
    on = []
    if mod.is_stock or mod.menu.replaces:
        # A replacement inherits its target's menus, because it inherits its
        # id and the build repoints both of FX1's tables to it.
        # A replacement CARRIES the stock effect's id, so its own fx2_id is
        # already the one to test.
        fx2_id = mod.menu.fx2_id
        if fx2_id in _stock.fx1_ids():
            on.append(FX1)
    elif mod.key in fx1_rows:
        on.append(FX1)
    on.append(FX2)
    return tuple(on)


# The MAIN MENU's tables: the five list descriptors and the row arrays they
# point at (docs/MAINMENU.md section 2). A remix changes the top-level menu
# only by writing here, so comparing this span against the pristine image
# answers "does this selection change the main menu" exactly, instantly, and
# without booting anything.
MENU_TABLES = (0x400cbc00, 0x400cc700)

# The id-indexed tables each menu resolves, and the two name fields inside a
# page descriptor (docs/PARAM_PAGES.md section 2). Read from the BUILT image
# rather than from the manifest: the manifest is what was ASKED for, and the
# whole point of looking is that a cloned descriptor can carry something else.
_FX1_IDS, _FX2_IDS = 0x400d5f58, 0x400d5fdc
_FX1_ID2POS, _FX2_ID2POS = 0x400d60d0, 0x400d6150
_NONE_DESC = 0x400d4618
_P_ABBR, _P_FULLNAME = 0x04, 0x09
_P_NAMES, _P_PENABLE_LO, _P_PENABLE_HI = 0x16, 0x18e, 0x18a


def drawn_as(fx2_id: int, img: bytes | None = None):
    """What the built image will make the unit PRINT for this id, and the
    chooser row each menu opens on.

    -> {"name", "abbr", "slots", "fx1", "fx2"} -- fx1/fx2 being the cursor
    row or None when that menu does not list the id at all -- or None if
    there is no image. `img` defaults to the built one; verify_menu passes
    the bytes it already has.
    """
    if img is None:
        from remix.state import BUILT_IMAGE
        if not BUILT_IMAGE.exists():
            return None
        img = BUILT_IMAGE.read_bytes()
    base = 0x40000400

    def rd32(a):
        i = a - base
        return int.from_bytes(img[i:i + 4], "big") if 0 <= i < len(img) - 3 else 0

    def field(p, off, n):
        i = p - base + off
        return img[i:i + n].split(b"\0")[0].decode("latin1", "replace")

    p2 = rd32(_FX2_IDS + fx2_id * 4)
    p1 = rd32(_FX1_IDS + fx2_id * 4)
    desc = p2 if p2 and p2 != _NONE_DESC else p1
    if not desc or desc == _NONE_DESC:
        return None
    # THE TWELVE SLOT NAMES the panel will print, and which are enabled --
    # the same two words stock.py reads, from the same descriptor. This is
    # the field a CLONE inherits from its donor, so reading it back out of
    # the built image is the check that the build wrote what was asked for.
    lo = rd32(desc + _P_PENABLE_LO)
    hi = rd32(desc + _P_PENABLE_HI)
    slots = []
    for i in range(12):
        on = bool(((lo if i < 8 else hi) >> (4 * (i if i < 8 else i - 8))) & 1)
        nm = field(desc, _P_NAMES + i * 6, 6)
        slots.append(nm if on and nm else None)
    return {"name": field(desc, _P_FULLNAME, 13),
            "abbr": field(desc, _P_ABBR, 5),
            "slots": tuple(slots),
            "fx1": (rd32(_FX1_ID2POS + fx2_id * 4)
                    if p1 and p1 != _NONE_DESC else None),
            "fx2": (rd32(_FX2_ID2POS + fx2_id * 4)
                    if p2 and p2 != _NONE_DESC else None)}


def menu_patched() -> int:
    """Bytes of the MAIN MENU tables this build changed. 0 = the unit's own
    menu, unchanged -- which is every remix so far."""
    from remix.state import BUILT_IMAGE
    from remix import stock as _stock
    img = BUILT_IMAGE.read_bytes() if BUILT_IMAGE.exists() else None
    raw = _stock._image()
    if img is None or raw is None:
        return 0
    lo, hi = (a - 0x40000400 for a in MENU_TABLES)
    return sum(1 for i in range(lo, min(hi, len(img), len(raw)))
               if img[i] != raw[i])


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
    #
    # ⚠️ A STOCK EFFECT SAYS WHAT IT USES, like everything else here. It used
    # to say "free", which is a MARGINAL cost worn as an absolute: listing it
    # costs no donor words because its code is already placed, and that is
    # true -- but in a remixer whose whole point is mixing stock and ours
    # freely, one kind of effect answering "how much does this use?" with
    # "free" and the other with "2,411 of 2,724 words" makes them look like
    # different KINDS of thing. They are not. They are effects, and every one
    # of them occupies words, a buffer slot and cycles.
    if mod.is_stock:
        w = stock.WORDS.get(mod.key, 0)
        if mod.key in stock.CONSUMED:
            # These three are the exception that proves it: their words ARE
            # the donor region, so they are the only stock effects whose
            # words are yours to take.
            at = stock.consumed_at(mod.key)
            out.append(f"{w:,} words — and they are the donor region")
            out.append("yours overwrite it first" if at == 0 else
                       f"survives while your modules stay under {at:,} words")
        elif w:
            # The consequence, not the mechanism: they are not in the donor
            # region, so they are not yours to trade either way.
            out.append(f"{w:,} words, already placed — listing it costs none "
                       f"and dropping it frees none")
        else:
            out.append("no DSP words — it runs on the ColdFire side")
        # WHAT LEAVING IT OUT ACTUALLY COSTS, in words rather than by a dash
        # in a column. The two menus are not symmetric: FX1's chooser is
        # stock's own and no image shortens it, so an unlisted effect that
        # FX1 lists is still there on FX1 -- and one FX2 only ever listed
        # (DELAY, the three reverbs) is gone from the panel entirely.
        if not selected:
            out.append("not listed — it keeps its FX1 row; only the FX2 one "
                       "is lost" if mod.menu.fx2_id in stock.fx1_ids()
                       else "not listed — and it was FX2-only, so it has no "
                            "row at all in this image")
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
        # The `1` hint only where `1` would work. Offering it beside an
        # effect you are merely previewing, or one the build would refuse,
        # sends you to a refusal you could have been told about here --
        # which is what this line exists for.
        from remix.state import fx1_hazard
        why = fx1_hazard(mod) if not mod.is_stock else None
        if why:
            out.append(f"FX1  no row — and cannot take one: {why}")
        elif selected and not mod.is_stock and mod.menu is not None:
            out.append("FX1  no row — 1 adds one: no words, 4 slots of "
                       "cycles")
        else:
            out.append("FX1  no row — takes nothing")

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
    ledger's own `fixed` test, in one place so the remixer cannot drift
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
