#!/usr/bin/env python3
"""test_morph: modules/morph/morph.s run from its source text in tools/octa303/sim/cfsim.py.

The firmware is a mock: the addresses morph.s reads and writes (the weights, the fader, the tempo,
the transport, the step word, the pattern's track record, the held keys) are plain memory; a mock
sequencer moves the step word every 992,250 / tempo24 frames while playing. The crossfader curve is
the user's 1.40C table from out/raw/section_3_MAIN_OS.bin when it is there (then every written
weight is checked against the stock writers' formula), else an injective stand-in, so every check
but that one runs anywhere. What it proves: the keys' state machine (arming, start on the next
step from A, stop at A, parking, re-attach, cancel, the master switch), the A->B->A triangle and its
length in steps for STEPS x (and STEPS 0 = the track's length), SMOOTH against TRIG HOLD, the
transport stop, and cfsim's ColdFire lint over the whole source. v1.1 (26 Oct 2026): the window stays
open (YES starts, NO starts nothing), both leave the window's tracks ARMED for the long press (a
track key held ~1 s alone starts and stops that track's morph, also with the MIXER open: the key
table under it is the same), x 1..100 (no easter egg), the stock scene indicator in the window (the
same calls stock's footer makes, moved; checked pixel for pixel against the footer on the port),
and the ARMED tracks saved. What it cannot: the hook site, the
key table under the real firmware, MACSR (cfsim has none: the frame stub is entered after the two
displaced instructions), the unit's frame rate."""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'octa303', 'sim'))
from cfsim import CPU, Mem

SRC = open(os.path.join(ROOT, 'modules', 'morph', 'morph.s')).read()
# cfsim has no MACSR and its lint reads `%macsr` as memory: the one displaced stock instruction
# `move.l #96,%macsr` (a93c 0000 0060, replayed verbatim) is left out of the simulated text only.
assert SRC.count('move.l  #96,%macsr') == 1
SRC = SRC.replace('move.l  #96,%macsr', '| (MACSR replay: not simulated)')
WEIGHTS, CURVE, XF, TEMPO24, TRANSPORT, HELD, NOTIFY, RESUME = (
    0x80003c60, 0x400bcd90, 0x460d16c8, 0x8000181c, 0x800065b8, 0x460fab40, 0x4005a2b8, 0x4000cc6c)
STEPW, BANK_PTR, PAT_IDX, PAT_STRIDE, TRK_STRIDE = 0x800065b2, 0x46c82456, 0x100b14d0, 0x8ed8, 0x91a
BANK = 0x41000000
fails = 0
def check(name, ok, info=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + (('   [' + info + ']') if info else ''))
    if not ok: fails += 1

img = os.path.join(ROOT, 'out', 'raw', 'section_3_MAIN_OS.bin')
real = os.path.exists(img)
if real:
    b = open(img, 'rb').read(); base = 0x40000400
    curve = [struct.unpack('>h', b[CURVE - base + 2 * i:CURVE - base + 2 * i + 2])[0] for i in range(128)]
else:
    curve = [-(127 - x) * 258 for x in range(128)]          # injective stand-in: xf 127 = 0 = all A
def stock_weight(xf):
    w = curve[xf] & 0xffff
    return ((w << 16) | ((0xffff8000 - w) & 0xffff)) & 0xffffffff
WMAP = {stock_weight(x): x for x in range(128)}

toasts = []
def notify(cpu):                     # reached by jmp (args above the return) or by jsr (args at a7)
    a = cpu.mem.r(cpu.a[7], 'l')
    toasts.append(a if a == C['lp_tbuf'] else cpu.mem.r(cpu.a[7] + 4, 'l'))
# ---- the window's firmware, mocked (reached by jsr: the first argument at a7)
WCREATE, WFRAME, WDESTROY, CLEAR, TEXT, TWIDTH, RULE, INVERT, SPRINTF, LPUSH, LPOP, TIMER, UNTIMER = (
    0x4005829c, 0x40056f4c, 0x40055db4, 0x40035624, 0x40012bd8, 0x40012f30, 0x40011910, 0x40012254,
    0x40013a08, 0x40031494, 0x4003146c, 0x40031a0c, 0x40031abc)
WIN = 0x48000000
ui = dict(win_args=None, texts=[], layers=[], timers={}, untimers=[], destroyed=0, boxes=[], nums=[], sprites=[],
          stock=[])
NUMTEXT, SPRITE, SC_SPR, SC_FMT, SC_W, STOCK_TKEY, ROWS, MIDIMODE, PART = (
    0x40013904, 0x400128a8, 0x400bcd7c, 0x400b437c, 0x400b4382, 0x40040250, 0x46100b18, 0x80000012, 0x80000003)
def arg(cpu, i): return cpu.mem.r(cpu.a[7] + 4 * i, 'l')
def cstr(a):
    s = b''
    while True:
        c = mem.r(a, 'b')
        if not c: return s.decode()
        s += bytes([c]); a += 1
def h_wcreate(cpu): ui['win_args'] = [arg(cpu, i) for i in range(6)]; cpu.d[0] = WIN
def h_wdestroy(cpu): mem.w(arg(cpu, 0), 'l', 0); ui['destroyed'] += 1
def h_clear(cpu): ui['texts'] = []; ui['boxes'] = []; ui['nums'] = []; ui['sprites'] = []
def s32(x): return x - (1 << 32) if x & 0x80000000 else x
def h_invert(cpu): ui['boxes'].append(tuple(s32(arg(cpu, i)) for i in range(1, 6)))
def h_numtext(cpu): ui['nums'].append(tuple(arg(cpu, i) for i in range(1, 9)))
def h_sprite(cpu): ui['sprites'].append((arg(cpu, 0), arg(cpu, 2), arg(cpu, 3)))
def h_stock(cpu):                    # the stock track handler: HELD follows the key
    code, ev = arg(cpu, 0), arg(cpu, 1); ui['stock'].append((code, ev)); t = code - 0x10
    h = mem.r(HELD, 'l'); mem.w(HELD, 'l', h | (1 << t) if ev == 1 else h & ~(1 << t))
def h_text(cpu): ui['texts'].append((arg(cpu, 2), arg(cpu, 3), cstr(arg(cpu, 5))))
def h_twidth(cpu): cpu.d[0] = 6 * len(cstr(arg(cpu, 2)))
def h_sprintf(cpu):
    buf, fmt = arg(cpu, 0), cstr(arg(cpu, 1)); out = ''; i = 0; n = 2
    while i < len(fmt):
        if fmt[i] == '%' and fmt[i + 1] == 'd': out += str(arg(cpu, n) - (1 << 32) * (arg(cpu, n) >> 31)); n += 1; i += 2
        elif fmt[i] == '%' and fmt[i + 1] == 's': out += cstr(arg(cpu, n)); n += 1; i += 2
        else: out += fmt[i]; i += 1
    for j, ch in enumerate(out.encode() + b'\0'): mem.w(buf + j, 'b', ch)
