#!/usr/bin/env python3
"""ColdFire instruction forms of a remix's runtime units that no stock code has run (docs/contributing/COLDFIRE_FORMS.md).

usage: python3 tools/build/cf_forms.py --census REMIX [--json]

A form is objdump's text of one instruction with numbers, addresses and branch targets blanked and register
classes kept, plus the instruction's byte length: `movel An@(N,Dn:l:4),An  [4b]`. The size suffix is part of the
mnemonic, the index register's size and scale are kept (ColdFire has no word index), and so are the EMAC
operands `<<`, `>>` and `&`.

Stock side: the address runs of instructions Ghidra's analysis found in MAIN_OS (tools/build/cf_code_runs.tsv,
written by tools/ghidra/OtCode.java), decoded from the user's own image. A linear sweep of the image would decode
its tables as code (2,965 of 3,541 forms measured), so it is not used. A run whose end objdump does not reach as an
instruction boundary is counted in `stock_misaligned` (its forms are still read).

Module side: the build assembles each runtime unit with `-almn` (tools/remix/platform_build.py link_runtime) and
writes out/platform/runtime/<NN>_<label>.lst, and listings.json beside them naming each unit's label and source (the
gate checks it against layout.json and the registry, so a listing of another build is refused). A listing line is an instruction unless its source, after an
optional `label:` and the `|` comment, starts with a directive (`.` or `dc.`). The instruction bytes of a unit
are decoded in one objdump run and every instruction's decoded length is checked against the listing's: a unit
where they differ is a problem (`problems`), never a silent mis-decode. Raw `objdump -d` of the object files is
not used: tables in `.text` decode as instructions there (1,016 forms against 535).

Not covered: ROM caves and detour stubs (build_bus.py assembles them without link_runtime), the loader, an
instruction a source writes as `.short`/`.word`, and a stock function Ghidra did not reach (its forms have no site
here: the error is toward reporting).
"""
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
OBJDUMP = "m68k-elf-objdump"
MACHINES = ("m68k:isa-c:emac", "m68k:cfv4e")     # this objdump refuses m68k:54455 and m68k:5475
IMAGE = ROOT / "out/raw/section_3_MAIN_OS.bin"
BASE = 0x40000400
RUNS = ROOT / "tools/build/cf_code_runs.tsv"
TABLE = ROOT / "docs/contributing/COLDFIRE_FORMS.md"
PLATFORM = ROOT / "out/platform"

INSN = re.compile(r"^\s*([0-9a-f]+):\t((?:[0-9a-f]{4} )+)\s*\t(\S+)(?:\s+(.*?))?\s*$")
REGLIST = re.compile(r"^%[a-z0-9]+([-/]%[a-z0-9]+)+$")


def machine():
    """The first machine name this objdump accepts for ColdFire ISA C + EMAC, or None without the tool."""
    for m in MACHINES:
        try:
            with tempfile.NamedTemporaryFile(suffix=".bin") as f:
                f.write(b"\x70\x01")                   # moveq #1,%d0
                f.flush()
                r = subprocess.run([OBJDUMP, "-D", "-b", "binary", "-m", m, f.name], capture_output=True, text=True)
        except FileNotFoundError:
            return None
        if "moveq" in r.stdout:
            return m
    return None


def operand(o):
    o = re.sub(r"\s*<[^>]*>", "", o.strip())
    if REGLIST.match(o):
        return "REGS"
    o = re.sub(r"%([da])[0-7]([lu])\b", lambda m: ("Dn" if m.group(1) == "d" else "An") + m.group(2), o)
    o = re.sub(r"%d[0-7]\b", "Dn", o)
    o = re.sub(r"%(?:a[0-7]|sp|fp)\b", "An", o)
    o = re.sub(r"%acc[0-3]\b", "ACC", o)
    o = re.sub(r"%accext\d+\b", "ACCEXT", o)
    o = re.sub(r"#-?(?:0x[0-9a-f]+|\d+)", "#N", o)
    o = re.sub(r"@\(-?(?:0x)?[0-9a-f]+(?=[,)])", "@(N", o)
    o = re.sub(r"^-?(?:0x)?[0-9a-f]+(:[wl])?$", lambda m: "ABS" + (m.group(1) or ""), o)
    return o


def split_operands(ops):
    parts, depth, cur = [], 0, ""
    for ch in ops:
        depth += (ch == "(") - (ch == ")")
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    return parts + ([cur] if cur else [])


def form(mnemonic, operands, nbytes):
    return f"{mnemonic} {','.join(operand(p) for p in split_operands(operands))}  [{nbytes}b]"


