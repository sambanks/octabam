#!/usr/bin/env python3
"""Pipeline stalls on the path a DSP module's proc actually executes.

The DSP56300 core inserts idle cycles for some instruction sequences
(DSP56300 Family Manual, Rev 5: section A.2 and section 3.5), and its
instructions do not all take one cycle (Table A-1). tools/build/cycle_count.py
counts words and dsp_host's -meter counts instructions; neither sees either.
This tool runs a module's proc under dsp_host, records the executed
instruction sequence of one steady block per setting, and prices it:

  cycles   Table A-1's T for the form, plus its +pru / +lab / +lim terms
  stalls   the sequence delays of A.2 and 3.5 that apply to code in
           internal memory (no external bus, no stack extension)

It is a model from the manual, not a measurement. Not counted: wait states
(a fetch from the shared window takes one more, DSP56720RM 16.2), memory
contention, interrupts. See "Readings" below for the calls the manual
leaves open.

usage:
  python3 tools/build/interlock_scan.py MODULE [NAME=VALUE ...] [--top N] [--dump]
  python3 tools/build/interlock_scan.py --selftest

NAME=VALUE sets a knob; a MODE given by its label (MODE=JUNO) starts from
that mode's view defaults. With no MODE, every mode of the module is run.
Run it from the root of a built tree (vendor/, out/raw/). The audition's
scratch dump (out/dsp/_audition_<module>_A.mem) is built when it is missing
or older than modules/. The trace needs a dsp_host with -steptrace (make
setup builds it from this tree); ILSCAN_HOST overrides the one it runs, for
example a branch's dsp_host built in an isolated tree
(docs/contributing/TOOLING.md section 1).

Readings (each kind is reported on its own, so a different reading can be
subtracted):
  agu-lua    A.2.4 counts a register written "in its move portion"; LUA has
             no move portion. Its destination is counted as such a write.
  arith-tcc  3.5.1 counts a "data ALU instruction". A Tcc writing an
             accumulator is counted as one.
  Several stalls on one instruction are combined as their maximum: the idle
  cycles inserted for one let the other's producer finish.
  The A.2.4 distance runs from the END of the writing instruction.
"""
import os
import pathlib
import re
import struct
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools")); import toolpath  # noqa: E402,F401
HOST = pathlib.Path(os.environ.get("ILSCAN_HOST", ROOT / "vendor/dsp56300/build/source/dsp_host/dsp_host"))
DIS = ROOT / "vendor/dsp56300/build/source/disassemble/dsp56kDisassemble"
ASM = ROOT / "vendor/dsp56300/build/source/dsp_host/dsp_asm"
LINE = re.compile(r"^([0-9a-f]{5,6}):\s+(.*?)\s*;\s*([0-9a-f]{6})(?:\s+([0-9a-f]{6}))?\s*$")
TRACE = re.compile(r"^\s+inst 0\s+(\d+)\s+pc=([0-9a-f]{6})")
FRAMES = 16          # the unit's block (docs/firmware/DSP.md); the gates run 15

KINDS = ("agu", "agu-lua", "agu-tcc", "arith", "arith-tcc", "transfer", "logic-ext", "status", "tcc-r")

# ---- the instruction model ---------------------------------------------------

CONDS = {"cc", "hs", "cs", "lo", "ec", "eq", "es", "ge", "gt", "lc", "le", "ls", "lt",
         "mi", "ne", "nr", "pl", "nn"}
ACC = {"a": "a", "a0": "a", "a1": "a", "a2": "a", "a10": "a",
       "b": "b", "b0": "b", "b1": "b", "b2": "b", "b10": "b"}
EXT_LSP = {"a0", "a2", "b0", "b2"}
LOGIC = {"and", "or", "eor", "not", "lsl", "lsr", "rol", "ror"}
NO_DEST = {"cmp", "cmpm", "cmpu", "tst"}
SR_NAMES = {"sr", "mr", "ccr"}
AGU = re.compile(r"^([rnm])([0-7])$")
MEM = re.compile(r"^([xylp]):(.+)$")


def _accs(reg):
    if reg in ("ab", "ba"):
        return {"a", "b"}
    return {ACC[reg]} if reg in ACC else set()