def h_lpush(cpu): ui['layers'].append(arg(cpu, 0))
def h_lpop(cpu):
    a = arg(cpu, 0)
    assert a in ui['layers'], 'LPOP of a layer not pushed'
    ui['layers'].remove(a)
def h_timer(cpu): s = 7 + len(ui['timers']); ui['timers'][s] = (arg(cpu, 0), arg(cpu, 1)); cpu.d[0] = s
def h_untimer(cpu): ui['untimers'].append(arg(cpu, 0)); ui['timers'].pop(arg(cpu, 0), None)
noop = lambda c: None
# ---- STORE's file calls, mocked: a dict of paths (modules/store/store.s: registers in, d0 out)
STORE = dict(store_path=0x4f000000, store_fopen=0x4f000010, store_fread=0x4f000020,
             store_fwrite=0x4f000030, store_fclose=0x4f000040, store_crc32=0x4f000050,
             store_refuse=0x4f000060)
F_COPY = 0x40016388
files, opened, refused, writes = {}, {}, [], []
def s_path(cpu):
    fmt = cstr(cpu.a[0]); out = fmt.replace('%s', '/P')
    for j, ch in enumerate(out.encode() + b'\0'): mem.w(cpu.a[1] + j, 'b', ch)
def s_fopen(cpu):
    path, mode = cstr(cpu.a[0]), cstr(cpu.a[1])
    if mode == 'r' and path not in files: cpu.d[0] = 0xffffffff; return
    opened[cpu.a[2]] = dict(path=path, mode=mode, pos=0, data=bytearray(files.get(path, b'')) if mode == 'r' else bytearray())
    cpu.d[0] = 0
def s_fread(cpu):
    f = opened[cpu.a[2]]; n = cpu.d[0]
    if f['pos'] + n > len(f['data']): cpu.d[0] = 0; return
    for j in range(n): mem.w(cpu.a[0] + j, 'b', f['data'][f['pos'] + j])
    f['pos'] += n; cpu.d[0] = 1
def s_fwrite(cpu):
    f = opened[cpu.a[2]]; f['data'] += bytes(mem.r(cpu.a[0] + j, 'b') for j in range(cpu.d[0])); cpu.d[0] = 1
def s_fclose(cpu):
    f = opened.pop(cpu.a[2], None)
    if f and f['mode'] == 'w': files[f['path']] = bytes(f['data']); writes.append(f['path'])
def s_crc(cpu):
    import zlib
    cpu.d[0] = zlib.crc32(bytes(mem.r(cpu.a[0] + j, 'b') for j in range(cpu.d[0])), cpu.d[1])
def s_refuse(cpu): refused.append((cpu.d[0], cpu.d[1]))
def f_copy(cpu):
    dst, src = cstr(arg(cpu, 0)), cstr(arg(cpu, 1))
    if src in files: files[dst] = files[src]; cpu.d[0] = 0
    else: cpu.d[0] = 0xffffffff
mem = Mem()
cpu = CPU(SRC, mem, defsyms=STORE, hooks={STORE['store_path']: s_path, STORE['store_fopen']: s_fopen,
                           STORE['store_fread']: s_fread, STORE['store_fwrite']: s_fwrite,
                           STORE['store_fclose']: s_fclose, STORE['store_crc32']: s_crc,
                           STORE['store_refuse']: s_refuse, F_COPY: f_copy,NOTIFY: notify, RESUME: noop, WCREATE: h_wcreate, WFRAME: noop,
                           WDESTROY: h_wdestroy, CLEAR: h_clear, TEXT: h_text, TWIDTH: h_twidth,
                           RULE: noop, INVERT: h_invert, SPRINTF: h_sprintf, LPUSH: h_lpush, LPOP: h_lpop,
                           TIMER: h_timer, UNTIMER: h_untimer, NUMTEXT: h_numtext, SPRITE: h_sprite,
                           STOCK_TKEY: h_stock})
check('cfsim_lint_and_load', True, '%d instructions' % len(cpu.prog))
for i, v in enumerate(curve): mem.w(CURVE + 2 * i, 'w', v & 0xffff)
C = cpu.consts
SP = 0x47000000

def key(label, held=None, ev=1):
    if held is not None: mem.w(HELD, 'l', held)
    mem.w(SP - 8, 'l', 0x33); mem.w(SP - 4, 'l', ev)         # (keycode, event) above the return address
    cpu.a[7] = SP - 8; cpu.call(label)
def enc(i, delta):
    mem.w(SP - 8, 'l', i); mem.w(SP - 4, 'l', delta & 0xffffffff)
    cpu.a[7] = SP - 8; cpu.call('mw_enc')
def tick():
    cpu.a[7] = SP; cpu.call('mw_tick')
def win(): return mem.r(C['mw_win'], 'l')
def start(held):                     # [TRACK]+[UP] opens the window, YES closes it and starts
    key('morph_up', held); key('mw_yes')
def tkey(code, ev):                  # a track key through the key table's press field
    mem.w(SP - 8, 'l', code); mem.w(SP - 4, 'l', ev); cpu.a[7] = SP - 8; cpu.call('lp_tpress')
def lp_ticks(n):                     # the long press's soft timer, n times (while it runs)
    for _ in range(n):
        if mem.r(C['lp_timer'], 'l') == 0xffffffff: return
        cpu.a[7] = SP; cpu.call('lp_tick')
def long_press(t, hold=70):          # T(t+1) down alone ~1 s (LONG = 58 ticks), then up
    tkey(0x10 + t, 1); lp_ticks(hold); tkey(0x10 + t, 0)
def prime(t): return bool(mem.r(C['mp_prime'], 'l') >> t & 1)
def text(a):
    s = b''
    while True:
        c = mem.r(a, 'b')
        if not c: return s.decode()
        s += bytes([c]); a += 1

class Seq:
    """The sequencer: the step word moves every 992,250 / tempo24 frames while playing."""
    def __init__(s): s.acc = 0.0; s.w = 0; s.steps = 0
    def frame(s):
        if mem.r(TRANSPORT, 'l') == 1:
            s.acc += mem.r(TEMPO24, 'l') / 992250.0
            if s.acc >= 1.0:
                s.acc -= 1.0; s.w = (s.w + 1) & 0xffff; s.steps += 1
                mem.w(STEPW, 'w', s.w)
        cpu.a[7] = SP; cpu.call('mf_body')
seq = Seq()
def frame(n=1):
    for _ in range(n): seq.frame()
def to_next_step():                  # frames until the step word moves (it moves inside that frame)
    s0 = seq.steps
    while seq.steps == s0: frame()
def state(t): return mem.r(C['mp_state'] + t, 'b')
def weight(t): return mem.r(WEIGHTS + 4 * t, 'l')
def xf_of(t): return WMAP.get(weight(t))
def settings(t, steps, mult, mode):
    a = C['mp_set'] + 4 * t
    mem.w(a, 'b', steps); mem.w(a + 1, 'b', mult); mem.w(a + 2, 'b', mode)
