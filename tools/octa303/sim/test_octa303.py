#!/usr/bin/env python3
"""OCTA303 v6.7 (dEVILish) test suite -- python3 tools/octa303/sim/test_octa303.py  (~1 min; OCTA303_FULL=1: ~4 min)

1. gen_tables --check; 2. cfsim lint (ColdFire limits; not an assembler);
3. BIT-EXACT: sy_render executed from the source text == ref303.render_call, every sample:
   saw/square, with and without the pedal, accents, trigless slides, carrier switches, split
   frames ([0,n) + [n,16)), extreme knobs;
4. the integration as poly.s 2.9 does it: four arguments re-pushed and the stock return handed
   back; PTCH/RATE = 0x4000/0x7f00 for the stock call on the frame's last call of a 303 track,
   restored after; the carrier's positions pinned; the retrig count cleared at a 303 START;
   ordinary samples, first calls of other tracks and dead voices untouched;
5. o3_retrig and o3_page / o3_mdesc executed against their stock contexts.
v7.9: the TB303* sample way in is gone.  The scripts below still name their carrier by a TB303* file
(the v6.x vocabulary): run() plays such a frame on the TB-303 machine, SETUP WAVE = that carrier and the
rest SETUP_NEUTRAL (what the sample's track played), and a TB303* sample on a FLEX track is checked to
be the stock renderer's (tb303_sample_*).
"""
import os, sys, random, subprocess
FULL = os.environ.get("OCTA303_FULL") == "1"     # the gate runs the quick set; FULL=1 the whole one
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from harness import *

results = []
def check(name, ok, detail=''):
    results.append(bool(ok)); print(('PASS  ' if ok else 'FAIL  ') + name + (('   [' + detail + ']') if detail else ''))

r = subprocess.run([sys.executable, os.path.join(HERE, '..', 'gen_tables.py'), '--check'], capture_output=True, text=True)
check('tables_up_to_date', r.returncode == 0, r.stdout.strip())
try:
    rig = Rig(); check('coldfire_lint', True, '%d instructions' % len(rig.cpu.prog))
except Exception as e:
    check('coldfire_lint', False, str(e)); sys.exit(1)

NAMES = {'saw': 'TB303.WAV', 'square': 'TB303SQ.WAV', 'saw_dist': 'TB303D.WAV', 'square_dist': 'tb303sqd.wav'}
def name_code(name):
    """The v6.x carrier names (the scripts' vocabulary, v7.9: no longer the engine's): (dist << 1) | wave, -1."""
    n = name.upper()
    if not n.startswith('TB303'): return -1
    n = n[5:]; w = 1 if n.startswith('SQ') else 0
    if w: n = n[2:]
    return w | (2 if n.startswith('D') else 0)
def SU(code):
    """The machine's SETUP that plays what a TB303* sample's track played (v6.9's SETUP_NEUTRAL, WAVE = code)."""
    return (code,) + tuple(T.SETUP_NEUTRAL[1:])
def W(tune=0, cut=64, res=64, env=64, dec=64, acc=0):
    return [0x4000 + tune * 256, cut << 8, res << 8, env << 8, dec << 8, acc << 8]

def run(script, track=0, rig=None):
    """script: frames (words, start_at or None, filename, alive).  start_at = sub-frame offset of a
    START this frame (0 = one call [0,16)).  Returns (asm, ref, first mismatch or None)."""
    rig = rig or Rig(); st = R.Track(); A = []; B = []
    for f, fr in enumerate(script):
        w, start_at, fname, alive = fr[:4]; df = fr[4] if len(fr) > 4 else None; fxslot = fr[5] if len(fr) > 5 else 1
        sq = fr[6] if len(fr) > 6 else None
        rdf = fr[7] if len(fr) > 7 else df                            # v7.1: the knobs the 303 should hear
        su = fr[8] if len(fr) > 8 else None                           # v7.0: the TB-303 machine's SETUP bytes
        sslot = 3 + (f % 2)                                          # the sample's FLEX slot
        rig.path(sslot, '/AUDIO/ACID/' + fname); rig.voice(track, alive, sslot)
        if su is None and name_code(fname) >= 0: su = SU(name_code(fname))   # v7.9: the carrier, on the machine
        rig.machine(track, su if su is not None else T.SETUP_NEUTRAL, sign=su is not None)
        calls = [(0, 16)] if not start_at else [(0, start_at), (start_at, 16)]
        for (a, b) in calls:
            last = b == 16
            L, Rr = rig.call(track, w, a, b, start_at is not None, SILENCE, df, fxslot, sq)
            if L != Rr: return A, B, 'L != R'
            code = name_code(fname) if (last and start_at is not None) else None
            if su is not None and code is not None: code = min(su[0], 7)         # the machine: SETUP's WAVE (v7.9: 8 values)
            ref = R.render_call(st, w, last and start_at is not None, -1 if code is None else code, b - a,
                               alive or su is not None, rdf if fxslot in (1, 2) else None, last=last, seq=sq,
                               setup=su)
            ref = [0] * (b - a) if ref is None else ref
            A += L; B += ref
            if L != ref:
                return A, B, len(A) - (b - a) + next(i for i in range(b - a) if L[i] != ref[i])
    return A, B, None

def scenario(fname, seed, frames=360, knobs=False):
    rnd = random.Random(seed); sc = []; w = W(); df = None; slot = 1
    for f in range(frames):
        start = None
        if f == 0 or rnd.random() < 0.05:
            start = rnd.choice([0, 0, 0, 5, 11])
            w = W(rnd.randint(-12, 24), rnd.randint(0, 127), rnd.randint(0, 127), rnd.randint(0, 127),
                  rnd.randint(0, 127), rnd.choice([0, 0, 64, 127]))
        elif rnd.random() < 0.03:
            w = list(w); w[0] = 0x4000 + rnd.randint(-12, 24) * 256      # a trigless PTCH lock: a slide
        if knobs and rnd.random() < 0.05:                                   # dEVILish moved, locked, taken away
            df = None if rnd.random() < 0.2 else tuple(rnd.choice([0, 1, 2, 3, 25, 50, 64, 100, 127, rnd.randint(0, 127)]) for _ in range(12))
            slot = rnd.choice([1, 2])
        sc.append((w, start, fname, True, df, slot))
    return sc

for nm, fn in NAMES.items():
    bad = None; total = 0
    for seed in range(2 if FULL else 1):
        A, B, mm = run(scenario(fn, seed * 31 + len(nm), 360 if FULL else 120))
        total += len(A)
        if mm is not None: bad = (seed, mm); break
    check('bit_exact_' + nm, bad is None, '%d samples' % total if bad is None else 'seed %d first mismatch @%s' % bad)

for nm, fn in NAMES.items():
    A, B, mm = run(scenario(fn, 77 + len(nm), 360 if FULL else 150, knobs=True))
    check('bit_exact_devilish_' + nm, mm is None, '%d samples' % len(A) if mm is None else 'mismatch @%s' % mm)
dfx = []
EXT = ((0,) * 12, (127,) * 12, (127, 127, 127, 127, 127, 0, 127, 1, 0, 2, 1, 1),
       (0, 127, 127, 0, 127, 127, 0, 2, 2, 1, 0, 1), (127, 127, 0, 127, 0, 50, 64, 0, 1, 0, 0, 0),
       (100, 127, 0, 96, 127, 50, 0, 1, 1, 0, 0, 0), T.DF_NEUTRAL)
for fn in ('TB303.WAV', 'TB303D.WAV', 'TB303SQ.WAV', 'tb303sqd.wav'):   # v7.6 (review): the square into the OTA too
    for df in EXT:
        for slot in (1, 2):
            sc = [(W(12, 0, 127, 127, 0, 127), 0, fn, True, df, slot)] + [(W(12, 0, 127, 127, 0, 127), None, fn, True, df, slot)] * (40 if FULL else 12)
            sc += [(W(-12, 127, 127, 0, 127, 127), 5, fn, True, df, slot)] + [(W(-12, 127, 127, 0, 127, 0), None, fn, True, df, slot)] * (30 if FULL else 10)
            A, B, mm = run(sc); dfx.append(mm is None)
check('bit_exact_devilish_extremes_fx1_fx2', all(dfx))
_sc = lambda fx: [(W(0, 40, 115, 90, 50, 127), 0, 'TB303.WAV', True, (110, 127, 60, 96, 127, 50, 0, 1, 2, 1, 1, 1), fx)] + \
                 [(W(5, 40, 115, 90, 50, 0), None, 'TB303.WAV', True, (110, 127, 60, 96, 127, 50, 0, 1, 2, 1, 1, 1), fx)] * 12
_a1, _b1, _m1 = run(_sc(1)); _a2, _b2, _m2 = run(_sc(2)); _a0, _b0, _m0 = run(_sc(0))
check('devilish_fx1_and_fx2_both_read', _m1 is None and _m2 is None and _a1 == _a2 and _a1 != _a0)
st_a = R.Track(); st_b = R.Track(); same = True
for f in range(200):
    w = W(3, 60, 100, 90, 50, 127 if f % 7 == 0 else 0)
    same &= R.render_call(st_a, w, f % 9 == 0, 0, 16, True, None) == R.render_call(st_b, w, f % 9 == 0, 0, 16, True, T.DF_NEUTRAL)
check('devilish_neutral_is_absent', same)

# v7.1: dEVILish's page 1 as the DSP gets it -- the voice record's halfwords (VREC + ping*0x200 +
# 64*track, FX1 6-11 / FX2 12-17), where the frame builder has applied the locks, the scene morph and
# the LFOs (LFO.md 5).  Knob = halfword >> 8, 0..127; the low byte is an LFO's fraction.
_lane = (25, 0, 0, 64, 0, 50, 0, 0, 1, 0, 0, 0)
def _vr(fx, hws, ping=0, rounds=None):
    rig = Rig(); rig.vrec(0, fx, hws, ping)
    if fx == 1: rig.vrec(0, 2, (0x7f00,) * 6)                         # FX2's knobs: FX1 must not read them
    else: rig.vrec(0, 1, (0x7f00,) * 6)
    exp = tuple(min(max(h - 0x10000 if h & 0x8000 else h, 0) >> 8, 127) for h in hws) + _lane[6:]
    sc = [(W(0, 60, 100, 90, 50, 127), 0, 'TB303.WAV', True, _lane, fx, None, exp)] + \
         [(W(0, 60, 100, 90, 50, 0), None, 'TB303.WAV', True, _lane, fx, None, exp)] * (rounds or (20 if FULL else 6))
    return run(sc, rig=rig)[2] is None
_HW = ((0x7f00, 0x0000, 0x40fe, 0x22fe, 0x7fff, 0x0080),            # an LFO's dirty low bytes
       (0x3200, 0x6400, 0x0100, 0x7e80, 0x1955, 0x00ff),
       (0x8000, 0xff00, 0x7f00, 0x0000, 0x4000, 0x4000))             # below the floor: 0
_ok = [_vr(fx, hw, ping) for fx in (1, 2) for hw in _HW for ping in (0, 1)]
check('devilish_vrec_bit_exact', all(_ok), '%d/%d' % (sum(_ok), len(_ok)))
rig = Rig(); rig.path(3, '/AUDIO/ACID/TB303.WAV'); rig.voice(0, True, 3); rig.machine(0, SU(0)); _l = []; st = R.Track()
for f in range(24):                                                # an LFO moving FM under a held note
    hw = (25 << 8, ((f * 11) % 128) << 8 | (f * 37) & 0xFF, 0, 64 << 8, 0, 50 << 8)
    rig.vrec(0, 2, hw, f % 2)
    exp = tuple(h >> 8 for h in hw) + _lane[6:]
    L, Rr = rig.call(0, W(0, 60, 100, 90, 50, 0), 0, 16, f == 0, SILENCE, _lane, 2)
    ref = R.render_call(st, W(0, 60, 100, 90, 50, 0), f == 0, 0 if f == 0 else -1, 16, True, exp, last=True, setup=SU(0))
    _l.append(L == ref)
check('devilish_lfo_moving', all(_l), '%d/%d' % (sum(_l), len(_l)))

