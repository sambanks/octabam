#!/usr/bin/env python3
"""Where the ColdFire's time goes, and what a routine costs: the port's counts by module, priced in V4 core cycles.

    python3 tools/build/cf_scan.py profile LEVELS [--platform DIR] [--build-log LOG] [--frames N] [--json OUT] [--top N]
    python3 tools/build/cf_scan.py price COVERAGE SYMBOL [--platform DIR] [--frames N] [--detail]
    python3 tools/build/cf_scan.py c07 [PATH ...]
    python3 tools/build/cf_scan.py --selftest

`profile` attributes the port's OT_PROFILE_LEVELS file ("addr mask count" per line: every instruction from the
transport start with `--coverage`, or every 64th with `--profile`, each under the SR interrupt mask it ran at) to the
build's runtime units (out/platform/runtime/runtime.map and layout.json) and, with `--build-log`, to the ROM caves
`make bus` reports ("KEY cave: N bytes at 0x..."). Every other address is "stock"; the frame interrupt's own routine
(vector 0x41, 0x4000aad0..0x4000d9b0) is "stock: frame ISR". Counts are instructions.

`price` prices one runtime routine's executed instructions (a `--coverage` file) in core cycles: each instruction's
time from MCF54455RM Tables 3-13..3-20 (tools/build/cf_timing.py) for its mnemonic and addressing modes, times its
count, plus two stalls between neighbours: a register written and used as the next instruction's base or index (2
cycles, 3 for an index scaled 2 or 4; section 3.3.5.1), and an accumulator store k instructions after a MAC (3 - k;
the note under Table 3-18). Memory is zero-wait and every branch is predicted. The address-use stall is charged for
every register write, though the manual's address ALU forwards some heavily used opcodes with no stall (it does not
say which), so that part can count high. docs/contributing/CF_SCAN.md says what the figures are good for.

`c07` finds checklist row C07 (docs/contributing/CF_SCAN.md): a zero or sign extension written as two instructions
where `mvz`/`mvs` is one, and says whether the swap keeps every flag the code reads.

The platform must be the one built with the image the port ran (out/platform after `make bus`, or a saved copy):
the symbols and ranges are that build's.
"""
import bisect
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/build"))
import cf_timing as T  # noqa: E402

FRAME_ISR = (0x4000aad0, 0x4000d9b0)
OBJDUMP_MACHINE = "m68k:cfv4e"            # decodes EMAC; the forms are the same as cf_forms.machine()'s
CAVE = re.compile(r"^\s+([A-Z0-9_ ]+?)(?: cave)?: (\d[\d,]*) bytes at (0x[0-9a-f]+)")


# ---------------------------------------------------------------- profile ---------------------------------------

def unit_ranges(platform, build_log=None):
    """[(lo, hi, owner, unit)] sorted: the runtime units from the map, owned by their module key (layout.json), and
    the caves `make bus` printed (unit 'cave')."""
    units = json.loads((platform / "layout.json").read_text())["units"]
    owner = {u[1]: u[0] for u in units}
    ranges = []
    for line in (platform / "runtime/runtime.map").read_text(errors="replace").splitlines():
        f = line.rstrip().split(None, 3)
        if len(f) == 4 and f[0].startswith(".") and f[3].endswith(".o"):
            m = re.match(r"(\d+)_(.+)\.o$", pathlib.Path(f[3]).name)
            lo, size = int(f[1], 16), int(f[2], 16)
            if m and size:
                ranges.append((lo, lo + size, owner.get(m.group(2), m.group(2)), m.group(2)))
    if build_log:
        for line in pathlib.Path(build_log).read_text(errors="replace").splitlines():
            m = CAVE.match(line)
            if m:
                lo = int(m.group(3), 16)
                ranges.append((lo, lo + int(m.group(2).replace(",", "")), m.group(1).strip(), "cave"))
    return sorted(ranges)


def owner_of(ranges, starts, pc):
    i = bisect.bisect_right(starts, pc) - 1
    if i >= 0 and ranges[i][0] <= pc < ranges[i][1]:
        return ranges[i][2], ranges[i][3]
    if FRAME_ISR[0] <= pc < FRAME_ISR[1]:
        return "stock: frame ISR", None
    return "stock", None


