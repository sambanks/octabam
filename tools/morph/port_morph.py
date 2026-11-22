#!/usr/bin/env python3
"""port_morph: MORPH under the ColdFire port, keys pressed on the emulated panel.

    .venv/bin/python3 tools/morph/port_morph.py [--remix morph] [--project DIR]

Builds the remix and stages the project as tools/site/capture_manual.py does (its prepare()),
boots it under ot_emu with the panel (tools/verify/stems_panel.MenuPort, MKI), presses PLAY, then
[T1]+[UP], and reads the per-track weight longs 0x80003c60 + 4*t. Each weight is mapped back to
the crossfader position whose stock weight it is (the curve 0x400bcd90 from out/raw). v1.1: [T1]+[UP]
opens the window and starts nothing; encoders A and B set 8 x 2 = 16 steps; releasing T1 leaves it
open; YES closes it and starts T1 on the next step from A, at the tempo; T2 keeps the crossfader;
STOP holds; [T1]+[DOWN] parks T1 on A after the cycle; TRIG HOLD (encoder C) holds one value a
step. The long press: T2's window closed with NO (nothing starts), T2 held ~2 s starts it, held
again stops it on A; the same with the MIXER open. PNGs of the window go to out/morph_port
(MORPH_SHOTS=<dir> elsewhere).
v1.2 (22 Nov 2026): T3 with END STAY, RET STEP, CURV HAND rises to B and stays there, the long
press brings it back to A; PNGs of the eight-row window (9_window_v12, 10_window_top).
What it cannot see: the toast text, the unit's real frame rate (the port's frame is its model)."""
import argparse, os, struct, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'site')); sys.path.insert(0, str(ROOT / 'tools' / 'verify'))
sys.path.insert(0, str(ROOT / 'tools'))
import capture_manual as cm          # noqa: E402  (prepare: build + stage the card)
from stems_panel import MenuPort     # noqa: E402

