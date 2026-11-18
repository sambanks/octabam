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
  python3 tools/build/interlock_scan.py EFFECT [NAME=VALUE ...] [--sweep] [--top N] [--json FILE] [--dump]
  python3 tools/build/interlock_scan.py --selftest

EFFECT is a module name (modulation, busverb) or a stock effect's key
(FILTER, "PLATE REV"). NAME=VALUE sets a knob; a select takes its label
(MODE=JUNO), and a MODE starts from that mode's view defaults. A run is made
for every value of the selector (MODE, else the first select of at most 8
values) not set on the command line. --sweep runs three variants a value:
the defaults, every other named knob at its maximum, and every other at its
minimum, and a fourth with the manifest's `dear` knobs when it declares
them; the sites printed are the dearest variant's. --noviews leaves a
mode's view defaults out: the knobs are the manifest's defaults plus the
command line, as the hardware matrix stamps them (tools/hw/ot_matrix.py).
--json writes every run's figures and sites.
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
import json
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
# The traced block is the last of BLOCKS: past the servers' dry start ("the
# engine stays dry for 256 CALLS", tools/harness/render_reverb.py WARMUP_BLOCKS).
BLOCKS = 264

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


def analyze(seq, agu_from=None):
    """seq: [Ins] in executed order, the conditional branches' outcome in .taken.
    -> (cycles, stalls {kind: cycles}, sites [(index, kind, n, index of the producer)])

    agu_from: where A.2.4's three-cycle distance starts. "end" (the default,
    ILSCAN_AGU_FROM) counts from the end of the writing instruction; "start"
    from its first cycle, so a two-cycle writer (a long immediate) is one
    cycle nearer clear. The manual's examples do not separate the two."""
    agu_from = agu_from or os.environ.get("ILSCAN_AGU_FROM", "end")
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
        start = t + st
        t += st + ins.cyc
        if ins.cond and ins.taken is False:
            t += 1                   # A.2.6.3: a false condition delays the next decode by one
        for s, how in ins.agu_dst.items():
            last_w[s] = ((start + 1) if agu_from == "start" else t, how, k)
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


class ScanError(Exception):
    """A run that could not be scanned; a sweep records it and goes on."""


def trace(t, params, blocks=BLOCKS):
    """PCs of the tracked instance's proc in block blocks-1 (a steady block)."""
    with tempfile.TemporaryDirectory(prefix="ilscan.") as d:
        d = pathlib.Path(d)
        n = FRAMES * blocks
        (d / "in.raw").write_bytes(b"".join(
            struct.pack("<i", int(0.3 * 8388607 * ((i * 37) % 200 - 100) / 100)) for i in range(2 * n)))
        cmd = [str(HOST), "-mem", str(t.mem), "-init", f"{t.init:x}", "-proc", f"{t.proc:x}",
               "-inst", "1", "-r7", str(t.r7), "-alloc", str(t.alloc), "-inmask", "1", "-stereo",
               *(["-audio", "0"] if t.audio0 else []),
               "-frames", str(FRAMES), "-blocks", str(blocks), "-diff", str(blocks),
               "-in", str(d / "in.raw"), "-out", str(d / "out.raw"),
               "-params", ",".join(str(x) for x in params),
               "-trace", "400000", "-trackinst", "0", "-steptrace"]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        except subprocess.TimeoutExpired:
            raise ScanError("dsp_host did not finish in 600 s")
    if r.returncode:
        tail = (r.stdout[-1200:] + r.stderr[-600:]).strip().splitlines()[-6:]
        raise ScanError(f"dsp_host failed ({HOST}; a host without -steptrace fails here too: "
                        f"set ILSCAN_HOST): " + " | ".join(tail))
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
        raise ScanError("dsp_host printed no trace")
    return calls[-1]


def _words(b):
    return [b[i] | b[i + 1] << 8 | b[i + 2] << 16 for i in range(0, len(b) - len(b) % 3, 3)]