ex = []
for fn in NAMES.values():
    for v in ((0, 0, 0, 0, 0, 127), (127, 127, 127, 127, 127, 127), (0, 127, 127, 0, 127, 127), (127, 0, 0, 127, 0, 0)):
        sc = [(W(12, *v[:4], v[4]), 0, fn, True)] + [(W(12, *v[:4], v[4]), None, fn, True)] * (80 if FULL else 25)
        sc += [(W(-12, *v[:4], 127), 7, fn, True)] + [(W(-12, *v[:4], 127), None, fn, True)] * (40 if FULL else 12)
        A, B, mm = run(sc); ex.append(mm is None)
check('bit_exact_extremes', all(ex))
sc = []
for k in range(8):
    fn = list(NAMES.values())[k % 4]
    sc += [(W(k, 90, 100, 80, 30, 127 * (k & 1)), 0, fn, True)] + [(W(k + 3, 90, 100, 80, 30, 0), None, fn, True)] * 30
A, B, mm = run(sc); check('bit_exact_carrier_switch', mm is None)

# v7.3 (#1011): the ladder clip eased at the top of the table (ACID only), with and without dEVILish's
# per-sample FM; WHST keeps the plain clip; ACCV 127 on open accented notes through the wider VCA.
_top = []; _seen = {'clg': 0}
_DFM = (25, 90, 0, 64, 0, 50, 0, 0, 1, 0, 0, 0)                  # FM up, ACID
_DWH = (25, 0, 0, 64, 0, 50, 0, 1, 1, 0, 1, 1)                   # WHST, CUTX, ENVX
for df, su, v in ((None, (0, 0, 64, 0, 0, 64), (127, 127, 120, 64, 0)), (None, (0, 0, 64, 0, 0, 64), (127, 127, 104, 64, 127)),
                  (_DFM, None, (112, 120, 127, 64, 90)), (_DWH, None, (127, 127, 127, 64, 127)),
                  (None, (0, 0, 64, 0, 0, 127), (80, 0, 127, 64, 127)), (None, (1, 0, 64, 0, 127, 127), (127, 0, 127, 64, 127)),
                  # v8.3 (review): OVDR 127 + FM 127 + MUFF HARD at the top, the case that uses most of l1's headroom
                  ((127, 127, 0, 64, 0, 50, 0, 0, 1, 2, 0, 0), None, (110, 127, 127, 64, 127))):
    n = 90 if FULL else 45
    fn = 'KICK.WAV' if su else 'TB303.WAV'                       # the machine (SETUP), or the TB303.WAV carrier (run(): SU(0)) + dEVILish
    fr = lambda tune, at: (W(tune, *v), at, fn, True, df, 1, None, df, su)        # rdf: the 303 hears dEVILish too
    sc = [fr(0, 0)] + [fr(0, None)] * n + [fr(-12, 3)] + [fr(-12, None)] * n
    _orig = R.clset
    def _spy(st, i, _o=_orig):
        _o(st, i); _seen['clg'] += st.clg > 0
    R.clset = _spy
    A, B, mm = run(sc); _top.append(mm is None)
    R.clset = _orig
check('bit_exact_v73_top_clip_accv', all(_top) and _seen['clg'] > 0,
      '%d/%d, clip eased in %d control steps' % (sum(_top), len(_top), _seen['clg']))
# v7.5 (review): dEVILish SPD SLOW with ACC 127 and accents in a row: the capacitor read doubled climbed past 2^31
# in the asm (wrapped) where the model's Python integers did not; now held under 2^30 in both
_sl = [(W(0, 64, 64, 64, 64, 127), 0 if f % 50 == 0 else None, 'TB303.WAV', True, (25, 0, 0, 64, 0, 127, 0, 0, 2, 0, 0, 0), 1)
       for f in range(600)]
_A, _B, _mm = run(_sl)
check('bit_exact_v75_slow_accent_run', _mm is None, 'SPD SLOW, ACC 127, an accent every 50 frames, 600 frames')
# v7.6: Q8's square through its tables: a slide over four octaves (every semitone's row, the edge's polyBLEP),
# accented, with dEVILish's OVDR up (the VCA's OTA in its curve) and plain
_sw = []
for f in range(420):
    tune = -24 + (f * 48) // 420
    _sw.append((W(tune, 90, 100, 100, 50, 127), 0 if f == 0 else None, 'TB303SQ.WAV', True, (110, 0, 0, 64, 0, 64, 0, 0, 1, 0, 0, 0) if f >= 210 else None, 1))
_A, _B, _mm = run(_sw)
check('bit_exact_v76_square_sweep_ota', _mm is None, 'SQR slid C1..C5, ACC 127, OVDR 110 on the second half, 420 frames')
# v7.6 (review): the edge rows (the pitch's clamps, rows 28 and 100) and a square after a saw (the edge lowpass's state
# left from the last square, at the lowest row, against a new note's first sample: the step is clamped)
_ed = [(W(-36, 60, 110, 100, 40, 127), 0 if f == 0 else None, 'TB303SQ.WAV', True) for f in range(60)]
_ed += [(W(-36, 60, 110, 100, 40, 0), 0 if f == 0 else None, 'TB303.WAV', True) for f in range(30)]
_ed += [(W(-36, 127, 0, 127, 40, 127), 0 if f == 0 else None, 'TB303SQ.WAV', True) for f in range(40)]
_ed += [(W(36, 127, 127, 127, 40, 127), 0 if f == 0 else None, 'TB303SQ.WAV', True) for f in range(60)]
_A, _B, _mm = run(_ed)
check('bit_exact_v76_square_edge_rows', _mm is None, 'SQR at the pitch clamps, saw between, 190 frames')

# ---------------------------------------------------------------- integration
rig = Rig(); feed = sample_feed(1)
rig.path(2, '/AUDIO/KICK.WAV'); rig.voice(1, True, 2); rig.seen.clear()
L, _ = rig.call(1, W(5), 0, 16, True, feed)
args, words = rig.seen[-1]
check('ordinary_sample_untouched', L == [feed(i) for i in range(16)])
check('args_repushed_return_handed_back', args == [1, 0x800000e4, 0, 16])
check('ordinary_sample_record_untouched', words == W(5))

rig = Rig(); rig.path(4, '/AUDIO/TB303.WAV'); rig.voice(2, True, 4); rig.machine(2, SU(0))
rig.cpu.mem.w(RS + 4, 'l', 7)
pos0 = rig.positions(2); w = W(5, 90, 100); rig.seen.clear()
rig.call(2, w, 0, 16, True, SILENCE)
# v8.7: the last call of a START frame still runs the stock renderer, neutralised (vFable's hybrid)
m = rig.cpu.mem
_, words_seen = rig.seen[-1]
check('start_frame_keeps_the_stock_call', rig.stock_called)
check('neutral_ptch_rate_for_the_stock_call', words_seen[0] == 0x4000 and words_seen[3] == 0x7f00, '%04x %04x' % (words_seen[0], words_seen[3]))
check('ptch_rate_restored_after', [rig.cpu.mem.r(FRAME + 2 * i, 'w') for i in range(6)] == w)
check('carrier_positions_pinned', rig.positions(2) == pos0)
check('retrig_count_cleared_at_303_start', rig.cpu.mem.r(RS + 4, 'l') == 0)
rig.seen.clear()
rig.call(2, w, 0, 16, False, SILENCE)
# v8.6/v8.7: a latched track's call without a START skips the stock renderer (CX OSC's sy_call): the header
# is what stock writes (count, start, rate 1.0, the ring word) and CURSOR moves past the 16 pairs
check('no_stock_call_without_start', not rig.seen and not rig.stock_called)
check('header_as_stock_writes_it', [m.r(CUR + 4 * i, 'l') for i in range(4)] == [16, 0, 0x04000000, 0]
      and m.r(CURSOR, 'l') == CUR + 16 + 8 * 16, '%08x %08x' % (m.r(CUR, 'l'), m.r(CURSOR, 'l')))
check('skip_record_untouched', [m.r(FRAME + 2 * i, 'w') for i in range(6)] == w and rig.positions(2) == pos0)
rig.cpu.mem.w(RS + 4, 'l', 7)
rig.call(2, w, 0, 5, True, SILENCE)                       # a first call: nothing neutralised, no stock call
check('first_call_no_stock_call', not rig.stock_called and m.r(CUR, 'l') == 5 and m.r(CUR + 4, 'l') == 0
      and m.r(CURSOR, 'l') == CUR + 16 + 8 * 5)
check('first_call_record_untouched', [m.r(FRAME + 2 * i, 'w') for i in range(6)] == w)
rig.call(2, w, 5, 16, False, SILENCE)                     # its second call: the ring word from start 5
check('second_call_header', [m.r(CUR + 4 * i, 'l') for i in range(4)] == [11, 5, 0x04000000, (5 << 26) & 0xFFFFFFFF])
check('retrig_count_kept_without_start', rig.cpu.mem.r(RS + 4, 'l') == 7)

# v7.9: a TB303* sample on a plain FLEX track is a sample: the stock renderer's, byte for byte
for fn in NAMES.values():
    rig = Rig(); rig.path(4, '/AUDIO/ACID/' + fn); rig.voice(3, True, 4); feed = sample_feed(6)
    rig.cpu.mem.w(RS + 4, 'l', 7); pos0 = rig.positions(3); w = W(5, 90, 100); rig.seen.clear()
    L, Rr = rig.call(3, w, 0, 16, True, feed)
    _, words = rig.seen[-1]
    L2, _ = rig.call(3, w, 0, 16, False, feed)
    check('tb303_sample_is_stock_' + fn.split('.')[0].lower(), L == [feed(i) for i in range(16)] and Rr == L and L2 == L
          and words == w and rig.cpu.mem.r(RS + 4, 'l') == 7 and rig.positions(3) != pos0,
          'samples, record, retrig count and positions as stock leaves them')

rig = Rig(); rig.path(4, '/AUDIO/TB303.WAV'); rig.path(6, '/AUDIO/LOOP.WAV')
rig.voice(0, True, 4); rig.machine(0, SU(0)); rig.call(0, W(), 0, 16, True, SILENCE)
rig.machine(0, T.SETUP_NEUTRAL, sign=False); rig.voice(0, True, 6); feed = sample_feed(8)
L, _ = rig.call(0, W(), 0, 16, True, feed)
L2, _ = rig.call(0, W(), 0, 16, False, feed)
check('machine_taken_away_releases_at_the_next_start', L == [feed(i) for i in range(16)] and L2 == L)

rig = Rig(); rig.voice(4, True, None); feed = sample_feed(2)
L, _ = rig.call(4, W(), 0, 16, True, feed)
check('null_settings_pointer_ignored', L == [feed(i) for i in range(16)])

rig = Rig(); feed = sample_feed(3); ok = True; st = R.Track()
rig.path(4, '/AUDIO/TB303.WAV'); rig.path(5, '/AUDIO/HATS.WAV'); rig.machine(0, SU(0))
for f in range(30):
    rig.voice(0, True, 4); L, _ = rig.call(0, W(3, 80, 90), 0, 16, f == 0, SILENCE)
    ref = R.render_call(st, W(3, 80, 90), f == 0, 0, 16, setup=SU(0))
    rig.voice(7, True, 5); L2, _ = rig.call(7, W(), 0, 16, f % 4 == 0, feed)
    ok &= (L == ref) and (L2 == [feed(i) for i in range(16)])
check('tracks_independent', ok)

def level(fn, acc):
    st = R.Track(); out = []
    for f in range(320):
        r = R.render_call(st, W(0, 70, 100, 90, 60, acc), f == 0, name_code(fn), 16); out += [R.s32(x) >> 16 for x in r]
    return max(abs(x) for x in out), (sum(x * x for x in out) / len(out)) ** .5
