#!/usr/bin/env python3
"""cfsim v2 -- source-level ColdFire (MCF547x, ISA_B) interpreter for GNU-as '%'-syntax sources.

Executes the TEXT of a .s file (not a binary) and LINTS it against ColdFire encoding limits that a
68k-minded author gets wrong (the v4 source used `asr.l #15`, which m68k-elf-as rejects for -mcpu=5475):
  * ALU/shift ops are .l only; shift/addq/subq immediates are 1..8; moveq is -128..127
  * muls.l/mulu.l/divs.l/divu.l take Dn,(An),(An)+,-(An),d16(An) -- never #imm, abs or indexed
  * immediate add/sub/and/or/eor/cmp only into a data register
  * move #imm -> d16(An)/indexed/abs and indexed/abs memory-to-memory moves are refused (conservative)
  * movem only to/from (An) or d16(An)
It is a correctness model, not a timing model, and it is NOT an assembler: `make check` is.
Supports .macro/.endm (\\arg, \\@), .set/.equ, .long/.short/.byte/.space/.zero/.align/.balign, .text/.bss/.data.
"""
import re

M32 = 0xFFFFFFFF
MASK = {'b': 0xFF, 'w': 0xFFFF, 'l': M32}
BITS = {'b': 8, 'w': 16, 'l': 32}
def s32(x): x &= M32; return x - (1 << 32) if x & 0x80000000 else x
def sx(x, sz):
    b = BITS[sz]; x &= (1 << b) - 1
    return x - (1 << b) if x >> (b - 1) else x

class LintError(Exception): pass