def tri(k, n, sub=0):               # the expected xf for k steps (+ sub/256 of a step) into an n-step cycle
    x = (k * 256 + sub) // n
    return 127 - x if x <= 127 else x - 128

BPM = 130; mem.w(TEMPO24, 'l', BPM * 24); mem.w(TRANSPORT, 'l', 1); mem.w(XF, 'l', 64)
for t in range(8): mem.w(WEIGHTS + 4 * t, 'l', 0x12345678)
FPS = 992250 / (BPM * 24)           # frames a step

frame(10)
check('idle_leaves_every_weight', all(weight(t) == 0x12345678 for t in range(8)))
check('defaults_are_v0', all(mem.r(C['mp_set'] + 4 * t, 'b') == 16 and mem.r(C['mp_set'] + 4 * t + 1, 'b') == 8
                            for t in range(8)))
key('morph_down', 0b1)
check('down_on_a_fader_track_does_nothing', state(0) == 0)

# ---- start: armed until the next step, then from A
key('morph_up', 0b101)    # T1 and T3: the window
check('up_opens_the_window', win() == WIN and ui['win_args'][:2] == [116, 64] and ui['win_args'][4] == 5
      and C['MW_LAYER'] in ui['layers'] and len(ui['timers']) == 1)
def ext(t, ret, curv, end):
    a = C['mp_ext'] + 4 * t
    mem.w(a, 'b', ret); mem.w(a + 1, 'b', curv); mem.w(a + 2, 'b', end)
def ext_of(t): return [mem.r(C['mp_ext'] + 4 * t + i, 'b') for i in range(4)]
def rows():                          # v1.2: y -> the texts of that row, left to right
    r = {}
    for x, y, s in sorted(ui['texts']): r.setdefault(y, []).append(s)
    return {y: tuple(v) for y, v in r.items()}
rr = rows()
check('window_paint', rr.get(52) == ('MORPH', 'T13', 'ARM') and rr.get(45) == ('CYCLE 128',)
      and rr.get(38) == ('STEPS (A)', '16') and rr.get(31) == ('x (B)', '8')
      and rr.get(24) == ('MODE (C)', 'SMOOTH') and rr.get(17) == ('RET (D)', 'SAME')
      and rr.get(10) == ('CURV (E)', 'LIN') and rr.get(3) == ('END (F)', 'LOOP'),
      str(sorted(ui['texts'], key=lambda r: -r[1])))
def no_overlap():                    # (the mock's 6 px a character: wider than the unit's font)
    t = sorted(ui['texts'], key=lambda r: (r[1], r[0]))
    return all(not (a[1] == b[1] and a[0] + 6 * len(a[2]) > b[0]) for a, b in zip(t, t[1:]))
check('window_rows_fit', all(3 <= y and y + 6 <= 58 for x, y, s in ui['texts'])   # v1.1's y 3..58
      and all(x + 6 * len(s) <= 116 for x, y, s in ui['texts']) and no_overlap()
      and all(x + 6 * len(s) < C['X_SC'] for x, y, s in ui['texts'] if y == C['Y_SC'])
      and len(set(y for x, y, s in ui['texts'])) == 8, str(ui['texts']))
check('up_holds_the_window_tracks', (state(0), state(1), state(2)) == (5, 0, 5))
for _ in range(3): to_next_step()
check('held_does_not_start_while_the_window_is_open', (state(0), state(2)) == (5, 5)
      and weight(0) == 0x12345678)
enc(1, -6); tick()
check('cycle_follows_the_settings', rows().get(45, ('',))[0] == 'CYCLE 32')
enc(1, 6)
mem.w(HELD, 'l', 0); tick(); tick()
check('release_leaves_it_open', win() == WIN and (state(0), state(2)) == (5, 5))
st = toasts[:]; key('mw_yes')
check('yes_closes_and_arms', win() == 0 and not ui['layers'] and not ui['timers'] and toasts == st
      and (state(0), state(1), state(2)) == (4, 0, 4) and prime(0) and prime(2) and not prime(1))
frame()
check('armed_leaves_the_weight_until_the_step', weight(0) == 0x12345678 or seq.steps > 0)
to_next_step()
check('starts_on_the_step_on_a', state(0) == 1 and xf_of(0) == 127, 'xf %s' % xf_of(0))
check('fader_track_untouched', weight(1) == 0x12345678)

# ---- SMOOTH, 16 x 8 = 128 steps: B at step 64, A again at 128, no jump
xs = [xf_of(0)]; ks = [0]; s0 = seq.steps
while seq.steps - s0 < 130:
    frame(); xs.append(xf_of(0)); ks.append(seq.steps - s0)
iB = xs.index(0)
check('every_weight_is_a_stock_weight', all(x is not None for x in xs))
check('reaches_b_at_step_64', abs(ks[iB] - 64) <= 1, 'B at step %d' % ks[iB])
iA = next(i for i in range(iB, len(xs)) if xs[i] == 127)
check('back_on_a_at_step_128', abs(ks[iA] - 128) <= 1, 'A again at step %d' % ks[iA])
check('smooth_no_jump', max(abs(xs[i + 1] - xs[i]) for i in range(len(xs) - 1)) <= 1)
check('step_aligned_values', all(xs[i] == tri(ks[i] % 128, 128) for i in range(1, len(xs))
                                 if ks[i] != ks[i - 1]), 'xf on each step\'s first frame = the triangle')
if real:
    check('weight_word_is_the_stock_writers', all(x is not None for x in xs), 'curve from out/raw')
else:
    print('SKIP  weight_word_is_the_stock_writers: no out/raw/section_3_MAIN_OS.bin (stand-in curve)')

# ---- the transport stopped: everything holds
mem.w(TRANSPORT, 'l', 2); before = weight(0); frame(200)
check('stopped_transport_holds', weight(0) == before)
mem.w(TRANSPORT, 'l', 1)

# ---- up on a running track: ignored
k = mem.r(C['mp_k'], 'l'); key('morph_up', 0b1); tick(); key('mw_no')
check('window_on_running_changes_nothing', mem.r(C['mp_k'], 'l') == k and state(0) == 1)
k = mem.r(C['mp_k'], 'l'); key('morph_up', 0b1); tick(); key('mw_yes')
check('yes_on_running_changes_nothing', mem.r(C['mp_k'], 'l') == k and state(0) == 1)

# ---- TRIG HOLD, 8 x 1: the step's value for the whole step, 8 values a cycle
key('morph_down', 0b101)
n = 0
while (state(0) == 2 or state(2) == 2) and n < 140 * FPS: frame(); n += 1
settings(0, 8, 1, 1)
mem.w(XF, 'l', 127); frame(); frame()   # both re-attach
start(0b1); to_next_step()
vals = []; s0 = seq.steps; per = {}
while seq.steps - s0 < 16:
    frame(); per.setdefault(seq.steps - s0, set()).add(xf_of(0))