class Ins:
    """One executed instruction, classified for Table A-1 and A.2 / 3.5."""
    __slots__ = ("pc", "text", "nwords", "mnem", "cyc", "alu_dst", "is_tcc", "is_dalu",
                 "mv_src_acc", "mv_dst_acc", "mv_dst_regs", "agu_use", "agu_dst",
                 "r_src", "sr_read", "cond", "lua", "taken")

    def __init__(self, pc, text, nwords):
        self.pc, self.text, self.nwords = pc, text, nwords
        self.taken = None            # a conditional branch's outcome, from the trace
        tok = text.split()
        self.mnem = m = tok[0] if tok else "nop"
        fields = tok[1:]
        self.alu_dst = None
        self.is_tcc = m[0] == "t" and m[1:] in CONDS
        self.mv_src_acc, self.mv_dst_acc, self.mv_dst_regs = set(), set(), set()
        self.agu_use, self.agu_dst = set(), {}
        self.r_src = False
        self.sr_read = None
        self.cond = (m[0] in "bj" and m[1:] in CONDS) or (m[:2] in ("bs", "js") and m[2:] in CONDS)
        self.lua = m in ("lua", "lea")
        pru = disp = 0
        movem = False

        def mem_operand(op):
            nonlocal pru, disp, movem
            mm = MEM.match(op)
            if not mm:
                return False
            space, addr = mm.groups()
            if space == "p":
                movem = True
            r = re.search(r"\(r([0-7])", addr)
            if r:
                self.agu_use.add(int(r.group(1)))
            if re.search(r"\(r[0-7]\+n[0-7]\)", addr) or addr.startswith("-("):
                pru += 1
            if re.search(r"\(r[0-7][+-]\$", addr):
                disp += 1
            return True

        def reg_read(op):
            self.mv_src_acc |= _accs(op)
            if AGU.match(op) and op[0] == "r":
                self.r_src = True
            if op in SR_NAMES:
                self.sr_read = "move"

        def reg_write(op, how="move"):
            self.mv_dst_acc |= _accs(op)
            self.mv_dst_regs.add(op)
            g = AGU.match(op)
            if g:
                self.agu_dst[int(g.group(2))] = how

        def move_field(f):
            parts = f.split(",")
            if len(parts) == 1:                     # U move: (r5)+n5
                r = re.search(r"\(r([0-7])", f)
                if r:
                    self.agu_use.add(int(r.group(1)))
                return
            src, dst = parts[0], parts[-1]
            if not mem_operand(src) and not src.startswith("#"):
                reg_read(src)
            if not mem_operand(dst):
                reg_write(dst)

        if m == "move" or m == "movec" or m == "movem" or m == "movep":
            for f in fields:
                move_field(f)
        elif self.lua:
            ea, dst = fields[0].split(",")
            r = re.search(r"\(r([0-7])", ea)
            if r:
                self.agu_use.add(int(r.group(1)))
            g = AGU.match(dst)
            if g:
                self.agu_dst[int(g.group(2))] = "lua"
        elif self.is_tcc:
            s1, d1 = fields[0].split(",")
            self.alu_dst = ACC.get(d1)
            if len(fields) > 1:                     # Tcc S1,D1 S2,D2: an address register transfer
                s2, d2 = fields[1].split(",")
                self.r_src = self.r_src or bool(AGU.match(s2))
                g = AGU.match(d2)
                if g:
                    self.agu_dst[int(g.group(2))] = "tcc"
        elif m in ("bset", "bclr", "bchg", "btst", "brset", "brclr", "bsset", "bsclr",
                   "jset", "jclr", "jsset", "jsclr"):
            ops = fields[0].split(",") if fields else []
            tgt = ops[1] if len(ops) > 1 else ""
            if tgt in SR_NAMES:
                self.sr_read = "bit"
            elif not mem_operand(tgt):
                self.mv_src_acc |= _accs(tgt)       # 3.5.1: a bit operation reads the accumulator
        elif m in ("do", "dor", "rep", "rts", "rti", "nop", "bsr", "bra", "jsr", "jmp",
                   "enddo", "brkcc") or self.cond:
            for f in fields:
                for op in f.split(","):
                    mem_operand(op)
        else:                                       # a data ALU instruction
            if fields:
                ops = fields[0].split(",")
                if m not in NO_DEST and ops[-1] in ACC and m not in ("norm",):
                    self.alu_dst = ACC[ops[-1]]
                elif m == "norm":
                    self.alu_dst = ACC.get(ops[-1])
            for f in fields[1:]:
                move_field(f)
        self.is_dalu = (self.alu_dst is not None or m in NO_DEST or self.is_tcc
                        or bool(self.mv_src_acc))

        # Table A-1
        if m in ("do", "dor", "rep"):
            c = 5
        elif m in ("rts", "rti", "jsr", "jmp"):
            c = 3 + (nwords - 1 if m in ("jsr", "jmp") else 0)
        elif m in ("bsr", "bra") or (self.cond and m[0] == "b"):
            c = 4 if nwords == 1 else 5
        elif self.cond:                              # Jcc, JScc
            c = 4
        elif m in ("brset", "brclr", "bsset", "bsclr", "jset", "jclr", "jsset", "jsclr"):
            c = 4 if m[0] == "j" else 5
        elif m in ("bset", "bclr", "bchg", "btst"):
            c = 2 + pru
        elif self.lua or m == "lra":
            c = 3
        elif movem or m == "movem":
            c = 6
        elif m == "movep":
            c = 2
        elif m in ("norm", "brkcc"):
            c = 5
        elif m in ("andi", "ori"):
            c = 3
        elif m in ("mpyi", "maci", "macri", "mpyri"):
            c = 2
        elif disp:
            c = 2 if nwords == 1 else 3
        else:
            c = 1 + (nwords - 1) + pru               # +lim / +lab for the second word; +pru
        self.cyc = c


