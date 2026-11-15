#!/usr/bin/env python3
"""Every DSP instruction form a remix ships has run on the chip, or is approved by name.

    python3 tools/verify/verify_dsp_forms.py <remix>

A form (tools/build/dsp_forms.py: the disassembled text with numbers and branch targets blanked, plus the word
count) passes when
  a stock payload has a site of it (out/dsp/payload_{A,B}.asm), or
  its module's strongest Evidence is Level.UNIT or above (the module ran on a unit), or
  a row of docs/firmware/CHIP.md's instruction-form register names it.
Anything else FAILs with the module, the form and an example site (TRAPS trap-chip-form), except the forms of a
module declared `bench_only` in a remix under remixes/test, which are counted as [info]; in a release remix they FAIL.

Negative control: `move a,y:(r3+$1)` (image 44's form: no stock site, no row) must be reported and `move x0,a`
must not. Register rows no module of this remix needs are counted as [info].

What it cannot see: a stock listing decodes tables as code, so a form can have a "site" the chip never ran; a
module's unit run proves the paths that ran, not every instruction of its source, and a source changed after
the run keeps its level (tools/build/evidence.py stale lists those); the build's own stubs, hook stubs and
trampolines are not assembled here. SKIPs without dsp_asm or dsp56kDisassemble.
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools")); sys.path.insert(0, str(ROOT / "tools/build"))
import dsp_forms as df  # noqa: E402
from remix import registry  # noqa: E402
from remix.schema import Level  # noqa: E402

CONTROL = "init:\n        move    a,y:(r3+$1)\n        move    x0,a\nproc:\n        rts\n"
PROVEN = {l.name for l in Level if l.rank >= Level.UNIT.rank}


def main():
    remix = sys.argv[1]
    if not df.DIS.exists() or not df.ASM.exists():
        print("  [SKIP] verify_dsp_forms: dsp_asm or dsp56kDisassemble is not built (make setup)")
        return 0
    stock_paths = [ROOT / "out/dsp/payload_A.asm", ROOT / "out/dsp/payload_B.asm"]
    if not all(p.exists() for p in stock_paths):
        subprocess.run([sys.executable, "tools/build/dsp_disasm_all.py"], cwd=ROOT, capture_output=True)
    if not all(p.exists() for p in stock_paths):
        print("  [FAIL] verify_dsp_forms: no out/dsp/payload_A.asm (tools/build/dsp_disasm_all.py)")
        return 1
    stock, rows = df.stock_forms(stock_paths), df.register_rows()
    bad = 0
    words, err = df.assemble_text(CONTROL)
    ctl = df.disassemble(words, "800") if words else {}
    new = {f for f in ctl if f not in stock and f not in rows}
    ok = new == {"move a,y:(r3+N)  [1w]"}
    print(f"  [{'PASS' if ok else 'FAIL'}] control: move a,y:(r3+$1) is reported, move x0,a is not  {sorted(new) if not ok else ''}{err or ''}")
    bad += not ok
    res, unused = df.census(remix)
    counts = [0, 0, 0, 0]                                 # forms, by a row, by the module's unit run, refused
    test, bench = registry.is_test(remix), {}
    for key, r in res.items():
        if r["status"] != "listing":
            print(f"  [FAIL] {key}: its forms could not be read: {r['status']} ({r['source']})")
            bad += 1
            continue
        counts[0] += r["forms"]
        for f, v in r["no_stock_site"].items():
            if v["row"]:
                counts[1] += 1
            elif r["level"] in PROVEN:
                counts[2] += 1
            elif r["bench_only"] and test:
                bench[key] = bench.get(key, 0) + 1
            else:
                counts[3] += 1
                bad += 1
                print(f"  [FAIL] {key}: `{f.strip()}` has no stock site, no register row, and {key} is at "
                      f"{r['level'] or 'no level'}  e.g. {v['example']}")
    for key, n in bench.items():
        print(f"  [info] {key} is bench_only: {n} form(s) with no stock site, row or unit run, not refused in a test remix")
    if unused:
        print(f"  [info] {len(unused)} register row(s) no module of {remix} needs" + (": " + "; ".join(f.strip() for f in unused) if len(unused) <= 4 else ""))
    print(f"  [{'PASS' if not counts[3] else 'FAIL'}] {remix}: {len(res)} DSP modules, {counts[0]} forms; without a stock site: "
          f"{counts[1]} by a register row, {counts[2]} by the module's unit run, {counts[3]} refused")
    print("verify_dsp_forms: " + ("OK" if not bad else f"{bad} FAILED"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