check('trig_hold_one_value_per_step', all(len(v) == 1 for v in per.values()), str({k: sorted(v) for k, v in per.items()}))
got = [per[k].copy().pop() for k in range(0, 16)]
check('trig_hold_values', got == [tri(k % 8, 8) for k in range(16)], str(got))

# ---- STEPS 0 = the track's length (32) x 2 = 64 steps
key('morph_down', 0b1)
while state(0) == 2: frame()
mem.w(BANK_PTR, 'l', BANK); mem.w(PAT_IDX, 'b', 3)
mem.w(BANK + 3 * PAT_STRIDE + 0 * TRK_STRIDE + 0x50, 'b', 32)
settings(0, 0, 2, 0)
mem.w(XF, 'l', 127); frame()
start(0b1); to_next_step()
xs = []; ks = []; s0 = seq.steps
while seq.steps - s0 < 66:
    frame(); xs.append(xf_of(0)); ks.append(seq.steps - s0)
check('steps_0_is_the_track_length', abs(ks[xs.index(0)] - 32) <= 1 and
      abs(ks[next(i for i in range(xs.index(0), len(xs)) if xs[i] == 127)] - 64) <= 1)

# ---- stop: finishes the cycle on A, then parks; the fader takes it back only at A
key('morph_down', 0b1)
check('down_sets_stopping', state(0) == 2)
check('toast_morph_stop', text(toasts[-1]) == 'MORPH STOP')
n = 0
while state(0) == 2 and n < 70 * FPS: frame(); n += 1
check('stops_at_end_of_cycle_on_a', state(0) == 3 and xf_of(0) == 127)
mem.w(XF, 'l', 30); mem.w(WEIGHTS, 'l', stock_weight(30)); frame()
check('parked_holds_a_against_the_fader', xf_of(0) == 127 and state(0) == 3)
mem.w(XF, 'l', 127); mem.w(WEIGHTS, 'l', stock_weight(127)); frame()
check('reattaches_at_fader_a', state(0) == 0)
mem.w(XF, 'l', 10); mem.w(WEIGHTS, 'l', stock_weight(10)); frame()
check('then_follows_the_fader', xf_of(0) == 10)

# ---- cancel, re-arm, armed then down
settings(2, 16, 8, 0)
start(0b100); to_next_step(); key('morph_down', 0b100); start(0b100)
check('up_cancels_a_stop', state(2) == 1)
key('morph_down', 0b100)
while state(2) == 2: frame()
key('morph_up', 0b100)
check('up_on_parked_holds_it_from_park', state(2) == 6)
mem.w(XF, 'l', 30); frame()
check('held_from_park_keeps_a', xf_of(2) == 127 and state(2) == 6)
key('mw_no')
check('no_parks_it_again', state(2) == 3 and win() == 0 and prime(2))
start(0b100)
check('up_on_parked_arms', state(2) == 4)
key('morph_down', 0b100)
check('down_on_armed_back_to_the_fader', state(2) == 0)

# ---- extremes: N = 512 and N = 1
settings(3, 64, 8, 0); mem.w(XF, 'l', 127)
start(0b1000); to_next_step(); s0 = seq.steps; xs = []
while seq.steps - s0 < 300: frame(); xs.append(xf_of(3))
check('n_512_reaches_b_at_256', xs.index(0) > 0 and abs(seq.steps - s0 - 300) <= 1 and min(xs) == 0)
settings(4, 1, 1, 1); start(0b10000); to_next_step(); frame(); a = xf_of(4); to_next_step(); frame()
check('n_1_trig_hold_is_a', a == 127 and xf_of(4) == 127)

# ---- the master switch
# ---- the window: encoders, release of the track keys, DOWN, several tracks
mem.w(XF, 'l', 64)
key('morph_up', 0b11000000)          # T7 and T8
enc(0, -20); enc(1, 3); enc(2, 1)
s6, s7 = [[mem.r(C['mp_set'] + 4 * t + i, 'b') for i in range(3)] for t in (6, 7)]
check('enc_sets_every_window_track', s6 == s7 == [0, 11, 1], '%s %s' % (s6, s7))
rr = rows()
check('window_shows_trk_and_hold', rr.get(38, ('',))[-1] == 'TRK' and rr.get(24, ('',))[-1] == 'HOLD'
      and rr.get(52, ('', ''))[1] == 'T78', str(rr))
enc(0, 100); enc(1, -20); enc(2, -1)
check('enc_clamps', [mem.r(C['mp_set'] + 4 * 6 + i, 'b') for i in range(3)] == [64, 1, 0])
enc(3, 5); enc(0, 0)
check('enc_d_leaves_a_b_c_and_zero_does_nothing', [mem.r(C['mp_set'] + 4 * 6 + i, 'b') for i in range(3)] == [64, 1, 0]
      and ext_of(6)[0] == 1)
enc(3, -1)
check('enc_d_back', ext_of(6) == ext_of(7) == [0, 0, 0, 0])
enc(1, 30)
check('x_goes_past_16', mem.r(C['mp_set'] + 4 * 6 + 1, 'b') == 31)
enc(1, 200)
rr = rows()
check('x_stops_at_100', mem.r(C['mp_set'] + 4 * 6 + 1, 'b') == 100 and rr.get(31, ('',))[-1] == '100'
      and rr.get(45, ('',))[0] == 'CYCLE 6400', str((rr.get(31), rr.get(45))))
enc(1, 5)
check('no_easter_egg', mem.r(C['mp_set'] + 4 * 6 + 1, 'b') == 100)
settings(6, 16, 8, 0); settings(7, 16, 8, 0)
mem.w(HELD, 'l', 0); tick()
check('open_after_the_release', win() == WIN)
key('mw_yes'); to_next_step(); frame(5)
check('yes_tracks_run', state(6) == 1 and state(7) == 1)
key('morph_up', 0b11000000); tick()
rr = rows(); st45 = rr.get(45, ('',))[0]
check('reopen_keeps_running', state(6) == 1 and state(7) == 1)
check('window_shows_on_and_the_step', rr.get(52, ('',))[-1] == 'ON' and st45.startswith('STEP ')
      and st45.endswith('/128'), str((rr.get(52), st45)))
n0 = len(ui['texts']); tick()
check('tick_repaints_only_on_change', len(ui['texts']) == n0)
key('mw_down')
check('down_in_the_window_stops', state(6) == 2 and state(7) == 2)
mem.w(HELD, 'l', 0); tick()
check('still_open_after_the_release', win() == WIN)
key('mw_no')
check('no_closes', win() == 0 and not ui['layers'] and not ui['timers'] and state(6) == 2)
key('mw_no')
check('close_twice_is_safe', win() == 0 and not ui['layers'])
key('morph_up', 0b1); key('morph_up', 0b1)
check('up_again_toggles_closed', win() == 0 and not ui['layers'])
mem.w(C['mp_state'], 'b', 0)
key('morph_up', 0b1); cpu.a[7] = SP; cpu.call('mw_closed')      # another TEMPO-class window took over
check('evicted_drops_layer_and_timer', win() == 0 and not ui['layers'] and not ui['timers'])
check('evicted_starts_nothing', state(0) == 0)
key('morph_up', 0, 1)
check('up_with_no_track_held_does_nothing', win() == 0)