def text_symbols(elf):
    out = subprocess.run(["m68k-elf-nm", "-n", "--defined-only", str(elf)], capture_output=True, text=True).stdout
    return [(int(f[0], 16), f[2]) for f in (l.split() for l in out.splitlines())
            if len(f) == 3 and f[1] in "Tt" and not f[2].startswith(".L")]


def attribute(levels_lines, ranges, syms, top=8):
    """{"total", "owners": {owner: {samples, share, by_mask, hottest: [(symbol, n)]}}} from "addr mask count" lines."""
    starts = [r[0] for r in ranges]
    sym_addr = [s[0] for s in syms]
    agg, total = {}, 0
    for line in levels_lines:
        f = line.split()
        if len(f) != 3:
            continue
        pc, mask, n = int(f[0], 16), int(f[1]), int(f[2])
        total += n
        own, unit = owner_of(ranges, starts, pc)
        a = agg.setdefault(own, {"samples": 0, "by_mask": {}, "syms": {}})
        a["samples"] += n
        a["by_mask"][mask] = a["by_mask"].get(mask, 0) + n
        if unit not in (None, "cave"):
            i = bisect.bisect_right(sym_addr, pc) - 1
            s = syms[i][1] if i >= 0 else f"{pc:#x}"
            a["syms"][s] = a["syms"].get(s, 0) + n
    owners = {}
    for own, a in sorted(agg.items(), key=lambda kv: -kv[1]["samples"]):
        owners[own] = {"samples": a["samples"], "share": a["samples"] / total if total else 0.0,
                       "by_mask": dict(sorted(a["by_mask"].items())),
                       "hottest": sorted(a["syms"].items(), key=lambda kv: -kv[1])[:top]}
    return {"total": total, "owners": owners}


def cmd_profile(a):
    platform = pathlib.Path(opt(a, "--platform", "out/platform"))
    rep = attribute(pathlib.Path(a[0]).read_text().splitlines(), unit_ranges(platform, opt(a, "--build-log")),
                    text_symbols(platform / "runtime/runtime.elf"), int(opt(a, "--top", "8")))
    frames = int(opt(a, "--frames", "0"))
    if opt(a, "--json"):
        pathlib.Path(opt(a, "--json")).write_text(json.dumps(rep, indent=1))
    print(f"{rep['total']:,} instructions" + (f", {rep['total'] / frames:,.0f} a frame" if frames else ""))
    for own, r in list(rep["owners"].items())[:40]:
        per = f"{r['samples'] / frames:9,.0f}/frame" if frames else ""
        masks = " ".join(f"m{k}:{v:,}" for k, v in r["by_mask"].items())
        print(f"  {own:28} {r['share'] * 100:6.2f} %  {r['samples']:>13,} {per}  {masks}")
        for s, n in r["hottest"][:3]:
            print(f"      {s:40} {n:>12,}" + (f"  {n / frames:9,.1f}/frame" if frames else ""))
    return 0


# ---------------------------------------------------------------- price -----------------------------------------

EA_IDX = {k: i for i, k in enumerate(T.EA)}
REG = r"%(?:d[0-7]|a[0-7]|sp|fp)"


def reg_name(r):
    return {"%sp": "%a7", "%fp": "%a6"}.get(r, r)


def split_ops(s):
    out, depth, cur = [], 0, ""
    for ch in s:
        depth += (ch == "(") - (ch == ")")
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return [o.strip() for o in out]


