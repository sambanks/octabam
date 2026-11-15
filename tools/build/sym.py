#!/usr/bin/env python3
"""Look an address or a name up in out/symbols.sqlite (tools/build/symdb.py).

    sym.py 0x4000aad0              the containing or nearest-below symbol: name+0xoff, owner, source, ref, cite count
    sym.py NAME                    exact, then prefix, matches
    sym.py --range LO HI           every symbol in [LO, HI)
    sym.py --callers 0x40054cd8    xrefs to an address (needs the ghidra ingester; exit 2 without it)
    sym.py --resolve               filter: rewrites each 0x4xxxxxxx on stdin to `0x4xxxxxxx <name+0xoff>`
    sym.py --histogram [--top N]   every 0x4xxxxxxx on stdin counted per symbol and per owner (PC samples:
                                   REMOTE's frame trace, ot_emu --profile)
    --json                         on every form (not --resolve)
    --space SPACE                  default cf; dspA:P, dspB:X, ...
DSP addresses are not rewritten by --resolve (ambiguous without a space).
"""
import argparse
import json
import pathlib
import re
import sqlite3
import sys

DB = pathlib.Path(__file__).resolve().parents[2] / "out/symbols.sqlite"
ADDR = re.compile(r"\b0x4[0-9a-fA-F]{7}\b")
# --resolve rewrites only an exact address or one inside a symbol's size: a nearest-below symbol without a size is a guess.
COLS = "space, addr, size, name, kind, owner, source, ref"


def connect(path=DB):
    if not pathlib.Path(path).exists():
        sys.exit("sym: no out/symbols.sqlite (make symbols)")
    return sqlite3.connect(path)


def rows(cur):
    keys = [c[0] for c in cur.description]
    return [dict(zip(keys, r)) for r in cur.fetchall()]


def at(db, addr, space="cf"):
    """Symbols that contain addr (sized and covering it), else those at the nearest address below. Narrowest first."""
    r = rows(db.execute(f"SELECT {COLS} FROM symbol WHERE space=? AND addr=? ORDER BY source", (space, addr)))
    if r:
        return r
    below = db.execute("SELECT MAX(addr) FROM symbol WHERE space=? AND addr<? AND kind NOT IN ('block')", (space, addr)).fetchone()[0]
    if below is None:
        return []
    r = rows(db.execute(f"SELECT {COLS} FROM symbol WHERE space=? AND addr=? AND kind<>'block' ORDER BY source", (space, below)))
    for x in r:
        x["off"] = addr - below
        x["covers"] = x["size"] is not None and addr < below + x["size"]
    return r


def cites(db, addr, space="cf"):
    return db.execute("SELECT COUNT(*) FROM cite WHERE space=? AND addr=?", (space, addr)).fetchone()[0]


def label(r):
    off = r.get("off", 0)
    return r["name"] + (f"+0x{off:x}" if off else "")


def resolve_line(db, line, cache):
    def sub(m):
        a = int(m.group(0), 16)
        if a not in cache:
            r = at(db, a)
            r = [x for x in r if x.get("covers", True)]
            cache[a] = label(r[0]) if r else None
        return f"{m.group(0)} <{cache[a]}>" if cache[a] else m.group(0)
    return ADDR.sub(sub, line)