# ---- the scene indicator (stock's footer calls, moved to x 89, y 3: stock's x 95..117, y 0..6)
mem.w(BANK_PTR, 'l', BANK); mem.w(PART, 'b', 2)
mem.w(BANK + 2 * 0x18b2 + 0x8ed90, 'b', 0); mem.w(BANK + 2 * 0x18b2 + 0x8ed91, 'b', 8)   # scenes 1 and 9
for t in range(8): mem.w(C['mp_state'] + t, 'b', 0)
mem.w(XF, 'l', 127)
key('morph_up', 0b1)
dx, dy = C['X_SC'] - 95, C['Y_SC']
stock = [(95, 0, 103, 6, 1), (109, 0, 117, 6, 1), (104, 0, 108, 6, 1), (104, 2, 108, 4, 0)]
moved = [(a + dx, b + dy, c + dx, d + dy, m) for a, b, c, d, m in stock]
check('indicator_boxes_are_stocks_moved', all(b in ui['boxes'] for b in moved), str(ui['boxes']))
check('indicator_numbers_are_stocks_calls',      # (surface, x, y, align, inverted, "00", "%02d", n)
      sorted(nm[1:] for nm in ui['nums']) ==
      sorted([(0x60 + dx, 1 + dy, 0, 1, SC_W, SC_FMT, 1), (0x6e + dx, 1 + dy, 0, 1, SC_W, SC_FMT, 9)]),
      str(ui['nums']))
def spr_idx(): return [(mem.r(SC_SPR + 4 * i, 'l')) for i in range(5)]
for i in range(5): mem.w(SC_SPR + 4 * i, 'l', 0x40ab0000 + i)
def shown_pos():
    cpu.a[7] = SP; cpu.call('mw_draw')
    (sp, x, y), = ui['sprites']
    return sp - 0x40ab0000, x, y
pos = []
for xf in (127, 112, 111, 80, 79, 48, 47, 16, 15, 0):
    mem.w(XF, 'l', xf); pos.append(shown_pos()[0])
check('indicator_follows_the_fader_as_stock', pos == [max(0, min(4, 4 - ((xf + 16) >> 5))) for xf in
      (127, 112, 111, 80, 79, 48, 47, 16, 15, 0)], str(pos))
check('indicator_sprite_at_stocks_place', shown_pos()[1:] == (104 + dx, 2 + dy))
settings(0, 16, 8, 0)
key('mw_yes'); to_next_step()
mem.w(XF, 'l', 0)
key('morph_up', 0b1); n0 = len(ui['texts'])
p0 = shown_pos()[0]
check('indicator_shows_the_morph_not_the_fader', p0 == 0, str(p0))       # on A at the start
n = 0
while mem.r(C['mp_k'], 'l') < 64 and n < 80 * FPS: frame(); n += 1
p1 = shown_pos()[0]
check('indicator_moves_with_the_morph', p1 == 4, str(p1))              # on B at the middle
n0 = len(ui['boxes']); mem.w(BANK + 2 * 0x18b2 + 0x8ed91, 'b', 3); tick()
check('a_scene_change_repaints', any(n[7] == 4 for n in ui['nums']), str(ui['nums']))
key('mw_no'); key('morph_down', 0b1)
while state(0) == 2: frame()
mem.w(XF, 'l', 127); frame()

# ---- the long press: on an ARMED track, a track key held ~1 s alone starts and stops its morph
for t in range(8): mem.w(C['mp_state'] + t, 'b', 0)
mem.w(C['mp_prime'], 'l', 0); mem.w(HELD, 'l', 0); mem.w(ROWS, 'l', 0); mem.w(ROWS + 4, 'l', 0)
settings(1, 2, 2, 0)
toasts.clear(); long_press(1)
check('long_press_on_a_track_never_armed_does_nothing', state(1) == 0 and not toasts)
check('long_press_calls_stock_first', ui['stock'][-2:] == [(0x11, 1), (0x11, 0)])
key('morph_up', 0b10); mem.w(HELD, 'l', 0); key('mw_no')
check('no_arms_for_the_long_press', prime(1) and state(1) == 0)
long_press(1)
check('long_press_starts', state(1) == 4 and text(toasts[-1]) == 'T2 MORPH ON', str(toasts and text(toasts[-1])))
to_next_step()
check('long_press_start_on_the_next_step', state(1) == 1)
long_press(1)
check('long_press_again_stops_at_the_cycles_end', state(1) == 2 and text(toasts[-1]) == 'T2 MORPH OFF')
n = 0
while state(1) == 2 and n < 20 * FPS: frame(); n += 1
check('then_parked_on_a', state(1) == 3 and xf_of(1) == 127)
long_press(1)
check('and_again_starts', state(1) == 4)
long_press(1)
check('waiting_then_off_back_to_the_fader', state(1) == 0 and text(toasts[-1]) == 'T2 MORPH OFF')
tkey(0x11, 1); lp_ticks(30); tkey(0x11, 0); lp_ticks(60)
check('a_short_press_does_nothing', state(1) == 0)
tkey(0x11, 1); lp_ticks(20); mem.w(HELD, 'l', mem.r(HELD, 'l') | 1); lp_ticks(60); tkey(0x11, 0)
mem.w(HELD, 'l', 0)
check('another_track_key_cancels', state(1) == 0)
tkey(0x11, 1); lp_ticks(20); mem.w(ROWS, 'l', 0x00000001); lp_ticks(60); tkey(0x11, 0); mem.w(ROWS, 'l', 0)
check('another_key_cancels', state(1) == 0)
mem.w(ROWS + 4, 'l', 0x00200000); tkey(0x11, 1); lp_ticks(70); tkey(0x11, 0); mem.w(ROWS + 4, 'l', 0)
check('func_down_is_a_mute_not_a_morph', state(1) == 0)
mem.w(MIDIMODE, 'b', 1); long_press(1); mem.w(MIDIMODE, 'b', 0)
check('midi_mode_does_nothing', state(1) == 0)
key('morph_up', 0b10); tkey(0x11, 1); lp_ticks(70); tkey(0x11, 0)
check('our_window_open_does_nothing', state(1) == 5)
key('mw_no')
check('timer_gone', mem.r(C['lp_timer'], 'l') == 0xffffffff and mem.r(C['lp_cand'], 'l') == 0xffffffff)
long_press(1); to_next_step()
check('long_press_starts_again', state(1) == 1)   # (with the MIXER open: on the port, not here)
long_press(1)
while state(1) == 2: frame()
mem.w(XF, 'l', 127); frame()