def ea_kind(op):
    """An MIT-syntax operand -> (EA column, base register, index register, scale)."""
    op = op.strip()
    if re.fullmatch(REG, op):
        return "Rn", None, None, 1
    if op.startswith("#"):
        return "#xxx", None, None, 1
    m = re.fullmatch(r"(%(?:a[0-7]|sp|fp|pc))@(\+|-)?(?:\((-?(?:0x)?[0-9a-fA-F]+)?(?:,(" + REG +
                     r"):[wl](?::([124]))?)?\))?", op)
    if m:
        base, inc, disp, idx, sf = m.groups()
        base = None if base == "%pc" else reg_name(base)
        if inc == "+":
            return "(An)+", base, None, 1
        if inc == "-":
            return "-(An)", base, None, 1
        if idx:
            return "(d8,An,Xi*SF)", base, reg_name(idx), int(sf or 1)
        return ("(d16,An)" if disp is not None else "(An)"), base, None, 1
    return "xxx.wl", None, None, 1


def _cell(row, col, default):
    v = row[EA_IDX[col]] if row is not None else None
    return v[0] if v else default


BCC = r"b(hi|ls|cc|cs|ne|eq|vc|vs|pl|mi|ge|lt|gt|le)[sw]?"


def price(mn, ops):
    """(cycles, kind) of one objdump instruction. kind: "mac", "acc" (an accumulator store), "" or "unpriced"."""
    o = split_ops(ops) if ops else []
    k = [ea_kind(x)[0] for x in o]
    if mn in ("moveq", "mov3ql"):
        return 1, ""
    if mn in ("movel", "moveb", "movew", "moveal", "moveaw") and len(o) == 2:
        if "%acc" in o[0]:
            return 1, "acc"
        if o[1] == "%macsr":
            return 8, ""
        if o[1] == "%mask":
            return 7, ""
        if "%acc" in o[1] or o[0] in ("%macsr", "%mask"):
            return 1, ""
        if "%sr" in o or "%ccr" in o:
            return (4 if o[1] == "%sr" else 1), ""
        src = {"Rn": "Dy", "(An)": "(Ay)", "(An)+": "(Ay)+", "-(An)": "-(Ay)", "(d16,An)": "(d16,Ay)",
               "(d8,An,Xi*SF)": "(d8,Ay,Xi*SF)", "xxx.wl": "xxx.l", "#xxx": "#xxx"}[k[0]]
        col = {"Rn": 0, "(An)": 1, "(An)+": 2, "-(An)": 3, "(d16,An)": 4, "(d8,An,Xi*SF)": 5, "xxx.wl": 6}[k[1]]
        v = (T.MOVE_L if mn.endswith("l") else T.MOVE_BW)[src][col]
        return (v[0], "") if v else (2, "unpriced")
    if mn.startswith("movclr"):
        return 1, "acc"
    if mn in ("mvzb", "mvzw", "mvsb", "mvsw"):
        return _cell(T.MISC[("mvz", "<ea>,Dx")], k[0], 1), ""
    if mn == "lea":
        return _cell(T.TWO_OPERAND[("lea", "<ea>,Ax")], k[0], 1), ""
    if mn == "pea":
        return _cell(T.MISC[("pea", "<ea>")], k[0], 1), ""
    if re.fullmatch(r"(clr|tst)[bwl]", mn):
        return _cell(T.ONE_OPERAND[mn[:3] + "." + mn[3]], k[0], 1), ""
    if re.fullmatch(r"(neg|negx|not|extb|ext|swap|byterev|bitrev|ff1|sats)[wl]?|s(eq|ne|cc|cs|pl|mi|hi|ls|ge|lt|gt|le|t|f|vc|vs)", mn):
        return 1, ""
    if re.fullmatch(r"(add|sub|and|or|cmp|eor)[bwl]|(adda|suba|cmpa)[wl]", mn):
        if len(k) == 2 and k[1] != "Rn":                       # Dy,<ea>: the destination is memory
            return _cell(T.TWO_OPERAND[("add.l", "Dy,<ea>")], k[1], 1), ""
        return _cell(T.TWO_OPERAND[("add.l", "<ea>,Rx")], k[0], 1), ""
    if re.fullmatch(r"(addi|subi|andi|ori|eori|cmpi)[bwl]|(asl|asr|lsl|lsr)[bwl]", mn):
        return 1, ""
    if re.fullmatch(r"(addq|subq)[bwl]", mn):
        return _cell(T._Q_EA, k[1], 1), ""
    if mn in ("btst", "bset", "bclr", "bchg"):
        return _cell(T.TWO_OPERAND[(mn, "#imm,<ea>" if k[0] == "#xxx" else "Dy,<ea>")], k[1], 2), ""
    if mn in ("mulsl", "mulul", "mulsw", "muluw"):
        return _cell(T.EMAC[(mn[:4] + "." + mn[4], "<ea>y,Dx")], k[0], 4), ""
    if re.fullmatch(r"(divs|divu|rems|remu)[wl]", mn):
        return _cell(T.TWO_OPERAND[(mn[:4] + "." + mn[4], "<ea>,Dx")], k[0], 35), ""
    if re.fullmatch(r"(mac|msac)[wl]", mn):
        return 1, "mac"
    if mn == "moveml":
        n = 0
        for grp in re.findall(r"%[ad]\d(?:-%[ad]\d)?", ops):
            lo, _, hi = grp.partition("-")
            n += (int(hi[2]) - int(lo[2]) + 1) if hi else 1
        return max(n, 1), ""
    if mn == "nop":
        return 6, ""
    if mn.startswith("tpf"):
        return 1, ""
    if mn == "rts":
        return T.RTS["predicted"][0], ""
    if mn == "rte":
        return 15, ""
    if mn in ("jsr", "jmp"):
        return (1 if k[0] == "xxx.wl" else 6 if k[0] == "(d8,An,Xi*SF)" else 5), ""
    if re.fullmatch(r"(bra|bsr)[sw]?|" + BCC, mn):
        return 1, ""
    if mn == "cpushl":
        return 12, ""
    return 1, "unpriced"