def decode(blob, mach):
    """objdump of raw code bytes -> [(offset, nbytes, mnemonic, operands, text)] in order."""
    with tempfile.NamedTemporaryFile(suffix=".bin") as f:
        f.write(blob)
        f.flush()
        out = subprocess.run([OBJDUMP, "-D", "-b", "binary", "-m", mach, f.name], capture_output=True, text=True).stdout
    rows = []
    for line in out.splitlines():
        m = INSN.match(line)
        if m:
            rows.append((int(m.group(1), 16), len(m.group(2).split()) * 2, m.group(3), m.group(4) or "", line.strip()))
    return rows


def forms_of(rows):
    """{form: example text}. An undecodable word (objdump's `.short`) is its own form `(undecodable)`."""
    out = {}
    for _off, n, mn, ops, text in rows:
        out.setdefault("(undecodable)" if mn.startswith(".") else form(mn, ops, n), text)
    return out


def code_runs(path=RUNS):
    runs = []
    for line in pathlib.Path(path).read_text().splitlines():
        if line and not line.startswith("#"):
            a, b = line.split()
            runs.append((int(a, 16), int(b, 16)))
    return runs


def runs_header(path=RUNS):
    return dict(re.findall(r"^#\s*([\w-]+):\s*(.*)$", pathlib.Path(path).read_text(), re.M))


def image_sha(path=IMAGE):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def stock_forms(mach, image=IMAGE, runs=None):
    """({form: example}, misaligned run count, instructions) of the stock instructions in the Ghidra runs."""
    img = pathlib.Path(image).read_bytes()
    runs = code_runs() if runs is None else runs
    blob, ends, pos = b"", [], 0
    for a, b in runs:
        blob += img[a - BASE:b - BASE]
        pos += b - a
        ends.append(pos)
    rows = decode(blob, mach)
    starts = {r[0] for r in rows} | {len(blob)}
    return forms_of(rows), sum(1 for e in ends if e not in starts), len(rows)


def listing_instructions(path):
    """[(source line, source text, bytes)] of the instruction lines of an `-almn` listing: the lines whose source is
    not a directive. A listing line is `<source line> <address> <bytes>\t<source>`; the bytes that do not fit
    continue on lines of the same number holding bytes only. A macro expansion's source text starts with `>`."""
    lst = re.compile(r"^\s*(\d+)\s+([0-9a-f?]{4,8})\s+((?:[0-9A-F]{2,4} ?)+)\s*\t(.*)$")
    cont = re.compile(r"^\s*(\d+)\s{6,}((?:[0-9A-F]{2,4} ?)+)\s*$")
    out, cur = [], None
    for line in pathlib.Path(path).read_text(errors="replace").splitlines():
        m = lst.match(line)
        if m:
            src = m.group(4).split("|")[0].lstrip("> \t")
            while True:
                s2 = re.sub(r"^\s*(?:[A-Za-z_.$][\w.$]*|\d+):", "", src, count=1)
                if s2 == src:
                    break
                src = s2
            tok = src.split()
            if tok and not tok[0].startswith(".") and not re.match(r"dc\.[bwl]\b", tok[0]):
                cur = [int(m.group(1)), m.group(4).strip(), bytes.fromhex(m.group(3).replace(" ", ""))]
                out.append(cur)
            else:
                cur = None
            continue
        m = cont.match(line)
        if m and cur and int(m.group(1)) == cur[0]:
            cur[2] += bytes.fromhex(m.group(2).replace(" ", ""))
        else:
            cur = None
    return [tuple(x) for x in out]


def unit_forms(path, mach):
    """({form: example}, problems, instructions) of one unit's listing. A problem is an instruction whose decoded
    length is not the listing's, or one objdump cannot decode: decoding stops at the first, since every later
    instruction of the unit may be shifted."""
    insns = listing_instructions(path)
    rows = decode(b"".join(i[2] for i in insns), mach)
    problems, ok = [], []
    for k, (line, text, raw) in enumerate(insns):
        if k >= len(rows):
            problems.append(f"{pathlib.Path(path).name}:{line}: `{text}` is not decoded (the listing holds more instructions)")
            break
        if rows[k][1] != len(raw) or rows[k][2].startswith("."):
            problems.append(f"{pathlib.Path(path).name}:{line}: `{text}` is {len(raw)} bytes; objdump read "
                            f"`{rows[k][4].split(chr(9))[-1]}` ({rows[k][1]} bytes)")
            break
        ok.append(rows[k])
    return forms_of(ok), problems, len(ok)


