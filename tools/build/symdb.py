#!/usr/bin/env python3
"""Symbol database: addresses, names, sizes and references from the repo's own tables and a build.

    python3 tools/build/symdb.py build [--remix NAME] [--platform DIR] [--out FILE] [--ghidra]
    make symbols [REMIX=]

Writes out/symbols.sqlite (never committed). Rows come from, in order: `layout` (tools/ghidra/ot_ghidra.py's
tables), `dispatch` (both payloads' effect dispatch tables and what they point at, from the stock image), `equ` (every `.set`/`.equ` of a stock address in modules), `map` (the build's runtime.elf at runtime
addresses), `build` (the remix's detour sites and cave hooks; the build's DSP window, demand and guard records), `cite` (tools/build/where.py's scan), `ghidra`
(out/ghidra/symbols.tsv and xrefs.tsv when present). Two names at one address are two rows. The DB holds no
image bytes and no disassembly.
"""
import argparse
import datetime
import hashlib
import pathlib
import re
import sqlite3
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools")); sys.path.insert(0, str(ROOT / "tools/ghidra")); sys.path.insert(0, str(ROOT / "tools/build"))
SCHEMA = 1
DEFAULT_OUT = ROOT / "out/symbols.sqlite"

DDL = """
CREATE TABLE meta   (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE symbol (space TEXT NOT NULL, addr INTEGER NOT NULL, size INTEGER, name TEXT NOT NULL,
                     kind TEXT NOT NULL, owner TEXT NOT NULL, source TEXT NOT NULL, ref TEXT);
CREATE INDEX symbol_addr ON symbol(space, addr);
CREATE INDEX symbol_name ON symbol(name);
CREATE TABLE xref   (space TEXT, src INTEGER, dst INTEGER, kind TEXT);
CREATE INDEX xref_dst ON xref(space, dst);
CREATE TABLE cite   (space TEXT, addr INTEGER, file TEXT, line INTEGER);
CREATE INDEX cite_addr ON cite(space, addr);
"""


def ingest_layout(add):
    import ot_ghidra as g
    n = 0
    for name, start, length, _flags in g.CF_BLOCKS:
        if start is not None:
            add("cf", start, length, name, "block", "stock", "layout", "tools/ghidra/ot_ghidra.py:CF_BLOCKS"); n += 1
    for addr, name, _c in g.CF_IO:
        add("cf", addr, None, name, "io", "stock", "layout", "tools/ghidra/ot_ghidra.py:CF_IO"); n += 1
    for addr, name, _c in g.CF_FUNCS:
        add("cf", addr, None, name, "func", "stock", "layout", "tools/ghidra/ot_ghidra.py:CF_FUNCS"); n += 1
    for addr, name, size, _c in g.CF_DATA:
        add("cf", addr, size or None, name, "data", "stock", "layout", "tools/ghidra/ot_ghidra.py:CF_DATA"); n += 1
    for kind, addr, name, _c in g.DSP_A_NAMES:
        add("dspA:P", addr, None, name, kind, "stock", "layout", "tools/ghidra/ot_ghidra.py:DSP_A_NAMES"); n += 1
    for sp, regs in g.DSP_IO.items():
        for addr, name in regs.items():
            for core in "AB":
                add(f"dsp{core}:{sp}", addr, 1, name, "io", "stock", "layout", "tools/ghidra/ot_ghidra.py:DSP_IO"); n += 1
    return n


DSP_LINE = re.compile(r"^(func|label) ([PXY]):0x([0-9a-f]+) (\S+)")


def ingest_dispatch(add):
    """Both payloads' dispatch tables and the entries they point at (`fx_filter_process`, `fx_null_init`, the
    two tables themselves, the payload entries), named by ot_ghidra.dsp_layout from the stock image. Needs
    out/raw/section_3_MAIN_OS.bin; names and addresses only."""
    import ot_ghidra as g
    if not g.IMG.exists():
        return None
    cores, _shared = g.dsp_images(g.IMG.read_bytes())
    n = 0
    for tag, (mem, recs, entry) in cores.items():
        other = cores["B"][2] if tag == "A" else None
        for line in g.dsp_layout(tag, mem, recs, entry, other):
            m = DSP_LINE.match(line)
            if m and m.group(4) not in {x[2] for x in g.DSP_A_NAMES}:
                kind, sp, addr, name = m.groups()
                add(f"dsp{tag}:{sp}", int(addr, 16), None, name, kind, "stock", "dispatch",
                    "tools/ghidra/ot_ghidra.py:dsp_layout"); n += 1
    return n