for nm, fn in NAMES.items():
    pk, rms = level(fn, 0); pka, rmsa = level(fn, 127)
    check('audible_bounded_' + nm, 800 < rms and pk < 32767, 'peak %d rms %.0f' % (pk, rms))   # v7.6: 800 (the refit: saw and square both ~0.6 dB under v7.5 here; the OTA ~0.1-0.2 dB of it)
    if 'dist' not in nm: check('accent_louder_' + nm, rmsa > rms * 1.05, 'rms %.0f -> %.0f' % (rms, rmsa))

# ---------------------------------------------------------------- o3_retrig (detour 0x4000c634)
CMD = 0x46104d15
def retrig(track, byte, latched):
    rig = Rig(); c = rig.cpu; m = c.mem
    if latched:
        rig.path(4, '/AUDIO/TB303.WAV'); rig.voice(track, True, 4); rig.machine(track, SU(0)); rig.call(track, W(), 0, 16, True, SILENCE)
    m.w(CMD + track, 'b', byte)
    c.a[7] = STACK; m.w(STACK - 4 + 114, 'l', track)   # the detour is a jmp: cfsim's call() pushes a return address first
    c.a[0] = CMD; c.d[1] = 0x5151; c.a[2] = 0x6262; c.d[0] = 0
    got = []
    c.hooks[0x4000c63c] = lambda cpu: got.append(1)
    c.call('o3_retrig')
    return m.r(CMD + track, 'b'), c.d[0] & 0xFF, c.a[1], c.d[1], c.a[2], got
b, d0, a1, d1, a2, got = retrig(3, 0x15, True)
check('retrig_303_start_becomes_0x30', b == 0x30 and d0 == 0x30 and a1 == 3 and got)
check('retrig_registers_kept', d1 == 0x5151 and a2 == 0x6262)
b, d0, *_ = retrig(3, 0x15, False)
check('retrig_other_track_untouched', b == 0x15 and d0 == 0x15)
b, d0, *_ = retrig(3, 0x02, True)
check('retrig_non_start_untouched', b == 0x02 and d0 == 0x02)

# ---------------------------------------------------------------- o3_page (detour 0x40031ece); v7.9: no TB303* clone
FLEX_P, TABLE, BANK = 0x400d31ae, 0x400d5f38, 0x41000000
def page(path, track=2, part=1, machine=1, slot=5, tblval=FLEX_P):
    rig = Rig(); c = rig.cpu; m = c.mem
    for i in range(0x192): m.w(FLEX_P + i, 'b', (i * 7 + 3) & 0xFF)
    m.w(TABLE + 4 * machine, 'l', tblval)
    m.w(BANK + part * 6322 + 0x8f04b + track * 5, 'b', slot)
    rig.path(slot, path)
    c.d[0], c.a[0], c.d[3], c.d[1], c.a[1] = machine, TABLE, track, part, BANK
    for r in (6, 7): c.d[r] = 0x7777 + r
    for r in range(2, 7): c.a[r] = 0x6600 + r
    c.a[7] = STACK; done = []
    c.hooks[0x40031ed6] = lambda cpu: done.append(1)
    c.call('o3_page')
    kept = all(c.d[r] == 0x7777 + r for r in (6, 7)) and all(c.a[r] == 0x6600 + r for r in range(2, 7)) and c.a[7] == STACK
    return c, c.d[0], kept and bool(done)
def playback_exp(c, stock):
    """The machine record's PLAYBACK fields (o3_mover's first seven entries) over the stock FLEX record."""
    exp = bytearray(stock); exp[0x9:0x12] = b'OCTA-303\0'
    exp[0x16:0x3a] = b'TUNE\0\0CUT\0\0\0RES\0\0\0ENV\0\0\0DEC\0\0\0ACC\0\0\0'; exp[0x5f:0x64] = bytes([64, 64, 64, 64, 0])
    for k in range(5): exp[0xce + 4 * k:0xd2 + 4 * k] = (0x4003c178).to_bytes(4, 'big')
    exp[0xca:0xce] = c.consts['o3_fmt_tune'].to_bytes(4, 'big')            # v6.4: TUNE in semitones
    exp[0x6a:0x6e] = (64 + T.TUNE_LO).to_bytes(4, 'big'); exp[0x9a:0x9e] = (T.TUNE_HI - T.TUNE_LO + 1).to_bytes(4, 'big')
    exp[0x12a:0x12e] = bytes(4)
    return exp
STOCKREC = bytes((i * 7 + 3) & 0xFF for i in range(0x192))
for p_ in ('/AUDIO/ACID/TB303.WAV', '/AUDIO/tb303sqd.wav'):               # v7.9: a TB303* sample is FLEX's
    c, d0, kept = page(p_)
    check('page_tb303_sample_is_stock_' + p_.split('/')[-1].split('.')[0].lower(), d0 == FLEX_P and kept
          and bytes(c.mem.r(c.consts['o3_desc'] + i, 'b') for i in range(0x192)) == bytes(0x192)
          and bytes(c.mem.r(FLEX_P + i, 'b') for i in range(0x192)) == STOCKREC, 'the stock FLEX record, nothing cloned')

# ---------------------------------------------------------------- v7.0: o3_fmt_tune (TUNE as a note name)
def fmt_tune(v):
    rig = Rig(); c = rig.cpu; m = c.mem; called = []
    c.hooks[0x40013a08] = lambda cpu: called.append(1)
    buf = 0x81000000
    for i in range(8): m.w(buf + i, 'b', 0xAA)
    c.a[7] = STACK; m.w(STACK - 4, 'l', v); m.w(STACK - 8, 'l', buf); c.a[7] = STACK - 8
    for r in range(2, 7): c.d[r] = 0x7700 + r
    for r in range(2, 7): c.a[r] = 0x6600 + r
    c.call('o3_fmt_tune')
    b = b''
    for i in range(8):
        x = m.r(buf + i, 'b')
        if not x: break
        b += bytes([x])
    return b.decode('latin1'), c.d[0], c.a[7] == STACK - 8, all(c.d[r] == 0x7700 + r for r in range(2, 7)) and all(c.a[r] == 0x6600 + r for r in range(2, 7)), not called
ok = True; seen = []
for v, want in ((40, 'C1'), (52, 'C2'), (63, 'B2'), (64, 'C3'), (65, 'C#3'), (67, 'D#3'), (69, 'F3'), (73, 'A3'), (85, 'A4'), (88, 'C5'), (0, 'C0'), (127, 'B7')):
    txt, n, sp_ok, regs, nosp = fmt_tune(v)
    seen.append(txt); ok &= txt == want and n == len(want) and sp_ok and regs and nosp
check('fmt_tune_prints_note_names', ok, ' '.join(seen))

# ---------------------------------------------------------------- v6.4: o3_chrom (detour 0x4004fc58)
def chrom(path, idx, track=3, machine=1, slot=6, part=2):
    rig = Rig(); c = rig.cpu; m = c.mem
    m.w(0x46c82456, 'l', BANK); m.w(0x100b14cf, 'b', part)
    P = BANK + part * 6322
    m.w(P + 0x8eda2 + track, 'b', machine); m.w(P + 0x8f04b + track * 5, 'b', slot)
    rig.path(slot, path)
    c.d[2] = track; c.a[2] = idx; c.a[7] = STACK
    for r in (3, 4, 5, 6, 7): c.d[r] = 0x5500 + r
    for r in (3, 4, 5, 6): c.a[r] = 0x6600 + r
    c.call('o3_chrom')
    kept = all(c.d[r] == 0x5500 + r for r in (3, 4, 5, 6, 7)) and all(c.a[r] == 0x6600 + r for r in (3, 4, 5, 6)) \
        and c.a[7] == STACK and c.d[2] == track
    return c.a[2], c.d[0], kept
okst = all(chrom(p, i, **kw)[:2] == (5 * i + 4, 2) and chrom(p, i, **kw)[2]
           for i in (0, 12, 24) for p, kw in (('/AUDIO/KICK.WAV', {}), ('/AUDIO/SYNTH.WAV', {}),
                                               ('/AUDIO/ACID/TB303.WAV', {}), ('/AUDIO/tb303sqd.wav', {}),
                                               ('/AUDIO/TB303.WAV', {'machine': 0}), ('/AUDIO/TB303.WAV', {'slot': 200})))
check('chrom_stock_for_other_tracks', okst, 'raw = 5 * idx + 4 (v7.9: a TB303* sample too; the machine: chrom_machine_keys_are_semitones)')

# ---------------------------------------------------------------- v6.4: the pitch is semitones, three octaves
def f0(tune):
    st = R.Track(); R.render_call(st, W(tune, 127, 0, 0, 127, 0), True, 0, 16)
    return st.inc * 44100 / 2 ** 32
check('tune_semitones_four_octaves', abs(f0(0) - 130.81) < 0.2 and abs(f0(-12) - 65.41) < 0.1 and abs(f0(-24) - 32.70) < 0.1
      and abs(f0(24) - 523.25) < 0.8 and abs(f0(7) - 196.0) < 0.3, '%.1f %.1f %.1f Hz' % (f0(-12), f0(0), f0(24)))
check('tune_clamped_for_old_bytes', abs(f0(60) - f0(36)) < 0.01 and abs(f0(-60) - f0(-36)) < 0.01)
for p, nm, kw in (('/AUDIO/KICK.WAV', 'ordinary_sample', {}), ('/AUDIO/SYNTH.WAV', 'synth_name', {}),
                  ('/AUDIO/TB303.WAV', 'recorder_slot', {'slot': 200}),
                  ('/AUDIO/TB303.WAV', 'other_machine', {'tblval': 0x400d4000})):
    _, d0, kept = page(p, **kw)
    check('page_stock_for_' + nm, d0 == kw.get('tblval', FLEX_P) and kept)

# ---------------------------------------------------------------- dEVILish's id and the remix without it
import re as _re
_om = open(os.path.join(ROOT, 'modules', 'octa303', 'manifest.py')).read()
_ox = int(_re.search(r'^DEVIL_ID = (0x[0-9a-fA-F]+)', _om, _re.M).group(1), 16)
check('devil_id_is_the_harnesss', _ox == DEVIL_ID, 'octa303 0x%x, harness 0x%x' % (_ox, DEVIL_ID))
_dpath = os.path.join(ROOT, 'modules', 'devilish', 'manifest.py')
if os.path.exists(_dpath):      # the dEVILish module (its own PR): its manifest must agree with the engine
    _dm = open(_dpath).read()
    _fx = int(_re.search(r'^FX_ID = (0x[0-9a-fA-F]+)', _dm, _re.M).group(1), 16)
    check('devilish_id_agrees', _fx == _ox == DEVIL_ID, 'devilish 0x%x, octa303 0x%x, harness 0x%x' % (_fx, _ox, DEVIL_ID))
    _names = _re.findall(r'Param\(b"(\w+)"', _dm)
    check('devilish_knob_order_is_the_engines', tuple(_names) == T.DF_NAMES, str(_names))
    _defs = tuple(int(x) for x in _re.findall(r'Param\(b"\w+", (\d+)', _dm))
    check('devilish_defaults_are_neutral', _defs == T.DF_NEUTRAL, str(_defs))
else:
    print('  (modules/devilish not in this tree: its three manifest checks skipped)')
# a remix without dEVILish (remix.inc: DEVIL_ID 0x100): the knobs on FX2 are someone else's, neutral
rig = Rig(source(devilish=False)); rig.path(4, '/AUDIO/TB303.WAV'); rig.voice(0, True, 4); rig.machine(0, SU(0))
st = R.Track(); ok = True
for f in range(40):
    w = W(0, 60, 110, 90, 50, 127 if f % 5 == 0 else 0)
    L, _r = rig.call(0, w, 0, 16, f == 0, SILENCE, (127, 127, 127, 0, 127, 0, 127, 2, 2, 2, 1, 1), 2)
    ok &= L == R.render_call(st, w, f == 0, 0, 16, True, None, setup=SU(0))
check('no_devilish_in_remix_is_neutral', ok)

# ---------------------------------------------------------------- v6.5 / v7.0: the 303's gate (SETUP's GATE)
GF = ('gmode', 'gate', 'glvl', 'gstep', 'lstep', 'ltick', 'idle', 'kmax', 'tps', 'gnew', 'gel', 'gend',
      'gsel', 'fcnt', 'fpt', 'fseen', 'gelf', 'fskip', 'stopd')