def written(mn, ops):
    """The register an instruction writes, as far as the address-use stall cares (a data or address register)."""
    o = split_ops(ops) if ops else []
    if not o or re.fullmatch(r"(cmp|cmpa|cmpi|tst|btst)[bwl]?|" + BCC + r"|(bra|bsr)[sw]?|jsr|jmp|rts", mn):
        return None
    return reg_name(o[-1]) if re.fullmatch(REG, o[-1]) else None


def address_uses(ops):
    """[(register, scale)] an instruction uses as a base or index. A (An)+ or -(An) base counts: the manual's NOTE
    frees only the increment's own result, which written() never reports."""
    out = []
    for x in split_ops(ops) if ops else []:
        kind, base, idx, sf = ea_kind(x)
        if kind in ("(An)", "(An)+", "-(An)", "(d16,An)", "(d8,An,Xi*SF)") and base:
            out.append((base, 1))
        if idx:
            out.append((idx, sf))
    return out


def model(rows, counts):
    """rows [(pc, mnemonic, operands)] in address order -> [(pc, mn, ops, count, cycles, stall, kind)]."""
    out, last_mac = [], None
    for i, (pc, mn, ops) in enumerate(rows):
        c, kind = price(mn, ops)
        stall = 0
        if i:
            w = written(rows[i - 1][1], rows[i - 1][2])
            for r, sf in address_uses(ops):
                if r == w:
                    stall = max(stall, T.STALL_INDEX_SF24 if sf in (2, 4) else T.STALL_BASE_OR_INDEX_SF1)
        if kind == "acc" and last_mac is not None and i - last_mac - 1 < 3:
            stall += 3 - (i - last_mac - 1)
        if kind == "mac":
            last_mac = i
        out.append((pc, mn, ops, counts.get(pc, 0), c, stall, kind))
    return out


def disassemble(elf, sym):
    syms = text_symbols(elf)
    start = next((a for a, n in syms if n == sym), None)
    if start is None:
        raise SystemExit(f"cf_scan price: {sym} is not a text symbol of {elf}")
    stop = min((a for a, n in syms if a > start), default=start + 4096)
    dis = subprocess.run(["m68k-elf-objdump", "-d", "-m", OBJDUMP_MACHINE, f"--start-address={start:#x}",
                          f"--stop-address={stop:#x}", str(elf)], capture_output=True, text=True).stdout
    rows = []
    for line in dis.splitlines():
        m = re.match(r"\s*([0-9a-f]+):\s+(?:[0-9a-f]{4} )+\s*(\S+)\s*(.*)$", line)
        if m:
            rows.append((int(m.group(1), 16), m.group(2), re.sub(r"\s*<[^>]*>", "", m.group(3)).strip()))
    return rows


