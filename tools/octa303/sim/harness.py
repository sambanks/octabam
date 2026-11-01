"""Run modules/octa303/octa303.s (the source text) in cfsim against a mock of OS 1.40C laid out as
Tim Hastie's poly.s 2.9 documents it: sy_render(track, ping, start, end), one or two calls a
16-sample frame, the header's byte 3 = samples shipped, L/R longs from +16, the voice structs
(byte 0 alive, +8 the settings record, +64..+83 the sample positions), the settings records'
paths, the packer's event byte (bit 4 = START), its render state (+4 retrig count), the DSP
parameter record (halfwords raw<<8).  The mocked stock renderer records what it was called with,
ships samples, advances the positions and returns a value.
"""
import os, sys, random
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..'))
from cfsim import CPU, Mem, s32, M32
import ref303 as R, o3tables as T

SRC_PATH = os.environ.get('OCTA_SRC', os.path.join(ROOT, 'modules', 'octa303', 'octa303.s'))
CURSOR, FP_PTR, RS_PTR, NIBBLE, STOCK = 0x80001c80, 0x800062a8, 0x800062a4, 0x46104d0c, 0x40004008
VOICE_BASE, VSTR, SETTINGS = 0x800049d8, 0xa8, 0x100b14f0
CUR, FRAME, RS, STACK = 0x80100000, 0x80200000, 0x80300000, 0x80400000
CURVALS, CVSTR = 0x80000810, 72
FXID1, FXID2 = 0x80000ec4, 0x80000ecc
VREC, PINGW = 0x80000110, 0x800000e0     # v7.1: the DSP voice records (+ ping*0x200 + 64*track), the ping
BANKP, PATB, STEPW, TICKB = 0x46c82456, 0x100b14d0, 0x800065b2, 0x800065b6   # v6.5: the gate's inputs
BANK, PATNO, PSTR, TSTR = 0x41000000, 3, 0x8ed8, 0x91a
PARTB, PART_OFF = 0x100b14cf, 0x8ed80                                        # v7.0: the machine's Part'
DEVIL_ID = 0x10          # modules/devilish/manifest.py FX_ID (test_octa303 checks they agree)

def hooks_flags():
    """modules/hooks's flags (FLAGS), read without importing the build's schema."""
    import ast
    tree = ast.parse(open(os.path.join(ROOT, 'modules', 'hooks', 'manifest.py')).read())
    return next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                and any(getattr(t, 'id', None) == 'FLAGS' for t in n.targets)).values()

def remix_inc(devilish=True):
    """What the build writes as remix.inc (modules/octa303/manifest.py remix_inc): OCTA303
    alone, so every HOOKS flag 0 (its own bytes)."""
    return ('        .set    DEVIL_ID, 0x%x\n' % (DEVIL_ID if devilish else 0x100)
            + ''.join('        .set    %s, 0\n' % f for f in hooks_flags()))

def _unflag(s):
    """The .if / .else / .endif blocks on a HOOKS flag resolved as OCTA303 alone builds them (every
    flag 0): cfsim has no conditional assembly."""
    flags, out, keep = set(hooks_flags()), [], [True]
    for line in s.split('\n'):
        tok = line.split('|')[0].split()
        if tok[:1] == ['.if']:
            if tok[1:] and tok[1] not in flags and all(keep):    # nested in a dropped block: any symbol
                raise ValueError('cfsim harness: .if on ' + ' '.join(tok[1:]) + ', not a HOOKS flag')
            keep.append(False)
        elif tok[:1] == ['.else']:
            keep[-1] = not keep[-1]
        elif tok[:1] == ['.endif']:
            keep.pop()
        elif all(keep):
            out.append(line)
    return '\n'.join(out)

def source(devilish=True):
    s = open(SRC_PATH).read()
    assert s.count('.include "remix.inc"') == 1
    return _unflag(s.replace('        .include "remix.inc"', remix_inc(devilish).rstrip('\n'), 1))