class Mem:
    def __init__(self): self.b = {}
    def r(self, a, sz):
        v = 0
        for i in range(BITS[sz] // 8): v = (v << 8) | self.b.get((a + i) & M32, 0)
        return v
    def w(self, a, sz, v):
        n = BITS[sz] // 8; v &= MASK[sz]
        for i in range(n): self.b[(a + i) & M32] = (v >> (8 * (n - 1 - i))) & 0xFF

CODE_BASE, TEXT_DATA, DATA_BASE, BSS_BASE = 0x50000000, 0x51000000, 0x52000000, 0x53000000

class CPU:
    def __init__(self, src, mem=None, hooks=None, defsyms=None):
        self.mem = mem or Mem(); self.hooks = hooks or {}
        self.via_jmp = False        # a hook reached by jmp finds its return address at a7 and the arguments above it
        self.d = [0] * 8; self.a = [0] * 8; self.N = self.Z = self.V = self.C = 0
        self.consts = dict(defsyms or {}); self.labels = {}; self.prog = []; self.icount = 0; self.prof = None
        self.lines = self._expand(src.splitlines())
        self._load()
        self._lint()

    # ---------------------------------------------------------------- loading
    def _expand(self, lines):
        macros, out, i, ctr = {}, [], 0, [0]
        while i < len(lines):
            raw = lines[i]; i += 1
            line = raw.split('|')[0].rstrip()
            st = line.strip()
            if st.startswith('.macro'):
                parts = re.split(r'[\s,]+', st[6:].strip()); name, args = parts[0], [p for p in parts[1:] if p]
                body = []
                while not lines[i].split('|')[0].strip().startswith('.endm'):
                    body.append(lines[i]); i += 1
                i += 1; macros[name] = (args, body); continue
            tok = st.split(None, 1)
            if tok and tok[0] in macros:
                args, body = macros[tok[0]]
                vals = [v.strip() for v in self._split(tok[1])] if len(tok) > 1 else []
                ctr[0] += 1
                sub = []
                for b in body:
                    b = b.split('|')[0]
                    for a_, v in zip(args, vals): b = b.replace('\\' + a_, v)
                    sub.append(b.replace('\\@', str(ctr[0])))
                lines = lines[:i] + sub + lines[i:]
                continue
            out.append(line)
        return out

    def _split(self, s):
        out, depth, cur = [], 0, ''
        for ch in s:
            if ch == '(': depth += 1
            if ch == ')': depth -= 1
            if ch == ',' and depth == 0: out.append(cur.strip()); cur = ''
            else: cur += ch
        if cur.strip(): out.append(cur.strip())
        return out

    def _load(self):
        sec = 'text'; ptr = {'text': TEXT_DATA, 'data': DATA_BASE, 'bss': BSS_BASE}
        pending_data = []
        for line in self.lines:
            line = line.strip()
            if not line: continue
            while True:
                m = re.match(r'^([A-Za-z_.][\w.]*):\s*(.*)$', line)
                if not m: break
                name, line = m.group(1), m.group(2).strip()
                pending_data.append(name)
                self.labels[name] = None
                self._bind_later = True
            if not line:
                continue
            if line.startswith('.'):
                d, _, arg = line.partition(' '); d = d.strip(); arg = arg.strip()
                if d in ('.text', '.data', '.bss'):
                    self._bind(pending_data, sec, ptr); pending_data = []; sec = d[1:]; continue
                if d in ('.set', '.equ'):
                    k, v = [x.strip() for x in arg.split(',', 1)]; self.consts[k] = self.ev(v); continue
                if d in ('.global', '.globl', '.type', '.size', '.section'): continue
                if d in ('.align', '.balign', '.p2align'):
                    n = self.ev(arg.split(',')[0]); n = (1 << n) if d == '.p2align' else n
                    ptr[sec] = (ptr[sec] + n - 1) // n * n
                    if sec == 'text' and pending_data == []: pass
                    continue
                if d in ('.long', '.short', '.word', '.byte', '.space', '.zero', '.ascii', '.asciz', '.fill', '.rept', '.endr'):
                    self._bind(pending_data, sec if sec != 'text' else 'tdata', ptr); pending_data = []
                    self._data(d, arg, sec, ptr); continue
                raise LintError('unsupported directive ' + line)
            # instruction
            if sec != 'text': raise LintError('instruction outside .text: ' + line)
            self._bind(pending_data, 'code', ptr); pending_data = []
            mn, _, ops = line.partition(' ')
            self.prog.append((mn.strip(), self._split(ops.strip()), line))
        self._bind(pending_data, sec if sec != 'text' else 'tdata', ptr)
        for k, v in self.labels.items():
            if v is None: raise LintError('unbound label ' + k)
        # resolve deferred data words (forward references)
        for addr, sz, expr in self._fix:
            self.mem.w(addr, sz, self.ev(expr))

    def _bind(self, names, kind, ptr):
        for n in names:
            if kind == 'code': self.labels[n] = ('code', len(self.prog)); self.consts[n] = CODE_BASE + 2 * len(self.prog)
            else:
                sec = 'text' if kind == 'tdata' else kind
                self.labels[n] = ('data', ptr[sec]); self.consts[n] = ptr[sec]

    _fix = None
    def _data(self, d, arg, sec, ptr):
        if self._fix is None: self._fix = []
        if d in ('.space', '.zero'):
            ptr[sec] += self.ev(arg); return
        if d == '.fill':
            n, sz, v = [self.ev(x) for x in self._split(arg)]
            for _ in range(n): self.mem.w(ptr[sec], {1: 'b', 2: 'w', 4: 'l'}[sz], v); ptr[sec] += sz
            return
        if d in ('.ascii', '.asciz'):
            s = bytes(arg.strip()[1:-1], 'latin1').decode('unicode_escape').encode('latin1')
            if d == '.asciz': s += b'\0'
            for c in s: self.mem.w(ptr[sec], 'b', c); ptr[sec] += 1
            return
        sz = {'.long': 'l', '.short': 'w', '.word': 'w', '.byte': 'b'}[d]
        for x in self._split(arg):
            self._fix.append((ptr[sec], sz, x)); ptr[sec] += BITS[sz] // 8

    def ev(self, e):
        e = e.strip()
        if re.fullmatch(r"'.'", e): return ord(e[1])
        toks = re.findall(r"0x[0-9a-fA-F]+|\d+|[A-Za-z_.][\w.]*|<<|>>|[-+*/()|&~]", e)
        py = []
        for t in toks:
            if re.fullmatch(r'[A-Za-z_.][\w.]*', t):
                if t not in self.consts: raise KeyError(t)
                py.append(str(self.consts[t]))
            elif t == '/': py.append('//')
            else: py.append(t)
        return eval(''.join(py), {}, {})

    # ---------------------------------------------------------------- lint
    def _kind(self, op):
        op = op.strip()
        if op.startswith('#'): return 'imm'
        if re.fullmatch(r'%d\d', op): return 'd'
        if re.fullmatch(r'%(a\d|sp)', op): return 'a'
        if re.fullmatch(r'\(%(a\d|sp)\)', op): return 'ind'
        if re.fullmatch(r'\(%(a\d|sp)\)\+', op): return 'post'
        if re.fullmatch(r'-\(%(a\d|sp)\)', op): return 'pre'
        if re.fullmatch(r'.+\(%pc\)', op): return 'pcrel'
        if re.fullmatch(r'[^(]*\(%(a\d|sp),%(d\d|a\d)\.l(\*\d)?\)', op): return 'idx'
        if re.fullmatch(r'[^(]+\(%(a\d|sp)\)', op): return 'd16'
        return 'abs'

    def _lint(self):
        MEMS = ('ind', 'post', 'pre', 'd16', 'idx', 'abs', 'pcrel')
        for mn, ops, line in self.prog:
            b, _, sz = mn.partition('.')
            k = [self._kind(o) for o in ops]
            def bad(why): raise LintError('%s  <-- %s' % (line, why))
            for o, kk in zip(ops, k):                       # v6.7.2: m68k-elf-as's displacement ranges
                if kk == 'idx' and not -128 <= self.ea(o)[4] <= 127: bad('indexed displacement must be -128..127 (byte)')
                if kk == 'd16' and not -32768 <= self.ea(o)[2] <= 32767: bad('d16 displacement out of range')
            if b in ('lsl', 'lsr', 'asr', 'asl'):
                if sz != 'l': bad('shifts are .l only on ColdFire')
                if k[0] == 'imm' and not 1 <= self.ev(ops[0][1:]) <= 8: bad('shift immediate must be 1..8')
                if k[-1] != 'd': bad('shift destination must be Dn')
            if b in ('addq', 'subq') and not 1 <= self.ev(ops[0][1:]) <= 8: bad('quick immediate 1..8')
            if b == 'moveq' and (not -128 <= self.ev(ops[0][1:]) <= 127 or k[1] != 'd'): bad('moveq range/dest')
            if b in ('add', 'sub', 'and', 'or', 'eor', 'neg', 'not', 'addx', 'subx') and sz not in ('l', ''):
                bad('ALU ops are .l only on ColdFire')
            if b in ('add', 'sub', 'and', 'or', 'cmp') and k[0] == 'imm' and k[1] not in ('d', 'a'):
                if not (b in ('add', 'sub') and False): bad('immediate ALU op only into a register')
            if b == 'eor' and k[0] not in ('d', 'imm'): bad('eor source must be Dn')
            if b == 'eor' and k[0] == 'imm' and k[1] != 'd': bad('eori only into Dn')
            if b in ('neg', 'not', 'ext', 'swap') and k[0] != 'd': bad('%s only on Dn' % b)
            if b in ('muls', 'mulu', 'divs', 'divu', 'rems', 'remu'):
                if sz == 'l' and k[0] not in ('d', 'ind', 'post', 'pre', 'd16'): bad('mul/div.l source: Dn,(An),(An)+,-(An),d16(An)')
                if sz == 'w' and k[0] in ('idx', 'abs', 'pcrel'): bad('mul/div.w source mode')
                if k[1] != 'd': bad('mul/div destination must be Dn')
            if b == 'cmp' and k[1] != 'd' and k[1] != 'a': bad('cmp destination must be a register')
            if b == 'move':
                if k[0] == 'imm' and k[1] in ('d16', 'idx', 'abs'): bad('move #imm to d16/indexed/abs memory')
                if k[0] in MEMS and k[1] in MEMS and ('idx' in k or 'abs' in k or 'pcrel' in k):
                    bad('memory-to-memory move with indexed/absolute operand')
            if b == 'movem':
                memop = ops[1] if '%' in ops[0] and '(' not in ops[0] else ops[0]
                if self._kind(memop) not in ('ind', 'd16'): bad('movem only (An)/d16(An)')
            if b in ('addi', 'subi', 'andi', 'ori', 'eori', 'cmpi') and k[1] != 'd': bad('immediate form only into Dn')
            if b in ('btst', 'bset', 'bclr', 'bchg') and k[0] == 'imm' and k[1] not in ('d', 'ind', 'post', 'pre', 'd16'):
                bad('bit op with #imm: Dn,(An),(An)+,-(An),d16(An) only (m68k-elf-as: operands mismatch)')

    # ---------------------------------------------------------------- operands
    def reg(self, t):
        t = t.strip().lstrip('%')
        if t == 'sp': return ('a', 7)
        return (t[0], int(t[1]))
    def ea(self, op):
        op = op.strip(); k = self._kind(op)
        if k == 'imm': return ('imm', self.ev(op[1:]))
        if k in ('d', 'a'): r = self.reg(op); return (r[0], r[1])
        if k in ('ind', 'post', 'pre'): return (k, self.reg(re.search(r'%(a\d|sp)', op).group(0))[1])
        if k == 'pcrel': return ('abs', self.ev(op[:op.index('(')]))
        if k == 'idx':
            m = re.fullmatch(r'([^(]*)\(%(a\d|sp),%([da]\d)\.l(?:\*(\d))?\)', op)
            disp = self.ev(m.group(1)) if m.group(1).strip() else 0
            return ('idx', self.reg(m.group(2))[1], m.group(3), int(m.group(4) or 1), disp)
        if k == 'd16':
            m = re.fullmatch(r'([^(]+)\(%(a\d|sp)\)', op)
            return ('d16', self.reg(m.group(2))[1], self.ev(m.group(1)))
        return ('abs', self.ev(op))
    def addr(self, e):
        if e[0] == 'ind': return self.a[e[1]]
        if e[0] == 'd16': return (self.a[e[1]] + e[2]) & M32
        if e[0] == 'idx':
            xr = self.d[int(e[2][1])] if e[2][0] == 'd' else self.a[int(e[2][1])]
            return (self.a[e[1]] + s32(xr) * e[3] + e[4]) & M32
        if e[0] == 'abs': return e[1] & M32
        raise ValueError(e)
    def get(self, op, sz):
        e = self.ea(op); k = e[0]
        if k == 'imm': return e[1] & MASK[sz]
        if k == 'd': return self.d[e[1]] & MASK[sz]
        if k == 'a': return self.a[e[1]] & MASK[sz]
        if k == 'post':
            v = self.mem.r(self.a[e[1]], sz); self.a[e[1]] = (self.a[e[1]] + BITS[sz] // 8) & M32; return v
        if k == 'pre':
            self.a[e[1]] = (self.a[e[1]] - BITS[sz] // 8) & M32; return self.mem.r(self.a[e[1]], sz)
        return self.mem.r(self.addr(e), sz)
    def put(self, op, sz, v):
        e = self.ea(op); k = e[0]; v &= MASK[sz]
        if k == 'd': self.d[e[1]] = (self.d[e[1]] & ~MASK[sz] & M32) | v
        elif k == 'a': self.a[e[1]] = sx(v, sz) & M32
        elif k == 'post': self.mem.w(self.a[e[1]], sz, v); self.a[e[1]] = (self.a[e[1]] + BITS[sz] // 8) & M32
        elif k == 'pre': self.a[e[1]] = (self.a[e[1]] - BITS[sz] // 8) & M32; self.mem.w(self.a[e[1]], sz, v)
        else: self.mem.w(self.addr(e), sz, v)

    # ---------------------------------------------------------------- flags
    def nz(self, v, sz): v &= MASK[sz]; self.N = (v >> (BITS[sz] - 1)) & 1; self.Z = int(v == 0)
    def cond(self, c):
        N, Z, V, C = self.N, self.Z, self.V, self.C
        return {'eq': Z, 'ne': not Z, 'mi': N, 'pl': not N, 'lt': N ^ V, 'ge': not (N ^ V), 'le': Z or (N ^ V),
                'gt': (not Z) and not (N ^ V), 'cc': not C, 'cs': C, 'hi': (not C) and (not Z), 'ls': C or Z,
                'hs': not C, 'lo': C}[c]
    def subf(self, d, s, sz):
        bits, m = BITS[sz], MASK[sz]; r = (d - s) & m; self.nz(r, sz)
        sd, ss, sr = (d >> (bits - 1)) & 1, (s >> (bits - 1)) & 1, (r >> (bits - 1)) & 1
        self.V = int(sd != ss and sr != sd); self.C = int((s & m) > (d & m)); return r
    def addf(self, d, s, sz):
        bits, m = BITS[sz], MASK[sz]; r = (d + s) & m; self.nz(r, sz)
        sd, ss, sr = (d >> (bits - 1)) & 1, (s >> (bits - 1)) & 1, (r >> (bits - 1)) & 1
        self.V = int(sd == ss and sr != sd); self.C = int((d & m) + (s & m) > m); return r

    # ---------------------------------------------------------------- run
    CONDS = ('eq', 'ne', 'mi', 'pl', 'lt', 'ge', 'le', 'gt', 'cc', 'cs', 'hi', 'ls', 'hs', 'lo')
    def call(self, label, maxsteps=50_000_000, retaddr=0xDEAD0000):
        self.a[7] = (self.a[7] - 4) & M32; self.mem.w(self.a[7], 'l', retaddr)
        pc = self.labels[label][1]; steps = 0
        while True:
            steps += 1
            if steps > maxsteps: raise RuntimeError('step limit')
            mn, ops, line = self.prog[pc]; pc += 1
            b, _, sz = mn.partition('.'); sz = sz if sz in ('b', 'w', 'l') else 'l'
            if b in ('bra', 'jra') or (b[0] in 'bj' and b[1:] in self.CONDS):
                if b in ('bra', 'jra') or self.cond(b[1:]): pc = self.labels[ops[0]][1]
                continue
            if b in ('bsr', 'jsr'):
                e = self.ea(ops[0])
                tgt = e[1] if e[0] == 'abs' else self.addr(e)
                if b == 'bsr': tgt = self.consts[ops[0]]
                if tgt in self.hooks: self.via_jmp = False; self.hooks[tgt](self); continue
                if CODE_BASE <= tgt < TEXT_DATA:
                    self.a[7] = (self.a[7] - 4) & M32; self.mem.w(self.a[7], 'l', CODE_BASE + 2 * pc)
                    pc = (tgt - CODE_BASE) // 2; continue
                raise RuntimeError('call to unmapped %#x  (%s)' % (tgt, line))
            if b == 'jmp':
                e = self.ea(ops[0]); tgt = e[1] if e[0] == 'abs' else self.addr(e)
                if tgt in self.hooks:
                    self.via_jmp = True; self.hooks[tgt](self); b = 'rts'
                elif CODE_BASE <= tgt < TEXT_DATA: pc = (tgt - CODE_BASE) // 2; continue
                else: raise RuntimeError('jmp to unmapped %#x' % tgt)
            if b == 'rts':
                ra = self.mem.r(self.a[7], 'l'); self.a[7] = (self.a[7] + 4) & M32
                if ra == retaddr: return steps
                pc = (ra - CODE_BASE) // 2; continue
            self.icount += 1
            if self.prof is not None: self.prof[pc - 1] = self.prof.get(pc - 1, 0) + 1
            self.exec1(b, sz, ops, line)

    def exec1(self, b, sz, ops, line):
        g, p = self.get, self.put
        if b in ('move', 'movea'):
            v = g(ops[0], sz)
            if self.ea(ops[1])[0] != 'a': self.nz(v, sz); self.V = self.C = 0
            p(ops[1], sz, v)
        elif b == 'moveq':
            v = sx(self.ev(ops[0][1:]), 'b') & M32; self.d[self.reg(ops[1])[1]] = v; self.nz(v, 'l'); self.V = self.C = 0
        elif b == 'lea':
            e = self.ea(ops[0]); v = e[1] if e[0] == 'abs' else self.addr(e); self.a[self.reg(ops[1])[1]] = v & M32
        elif b == 'pea':
            e = self.ea(ops[0]); v = e[1] if e[0] == 'abs' else self.addr(e)
            self.a[7] = (self.a[7] - 4) & M32; self.mem.w(self.a[7], 'l', v)
        elif b in ('add', 'sub', 'addq', 'subq', 'addi', 'subi', 'adda', 'suba'):
            s = g(ops[0], sz); de = self.ea(ops[1])
            if de[0] == 'a':
                s = sx(s, sz) & M32 if sz != 'l' else s
                self.a[de[1]] = (self.a[de[1]] + (s if b.startswith('add') else -s)) & M32; return
            d = g(ops[1], sz)
            p(ops[1], sz, self.addf(d, s, sz) if b.startswith('add') else self.subf(d, s, sz))
        elif b in ('cmp', 'cmpi', 'cmpa'):
            self.subf(g(ops[1], sz), g(ops[0], sz), sz)
        elif b == 'tst':
            self.nz(g(ops[0], sz), sz); self.V = self.C = 0
        elif b in ('and', 'or', 'eor', 'andi', 'ori', 'eori'):
            d = g(ops[1], sz); s = g(ops[0], sz); bb = b.rstrip('i') if b != 'ori' else 'or'
            r = {'and': d & s, 'or': d | s, 'eor': d ^ s}[bb if bb in ('and', 'or', 'eor') else 'or']
            self.nz(r, sz); self.V = self.C = 0; p(ops[1], sz, r)
        elif b == 'neg':
            p(ops[0], sz, self.subf(0, g(ops[0], sz), sz))
        elif b == 'not':
            r = ~g(ops[0], sz) & MASK[sz]; self.nz(r, sz); self.V = self.C = 0; p(ops[0], sz, r)
        elif b == 'clr':
            p(ops[0], sz, 0); self.N = 0; self.Z = 1; self.V = self.C = 0
        elif b == 'swap':
            r = self.reg(ops[0])[1]; v = self.d[r]; v = ((v << 16) | (v >> 16)) & M32; self.d[r] = v; self.nz(v, 'l'); self.V = self.C = 0
        elif b == 'ext':
            r = self.reg(ops[0])[1]; v = sx(self.d[r], 'w') & M32 if sz == 'l' else self.d[r]; self.d[r] = v; self.nz(v, 'l')
        elif b in ('lsl', 'lsr', 'asr', 'asl'):
            if len(ops) == 1: cnt, dst = 1, ops[0]
            else:
                cnt = self.ev(ops[0][1:]) if ops[0].startswith('#') else self.d[self.reg(ops[0])[1]] & 63
                dst = ops[1]
            v = g(dst, 'l')
            if b in ('lsl', 'asl'): r = (v << cnt) & M32 if cnt < 32 else 0
            elif b == 'lsr': r = v >> cnt if cnt < 32 else 0
            else: r = (s32(v) >> min(cnt, 31)) & M32
            self.nz(r, 'l'); self.V = 0; p(dst, 'l', r)
        elif b in ('muls', 'mulu'):
            dreg = self.reg(ops[1])[1]
            if sz == 'w':
                s = g(ops[0], 'w'); d = self.d[dreg] & 0xFFFF
                r = (sx(d, 'w') * sx(s, 'w')) & M32 if b == 'muls' else (d * s) & M32
            else:
                s = g(ops[0], 'l'); d = self.d[dreg]
                r = (s32(d) * s32(s)) & M32 if b == 'muls' else (d * s) & M32
            self.d[dreg] = r; self.nz(r, 'l'); self.V = self.C = 0
        elif b in ('divu', 'divs'):
            dreg = self.reg(ops[1])[1]; d = self.d[dreg]
            if sz == 'w':
                s = g(ops[0], 'w')
                if s == 0: raise ZeroDivisionError(line)
                if b == 'divu':
                    q, r = d // s, d % s
                else:
                    sd, ss = s32(d), sx(s, 'w'); q = abs(sd) // abs(ss); q = -q if (sd < 0) != (ss < 0) else q; r = sd - q * ss
                if not (0 <= q <= 0xFFFF if b == 'divu' else -32768 <= q <= 32767): self.V = 1; return
                self.d[dreg] = ((r & 0xFFFF) << 16) | (q & 0xFFFF); self.nz(q, 'w'); self.V = 0
            else:
                s = g(ops[0], 'l')
                if s == 0: raise ZeroDivisionError(line)
                if b == 'divu': q = d // s
                else:
                    sd, ss = s32(d), s32(s); q = abs(sd) // abs(ss); q = -q if (sd < 0) != (ss < 0) else q
                self.d[dreg] = q & M32; self.nz(q, 'l'); self.V = self.C = 0
        elif b == 'btst':
            bit = self.ev(ops[0][1:]) if ops[0].startswith('#') else self.d[self.reg(ops[0])[1]]
            if self._kind(ops[1]) == 'd': v = self.d[self.reg(ops[1])[1]]; bit &= 31
            else: v = g(ops[1], 'b'); bit &= 7
            self.Z = int(not (v >> bit) & 1)
        elif b in ('mvs', 'mvz'):
            s = g(ops[0], sz); r = (sx(s, sz) if b == 'mvs' else s) & M32
            self.d[self.reg(ops[1])[1]] = r; self.nz(r, 'l'); self.V = self.C = 0
        elif b == 'movem':
            if '(' in ops[1]:  # regs -> mem
                regs, memop = ops[0], ops[1]; store = True
            else: regs, memop = ops[1], ops[0]; store = False
            base = self.addr(self.ea(memop)); lst = []
            for part in regs.split('/'):
                if '-' in part:
                    a_, b_ = [self.reg(x) for x in part.split('-')]
                    lst += [(a_[0], i) for i in range(a_[1], b_[1] + 1)]
                else: lst.append(self.reg(part))
            lst.sort(key=lambda r: (r[0] == 'a', r[1]))
            for i, (k, n) in enumerate(lst):
                if store: self.mem.w(base + 4 * i, 'l', (self.d if k == 'd' else self.a)[n])
                else: (self.d if k == 'd' else self.a)[n] = self.mem.r(base + 4 * i, 'l')
        elif b == 'nop':
            pass
        else:
            raise NotImplementedError(line)