def cmd_price(a):
    platform = pathlib.Path(opt(a, "--platform", "out/platform"))
    counts = {}
    for line in pathlib.Path(a[0]).read_text().splitlines():
        f = line.split()
        if len(f) == 2:
            counts[int(f[0], 16)] = int(f[1])
    res = model(disassemble(platform / "runtime/runtime.elf", a[1]), counts)
    frames = int(opt(a, "--frames", "0"))
    if "--detail" in a:
        for pc, mn, ops, n, c, s, kind in res:
            if n:
                print(f"{n:>11,} {c:>3}{'+' + str(s) if s else '  '}  {pc:08x}  {mn} {ops}{'  (unpriced)' if kind == 'unpriced' else ''}")
    n = sum(r[3] for r in res)
    base = sum(r[3] * r[4] for r in res)
    stall = sum(r[3] * r[5] for r in res)
    per = (lambda x: f" ({x / frames:,.1f} a frame)") if frames else (lambda x: "")
    print(f"{a[1]}: {n:,} instructions{per(n)}, {base + stall:,} cycles{per(base + stall)}: "
          f"{base:,} from the tables, {stall:,} stalls; CPI {(base + stall) / n if n else 0:.2f}")
    unpriced = sorted({r[1] for r in res if r[6] == "unpriced" and r[3]})
    if unpriced:
        print("  unpriced, charged 1 cycle:", ", ".join(unpriced))
    return 0


# ---------------------------------------------------------------- c07 -------------------------------------------

SETS_FLAGS = (r"(cmp|cmpi|tst|btst|add|addi|addq|sub|subi|subq|and|andi|or|ori|eor|eori|move|moveq|mvz|mvs|lsl|lsr|"
              r"asl|asr|clr|neg|not|swap|ext|extb|mulu|muls|divu|divs|bset|bclr|bchg)(\.[bwl])?")
NEUTRAL = r"(lea|movea|pea|adda|suba|tpf)(\.[bwl])?"
Z_ONLY = r"[bj](eq|ne|hi|ls|cc|cs)(\.?[bswl])?|s(eq|ne|hi|ls|cc|cs)"


def parse_line(line):
    """(label or None, mnemonic or None, operands) of one source line, MIT or Motorola syntax, sizes as `.b`."""
    s = line.split("|")[0].strip()
    lab = None
    m = re.match(r"^([A-Za-z_.$0-9]+):\s*(.*)$", s)
    if m:
        lab, s = m.group(1), m.group(2)
    if not s or s.startswith("."):
        return lab, None, ""
    p = s.split(None, 1)
    mn = re.sub(r"^(move|add|sub|and|or|cmp|tst|clr|ext|extb|mvz|mvs|moveq|addq|subq|addi|subi|andi|ori|cmpi|eor|"
                r"eori|lsl|lsr|asl|asr|neg|not|movea|adda|suba|cmpa|btst|bset|bclr|mulu|muls)([bwl])$", r"\1.\2",
                p[0].lower())
    return lab, mn, (p[1].replace(" ", "") if len(p) > 1 else "")