class Rig:
    def __init__(self, src=None):
        self.cpu = CPU(src or source(), hooks={STOCK: self._stock})
        m = self.cpu.mem
        m.w(CURSOR, 'l', CUR); m.w(FP_PTR, 'l', FRAME); m.w(RS_PTR, 'l', RS)
        self.seen = []; self.feed = None; self.slots = {}
        self.ping = 0; self.vover = {}
    def vrec(self, track, slot, hws, ping=None):
        """v7.1: what the frame builder left in track's DSP voice record for FX slot (1, 2): six page-1
        halfwords (raw << 8, locks, scenes and LFOs applied); None = the lane's knobs << 8."""
        if ping is not None: self.ping = ping
        if hws is None: self.vover.pop((track, slot), None)
        else: self.vover[(track, slot)] = tuple(hws)
    def path(self, slot, p):
        for i, ch in enumerate(p.encode() + b'\0'): self.cpu.mem.w(SETTINGS + 0x448 * slot + i, 'b', ch)
    def voice(self, track, alive, slot):
        m = self.cpu.mem; v = VOICE_BASE + VSTR * track
        m.w(v, 'b', 1 if alive else 0); m.w(v + 8, 'l', SETTINGS + 0x448 * slot if slot is not None else 0)
    def positions(self, track):
        return [self.cpu.mem.r(VOICE_BASE + VSTR * track + 64 + 4 * i, 'l') for i in range(5)]
    def _stock(self, cpu):
        m = cpu.mem
        args = [m.r(cpu.a[7] + 4 * i, 'l') for i in range(4)]
        words = [m.r(FRAME + 2 * i, 'w') for i in range(6)]
        self.seen.append((args, words))
        t, n = args[0], args[3] - args[2]
        m.w(CUR + 3, 'b', n)
        for i in range(n):
            v = self.feed(i); m.w(CUR + 16 + 8 * i, 'l', v); m.w(CUR + 20 + 8 * i, 'l', v)
        for i in range(5):                           # the stock renderer advances the positions
            a = VOICE_BASE + VSTR * t + 64 + 4 * i; m.w(a, 'l', (m.r(a, 'l') + 0x111 * (i + 1)) & M32)
        cpu.d[0] = 0xC0DE0000 + t; cpu.d[1] = 0xBAD0BAD0; cpu.a[0] = cpu.a[1] = 0xBAD0BAD0
    def machine(self, track, setup, part=0, sign=True):
        """v7.0: track = the TB-303 machine in the current part (FLEX, signed 'T','B',1 in Part' + 0x3c +
        30*track), its live lane's SETUP bytes (+0x20) = setup."""
        m = self.cpu.mem; P = BANK + PART_OFF + part * 6322
        m.w(BANKP, 'l', BANK); m.w(PARTB, 'b', part)
        m.w(P + 0x22 + track, 'b', 1)
        for i, b in enumerate(b'TB\x01' if sign else b'\0\0\0'): m.w(P + 0x3c + 30 * track + i, 'b', b)
        for i, v in enumerate(setup): m.w(CURVALS + CVSTR * track + 0x20 + i, 'b', v & 0xFF)
    def seq(self, track, seq):
        """v6.5: the gate's inputs, seq = (hold, step, tick, slides, length) -- slides split between the
        trigless-trig mask (+8) and the trigless-lock mask (+16); a trig mask (+0) the gate must ignore."""
        m = self.cpu.mem
        hold, step, tick, slides, L = seq
        m.w(CURVALS + CVSTR * track + 13, 'b', hold)
        m.w(STEPW, 'w', step); m.w(TICKB, 'b', tick)
        m.w(BANKP, 'l', BANK); m.w(PATB, 'b', PATNO)
        rec = BANK + PATNO * PSTR + track * TSTR
        m1 = slides & 0x5555555555555555; m2 = slides & ~0x5555555555555555 & (2 ** 64 - 1)
        for i, v in enumerate((0xF0F0F0F0F0F0F0F0 & ~slides, m1, m2)):
            for j, b in enumerate(v.to_bytes(8, 'big')): m.w(rec + 8 * i + j, 'b', b)
        m.w(rec + 0x50, 'b', L)
    def call(self, track, words, start, end, startbit, feed, df=None, slot=1, seq=None):
        """df = dEVILish's twelve knobs on this track (slot 1 = FX1, 2 = FX2), or None (not there)."""
        m = self.cpu.mem
        lane = CURVALS + CVSTR * track
        m.w(FXID1 + track, 'b', 0x04); m.w(FXID2 + track, 'b', 0x08)        # FILTER, DELAY
        for i in range(6): m.w(lane + 18 + i, 'b', 99); m.w(lane + 24 + i, 'b', 99)   # their knobs: not ours
        if df is not None and slot in (1, 2):                          # slot 0: the knobs set, no dEVILish
            m.w((FXID1 if slot == 1 else FXID2) + track, 'b', DEVIL_ID)
        if df is not None:
            p1, p2 = (18, 0x32) if slot == 1 else (24, 0x38)
            for i in range(6): m.w(lane + p1 + i, 'b', df[i]); m.w(lane + p2 + i, 'b', df[6 + i])
        # v7.1: the voice records -- this ping's from the lane (or vrec()), the other ping's garbage
        m.w(PINGW, 'l', self.ping)
        for pg in (0, 1):
            rec = VREC + pg * 0x200 + 64 * track
            for s, (p1, hw) in ((1, (18, 6)), (2, (24, 12))):
                over = self.vover.get((track, s))
                for i in range(6):
                    v = (over[i] if over is not None else m.r(lane + p1 + i, 'b') << 8) if pg == self.ping else 0x5A5A
                    m.w(rec + 2 * (hw + i), 'w', v & 0xFFFF)
        if seq is not None: self.seq(track, seq)
        for i, w in enumerate(words): m.w(FRAME + 2 * i, 'w', w)
        m.w(NIBBLE + track, 'b', 0x10 if startbit else 0)
        m.w(CUR, 'l', 0xABCDEF00)
        self.feed = feed
        self.cpu.a[7] = STACK
        for v in reversed([track, 0x800000e4, start, end]): self.cpu.a[7] -= 4; m.w(self.cpu.a[7], 'l', v)
        sp0 = self.cpu.a[7]
        for r in range(8): self.cpu.d[r] = 0x11110000 + r
        for r in range(7): self.cpu.a[r] = 0x22220000 + r
        self.cpu.call('sy_render')
        assert self.cpu.a[7] == sp0, 'stack not balanced'
        for r in range(2, 8): assert self.cpu.d[r] == 0x11110000 + r, 'd%d not preserved' % r
        for r in range(2, 7): assert self.cpu.a[r] == 0x22220000 + r, 'a%d not preserved' % r
        assert self.cpu.d[0] == 0xC0DE0000 + track, 'stock return value not handed back'
        n = end - start
        return [m.r(CUR + 16 + 8 * i, 'l') for i in range(n)], [m.r(CUR + 20 + 8 * i, 'l') for i in range(n)]

def sample_feed(seed):
    tab = [(random.Random(seed * 1000 + i).randrange(-30000, 30000) << 16) & M32 for i in range(16)]
    return lambda i: tab[i]
SILENCE = lambda i: 0
