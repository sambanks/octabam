#!/usr/bin/env python3
"""Print the module index and the available remixes.

    python3 tools/remix/index.py

This is the authoritative list. Anything written in a README is a copy, and
copies go stale -- so when the two disagree, this is right.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from remix import registry  # noqa: E402
from remix.schema import Kind  # noqa: E402


def main():
    mods = registry.modules()
    print("MODULES  (modules/<name>/manifest.py)\n")
    for key in sorted(mods):
        m = mods[key]
        if m.is_stock:
            continue
        bits = []
        if m.menu is not None:
            bits.append(f"FX2 id 0x{m.menu.fx2_id:02x}")
            bits.append(f"{len(m.active_params)} knobs")
        if m.dsp is not None:
            bits.append(f"asm {m.dsp.asm}")
        if m.cf_patches:
            bits.append(f"{len(m.cf_patches)} ColdFire cave"
                        f"{'s' if len(m.cf_patches) > 1 else ''}")
        print(f"  {m.name:<12} {m.kind.value:<10} [{m.key}]")
        print(f"      {m.doc}")
        print(f"      {' | '.join(bits)}")
        if m.menu is not None:
            knobs = ", ".join(f"{n}@{i}" for n, i in sorted(
                m.knob_map().items(), key=lambda kv: kv[1]))
            print(f"      knobs: {knobs}")
        print()

    from remix import stock
    print("STOCK FX2 EFFECTS  (tools/remix/stock.py -- already in every image;\n"
          "list one in a remix to KEEP its chooser row, by key)\n")
    for m in stock.MODULES:
        buf = "  [instance buffer -- not beside BusVerb/Nimbus/BusDelay]" \
            if m.claims is not None and m.claims.stock_instance_buffer else ""
        print(f"  {m.key:<12} FX2 id 0x{m.menu.fx2_id:02x}  {m.doc}{buf}")
        if m.params:
            knobs = ", ".join(f"{n}@{i}" for n, i in sorted(
                m.knob_map().items(), key=lambda kv: kv[1]))
            print(f"      knobs: {knobs}")
    # ⚠️ NOT "every remix" any more: what a remix gives up is DERIVED from
    # its two choosers -- an effect on neither is one it does not want -- and
    # each remix's is printed with it below when it differs from these.
    print(f"\n  given up by most remixes (on neither chooser): "
          f"{', '.join(stock.CONSUMED)}\n")

    print("REMIXES  (remixes/<name>.py)\n")
    for name in registry.remix_names():
        r = registry.remix(name)
        default = "  <- default" if name == registry.DEFAULT_REMIX else ""
        print(f"  {r.name:<12} {r.doc}{default}")
        print(f"      modules: {', '.join(r.modules)}")
        if r.fx1:
            print(f"      also on the FX1 chooser: {', '.join(r.fx1)}")
        _hv = stock.region_of(stock.harvested(
            set(r.modules) | set(r.fx1 or [
                k for k in stock.p_spans("A")
                if registry.modules()[k].menu.fx2_id in stock.fx1_ids()])))
        if tuple(_hv) != stock.CONSUMED:
            print(f"      gives up (on neither chooser): "
                  f"{', '.join(_hv) or 'nothing'}")
        print(f"      unimplemented ids fall back to: {r.fallback}")
        print()
    print("Build one with:  make bus REMIX=<name>")


if __name__ == "__main__":
    main()