GOFF = {'gmode': 248, 'gate': 252, 'glvl': 256, 'gstep': 260, 'lstep': 264, 'ltick': 268, 'idle': 272,
        'kmax': 276, 'tps': 280, 'gnew': 284, 'gel': 288, 'gend': 292,
        'gsel': 344, 'fcnt': 348, 'fpt': 352, 'fseen': 356, 'gelf': 360, 'fskip': 380, 'stopd': 384}
check('gate_state_offsets_are_the_sources', all(Rig().cpu.consts['S_' + f.upper()] == GOFF[f] for f in GF))
def gate_fuzz(n, seed):
    """o3_gate run on random states and inputs == ref303.gate_frame, every field"""
    rnd = random.Random(seed); rig = Rig(); c = rig.cpu; m = c.mem; base = c.consts['o3_state']
    for it in range(n):
        t = rnd.randrange(8); L = rnd.choice([16, 16, 32, 64, 1, 2, 7, 0, 99])
        st = R.Track()
        LL = L if 1 <= L <= 64 else 16
        st.gmode = rnd.randint(0, 1); st.gate = rnd.randint(0, 1); st.glvl = rnd.randint(0, 32767)
        st.gstep = rnd.randrange(LL); st.lstep = rnd.randrange(LL); st.ltick = rnd.randrange(6)
        st.idle = rnd.choice([0, 1, 5, T.GATE_IDLE - 1, T.GATE_IDLE]); st.kmax = rnd.randrange(12)
        st.tps = rnd.choice([0, 3, 6, 12]); st.gnew = rnd.randint(0, 1)
        st.gel = rnd.choice([0, 1, 2, 3, 5, 9, 4095, 4096]); st.gend = rnd.choice([0, 3, 6, 7, 12, 18, 30])
        st.gsel = rnd.choice([0, 1, 1]); st.fseen = rnd.randint(0, 1)
        st.fcnt = rnd.choice([0, 1, 2, 3, 4094, 4095]); st.fpt = rnd.choice([0, 0, 1, 2, 3, 7, 40])
        st.gelf = rnd.choice([0, 1, 5, 6, 7, 13, 14, 15, 65534, 65535])
        st.fskip = rnd.choice([0, 0, 1, 2]); st.stopd = rnd.randint(0, 1)
        step = rnd.choice([st.lstep, (st.lstep + 1) % LL, st.gstep, (st.gstep + 1) % LL, rnd.randrange(300)])
        tick = rnd.choice([st.ltick, rnd.randrange(12)])
        seq = (rnd.choice([127, 0, 64]), step, tick, rnd.getrandbits(64), L, rnd.choice([1, 1, 0, 2]))   # v7.5: 2 = STOP key
        a3 = base + t * 512
        for f in GF: m.w(a3 + GOFF[f], 'l', getattr(st, f) & M32)
        rig.seq(t, seq)
        c.d[2] = t; c.a[3] = a3; c.a[7] = STACK
        for r in (3, 4, 5, 6): c.d[r] = 0x4400 + r
        c.call('o3_gate')
        R.gate_frame(st, seq)
        got = {f: R.s32(m.r(a3 + GOFF[f], 'l')) for f in GF}
        want = {f: getattr(st, f) for f in GF}
        if got != want or any(c.d[r] != 0x4400 + r for r in (3, 4, 5, 6)) or c.a[7] != STACK:
            return 'case %d: %s' % (it, {f: (got[f], want[f]) for f in GF if got[f] != want[f]})
    return None
bad = gate_fuzz(3000 if FULL else 800, 5)
check('gate_state_machine_bit_exact', bad is None, bad or 'random states and inputs, every field')

# v7.4 (Discord, 2 Nov 2026): GATE 303's first note after PLAY.  A stopped sequencer, then PLAY in the orders the
# position reset and the first tick could reach the gate (a pair one or two frames apart, the START with either):
# the first note stays open 3.5 ticks, as every other (before: ~1.5 ms in the paired orders: silent).
class _GatePair:
    """v7.5 (review): o3_gate and ref303.gate_frame on one state each, frame by frame, every field compared"""
    def __init__(self, st, t=0):
        self.st, self.t, self.rig = st, t, Rig(); c = self.rig.cpu; self.a3 = c.consts['o3_state'] + t * 512; self.bad = None
        for f in GF: c.mem.w(self.a3 + GOFF[f], 'l', getattr(st, f) & M32)
    def __call__(self, seq):
        c = self.rig.cpu; m = c.mem
        self.rig.seq(self.t, seq); m.w(self.a3 + GOFF['gnew'], 'l', self.st.gnew & M32)
        c.d[2] = self.t; c.a[3] = self.a3; c.a[7] = STACK
        c.call('o3_gate'); R.gate_frame(self.st, seq)
        if self.bad is None:
            got = {f: R.s32(m.r(self.a3 + GOFF[f], 'l')) for f in GF}; want = {f: getattr(self.st, f) for f in GF}
            if got != want: self.bad = {f: (got[f], want[f]) for f in GF if got[f] != want[f]}
