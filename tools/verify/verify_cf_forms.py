#!/usr/bin/env python3
"""The ColdFire instruction forms a remix's runtime units contain, and which of them stock code has run.

    python3 tools/verify/verify_cf_forms.py <remix>

A form (tools/build/cf_forms.py) has a stock site when the analysed stock code (tools/build/cf_code_runs.tsv,
decoded from the user's own image) holds it. One without is cleared when its module's strongest Evidence is
Level.UNIT or above (the module ran on a unit) or a row of docs/contributing/COLDFIRE_FORMS.md names it; the rest
are reported, one line each, as the forms whose only evidence is the port (TRAPS trap-unicorn-frac,
trap-unicorn-macload, trap-macsr). This gate does not refuse them yet.

FAILs: the control is wrong; the image is not the one tools/build/cf_code_runs.tsv was written from; a unit has no
listing, or the listings are of another build; an instruction whose decoded length is not its listing's.

Control: `wddatal %a0@` (ISA C debug write; no stock site and no module of `octabam` uses it, measured 15 Nov 2026:
`ff1`, `bitrev`, `byterev`, `swap`, `satsl` and `halt` all have stock sites) must be reported (no stock site, no row) and `moveq #1,%d0` must not.

What it cannot see: ROM caves, detour stubs and the loader; an instruction a source writes as `.short`; a stock
function Ghidra did not reach (its forms have no site here); a unit run proves the paths that ran, not every
instruction of the source, and a source changed after the run keeps its level (tools/build/evidence.py stale lists
those); the port may still shim a form that has a stock site. SKIPs without the m68k binutils.
"""
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools")); sys.path.insert(0, str(ROOT / "tools/build"))
import cf_forms as cf  # noqa: E402
from remix.schema import Level  # noqa: E402

PROVEN = {l.name for l in Level if l.rank >= Level.UNIT.rank}
CONTROL = "        wddatal %a0@\n        moveq   #1,%d0\n"


def control(mach):
    """(forms of the control source, error): assembled with the build's own flags."""
    with tempfile.TemporaryDirectory() as d:
        src, obj, raw = pathlib.Path(d) / "c.s", pathlib.Path(d) / "c.o", pathlib.Path(d) / "c.bin"
        src.write_text(CONTROL)
        for args in (["m68k-elf-as", "-mcpu=54455", "-o", obj, src], ["m68k-elf-objcopy", "-O", "binary", "-j", ".text", obj, raw]):
            r = subprocess.run([str(a) for a in args], capture_output=True, text=True)
            if r.returncode:
                return {}, r.stderr.strip()[:200]
        return cf.forms_of(cf.decode(raw.read_bytes(), mach)), None


def main():
    remix = sys.argv[1]
    mach = cf.machine()
    if mach is None:
        print("  [SKIP] verify_cf_forms: m68k-elf-objdump (m68k:isa-c:emac) is not installed")
        return 0
    bad = 0
    head = cf.runs_header()
    sha = cf.image_sha() if cf.IMAGE.exists() else None
    if sha is None or sha != head.get("image-sha256"):
        print(f"  [FAIL] verify_cf_forms: out/raw/section_3_MAIN_OS.bin is {sha} and tools/build/cf_code_runs.tsv was written "
              f"from {head.get('image-sha256')}: regenerate it (tools/ghidra/README.md, OtCode.java)")
        return 1
    stock, misaligned, n_stock = cf.stock_forms(mach)
    ctl, err = control(mach)
    rows = cf.register_rows()
    new = {f for f in ctl if f not in stock and f not in rows}
    ok = new == {"wddatal An@  [2b]"}
    print(f"  [{'PASS' if ok else 'FAIL'}] control: wddatal %a0@ is reported, moveq #1,%d0 is not  {sorted(new) if not ok else ''}{err or ''}")
    bad += not ok
    from remix import registry  # noqa: E402
    dram = [u.label for m in registry.selected(registry.remix(remix)) for u in (getattr(m, "linked", None) or ())
            if getattr(u, "dram", False)]
    if not dram:
        # No runtime unit, so no out/platform/layout.json from this remix's build (bbd: a ROM stub only); one left by
        # another remix's build is not this remix's to census.
        print(f"  [PASS] {remix}: no runtime units (no module links into DRAM): no forms to census")
        print("verify_cf_forms: " + ("OK" if not bad else f"{bad} FAILED"))
        return 1 if bad else 0
    if not (cf.PLATFORM / "layout.json").is_file():
        # Run on its own (a CI unit of this job alone, sambanks/octabam#1157) nothing has built the remix: build it,
        # as the gates that read an image do. A listing of another remix's build is refused by the census below.
        env = dict(os.environ, REMIX=remix, XBUS="1", SPEC="1")
        env.setdefault("BUILD", "0")
        r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env, cwd=ROOT,
                           capture_output=True, text=True)
        if r.returncode:
            print(f"  [FAIL] verify_cf_forms: building {remix} failed:\n{(r.stdout + r.stderr)[-1200:]}")
            return 1
    per, info = cf.census(remix)
    for p in info["problems"]:
        print(f"  [FAIL] {p}")
        bad += 1
    totals = [0, 0, 0, 0, 0]                       # forms, no stock site, by a row, by the module's unit run, uncleared
    for key, r in per.items():
        totals[0] += r["forms"]
        unc = []
        for f, v in r["no_stock_site"].items():
            totals[1] += 1
            if v["row"]:
                totals[2] += 1
            elif r["level"] in PROVEN:
                totals[3] += 1
            else:
                unc.append((f, v["example"]))
        totals[4] += len(unc)
        if unc:
            print(f"  [info] {key} (level {r['level'] or 'none'}{', bench_only' if r['bench_only'] else ''}): "
                  f"{len(unc)} form(s) with no stock site, no row and no unit run")
            for f, ex in unc:
                print(f"           {f:50s} e.g. {ex}")
    if info["unused_rows"]:
        print(f"  [info] {len(info['unused_rows'])} register row(s) no module of {remix} needs")
    print(f"  [info] stock: {len(stock)} forms from {n_stock} instructions in {info['stock_runs']} Ghidra runs, "
          f"{misaligned} run end(s) not an objdump boundary")
    print(f"  [{'PASS' if not bad else 'FAIL'}] {remix}: {len(per)} modules, {totals[0]} forms; without a stock site: {totals[1]} "
          f"({totals[2]} by a register row, {totals[3]} by the module's unit run, {totals[4]} not cleared; not refused)")
    print("verify_cf_forms: " + ("OK" if not bad else f"{bad} FAILED"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