def c07_sites(text):
    """[(line, shape, verdict, first, second)]: Z1 moveq #0|clr.l Dn + move.b|w <ea>,Dn; Z2 move.b|w <ea>,Dn +
    and.l #0xff|#0xffff,Dn; S1 move.b + extb.l; S2 move.w + ext.l. Only Z1 changes a flag (move sets N from the byte
    or word, mvz clears it), so a Z1 site is SAFE when the next instruction that touches the flags sets them itself or
    reads only Z and C; REVIEW when a label, a call or an N-reading branch comes first."""
    rows = [parse_line(l) for l in text.splitlines()]
    sites = []
    for i in range(len(rows) - 1):
        _, a, ao = rows[i]
        lab1, b, bo = rows[i + 1]
        if not a or not b or lab1:
            continue
        dst = ao.rsplit(",", 1)[-1]
        shape = None
        if (a == "moveq" and ao == f"#0,{dst}" or a == "clr.l" and ao == dst) and re.fullmatch(r"%d[0-7]", dst) \
                and b in ("move.b", "move.w") and bo.rsplit(",", 1)[-1] == dst:
            shape = "Z1"
        elif a in ("move.b", "move.w") and re.fullmatch(r"%d[0-7]", dst) and b in ("and.l", "andi.l") and \
                bo.lower() in (f"#0xff,{dst}", f"#255,{dst}", f"#0xffff,{dst}", f"#65535,{dst}"):
            shape = "Z2"
        elif a == "move.b" and b == "extb.l" and bo == dst:
            shape = "S1"
        elif a == "move.w" and b == "ext.l" and bo == dst:
            shape = "S2"
        if not shape:
            continue
        verdict = "SAFE" if shape != "Z1" else "REVIEW"
        for lab, c, _ in rows[i + 2:] if shape == "Z1" else ():
            if lab:
                break
            if c is None:
                continue
            if re.fullmatch(NEUTRAL, c):
                continue
            if re.fullmatch(SETS_FLAGS, c) and not c.startswith("movea") or re.fullmatch(Z_ONLY, c):
                verdict = "SAFE"
            break
        sites.append((i + 1, shape, verdict, f"{a} {ao}", f"{b} {bo}"))
    return sites


def cmd_c07(a):
    paths = [pathlib.Path(p) for p in (a or ["modules"])]
    files = sorted(f for p in paths for f in ([p] if p.is_file() else list(p.rglob("*.s")) + list(p.rglob("*.inc"))))
    total = safe = 0
    for f in files:
        for ln, shape, verdict, first, second in c07_sites(f.read_text(errors="replace")):
            total += 1
            safe += verdict == "SAFE"
            print(f"{f}:{ln}: {shape} {verdict:6} {first} / {second}")
    print(f"{total} site(s), {safe} SAFE")
    return 0


# ---------------------------------------------------------------- main ------------------------------------------

def opt(a, name, default=None):
    return a[a.index(name) + 1] if name in a else default


def selftest():
    """The manual's own figures for a short sequence, the two stalls, and the C07 shapes."""
    seq = [(0, "moveq", "#1,%d0"), (2, "movel", "%a0@+,%d1"), (4, "addl", "%d1,%d0"), (6, "bnes", "0x0"),
           (8, "jsr", "0x40001000"), (14, "lea", "%a0@(4),%a1"), (18, "movel", "%a1@,%d2"),
           (20, "macl", "%d0,%d1,%acc0"), (22, "movclrl", "%acc0,%d3"), (24, "movel", "%d2,%a0@(0,%d0:l:4)")]
    got = {r[0]: (r[4], r[5]) for r in model(seq, {pc: 1 for pc, _, _ in seq})}
    want = {0: (1, 0), 2: (1, 0), 4: (1, 0), 6: (1, 0), 8: (1, 0), 14: (1, 0), 18: (1, 2), 20: (1, 0), 22: (1, 3),
            24: (2, 0)}
    bad = {pc: (got[pc], want[pc]) for pc in want if got[pc] != want[pc]}
    src = "\tmoveq #0,%d0\n\tmove.b (%a0),%d0\n\tbmi 1f\n\tmoveq #0,%d1\n\tmove.b (%a1),%d1\n\tbeq 1f\n"
    shapes = [(s[1], s[2]) for s in c07_sites(src)]
    if shapes != [("Z1", "REVIEW"), ("Z1", "SAFE")]:
        bad["c07"] = shapes
    print("cf_scan selftest:", "PASS" if not bad else f"FAIL {bad}")
    return 0 if not bad else 1


def main(argv):
    if argv[:1] == ["--selftest"]:
        return selftest()
    if len(argv) < 1 or argv[0] not in ("profile", "price", "c07"):
        print(__doc__)
        return 2
    return {"profile": cmd_profile, "price": cmd_price, "c07": cmd_c07}[argv[0]](argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