def form_of(ins):
    """Why an instruction takes more than one cycle (Table A-1), or None."""
    m = ins.mnem
    if ins.cyc <= 1:
        return None
    if m in ("bsr", "jsr", "rts", "rti"):
        return "call/return"
    if m in ("bra", "jmp") or ins.cond:
        return "branch"
    if ins.lua:
        return "lua"
    if m in ("do", "dor", "rep"):
        return "do/rep"
    if ins.cyc == 6:
        return "movem"
    if re.search(r"\(r[0-7][+-]\$", ins.text):
        return "displaced move"
    if re.search(r"\(r[0-7]\+n[0-7]\)|-\(r", ins.text):
        return "(rn+nn) / -(rn)"
    if ins.nwords == 2:
        return "long immediate/absolute"
    return "other"


FORMS = ("call/return", "branch", "lua", "displaced move", "(rn+nn) / -(rn)",
         "long immediate/absolute", "do/rep", "movem", "other")


def analyze(seq):
    """seq: [Ins] in executed order, the conditional branches' outcome in .taken.
    -> (cycles, stalls {kind: cycles}, sites [(index, kind, n, index of the producer)])"""
    t = 0
    last_w = {}                     # AGU set -> (end cycle, how, index of the writer)
    stalls = Counter()
    sites = []
    for k, ins in enumerate(seq):
        prev = seq[k - 1] if k else None
        prev2 = seq[k - 2] if k > 1 else None
        cand = []                   # (kind, cycles, producer index)
        if prev is not None:
            if prev.alu_dst and prev.alu_dst in ins.mv_src_acc:
                cand.append(("arith-tcc" if prev.is_tcc else "arith", 1, k - 1))
            if prev.mv_dst_acc & ins.mv_src_acc:
                cand.append(("transfer", 1, k - 1))
            if prev.is_tcc and ins.r_src:
                cand.append(("tcc-r", 1, k - 1))
        if ins.mnem in LOGIC and ins.alu_dst and any(
                r in EXT_LSP and ACC[r] == ins.alu_dst for r in ins.mv_dst_regs):
            cand.append(("logic-ext", 1, k))
        if ins.sr_read:
            if prev is not None and prev.is_dalu:
                cand.append(("status", 2 if ins.sr_read == "move" else 1, k - 1))
            elif prev2 is not None and prev2.is_dalu:
                cand.append(("status", 1, k - 2))
        for s in ins.agu_use:
            if s in last_w:
                end, how, w = last_w[s]
                gap = t - end
                if gap < 3:
                    cand.append(({"move": "agu", "lua": "agu-lua", "tcc": "agu-tcc"}[how], 3 - gap, w))
        st = 0
        if cand:
            kind, st, w = max(cand, key=lambda c: c[1])
            stalls[kind] += st
            sites.append((k, kind, st, w))
        t += st + ins.cyc
        if ins.cond and ins.taken is False:
            t += 1                   # A.2.6.3: a false condition delays the next decode by one
        for s, how in ins.agu_dst.items():
            last_w[s] = (t, how, k)
    return t, stalls, sites