def labels_for(mod, init, p):
    """[(address, label)] of the module's source where the dump has it, or [].

    The source is assembled once at 0; the base is the one, among init minus
    each label's address, at which the most words agree with the dump (a
    word holding an absolute address differs, the rest agree)."""
    import cycle_count
    try:
        src = cycle_count.prep(pathlib.Path(mod.dsp.asm).stem)
    except SystemExit:
        return []
    with tempfile.TemporaryDirectory(prefix="ilscan.") as d:
        d = pathlib.Path(d)
        (d / "s.asm").write_text(src)
        r = subprocess.run([str(ASM), "-in", str(d / "s.asm"), "-org", "0",
                            "-out", str(d / "s.bin"), "-sym", str(d / "s.sym")], capture_output=True, text=True)
        if r.returncode or not (d / "s.bin").exists():
            return []
        w = _words((d / "s.bin").read_bytes())
        syms = sorted((int(v, 16), k) for k, v in (l.split() for l in (d / "s.sym").read_text().splitlines()
                                                    if l.strip()))
    best, best_same = None, 0.0
    for a, _k in syms:
        base = init - a
        if base < 0:
            continue
        same = sum(1 for i, x in enumerate(w) if p.get(base + i) == x) / max(1, len(w))
        if same > best_same:
            best, best_same = base, same
    if best is None or best_same < 0.9:
        return []
    return [(a + best, k) for a, k in syms]


def insert_mem(mod):
    """The audition's scratch dump for an insert, with the modules it requires.

    audition._ensure_insert_mem builds a two-module remix (the insert and
    SEND); a module with `requires` (DEVILISH needs OCTA303, EUCLID EVENTS)
    refuses that build, so its scratch remix carries them too."""
    from remix import audition, registry
    need, todo = [], list(mod.requires or ())
    while todo:
        k = todo.pop()
        if k not in need and k != mod.key:
            need.append(k)
            todo += list(registry.by_key(k).requires or ())
    if not need:
        return audition._ensure_insert_mem(mod, log=lambda *_a: None)
    mem = ROOT / f"out/dsp/_audition_{mod.name}_A.mem"
    if mem.exists() and mem.stat().st_mtime > audition._newest_input_mtime():
        return mem
    send = registry.by_name("send")
    keys = ", ".join(f'"{k}"' for k in [mod.key, send.key, *need])
    scratch = ROOT / "remixes/_audition.py"
    scratch.write_text(
        f'"""_audition -- scratch: {mod.name} + SEND + what it requires, for interlock_scan.\n\n'
        f'Written and removed by tools/build/interlock_scan.py.\n"""\n\n'
        f'from remix.schema import Remix\n\n'
        f'REMIX = Remix(\n    name="_audition",\n    doc="audition scratch",\n'
        f'    modules=({keys},),\n    fallback="{send.key}",\n)\n')
    keep = audition.IMAGE.read_bytes() if audition.IMAGE.exists() else None
    try:
        audition._build({"REMIX": "_audition", "XBUS": "1", "SPEC": "1"})
        audition._dump(mem)
    finally:
        scratch.unlink(missing_ok=True)
        for junk in (ROOT / "remixes/__pycache__").glob("_audition*"):
            junk.unlink(missing_ok=True)
        if keep is not None:
            audition.IMAGE.write_bytes(keep)
    return mem


