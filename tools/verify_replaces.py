#!/usr/bin/env python3
"""No stock effect is hijacked by accident.

    python3 tools/verify_replaces.py [remix ...]     (default: every remix)

THE FAILURE THIS EXISTS FOR. The DSP dispatch tables are indexed by the raw
effect id and SHARED BY BOTH MENUS, so a module carrying a stock effect's id
replaces that effect wherever it is selected -- FX1 included -- and a remix
that omits the module then aliases the id to the fallback, taking the stock
effect away from FX1 too. Rungs sat on EQUALIZER's 0x0c and Nimbus on DJ EQ's
0x0d from 29 Aug to 2 Sep 2026, in every local image. Every existing check
passed: the modules built, dispatched, rendered and sounded correct. What was
wrong was invisible from any one module's point of view.

WHAT IS CHECKED, per remix, per payload, for every stock effect id:

  * the module carrying it DECLARED it (MenuEntry.replaces naming that
    effect), or
  * the id is untouched -- FX2_IDS still points at the stock descriptor and
    the dispatch entries still hold the pristine image's values.

BOTH MENUS ARE CHECKED. FX1 resolves its own descriptors (FX1_IDS, and the
chooser list it scrolls), so an id can be correct on FX2 and wrong on FX1 --
which is the shape of the bug this file exists for. For a stock effect
nobody declared, FX1's two tables must read back the pristine image's
values; for a declared replacement, both must point at the module's clone
(or be left alone when FX1 does not list that effect at all).

THE ONE LEGITIMATE EXCEPTION is a donor reverb whose words this selection
took: PLATE/SPRING/DARK REV's code IS the donor region, so an id whose code
was overwritten is repointed at the null stub. That is allowed, and ONLY
that -- a donor id may be stock or the null stub, never anything else.

Static checks run with no image: a declared replacement must name a real
stock effect and carry that effect's id.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from remix import registry, stock  # noqa: E402

BASE = 0x40000400
FX2_IDS = 0x400d5fdc
FX1_IDS = 0x400d5f58
FX1_LIST = 0x400d6060
FX1_NONE = 0x400d4618
PRISTINE = pathlib.Path("out/raw/section_3_MAIN_OS.bin")
# (tag, xtab, null init, null proc) -- build_bus.py's PAYLOADS
PAYLOADS = (("A", 0x400e2345, 0x007c8, 0x007c9),
            ("B", 0x400f5a10, 0x00588, 0x00589))
DONOR_IDS = {0x14, 0x15, 0x16}


def rd32(img, p):
    return int.from_bytes(img[p - BASE:p - BASE + 4], "big")


def rdw(img, p):
    return int.from_bytes(img[p - BASE:p - BASE + 3], "little")


def _fx1_rows(pristine):
    """Addresses of the FX1 chooser list's entries, from the pristine image
    (the list is never relocated by build_bus -- a replacement rewrites a row
    in place -- so the pristine addresses are the live ones)."""
    out, a = [], FX1_LIST
    while rd32(pristine, a) != 0 and len(out) < 32:
        out.append(a)
        a += 4
    return out


def static_checks(fails):
    """A declared replacement must name a real stock effect, on its id."""
    for m in registry.modules().values():
        rep = m.menu.replaces if m.menu is not None else None
        if not rep:
            continue
        target = stock.BY_KEY.get(rep)
        if target is None:
            fails.append(f"{m.key}: replaces={rep!r}, which is not a stock "
                         f"effect (have: {', '.join(sorted(stock.BY_KEY))})")
        elif target.menu.fx2_id != m.menu.fx2_id:
            fails.append(
                f"{m.key}: replaces={rep!r} but carries id "
                f"0x{m.menu.fx2_id:02x}; {rep} is 0x{target.menu.fx2_id:02x}")
        else:
            print(f"  [PASS] {m.key} declares it replaces {rep} "
                  f"(id 0x{m.menu.fx2_id:02x})")


def check_image(name, img, pristine, fails):
    mods = registry.modules()
    remix = registry.remix(name)
    declared = {}
    for key in remix.modules:
        m = mods.get(key)
        if m is not None and m.menu is not None and m.menu.replaces:
            declared[m.menu.fx2_id] = m.key
    for eff in stock.MODULES:
        eid = eff.menu.fx2_id
        want_desc = eff.menu.donor_desc + 0x38
        fx1_slot = FX1_IDS + eid * 4
        on_fx1 = rd32(pristine, fx1_slot) != FX1_NONE
        if eid in declared:
            # A declared replacement must have taken FX1 too, or FX1 would
            # run its code under the stock effect's knob names.
            if not on_fx1:
                continue
            got_id = rd32(img, fx1_slot)
            got_row = [rd32(img, a) for a in _fx1_rows(pristine)
                       if rd32(pristine, a) == want_desc]
            if got_id == want_desc:
                fails.append(
                    f"{name}: FX1_IDS[0x{eid:02x}] still points at stock "
                    f"{eff.key}, but {declared[eid]} replaces it -- FX1 would "
                    f"run the module under stock's knob names")
            if got_row and got_row[0] == want_desc:
                fails.append(
                    f"{name}: the FX1 chooser row for {eff.key} still points "
                    f"at stock's descriptor, but {declared[eid]} replaces it")
            if got_id != want_desc and (not got_row or got_row[0] != want_desc):
                print(f"  [PASS] {name}: {declared[eid]} took {eff.key}'s FX1 "
                      f"page as well as FX2's")
            continue
        if on_fx1:
            for a in (fx1_slot,) + tuple(
                    x for x in _fx1_rows(pristine)
                    if rd32(pristine, x) == want_desc):
                if rd32(img, a) != rd32(pristine, a):
                    fails.append(
                        f"{name}: FX1 table at 0x{a:08x} ({eff.key}) is "
                        f"0x{rd32(img, a):08x}, not stock's "
                        f"0x{rd32(pristine, a):08x} -- nothing declared "
                        f"replaces={eff.key!r}")
        got_desc = rd32(img, FX2_IDS + eid * 4)
        if got_desc != want_desc:
            fails.append(
                f"{name}: FX2_IDS[0x{eid:02x}] ({eff.key}) is "
                f"0x{got_desc:08x}, not stock's 0x{want_desc:08x} -- nothing "
                f"in this remix declared replaces={eff.key!r}")
        for tag, xtab, nul_i, nul_p in PAYLOADS:
            for slot, nul in ((eid, nul_i), (32 + eid, nul_p)):
                got = rdw(img, xtab + slot * 3)
                want = rdw(pristine, xtab + slot * 3)
                if got == want:
                    continue
                if eid in DONOR_IDS and got == nul:
                    continue               # its words were taken; see above
                fails.append(
                    f"{name}: payload {tag} dispatch[0x{eid:02x}] "
                    f"({eff.key}) is 0x{got:05x}, not stock's 0x{want:05x}"
                    + (f" (nor the null stub 0x{nul:05x})"
                       if eid in DONOR_IDS else ""))


def main():
    if not PRISTINE.exists():
        sys.exit(f"missing {PRISTINE} -- run 'make setup'")
    pristine = PRISTINE.read_bytes()
    fails: list[str] = []
    static_checks(fails)
    names = sys.argv[1:] or [n for n in registry.remix_names()
                             if not n.startswith("_")]
    out = pathlib.Path("out/mainos_bus.bin")
    # ⚠️ EVERY BUILD HERE OVERWRITES THE SHIPPING ARTIFACT, and the checks
    # that run after this one read it. verify_burn already had to say so in
    # the Makefile; do it here instead, so the tool cleans up after itself
    # rather than the caller having to know. (audition.py uses the same
    # save-and-restore for its scratch builds.)
    saved = out.read_bytes() if out.exists() else None
    try:
        run(names, out, pristine, fails)
    finally:
        if saved is not None:
            out.write_bytes(saved)
    print()
    for f in fails:
        print(f"  [FAIL] {f}")
    print("OK" if not fails else f"{len(fails)} FAILED")
    return 1 if fails else 0


def run(names, out, pristine, fails):
    import os
    import subprocess
    for name in names:
        env = {**os.environ, "REMIX": name, "XBUS": "1", "SPEC": "1"}
        r = subprocess.run([sys.executable, "tools/build_bus.py"],
                           capture_output=True, text=True, env=env)
        if r.returncode != 0:
            tail = (r.stdout + r.stderr).strip().splitlines()
            fails.append(f"{name}: build failed: {tail[-1] if tail else '?'}")
            continue
        before = len(fails)
        check_image(name, out.read_bytes(), pristine, fails)
        if len(fails) == before:
            print(f"  [PASS] {name}: every stock id is stock's, or declared")


if __name__ == "__main__":
    sys.exit(main())
