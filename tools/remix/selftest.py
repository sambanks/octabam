#!/usr/bin/env python3
"""Prove the ledger catches what it claims to catch.

A guard nobody has watched fail is a guard nobody knows works. Each case
below builds two modules that collide in one specific way and asserts the
ledger names both of them; the last case asserts a clean pair stays clean,
because a checker that fires on everything is no better than one that fires
on nothing.

    python3 tools/remix/selftest.py
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from remix import ledger  # noqa: E402
from remix.schema import (CavePatch, Claims, DspSection, Kind, MenuEntry,  # noqa: E402
                          Module, Param)


def _effect(name, fx2_id, priority=0, reserved=(), buffers=False):
    return Module(
        name=name, key=name.upper(), kind=Kind.DSP_EFFECT,
        doc="fixture",
        menu=MenuEntry(fx2_id=fx2_id, donor_desc=0x400d58b8,
                       abbr=b"FIX", fullname=b"Fixture"),
        params=tuple([Param(b"A", 0, active=True)] + [Param()] * 11),
        # No asm path on disk, so the ledger's scan finds nothing and only
        # the reserved words below are claimed -- which is what lets these
        # fixtures test the claim path in isolation.
        dsp=DspSection(asm="does/not/exist.asm", priority=priority),
        claims=Claims(reserved_private_y=reserved,
                      owns_fx2_buffers=buffers),
    )


def _cave(name, cave_addr, length=16, hook_addr=None):
    return Module(
        name=name, key=name.upper(), kind=Kind.CF_PATCH, doc="fixture",
        cf_patches=(CavePatch(label=f"{name} cave", cave_addr=cave_addr,
                              pinned=b"\x4e\x71" * (length // 2),
                              hook_addr=hook_addr,
                              hook_stock=b"\x00" * 10 if hook_addr else b""),),
    )


CASES = [
    ("two modules claiming one FX2 id",
     [_effect("alpha", 0x07), _effect("beta", 0x07)], "fx2 id"),
    ("two caves overlapping in memory",
     [_cave("alpha", 0x400d7000, 64), _cave("beta", 0x400d7020, 64)],
     "ColdFire cave"),
    ("two modules hooking the same instruction",
     [_cave("alpha", 0x400d7000, hook_addr=0x40004d40),
      _cave("beta", 0x400d7100, hook_addr=0x40004d40)], "hook site"),
    ("two effects claiming one core-private Y word",
     [_effect("alpha", 0x07, reserved=(0x0905,)),
      _effect("beta", 0x08, reserved=(0x0905,))], "core-private Y"),
    # The shape this one guards is a module that works perfectly in every
    # test done alone: ChonVerb's tank and Nimbus's granular line are both
    # hardcoded into Y:0x4000-0xBFFF, which is per CORE.
    ("two effects owning the FX2 instance buffer region",
     [_effect("alpha", 0x07, buffers=True),
      _effect("beta", 0x08, buffers=True)], "FX2 instance buffers"),
]

CLEAN = [_effect("alpha", 0x07, reserved=(0x0905,)),
         _effect("beta", 0x08, reserved=(0x0906,)),
         _cave("gamma", 0x400d7000, 64, hook_addr=0x40004d40),
         _cave("delta", 0x400d7040, 64, hook_addr=0x40004d50)]


def main():
    bad = 0
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
    found = ledger.check(CLEAN)
    if found:
        bad += 1
        print(f"  [FAIL] modules that do not collide were reported: {found}")
    else:
        print("  [PASS] modules that do not collide are left alone")

    # ---- the rig's derivations (tools/remix/rig.py) ---------------------
    # The track model is DERIVED, so hold the derivation to the measured
    # facts: payload A serves TRACKS 5-8, B serves 1-4 (10 Aug 2026), an
    # insert runs anywhere, SYSTEM modules never sit on a track.
    from remix import registry, rig
    for mod in registry.modules().values():
        cat = rig.category(mod)
        tr = rig.track_range(mod)
        if cat == rig.SERVER:
            want = (rig.PAYLOAD_TRACKS["A"]
                    if mod.dsp.payloads == frozenset({"A"})
                    else rig.PAYLOAD_TRACKS["B"])
            ok = len(mod.dsp.payloads) == 1 and tr == want
        elif cat == rig.INSERT:
            ok = tr == rig.TRACKS
        else:
            ok = len(tr) == 0
        if ok:
            print(f"  [PASS] {mod.name}: {cat}, tracks "
                  f"{f'{tr.start}-{tr.stop - 1}' if len(tr) else 'none'}")
        else:
            bad += 1
            print(f"  [FAIL] {mod.name}: category {cat} derived tracks {tr}")
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
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import render_reverb
    cv = registry.by_key("REVERB SERVER")
    for name, slot in sorted(cv.knob_map().items(), key=lambda kv: kv[1]):
        if slot == 7:
            ok = render_reverb.PARAMS[slot][0] == "_C"   # MODE goes via --mode
        else:
            rr_name = render_reverb.PARAMS[slot][0]
            ok = rr_name in render_reverb.NAMES and \
                render_reverb.NAMES[rr_name] == slot
        if not ok:
            bad += 1
            print(f"  [FAIL] chonverb {name}@{slot} has no aligned "
                  f"render_reverb param")
    else:
        print("  [PASS] chonverb's manifest slots align with render_reverb")

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