class Target:
    """What one effect needs for a run: its dump, entries, slot and labels."""

    def __init__(self, mod):
        import send_probe
        from remix import audition, registry, schema, stock
        self.mod = mod
        quiet = lambda *_a: None  # noqa: E731
        self.audio0 = False
        if getattr(mod, "is_stock", False):
            if mod.key in stock.NO_DSP:
                raise ScanError(f"{mod.key} runs on the ColdFire (stock.NO_DSP): its DSP entry is "
                                "the passthrough stub")
            self.mem = audition._ensure_stock_mem(log=quiet)
            self.r7, self.alloc = schema.render_slot(mod)
            self.audio0 = True            # dsp_host's default audio block sits in stock scratch
        elif mod.dsp is None or mod.menu is None:
            raise ScanError(f"{mod.name} has no DSP effect of its own to scan")
        elif mod.name == "busdelay":
            self.mem = audition._ensure_delay_mem(log=quiet)   # the DEV hatch: the server in payload A
            self.r7, self.alloc = schema.render_slot(mod)
        elif mod.key == registry.by_name("send").key:
            # SEND cannot pair with itself in the audition's scratch remix; the
            # reverb server's scratch dump is the reverb plus SEND
            self.mem = audition._ensure_insert_mem(registry.by_name("busverb"), log=quiet)
            self.r7, self.alloc = schema.render_slot(mod)
        else:
            try:
                self.mem = insert_mem(mod)
            except RuntimeError as e:          # the audition's build refused the scratch remix
                raise ScanError(str(e))
            if mod.name == "busverb":
                import render_reverb      # its slot rule: the first FX2 slot on a guarded image
                self.r7, self.alloc = (2 if render_reverb._guarded(self.mem) else 4), 3
            else:
                self.r7, self.alloc = schema.render_slot(mod)
        self.init, self.proc = send_probe.entry_points(str(self.mem), mod.menu.fx2_id)
        send = registry.by_name("send")
        if not getattr(mod, "is_stock", False) and mod.key != send.key and \
                (self.init, self.proc) == send_probe.entry_points(str(self.mem), send.menu.fx2_id):
            raise ScanError(f"fx id 0x{mod.menu.fx2_id:02x} resolves to SEND's entry points: "
                            f"{mod.name} is not in {self.mem}")
        self.p = load_p(self.mem)
        self.syms = [] if getattr(mod, "is_stock", False) else labels_for(mod, self.init, self.p)
        self.labelled = bool(self.syms)
        if not self.syms:
            # stock code, or a source the build edits (a key bus reader, a
            # per-remix substitution): sites read from the entries instead
            self.syms = sorted({(self.init, "init"), (self.proc, "proc")})


def where(pc, syms):
    best = None
    for a, k in syms:
        if a <= pc:
            best = (a, k)
        else:
            break
    return f"{best[1]}+{pc - best[0]}" if best else f"P:{pc:x}"


# ---- settings -----------------------------------------------------------------

def _name(q):
    n = q.name
    return (n.decode() if isinstance(n, bytes) else n) or ""


def selector(mod):
    """The knob a sweep runs every value of: MODE, else the first select of at most 8 values."""
    names = [_name(q) for q in mod.params]
    if "MODE" in names:
        return "MODE"
    for q in mod.params:
        if q.labels and q.count and q.count <= 8:
            return _name(q)
    return None


def settings_for(mod, args, sweep=False, views=True):
    """[(label, variant, params)]: the knob vector of each run.

    A run per value of the selector (MODE, or the first small select), from
    that value's view defaults when the module has views. With sweep, three
    variants a value: the defaults, every other named knob at its maximum,
    and every other named knob at its minimum (the "dearest of as-picked,
    all-min, all-max" of the stock measurements in CHIP.md), and the
    manifest's `dear` knobs when it has them."""
    names = [_name(q) for q in mod.params]
    K = {n: i for i, n in enumerate(names) if n}
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
    sel = selector(mod)
    qsel = mod.params[K[sel]] if sel else None
    values = [over[sel]] if sel in over else (list(range(qsel.count)) if sel else [None])
    runs = []
    for sv in values:
        v = list(base)
        label = "defaults"
        if sv is not None:
            view = mod.view_for(sv) if views and sel == "MODE" and hasattr(mod, "view_for") else None
            for slot, val in (view.defaults.items() if view is not None else ()):
                v[K[mod.canon_name(slot)]] = val
            v[K[sel]] = sv
            label = (qsel.labels[sv] if qsel.labels else f"{sel}={sv}")
            if sel != "MODE":
                label = f"{sel}={label}"
        variants = [("def", v)]
        if sweep:
            hi, lo = list(v), list(v)
            for i, q in enumerate(mod.params):
                n = names[i]
                if not n or n == sel:
                    continue
                hi[i] = (q.count - 1) if q.count else 127
                lo[i] = 0
            variants += [("max", hi), ("min", lo)]
            dear = dict(getattr(mod, "dear", None) or {})
            if dear:
                # the manifest's dearest knobs (schema `dear`, what the hardware
                # matrix and the pressure render use), the selector kept
                dv = list(v)
                for n, val in dear.items():
                    if n != sel and n in K:
                        dv[K[n]] = val
                variants.append(("dear", dv))
        for var, vec in variants:
            vec = list(vec)
            for name, val in over.items():
                if name != sel:
                    vec[K[name]] = val
            extra = " ".join(f"{n}={x}" for n, x in over.items() if n != sel)
            runs.append(((label + " " + extra).strip(), var, vec))
    return runs