# ---- the review's cases (26 Oct 2026)
for t in range(8): mem.w(C['mp_state'] + t, 'b', 0)
mem.w(C['mp_prime'], 'l', 0b100); mem.w(HELD, 'l', 0); mem.w(XF, 'l', 127)
tkey(0x12, 1); lp_ticks(70)                     # T3 held past a second: the long press fires...
check('slow_track_up_fires_first', state(2) == 4)
key('morph_up')                                 # ... then UP (T3 still held): undone, the window
check('slow_track_up_undoes_the_long_press', state(2) == 5 and win() == WIN, str(state(2)))
mem.w(HELD, 'l', 0); key('mw_no')
check('then_no_starts_nothing', state(2) == 0)
mem.w(C['mp_state'] + 2, 'b', 1)                # morphing, T3 held past a second, then DOWN
tkey(0x12, 1); lp_ticks(70)
check('long_press_stops_it', state(2) == 2)
key('morph_down', None)
check('slow_track_down_undoes_then_stops', state(2) == 2 and mem.r(C['lp_ut'], 'l') == 0xffffffff)
tkey(0x12, 0)
mem.w(C['mp_state'] + 2, 'b', 0)
long_press(2); to_next_step()                   # a long press, released: it stands
key('morph_up', 0b100)
check('a_released_long_press_stands', state(2) == 1, str(state(2)))
key('mw_no')
mem.w(C['mp_prime'], 'l', 0)                    # a project loaded with the window open
key('morph_up', 0b10000); mem.w(HELD, 'l', 0)
cpu.a[7] = SP; cpu.call('mrp_st_newproj')
key('mw_no')
check('a_load_meanwhile_arms_nothing', mem.r(C['mp_prime'], 'l') == 0)
_wc = cpu.hooks[WCREATE]; cpu.hooks[WCREATE] = lambda c: c.d.__setitem__(0, 0)
key('morph_up', 0b100000)
cpu.hooks[WCREATE] = _wc
check('no_window_arms_nothing', mem.r(C['mp_prime'], 'l') == 0 and state(5) == 0)
for t in range(8): mem.w(C['mp_state'] + t, 'b', 0)

# ---- saving: morph.work through STORE
import zlib
def ev(name): cpu.a[7] = SP; cpu.call('mrp_st_' + name)
def setall(states):
    for i, s in enumerate(states): mem.w(C['mp_state'] + i, 'b', s)
W, S = '/P/morph.work', '/P/morph.strd'
files.clear(); writes.clear()
for i in range(8): settings(i, 16, 8, 0)
setall([0] * 8); ev('newproj'); ev('bankw_post')
check('save_untouched_writes_nothing', not writes and W not in files)
mem.w(C['mp_prime'], 'l', 0b10100)
settings(0, 8, 2, 1); settings(4, 0, 17, 0); setall([1, 0, 0, 0, 4, 0, 3, 0]); ev('bankw_post')
f = files.get(W, b'')
ok = (len(f) == 56 and f[:4] == b'MRPW' and struct.unpack('>III', f[4:16]) == (2, 40, zlib.crc32(f[16:]))
      and f[16:20] == bytes([8, 2, 1, 0]) and f[32:36] == bytes([0, 17, 0, 0]) and f[48] == 0b10001
      and f[49] == 0b10100 and f[50:] == bytes(6))
check('save_writes_morph_work', ok, f.hex())
n = len(writes); ev('pstore_pre')
check('save_unchanged_writes_once', len(writes) == n)
ev('pstore_post')
check('store_copies_to_strd', files.get(S) == f)
settings(0, 16, 8, 0); settings(4, 16, 8, 0); setall([0, 1, 0, 0, 0, 0, 0, 0])
mem.w(C['mp_prime'], 'l', 0)
ev('loadall_post')
check('load_restores_the_armed_tracks', mem.r(C['mp_prime'], 'l') == 0b10100)
check('load_restores_settings', [mem.r(C['mp_set'] + i, 'b') for i in range(4)] == [8, 2, 1, 0]
      and mem.r(C['mp_set'] + 17, 'b') == 17)
check('load_arms_the_morphing_tracks', [state(i) for i in range(8)] == [4, 3, 0, 0, 4, 0, 0, 0],
      str([state(i) for i in range(8)]))
n = len(writes); ev('bankw_post')
check('load_then_save_writes_nothing', len(writes) == n)
settings(1, 32, 4, 0); ev('bankw_post')
check('a_change_writes', len(writes) == n + 1 and files[W] != files[S])
ev('preload_post')
check('reload_returns_to_the_saved_copy', files[W] == files[S] and mem.r(C['mp_set'] + 4, 'b') == 16)
files[W] = files[W][:20] + b'\x63' + files[W][21:]                  # a bad CRC
refused.clear(); good = files[W]; ev('loadall_post')
check('bad_file_is_refused', refused == [(4, 0)] and mem.r(C['mp_set'], 'b') == 16
      and all(state(i) in (0, 3) for i in range(8)))
settings(2, 5, 5, 0); ev('bankw_post')
check('refused_file_is_never_written_over', files[W] == good)
cpu.d[0] = 2; cpu.a[7] = SP; cpu.call('mrp_st_answer'); ev('bankw_post')
check('backup_answer_keeps_bak_then_writes', files.get('/P/morph.bak') == good and files[W] != good
      and files[W][:4] == b'MRPW')
del files[W]; setall([1, 0, 0, 0, 0, 0, 0, 0]); ev('loadmask_post')
check('no_file_defaults_and_parks', mem.r(C['mp_set'] + 9, 'b') == 8 and state(0) == 3)

# version 1 (v1): its x 17 was 41.625 -> 42; read as before otherwise
files.clear()
pl = bytes([16, 17, 0, 0] + [16, 8, 0, 0] * 7 + [0] * 8)
files[W] = b'MRPW' + struct.pack('>III', 1, 40, zlib.crc32(pl)) + pl
ev('loadall_post')
check('v1_file_x17_is_42', mem.r(C['mp_set'] + 1, 'b') == 42 and mem.r(C['mp_prime'], 'l') == 0)
pl = bytes([16, 17, 0, 0] + [16, 8, 0, 0] * 7 + [0] * 8)
files[W] = b'MRPW' + struct.pack('>III', 2, 40, zlib.crc32(pl)) + pl
ev('loadall_post')
check('v2_file_x17_is_17', mem.r(C['mp_set'] + 1, 'b') == 17)
files[W] = b'MRPW' + struct.pack('>III', 3, 40, zlib.crc32(pl)) + pl
refused.clear(); ev('loadall_post')
check('version_3_of_40_bytes_is_refused', refused == [(4, 0)])
files[W] = b'MRPW' + struct.pack('>III', 4, 72, zlib.crc32(pl + bytes(32))) + pl + bytes(32)
refused.clear(); ev('loadall_post')
check('version_4_is_refused', refused == [(4, 0)])

