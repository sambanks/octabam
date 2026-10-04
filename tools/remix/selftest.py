#!/usr/bin/env python3
"""Prove the ledger catches what it claims to catch, and every shipped remix
is clean.

Each case builds two modules that collide in one specific way and asserts
the ledger names both; a clean pair must stay clean.

    python3 tools/remix/selftest.py
"""

import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
ROOT = pathlib.Path(__file__).resolve().parents[2]

from remix import ledger, registry, schema, state, stock  # noqa: E402
from remix.schema import (BusRole, CavePatch, Claims, Detour, DspHook, DspRange,  # noqa: E402
                          DspSection, Formatter, Keep, Kind, MenuEntry, Module, Param,
                          Poke, SymbolRef, TableGrow, YBase)


def _effect(name, fx2_id, priority=0, reserved=(), buffers=False,
            ybase=YBase.NEVER, ptable=(), asm="does/not/exist.asm"):
    return Module(
        name=name, key=name.upper(), kind=Kind.DSP_EFFECT,
        doc="fixture",
        menu=MenuEntry(fx2_id=fx2_id, donor_desc=0x400d58b8,
                       abbr=b"FIX", fullname=b"Fixture"),
        params=tuple([Param(b"A", 0, active=True)] + [Param()] * 11),
        # No asm path on disk, so the ledger's scan finds nothing and only
        # the reserved words below are claimed -- which is what lets these
        # fixtures test the claim path in isolation.
        dsp=DspSection(asm=asm, priority=priority, ybase=ybase,
                       ptable=ptable),
        claims=Claims(reserved_private_y=reserved,
                      owns_fx2_buffers=buffers),
    )


# A source that addresses the stock curve bank X:0x4840 by literal -- the
# one claim the ledger derives from the TEXT of a source, so it needs a file
# on disk (an absolute path: ledger joins it to ROOT, which pathlib leaves
# absolute).
import tempfile  # noqa: E402
_HARD_ASM = pathlib.Path(tempfile.mkdtemp(prefix="octabam_selftest_")) / "hard.asm"
_HARD_ASM.write_text("        move    x:>$4a40,x0             ; curve 4's base\n"
                     "        rts\n")


def _hooked(name, site=0x88, payloads=frozenset({"A"}), sram=()):
    """A DSP section with no chooser row, reached by a jsr planted in stock
    P code (USB AUDIO IN's RX inject)."""
    return Module(
        name=name, key=name.upper(), kind=Kind.HYBRID, doc="fixture",
        dsp=DspSection(asm="does/not/exist.asm", priority=20, payloads=payloads,
                       hooks=(DspHook(site, (0x627000, 0x000204), "inject"),)),
        claims=Claims(sram=sram) if sram else None,
    )


def _stock(name, fx2_id, buffer):
    """A stock FX2 effect as the registry carries it (tools/remix/stock.py)."""
    return Module(
        name=name, key=name.upper(), kind=Kind.STOCK, doc="fixture",
        menu=MenuEntry(fx2_id=fx2_id, donor_desc=0x400d4772,
                       abbr=b"STK", fullname=b"Stock"),
        claims=Claims(stock_instance_buffer=buffer) if buffer else None,
    )