_GBAD = []
def _first_open(stop_frames, stop_at_tick=5, fpt=57, play_tick1_after=1, start_at=1, fresh=False, stop_word=0):
    """the gate through the order measured under the port (3 Nov 2026, 1.40C MKI): a run, STOP (transport 0 or 2, step
    word 0, the tick kept), PLAY (step word 1, tick 0, transport 1; tick 1 the next frame), the START a frame after
    PLAY; returns the frames the first note's gate stays open (3.5 ticks: ~200)"""
    st = R.Track(); st.latched = 1; st.gsel = 1; G = _GatePair(st)   # v7.5: the asm alongside, every frame
    if not fresh:                                              # fresh: the first PLAY after boot (review)
        for s_ in range(1, 4):                                 # running: the step word is the NEXT step
            for k_ in range(6):
                for _ in range(fpt): G((127, s_, k_, 0, 16, 1))
        for _ in range(fpt * stop_at_tick // 6): G((127, 4, 0, 0, 16, 1))
        for _ in range(stop_frames):                           # STOP early in a tick (Q1's regression); stop_word 2:
            G((127, 4 if stop_word == 2 else 0, 0, 0, 16, stop_word))   # the STOP key, the position kept (STEM_REC.md)
    seqs = [(127, 1, 0, 0, 16, 1)] * play_tick1_after + [(127, 1, 1, 0, 16, 1)] * fpt
    for t_ in range(2, 6): seqs += [(127, 1, t_, 0, 16, 1)] * fpt
    for fr, sq in enumerate(seqs):
        if fr == start_at: st.gnew = 1
        G(sq)
        if fr > start_at and not st.gate: _GBAD.append(G.bad); return fr - start_at
    _GBAD.append(G.bad); return None
_fo = [_first_open(3000), _first_open(200), _first_open(3000, stop_at_tick=1), _first_open(30, stop_at_tick=1),
       _first_open(3000, start_at=0), _first_open(0, fresh=True), _first_open(0, fresh=True, start_at=0),
       _first_open(3000, stop_word=2), _first_open(3000, stop_word=2, start_at=0)]
check('gate_first_note_after_play', all(f is not None and 195 <= f <= 205 for f in _fo) and not any(_GBAD),
      'open frames %s (3.5 ticks = 199; also the first PLAY after boot and the STOP key); asm == ref %s' % (_fo, [b for b in _GBAD if b] or 'every frame'))
def _slide_open(mark):
    """a note on step 1 (the START a frame after the step word reads 1), a slide marker on step `mark` (0-based):
    the frames the gate stays open; legato only for a marker on the next step"""
    st = R.Track(); st.latched = 1; st.gsel = 1; fpt = 57; sl = 1 << mark; G = _GatePair(st)
    for k_ in range(6):
        for _ in range(fpt): G((127, 0, k_, sl, 16, 1))
    seqs = []
    for s_ in (1, 2, 3, 4):
        for k_ in range(6): seqs += [(127, s_ % 16, k_, sl, 16, 1)] * fpt
    for fr, sq in enumerate(seqs[1:]):
        if fr == 0: st.gnew = 1
        G(sq)
        if fr > 0 and not st.gate: _GBAD.append(G.bad); return fr
    _GBAD.append(G.bad); return None
_GBAD = []
_so = [_slide_open(1), _slide_open(2), _slide_open(5)]
check('gate_slide_on_the_next_step', 540 <= _so[0] <= 560 and all(195 <= x <= 205 for x in _so[1:]) and not any(_GBAD),
      'marker on step 2: %s frames (legato), step 3: %s, step 6: %s (3.5 ticks)' % tuple(_so))

PATG = [(0, 1, 0), (12, 0, 1), (7, 0, 0), (None, 0, 0), (0, 0, 1), (3, 1, 1), (5, 0, 0), (0, 0, 0)] * 2
SLIDES = sum(1 << ((i + 1) % 16) for i, p in enumerate(PATG) if p[2])
def gate_script(fname, steps=32, tf=2, setup=None, alive=True):
    """the sequencer sped up: 6 ticks a step, tf frames a tick; PATG's trigs, slides as trigless steps;
    setup = the TB-303 machine's SETUP bytes (None: the carrier fname names, on the machine: run(), SU)"""
    sc = []
    for f in range(steps * 6 * tf):
        k = f // tf; sq = (127, k // 6 + 1, k % 6, SLIDES, 16)          # v7.5: the step word holds the NEXT step
        st_i = (k // 6) % 16; first = f % (6 * tf) == 0
        n, acc, sl = PATG[st_i]; prev = PATG[(st_i - 1) % 16]
        trig = first and n is not None and not prev[2]
        tune = n if n is not None else (prev[0] or 0)
        if not trig and prev[2] and n is not None: tune = n            # the slide's lock
        w = W(tune, 30, 110, 80, 40, 120 if acc else 0)
        sc.append((w, 0 if trig else None, fname, alive, None, 1, sq, None, setup))
    return sc
okg = True
for wv in (0, 1, 2, 3, 4, 5, 6, 7):
    A, B, mm = run(gate_script('KICK.WAV', setup=(wv, 1, 64, 0, 0, 64))); okg &= mm is None
check('bit_exact_machine_gate_303', okg, 'WAVE SAW SQR SAW+D SQR+D RSAW RSQR RSAWD RSQRD (v7.9), GATE 303, slides, rests, 32 steps')
A0, _, mm0 = run(gate_script('KICK.WAV', setup=(1, 0, 90, 60, 100, 20), alive=False))
check('bit_exact_machine_gate_off_dead_voice', mm0 is None, 'GATE OFF, FINE/SLID/DRIV/ACCV moved, no sample voice')
_, _, mm1 = run(gate_script('TB303SQD.WAV'))
check('bit_exact_machine_gate_off_with_sequencer', mm1 is None, 'SQR+D, GATE OFF (v6.9 sample for sample), the sequencer running')
def gate_len(tf, setup=(0, 1, 64, 0, 0, 64)):
    """frames from a START to the gate's close, the sequencer at tf frames a tick (no slide)"""
    st = R.Track(); n = None
    for f in range(6 * tf * 4):
        k = f // tf; sq = (127, k // 6, k % 6, 0, 16)
        R.render_call(st, W(), f == 0 or f == 6 * tf * 2, 0, 16, True, None, last=True, seq=sq, setup=setup)
        if f >= 6 * tf * 2 and n is None and st.gate == 0: n = f - 6 * tf * 2
    return n
_gl = [gate_len(tf) for tf in (2, 3, 4)]
check('gate_303_is_3_5_of_6_clocks', _gl == [7, 11, 14], 'closes after %s frames at 12/18/24 frames a step (Whittle: 58%%)' % _gl)
check('gate_off_never_closes', gate_len(2, (0, 0, 64, 0, 0, 64)) is None)

# ---------------------------------------------------------------- v7.0: the TB-303 machine's bit-exact runs
def mscen(seed, frames):
    rnd = random.Random(seed); sc = []; w = W(); su = [0, 0, 64, 0, 0, 64]; df = None; slot = 1
    for f in range(frames):
        start = None
        if f == 0 or rnd.random() < 0.06:
            start = rnd.choice([0, 0, 5, 11])
            w = W(rnd.randint(-24, 24), rnd.randint(0, 127), rnd.randint(0, 127), rnd.randint(0, 127),
                  rnd.randint(0, 127), rnd.choice([0, 0, 64, 127]))
        if rnd.random() < 0.05:                                            # SETUP moved or locked
            i = rnd.randrange(6); su = list(su)
            su[i] = rnd.choice([0, 1, 2, 3, 4, 5, 6, 7, 8, 63, 64, 65, 127, 200, rnd.randint(0, 127)])
        if rnd.random() < 0.03:
            df = None if rnd.random() < 0.4 else tuple(rnd.randint(0, 127) for _ in range(12)); slot = rnd.choice([1, 2])
        k = f // 2; sq = (127, k // 6, k % 6, rnd.getrandbits(16), 16)
        sc.append((w, start, 'KICK.WAV', rnd.random() < 0.7, df, slot, sq, df, tuple(su)))
    return sc
_bad = None
for seed in range(3 if FULL else 1):
    A, B, mm = run(mscen(900 + seed, 400 if FULL else 160))
    if mm is not None: _bad = (seed, mm); break
check('bit_exact_machine_setup_page', _bad is None, 'WAVE GATE FINE SLID DRIV ACCV moved, dEVILish on/off, dead voices'
      if _bad is None else 'seed %d mismatch @%s' % _bad)
def _setup_effect(i, v):
    sc = [(W(0, 40, 100, 80, 60, 127), 0, 'KICK.WAV', True, None, 1, None, None, tuple(v if j == i else T.SETUP_NEUTRAL[j] for j in range(6)))]
    sc += [(W(0, 40, 100, 80, 60, 0), None, 'KICK.WAV', True, None, 1, None, None, sc[0][8])] * 30
    A, B, mm = run(sc); return A if mm is None else None
_n = _setup_effect(0, 0)
_eff = {nm: _setup_effect(i, v) for i, v, nm in ((0, 1, 'WAVE'), (2, 100, 'FINE'), (3, 100, 'SLID'), (4, 127, 'DRIV'), (5, 0, 'ACCV'))}
check('machine_setup_knobs_act', _n is not None and all(a is not None and a != _n for nm, a in _eff.items() if nm != 'SLID'),
      'WAVE FINE DRIV ACCV change the sound (SLID: the next slide)')
# ---------------------------------------------------------------- v7.9: WAVE's R, the factory preset (TM3 as Roland trims it)
def _fab_render(code, cut=64, res=127, env=0, dec=0, frames=3600):
    st = R.Track(); y = []
    for f in range(frames):
        r = R.render_call(st, W(-12, cut, res, env, dec, 0), f == 0, code if f == 0 else -1, 16)   # key C = C2, 65.4 Hz
        y += [R.s32(x) >> 16 for x in r]
    return y, st
def _ring_ms(y, a, b, fs=44100.0):
    """service notes p. 7: the first interval between the ring's peaks after the saw's edge: the VCO's cycles averaged
    in sync, the harmonics under 150 Hz removed (the cycle is periodic: an FFT high-pass; numpy only)"""
    import numpy as np
    x = np.asarray(y[int(a * fs):int(b * fs)], float)
    f0 = R.T.F_LOW * 2 ** (52 / 12.0); P = fs / f0; n = int(len(x) / P) - 1
    cyc = np.mean([np.interp(np.arange(int(P)), np.arange(len(x)) - k * P, x) for k in range(n)], axis=0)
    X = np.fft.rfft(cyc); X[:int(150.0 / (fs / len(cyc))) + 1] = 0; h = np.fft.irfft(X, len(cyc))
    e = int(np.argmax(np.abs(np.diff(np.tile(cyc, 2)))[:len(cyc)])); h = np.roll(h, -e - 2)
    w = h[:int(0.006 * fs)]; sg = np.sign(w[np.argmax(np.abs(w[:int(0.002 * fs)]))])
    pk = [i for i in range(1, len(w) - 1) if (w[i] - w[i - 1]) * (w[i + 1] - w[i]) < 0 and np.sign(w[i]) == sg]
    return (pk[1] - pk[0]) / fs * 1e3 if len(pk) > 1 else float('nan')
try:
    import numpy as _np_fab                                 # the emu extra brings numpy; without it the ring check skips
except ImportError:
    _np_fab = None
_yr, _ = _fab_render(4); _y0, _ = _fab_render(0)
if _np_fab is None:
    _rr = _r0 = [2.0] * 4; print('[SKIP] fab_roland_ring_2ms: no numpy')
else:
    _rr = [_ring_ms(_yr, a, a + 0.1) for a in (0.5, 0.7, 0.9, 1.1)]; _r0 = [_ring_ms(_y0, a, a + 0.1) for a in (0.5, 0.7, 0.9, 1.1)]
check('fab_roland_ring_2ms', all(abs(v - 2.0) <= 0.1 for v in _rr),
      "RSAW at Roland's VCF procedure (key C, CUT 64, RES 127, ENV/DEC/ACC 0): the ring's first interval %s ms, 500-1200 ms "
      "(2.0 +- 0.1; SAW, Din Sync's 303: %s ms)" % ('/'.join('%.2f' % v for v in _rr), '/'.join('%.2f' % v for v in _r0)))
_sh = []
for _c in (0, 32, 64, 95, 127):
    _, _sa = _fab_render(0, _c, 127, 0, 0, 300); _, _sb = _fab_render(4, _c, 127, 0, 0, 300)
    _sh.append(_sb.sctrl - _sa.sctrl)
check('fab_same_octaves_every_cut', all(v == T.TM3_FAB or (v < T.TM3_FAB and _c == 127) for v, _c in zip(_sh, (0, 32, 64, 95, 127))),
      'the cutoff moves by %d (%.3f octave) at CUT 0/32/64/95/127: %s (the ladder\'s top clamps)' % (T.TM3_FAB, T.TM3_FAB / 3072.0, _sh))
# ---------------------------------------------------------------- v7.7: DRIV = VR8 past Din Sync's position, into Q33/Q34
import types as _ty
def _drv_ops(y, g):
    """every product of octa303.s's .Losd / DRVSAT path (= ref303.drive), for the overflow sweep"""
    y = max(-T.DRV_YLIM, min(T.DRV_YLIM, y)); m = [(y >> 6) * g]; x = m[0] >> 6
    K, Rr, Wd, D4 = (T.DRV_KN, T.DRV_RN, T.DRV_WN, T.DRV_DN4) if x < 0 else (T.DRV_KP, T.DRV_RP, T.DRV_WP, T.DRV_DP4)
    d = abs(x) - K
    if d > 0:
        d = min(d, D4); m.append(d * Rr); t = m[-1] >> 6; i = t >> 16
        if i >= 256: v = T.DRV_TH[256]
        else: m.append((T.DRV_TH[i + 1] - T.DRV_TH[i]) * ((t & 0xFFFF) >> 1)); v = T.DRV_TH[i] + (m[-1] >> 15)
        m.append(Wd * v)
    return m
_ovf = _n = 0; _hi = _lo = 0
_ys = list(range(-(1 << 25), (1 << 25) + 1, 8191)) + [s * (T.DRV_YLIM + e) for s in (-1, 1) for e in (-1, 0, 1)] + [s * (1 << 25) for s in (-1, 1)]
for g in T.DRV_G[1:]:
    st_ = _ty.SimpleNamespace(osin=g)
    for y in _ys:
        for v in _drv_ops(y, g):
            _n += 1; _ovf += not (-2 ** 31 <= v < 2 ** 31)
        o = R.drive(st_, y); _hi = max(_hi, o); _lo = min(_lo, o)
check('driv_no_overflow', _ovf == 0, '%d products, DRIV 1..127, y over +-2^25: every one in 32 bits' % _n)
check('driv_ceiling_per_side', 0 < _hi <= T.DRV_LP and -T.DRV_LN <= _lo < 0,
      'max %+d <= L+ %d, min %+d >= -L- %d' % (_hi, T.DRV_LP, _lo, T.DRV_LN))
def _drv_scen(drv, wave, df):
    su = (wave, 1, 64, 0, drv, 64); sc = []
    for f in range(144 if FULL else 48):
        k = f // 2; sq = (127, k // 6, k % 6, 0, 16); acc = 127 if (f // 12) % 2 == 0 else 0
        sc.append((W(12 if acc else -12, 127, 127, 127, 64, acc), 0 if f % 12 == 0 else None, 'KICK.WAV', True, df, 1, sq, df, su))
    return sc
def _drv_never(st, y): raise AssertionError('drive() called at DRIV 0')
_drv_keep = R.drive; R.drive = _drv_never
try:
    _ok0 = True
    for wv in (0, 2):
        for df in (None, (127,) * 12):
            _, _, _mm0 = run(_drv_scen(0, wv, df)); _ok0 &= _mm0 is None
except AssertionError:
    _ok0 = False
finally:
    R.drive = _drv_keep
check('driv_0_skips_the_block', _ok0 and T.DRV_G[0] == T.DRV_G0 == 4096 and T.DRV_G[1] != 4096,
      'DRIV 0, loud accents, SAW and SAW+D, dEVILish on/off: the reference never enters drive() and the asm equals it')
_bad = None; _pk = {}
for drv in (1, 64, 127):
    for wave in ((0, 1, 2, 3) if drv == 127 else (0, 2)):              # 2, 3 = the pedal voices: the positive side's knee and cap
        for df in (None, (127,) * 12):
            A, B, mm = run(_drv_scen(drv, wave, df))
            if mm is not None and _bad is None: _bad = (drv, wave, df is not None, mm)
            s = [((v & 0xFFFFFFFF) >> 16) - (65536 if v & 0x80000000 else 0) for v in A]
            _pk[(drv, wave, df is not None)] = (max(s), min(s))
check('bit_exact_driv_loud', _bad is None, 'DRIV 1/64 (SAW, SAW+D) and 127 (all four waves), dEVILish all 127 on/off, accents 127 at CUT/RES/ENV 127'
      if _bad is None else 'DRIV %d wave %d dEVILish %s mismatch @%s' % _bad)
_neg = min(v[1] for k, v in _pk.items() if k[0] == 127); _pos = max(v[0] for k, v in _pk.items() if k[0] == 127)
check('driv_127_reaches_both_knees', _neg <= -(T.DRV_KN >> 6) and _pos >= (T.DRV_KP >> 6),
      'DRIV 127: peaks %+d / %+d, knees -%d / +%d (the bit-exact run covers both sides)' % (_pos, _neg, T.DRV_KN >> 6, T.DRV_KP >> 6))

# ---------------------------------------------------------------- v7.8 (V8A): the MEG and the accent from the circuit
def _meg_t10(dec):                                   # ref303's own MEG (the integer steps), frames to 10 % of its peak
    m, n = T.ONE30, 0
    while m > T.ONE30 // 10 and n < 20000:
        m = R.mul30(m, R.megf(m, dec)); n += 1
    return n * T.CS / T.FS * 1e3
_t0, _t127 = _meg_t10(0), _meg_t10(127)
check('meg_roland_min_max', abs(_t0 - 200.0) < 4.0 and abs(_t127 - 2500.0) < 50.0,
      'DECAY 0 (and accents) at 10 %% in %.0f ms, DECAY 127 in %.0f ms (Roland: MIN 200 ms, MAX 2.5 s)' % (_t0, _t127))
_mono = all(0 < R.megf(m, d) < T.ONE30 for d in range(128) for m in (1, 3, 1000, 1 << 10, 1 << 15, 1 << 20, 1 << 25, T.ONE30 // 3, T.ONE30))
_dmono = all(_meg_t10(d) <= _meg_t10(d + 8) for d in range(0, 120, 8))
check('meg_factor_sane', _mono and _dmono, 'every factor in (0, 1) at any level and DECAY; the decay time grows with DECAY')
_rat = [((1 << 30) - row[j + 1]) / float((1 << 30) - row[j]) for row in T.MEG_T for j in range(T.MEG_NLEV - 4)]
check('meg_table_smooth', 0.5 < min(_rat) and max(_rat) < 1.5,
      "each row's decay (1 - factor) moves by %.3f..%.3f a level step: no stuck tail (review: a factor of 1.0 past the run's end)" % (min(_rat), max(_rat)))
# ---------------------------------------------------------------- v7.9: dEVILish ADEC continuous (ADEC_T, o3meg.adec_tables)
def _adec_t10(a):                                    # the accent MEG at dEVILish ADEC a, frames to 10 %, in ms
    m, n = T.ONE30, 0
    while m > T.ONE30 // 10 and n < 40000:
        m = R.mul30(m, R.megf(m, T.DF_ADEC[a], T.ADEC_T)); n += 1
    return n * T.CS / T.FS * 1e3
_lv = (1, 3, 1000, 1 << 10, 1 << 15, 1 << 20, 1 << 25, T.ONE30 // 3, T.ONE30 // 2, T.ONE30 - 1, T.ONE30)
check('adec_50_is_v78', T.ADEC_T[T.ADEC_Q50 >> 2] == T.MEG_T[0] and T.DF_ADEC[50] == T.ADEC_Q50
      and all(R.megf(m, T.ADEC_Q50, T.ADEC_T) == R.megf(m, 0) for m in _lv),
      'ADEC 50 (and no dEVILish) reads ADEC_T row 13 = MEG_T row 0, every factor the same bits')
_ta = [_adec_t10(a) for a in range(128)]
_up = max(_ta[a + 1] / _ta[a] for a in range(127)); _dn = min(_ta[a + 1] / _ta[a] for a in range(127))
check('adec_continuous', 1.0 <= _dn and _up <= 1.06,
      'ADEC 0..127: the time to 10 %% grows at every step, by %.1f..%.1f %% (no jump at 50: 49 %.0f / 50 %.0f / 51 %.0f ms)'
      % (100 * (_dn - 1), 100 * (_up - 1), _ta[49], _ta[50], _ta[51]))
def _adec_tl(a, lvl):                               # frames to a level below 10 %: the tail (review, 7 Nov)
    m, n = T.ONE30, 0
    while m > int(T.ONE30 * lvl) and n < 400000:
        m = R.mul30(m, R.megf(m, T.DF_ADEC[a], T.ADEC_T)); n += 1
    return n
_tl = [[_adec_tl(a, l) for a in range(0, 128, 2)] for l in (0.01, 0.001)]
check('adec_tail_monotonic', all(v[i + 1] >= v[i] for v in _tl for i in range(len(v) - 1)),
      'the tail too (1 %% and 0.1 %%) lengthens with ADEC, across 50 included (ADEC 50: %.0f / %.0f ms)'
      % (_adec_tl(50, 0.01) * T.CS / T.FS * 1e3, _adec_tl(50, 0.001) * T.CS / T.FS * 1e3))
check('adec_ends_devil_fish', abs(_ta[0] - 30.0) <= 2.0 and abs(_ta[127] - 3000.0) <= 100.0,
      'ADEC 0 at 10 %% in %.1f ms, ADEC 127 in %.0f ms (Devil Fish Accent Decay 30 ms .. 3 s)' % (_ta[0], _ta[127]))
check('adec_factor_sane', all(0 < R.megf(m, q, T.ADEC_T) < T.ONE30 for q in range(2, 130) for m in _lv),
      'every ADEC_T factor in (0, 1), every row position and level')
def _twin_step(s, Tm, dt, a7, res):                  # the twin's a2_step (sim.c), floats: the circuit itself
    import math
    VT, NVT, IS = 0.02585, 1.752 * 0.02585, 2.52e-9
    def iser(v, Rr):
        if v <= 0: return 0.0
        i = max(0.5 * v / Rr, 1e-12)
        for _ in range(60):
            f = i * Rr + NVT * math.log(1 + i / IS) - v; i2 = i - f / (Rr + NVT / (IS + i))
            if i2 <= 0: i2 = 0.1 * i
            if abs(i2 - i) < 1e-15: return i2
            i = i2
        return i
    r = T._smap(res / 127.0, 0.16)
    Rt = (1 - a7) * 50e3 + 201.0; Rb = a7 * 50e3 + 1.0; kth = Rb / (Rt + Rb); Rth = Rt * Rb / (Rt + Rb)
    Rbw = r * 50e3 + 1.0; Rwc = (1 - r) * 50e3 + 1.0; RA = 47e3 + Rbw + Rwc * 1e5 / (Rwc + 1e5)
    VA0 = (s['vc'] * 1e5 + 3.27 * Rwc) / (Rwc + 1e5); g = 1 / Rth + 1 / 47e3
    Ve = (Tm * kth / Rth + s['v34'] / 47e3) / g; Re = 1 / g
    i24 = iser(Ve - VA0, Re + RA); W7 = Ve - i24 * Re
    k = dt / (1e-6 * (Rwc + 1e5)); s['vc'] = (s['vc'] + k * (3.27 + i24 * 1e5)) / (1 + k)
    V69 = VT * math.log(1.0 + (48e-6 + s['i27']) / 1e-14); G = 0.033e-6 / dt + 1 / 47e3
    i27 = iser((0.033e-6 * s['v34'] / dt + W7 / 47e3) / G - V69, 22e3 + 1 / G)
    s['v34'] = (0.033e-6 * s['v34'] / dt + W7 / 47e3 - i27) / G; s['i27'] = i27
    Wp = (s['vc'] * 1e5 + 3.27 * Rwc) / (Rwc + 1e5) + i24 * Rwc * 1e5 / (Rwc + 1e5)
    return 2.2e3 * (Wp - 3.27) / 1e5 / (VT * math.log(2))
_ew, _ev, _vmax = 0.0, 0.0, 0
for _acc, _res in ((127, 0), (127, 127), (95, 64), (64, 32), (32, 127), (8, 100)):
    _st = R.Track(); _st.acci, _st.res, _st.spd = _acc, _res, 2
    _tw = {'vc': 3.27, 'v34': 0.0, 'i27': 0.0}; _a7 = T._smap(_acc / 127.0, 0.16)
    _m = T.ONE30
    for _f in range(2000):                            # 0.73 s: three accents 240 ms apart, the MEG's own decay
        if _f % 660 == 0: _m = T.ONE30
        _m = R.mul30(_m, R.megf(_m, 0)) if _f % 660 < 600 else 0
        _sw, _vi = R.accent(_st, _m)
        for _j in range(2): _oc = _twin_step(_tw, 9.99 * _m / 2.0 ** 30, T.CS / T.FS / 2, _a7, _res)
        _ew = max(_ew, abs(_sw / 3072.0 - _oc)); _ev = max(_ev, abs(_vi / 16384.0 - _tw['i27'] / 48e-6)); _vmax = max(_vmax, _vi)
check('accent_is_the_circuit', _ew < 0.01 and _ev < 0.01,
      'ref303 vs the circuit in floats (the twin\'s a2_step): push within %.4f octaves, I27 / I_Q31 within %.4f (max %.2f)' % (_ew, _ev, _vmax / 16384.0))
_ovf, _n = 0, 0
_keep = R.CHECK; R.CHECK = True
try:
    for _spd in (1, 2, 3):
        for _acc in (1, 64, 95, 127):
            for _res in (0, 64, 127):
                _st = R.Track(); _st.acci, _st.res, _st.spd = _acc, _res, _spd
                for _f in range(1500):
                    _m = T.ONE30 if _f % 100 < 3 else T.ONE30 // 2   # accents in a row, the MEG near its peak
                    _sw, _vi = R.accent(_st, _m); _n += 1
                    if not (0 <= _st.dvc < 2 ** 30 and 0 <= _st.v34 < 2 ** 30 and 0 <= _st.y27 <= T.AC_YMAX
                            and 0 <= _sw < 2 ** 24 and 0 <= _vi * 127 < 2 ** 31): _ovf += 1
except OverflowError: _ovf += 1
R.CHECK = _keep
check('accent_no_overflow', _ovf == 0, '%d frames, SPD FAST/NORM/SLOW, ACC 1..127, RES 0..127, the MEG held high: states in range' % _n)
import inspect as _insp, random as _rnd
_src = _insp.getsource(R.accent).replace("if tm == 0 and st.v34 == 0", "if False and tm == 0 and st.v34 == 0").replace('def accent(', 'def _accent_full(')
_ns = dict(R.__dict__); exec(_src, _ns); _full = _ns['_accent_full']
_r = _rnd.Random(78); _bad = 0
for _k in range(3000 if FULL else 600):
    _s1 = R.Track(); _s1.acci, _s1.res, _s1.spd = _r.randint(0, 127), _r.randint(0, 127), _r.choice([1, 2, 3])
    _s1.dvc = _r.choice([0, _r.randint(0, 2000), _r.randint(0, 10 ** 6)]); _s1.v34 = _r.choice([0, 0, _r.randint(0, 10 ** 6)])
    _s1.y27 = _r.choice([0, 0, _r.randint(0, 10 ** 6)]); _tm = _r.choice([0, 0, _r.randint(0, T.ONE30)])
    _s2 = R.Track(); _s2.__dict__.update(_s1.__dict__)
    if R.accent(_s1, _tm) != _full(_s2, _tm) or (_s1.dvc, _s1.v34, _s1.y27) != (_s2.dvc, _s2.v34, _s2.y27): _bad += 1
check('accent_rest_shortcut_exact', _bad == 0, 'the at-rest shortcut = the two sub-steps, outputs and state (%d random states)' % (3000 if FULL else 600))
check('p6_asymmetric', abs(T.P6_FP[256] / T.P6_F[256] - T.CAL['p6r']) < 0.002,
      'pin 6: the positive side at %.3f x the negative (p6r %.2f)' % (T.P6_FP[256] / T.P6_F[256], T.CAL['p6r']))
def _acc_scen(df, accs=(127, 95, 64, 32, 0), res=(0, 64, 127)):
    sc = []
    for r in res:
        for a in accs:
            for f in range(36 if FULL else 18):
                sc.append((W(12 if a else -12, 90, r, 100, 40, a), 0 if f == 0 else None, 'TB303.WAV', True, df))
    return sc
_bad = None
for _df in (None, (25, 0, 0, 64, 0, 50, 0, 0, 0, 0, 0, 0), (25, 0, 0, 64, 0, 50, 0, 0, 2, 0, 0, 0),
            (25, 0, 0, 64, 0, 10, 0, 0, 1, 0, 0, 0), (25, 0, 0, 64, 0, 127, 0, 2, 1, 0, 0, 0),
            (25, 0, 0, 64, 0, 0, 0, 0, 1, 0, 0, 0), (25, 0, 0, 64, 0, 49, 0, 0, 1, 0, 0, 0),
            (25, 0, 0, 64, 0, 51, 0, 0, 1, 0, 0, 0), (25, 0, 0, 64, 0, 90, 0, 0, 1, 0, 0, 0)):
    _A, _B, _mm = run(_acc_scen(_df))
    if _mm is not None and _bad is None: _bad = (_df, _mm)
check('bit_exact_accent_circuit', _bad is None,
      'accents in a row ACC 127..0 at RES 0/64/127: the 303, SPD FAST, SPD SLOW, ADEC 0/10/49/50/51/90/127 (v7.9: ADEC_T), SWP SELF'
      if _bad is None else 'dEVILish %s mismatch @%s' % _bad)

# ---------------------------------------------------------------- v7.0: the machine's registration helpers
PP = lambda part: BANK + 0x8ed80 + part * 6322
def mrig(part=1, cur=None, sig=((2, b'TB\x01'),), types=None):
    rig = Rig(); c = rig.cpu; m = c.mem
    m.w(0x46c82456, 'l', BANK); m.w(0x100b14cf, 'b', part if cur is None else cur)
    P = PP(part)
    for t in range(8): m.w(P + 0x22 + t, 'b', (types or [1] * 8)[t])
    for t, b in sig:
        for i, x in enumerate(b): m.w(P + 0x3c + 30 * t + i, 'b', x)
    return rig, c, m, P
def sig(t, **kw):
    rig, c, m, P = mrig(**kw); c.a[0] = P; c.d[0] = t; c.a[7] = STACK; c.a[1] = 0x1234
    c.call('o3_sig'); return c.d[0], c.a[1] == 0x1234
check('sig_reads_the_signature', sig(2) == (1, True) and sig(3)[0] == 0 and sig(2, sig=((2, b'TB\x02'),))[0] == 0
      and sig(2, sig=((2, b'AB\x01'),))[0] == 0 and sig(2, types=[1, 1, 3, 1, 1, 1, 1, 1])[0] == 0 and sig(9)[0] == 0,
      'FLEX + T B 1 only (ANALOG BD\'s A B 1 is not ours)')
def otype(v, off, **kw):
    rig, c, m, P = mrig(**kw); c.a[0] = P + 0x22 + off if off is not None else 0x80001234; c.d[0] = v
    a0 = c.a[0]; c.d[1] = 0x77; c.a[1] = 0x88; c.a[7] = STACK
    c.call('o3_type'); return c.d[0], (c.a[0], c.d[1], c.a[1], c.a[7]) == (a0, 0x77, 0x88, STACK)
check('type_maps_signed_flex_to_row_5', otype(1, 2) == (5, True) and otype(1, 3) == (1, True) and otype(0, 2)[0] == 0
      and otype(1, None) == (1, True) and otype(1, 2, cur=0)[0] == 1 and otype(1, 9)[0] == 1)
def swrite(t, flag, pre=None, part=1, cur=None):
    rig, c, m, P = mrig(part=part, cur=cur, sig=pre or ())
    for i in range(72): m.w(CURVALS + 72 * t + i, 'b', 0xDD)
    sh = P - BANK - 0x8ed80 + 0x100a4ece
    for k in range(6):
        for base in (P, sh): m.w(base + 0x30 + 30 * t + k, 'b', 0x11 + k); m.w(base + 0x1e0 + 30 * t + k, 'b', 0x21 + k)
    if pre:
        for tt, b in pre:
            for i, x in enumerate(b): m.w(sh + 0x3c + 30 * tt + i, 'b', x)
    c.a[0] = P; c.d[0] = t; c.d[1] = flag; c.d[2] = 0x55; c.a[1] = 0x66; c.a[7] = STACK
    c.call('o3_sigwrite')
    kept = (c.a[0], c.d[0], c.d[1], c.d[2], c.a[1], c.a[7]) == (P, t, flag, 0x55, 0x66, STACK)
    g = lambda a, n: bytes(m.r(a + i, 'b') for i in range(n))
    swrite.lane = (g(CURVALS + 72 * t, 6), g(CURVALS + 72 * t + 0x20, 6), g(CURVALS + 72 * t + 6, 26))
    return [(g(b + 0x3c + 30 * t, 3), g(b + 0x30 + 30 * t, 6), g(b + 0x1e0 + 30 * t, 6)) for b in (P, sh)], kept
_w, _k = swrite(4, 1)
_d1, _d2 = bytes([64, 64, 64, 64, 64, 0]), bytes(T.SETUP_NEUTRAL)
check('sigwrite_new_machine_defaults', _k and all(x == (b'TB\x01', _d1, _d2) for x in _w), str(_w))
check('sigwrite_current_part_lane', swrite.lane == (_d1, _d2, b'\xdd' * 26), str(swrite.lane))
_w, _k = swrite(4, 1, cur=0)
check('sigwrite_other_part_no_lane', _k and swrite.lane == (b'\xdd' * 6, b'\xdd' * 6, b'\xdd' * 26) and all(x[0] == b'TB\x01' for x in _w))
_w, _k = swrite(4, 1, pre=((4, b'TB\x01'),))
check('sigwrite_reselect_keeps_the_knobs', _k and all(x == (b'TB\x01', bytes(range(0x11, 0x17)), bytes(range(0x21, 0x27))) for x in _w))
_w, _k = swrite(4, 0, pre=((4, b'TB\x01'),), part=3)
check('sigwrite_other_machine_unsigns', _k and all(x[0] == b'\0\0\0' and x[1] == bytes(range(0x11, 0x17)) for x in _w))
_w, _k = swrite(4, 0, pre=((4, b'AB\x01'),))
check('sigwrite_leaves_analog_bd_alone', _k and all(x[0] == b'AB\x01' for x in _w))
def validate():
    rig, c, m, P = mrig(sig=((2, b'TB\x01'), (7, b'TB\x01')))
    stock = [(i * 13 + 1) & 0x7F for i in range(12)]
    for i in range(12): m.w(0x400d320c + i, 'b', stock[i])
    for t in range(8):
        for k in range(6): m.w(P + 0x30 + 30 * t + k, 'b', 100 + k); m.w(P + 0x1e0 + 30 * t + k, 'b', 110 + k)
    seen = []
    def hook(cpu):
        mm = cpu.mem; sp = cpu.a[7]
        part = mm.r(sp + 96 + 4, 'l')
        seen.append([[mm.r(part + 0x30 + 30 * t + k, 'b') for k in range(6)] + [mm.r(part + 0x1e0 + 30 * t + k, 'b') for k in range(6)] for t in range(8)])
        regs = [mm.r(sp + 4 * i, 'l') for i in range(11)]
        for i, r in enumerate(range(2, 8)): cpu.d[r] = regs[i]
        for i, r in enumerate(range(2, 7)): cpu.a[r] = regs[6 + i]
        cpu.a[7] = sp + 96; cpu.d[0] = 0xAB
    c.hooks[0x40002320] = hook
    c.a[7] = STACK - 8; m.w(STACK - 8, 'l', P)
    for r in range(2, 8): c.d[r] = 0x3300 + r
    for r in range(2, 7): c.a[r] = 0x4400 + r
    c.call('o3_validate')
    kept = all(c.d[r] == 0x3300 + r for r in range(2, 8)) and all(c.a[r] == 0x4400 + r for r in range(2, 7)) and c.a[7] == STACK - 8
    after = [[m.r(P + 0x30 + 30 * t + k, 'b') for k in range(6)] + [m.r(P + 0x1e0 + 30 * t + k, 'b') for k in range(6)] for t in range(8)]
    own = list(range(100, 106)) + list(range(110, 116))
    return seen and all(seen[0][t] == (stock if t in (2, 7) else own) for t in range(8)) and after == [own] * 8 and kept and c.d[0] == 0xAB
check('validate_sees_flex_defaults_then_restores', validate())
def mdesc_built():
    rig = Rig(); c = rig.cpu; m = c.mem
    for i in range(0x192): m.w(FLEX_P + i, 'b', (i * 7 + 3) & 0xFF)
    c.a[7] = STACK; c.call('o3_mdesc'); d = c.d[0]
    return c, d, bytes(m.r(d + i, 'b') for i in range(0x192))
c, d, md = mdesc_built()
exp = playback_exp(c, STOCKREC)
exp[0x3a:0x5e] = b''.join(n.encode().ljust(6, b'\0') for n in T.SETUP_NAMES); exp[0x64:0x6a] = bytes(T.SETUP_NEUTRAL)
for k in range(6):
    exp[0x82 + 4 * k:0x86 + 4 * k] = bytes(4); exp[0xb2 + 4 * k:0xb6 + 4 * k] = T.SETUP_COUNT[k].to_bytes(4, 'big')
    exp[0x112 + 4 * k:0x116 + 4 * k] = bytes(4); exp[0x142 + 4 * k:0x146 + 4 * k] = bytes(4)
exp[0xe2:0xfa] = b''.join(c.consts[n].to_bytes(4, 'big') for n in ('o3_fmt_wave', 'o3_fmt_gate', 'o3_fmt_fine')) + (0x4003c178).to_bytes(4, 'big') * 3
exp[0x18a:0x192] = bytes.fromhex('0000111111311311')
check('machine_record_fields', d == c.consts['o3_desc'] and md == bytes(exp),
      'diff at %s' % [hex(i) for i in range(0x192) if md[i] != exp[i]][:6])
check('machine_tune_three_octaves', md[0x16:0x1c] == b'TUNE\0\0' and md[0x5e] == STOCKREC[0x5e]
      and int.from_bytes(md[0x6a:0x6e], 'big') == 40 and int.from_bytes(md[0x9a:0x9e], 'big') == 49
      and 4 <= 40 and 40 + 49 - 1 <= 124, 'raw 40..88 = -24..+24, inside the Part validator\'s 4..124')
def mpage(signed, path='/AUDIO/KICK.WAV'):
    rig = Rig(); c = rig.cpu; m = c.mem
    for i in range(0x192): m.w(FLEX_P + i, 'b', (i * 7 + 3) & 0xFF)
    m.w(TABLE + 4, 'l', FLEX_P); part, track = 2, 5
    m.w(BANK + part * 6322 + 0x8f04b + track * 5, 'b', 9); rig.path(9, path)
    P = PP(part); m.w(P + 0x22 + track, 'b', 1)
    for i, x in enumerate(b'TB\x01' if signed else b'\0\0\0'): m.w(P + 0x3c + 30 * track + i, 'b', x)
    c.d[0], c.a[0], c.d[3], c.d[1], c.a[1] = 1, TABLE, track, part, BANK
    for r in (6, 7): c.d[r] = 0x7777 + r
    for r in range(2, 7): c.a[r] = 0x6600 + r
    c.a[7] = STACK; done = []
    c.hooks[0x40031ed6] = lambda cpu: done.append(1)
    c.call('o3_page')
    kept = all(c.d[r] == 0x7777 + r for r in (6, 7)) and all(c.a[r] == 0x6600 + r for r in range(2, 7)) and c.a[7] == STACK
    return c.d[0] - c.consts['o3_desc'] if c.d[0] != FLEX_P else 'stock', kept and bool(done)
check('page_machine_gets_its_record', mpage(True) == (0, True) and mpage(True, '/AUDIO/TB303.WAV') == (0, True)
      and mpage(False) == ('stock', True) and mpage(False, '/AUDIO/TB303.WAV') == ('stock', True))
def lfoname(signed, machine=1):
    """o3_lfo_name at 0x4003bff0 in the LFO PMTR formatter: a0 = Part + 0x8eda2 + track, d1 = track."""
    rig = Rig(); c = rig.cpu; m = c.mem
    for i in range(0x192): m.w(FLEX_P + i, 'b', (i * 7 + 3) & 0xFF)
    part, track = 2, 5; P = PP(part); m.w(P + 0x22 + track, 'b', machine)
    for i, x in enumerate(b'TB\x01' if signed else b'\0\0\0'): m.w(P + 0x3c + 30 * track + i, 'b', x)
    c.a[0] = P + 0x22 + track; c.d[1] = track; c.d[2] = 4; c.a[2] = 0x6602; c.a[4] = 0x6604
    c.a[7] = STACK; out = []
    c.hooks[0x4003c058] = lambda cpu: out.append(('rec', cpu.a[2]))
    c.hooks[0x4003c054] = lambda cpu: out.append(('stock', cpu.a[0], cpu.d[0]))
    c.call('o3_lfo_name')
    kept = c.d[1] == track and c.d[2] == 4 and c.a[4] == 0x6604 and c.a[7] == STACK
    return out[0] if out else None, kept
_r, _k = lfoname(True)
check('lfo_names_machine_record', _k and _r[0] == 'rec' and _r[1] == Rig().cpu.consts['o3_desc'], str(_r))
check('lfo_names_flex_and_others_stock', lfoname(False) == (('stock', TABLE, 1), True)
      and lfoname(False, machine=2) == (('stock', TABLE, 2), True), str((lfoname(False), lfoname(False, 2))))
# ---- v7.1: held trig + UP / DOWN (o3_octave) and the automatic slide lock (o3_autoslide)
LK = lambda pat, t, s: BANK + pat * 0x8ed8 + t * 0x91a + 0x59 + s * 32
SH = lambda pat, t, s: 0x1001614e + pat * 0x8ed8 + t * 0x91a + 0x59 + s * 32
def lrig(signed=True, midi=0, part=1, pat=3, track=2, base=64):
    rig = Rig(); c = rig.cpu; m = c.mem
    m.w(0x46c82456, 'l', BANK); m.w(0x100b14cf, 'b', part); m.w(0x100b14d0, 'b', pat)
    m.w(0x100b14cc, 'b', track); m.w(0x80000012, 'l', midi)
    P = PP(part); m.w(P + 0x22 + track, 'b', 1)
    for i, x in enumerate(b'TB\x01' if signed else b'\0\0\0'): m.w(P + 0x3c + 30 * track + i, 'b', x)
    m.w(BANK + part * 6322 + 0x8edb0 + 30 * track, 'b', base)       # the Part's TUNE
    for s in range(64):
        m.w(LK(pat, track, s), 'b', 0xff); m.w(SH(pat, track, s), 'b', 0xff)
    return rig, c, m
def octave(key, held, page=0, locks=None, **kw):
    rig, c, m = lrig(**kw); pat, t = kw.get('pat', 3), kw.get('track', 2)
    for s, v in (locks or {}).items(): m.w(LK(pat, t, s), 'b', v)
    m.w(0x460d174a, 'w', held); m.w(0x460d174c, 'l', page)
    toast, ev, out = [], [], []
    c.hooks[0x4005a2b8] = lambda cpu: toast.append(cpu.mem.r(cpu.a[7], 'l'))
    c.hooks[0x40027e00] = lambda cpu: ev.append('e00')
    c.hooks[0x4009da20] = lambda cpu: ev.append(('da20', cpu.mem.r(cpu.a[7], 'l')))
    c.hooks[0x40027de4] = lambda cpu: out.append(('tail', cpu.a[7]))
    def _stock(cpu): out.append(('stock', cpu.a[7], cpu.mem.r(cpu.a[7], 'l'))); cpu.a[7] += 28
    c.hooks[0x400434e0] = _stock
    for r in range(2, 8): c.d[r] = 0x7700 + r
    for r in range(2, 7): c.a[r] = 0x6600 + r
    m.w(STACK - 4, 'l', 1); m.w(STACK - 8, 'l', key); c.a[7] = STACK - 8    # (key, event); call pushes the return
    c.call('o3_octave')
    kept = all(c.d[r] == 0x7700 + r for r in range(2, 8)) and all(c.a[r] == 0x6600 + r for r in range(2, 7))
    lk = {s: m.r(LK(pat, t, s), 'b') for s in range(64) if m.r(LK(pat, t, s), 'b') != 0xff}
    sh = {s: m.r(SH(pat, t, s), 'b') for s in range(64) if m.r(SH(pat, t, s), 'b') != 0xff}
    edited = m.r(BANK + 0x9b332, 'l') == 1 and m.r(0x100f8598, 'l') == 1
    return dict(locks=lk, shadow=sh, edited=edited, ev=ev, out=out, kept=kept, toast=toast, m=m)
r = octave(0x33, 0b101, page=16, locks={18: 70})               # steps 16 (no lock) and 18 (70)
_txt = ''
if r['toast']:
    _a, _b = r['toast'][0], b''
    while r['m'].r(_a + len(_b), 'b'): _b += bytes([r['m'].r(_a + len(_b), 'b')])
    _txt = _b.decode()
check('octave_up_held_steps', r['locks'] == {16: 76, 18: 82} and r['shadow'] == r['locks'] and r['edited']
      and r['ev'] == ['e00', ('da20', 2)] and r['out'] == [('tail', STACK - 12)] and r['kept'], str(r))
check('octave_toast_names_the_note', _txt == 'F#4 +OCT', repr(_txt))
r = octave(0x20, 0b1, locks={0: 45})                           # C#1 + a fifth: below C1 after an octave down
check('octave_down_stops_at_c1', r['locks'] == {0: 45} and not r['edited'] and r['ev'] == [] and r['toast'] == []
      and r['out'] == [('tail', STACK - 12)], str(r))
r = octave(0x20, 0b10, locks={1: 64})
check('octave_down', r['locks'] == {1: 52} and r['shadow'] == {1: 52}, str(r))
for kw in (dict(signed=False), dict(midi=1)):
    r = octave(0x33, 0b1, **kw)
    check('octave_stock_elsewhere_%s' % ('flex' if 'signed' in kw else 'midi'), r['locks'] == {}
          and r['out'] == [('stock', STACK - 12 - 28, 0x7702)], str(r))
def slide(steps, kind=8, trigs=(), trigless=(), tlocks=(), locks=None, other_track=False, **kw):
    """o3_trig_in, then the handler (here: set the trigless bits of `steps` at +kind), then o3_trig_out."""
    rig, c, m = lrig(**kw); pat, t = kw.get('pat', 3), kw.get('track', 2)
    rec = BANK + pat * 0x8ed8 + t * 0x91a
    setb = lambda off, s: m.w(rec + off + 7 - s // 8, 'b', m.r(rec + off + 7 - s // 8, 'b') | (1 << (s % 8)))
    for s in trigs: setb(0, s)
    for s in trigless: setb(8, s)
    for s in tlocks: setb(16, s)
    for s, v in (locks or {}).items(): m.w(LK(pat, t, s), 'b', v)
    back = []
    def _in(cpu): back.append(('in', cpu.a[7], cpu.mem.r(cpu.a[7], 'l'))); cpu.a[7] += 12
    def _out(cpu): back.append(('out', cpu.a[7])); cpu.a[7] -= 44
    c.hooks[0x40060b60] = _in; c.hooks[0x40060b48] = _out
    for r_ in range(2, 8): c.d[r_] = 0x7700 + r_
    for r_ in range(2, 6): c.a[r_] = 0x6600 + r_
    m.w(STACK - 8, 'l', 1); m.w(STACK - 4, 'l', 1)             # (key, event 1: a press)
    c.a[7] = STACK - 8; c.call('o3_trig_in')
    ok_in = back == [('in', STACK - 12 - 12, 0x7702)]
    c.a[7] = STACK                                            # the handler's frame is gone again
    for s in steps: setb(kind, s)
    if other_track: m.w(0x100b14cc, 'b', t + 1)
    # the exit: pea -1 below the saved registers (44 bytes: -1, d2-d7, a2-a5)
    base = STACK - 48
    m.w(base, 'l', 0xffffffff)
    for i, v in enumerate([0x5502 + k for k in range(6)] + [0x4402 + k for k in range(4)]): m.w(base + 4 + 4 * i, 'l', v)
    c.a[7] = base + 4; c.call('o3_trig_out')       # call's return address stands in the -1's slot
    ok_out = back[-1] == ('out', base + 44) and [c.d[k] for k in range(2, 8)] == [0x5502 + k for k in range(6)] \
        and [c.a[k] for k in range(2, 6)] == [0x4402 + k for k in range(4)]
    lk = {s: m.r(LK(pat, t, s), 'b') for s in range(64) if m.r(LK(pat, t, s), 'b') != 0xff}
    sh = {s: m.r(SH(pat, t, s), 'b') for s in range(64) if m.r(SH(pat, t, s), 'b') != 0xff}
    return lk, sh, ok_in and ok_out
# a trig with E (68) on step 20, a trigless trig placed on step 21: it ties into E
check('slide_takes_the_previous_note', slide([21], trigs=[20], locks={20: 68}) == ({20: 68, 21: 68}, {21: 68}, True),
      str(slide([21], trigs=[20], locks={20: 68})))
check('slide_trigless_lock_too', slide([21], kind=16, trigs=[20], locks={20: 68}) == ({20: 68, 21: 68}, {21: 68}, True))
check('slide_previous_trig_without_lock_is_the_part_tune', slide([21], trigs=[20], base=60) == ({21: 60}, {21: 60}, True))
check('slide_chains_through_a_slide', slide([22], trigs=[20], trigless=[21], locks={20: 68, 21: 75})
      == ({20: 68, 21: 75, 22: 75}, {22: 75}, True))
check('slide_wraps_around', slide([0], trigs=[63], locks={63: 50}) == ({63: 50, 0: 50}, {0: 50}, True))
check('slide_keeps_an_existing_lock', slide([21], trigs=[20], locks={20: 68, 21: 40}) == ({20: 68, 21: 40}, {}, True))
check('slide_only_new_trigless_steps', slide([], trigs=[20], trigless=[21], locks={20: 68}) == ({20: 68}, {}, True))
check('slide_stock_elsewhere', slide([21], trigs=[20], locks={20: 68}, signed=False) == ({20: 68}, {}, True)
      and slide([21], trigs=[20], locks={20: 68}, midi=1) == ({20: 68}, {}, True)
      and slide([21], trigs=[20], locks={20: 68}, other_track=True) == ({20: 68}, {}, True))
def mchrom(signed, idx=0):
    rig = Rig(); c = rig.cpu; m = c.mem; part, track = 2, 3
    m.w(0x46c82456, 'l', BANK); m.w(0x100b14cf, 'b', part)
    P = BANK + part * 6322
    m.w(P + 0x8eda2 + track, 'b', 1); m.w(P + 0x8f04b + track * 5, 'b', 0xff)
    for i, x in enumerate(b'TB\x01' if signed else b'\0\0\0'): m.w(P + 0x8ed80 + 0x3c + 30 * track + i, 'b', x)
    c.d[2] = track; c.a[2] = idx; c.a[7] = STACK
    c.call('o3_chrom'); return c.a[2]
check('chrom_machine_keys_are_semitones', mchrom(True, 0) == 52 and mchrom(True, 24) == 76 and mchrom(False, 24) == 124)
def fmt(name, v):
    rig = Rig(); c = rig.cpu; m = c.mem; buf = 0x81000000; out = []
    c.hooks[0x40013a08] = lambda cpu: out.append((cpu.mem.r(cpu.a[7], 'l'), cpu.mem.r(cpu.a[7] + 4, 'l'), R.s32(cpu.mem.r(cpu.a[7] + 8, 'l'))))
    for i in range(8): m.w(buf + i, 'b', 0xAA)
    m.w(STACK - 4, 'l', v & M32); m.w(STACK - 8, 'l', buf); c.a[7] = STACK - 8
    for r in range(2, 7): c.d[r] = 0x7700 + r; c.a[r] = 0x6600 + r
    c.call(name)
    ok = c.a[7] == STACK - 8 and all(c.d[r] == 0x7700 + r and c.a[r] == 0x6600 + r for r in range(2, 7))
    if out: return out[0], ok
    b = b''
    for i in range(8):
        x = m.r(buf + i, 'b')
        if not x: break
        b += bytes([x])
    return (b.decode(), c.d[0]), ok
_fw = [fmt('o3_fmt_wave', v) for v in (0, 1, 2, 3, 4, 5, 6, 7, 9, -1)]
_fg = [fmt('o3_fmt_gate', v) for v in (0, 1, 5)]
check('fmt_wave_gate_labels', [x[0][0] for x in _fw] == list(T.WAVE_LABELS) + ['RSQRD', 'SAW']
      and all(x[1] and x[0][1] == len(x[0][0]) for x in _fw + _fg) and [x[0][0] for x in _fg] == ['OFF', '303', '303'])
_ff = [fmt('o3_fmt_fine', v) for v in (0, 64, 127)]
c0 = Rig().cpu
_lw = bytes(c0.mem.r(c0.consts['o3_lwave'] + i, 'b') for i in range(6 * len(T.WAVE_LABELS)))
check('wave_labels_fit_their_field', all(_lw[6 * i:6 * i + 6] == l.encode().ljust(6, b'\0') for i, l in enumerate(T.WAVE_LABELS))
      and all(len(l) <= 5 for l in T.WAVE_LABELS), 'v7.9: 8 labels, each in its 6-byte field with its NUL (trap-name-nul)')
check('fmt_fine_signed', [x[0] for x in _ff] == [(0x81000000, 0x400b465d, -64), (0x81000000, 0x400b465d, 0), (0x81000000, c0.consts['o3_f_plus'], 63)]
      and all(x[1] for x in _ff))

n = sum(results); print('\n%d/%d PASS' % (n, len(results))); sys.exit(0 if n == len(results) else 1)