def histogram(db, addrs):
    """PC samples counted per symbol and per owner. A sample with no covering or exact symbol is counted under
    its 256-byte page, `0x40098800.. (below: name)`, owner `unknown`: the symbol below is where to start
    looking, not the routine."""
    syms, owners, total, cache = {}, {}, 0, {}
    for a in addrs:
        total += 1
        if a not in cache:
            r = at(db, a)
            good = [x for x in r if x.get("covers", True)]
            pick = (good or r or [None])[0]
            cache[a] = ("(none)", "unknown") if pick is None else \
                ((pick["name"], pick["owner"]) if good else (f"{a & ~0xff:#x}.. (below: {pick['name']})", "unknown"))
        name, owner = cache[a]
        syms[name] = syms.get(name, 0) + 1
        owners[owner] = owners.get(owner, 0) + 1
    order = lambda d: sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))  # noqa: E731
    return {"samples": total, "owners": order(owners), "symbols": order(syms)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", nargs="?")
    ap.add_argument("--range", nargs=2, metavar=("LO", "HI"))
    ap.add_argument("--callers", metavar="ADDR")
    ap.add_argument("--resolve", action="store_true")
    ap.add_argument("--histogram", action="store_true")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--space", default="cf")
    ap.add_argument("--db", default=str(DB))
    a = ap.parse_args()
    db = connect(a.db)
    if a.resolve:
        cache = {}
        for line in sys.stdin:
            sys.stdout.write(resolve_line(db, line.rstrip("\n"), cache) + "\n")
        return 0
    if a.histogram:
        out = histogram(db, (int(m, 16) for line in sys.stdin for m in ADDR.findall(line)))
        if a.json:
            print(json.dumps(out, indent=1))
        else:
            n = out["samples"] or 1
            print(f"{out['samples']} samples")
            for title, rows_ in (("by owner", out["owners"]), ("by symbol", out["symbols"][:a.top])):
                print(title)
                for name, c in rows_:
                    print(f"  {c:7d} {100 * c / n:5.1f}%  {name}")
        return 0
    if a.callers:
        ing = (db.execute("SELECT value FROM meta WHERE key='ingesters'").fetchone() or [""])[0]
        if "ghidra" not in ing.split(","):
            print("sym: no xref rows: the database was built without the ghidra ingester (symdb.py build --ghidra)", file=sys.stderr)
            return 2
        dst = int(a.callers, 0)
        out = rows(db.execute("SELECT space, src, dst, kind FROM xref WHERE space=? AND dst=? ORDER BY src", (a.space, dst)))
        for x in out:
            s = at(db, x["src"], a.space)
            x["from"] = label(s[0]) if s else None
        print(json.dumps(out, indent=1) if a.json else "\n".join(f"0x{x['src']:08x} {x['kind']:5s} {x['from'] or ''}" for x in out))
        return 0
    if a.range:
        lo, hi = (int(x, 0) for x in a.range)
        out = rows(db.execute(f"SELECT {COLS} FROM symbol WHERE space=? AND addr>=? AND addr<? ORDER BY addr, source", (a.space, lo, hi)))
        print(json.dumps(out, indent=1) if a.json else "\n".join(
            f"0x{x['addr']:08x} {x['size'] if x['size'] is not None else '-':>6} {x['name']}  [{x['owner']}/{x['source']}]" for x in out))
        return 0 if out else 1
    if not a.query:
        ap.error("an address, a name, --range, --callers or --resolve")
    if (re.fullmatch(r"(0x)?[0-9a-fA-F]{6,8}", a.query) and (a.query.startswith("0x") or a.query.isdigit())) \
            or (a.space != "cf" and re.fullmatch(r"0x[0-9a-fA-F]{1,8}", a.query)):      # a DSP address is short
        addr = int(a.query, 16 if a.query.startswith("0x") else 10)
        r = at(db, addr, a.space)
        n = cites(db, addr, a.space)
        if a.json:
            print(json.dumps({"addr": addr, "symbols": r, "cites": n}, indent=1))
        elif not r:
            print(f"0x{addr:08x}: no symbol at or below")
        else:
            for x in r:
                note = "" if x.get("covers", True) else (" (size unknown)" if x["size"] is None else " (past its size)")
                print(f"0x{addr:08x} {label(x)}{note}  {x['kind']} owner={x['owner']} source={x['source']}"
                      f"{' ref=' + x['ref'] if x['ref'] else ''}  cites={n}")
        return 0 if r else 1
    r = rows(db.execute(f"SELECT {COLS} FROM symbol WHERE name=? ORDER BY space, addr", (a.query,)))
    if not r:
        r = rows(db.execute(f"SELECT {COLS} FROM symbol WHERE name LIKE ? ESCAPE '\\' ORDER BY name, addr LIMIT 50",
                            (a.query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%",)))
    if a.json:
        print(json.dumps(r, indent=1))
    else:
        for x in r:
            print(f"{x['space']} 0x{x['addr']:08x} {x['name']}  {x['kind']} owner={x['owner']} source={x['source']}")
    return 0 if r else 1


if __name__ == "__main__":
    sys.exit(main())
