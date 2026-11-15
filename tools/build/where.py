#!/usr/bin/env python3
"""What the docs already say about a ColdFire address, and what is there.

    python3 tools/build/where.py 0x40004d40
    make where A=0x40004d40 [N=128]

Prints every paragraph of AGENTS.md, README.md, docs/**/*.md,
tools/**/*.md and modules/*/README.md that cites the exact address (file:line first), the
nearest other cited addresses within 0x200, and an EMAC-correct
disassembly window from scripts/disasm.sh. The docs are scanned on each
call; nothing is cached or duplicated. A new finding about an address goes
in the topical doc under docs/firmware/, which is what the next call
prints.
"""
import argparse, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
ADDR_RE = re.compile(r"\b0x4[0-9a-f]{7}\b")
NEARBY_WINDOW = 0x200
NEARBY_MAX = 6


def files():
    return ([ROOT / "AGENTS.md", ROOT / "README.md"]
            + sorted((ROOT / "docs").rglob("*.md"))
            + sorted((ROOT / "tools").rglob("*.md"))
            + sorted((ROOT / "modules").glob("*/README.md")))


def paragraphs(text):
    """(start_line, paragraph) per blank-line-delimited block."""
    buf, start = [], 1
    for i, line in enumerate(text.splitlines(), 1):
        if line.strip():
            if not buf:
                start = i
            buf.append(line)
        elif buf:
            yield start, "\n".join(buf)
            buf = []
    if buf:
        yield start, "\n".join(buf)


def scan():
    """addr -> [(file:line, paragraph)] over every doc, one pass."""
    cites = {}
    for f in files():
        if not f.is_file():
            continue
        rel = f.relative_to(ROOT)
        for start, para in paragraphs(f.read_text(errors="replace")):
            for a in set(ADDR_RE.findall(para)):
                cites.setdefault(int(a, 16), []).append((f"{rel}:{start}", para))
    return cites


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("addr")
    ap.add_argument("--bytes", "-n", type=lambda s: int(s, 0), default=64,
                    help="disassembly window size (default 64)")
    args = ap.parse_args()
    s = args.addr.strip().lower()
    s = s if s.startswith("0x") else "0x" + s
    if not re.fullmatch(r"0x[0-9a-f]{6,8}", s):
        sys.exit(f"where: {args.addr!r} is not a hex address")
    ival = int(s, 16)
    cites = scan()

    print(f"=== 0x{ival:08x} ===")
    db = ROOT / "out/symbols.sqlite"
    if db.is_file():
        r = subprocess.run([sys.executable, str(ROOT / "tools/build/sym.py"), "--db", str(db), s], capture_output=True, text=True)
        if r.stdout.strip():
            print("  symbols (tools/build/sym.py):")
            print("\n".join("    " + l for l in r.stdout.splitlines()))
    for src, para in cites.get(ival, []):
        print(f"  ({src}) {' '.join(para.split())}")
    if ival not in cites:
        print("  no doc cites this address")

    nearby = sorted((abs(a - ival), a) for a in cites if a != ival
                    and abs(a - ival) <= NEARBY_WINDOW)[:NEARBY_MAX]
    if nearby:
        print(f"\n  nearby cited addresses (within 0x{NEARBY_WINDOW:x}):")
        for dist, a in nearby:
            src, para = cites[a][0]
            sign = "+" if a >= ival else "-"
            print(f"    0x{a:08x}  ({sign}0x{dist:x})  {src}: "
                  f"{' '.join(para.split())[:70]}...")

    disasm = ROOT / "scripts" / "disasm.sh"
    raw = ROOT / "out" / "raw" / "section_3_MAIN_OS.bin"
    if disasm.is_file() and raw.is_file() and ival >= 0x40000400:
        print(f"\n  -- scripts/disasm.sh emac 0x{ival:08x} {args.bytes} --")
        r = subprocess.run(["bash", str(disasm), "emac", f"0x{ival:08x}", str(args.bytes)],
                           cwd=ROOT, capture_output=True, text=True)
        print((r.stdout or r.stderr).rstrip())
    else:
        print("\n  (no out/raw/section_3_MAIN_OS.bin: `make os` then `make recon` "
              "for the disassembly window)")


if __name__ == "__main__":
    main()
