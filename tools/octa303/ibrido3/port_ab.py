"""The hybrid end to end under the port: the same project on two images -- aCiDtRacK (the voice on the ColdFire) and
aCiDhYb (the chain after u on the DSP, OCTA303 SEAM) -- and their main outs compared sample for sample.  The project:
play_gate.py's fixture (T5 and T6 OCTA-303 every step with CUT/RES/ENV/ACC 127, T1 on 1 5 9 13, 300 BPM).
usage (worktree root): [O3_PAB_DEVIL=page1/page2] port_ab.py IMAGE_CF IMAGE_HYB PROJECT [frames]
What it cannot see: the port runs a frame when its work is done (no cycle limit) and models one DSP core at a time;
equal audio here says the record, the seam and the chain are right, not that the chip has the cycles."""
import os, pathlib, subprocess, sys, wave
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/octa303/v82'))
import play_gate as PG
a, b, proj = sys.argv[1:4]; frames = sys.argv[4] if len(sys.argv) > 4 else '3000'
out = ROOT / 'out/octa303/port-ab'; out.mkdir(parents=True, exist_ok=True)
card = PG.fixture(proj, out)
DEVIL = os.environ.get('O3_PAB_DEVIL')   # v9.1: "p1,p1,p1,p1,p1,p1/p2,..": dEVILish on T5 and T6 FX1 with these pages
if DEVIL:                                # (FM, MUFF, SWP...: the voices the DSP now carries too)
    sys.path.insert(0, str(ROOT / 'tools/hw')); import ot_project as OTP
    p1, p2 = ([int(x) for x in h.split(',')] for h in DEVIL.split('/'))
    for t in (5, 6): OTP.set_fx(out / 'RIG', 'fx1', t, 'DEVILISH', page=p1, page2=p2, guard=False)
    subprocess.run([sys.executable, str(ROOT / 'tools/emu/ot_emu/stage_card.py'), str(out / 'RIG'), 'OCTABAM', 'RIG',
                    '--tree', str(out / 'tree'), '--out', str(card)], check=True, stdout=subprocess.DEVNULL)
res = {}
for tag, img in (('cf', a), ('hyb', b)):
    wav = out / ('%s.wav' % tag)
    cmd = [str(ROOT / 'out/emu/ot_emu'), '--image', img, '--card', str(card), '--set', 'OCTABAM', '--project', 'RIG',
           '--sequencer', '--internal-clock', '--frames', frames, '--load-ms', '90000', '--dsp', '--main-level', '64',
           '--audio-out', str(wav)]
    with (out / ('%s.log' % tag)).open('w') as log:
        r = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=3600)
    lg = (out / ('%s.log' % tag)).read_text()
    print('%s: exit %d, ended %s, loaded %s, ILLEGAL %s' % (tag, r.returncode, 'run ended REACHED' in lg,
          'LOAD PROJECT handled' in lg, 'ILLEGAL' in lg))
    w = wave.open(str(wav) + '_core0.wav')     # the port writes core 0's main out (T5-T8 play there)
    res[tag] = (w.getnchannels(), w.getsampwidth(), w.readframes(w.getnframes())); w.close()
(ca, sa, da), (cb, sb, db) = res['cf'], res['hyb']
print('formats', (ca, sa), (cb, sb), 'bytes', len(da), len(db))
def dec(d, ch, sw):
    """per channel, the signed samples (no numpy: the Mac's venv may not have it)"""
    n = len(d) // (ch * sw); top = 1 << (8 * sw - 1)
    out = []
    for c in range(ch):
        v = [int.from_bytes(d[(k * ch + c) * sw:(k * ch + c + 1) * sw], 'little') for k in range(n)]
        out.append([x - 2 * top if x & top else x for x in v])
    return out
A, B = dec(da, ca, sa), dec(db, cb, sb)
n = min(len(A[0]), len(B[0]))
bad, sounded = False, False
for c in range(ca):
    a, b = A[c][:n], B[c][:n]
    if not any(a) and not any(b): continue
    first = next(k for k in range(n) if a[k] or b[k]); w0, w1 = max(0, first - 100), min(n, first + 20000)
    def err(L, lo=w0, hi=w1):
        return sum(1 for k in range(max(lo, -L), min(hi, n - L)) if a[k] != b[k + L])
    best = min(range(-48, 49), key=err)
    e = err(best, 0, n)
    nd = sum(1 for k in range(n) if a[k] != b[k])
    print('channel %d: %d frames, non-zero %d / %d, differing at lag 0: %d; best lag %+d samples: differing %d'
          % (c, n, sum(1 for x in a if x), sum(1 for x in b if x), nd, best, e))
    sounded = True; bad = bad or e != 0
bad = bad or not sounded               # silence on both would pass vacuously
# PASS: every sounding channel equal word for word at one constant lag (19 Nov 2026: +5 samples; the stock source's
# interpolator ring delays the ColdFire's samples, the seam writes X:0 directly).  25 Nov 2026: +26 between this
# branch's aCiDtRacK and aCiDhYb images, while the 19 Nov pair still gives +5 under the same port and the 25 Nov
# aCiDhYb equals the 24 Nov one (ACIDV98) at lag 0 / +1: the lag follows the images' start, not the seam)
print('port_ab: ' + ('PASS' if not bad else 'FAIL'))
sys.exit(1 if bad else 0)