WEIGHTS, CURVE, XF, TEMPO24, TRANSPORT = 0x80003c60, 0x400bcd90, 0x460d16c8, 0x8000181c, 0x800065b8
fails = 0
def check(name, ok, info=''):
    global fails
    print(('  [PASS] ' if ok else '  [FAIL] ') + name + (('  ' + info) if info else ''), flush=True)
    if not ok: fails += 1

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--remix', default='morph')
    cfg = Path.home() / '.octabam_project'
    ap.add_argument('--project', default=os.environ.get('OT_PROJECT') or (cfg.read_text().strip() if cfg.is_file() else ''))
    a = ap.parse_args()
    if not a.project:
        print('  [SKIP] port_morph: no project (OT_PROJECT=<dir>, --project or ~/.octabam_project)'); return 0
    raw = (ROOT / 'out/raw/section_3_MAIN_OS.bin').read_bytes(); base = 0x40000400
    curve = [struct.unpack('>h', raw[CURVE - base + 2 * i:CURVE - base + 2 * i + 2])[0] & 0xffff for i in range(128)]
    stock = {((w << 16) | ((0xffff8000 - w) & 0xffff)) & 0xffffffff: x for x, w in enumerate(curve)}
    cm.OUT.mkdir(parents=True, exist_ok=True)
    work = cm.prepare(a.remix, Path(a.project), [])
    with MenuPort((work / 'image.bin').resolve(), (work / 'card.img').resolve(), 'MANUAL', 'SCREENS', False,
                  log_path=work / 'port_morph.log') as p:
        p.settle()
        W = lambda t: p.long(WEIGHTS + 4 * t)
        xf = lambda t: stock.get(W(t))
        shots = Path(os.environ.get('MORPH_SHOTS', str(ROOT / 'out' / 'morph_port')))
        shot = lambda name: p.png(shots / (name + '.png'))
        def enc(i, d):
            p.proc.command('knob %#04x %d' % (0x30 + i, d), 'ok'); p.run(80)
        p.press('play', settle=300)
        check('transport running after PLAY', p.long(TRANSPORT) == 1, 'word %d' % p.long(TRANSPORT))
        tempo24 = p.long(TEMPO24); fader = p.long(XF)
        step_s = 992250 / tempo24 * 16 / 44100
        print('  tempo24 %d (%.1f BPM), a step %.3f s, crossfader xf %d' % (tempo24, tempo24 / 24, step_s, fader),
              flush=True)
        w1, w2 = W(0), W(1)
        # [T1]+[UP]: the window, T1 armed but held while T1 is held
        p.key('t1', True); p.run(60); p.press('up', settle=120)
        shot('1_window_open')
        # the encoders while T1 is held: STEPS 16 -> 8, x 8 -> 2 (16 steps), MODE stays SMOOTH
        enc(0, -8); enc(1, -6)
        p.run(int(step_s * 2000))
        shot('2_window_steps_8_x_2')
        check('T1 held in the window: nothing starts over two steps', W(0) == w1)
        # release T1: the window stays; YES closes it, the morph starts on the next step from A
        p.key('t1', False); p.run(int(step_s * 2000))
        check('released: the window stays, nothing starts', W(0) == w1)
        p.press('yes', settle=60); p.run(int(step_s * 1000))
        shot('3_yes_closed')
        tri = lambda s: int(round(127 - 127 * min(s, 8) / 8))
        x0 = xf(0)
        check('YES: T1 starts from A and moves', x0 is not None and 90 <= x0 <= 127, 'xf %s' % x0)
        # [T1]+[UP] again: the window over a running morph, it goes on
        p.key('t1', True); p.run(60); p.press('up', settle=120)
        shot('4_window_on')
        p.key('t1', False); p.press('no', settle=60); p.run(200)
        x1 = []                             # a quarter step apart: 16 steps a cycle = 127 / 8 a step
        for _ in range(12):
            p.run(int(step_s * 250)); x1.append(xf(0))
        d = [abs(x1[i + 1] - x1[i]) for i in range(len(x1) - 1) if None not in (x1[i], x1[i + 1])]
        check('T1 moves at the tempo (16 steps a cycle: ~4 a quarter step)',
              len(d) >= 8 and sorted(d)[len(d) // 2] in range(2, 7), str(x1))
        check('T2 keeps the crossfader', W(1) == w2)
        p.press('stop', settle=60); held = W(0); p.run(500)
        check('STOP holds T1', W(0) == held, 'xf %s -> %s' % (stock.get(held), xf(0)))
        p.press('play', settle=300); p.run(int(step_s * 2000))
        check('PLAY carries on', xf(0) is not None and W(0) != held, 'xf %s' % xf(0))
        # [T1]+[DOWN] without the window: the cycle finishes on A, then T1 is parked
        p.chord('t1', 'down', settle=60)
        p.run(int(step_s * 17 * 1000), wall=120)
        check('T1+DOWN: parked on A after the cycle', xf(0) == 127, 'xf %s' % xf(0))
        # TRIG HOLD: the window again, MODE right, YES; one value a step
        p.key('t1', True); p.run(60); p.press('up', settle=120); enc(2, 1)
        shot('5_window_hold')
        p.key('t1', False); p.press('yes', settle=60); p.run(int(step_s * 1500))
        vals = set()
        for _ in range(6):
            p.run(int(step_s * 1000 / 8)); vals.add(xf(0))
        check('TRIG HOLD: at most two values in 0.75 step', len(vals) <= 2, str(sorted(vals, key=str)))
        # ---- v1.1, the long press on T2 (2 x 2 = 4 steps a cycle)
        p.key('t2', True); p.run(60); p.press('up', settle=120); enc(0, -14); enc(1, -6)
        p.key('t2', False); p.press('no', settle=120); p.run(int(step_s * 2000))
        check('NO: T2 armed, nothing starts', W(1) == w2)
        p.key('t2', True); p.run(2000); shot('6_long_press_on'); p.key('t2', False)
        p.run(int(step_s * 1500))
        def sample(t, n=8):              # xf every quarter step
            out = []
            for _ in range(n):
                p.run(int(step_s * 250)); out.append(xf(t))
            return out
        x2 = sample(1)
        check('long press: T2 morphs', len(set(x2)) > 2 and W(1) != w2, str(x2))
        p.key('t2', True); p.run(2000); shot('7_long_press_off'); p.key('t2', False)
        p.run(int(step_s * 6000))
        check('long press again: T2 parked on A', xf(1) == 127, 'xf %s' % xf(1))
        # ---- v1.2 on T3: STEPS 2 x 2 (2 steps up), RET STEP, CURV HAND, END STAY: up to B, held there;
        #      the long press: back to A over a step, then parked
        p.key('t3', True); p.run(60); p.press('up', settle=120)
        enc(0, -14); enc(1, -6)
        for _ in range(7): enc(3, 1)          # RET: one value a click -> STEP
        enc(4, 1)                             # CURV: HAND
        for _ in range(2): enc(5, 1)          # END: STAY
        shot('9_window_v12')
        p.key('t3', False); p.press('yes', settle=60)
        p.run(int(step_s * 5000))
        check('v1.2 STAY: T3 up to B and held there', xf(2) == 0, 'xf %s' % xf(2))
        p.run(int(step_s * 3000))
        check('v1.2 STAY: still on B three steps later', xf(2) == 0, 'xf %s' % xf(2))
        p.key('t3', True); p.run(60); p.press('up', settle=120)
        shot('10_window_top')
        p.key('t3', False); p.press('no', settle=60)
        p.key('t3', True); p.run(2000); p.key('t3', False)
        p.run(int(step_s * 3000))
        check('v1.2 STAY: the long press brings T3 back to A', xf(2) == 127, 'xf %s' % xf(2))
        check('v1.2: T2 untouched meanwhile (parked on A)', xf(1) == 127, 'xf %s' % xf(1))
        p.press('mixer', settle=300)
        p.key('t2', True); p.run(2000); shot('8_mixer_long_press'); p.key('t2', False)
        p.run(int(step_s * 1500))
        x3 = sample(1)
        check('long press in the MIXER: T2 morphs', len(set(x3)) > 2, str(x3))
    print('port_morph: %d failure(s)' % fails, flush=True)
    return 1 if fails else 0

if __name__ == '__main__':
    sys.exit(main())
