#!/usr/bin/env python3
"""Reachability sweep of a DSP payload's P space.

Disassemble every P module at its load address, then walk control flow from the
real entry points (both dispatch tables, the interrupt vectors, the bootstraps).
Whatever is never reached is either code whose caller we have not found, or
genuinely dead space.

Written to answer two questions at once: where the stock DELAY lives, and
whether there is a pool of unused program memory to reclaim. Answer to the
second: no. Payload A is 95.8% reached, B is 98.5%, and every unreached run is
small and inside a module that is otherwise reached.

READ THE LIMITS BEFORE TRUSTING A RESULT (DSP.md §5):
  * The DSP SELF-MODIFIES -- frame setup writes `move x0,p:>$58c`. Static
    reachability cannot follow a path the program writes for itself, so this
    bounds how much UNREFERENCED code exists; it does not prove that all
    behaviour is accounted for.
  * Computed jumps are not followed either. Unreached does not mean dead --
    it means "no caller found by this method".

Usage:  python3 tools/dsp_reach.py
"""
import re, subprocess, sys, pathlib, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import dsp_modmap as dm

SP = pathlib.Path(tempfile.mkdtemp(prefix='dspreach'))
ROOT = pathlib.Path(__file__).resolve().parent.parent
D = str(ROOT / 'vendor/dsp56300/build/source/disassemble/dsp56kDisassemble')
XTAB = {"A": 0x400e2345, "B": 0x400f5a10}

UNCOND = re.compile(r'^(jmp|bra|rts|rti|stop)\b', re.I)
CALLISH = re.compile(r'^(jsr|bsr|j[a-z]{2}|b[a-z]{2}|do|rep)\b', re.I)
TARGET = re.compile(r'func_([0-9a-f]+)|>\$([0-9a-f]+)|\$([0-9a-f]+)')


def disasm_all(tag):
    base = dm.IMG.read_bytes()
    va, ln = [(va, ln) for t, va, ln in dm.PAYLOADS if t == tag][0]
    mods, b = dm.modules(base, va, ln)
    insns, mod_of = {}, {}
    for sp, a, cnt, off in mods:
        if sp != 0:
            continue
        blob = b[off:off + cnt * 3]
        (SP / '_r.bin').write_bytes(blob)
        r = subprocess.run([D, '-in', str(SP / '_r.bin'), '-pc', f'{a:x}', 'le'],
                           capture_output=True, text=True)
        for line in r.stdout.split("\n"):
            m = re.match(r'^([0-9a-f]{6}):\s+(.*?)\s*;', line)
            if not m:
                continue
            ad = int(m.group(1), 16)
            insns[ad] = m.group(2).strip()
        for w in range(cnt):
            mod_of[a + w] = (a, cnt)
    # instruction lengths from the address sequence within each module
    order = sorted(insns)
    nxt = {}
    for i, ad in enumerate(order):
        nxt[ad] = order[i + 1] if i + 1 < len(order) else None
    return insns, nxt, mod_of, mods


def sweep(tag):
    insns, nxt, mod_of, mods = disasm_all(tag)
    base = dm.IMG.read_bytes()

    def rdw(a):
        i = a - dm.BASE
        return base[i] | (base[i + 1] << 8) | (base[i + 2] << 16)

    seeds = set()
    for i in range(32):                      # both dispatch tables, all ids
        for t in (0, 1):
            v = rdw(XTAB[tag] + (t * 32 + i) * 3)
            if v in insns:
                seeds.add(v)
    for a in range(0x00, 0x40):              # interrupt / reset vectors
        if a in insns:
            seeds.add(a)
    for a in (0x30000, 0x38000):             # bootstraps
        if a in insns:
            seeds.add(a)

    seen, work = set(), list(seeds)
    while work:
        ad = work.pop()
        if ad in seen or ad not in insns:
            continue
        seen.add(ad)
        t = insns[ad]
        for m in TARGET.finditer(t):
            v = m.group(1) or m.group(2) or m.group(3)
            try:
                tgt = int(v, 16)
            except ValueError:
                continue
            if tgt in insns and (CALLISH.match(t) or UNCOND.match(t)):
                work.append(tgt)
        if not UNCOND.match(t) and nxt.get(ad) is not None:
            work.append(nxt[ad])

    # report unreached runs, grouped by module
    print(f"=== payload {tag}: {len(insns)} instructions, {len(seen)} reached "
          f"({100.0*len(seen)/len(insns):.1f}%) ===")
    unreached = sorted(set(insns) - seen)
    runs, cur = [], []
    for ad in unreached:
        if cur and ad == nxt.get(cur[-1]):
            cur.append(ad)
        else:
            if cur:
                runs.append(cur)
            cur = [ad]
    if cur:
        runs.append(cur)
    big = [r for r in runs if len(r) >= 15]
    print(f"  unreached instructions: {len(unreached)}  in {len(runs)} runs, "
          f"{len(big)} of them >= 15 instructions")
    for r in sorted(big, key=len, reverse=True)[:15]:
        a, c = mod_of.get(r[0], (0, 0))
        print(f"    0x{r[0]:05x}..0x{r[-1]:05x}  {len(r):5} instrs   "
              f"(module 0x{a:05x}, {c} words)")


for tag in ("A", "B"):
    sweep(tag)