# ---- the report -----------------------------------------------------------------

def scan(t, params):
    pcs = trace(t, params)
    p = t.p
    ins = decode(p, pcs, min(min(pcs), t.init))
    # dsp_host ignores an option it does not know: a host without -steptrace
    # runs each DO loop inside one step, and the trace goes from the `do`
    # straight to the address after the loop (the disassembler prints that
    # address, LA + 1, as the `do`'s operand).
    # A `do` whose count is zero skips its body too (an annulled DO, A.2.6.6:
    # three more decode cycles), so only a count known to be non-zero proves
    # the host: n7 (the frame count) or a non-zero immediate.
    annulled = set()
    for k in range(len(pcs) - 1):
        txt = ins[pcs[k]][0]
        m = re.match(r"do\s+(\S+),>?\$([0-9a-f]+)", txt)
        if m and pcs[k + 1] == int(m.group(2), 16):
            cnt = m.group(1)
            imm = re.match(r"#[<>]?\$?([0-9a-f]+)$", cnt)
            if cnt == "n7" or (imm and int(imm.group(1), 16) != 0):
                sys.exit(f"the trace skips the body of `{txt}` at P:0x{pcs[k]:x}: this dsp_host ({HOST}) "
                         "does not step DO loops (-steptrace). Set ILSCAN_HOST to one that does.")
            annulled.add(k)
    seq = []
    for k, pc in enumerate(pcs):
        i = Ins(pc, *ins[pc])
        if i.cond and k + 1 < len(pcs):
            i.taken = pcs[k + 1] != pc + i.nwords
        if k in annulled:
            i.cyc += 3
        seq.append(i)
    total, stalls, sites = analyze(seq)
    return seq, total, stalls, sites


