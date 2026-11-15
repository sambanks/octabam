#!/usr/bin/env python3
"""DSP instruction forms with no stock site (docs/firmware/CHIP.md, the instruction-form register).

usage: python3 tools/build/dsp_forms.py out/dsp/payload_A.asm out/dsp/payload_B.asm <hex words file> <pc, hex>
       python3 tools/build/dsp_forms.py --census REMIX [--json]

The two stock listings come from tools/build/dsp_disasm_all.py; the words file holds the module's code words
(not its tables) as space-separated hex, e.g. from out/dsp/demand_records.json or window_records.json.
A form is the disassembled text with immediates, addresses and displacements blanked (registers, spaces and
addressing modes kept) plus the instruction's word count, so a short and a long encoding are different forms.

--census: for each module of the remix with a DspSection, the forms of its code words with no stock site and
whether a register row of CHIP.md matches. Code words come from assembling the module's source with dsp_asm
(`-org 800`, the ptable literals set to a placeholder) and decoding them with dsp56kDisassemble: every word of
an assembled source is code (dsp_asm has no data directive). Modules with no source on disk (a generated one
the build writes) and the build's own stubs and trampolines are reported as not covered.
"""
import json
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
DIS = ROOT / "vendor/dsp56300/build/source/disassemble/dsp56kDisassemble"
ASM = ROOT / "vendor/dsp56300/build/source/dsp_host/dsp_asm"
CHIP = ROOT / "docs/firmware/CHIP.md"
LINE = re.compile(r"^([0-9a-f]{5,6}):\s+(.*?)\s*;\s*([0-9a-f]{6})(?:\s+([0-9a-f]{6}))?\s*$")


def form(text, nwords):
    t = re.sub(r"\s+", " ", text.strip())
    t = re.sub(r"\b(func|loc|sub|lab)_[0-9a-f]+\b", "L", t)   # branch targets
    t = re.sub(r"\(r([0-7])-", r"(r\1+", t)              # a displacement's sign is not a form
    t = re.sub(r"[<>]?\$[0-9a-f]+", "N", t)          # immediates, addresses, displacements
    t = re.sub(r"#[<>]?-?[0-9]+\b", "#N", t)
    t = re.sub(r"\+-?[0-9]+\)", "+N)", t)
    return f"{t}  [{nwords}w]"


def forms_of(lines):
    out = {}
    for l in lines:
        m = LINE.match(l)
        if not m:
            continue
        f = form(m.group(2), 2 if m.group(4) else 1)
        out.setdefault(f, m.group(0))
    return out


def stock_forms(paths):
    stock = {}
    for p in paths:
        stock.update(forms_of(pathlib.Path(p).read_text().splitlines()))
    return stock


def disassemble(words_hex, pc):
    """Forms of the code words (a string of space-separated hex words) at pc: {form: example line}."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt") as f:
        f.write(words_hex)
        f.flush()
        r = subprocess.run([str(DIS), "-in", f.name, "-pc", pc], capture_output=True, text=True)
    return forms_of(r.stdout.splitlines())


def register_rows(path=CHIP):
    """The CHIP.md register's forms -> the row's text: first cell `form` (Nw) -> the form()'s '  [Nw]' spelling."""
    text = pathlib.Path(path).read_text()
    i = text.index("### The instruction-form register")
    rows = {}
    section = re.split(r"^#{1,3} ", text[i + 4:], maxsplit=1, flags=re.M)[0]
    for line in section.splitlines():
        m = re.match(r"^\|\s*`([^`]+)`\s*\((\d+)w\)\s*\|(.*)$", line)
        if m:
            rows[f"{m.group(1)}  [{m.group(2)}w]"] = m.group(3).strip()
    return rows


def assemble_words(src_path):
    """(hex words string, error) of a module source assembled at P:$800."""
    src = pathlib.Path(src_path).read_text().replace("$fab1e0", "$000400").replace("$fab2e0", "$000400")
    with tempfile.TemporaryDirectory(prefix="dspforms.") as d:
        d = pathlib.Path(d)
        (d / "s.asm").write_text(src)
        r = subprocess.run([str(ASM), "-in", str(d / "s.asm"), "-org", "800", "-out", str(d / "s.bin"),
                            "-sym", str(d / "s.sym")], capture_output=True, text=True)
        if r.returncode or not (d / "s.bin").exists():
            return None, (r.stderr or r.stdout).strip().splitlines()[-1:] or ["dsp_asm failed"]
        b = (d / "s.bin").read_bytes()
    return " ".join(f"{b[i] | b[i + 1] << 8 | b[i + 2] << 16:06x}" for i in range(0, len(b) - len(b) % 3, 3)), None


def census(remix):
    sys.path.insert(0, str(ROOT / "tools"))
    from remix import registry
    stock = stock_forms([ROOT / "out/dsp/payload_A.asm", ROOT / "out/dsp/payload_B.asm"])
    rows = register_rows()
    out = {}
    used = set()
    for m in registry.selected(registry.remix(remix)):
        d = m.dsp
        if d is None:
            continue
        src = ROOT / d.asm
        if not src.exists():
            out[m.key] = {"source": d.asm, "status": "no source on disk (written by the build)"}
            continue
        words, err = assemble_words(src)
        if words is None:
            out[m.key] = {"source": d.asm, "status": f"dsp_asm failed: {err[0]}"}
            continue
        mine = disassemble(words, "800")
        new = {f: ex.split(";")[0].strip() for f, ex in mine.items() if f not in stock}
        used |= set(new)
        out[m.key] = {"source": d.asm, "status": "listing", "forms": len(mine), "payloads": sorted(d.payloads),
                      "no_stock_site": {f: {"example": ex, "row": f in rows} for f, ex in sorted(new.items())}}
    return out, sorted(set(rows) - used)


def print_census(remix, res, unused):
    for key, r in res.items():
        if r["status"] != "listing":
            print(f"{key}: not covered: {r['status']} ({r['source']})")
            continue
        n = r["no_stock_site"]
        print(f"{key}: {r['forms']} forms, {len(n)} with no stock site, {sum(1 for v in n.values() if not v['row'])} of them with no row"
              f"  [source: dsp_asm listing of {r['source']}]")
        for f, v in n.items():
            print(f"  {'row ' if v['row'] else 'NONE'} {f:56s} e.g. {v['example']}")
    print(f"register rows no census module uses: {len(unused)}")


def main(argv):
    if argv and argv[0] == "--census":
        res, unused = census(argv[1])
        if "--json" in argv:
            print(json.dumps({"remix": argv[1], "modules": res, "unused_rows": unused}, indent=1))
        else:
            print_census(argv[1], res, unused)
        return 0
    stock = stock_forms(argv[0:2])
    mine = disassemble(open(argv[2]).read(), argv[3])
    new = {f: ex for f, ex in mine.items() if f not in stock}
    print(f"{len(mine)} forms, {len(new)} with no stock site")
    for f, ex in sorted(new.items()):
        print(f"  {f:60s} e.g. {ex.split(';')[0].strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