# ---- the manual's own examples ----------------------------------------------

def selftest():
    def run(lines):
        seq = [Ins(i, l, 1) for i, l in enumerate(lines)]
        _t, _s, sites = analyze(seq)
        return [(seq[k].text, kind, n) for k, kind, n, _w in sites]

    cases = [
        ("A-1: N0 written two cycles back... I5/I6 (Type0)",
         ["move #$1000,r0", "nop", "nop", "nop", "move #$10,n0", "move x:(r0)+,y1"],
         [("move x:(r0)+,y1", "agu", 3)]),
        ("Figure A-1 Type0", ["move #$1000,r0", "move x:(r0)+,y1"], [("move x:(r0)+,y1", "agu", 3)]),
        ("Figure A-1 Type1", ["move #$1000,r0", "clr a", "move x:(r0)+,y1"], [("move x:(r0)+,y1", "agu", 2)]),
        ("Figure A-1 Type2", ["move #$1000,r0", "clr a", "inc b", "move x:(r0)+,y1"],
         [("move x:(r0)+,y1", "agu", 1)]),
        ("A-2 as given", ["move #$1000,r0", "clr a", "move x:(r0)+,y1", "move x:(r0)+,y0"],
         [("move x:(r0)+,y1", "agu", 2)]),
        ("A-2 with I3 not using R0", ["move #$1000,r0", "clr a", "move x:(r1)+,y1", "move x:(r0)+,y0"],
         [("move x:(r0)+,y0", "agu", 1)]),
        ("3-11 mac then move a1", ["mac x0,y0,a", "move a1,x:(r0)+"], [("move a1,x:(r0)+", "arith", 1)]),
        ("3-11 tfr then bset", ["tfr a,b", "bset #3,b"], [("bset #3,b", "arith", 1)]),
        ("3-11 a useful instruction between", ["mac x0,y0,a", "mac x1,y1,b", "move a,x:(r0)+"], []),
        ("3-12 mac then move sr", ["mac x0,y0,a", "move sr,x:(r0)+"], [("move sr,x:(r0)+", "status", 2)]),
        ("3-12 accumulator read, nop, btst sr", ["move a,x:(r0)+", "nop", "btst #5,sr"],
         [("btst #5,sr", "status", 1)]),
        ("3-13 transfer stall", ["move y:(r1)+,a1", "move a2,x:(r0)+"], [("move a2,x:(r0)+", "transfer", 1)]),
        ("3-13 a useful instruction between", ["move y:(r1)+,a1", "mac x1,y1,b", "move a,x:(r0)+"], []),
        ("3-13 note: logic with an EXT/LSP write", ["or x1,a y1,a0"], [("or x1,a y1,a0", "logic-ext", 1)]),
        ("A.2.4 Tcc then an R source", ["tgt x0,a", "move r2,r5"], [("move r2,r5", "tcc-r", 1)]),
        ("post-update does not interlock", ["move x:(r0)+,x0", "move x:(r0)+,x1"], []),
        ("arithmetic result into arithmetic", ["add x0,a", "add a,b"], []),
    ]
    bad = 0
    for name, lines, want in cases:
        got = run(lines)
        ok = got == want
        bad += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {name}" + ("" if ok else f": got {got}, want {want}"))
    # Table A-1 forms the scan relies on (probe 57's four among them)
    forms = [("move x0,a", 1, 1), ("move x:(r0),a", 1, 1), ("move x:(r7+$15),a", 1, 2),
             ("move x:(r7+$70),a", 2, 3), ("move x:(r0+n0),x0", 1, 2), ("move #>$7f0000,x0", 2, 2),
             ("and #>$7f0000,a", 2, 2), ("lua (r7+$23),r3", 1, 3), ("move p:(r5),x0", 1, 6),
             ("bsr func_0015fa", 1, 4), ("rts", 1, 3), ("do n7,>$13de", 2, 5),
             ("mpy x0,y1,a x:(r3),x0", 1, 1), ("move (r5)+n5", 1, 1), ("tge x0,a", 1, 1)]
    for text, nw, want in forms:
        got = Ins(0, text, nw).cyc
        ok = got == want
        bad += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} Table A-1: {text} ({nw}w) = {got}" + ("" if ok else f", want {want}"))
    print("selftest:", "PASS" if not bad else f"{bad} FAILED")
    return bad == 0


