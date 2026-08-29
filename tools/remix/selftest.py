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

    # And the real thing: every shipped remix must be clean.
    from remix import registry
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