# ---- v1.2 (22 Nov 2026): RET, CURV, END on encoders D, E, F (mp_ext); all 0 = v1.1 (every check
#      above ran with them 0: the triangle, its length, SMOOTH, the stop, the saving as version 2)
def tlen(n, ret): return n << (7 - ret) if ret < 5 else (4096, 1024, 256, 0)[ret - 5]
def model(pos, n, ret, curv):        # the xf the frame should write pos/256 steps into the cycle
    L, T = n * 128, tlen(n, ret)
    if pos < L:
        v = pos * 256 // L
        if curv & 2: v = v * v >> 8
        return 127 - (v >> 1)
    if T == 0: return 127
    u = min(255, (pos - L) * 256 // T)
    return 127 - ((255 - u) ** 2 >> 9) if curv & 1 else u >> 1
def cyc(n, ret, end): return -(-(n * 128 + (0 if end == 2 else tlen(n, ret))) // 256)
def hop():                           # one step in one frame (the step word moves; TRIG HOLD tests)
    seq.w = (seq.w + 1) & 0xffff; seq.steps += 1; mem.w(STEPW, 'w', seq.w)
    cpu.a[7] = SP; cpu.call('mf_body')
def reset8():
    for t in range(8):
        mem.w(C['mp_state'] + t, 'b', 0); mem.w(C['mp_k'] + 4 * t, 'l', 0); ext(t, 0, 0, 0)
    mem.w(XF, 'l', 64)                 # the fader off A: a parked track stays parked
def still():                         # a frame inside the same step
    cpu.a[7] = SP; cpu.call('mf_body')
reset8(); mem.w(TRANSPORT, 'l', 1)
cpu.a[7] = SP; cpu.call('mf_body')    # (the step word as it stands)

# the model of the defaults is v1.1's triangle, for every N up to 6400 (floor identities)
check('model_defaults_are_the_triangle', all(model(k * 256 + f, n, 0, 0) == tri(k, n, f)
      for n in (1, 2, 3, 7, 16, 128, 6400) for k in range(0, n, max(1, n // 50)) for f in (0, 77, 255))
      and all(cyc(n, 0, 0) == n for n in (1, 3, 16, 6400)))

# LOOP / ONCE, every RET and CURV: the value on each step's first frame (TRIG HOLD) is the model's
bad = []
for steps, mult in ((4, 1), (3, 2), (16, 1)):
    n = steps * mult
    for ret in range(9):
        for curv in range(4):
            reset8(); settings(0, steps, mult, 1); ext(0, ret, curv, 0)
            mem.w(C['mp_state'], 'b', 4)           # armed
            hop()                                  # the first step: k = 0, A
            c = cyc(n, ret, 0); got = [xf_of(0)]
            for _ in range(c + 1): hop(); got.append(xf_of(0))
            want = [model((k % c) * 256, n, ret, curv) for k in range(c + 2)]
            if got != want or state(0) != 1: bad.append((steps, mult, ret, curv, got, want, state(0)))
check('loop_follows_the_model', not bad, str(bad[:2]))
bad = []
for ret, curv in ((1, 0), (4, 1), (8, 0), (6, 3)):
    reset8(); settings(0, 4, 1, 1); ext(0, ret, curv, 1); mem.w(C['mp_state'], 'b', 4); hop()
    c = cyc(4, ret, 1)
    for _ in range(c - 1): hop()
    s1 = state(0); hop()
    if not (s1 == 1 and state(0) == 3 and xf_of(0) == 127): bad.append((ret, curv, s1, state(0), xf_of(0)))
check('once_parks_on_a_after_one_cycle', not bad, str(bad))
check('model_cut_is_back_on_the_next_step', cyc(4, 8, 0) == 2 and model(512, 4, 8, 0) == 127)
check('model_hand_is_fast_then_soft', [model(512 + u, 4, 0, 1) for u in (0, 128, 256, 384, 511)]
      == [0, 56, 96, 120, 127], str([model(512 + u, 4, 0, 1) for u in (0, 128, 256, 384, 511)]))

# STAY: up to B, held there (TOP); the long press, DOWN or the window's DOWN: back over RET, parked
def stay_up(ret, curv, steps=4, mult=1):
    reset8(); settings(0, steps, mult, 1); ext(0, ret, curv, 2); mem.w(C['mp_state'], 'b', 4); hop()
    for _ in range(cyc(steps * mult, ret, 2)): hop()
stay_up(3, 0)
check('stay_holds_b', state(0) == 7 and xf_of(0) == 0)
for _ in range(5): hop()
check('stay_holds_b_for_ever', state(0) == 7 and xf_of(0) == 0 and mem.r(C['mp_k'], 'l') == 0)
toasts.clear(); mem.w(HELD, 'l', 0); long_press(0)
check('long_press_on_top_asks_the_way_back', state(0) == 8 and len(toasts) == 1
      and text(toasts[0]) == 'T1 MORPH OFF', str([text(a) for a in toasts]))
still()
check('the_way_back_waits_for_the_step', state(0) == 8 and xf_of(0) == 0)
got = []
for _ in range(4): hop(); got.append((state(0), xf_of(0)))
n = 4; T = tlen(n, 3)                                # 1/8 of the way up: 64, a quarter of a step
check('the_way_back_is_ret_long', got[0] == (9, 0) and got[1] == (3, 127) and T == 64, str(got))
stay_up(5, 1)                                      # BAR: 16 steps, HAND
key('morph_down', 0b1)
check('down_on_top_asks_the_way_back', state(0) == 8)
got = []
for _ in range(18): hop(); got.append(xf_of(0))
want = [model(512 + k * 256, 4, 5, 1) for k in range(16)] + [127, 127]
check('stay_back_over_a_bar_by_hand', got == want and state(0) == 3, str(got))
stay_up(8, 0)                                      # CUT
key('morph_down', 0b1); hop()
check('stay_cut_is_back_on_the_step', state(0) == 3 and xf_of(0) == 127)
reset8(); settings(0, 16, 1, 1); ext(0, 7, 0, 2); mem.w(C['mp_state'], 'b', 4); hop(); hop()
key('morph_down', 0b1)
check('stop_on_the_way_up_is_stop', state(0) == 2)
for _ in range(8): hop()
check('a_stop_on_the_way_up_comes_back_at_b', (state(0), xf_of(0)) == (9, 0), str((state(0), xf_of(0))))
hop(); hop()
check('then_parks', state(0) == 3 and xf_of(0) == 127)

# END changed while it runs: STAY on the way back parks on A (no jump to B); TOP without STAY
# goes back on the next step
reset8(); settings(0, 4, 1, 1); ext(0, 0, 0, 0); mem.w(C['mp_state'], 'b', 4); hop()
for _ in range(3): hop()                          # k = 3: on the way back (C = 4)
x0 = xf_of(0); ext(0, 0, 0, 2); hop()
check('stay_turned_on_going_back_parks', x0 == model(3 * 256, 4, 0, 0) and state(0) == 3
      and xf_of(0) == 127, str((x0, state(0), xf_of(0))))
stay_up(0, 0); ext(0, 0, 0, 0); still()
check('top_without_stay_goes_back', state(0) == 8 and xf_of(0) == 0)
hop()
check('top_without_stay_goes_back_on_the_step', state(0) == 9)

# the scene indicator of a fader track is the fader's (review, 22 Nov: 7..9 tested first)
reset8(); mem.w(XF, 'l', 127); mem.w(C['mp_xf'], 'b', 0)
cpu.d[0] = 0; cpu.a[7] = SP; cpu.call('mw_sc')
check('indicator_of_a_fader_track_is_the_fader', cpu.d[0] >> 16 == 0, hex(cpu.d[0]))
mem.w(C['mp_state'], 'b', 7); cpu.d[0] = 0; cpu.a[7] = SP; cpu.call('mw_sc')
check('indicator_of_top_is_b', cpu.d[0] >> 16 == 4, hex(cpu.d[0]))

# the largest cycle, 64 x 100 = 6400, every RET, TRIG HOLD: k set near the turns, one step
bad = []
for ret in range(9):
    for curv in (0, 3):
        L, c = 6400 * 128, cyc(6400, ret, 0)
        for k in sorted({1, L // 256 - 1, L // 256, L // 256 + 1, c - 2, c - 1}):
            if not 0 < k < c: continue
            reset8(); settings(0, 64, 100, 1); ext(0, ret, curv, 0); mem.w(C['mp_state'], 'b', 1)
            mem.w(C['mp_k'], 'l', k - 1); hop()
            if xf_of(0) != model(k * 256, 6400, ret, curv): bad.append((ret, curv, k, xf_of(0), model(k * 256, 6400, ret, curv)))
check('largest_cycle_follows_the_model', not bad, str(bad[:3]))

# SMOOTH: every frame of three cycles of 3 x 1 (odd: the last step half on A), 1/16 back, BOTH
reset8(); settings(0, 3, 1, 0); ext(0, 4, 3, 0); mem.w(C['mp_state'], 'b', 4)
to_next_step()
bad = []; n = 0; c = cyc(3, 4, 0); s0 = seq.steps
while seq.steps - s0 < 3 * c and n < 20000:
    frame(); n += 1
    fs = mem.r(C['mp_fsince'], 'l'); f = min(255, ((min(fs, 0xffff) * BPM * 24) >> 8) * C['SUB_K'] >> 16)
    k = mem.r(C['mp_k'], 'l'); want = model(k * 256 + f, 3, 4, 3)
    if xf_of(0) != want: bad.append((k, f, xf_of(0), want))
check('smooth_follows_the_model', not bad and n > 100 and c == 2, str((len(bad), bad[:3], n, c)))

# the window on a STAY track: open, close, nothing moves; its DOWN starts the way back
stay_up(0, 0)
key('morph_up', 0b1)
check('window_shows_top', rows().get(52, ('',))[-1] == 'TOP' and state(0) == 7, str(rows().get(52)))
key('mw_no')
check('window_close_keeps_top', state(0) == 7)
key('morph_up', 0b1); key('mw_down')
check('window_down_on_top', state(0) == 8)
key('mw_no')
check('window_close_keeps_the_way_back', state(0) == 8)
for _ in range(2): hop()
key('morph_up', 0b1)
check('window_shows_back', rows().get(45, ('',))[0] == 'BACK 2/2' and rows().get(52, ('',))[-1] == 'RET',
      str((rows().get(45), rows().get(52))))
key('mw_no')

# encoders D, E, F: one value a click, clamped, on every window track; the rows show them
reset8(); settings(0, 16, 8, 0); settings(2, 16, 8, 0)
key('morph_up', 0b101)
enc(3, 1); enc(3, 5); enc(4, -1); enc(4, 2); enc(5, 1)
check('enc_d_e_f_set_every_window_track', ext_of(0) == [2, 1, 1, 0] and ext_of(2) == [2, 1, 1, 0]
      and ext_of(1) == [0, 0, 0, 0], str((ext_of(0), ext_of(2))))
for _ in range(12): enc(3, 1)
for _ in range(6): enc(4, 1)
for _ in range(6): enc(5, 1)
check('enc_d_e_f_clamp', ext_of(0) == [8, 3, 2, 0])
r = rows()
check('window_names', r.get(17) == ('RET (D)', 'CUT') and r.get(10) == ('CURV (E)', 'BOTH')
      and r.get(3) == ('END (F)', 'STAY') and r.get(45, ('',))[0] == 'CYCLE 64', str(r))
for _ in range(12): enc(3, -1)
check('enc_d_floor', ext_of(0)[0] == 0)
for _ in range(4): enc(3, 4)                       # one value a click, whatever the speed
r = rows()
check('window_ret_names', r.get(17) == ('RET (D)', '1/16'), str(r.get(17)))
key('mw_no')

# saving: version 3 only with a v1.2 setting; read back; v2 still read (all 0)
files.clear(); writes.clear()
for i in range(8): settings(i, 16, 8, 0)
reset8(); ev('newproj'); ev('bankw_post')
check('v12_untouched_writes_nothing', not writes)
ext(3, 5, 2, 1); ev('bankw_post')
f = files.get(W, b'')
check('v12_writes_version_3', len(f) == 88 and struct.unpack('>III', f[4:16]) == (3, 72, zlib.crc32(f[16:]))
      and f[16 + 40 + 12:16 + 40 + 16] == bytes([5, 2, 1, 0]) and f[56:68] == bytes(12), f.hex())
ext(3, 0, 0, 0); ev('loadall_post')
check('v3_is_read_back', ext_of(3) == [5, 2, 1, 0])
ext(3, 0, 0, 0); ev('bankw_post')
f = files.get(W, b'')
check('all_zero_writes_version_2_again', len(f) == 56 and struct.unpack('>II', f[4:12]) == (2, 40))
ext(5, 1, 1, 1); ev('loadall_post')
check('v2_file_clears_the_v12_settings', all(ext_of(t) == [0, 0, 0, 0] for t in range(8)))
pl = bytes([16, 8, 0, 0] * 8 + [0] * 8) + bytes([9, 4, 3, 7] + [1, 2, 0, 0] * 7)
files[W] = b'MRPW' + struct.pack('>III', 3, 72, zlib.crc32(pl)) + pl
ev('loadall_post')
check('v3_stray_values_are_0', ext_of(0) == [0, 0, 0, 0] and ext_of(1) == [1, 2, 0, 0])
stay_up(0, 0); ev('bankw_post')
f = files.get(W, b'')
check('top_saves_as_morphing', len(f) > 48 and f[48] & 1, f.hex())
print('%d failure(s)' % fails)
sys.exit(1 if fails else 0)