# ---- the dump, the trace and the decode ---------------------------------------

def load_p(mem):
    """P words of a dsp_host .mem dump: {address: word}."""
    b = pathlib.Path(mem).read_bytes()
    p, i = {}, 0
    while i + 9 <= len(b):
        sp = b[i]
        addr, cnt = struct.unpack_from("<II", b, i + 1)
        i += 9
        if sp == 0xff:
            break
        if sp == 0:
            for k in range(cnt):
                p[addr + k] = struct.unpack_from("<I", b, i + 4 * k)[0] & 0xffffff
        i += 4 * cnt
    return p


def disassemble(p, lo, hi):
    """{address: (text, nwords)} for P[lo..hi], decoded from lo."""
    words = " ".join(f"{p.get(a, 0):06x}" for a in range(lo, hi + 2))
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(words)
    r = subprocess.run([str(DIS), "-in", f.name, "-pc", f"{lo:x}"], capture_output=True, text=True)
    pathlib.Path(f.name).unlink()
    out = {}
    for l in r.stdout.splitlines():
        m = LINE.match(l)
        if m:
            out[int(m.group(1), 16)] = (re.sub(r"\s+", " ", m.group(2).strip()), 2 if m.group(4) else 1)
    return out


def decode(p, pcs, lo):
    ins = disassemble(p, lo, max(pcs) + 2)
    # A traced PC is an instruction start by definition. A straight decode
    # that missed one (a table word in the code, or a decode out of step)
    # is corrected by decoding that PC on its own.
    for pc in sorted(set(pc for pc in pcs if pc not in ins)):
        if p.get(pc, 0) == 0:            # the disassembler prints no line for a nop (000000)
            ins[pc] = ("nop", 1)
            continue
        one = disassemble(p, pc, pc)
        if pc not in one:
            sys.exit(f"cannot decode the traced PC 0x{pc:x}")
        ins[pc] = one[pc]
    return ins


def trace(mem, init, proc, params, blocks=4):
    """PCs of the tracked instance's proc in block blocks-1 (a steady block)."""
    with tempfile.TemporaryDirectory(prefix="ilscan.") as d:
        d = pathlib.Path(d)
        n = FRAMES * blocks
        (d / "in.raw").write_bytes(b"".join(
            struct.pack("<i", int(0.3 * 8388607 * ((i * 37) % 200 - 100) / 100)) for i in range(2 * n)))
        cmd = [str(HOST), "-mem", str(mem), "-init", f"{init:x}", "-proc", f"{proc:x}",
               "-inst", "1", "-r7", "1", "-alloc", "0", "-inmask", "1", "-stereo",
               "-frames", str(FRAMES), "-blocks", str(blocks), "-diff", str(blocks),
               "-in", str(d / "in.raw"), "-out", str(d / "out.raw"),
               "-params", ",".join(str(x) for x in params),
               "-trace", "400000", "-trackinst", "0", "-steptrace"]
        r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"dsp_host failed ({HOST}; a host without -steptrace fails here too: set ILSCAN_HOST):\n"
                 f"{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    calls, cur = [], None
    for l in r.stdout.splitlines():
        m = TRACE.match(l)
        if not m:
            continue
        if int(m.group(1)) == 0:
            cur = []
            calls.append(cur)
        cur.append(int(m.group(2), 16))
    if not calls:
        sys.exit("dsp_host printed no trace")
    return calls[-1]