def ingest_equ(add):
    import ot_ghidra as g
    n = 0
    for addr, names in g.module_names().items():
        for name, file, _c in names:
            add("cf", addr, None, name, "label", "stock", "equ", file); n += 1
    return n


def _units(platform):
    import json
    p = platform / "layout.json"
    # the generated clones unit is filed under whichever module the build listed it with: name it "build"
    return [("build" if u[1] == "clones" else u[0]) for u in json.loads(p.read_text())["units"]] if p.exists() else []


def ingest_map(add, platform):
    """Module symbols at their runtime addresses, from the final link's ELF. A symbol inside the clones'
    staging range (layout.json's stage..stage_end; TRAPS trap-dram-clone-stage) is not a runtime address and
    is left out; the final ELF's CLONE_<key> symbols are in the runtime (measured on octabam, 15 Nov 2026:
    all five between base and runtime_end)."""
    elf, mp = platform / "runtime/runtime.elf", platform / "runtime/runtime.map"
    if not elf.exists():
        return None
    owners = _units(platform)
    lay = platform / "layout.json"
    stage = (lambda j: (j.get("stage", 0), j.get("stage_end", 0)))(__import__("json").loads(lay.read_text())) if lay.exists() else (0, 0)
    ranges = []
    if mp.exists():
        for line in mp.read_text(errors="replace").splitlines():
            f = line.rstrip().split(None, 3)
            if len(f) == 4 and f[0].startswith(".") and f[3].endswith(".o"):
                m = re.match(r"(\d+)_", pathlib.Path(f[3]).name)
                try:
                    ranges.append((int(f[1], 16), int(f[1], 16) + int(f[2], 16), owners[int(m.group(1))] if m else "?"))
                except (ValueError, IndexError):
                    pass
    out = subprocess.run(["m68k-elf-nm", "-S", "-n", "--defined-only", str(elf)], capture_output=True, text=True, check=True).stdout
    n = 0
    for line in out.splitlines():
        f = line.split()
        if len(f) == 4:
            addr, size, t, name = int(f[0], 16), int(f[1], 16), f[2], f[3]
        elif len(f) == 3:
            addr, size, t, name = int(f[0], 16), None, f[1], f[2]
        else:
            continue
        if t in "aA" or name.startswith(".L") or stage[0] <= addr < stage[1]:
            continue
        owner = next((o for lo, hi, o in ranges if lo <= addr < hi), "module")
        add("cf", addr, size, name, "func" if t in "Tt" else "data", owner, "map", "out/platform/runtime/runtime.elf"); n += 1
    return n


def ingest_build(add, remix):
    from remix import registry
    n = 0
    for m in registry.selected(registry.remix(remix)):
        for d in m.detours:
            add("cf", d.site, d.pad_to or 6, f"hook {d.symbol or hex(d.target or 0)}", "hook", m.key, "build",
                f"modules/{m.name}/manifest.py"); n += 1
        for c in m.cf_patches:
            if c.hook_addr:
                add("cf", c.hook_addr, len(c.hook_stock) or None, f"hook {c.label}", "hook", m.key, "build", f"modules/{m.name}/manifest.py"); n += 1
            if c.cave_addr:
                add("cf", c.cave_addr, len(c.pinned), c.label, "cave", m.key, "build", f"modules/{m.name}/manifest.py"); n += 1
    return n