def main(argv):
    if "--selftest" in argv:
        sys.exit(0 if selftest() else 1)
    dump = "--dump" in argv
    sweep = "--sweep" in argv
    views = "--noviews" not in argv
    top, jpath = 12, None
    for opt in ("--top", "--json"):
        if opt in argv:
            i = argv.index(opt)
            if opt == "--top":
                top = int(argv[i + 1])
            else:
                jpath = argv[i + 1]
            del argv[i:i + 2]
    argv = [a for a in argv if a not in ("--dump", "--sweep", "--noviews")]
    if not argv:
        sys.exit(__doc__)
    # the servers' build paths (the DEV hatch, BusDelay's geometry) read the
    # selected remix; octabam-bus carries both servers
    os.environ.setdefault("REMIX", "octabam-bus")
    from remix import registry, stock
    e = next((e for e in stock.MODULES if e.key.upper() == argv[0].upper()), None)
    mod = registry.by_key(e.key) if e is not None else None
    if mod is None:
        mod = next((m for m in registry.modules().values() if m.key.upper() == argv[0].upper()), None)
    if mod is None:
        try:
            mod = registry.by_name(argv[0])
        except SystemExit:
            mod = None
    if mod is None:
        sys.exit(f"no module or stock effect named {argv[0]!r}")
    who = getattr(mod, "key", mod.name)
    result = dict(target=who, name=mod.name, stock=bool(getattr(mod, "is_stock", False)),
                  frames=FRAMES, runs=[], error=None)
    try:
        t = Target(mod)
    except ScanError as e:
        result["error"] = str(e)
        print(f"{who}: not scanned: {e}")
        if jpath:
            pathlib.Path(jpath).write_text(json.dumps(result, indent=1))
        return
    result.update(init=t.init, proc=t.proc, r7=t.r7, alloc=t.alloc, labels=t.labelled)
    print(f"{who}: init P:0x{t.init:x} proc P:0x{t.proc:x} (r7 {t.r7}, alloc {t.alloc}"
          f"{', -audio 0' if t.audio0 else ''}), {FRAMES}-sample blocks, one steady block a setting")
    print("cycles = Table A-1 (DSP56300FM Rev 5); stalls = sections A.2 and 3.5; internal memory, no wait states")
    print(f"{'setting':28} {'var':3} {'instr/smp':>9} {'cyc/smp':>8} {'stall/smp':>9}  "
          + " ".join(f"{k:>9}" for k in KINDS))
    reports = []
    for label, var, params in settings_for(mod, argv[1:], sweep, views):
        try:
            seq, total, stalls, sites = scan(t, params)
        except ScanError as e:
            print(f"{label:28} {var:3} not scanned: {e}")
            result["runs"].append(dict(label=label, variant=var, params=params, error=str(e)))
            continue
        base = sum(i.cyc for i in seq)
        st = sum(stalls.values())
        print(f"{label:28} {var:3} {len(seq) / FRAMES:9.1f} {total / FRAMES:8.1f} {st / FRAMES:9.1f}  "
              + " ".join(f"{stalls[k] / FRAMES:9.2f}" for k in KINDS))
        extra = Counter()
        for i in seq:
            f = form_of(i)
            if f:
                extra[f] += i.cyc - 1
        nt = sum(1 for i in seq if i.cond and i.taken is False)
        agg = defaultdict(lambda: [0, 0])
        for k, kind, n, w in sites:
            agg[(seq[w].pc, seq[k].pc, kind)][0] += 1
            agg[(seq[w].pc, seq[k].pc, kind)][1] += n
        at = {i.pc: i for i in seq}
        topsites = [dict(stall=n / FRAMES, kind=kind, site=where(pc, t.syms), pc=pc, text=at[pc].text,
                         waits_on=at[wpc].text, waits_on_site=where(wpc, t.syms))
                    for (wpc, pc, kind), (cnt, n) in sorted(agg.items(), key=lambda kv: -kv[1][1])]
        run = dict(label=label, variant=var, params=params, instr=len(seq) / FRAMES,
                   cycles=total / FRAMES, base=base / FRAMES, stall=st / FRAMES,
                   stalls={k: stalls[k] / FRAMES for k in KINDS},
                   forms={f: extra[f] / FRAMES for f in FORMS}, branch_false=nt / FRAMES,
                   sites=topsites[:40])
        result["runs"].append(run)
        reports.append((run, seq, sites))
    print("\ncyc/smp includes the stalls and A.2.6.3's +1 after a conditional branch not taken.")
    print(f"\ncycles a sample above one an instruction, by form (Table A-1):\n{'setting':28} {'var':3} "
          + " ".join(f"{f[:11]:>11}" for f in FORMS) + f" {'branch+1':>9}")
    for run, _seq, _sites in reports:
        print(f"{run['label']:28} {run['variant']:3} " + " ".join(f"{run['forms'][f]:11.2f}" for f in FORMS)
              + f" {run['branch_false']:9.2f}")
    # the sites of the dearest variant of each setting
    dearest = {}
    for run, seq, sites in reports:
        if run["label"] not in dearest or run["cycles"] > dearest[run["label"]][0]["cycles"]:
            dearest[run["label"]] = (run, seq, sites)
    for run, seq, sites in dearest.values():
        print(f"\n{run['label']} ({run['variant']}): params {run['params']}; {run['instr']:.1f} instructions "
              f"a sample, {run['base']:.1f} cycles before stalls, {run['cycles']:.1f} after")
        print(f"  {'stall/smp':>9}  {'kind':9}  {'site':22} the instruction that waits     waits on")
        for s in run["sites"][:top]:
            print(f"  {s['stall']:9.2f}  {s['kind']:9}  {s['site']:22} {s['text']:30} "
                  f"{s['waits_on']} ({s['waits_on_site']})")
        if dump:
            st = {k: (kind, n) for k, kind, n, _w in sites}
            for k, i in enumerate(seq):
                s = st.get(k)
                print(f"    {k:6} {i.pc:06x} {where(i.pc, t.syms):22} {i.cyc}c "
                      f"{('+' + str(s[1]) + ' ' + s[0]) if s else '':14} {i.text}")
    if jpath:
        pathlib.Path(jpath).write_text(json.dumps(result, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