def labels_at(mod_name, base, p):
    """[(address, label)] of the module's source assembled at base, checked against the dump."""
    import cycle_count
    src = cycle_count.prep(mod_name)
    with tempfile.TemporaryDirectory(prefix="ilscan.") as d:
        d = pathlib.Path(d)
        (d / "s.asm").write_text(src)
        r = subprocess.run([str(ASM), "-in", str(d / "s.asm"), "-org", f"{base:x}",
                            "-out", str(d / "s.bin"), "-sym", str(d / "s.sym")], capture_output=True, text=True)
        if r.returncode:
            return [], 0.0
        b = (d / "s.bin").read_bytes()
        syms = [(int(v, 16), k) for k, v in (l.split() for l in (d / "s.sym").read_text().splitlines() if l.strip())]
    w = [b[i] | b[i + 1] << 8 | b[i + 2] << 16 for i in range(0, len(b) - len(b) % 3, 3)]
    same = sum(1 for i, x in enumerate(w) if p.get(base + i) == x) / max(1, len(w))
    return sorted(syms), same


def where(pc, syms):
    best = None
    for a, k in syms:
        if a <= pc:
            best = (a, k)
        else:
            break
    return f"{best[1]}+{pc - best[0]}" if best else f"P:{pc:x}"


# ---- settings -----------------------------------------------------------------

def settings_for(mod, args):
    """[(label, params)]: the knob vector of each run."""
    K = mod.knob_map()
    base = [(q.default or 0) for q in mod.params]
    over = {}
    for a in args:
        name, val = a.split("=", 1)
        name = name.upper()
        if name not in K:
            sys.exit(f"{mod.name} has no knob {name} ({', '.join(K)})")
        q = mod.params[K[name]]
        labels = [l.upper() for l in (q.labels or ())]
        over[name] = labels.index(val.upper()) if val.upper() in labels else int(val)
    runs = []
    modes = [over["MODE"]] if "MODE" in over else (
        list(range(mod.params[K["MODE"]].count)) if "MODE" in K else [None])
    for mv in modes:
        v = list(base)
        label = ""
        if mv is not None:
            view = mod.view_for(mv)
            for slot, val in (view.defaults.items() if view is not None else ()):
                v[K[mod.canon_name(slot)]] = val
            v[K["MODE"]] = mv
            q = mod.params[K["MODE"]]
            label = q.labels[mv] if q.labels else f"MODE={mv}"
        for name, val in over.items():
            if name != "MODE":
                v[K[name]] = val
        extra = " ".join(f"{n}={x}" for n, x in over.items() if n != "MODE")
        runs.append(((label + " " + extra).strip() or "defaults", v))
    return runs


# ---- the report -----------------------------------------------------------------

def scan(mod, mem, init, proc, params, p, syms):
    pcs = trace(mem, init, proc, params)
    ins = decode(p, pcs, min(min(pcs), init))
    # dsp_host ignores an option it does not know: a host without -steptrace
    # runs each DO loop inside one step, and the trace goes from the `do`
    # straight to the address after the loop (the disassembler prints that
    # address, LA + 1, as the `do`'s operand).
    for k in range(len(pcs) - 1):
        t = ins[pcs[k]][0]
        m = re.match(r"do\s+\S+,>?\$([0-9a-f]+)", t)
        if m and pcs[k + 1] == int(m.group(1), 16):
            sys.exit(f"the trace skips the body of `{t}` at P:0x{pcs[k]:x}: this dsp_host ({HOST}) "
                     "does not step DO loops (-steptrace). Set ILSCAN_HOST to one that does.")
    seq = []
    for k, pc in enumerate(pcs):
        i = Ins(pc, *ins[pc])
        if i.cond and k + 1 < len(pcs):
            i.taken = pcs[k + 1] != pc + i.nwords
        seq.append(i)
    total, stalls, sites = analyze(seq)
    return seq, total, stalls, sites