def register_rows(path=TABLE):
    """The ColdFire form register of docs/contributing/COLDFIRE_FORMS.md: first cell a `form  [Nb]`."""
    p = pathlib.Path(path)
    if not p.exists():
        return {}
    rows = {}
    for line in p.read_text().splitlines():
        m = re.match(r"^\|\s*`([^`]+\[\d+b\])`\s*\|(.*)$", line)
        if m:
            rows[m.group(1)] = m.group(2).strip()
    return rows


def census(remix, platform=PLATFORM):
    """(per module, info) for the remix built into `platform`. per[key] = {units, instructions, forms,
    no_stock_site: {form: {example, row}}, level, bench_only, problems}."""
    sys.path.insert(0, str(ROOT / "tools"))
    from remix import registry
    from remix.schema import best
    mach = machine()
    stock, misaligned, n_stock = stock_forms(mach)
    rows = register_rows()
    selected = {m.key: m for m in registry.selected(registry.remix(remix))}
    sources = {(m.key, u.label): str(u.source) for m in selected.values() for u in (getattr(m, "linked", None) or ())}
    lay = json.loads((pathlib.Path(platform) / "layout.json").read_text())
    lj = pathlib.Path(platform) / "runtime" / "listings.json"
    listed = json.loads(lj.read_text()) if lj.exists() else []
    per, problems = {}, []
    if [(x[0], x[1]) for x in listed] != [(i, u[1]) for i, u in enumerate(lay["units"])]:
        problems.append(f"listings.json names {len(listed)} unit(s) that are not layout.json's {len(lay['units'])}: "
                        "the listings are of another build (make bus REMIX=...)")
        listed = []
    for i, u in enumerate(lay["units"]):
        key, label = u[0], u[1]
        if not listed:
            break
        lst = pathlib.Path(platform) / "runtime" / f"{i:02d}_{label}.lst"
        want = sources.get((key, label))
        if want and listed[i][2] != want:
            problems.append(f"{key} unit {label}: listings.json says {listed[i][2]}, the registry says {want}")
            continue
        if not lst.exists():
            problems.append(f"{key} unit {label}: no listing {lst.name} (the build writes one per unit)")
            continue
        f, probs, n = unit_forms(lst, mach)
        problems += [f"{key} unit {label}: {p}" for p in probs]
        r = per.setdefault(key, {"units": 0, "instructions": 0, "forms": {}, "problems": 0})
        r["units"] += 1
        r["instructions"] += n
        r["problems"] += len(probs)
        r["forms"].update(f)
    out = {}
    for key, r in per.items():
        m = selected.get(key)
        ev = best(m.evidence) if m else None
        new = {f: ex for f, ex in r["forms"].items() if f not in stock}
        out[key] = {"units": r["units"], "instructions": r["instructions"], "forms": len(r["forms"]),
                    "level": ev.level.name if ev else None, "bench_only": bool(m and m.bench_only),
                    "no_stock_site": {f: {"example": ex, "row": f in rows} for f, ex in sorted(new.items())}}
    info = {"stock_forms": len(stock), "stock_instructions": n_stock, "stock_runs": len(code_runs()),
            "stock_misaligned": misaligned, "problems": problems, "rows": len(rows),
            "unused_rows": sorted(set(rows) - {f for r in out.values() for f in r["no_stock_site"]})}
    return out, info


def print_census(remix, per, info):
    print(f"stock: {info['stock_forms']} forms from {info['stock_instructions']} instructions in {info['stock_runs']} Ghidra runs, "
          f"{info['stock_misaligned']} run end(s) not an objdump boundary")
    for key, r in per.items():
        n = r["no_stock_site"]
        print(f"{key}: {r['forms']} forms in {r['instructions']} instructions ({r['units']} unit(s)), {len(n)} with no stock site, "
              f"{sum(1 for v in n.values() if not v['row'])} of them with no row  [level {r['level']}]")
        for f, v in n.items():
            print(f"  {'row ' if v['row'] else 'NONE'} {f:56s} e.g. {v['example']}")
    for p in info["problems"]:
        print(f"problem: {p}")
    print(f"register rows no module uses: {len(info['unused_rows'])}")


def main(argv):
    if argv and argv[0] == "--census" and len(argv) > 1:
        per, info = census(argv[1])
        if "--json" in argv:
            print(json.dumps({"remix": argv[1], "modules": per, "info": info}, indent=1))
        else:
            print_census(argv[1], per, info)
        return 1 if info["problems"] else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