def ingest_dsp(add, dsp):
    """The build's DSP records (out/dsp/*_records.json): the shared window's blocks, each demand-loaded
    module's homes with init and proc, and the guard wrappers. A window address is the same word on both
    cores (CHIP.md section 3); a record is filed under core A unless its name ends in :B or " B"."""
    import json
    n = 0

    def cores(name):
        if name.endswith(" AB"):
            return "AB"
        return "B" if name.endswith((":B", " B")) else "A"
    f = dsp / "window_records.json"
    if f.exists():
        for name, (addr, words) in json.loads(f.read_text()).items():
            for c in cores(name):
                add(f"dsp{c}:P", addr, len(words), name, "block", name.split(":")[0], "build", "out/dsp/window_records.json"); n += 1
    f = dsp / "demand_records.json"
    if f.exists():
        for key, r in json.loads(f.read_text()).items():
            for i, h in enumerate(r["homes"]):
                add("dspA:P", h["addr"], len(h["words"]), f"{key} home {i}", "block", key, "build", "out/dsp/demand_records.json")
                add("dspA:P", h["init"], None, f"{key} init (home {i})", "func", key, "build", "out/dsp/demand_records.json")
                add("dspA:P", h["proc"], None, f"{key} proc (home {i})", "func", key, "build", "out/dsp/demand_records.json")
                n += 3
    f = dsp / "guard_records.json"
    if f.exists():
        for name, r in json.loads(f.read_text()).items():
            key, _, c = name.partition(":")
            for k in ("init", "proc"):
                if k in r:
                    add(f"dsp{c or 'A'}:P", r[k], None, f"{key} guard {k}", "func", key, "build", "out/dsp/guard_records.json"); n += 1
    return n


def ingest_cite(db):
    import where
    n = 0
    for addr, rows in where.scan().items():
        for src, _para in rows:
            f, _, line = src.rpartition(":")
            db.execute("INSERT INTO cite VALUES ('cf',?,?,?)", (addr, f, int(line))); n += 1
    return n


def ingest_ghidra(db, add):
    d = ROOT / "out/ghidra"
    syms, xr = d / "symbols.tsv", d / "xrefs.tsv"
    if not syms.exists():
        print("symdb: no out/ghidra/symbols.tsv; ghidra ingester skipped (OtExport.java writes it)")
        return None
    n = 0
    for line in syms.read_text().splitlines():
        sp, addr, size, name = line.split("\t")[:4]
        add(sp, int(addr, 16), int(size, 16) if size else None, name, "func", "stock", "ghidra", None); n += 1
    if xr.exists():
        for line in xr.read_text().splitlines():
            sp, src, dst, kind = line.split("\t")[:4]
            db.execute("INSERT INTO xref VALUES (?,?,?,?)", (sp, int(src, 16), int(dst, 16), kind))
    return n


def build(remix, platform, out, ghidra):
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    db = sqlite3.connect(out)
    db.executescript(DDL)

    def add(space, addr, size, name, kind, owner, source, ref):
        db.execute("INSERT INTO symbol VALUES (?,?,?,?,?,?,?,?)", (space, addr, size, name, kind, owner, source, ref))

    counts = {"layout": ingest_layout(add), "dispatch": ingest_dispatch(add), "equ": ingest_equ(add),
              "map": ingest_map(add, platform)}
    counts["build"] = ingest_build(add, remix) if remix else None
    counts["dsp"] = ingest_dsp(add, platform.parent / "dsp") or None
    counts["cite"] = ingest_cite(db)
    counts["ghidra"] = ingest_ghidra(db, add) if ghidra else None
    img = ROOT / "out/raw/section_3_MAIN_OS.bin"
    meta = {"schema": SCHEMA, "image_sha256": hashlib.sha256(img.read_bytes()).hexdigest() if img.exists() else "",
            "remix": remix or "", "built_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "ingesters": ",".join(k for k, v in counts.items() if v is not None)}
    db.executemany("INSERT INTO meta VALUES (?,?)", meta.items())
    db.commit()
    db.close()
    for k, v in counts.items():
        print(f"symdb: {k:7s} {'skipped' if v is None else f'{v} rows'}")
    print(f"symdb: wrote {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--remix")
    b.add_argument("--platform", type=pathlib.Path, default=ROOT / "out/platform")
    b.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    b.add_argument("--ghidra", action="store_true")
    a = ap.parse_args()
    build(a.remix, a.platform, a.out, a.ghidra)


if __name__ == "__main__":
    main()