def _cave(name, cave_addr, length=16, hook_addr=None):
    return Module(
        name=name, key=name.upper(), kind=Kind.CF_PATCH, doc="fixture",
        cf_patches=(CavePatch(label=f"{name} cave", cave_addr=cave_addr,
                              pinned=b"\x4e\x71" * (length // 2),
                              hook_addr=hook_addr,
                              hook_stock=b"\x00" * 10 if hook_addr else b""),),
    )


def _cf(name, **kw):
    """A ColdFire module declaring fixed-address writes and claims."""
    return Module(name=name, key=name.upper(), kind=Kind.CF_PATCH, doc="fixture", **kw)


def _poke(addr, n=2):
    return Poke(addr, b"\x00" * n, b"\x4e\x71"[:n] * (n // 2 or 1))


def _ranged(name, *ranges, payloads=frozenset({"A"}), role=BusRole.NONE, buffers=False):
    """A hooked DSP section declaring data ranges."""
    return Module(
        name=name, key=name.upper(), kind=Kind.HYBRID, doc="fixture",
        dsp=DspSection(asm="does/not/exist.asm", priority=20, payloads=payloads, bus_role=role,
                       hooks=(DspHook(0x88 + len(name), (0x627000, 0x000204), "inject"),)),
        claims=Claims(dsp_ranges=tuple(ranges), owns_fx2_buffers=buffers))


CASES = [
    ("two modules claiming one FX2 id",
     [_effect("alpha", 0x07), _effect("beta", 0x07)], "fx2 id"),
    ("two caves overlapping in memory",
     [_cave("alpha", 0x400d7000, 64), _cave("beta", 0x400d7020, 64)],
     "ColdFire cave"),
    ("two modules hooking the same instruction",
     [_cave("alpha", 0x400d7000, hook_addr=0x40004d40),
      _cave("beta", 0x400d7100, hook_addr=0x40004d40)], "hook site"),
    ("two DSP sections hooking one stock P word on one payload",
     [_hooked("alpha"), _hooked("beta")], "DSP hook site"),
    ("two per-payload DSP hooks sharing one word on payload B",
     [_hooked("alpha", site={"A": 0x88, "B": 0x29c}, payloads=frozenset({"A", "B"})),
      _hooked("beta", site={"A": 0x4a7, "B": 0x29d}, payloads=frozenset({"A", "B"}))],
     "DSP hook site"),
    ("two modules claiming one on-chip SRAM window",
     [_hooked("alpha", sram=((0x80007c00, 1024, "dTDs"),)),
      _hooked("beta", site=0x90, sram=((0x80007e00, 512, "reply"),))], "on-chip SRAM"),
    ("two effects claiming one core-private Y word",
     [_effect("alpha", 0x07, reserved=(0x0905,)),
      _effect("beta", 0x1e, reserved=(0x0905,))], "core-private Y"),
    # The shape this one guards is a module that works perfectly in every
    # test done alone: BusVerb's tank is hardcoded into Y:0x4000-0xBFFF,
    # which is per CORE, and a second such module on the core overwrites it.
    ("two effects owning the FX2 instance buffer region",
     [_effect("alpha", 0x07, buffers=True),
      _effect("beta", 0x1e, buffers=True)], "FX2 instance buffers"),
    # A BUFFERED stock effect takes a per-track base from the host's
    # allocator, and those bases are the addresses the servers hardcode:
    # CHORUS on T6 beside BusVerb on T5 writes into the tank. Refused
    # beside a module that owns the region ...
    ("a buffered stock effect beside a module owning FX2 buffers",
     [_stock("chorus", 0x12, True), _effect("beta", 0x07, buffers=True)],
     "stock instance buffer"),
    # ... and beside one whose lines live in the shared window (BusDelay:
    # ybase ALWAYS), which is core 1's tracks 3-4 slots.
    ("a buffered stock effect beside a shared-window module",
     [_stock("comb", 0x13, True), _effect("beta", 0x07, ybase=YBase.ALWAYS)],
     "stock instance buffer"),
    # The build parks a module's P table in the stock curve bank X:0x4840
    #; a module that addresses that record itself would find
    # the table written under its reference.
    ("a table module beside a module addressing the stock curve bank",
     [_effect("alpha", 0x07, ptable=(1, 2, 3)),
      _effect("beta", 0x1e, asm=str(_HARD_ASM))], "X:0x4840 curve bank"),
    # ---- fixed-address spans, plain against plain ----------------------
    ("two plain pokes overlapping by one byte",
     [_cf("alpha", pokes=(_poke(0x4001f322, 4),)), _cf("beta", pokes=(_poke(0x4001f324, 2),))],
     "poke site"),
    ("a plain poke inside a pinned cave",
     [_cave("alpha", 0x400d7000, 64), _cf("beta", pokes=(_poke(0x400d7010),))], "ColdFire cave"),
    ("a plain poke inside a cave hook's span",
     [_cave("alpha", 0x400d7000, hook_addr=0x40004d40), _cf("beta", pokes=(_poke(0x40004d46),))],
     "hook site"),
    ("two symbol refs on one pointer (synth and Analog BD's FLEX renderer)",
     [_cf("alpha", symbol_refs=(SymbolRef(0x400d6438, 0x40004008, "u", "a"),)),
      _cf("beta", symbol_refs=(SymbolRef(0x400d6438, 0x40004008, "u", "b"),))], "poke site"),
    ("a table ref on a plain poke",
     [_cf("alpha", tables=(TableGrow("t", 0x40100000, 4, (("u", "s"),), ((0x40065bd8, 0x40100000),)),)),
      _cf("beta", pokes=(_poke(0x40065bda),))], "poke site"),
    ("a detour's pad_to span over another's site",
     [_cf("alpha", detours=(Detour(0x40079816, b"\x00" * 8, "u", "a", pad_to=8),)),
      _cf("beta", detours=(Detour(0x4007981c, b"\x00" * 6, "u", "b"),))], "hook site"),
    # ---- kept bytes ------------------------------------------------------
    ("a poke on bytes another module keeps",
     [_cf("alpha", keeps=(Keep(0x4001f322, bytes.fromhex("48780064"), "pea 0x64"),)),
      _cf("beta", pokes=(Poke(0x4001f322, bytes.fromhex("48780064"), bytes.fromhex("48780070")),))],
     "kept bytes"),
    ("a detour over kept bytes",
     [_cf("alpha", keeps=(Keep(0x4001f324, bytes.fromhex("0064"), "pea operand"),)),
      _cf("beta", detours=(Detour(0x4001f322, b"\x00" * 6, "u", "b"),))], "kept bytes"),
    ("two keepers expecting different stock",
     [_cf("alpha", keeps=(Keep(0x4001f322, bytes.fromhex("48780064")),)),
      _cf("beta", keeps=(Keep(0x4001f322, bytes.fromhex("48780070")),))], "kept bytes"),
    # ---- grown tables ----------------------------------------------------
    ("two modules growing one stock array",
     [_cf("alpha", tables=(TableGrow("t", 0x40100000, 4, (("u", "a"),), ((0x40065bd8, 0x40100000),)),)),
      _cf("beta", tables=(TableGrow("t", 0x40100008, 2, (("u", "b"),), ((0x40065d3e, 0x40100008),)),))],
     "grown table"),
    # ---- declared conflicts ----------------------------------------------
    ("two designs of one behaviour",
     [_cf("alpha", pokes=(_poke(0x40100000),), conflicts=(("BETA", "both retime a cued pattern"),)),
      _cf("beta", pokes=(_poke(0x40100010),))], "declared conflict"),
    # ---- DSP data ranges -------------------------------------------------
    ("two modules on one shared-window range from different payloads",
     [_ranged("alpha", DspRange("y", 0x3a000, 0x100, "buf")),
      _ranged("beta", DspRange("y", 0x3a080, 0x100, "buf"), payloads=frozenset({"B"}))], "DSP data"),
    ("two modules on one private X range on one payload",
     [_ranged("alpha", DspRange("x", 0x6000, 0x10, "table")),
      _ranged("beta", DspRange("x", 0x6008, 0x10, "table"))], "DSP data"),
    ("a declared range in another module's FX2 buffer region",
     [_ranged("alpha", DspRange("y", 0x8000, 0x10, "state")),
      _ranged("beta", buffers=True)], "DSP data"),
    ("a non-bus module's range in the bus scratch",
     [_ranged("alpha", DspRange("y", 0x36100, 0x10, "state")),
      _ranged("beta", role=BusRole.CLIENT)], "DSP data"),
    ("a range over stock's core 1 -> core 0 mailbox",
     [_ranged("alpha", DspRange("y", 0x7e00, 0x200, "line", half_relative=True))], "DSP data"),
    ("a range on another module's core-private Y word",
     [_ranged("alpha", DspRange("y", 0x0900, 0x10, "state")),
      _effect("beta", 0x1e, reserved=(0x0905,))], "DSP data"),
]

CLEAN = [_effect("alpha", 0x07, reserved=(0x0905,)),
         _effect("beta", 0x1e, reserved=(0x0906,), buffers=True),
         _cave("gamma", 0x400d7000, 64, hook_addr=0x40004d40),
         _cave("delta", 0x400d7040, 64, hook_addr=0x40004d50),
         # Stock effects with NO buffer sit beside anything, and two
         # buffered stock effects sit beside each other (the allocator
         # keeps them apart -- that is what it is for).
         _stock("filter", 0x04, False),
         _stock("compressor", 0x18, False)]
CLEAN_STOCK_PAIR = [_stock("chorus", 0x12, True), _stock("comb", 0x13, True),
                    _effect("alpha", 0x07)]
# One site, two payloads: no clash, each core has its own P.
CLEAN_HOOK_PAIR = [_hooked("alpha", payloads=frozenset({"A"})),
                   _hooked("beta", payloads=frozenset({"B"})),
                   # per-payload sites: one address, a different payload each
                   _hooked("gamma", site={"A": 0x4a7, "B": 0x29c}, payloads=frozenset({"A", "B"})),
                   _hooked("delta", site={"A": 0x29c, "B": 0x4a7}, payloads=frozenset({"A", "B"}))]
# Adjacent pokes, matching keepers, one half-relative range on each half, a
# private X range on two payloads, and a conflict naming a module that is absent.
CLEAN_CLAIMS = [_cf("alpha", pokes=(_poke(0x4001f322, 4),),
                    keeps=(Keep(0x40100000, bytes.fromhex("48780064")),),
                    conflicts=(("ABSENT", "fixture"),)),
                _cf("beta", pokes=(_poke(0x4001f326, 2),),
                    keeps=(Keep(0x40100002, bytes.fromhex("0064")),)),
                _ranged("gamma", DspRange("y", 0x0800, 0x100, "buf", half_relative=True),
                        DspRange("x", 0x6000, 0x10, "table")),
                _ranged("delta", DspRange("y", 0x0800, 0x100, "buf", half_relative=True),
                        DspRange("x", 0x6000, 0x10, "table"), payloads=frozenset({"B"}))]


def _submodule_preflight() -> int:
    """Refuse early, with the fix, if a module's upstream submodule is not checked out.

    `make check` runs EVERY remix, so a clone without submodules fails on
    somebody else's module even when the remix under test has nothing to do
    with it -- and it failed as a bare FileNotFoundError traceback out of
    ledger.runtime_write_spans (octakit's firmware.json) or as an assembler
    "can't open" from midi-scenes' sources. Measured on a fresh
    clone: `make bus REMIX=recfix` succeeds, `make check REMIX=recfix` dies.
    That is a wall in front of the first thing an outside contributor is
    asked to run, so it gets a message instead of a traceback.
    """
    missing = sorted(d.parent.name for d in ROOT.glob("modules/*/upstream")
                     if d.is_dir() and not any(d.iterdir()))
    if not missing:
        return 0
    print(f"  [FAIL] upstream submodule(s) not checked out: {', '.join(missing)}")
    print("         `make check` builds EVERY remix, so these are needed even "
          "when yours does not use them.")
    print("         Fix:  git submodule update --init --recursive")
    print("         (Building just your own remix does not need them: "
          "`make bus REMIX=<name>` works without.)")
    return 1


HARNESS = {
    "dsp_asm": ROOT / "vendor/dsp56300/build/source/dsp_host/dsp_asm",
    "dsp_host": ROOT / "vendor/dsp56300/build/source/dsp_host/dsp_host",
}


def _harness_preflight() -> int:
    """Refuse early, with the fix, if the DSP assembler or emulator is not built.

    `make setup` builds both, but its step 4 used to (a) swallow a failed
    cmake build behind an echo and (b) decide "already built" from the
    DISASSEMBLER alone, so a machine whose first setup got that far and no
    further passed every later `make setup` and then died in verify_twocore
    as a FileNotFoundError traceback on dsp_host -- the second wall Bryan T
    hit on a fresh clone. And a missing dsp_host is not only a
    crash later: the FLANGER passthrough probe below silently SKIPS without
    it, which is a gate reporting nothing rather than green.
    """
    missing = sorted(k for k, p in HARNESS.items() if not p.exists())
    if not missing:
        return 0
    print(f"  [FAIL] DSP harness not built: {', '.join(missing)} "
          f"(expected under vendor/dsp56300/build/source/dsp_host/)")
    print("         `make check` renders every effect under the emulator, so "
          "these are needed even when your remix touches no DSP code.")
    print("         Fix:  make setup      (needs cmake: brew install cmake)")
    print("         If it says 'already built', delete "
          "vendor/dsp56300/build and run it again.")
    return 1


def main():
    bad = _submodule_preflight() or _harness_preflight()
    if bad:
        return bad                      # nothing below can run without them
    for label, mods, expect in CASES:
        found = ledger.check(mods)
        hit = [p for p in found if p.startswith(expect)]
        names = hit and all(m.name in hit[0] for m in mods[:2])
        if hit and names:
            print(f"  [PASS] {label}")
            print(f"         -> {hit[0]}")
        else:
            bad += 1
            print(f"  [FAIL] {label}: expected a {expect!r} collision naming "
                  f"both modules, got {found}")
    for label, mods in (("modules that do not collide", CLEAN),
                        ("two buffered stock effects + a zero-buffer insert",
                         CLEAN_STOCK_PAIR),
                        ("two DSP sections hooking one site on different payloads",
                         CLEAN_HOOK_PAIR),
                        ("adjacent pokes, agreeing keepers, ranges on different payloads",
                         CLEAN_CLAIMS)):
        found = ledger.check(mods)
        if found:
            bad += 1
            print(f"  [FAIL] {label} were reported: {found}")
        else:
            print(f"  [PASS] {label} are left alone")

    try:
        _effect("hijack", 0x0c)
        bad += 1
        print("  [FAIL] a module on a stock FX2 id (0x0c, EQUALIZER) was accepted")
    except ValueError:
        print("  [PASS] a module on a stock FX2 id is refused")

    for label, make in (
            ("a module keeping bytes it pokes",
             lambda: _cf("k", pokes=(_poke(0x40100000, 4),), keeps=(Keep(0x40100002, b"\x00\x00"),))),
            ("a key in both requires and conflicts",
             lambda: _cf("k", requires=("X",), conflicts=(("X", "fixture"),))),
            ("a conflict with itself", lambda: _cf("k", conflicts=(("K", "fixture"),))),
            ("TableGrow.insert_at past the stock count",
             lambda: TableGrow("t", 0x40100000, 4, (), (), insert_at=5)),
            ("a DspRange straddling the shared window", lambda: DspRange("y", 0x2ff00, 0x200, "x")),
            ("a half-relative DspRange past its half",
             lambda: DspRange("y", 0x7f00, 0x200, "x", half_relative=True)),
            ("a per-payload DspHook site naming a payload the section is not on",
             lambda: _hooked("h", site={"A": 0x4a7, "B": 0x29c})),
            ("a per-payload DspHook site missing one of the section's payloads",
             lambda: _hooked("h", site={"A": 0x4a7}, payloads=frozenset({"A", "B"}))),
            ("MenuEntry.stock_dsp without replaces",
             lambda: MenuEntry(fx2_id=0x1f, donor_desc=0x400d58b8, abbr=b"F",
                               fullname=b"F", stock_dsp=True)),
            ("a stock_dsp module with no DspHook",
             lambda: Module(name="sd", key="SD", kind=Kind.DSP_EFFECT, doc="fixture",
                            menu=MenuEntry(fx2_id=0x18, donor_desc=0x400d5a4a,   # COMPRESSOR
                                           abbr=b"SD", fullname=b"SD",
                                           replaces="COMPRESSOR", stock_dsp=True),
                            params=tuple([Param(b"A", 0, active=True)] + [Param()] * 11),
                            dsp=schema.DspSection(asm="does/not/exist.asm", priority=0))),
            ("a Param with a formatter and raw descriptor words",
             lambda: Param(b"MON", 0, count=2, active=True, formatter=Formatter.STEPPED,
                           labels=("OFF", "ON"), widget_word=0x40046f10)),
            ("a raw descriptor word that is neither a u32 nor a (unit, symbol)",
             lambda: Param(b"KEY", 0, active=True, formatter_word=("unit",))),
            ("DspSection.subst on a payload the section is not placed on",
             lambda: schema.DspSection(asm="x.asm", priority=0, payloads=frozenset({"A"}),
                                subst={"A": {"@S@": "$1"}, "B": {"@S@": "$2"}})),
            ("DspSection.subst with different keys per payload",
             lambda: schema.DspSection(asm="x.asm", priority=0,
                                subst={"A": {"@S@": "$1"}, "B": {"@T@": "$2"}})),
            ("DspSection.subst key overlapping the build's $30000 rewrite",
             lambda: schema.DspSection(asm="x.asm", priority=0,
                                subst={"A": {"$3000": "$1"}, "B": {"$3000": "$2"}})),
            ("DspSection.subst value carrying a build marker",
             lambda: schema.DspSection(asm="x.asm", priority=0,
                                subst={"A": {"@S@": "; ROTLATCH"}, "B": {"@S@": "$2"}})),
            ("DspSection.subst on a source without the key",
             lambda: schema.DspSection(asm="x.asm", priority=0,
                                subst={"A": {"@S@": "$1"}, "B": {"@S@": "$2"}}
                                ).source_for("A", "        nop\n"))):
        try:
            make()
            bad += 1
            print(f"  [FAIL] {label} was accepted")
        except ValueError:
            print(f"  [PASS] {label} is refused")
    got = registry.validate_keys({"ALPHA": _cf("alpha", conflicts=(("NOPE", "fixture"),))})
    if got:
        print(f"  [PASS] an unknown conflicts key is refused -> {got[0]}")
    else:
        bad += 1
        print("  [FAIL] an unknown conflicts key was accepted")
    grown = TableGrow("t", 0, 3, (), (), insert_at=1).entries([1, 2, 3], [9, 8])
    if grown == [1, 9, 8, 2, 3] and TableGrow("t", 0, 3, (), ()).entries([1, 2, 3], [9]) == [1, 2, 3, 9]:
        print("  [PASS] TableGrow inserts a block at insert_at and appends by default")
    else:
        bad += 1
        print(f"  [FAIL] TableGrow.entries gave {grown}")
    # The real pair the plain-span pass newly refuses: both rewrite the FLEX
    # renderer pointer 0x400d6438, and synth's machine-window detour spans
    # Analog BD's at 0x4007981c.
    pair = ledger.check([registry.by_key("SYNTH MACHINE"), registry.by_key("ANALOG BD")])
    if any(p.startswith(("poke site", "hook site")) for p in pair):
        print(f"  [PASS] SYNTH MACHINE + ANALOG BD are refused -> {pair[0]}")
    else:
        bad += 1
        print(f"  [FAIL] SYNTH MACHINE + ANALOG BD: {pair}")

    try:
        Param(b"SIXSIX")
        bad += 1
        print("  [FAIL] a six-character parameter name was accepted without a terminator")
    except ValueError:
        print("  [PASS] a six-character parameter name is refused")

    # ---- the rig's derivations (tools/remix/rig.py) ---------------------
    # The track model is DERIVED, so hold the derivation to the measured
    # facts: payload A serves TRACKS 5-8, B serves 1-4, an
    # insert runs anywhere, SYSTEM modules never sit on a track.
    from remix import rig
    for mod in registry.modules().values():
        cat = rig.category(mod)
        tr = rig.track_range(mod)
        if cat == rig.SERVER:
            want = (rig.PAYLOAD_TRACKS["A"]
                    if mod.dsp.payloads == frozenset({"A"})
                    else rig.PAYLOAD_TRACKS["B"])
            ok = len(mod.dsp.payloads) == 1 and tr == want
        elif cat in (rig.INSERT, rig.STOCK):
            ok = tr == rig.TRACKS
        else:
            ok = len(tr) == 0
        if ok:
            print(f"  [PASS] {mod.name}: {cat}, tracks "
                  f"{f'{tr.start}-{tr.stop - 1}' if len(tr) else 'none'}")
        else:
            bad += 1
            print(f"  [FAIL] {mod.name}: category {cat} derived tracks {tr}")
    # ---- the module table's fields --------------------------------------
    # README.md's table is rendered from these (make docs); a module without
    # them has no row, which is how eight merged modules went unlisted.
    for mod in registry.modules().values():
        if mod.is_stock:
            continue
        missing = [f for f in ("category", "author", "author_url", "proof")
                   if not getattr(mod, f)]
        if missing:
            bad += 1
            print(f"  [FAIL] {mod.name}: manifest declares no {', '.join(missing)}")
    print("  [PASS] every module declares category, author, author_url, proof")
    # ---- every module has a remix ----------------------------------------
    # Every check starts from a remix (make check, make accept, the module
    # gates, make reach): a module no selection carries is never built or
    # checked. A module arrives with its remix (remixes/<name>/remix.py or
    # remixes/test/<name>/remix.py, README.md beside it), or in an existing one.
    carried = {k for n in registry.remix_names() for k in registry.remix(n).modules}
    orphans = sorted(m.key for m in registry.modules().values()
                     if not m.is_stock and m.key not in carried)
    for key in orphans:
        bad += 1
        print(f"  [FAIL] {key}: no remix carries it -- add it to one, or add remixes/test/<name>/")
    if not orphans:
        print("  [PASS] every module is carried by at least one remix")

    # A server that never declared its payload must refuse, not guess: the
    # field's default is {"A","B"} and a guess would put the effect on all
    # eight tracks of the picker.
    from remix.schema import BusRole, DspSection, Harness
    vague = Module(
        name="vague", key="VAGUE", kind=Kind.DSP_EFFECT, doc="fixture",
        menu=MenuEntry(fx2_id=0x1f, donor_desc=0x400d58b8,
                       abbr=b"VAG", fullname=b"Vague"),
        dsp=DspSection(asm="does/not/exist.asm", priority=0,
                       bus_role=BusRole.SERVER),
        harness=Harness(layout_char=None, is_server=True))
    try:
        rig.track_range(vague)
        bad += 1
        print("  [FAIL] a server with undeclared payload was given tracks")
    except ValueError:
        print("  [PASS] a server with undeclared payload is refused")

    # ---- one knob-name universe -----------------------------------------
    # The audition path drives render_reverb, whose PARAMS list predates the
    # manifest and keeps two historical labels (MIX for IN, SPEED for SHMR).
    # The bridge is positional -- manifest slot -> PARAMS[slot] -- so prove
    # the two tables stay slot-for-slot aligned; a slot that moves in one and
    # not the other is exactly the wrapper drift that has burned renders
    # before (the harness-knob-drift rule).
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
    import render_reverb
    cv = registry.by_key("REVERB SERVER")
    for name, slot in sorted(cv.knob_map().items(), key=lambda kv: kv[1]):
        if name == "MODE":                               # goes via --mode
            ok = render_reverb.PARAMS[slot][0] == "_C"   # (slot 6 since v7)
        else:
            rr_name = render_reverb.PARAMS[slot][0]
            ok = rr_name in render_reverb.NAMES and \
                render_reverb.NAMES[rr_name] == slot
        if not ok:
            bad += 1
            print(f"  [FAIL] busverb {name}@{slot} has no aligned "
                  f"render_reverb param")
    else:
        print("  [PASS] busverb's manifest slots align with render_reverb")

    # ---- every drawn knob answers "what is this?" -----------------------
    # The remixer shows Param.doc as the help line under the knob cursor,
    # and a select's labels beside its value. A knob with neither is a knob
    # the operator has to reverse-engineer by ear, so hold the line: every
    # named, drawn param of every menu-bearing module carries a doc.
    # (Length is capped so the help row stays one line; the schema already
    # pins labels to the declared count.)
    for mod in registry.modules().values():
        if mod.menu is None:
            continue
        undocumented = [p.name.decode() for p in mod.params
                        if p.name and p.active and not p.doc]
        toolong = [p.name.decode() for p in mod.params
                   if p.name and p.doc and len(p.doc) > 90]
        if undocumented or toolong:
            bad += 1
            print(f"  [FAIL] {mod.name}: undocumented knobs {undocumented}, "
                  f"over-long docs {toolong}")
        else:
            print(f"  [PASS] {mod.name}: every drawn knob has a doc")

    # ---- stock rows carry their descriptor's knobs -----------------------
    # Read from the pristine image, so the rig shows a stock effect's real
    # controls and send_probe can drive them by name. Only checkable when
    # the image is on disk (make setup); a fresh clone gets params=().
    from remix import stock
    if stock.STOCK_IMAGE.exists():
        for mod in stock.MODULES:
            names = sorted(mod.knob_map())
            if not names or len(mod.params) != 12:
                bad += 1
                print(f"  [FAIL] {mod.name}: no knobs read from its descriptor")
            elif len(set(names)) != len(names):
                bad += 1
                print(f"  [FAIL] {mod.name}: duplicate knob names {names}")
            else:
                print(f"  [PASS] {mod.name}: {len(names)} stock knobs read "
                      f"({' '.join(names)})")
    else:
        print("  [SKIP] stock knobs: out/raw/section_3_MAIN_OS.bin not on disk")
    # ---- stock selects carry the firmware's own labels ---------------------
    # tools/build/stock_labels.py asked each select's display formatter what it
    # prints; the JSON it wrote must cover every select at the right length,
    # and -- when the emulator is on hand -- still match the firmware.
    if stock.STOCK_IMAGE.exists():
        missing = [f"{m.key}.{p.name.decode()}" for m in stock.MODULES
                   for p in m.params
                   if p.name and p.active and p.count is not None and not p.labels]
        if missing:
            bad += 1
            print(f"  [FAIL] stock selects without firmware labels: {missing} "
                  f"-- run: make stock-labels")
        else:
            n = sum(1 for m in stock.MODULES for p in m.params if p.labels)
            print(f"  [PASS] all {n} stock selects carry the firmware's labels")
        _venv = ROOT / ".venv/bin/python3"
        if _venv.exists():
            r = subprocess.run([str(_venv), "tools/build/stock_labels.py", "--check"],
                               cwd=ROOT, capture_output=True, text=True)
            if r.returncode == 0:
                print("  [PASS] stock_labels.json matches what the emulated "
                      "firmware prints")
            else:
                bad += 1
                print("  [FAIL] stock_labels.json is stale: "
                      + (r.stdout + r.stderr).strip().splitlines()[-1])
        else:
            print("  [SKIP] label check against the firmware: no .venv "
                  "(make emu-setup)")

    # Every module in the registry needs a distinct layout letter or the
    # send_probe alphabet silently drops one.
    chars = [m.harness.layout_char for m in registry.modules().values()
             if m.harness is not None and m.harness.layout_char]
    if len(set(chars)) != len(chars):
        bad += 1
        print(f"  [FAIL] duplicate layout letters: {sorted(chars)}")
    else:
        print(f"  [PASS] {len(chars)} distinct layout letters")

    # ---- the stock-render harness puts the audio block where hardware does --
    # The dispatcher's `move #$0,r0`: the audio block is at X:0 and stock
    # effects use the X right after it as scratch (the flanger writes
    # X:0x20-0xff every block). dsp_host's default of X:0x80 sat inside that
    # scratch and turned FLANGER into a Nyquist-rate alternation while EQ,
    # DJ EQ, PHASER, SPATIALIZER and COMB were quietly 5-17 dB dirtier than
    # they should be. Hold the line with the sharpest of them:
    # FLANGER at MIX=0 is a BIT-EXACT dry passthrough at the right address.
    _host = ROOT / "vendor/dsp56300/build/source/dsp_host/dsp_host"
    _dump = ROOT / "out/dsp/_stock_A.mem"
    if _host.exists() and stock.STOCK_IMAGE.exists():
        if not _dump.exists():
            import dsp_modmap
            _dump.parent.mkdir(parents=True, exist_ok=True)
            dsp_modmap.dumpmem(stock.STOCK_IMAGE.read_bytes(), ["A", str(_dump)])
        r = subprocess.run([sys.executable, "tools/harness/send_probe.py", "--mem",
                            str(_dump), "--direct", "--pick", "flanger",
                            "--dur", "0.45", "--tail", "0.05", "--set=MIX=0"],
                           cwd=ROOT, capture_output=True, text=True)
        import re as _re
        m = _re.search(r"THD \(2f\.\.9f\) = *(-?[\d.]+) dB", r.stdout)
        pk = _re.search(r"peak +([\d.]+) FS", r.stdout)
        thd = float(m.group(1)) if m else None
        peak = float(pk.group(1)) if pk else None
        # The tone metric floors around -54 dB in send_probe's window (a
        # unity pass of the 0.5 FS tone reads -53.8); the broken state read
        # peak 1.000 / THD -2 dB. Either number alone discriminates.
        if (r.returncode == 0 and thd is not None and peak is not None
                and thd < -50 and abs(peak - 0.5) < 0.005):
            print(f"  [PASS] stock FLANGER at MIX=0 is a dry pass (peak "
                  f"{peak:.3f} FS, THD {thd:.0f} dB) -- the audio block is at X:0")
        else:
            bad += 1
            print(f"  [FAIL] stock FLANGER at MIX=0 is not dry (peak {peak}, "
                  f"THD {thd}) -- is dsp_host's audio block back inside "
                  f"stock scratch?")
    else:
        print("  [SKIP] stock render harness: dsp_host or the stock image is missing")

    # THE BUDGET'S TOTALS ARE NOT THE BUDGET'S TO DECIDE. The remixer
    # states "N free of TOTAL" for the ColdFire cave, and the build reports
    # only what is LEFT of it -- so the total is written down in state.py and
    # would go stale silently the day the cave's bounds move. Pin it to
    # build_bus's own constants by reading them out of the source: a total
    # that is quietly wrong is exactly the kind of confident stale number
    # this project keeps getting burned by.
    _bb = (ROOT / "tools/build/build_bus.py").read_text()
    _bounds = {}
    for _name in ("NEW_LIST", "ZERO_RUN_END"):
        _m = re.search(rf"^{_name} = (0x[0-9a-f]+)", _bb, re.M)
        if _m:
            _bounds[_name] = int(_m.group(1), 16)
    if len(_bounds) != 2:
        bad += 1
        print("  [FAIL] could not read NEW_LIST/ZERO_RUN_END out of "
              "build_bus.py -- the cave total cannot be pinned")
    elif _bounds["ZERO_RUN_END"] - _bounds["NEW_LIST"] == state.CAVE_BYTES:
        print(f"  [PASS] the cave total ({state.CAVE_BYTES:,} B) matches "
              f"build_bus's own bounds")
    else:
        bad += 1
        print(f"  [FAIL] state.CAVE_BYTES is {state.CAVE_BYTES:,} B but "
              f"build_bus's cave is "
              f"{_bounds['ZERO_RUN_END'] - _bounds['NEW_LIST']:,} B")

    # THE NONE FALLBACK IS ONLY SAFE WITHOUT A BUS, and that is a refusal,
    # not a convention -- an unassigned track then runs nothing at all, so
    # nobody flips the rotation or clears the accumulators. dsp_host is
    # single-core and can never reproduce the defect, so this check is the
    # only thing standing between the two. See schema.NO_FALLBACK.
    _probe = ROOT / "remixes/_selftest_nofb.py"
    try:
        _probe.write_text(
            "from remix.schema import Remix\n\n"
            "REMIX = Remix(name='_selftest_nofb', doc='scratch',\n"
            "              modules=('SPECTRUM', 'SEND'), fallback='NONE')\n")
        registry.remix("_selftest_nofb")
        bad += 1
        print("  [FAIL] fallback='NONE' was accepted beside SEND -- an "
              "unassigned track would leave the bus unhousekept")
    except SystemExit as e:
        if "no bus participant" in str(e):
            print("  [PASS] fallback='NONE' is refused beside a bus participant")
        else:
            bad += 1
            print(f"  [FAIL] fallback='NONE' beside SEND was refused for the "
                  f"wrong reason: {e}")
    finally:
        _probe.unlink(missing_ok=True)
        for junk in (ROOT / "remixes/__pycache__").glob("_selftest_nofb*"):
            junk.unlink(missing_ok=True)

    # And the same rule read off the SHIPPED remixes, which is where it would
    # actually go wrong: nothing may pair NO_FALLBACK with a bus module.
    for _n in registry.remix_names():
        _r = registry.remix(_n)
        _bus = [k for k in _r.modules
                if schema.on_the_bus(registry.modules()[k])]
        if _r.fallback == schema.NO_FALLBACK and _bus:
            bad += 1
            print(f"  [FAIL] remix {_n!r} falls back to NONE but carries "
                  f"{', '.join(_bus)}")
    print(f"  [PASS] every remix's fallback matches whether it has a bus")

    # ---- dynamic donor regions (Remix.harvest) ---------------------------
    # The property the whole idea rests on: the thirteen DSP effects are
    # CONTIGUOUS in both payloads and their record sizes match what stock.py
    # says they cost. Derived from the module map every run, so a firmware
    # whose layout differs fails here rather than being written over.
    for _pay in ("A", "B"):
        try:
            _sp = stock.p_spans(_pay)
        except Exception as e:                       # noqa: BLE001
            bad += 1
            print(f"  [FAIL] payload {_pay}: no effect run found -- {e}")
            continue
        _run = sorted(_sp.values())
        _lo, _hi = _run[0][0], _run[-1][0] + _run[-1][1]
        _gap = [a for (a, n), (a2, _n) in zip(_run, _run[1:]) if a + n != a2]
        if _gap:
            bad += 1
            print(f"  [FAIL] payload {_pay}: effect code is not contiguous")
        _wrong = [k for k, (_a, n) in _sp.items()
                  if k in stock.WORDS and stock.WORDS[k] != n
                  and k != "PHASER"]
        if _wrong:
            bad += 1
            print(f"  [FAIL] payload {_pay}: {_wrong} disagree with "
                  f"stock.WORDS")
        # ⚠️ AND EVERY SPAN KEY MUST BE A REAL STOCK KEY. `COMB` against the
        # registry's `COMB FILTER` made `h` answer "it runs on the ColdFire"
        # for an effect with 277 words of DSP code -- a silent miss, because
        # a missing key looks exactly like an effect with no code.
        _reg = {m.key for m in stock.MODULES}
        _orphan = sorted(set(_sp) - _reg)
        if _orphan:
            bad += 1
            print(f"  [FAIL] payload {_pay}: span keys not in the registry: "
                  f"{_orphan}")
        elif not _wrong:
            print(f"  [PASS] payload {_pay}: {len(_sp)} effects contiguous, "
                  f"P:0x{_lo:05x}..0x{_hi:05x} = {_hi - _lo:,} words")
    # Routines a kept effect calls inside a harvested span (stock.pinned):
    # the scan must find the measured four on each payload, and nothing for
    # the default harvest. An empty scan (no disassembler, a decode change)
    # would otherwise read as "nothing to keep".
    _pin_want = {
        "A": {("SPRING REV",): ((0x1586, 35),), ("DARK REV",): ((0x1a47, 93),),
              ("FILTER",): ((0x09ad, 12), (0x09c6, 15)), stock.CONSUMED: ()},
        "B": {("SPRING REV",): ((0x1346, 35),), ("DARK REV",): ((0x1807, 93),),
              ("FILTER",): ((0x076d, 12), (0x0786, 15)), stock.CONSUMED: ()},
    }
    for _pay, _cases in _pin_want.items():
        for _h, _exp in _cases.items():
            _got = tuple((a, n) for a, n, _k, _c in stock.pinned(_pay, _h))
            if _got != _exp:
                bad += 1
                print(f"  [FAIL] payload {_pay}: pinned({_h}) = {_got}, "
                      f"expected {_exp}")
    print("  [PASS] the routines kept effects call inside a harvest are "
          "found on both payloads")
    # ⚠️ AND THE DERIVED HARVEST MUST REPRODUCE WHAT THE BUILD HAS ALWAYS
    # DONE. "On neither chooser" gives every shipped remix exactly the three
    # reverbs -- FX1 lists ten of the thirteen and the reverbs are FX2-only
    # -- which is the whole reason removing the explicit field was safe.
    # mods lists all fourteen and places nothing, so it gives up nothing.
    _sp = stock.p_spans("A")
    _fx1_all = {k for k in _sp
                if registry.modules()[k].menu.fx2_id in stock.fx1_ids()}
    # The three that differ, and why -- a remix reaching this list by
    # accident is the thing being guarded against.
    # Remixes that list all fourteen stock effects place no DSP words and
    # give up nothing; the rig replaces FILTER, LO-FI and CHORUS with the
    # stations and lists nothing else, so all thirteen go as one run.
    _rig = ("FILTER", "SPATIALIZER", "EQUALIZER", "PHASER", "FLANGER", "CHORUS",
                 "PLATE REV", "SPRING REV", "DARK REV", "COMPRESSOR", "LO-FI",
                 "DJ EQ", "COMB FILTER")
    _want = {"mods": (), "ok-ms": (), "usb-out-tracks-main-cue": (), "usb-out-tracks": (), "usb-out-master": (),
             "usb-out-main-cue": (), "usb-out-main": (), "usb-midi": (),     # stock effects + ColdFire modules, no DSP words
             "repitch": (), "plocks-p2": (), "analog-bassdrum": ("SPRING REV",),
             # Zac Kyoti's ColdFire modules on the stock effects, no DSP words
             **{_k: () for _k in ("direct-jump-kyoti", "batch-bugfixes", "reload-from-project",
                                  "quantize-live-rec-toggle", "erase-empty-trigless-locks",
                                  "mute-modes", "kyoti-mute-jump", "kyoti-fixes", "rec-trig-mute")},
             # the twelve io remixes: the IN module's RX inject is placed in SPATIALIZER's words
             **{f"usb-io-{o}-{i}": ("SPATIALIZER",) for o in ("tracks", "tracks-main-cue", "main-cue", "main") for i in ("ab", "cd", "abcd")},
             "octatrick": ("SPATIALIZER",),   # USB AUDIO IN ABCD's inject, as in the io remixes
             "sos-capture": ("SPATIALIZER",),   # usb-io-tracks-ab + the recorder fixes
             "cfmeter": ("DARK REV",), "cfmeter-port": ("DARK REV",),   # the readout insert's words
             "waveload": ("DARK REV",), "waveload-port": ("DARK REV",),   # CF METER's readout insert, as cfmeter
             "wave": ("SPRING REV", "DARK REV"),   # WAVE runs in their words
             "transient": ("PLATE REV",),   # TRANSIENT runs in its words; the other 13 stay
             "euclid": ("SPATIALIZER", "FLANGER", "CHORUS", "COMB FILTER"),
             "rig": _rig, "bottleservice": _rig}
    for _n in registry.remix_names():
        _r = registry.remix(_n)
        _hv = stock.region_of(stock.harvested(
            set(_r.modules) | set(_r.fx1 or _fx1_all)))
        _exp = _want.get(_n, stock.CONSUMED)
        if tuple(_hv) != tuple(_exp):
            bad += 1
            print(f"  [FAIL] remix {_n!r} gives up {_hv}, expected {_exp}")
        # ⚠️ RUNS, NOT ONE RUN. Since a gap is two placeable
        # openings rather than a refusal, so what has to hold is that the
        # grouping is sound: every run internally contiguous, and the runs
        # together covering exactly the harvested set.
        _runs = stock.regions_of(_hv)
        for _g in _runs:
            _run = [_sp[k] for k in _g]
            if any(a + n != a2 for (a, n), (a2, _x) in zip(_run, _run[1:])):
                bad += 1
                print(f"  [FAIL] remix {_n!r}: run {_g} is not contiguous")
        if sorted(k for g in _runs for k in g) != sorted(_hv):
            bad += 1
            print(f"  [FAIL] remix {_n!r}: the runs do not cover {_hv}")
    print(f"  [PASS] every remix's given-up effects group into contiguous "
          f"runs, and the shipped ones give up exactly what they always did")

    # ---- MULTI-RUN PLACEMENT, actually built --------------------------
    # The grouping above is arithmetic; this builds a remix whose harvest is
    # two non-adjacent runs (FLANGER+CHORUS 618 w; SPRING REV+DARK REV
    # 2,130 w, PLATE REV kept on the chooser to split them) and requires
    # MINIVERB (457 w, placed first) in run 1 and EUCLID (362 w + 33 table)
    # in run 2. A placer that reverted to one bump cursor would leave the
    # small run empty and still build.
    _probe = ROOT / "remixes/_selftest_scattered.py"
    _probe.write_text(
        "from remix.schema import Remix\n\n"
        "REMIX = Remix(name='_selftest_scattered', doc='scratch',\n"
        "              modules=('EUCLID', 'MINIVERB', 'PLATE REV'),\n"
        "              fallback='NONE',\n"
        "              fx1=('FILTER', 'EQUALIZER', 'DJ EQ', 'PHASER',\n"
        "                   'SPATIALIZER', 'COMPRESSOR', 'LO-FI',\n"
        "                   'COMB FILTER'))\n")
    r = subprocess.run([sys.executable, "tools/build/build_bus.py"],
                       cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, "REMIX": "_selftest_scattered",
                            "XBUS": "1", "SPEC": "1"})
    _probe.unlink(missing_ok=True)
    for junk in (ROOT / "remixes/__pycache__").glob("_selftest_scattered*"):
        junk.unlink(missing_ok=True)
    if r.returncode:
        bad += 1
        print(f"  [FAIL] remix 'placer probe' does not build:\n"
              f"{r.stdout[-600:]}{r.stderr[-400:]}")
    else:
        # ⚠️ PER PAYLOAD. The two payloads put the same effects at
        # DIFFERENT addresses, so merging their run lines checks neither --
        # and "one instance is one payload" is exactly how this codebase
        # has been bitten before (docs/firmware/DSP.md s11).
        _by_pay, _pay = {}, None
        for line in r.stdout.splitlines():
            m = re.match(r"-- payload (\w+) --", line.strip())
            if m:
                _pay = m.group(1)
                _by_pay[_pay] = {"runs": [], "at": {}}
            if _pay is None:
                continue
            m = re.match(r"\s+run \d+ P:0x([0-9a-f]+)\.\.0x([0-9a-f]+)", line)
            if m:
                _by_pay[_pay]["runs"].append((int(m.group(1), 16),
                                              int(m.group(2), 16)))
            m = re.match(r"\s{2}(EUCLID|MINIVERB)\s+P:0x([0-9a-f]+)", line)
            if m:
                _by_pay[_pay]["at"][m.group(1)] = int(m.group(2), 16)
        if sorted(_by_pay) != ["A", "B"]:
            bad += 1
            print(f"  [FAIL] 'placer probe': expected both payloads, saw "
                  f"{sorted(_by_pay)}")
        else:
            _ok = True
            for _p, _d in sorted(_by_pay.items()):
                _rs, _at = _d["runs"], _d["at"]
                _in = {k: next((i for i, (lo, hi) in enumerate(_rs)
                                if lo <= a < hi), None)
                       for k, a in _at.items()}
                # PLATE, kept, calls the last 93 words of DARK's span
                # (stock.pinned), so the SPRING+DARK run ends where they start.
                _pin = stock.pinned(_p, ("FLANGER", "CHORUS", "SPRING REV",
                                         "DARK REV"))
                if len(_rs) != 2:
                    bad += 1; _ok = False
                    print(f"  [FAIL] 'placer probe' payload {_p}: {len(_rs)} "
                          f"runs, expected 2")
                elif len(_pin) != 1 or _rs[1][1] != _pin[0][0]:
                    bad += 1; _ok = False
                    print(f"  [FAIL] 'placer probe' payload {_p}: run 2 ends "
                          f"at 0x{_rs[1][1]:05x}, the pinned routine is {_pin}")
                elif sorted(_at) != ["EUCLID", "MINIVERB"]:
                    bad += 1; _ok = False
                    print(f"  [FAIL] 'placer probe' payload {_p}: placed "
                          f"{sorted(_at)}, expected both modules")
                elif None in _in.values():
                    bad += 1; _ok = False
                    print(f"  [FAIL] 'placer probe' payload {_p}: a module "
                          f"landed outside every run -- {_at} vs {_rs}")
                elif len(set(_in.values())) < 2:
                    bad += 1; _ok = False
                    print(f"  [FAIL] 'placer probe' payload {_p}: both modules "
                          f"landed in the SAME run ({_in}) -- the placer is "
                          f"not filling the smaller openings")
                elif _in["MINIVERB"] != 0:
                    # MINIVERB is 457 words and run 1 holds 618: first-fit
                    # MUST take it. Anywhere else means the small opening
                    # was skipped, which is the whole defect.
                    bad += 1; _ok = False
                    print(f"  [FAIL] 'placer probe' payload {_p}: MINIVERB went "
                          f"to run {_in['MINIVERB'] + 1}, not the 618-word "
                          f"opening it fits")
            # The pinned routine is still stock in the image.
            import dsp_modmap as _dm
            _out = (ROOT / "out/mainos_bus.bin").read_bytes()
            _stk = (ROOT / _dm.IMG).read_bytes()
            for _p, _va, _ln in _dm.PAYLOADS:
                _recs, _b = _dm.modules(_stk, _va, _ln)
                _hv = ("FLANGER", "CHORUS", "SPRING REV", "DARK REV")
                for _a, _n, _k, _c in stock.pinned(_p, _hv):
                    for _sp_, _ra, _rc, _ro in _recs:
                        if _sp_ == 0 and _ra <= _a and _a + _n <= _ra + _rc:
                            _o = _va - _dm.BASE + _ro + (_a - _ra) * 3
                            if _out[_o:_o + _n * 3] != _stk[_o:_o + _n * 3]:
                                bad += 1; _ok = False
                                print(f"  [FAIL] 'placer probe' payload {_p}: "
                                      f"P:0x{_a:05x}+{_n} ({_k}, called by "
                                      f"{_c}) is not stock in the image")
            if _ok:
                print(f"  [PASS] 'placer probe' fills its non-contiguous "
                      f"runs in BOTH payloads (MiniVerb into the 618-word "
                      f"opening, Euclid into the big run) and leaves PLATE's "
                      f"routine in DARK's span stock")

    # ---- FX1 rows (Remix.fx1) -------------------------------------------
    # The schema half. The BUILD half -- the relocated list, FX1's own id and
    # cursor tables, and stock's eleven rows unchanged and still first -- is
    # tools/verify/verify_menu.py, which needs a built image and so runs there.
    try:
        schema.Remix(name="_x", doc="_", modules=("SPECTRUM",),
                     fallback=schema.NO_FALLBACK, fx1=("SPECTRUM", "SPECTRUM"))
        bad += 1
        print("  [FAIL] Remix(fx1=...) accepted a duplicate key")
    except ValueError:
        print("  [PASS] Remix(fx1=...) refuses a duplicate key")
    # A STOCK effect may be on the FX1 list without an FX2 row -- the two
    # lists are independent -- so the schema deliberately does NOT require
    # every fx1 key to be in `modules`. Pinned, because it was required for
    # one day and that would have made a curated FX1 chooser impossible.
    try:
        schema.Remix(name="_x", doc="_", modules=("SPECTRUM",),
                     fallback=schema.NO_FALLBACK, fx1=("FILTER", "SPECTRUM"))
        print("  [PASS] an fx1 row may be a stock effect with no FX2 row")
    except ValueError as e:
        bad += 1
        print(f"  [FAIL] Remix(fx1=...) refused a stock key: {e}")
    # A module of ours is FX2-only until a remix says otherwise, and then it
    # is on both -- this is the derivation the remixer's menus column and
    # every resource line read.
    # EUCLID replaces no stock effect, so it has no FX1 row of its own.
    _eu = registry.modules()["EUCLID"]
    if rig.menus(_eu) != (rig.FX2,):
        bad += 1
        print(f"  [FAIL] Euclid is {rig.menus(_eu)} with no fx1 row")
    elif rig.menus(_eu, {"EUCLID"}) != (rig.FX1, rig.FX2):
        bad += 1
        print(f"  [FAIL] Euclid is {rig.menus(_eu, {'EUCLID'})} with one")
    else:
        print("  [PASS] an fx1 row moves a module from FX2 to FX1+FX2")
    # ⚠️ ONLY A BUFFER-FREE INSERT MAY TAKE AN FX1 ROW. The measured reason
    # is docs/firmware/DSP.md's "wrong claim 1": a 16K layout at an FX1 base runs
    # through the other FX1 buffers and into FX2 slot 0. Pinned per module so
    # a manifest that starts reading the allocator cannot quietly become
    # eligible.
    _want = {"MINIVERB": "FX2 slot",
             "REVERB SERVER": "bus server", "DELAY SERVER": "bus server",
             "SPECTRUM": None, "CHARACTER": None, "EUCLID": None}
    for _k, _frag in _want.items():
        _why = state.fx1_hazard(registry.modules()[_k])
        if (_frag is None) != (_why is None) or (_frag and _frag not in _why):
            bad += 1
            print(f"  [FAIL] fx1_hazard({_k}) = {_why!r}, wanted "
                  f"{_frag!r}")
    print(f"  [PASS] {len(_want)} modules classified for an FX1 row "
          f"({sum(v is None for v in _want.values())} eligible)")

    # WHAT EVERY SHIPPED FX1 CHOOSER MAY HOLD. A stock effect must be one
    # FX1 already lists (DELAY and the reverbs are FX2-only because they do
    # not fit a 3,072-word FX1 allocation); a module of ours must have an FX2
    # row -- that is where its descriptor clone comes from -- must not be a
    # `replaces` (which already inherits an FX1 row) and must clear
    # fx1_hazard.
    from remix import stock as _stk
    for _n in registry.remix_names():
        _r = registry.remix(_n)
        for _k in _r.fx1:
            _m = registry.modules().get(_k)
            if _m is None or _m.menu is None:
                bad += 1
                print(f"  [FAIL] remix {_n!r}: fx1={_k!r} is not an effect")
                continue
            if _m.is_stock:
                if _m.menu.fx2_id not in _stk.fx1_ids():
                    bad += 1
                    print(f"  [FAIL] remix {_n!r}: stock {_k} is FX2-only")
                _rep = [x for x in _r.modules if registry.modules()[x].menu is not None
                        and registry.modules()[x].menu.replaces == _k]
                if _rep:
                    bad += 1
                    print(f"  [FAIL] remix {_n!r}: fx1 lists stock {_k}, "
                          f"which {_rep[0]} replaces -- list the "
                          f"replacement")
                continue
            if _k not in _r.modules:
                bad += 1
                print(f"  [FAIL] remix {_n!r}: {_k} has no FX2 row, so there "
                      f"is no descriptor clone for FX1 to point at")
            _why = state.fx1_hazard(_m)
            if _why:
                bad += 1
                print(f"  [FAIL] remix {_n!r}: {_k} on FX1 -- {_why}")
    print("  [PASS] every shipped FX1 chooser holds only what FX1 can host")

    # And the real thing: every shipped remix must be clean.
    for name in registry.remix_names():
        r = registry.remix(name)
        found = ledger.check(registry.selected(r))
        if found:
            bad += 1
            print(f"  [FAIL] remix {name!r} has collisions: {found}")
        else:
            print(f"  [PASS] remix {name!r} is clean")

    print("\nOK" if not bad else f"\n{bad} FAILED")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
