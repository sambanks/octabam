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

  SERVER  harness.is_server -- pays the bus costs, lives in ONE payload, and
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

SERVER, INSERT, STOCK, SYSTEM = "server", "insert", "stock", "system"


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


def menus(mod) -> tuple[str, ...]:
    """The chooser(s) this module has a row on.

    FX1 and FX2 are two slots on the SAME track -- the payload split decides
    which TRACKS a module can appear on, never which slot -- and stock gives
    them different lists: ten effects on FX1, those ten plus DELAY and the
    three reverbs on FX2.

    Our own modules are FX2-only, and that is a BUILD limit rather than a
    hardware one. The DSP dispatch tables are indexed by the raw id and
    SHARED between the two menus, so a module's code already runs from FX1
    the moment FX1 selects its id (that is exactly how Rungs ran wherever
    FX1 chose EQUALIZER). What is missing is the panel side: FX1's 15-entry
    chooser cannot grow in place and has to be relocated to a cave
    (`tools/build_fx1.py` proved it can be), and no manifest field asks for
    a row. `verify_menu` asserts FX1's list and id lookup are byte-identical
    to stock, deliberately, until that lands.
    """
    from remix import stock as _stock
    if mod.menu is None:
        return ()
    if mod.is_stock:
        return (FX1, FX2) if mod.menu.fx2_id in _stock.fx1_ids() else (FX2,)
    return (FX2,)


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