def main(argv):
    if "--selftest" in argv:
        sys.exit(0 if selftest() else 1)
    dump = "--dump" in argv
    top = 12
    if "--top" in argv:
        i = argv.index("--top")
        top = int(argv[i + 1])
        del argv[i:i + 2]
    argv = [a for a in argv if a != "--dump"]
    if not argv:
        sys.exit(__doc__)
    import send_probe
    from remix import audition, registry
    mod = registry.by_name(argv[0])
    if mod.dsp is None or mod.menu is None:
        sys.exit(f"{mod.name} has no DSP effect of its own to scan")
    # the audition's scratch dump: payload A with this module (and SEND) in it,
    # rebuilt when anything under modules/ is newer than it
    mem = audition._ensure_insert_mem(mod, log=lambda *_a: None)
    init, proc = send_probe.entry_points(str(mem), mod.menu.fx2_id)
    send = registry.by_name("send")
    if mod.key != send.key and (init, proc) == send_probe.entry_points(str(mem), send.menu.fx2_id):
        sys.exit(f"fx id 0x{mod.menu.fx2_id:02x} resolves to SEND's entry points: {mod.name} is not in {mem}")
    p = load_p(mem)
    syms, same = labels_at(mod.name, init, p)
    if same < 0.99:
        syms = []                    # the module does not start at its init entry: no labels
    print(f"{mod.name}: init P:0x{init:x} proc P:0x{proc:x}, {FRAMES}-sample blocks, one steady block a setting")
    print("cycles = Table A-1 (DSP56300FM Rev 5); stalls = sections A.2 and 3.5; internal memory, no wait states")
    print(f"{'setting':28} {'instr/smp':>9} {'cyc/smp':>8} {'stall/smp':>9}  " + " ".join(f"{k:>9}" for k in KINDS))
    reports = []
    for label, params in settings_for(mod, argv[1:]):
        seq, total, stalls, sites = scan(mod, mem, init, proc, params, p, syms)
        base = sum(i.cyc for i in seq)
        st = sum(stalls.values())
        print(f"{label:28} {len(seq) / FRAMES:9.1f} {(total) / FRAMES:8.1f} {st / FRAMES:9.1f}  "
              + " ".join(f"{stalls[k] / FRAMES:9.2f}" for k in KINDS))
        reports.append((label, params, seq, total, base, stalls, sites))
    print("\ncyc/smp includes the stalls and A.2.6.3's +1 after a conditional branch not taken.")
    print(f"\ncycles a sample above one an instruction, by form (Table A-1):\n{'setting':28} "
          + " ".join(f"{f[:11]:>11}" for f in FORMS) + f" {'branch+1':>9}")
    for label, params, seq, total, base, stalls, sites in reports:
        extra = Counter()
        for i in seq:
            f = form_of(i)
            if f:
                extra[f] += i.cyc - 1
        nt = sum(1 for i in seq if i.cond and i.taken is False)
        print(f"{label:28} " + " ".join(f"{extra[f] / FRAMES:11.2f}" for f in FORMS) + f" {nt / FRAMES:9.2f}")
    for label, params, seq, total, base, stalls, sites in reports:
        agg = defaultdict(lambda: [0, 0])
        for k, kind, n, w in sites:
            key = (seq[w].pc, seq[k].pc, kind)
            agg[key][0] += 1
            agg[key][1] += n
        at = {i.pc: i for i in seq}
        print(f"\n{label}: params {params}; {len(seq)} instructions, {base} cycles before stalls, "
              f"{total - base} after (stalls and branch decode), {total} in the block")
        print(f"  {'stall/smp':>9}  {'kind':9}  {'site':18} the instruction that waits     waits on")
        for (wpc, pc, kind), (cnt, n) in sorted(agg.items(), key=lambda kv: -kv[1][1])[:top]:
            print(f"  {n / FRAMES:9.2f}  {kind:9}  {where(pc, syms):18} {at[pc].text:30} "
                  f"{at[wpc].text} ({where(wpc, syms)})")
        if dump:
            st = {k: (kind, n) for k, kind, n, _w in sites}
            for k, i in enumerate(seq):
                s = st.get(k)
                print(f"    {k:6} {i.pc:06x} {where(i.pc, syms):18} {i.cyc}c {('+' + str(s[1]) + ' ' + s[0]) if s else '':14} {i.text}")


if __name__ == "__main__":
    main(sys.argv[1:])
