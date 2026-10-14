#!/usr/bin/env python3
"""BBD Delay's render gates, through the native builder and dsp_host. Not hardware.

    python3 tools/verify/verify_bbd.py

Needs your own OS 1.40C extraction at out/raw/section_3_MAIN_OS.bin and the patched DSP56300 tools
(vendor/dsp56300). It builds a private image in a temporary folder: the stock code built in and BBD in
the space of SPRING REV and PLATE REV, as remixes/test/bbd places it (see DONORS). The image, dumps and renders are deleted.

Gates:
  source      init leaves r1/n1/m1 alone (verify_initregs.py's scan); cycle_count.py prices the
              per-sample loop and four instances fit a core's 3120 usable cycles
  placement   the image builds and BBD sits in the donor run on both payloads, clear of the
              SPRING REV words DARK REV calls
  dry         MIX 0 is the input sample for sample, every other knob moving, with trig splits
  reference   the DSP against bbd_ref.py, the float model of the same chain, across TIME, STGS,
              MIX, FDBK and TONE: residual below -60 dB (-50 dB at the slowest clocks, where
              24-bit filter state noise is -56 dB; -40 dB with feedback)
  splits      a trig split in every block matches the model split alike
  stages      STGS changed twice mid-signal: fade, clear and fade back match the model
  kill        the stop kill (hidden slot 11 at 0): dry exactly while it holds, no tail after
  freeze      FRZ 127 mid-signal: matches the model, the loop sustains, new input stays out
  idle        after a burst the repeats die away below -90 dBFS; FDBK 127 at TONE 0
              self-oscillates without reaching full scale, and LIM 127 (the default)
              settles it at least 8 dB under LIM 0 (the governor off)
  isolation   eight instances, four per core, own knobs and input, under -guard 0x4000
              -guard-shared -dirty 0x5a: no stray write or clobber, each identical alone
  garbage     from an instance block pre-filled with garbage (verify_dirtystate.py's fills),
              silence renders exactly as from a zeroed block (the bucket noise: at most 2 LSB)
              and a tone starts like a zeroed start
  zipper      every continuous knob (HPF too) and TONE in the loop jumped and turned under a steady tone: no block-rate
              step above -70 dBFS and 6 dB over the knob held still (verify_knob_clicks.py)
  stock       DARK REV on both cores, fixed and moving, renders as on the stock OS
"""
import array
import contextlib
import importlib
import io
import math
import os
import pathlib
import random
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
FOLDER = ROOT / 'modules/bbd'
STOCK = ROOT / 'out/raw/section_3_MAIN_OS.bin'
HOST = ROOT / 'vendor/dsp56300/build/source/dsp_host/dsp_host'
for need, how in ((STOCK, 'your own OS 1.40C MAIN OS: make os, then make recon'),
                  (HOST, 'the patched DSP56300 tools: make setup')):
    if not need.is_file():
        sys.exit(f'[FAIL] bbd: missing {need} ({how})')
sys.path[:0] = [str(ROOT / 'tools/build'), str(ROOT / 'tools/harness'), str(ROOT / 'tools/verify'), str(ROOT / 'tools'),
                str(FOLDER)]
os.environ.update(XBUS='1', SPEC='1', DEV='0', NOROUNDTRIP='0', OCTABAM_NO_CACHE='1')
os.environ.setdefault('BUILD', '79')
import toolpath  # noqa: E402,F401
import dsp_modmap  # noqa: E402
from remix import registry, stock  # noqa: E402
from remix.schema import Remix  # noqa: E402
import bbd_ref  # noqa: E402

dsp_modmap.IMG = STOCK
KNOWN = registry.modules()
MOD = KNOWN['BBD']
NAMES = [p.name.decode() if p.name else '' for p in MOD.params]
# BBD beside the stock effects (remixes/test/bbd): SPRING REV alone would hold BBD's
# 1,075 words, but DARK REV calls a 35-word routine at SPRING REV+820, so PLATE REV goes too
# and BBD is placed from PLATE REV's start, clear of that routine (gate_stock_reverbs).
DONORS = ('SPRING REV', 'PLATE REV')
FR, SR = 16, 44100
LEAD = 64                                   # blocks of silence first: the ring clears in 32 calls
FS = 8388607


def remix_for(donors):
    ids = {m.menu.fx2_id: m.key for m in KNOWN.values() if m.is_stock and m.menu is not None}
    fx1 = [ids[i] for i in stock.fx1_order() if i]
    fx2 = [ids[i] for i in stock._chooser_order(stock.FX2_CHOOSER) if i]
    return Remix(name='bbd-verify', doc='Private gate image; never flashed.',
                 modules=tuple(k for k in fx2 if k not in donors) + ('BBD',),
                 fx1=tuple(fx1), fallback='NONE')


def build_image(work, donors=DONORS):
    """The native build in a scratch tree, the composition exporter's way. Returns (image, log)."""
    remix = remix_for(donors)
    registry.remix = lambda _: remix
    tree = work / 'tree'
    tree.mkdir()
    for name in ('modules', 'platform', 'dsp', 'vendor'):
        os.symlink(ROOT / name, tree / name, target_is_directory=True)
    (tree / 'out').mkdir()
    cwd = os.getcwd()
    os.chdir(tree)
    log = io.StringIO()
    try:
        sys.modules.pop('build_bus', None)
        build = importlib.import_module('build_bus')
        build.IMG = STOCK
        build.OUT = work / 'bbd.bin'
        with contextlib.redirect_stdout(log):
            build.main()
    finally:
        if 'build' in locals() and build._SCRATCH is not None:
            shutil.rmtree(build._SCRATCH, ignore_errors=True)
        os.chdir(cwd)
    return work / 'bbd.bin', log.getvalue()


class Gates:
    def __init__(self):
        self.failed = []

    def check(self, name, ok, detail=''):
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}{': ' + detail if detail else ''}", flush=True)
        if not ok:
            self.failed.append(name)


def knobs(**kw):
    vals = [p.default or 0 for p in MOD.params] + [0] * (12 - len(MOD.params))
    for k, v in kw.items():
        vals[NAMES.index(k)] = v
    return vals


def write_raw(path, frames):
    """frames: list of (L, R) floats -> interleaved int32 (dsp_host -stereo)"""
    a = array.array('i', [0] * (2 * len(frames)))
    for i, (l, r) in enumerate(frames):
        a[2 * i] = max(-FS - 1, min(FS, int(round(l * FS))))
        a[2 * i + 1] = max(-FS - 1, min(FS, int(round(r * FS))))
    path.write_bytes(a.tobytes())
    return path


def read_raw(path):
    a = array.array('i')
    a.frombytes(path.read_bytes())
    return a


class Host:
    """dsp_host on the image's two payloads; BBD on FX2 at positions 0..3 of each core."""

    def __init__(self, mems, work):
        import send_probe
        self.mems, self.work, self.n = mems, work, 0
        self.ep = {c: send_probe.entry_points(mems[c], MOD.menu.fx2_id) for c in (0, 1)}

    def run(self, insts, blocks, inputs, extra=(), mems=None, fx=None):
        """insts: dicts with core, pos, and knobs or paramfile; inputs: one raw per instance; fx: another
        effect's FX2 id to run instead of BBD. Returns (stdout, [interleaved int32 output per instance])."""
        import send_probe
        mems = mems or self.mems
        ep = self.ep if fx is None else {c: send_probe.entry_points(mems[c], fx) for c in (0, 1)}
        self.n += 1
        out = self.work / f'r{self.n}.raw'
        cmd = [str(HOST), '-mem', str(mems[0]), '-memB', str(mems[1]),
               '-init', ','.join('%x' % ep[i['core']][0] for i in insts),
               '-proc', ','.join('%x' % ep[i['core']][1] for i in insts),
               '-inst', str(len(insts)), '-core', ','.join(str(i['core']) for i in insts),
               '-alloc', ','.join(str(1 + 2 * i['pos']) for i in insts),
               '-r7', ','.join(str(2 + 3 * i['pos']) for i in insts),
               '-audioidx', ','.join(str(k) for k in range(len(insts))), '-audio', '9000',
               '-in', ','.join(str(p) for p in inputs), '-stereo',
               '-frames', str(FR), '-blocks', str(blocks), '-out', str(out)]
        for i in insts:
            cmd += ['-params', ','.join(map(str, i.get('knobs', knobs())))]
        for i in insts:
            if 'paramfile' in i:
                cmd += ['-paramfile', str(i['paramfile'])]
        cmd += list(extra)
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if r.returncode or 'HANG' in r.stdout:
            raise RuntimeError(f'dsp_host failed ({r.returncode}):\n{r.stdout[-3000:]}{r.stderr[-1000:]}')
        outs = [read_raw(out if k == 0 else pathlib.Path(f'{out}.i{k}')) for k in range(len(insts))]
        for p in [out] + [pathlib.Path(f'{out}.i{k}') for k in range(1, len(insts))]:
            p.unlink(missing_ok=True)
        return r.stdout, outs


def dbfs(v):
    return 20 * math.log10(max(abs(v), 1) / (FS + 1))


def signal(seconds, level=1.0, seed=1, lead=LEAD):
    """Silence through the clear, then four decaying tones and a little noise (mono, as frames)."""
    rnd = random.Random(seed)
    n, x = int(seconds * SR) // FR * FR, []
    for i in range(n):
        t, v = i - lead * FR, 0.0
        if t >= 0:
            for k, (f0, a) in enumerate(((220, .45), (587, .35), (1250, .25), (2900, .3))):
                u = t - int((0.03 + 0.27 * k) * SR)
                if u >= 0:
                    v += a * math.sin(2 * math.pi * f0 * u / SR) * math.exp(-u / (0.15 * SR))
            v += 0.01 * (rnd.random() * 2 - 1)
        x.append((v * level, v * level))
    return x


def noise(n, level, seed):
    rnd = random.Random(seed)
    return [((rnd.random() * 2 - 1) * level, (rnd.random() * 2 - 1) * level) for _ in range(n)]


def reference(frames, calls, split=0):
    """bbd_ref through the same calls; a split s > 0 cuts every block at s."""
    fx, out = bbd_ref.BBD(), []
    for b, k in enumerate(calls):
        block = frames[FR * b:FR * b + FR]
        for part in ((block[:split], block[split:]) if split else (block,)):
            if part:
                out += fx.call(part, k)
    return [v for frame in out for v in frame]


def residual_db(dsp, ref, start):
    num = sum((a / (FS + 1) - b) ** 2 for a, b in zip(dsp[2 * start:], ref[2 * start:]))
    den = sum(b * b for b in ref[2 * start:]) or 1e-30
    return 10 * math.log10(num / den + 1e-30)


def gate_source(g):
    import verify_initregs
    src = (FOLDER / 'bbd.asm').read_text()
    block = verify_initregs.init_block(src)
    g.check('source: init leaves r1/n1/m1 alone', bool(block) and not verify_initregs.WRITE.search(block))
    registry.remix = lambda _: Remix(name='bbd-verify', doc='cycle count', modules=('BBD',), fallback='NONE')
    import cycle_count
    row = cycle_count.measure('bbd')
    same = cycle_count.verify('bbd', row)
    per = row['cycles']
    g.check('source: static cycles', same and 4 * per <= cycle_count.USABLE,
            f'{per} cycles/sample per instance (the tick path), 4 per core = {4 * per} of {cycle_count.USABLE}; marker no-op {same}')
    return per


def gate_placement(g, log):
    """BBD sits inside the donated run and clear of the SPRING REV words DARK REV calls."""
    for tag in 'AB':
        sec = log.split(f'-- payload {tag} --')[1].split('-- payload')[0] if f'-- payload {tag} --' in log else ''
        kept = re.search(r'P:0x([0-9a-f]+)\+(\d+) kept', sec)
        m = re.search(r'BBD\s+P:0x([0-9a-f]+)\.\.0x([0-9a-f]+) \((\d+) words\)', sec)
        run = re.search(r'run \d+ P:0x([0-9a-f]+)\.\.0x([0-9a-f]+)', sec)
        if not (kept and m and run):
            g.check(f'placement: payload {tag}', False, 'no BBD, run or kept line in the build log')
            continue
        lo, hi, k0 = int(m[1], 16), int(m[2], 16), int(kept[1], 16)
        k1 = k0 + int(kept[2])
        ok = int(run[1], 16) <= lo and hi <= int(run[2], 16) and (hi <= k0 or lo >= k1)
        g.check(f'placement: payload {tag}', ok, f'BBD P:0x{lo:05x}..0x{hi:05x} ({m[3]} words) in '
                f'P:0x{run[1]}..0x{run[2]}, clear of DARK REV\'s P:0x{k0:05x}..0x{k1:05x}')


def gate_dry(g, host, work):
    blocks = 1500
    inp = write_raw(work / 'dry_in.raw', noise(blocks * FR, 0.9, 7))
    want = read_raw(inp)
    rnd = random.Random(3)
    rows = []
    for b in range(0, blocks, 37):
        kw = {n: rnd.randrange(p.count or 128) for n, p in zip(NAMES, MOD.params) if p.name}
        rows.append(','.join(map(str, [b, *knobs(**{**kw, 'MIX': 0})])))
    pf = work / 'dry_auto.csv'
    pf.write_text('\n'.join(rows) + '\n')
    for label, extra in (('static', ()), ('moving knobs', ()), ('moving knobs, split 5', ('-split', '5'))):
        inst = dict(core=0, pos=1, knobs=knobs(MIX=0, FDBK=127, TONE=0, STGS=1))
        if label != 'static':
            inst['paramfile'] = pf
        _, (out,) = host.run([inst], blocks, [inp], extra)
        g.check(f'dry: MIX 0 is the input sample for sample ({label})', out == want,
                f'{sum(1 for a, b in zip(out, want) if a != b)} of {len(want)} words differ')


CASES = (('TIME 0', dict(TIME=0), -60), ('TIME 64', dict(TIME=64), -60), ('TIME 127', dict(TIME=127), -50),
         ('TIME 32, STGS 1024', dict(TIME=32, STGS=0), -60), ('TIME 96, STGS 1024', dict(TIME=96, STGS=0), -50),
         ('MIX 64', dict(TIME=40, MIX=64), -60), ('FDBK 80', dict(TIME=20, FDBK=80), -40),
         ('FDBK 90, TONE 127', dict(TIME=20, FDBK=90, TONE=127), -40), ('FDBK 70, TONE 0', dict(TIME=20, FDBK=70, TONE=0), -40),
         ('FDBK 40, TONE 0, FREQ 0', dict(TIME=20, FDBK=40, TONE=0, FREQ=0), -40),
         ('FDBK 40, TONE 0, FREQ 127', dict(TIME=20, FDBK=40, TONE=0, FREQ=127), -40),
         ('FDBK 40, FRZ 64', dict(TIME=20, FDBK=40, FRZ=64), -40),
         ('FDBK 100, TONE 0, LIM 120', dict(TIME=20, FDBK=100, TONE=0, LIM=120), -40),
         ('MIX 32', dict(TIME=40, MIX=32), -60), ('MIX 96', dict(TIME=40, MIX=96), -60),
         ('HPF 1 (20 Hz)', dict(TIME=40, FDBK=60, HPF=1), -60), ('HPF 64', dict(TIME=40, FDBK=60, HPF=64), -60),
         ('HPF 127 (400 Hz)', dict(TIME=40, FDBK=60, HPF=127), -60))


def gate_reference(g, host, work):
    sig = signal(2.0)
    blocks = len(sig) // FR
    inp = write_raw(work / 'ref_in.raw', sig)
    for label, kw, limit in CASES:
        k = knobs(**{'MIX': 127, **kw})
        _, (out,) = host.run([dict(core=0, pos=0, knobs=k)], blocks, [inp])
        res = residual_db(out, reference(sig, [k] * blocks), (LEAD + 64) * FR)
        peak = max(abs(v) for v in out)
        g.check(f'reference: {label}', res < limit and peak < FS, f'{res:.1f} dB against bbd_ref (limit {limit}), peak {dbfs(peak):.1f} dBFS')


def gate_splits(g, host, work):
    """The clear counts calls, so a split render starts its clock sooner: each split must still
    match the model split the same way."""
    sig = signal(2.0)
    blocks = len(sig) // FR
    inp = write_raw(work / 'split_in.raw', sig)
    k = knobs(TIME=10, FDBK=60, MIX=127)
    for split in (1, 7, 15):
        _, (out,) = host.run([dict(core=0, pos=0, knobs=k)], blocks, [inp], ('-split', str(split)))
        res = residual_db(out, reference(sig, [k] * blocks, split), (LEAD + 64) * FR)
        g.check(f'splits: split {split} matches the model split alike', res < -60, f'{res:.1f} dB')


def gate_stages(g, host, work):
    sig = signal(2.0) * 2
    blocks = len(sig) // FR
    calls = [knobs(STGS=1, MIX=127)] * 1500 + [knobs(STGS=0, MIX=127)] * 1500 + [knobs(STGS=1, MIX=127)] * (blocks - 3000)
    pf = work / 'stages.csv'
    pf.write_text('\n'.join(','.join(map(str, [b, *k])) for b, k in enumerate(calls)) + '\n')
    _, (out,) = host.run([dict(core=0, pos=0, knobs=calls[0], paramfile=pf)], blocks, [write_raw(work / 'st_in.raw', sig)])
    res = residual_db(out, reference(sig, calls), (LEAD + 64) * FR)
    g.check('stages: STGS 4096 -> 1024 -> 4096 mid-signal matches the model', res < -60 and max(map(abs, out)) < FS,
            f'{res:.1f} dB through two fades and clears')


def gate_kill(g, host, work):
    """The stop kill (kill.s zeroes hidden slot 11 while it holds): a ringing tail after the
    the input, wet only; the kill from block 2000 (the input still playing) to 3300 (past its
    end, 2756): the input exactly while it holds, no tail after it, as the model; the same
    render without the kill still rings there."""
    sig = signal(1.0)
    sig += [(0.0, 0.0)] * (4 * SR // FR * FR - len(sig))
    blocks = len(sig) // FR
    live = knobs(TIME=20, FDBK=110, MIX=127)
    dead = list(live)
    dead[11] = 0
    at, until = 2000, 3300
    for tag, calls in (('kill', [live] * at + [dead] * (until - at) + [live] * (blocks - until)),
                       ('none', [live] * blocks)):
        pf = work / f'kill_{tag}.csv'
        pf.write_text('\n'.join(','.join(map(str, [b, *k])) for b, k in enumerate(calls)) + '\n')
        _, (out,) = host.run([dict(core=0, pos=0, knobs=calls[0], paramfile=pf)], blocks,
                             [write_raw(work / 'kill_in.raw', sig)])
        after = max(map(abs, out[2 * FR * (until + 16):]))
        if tag == 'none':
            g.check('kill: without the kill the tail still rings after block 3316', dbfs(after) > -60,
                    f'peak {dbfs(after):.1f} dBFS')
            continue
        res = residual_db(out, reference(sig, calls), (LEAD + 64) * FR)
        held = list(out[2 * FR * at:2 * FR * until])
        dry = [max(-FS - 1, min(FS, int(round(v * FS)))) for f in sig[FR * at:FR * until] for v in f]
        g.check('kill: matches the model through the kill and its release', res < -60, f'{res:.1f} dB')
        g.check('kill: the input exactly while it holds', held == dry,
                f'{sum(1 for a, b in zip(held, dry) if a != b)} of {len(dry)} words differ')
        g.check('kill: no tail after its release', dbfs(after) < -100, f'peak {dbfs(after):.1f} dBFS')


def gate_idle(g, host, work):
    burst = signal(10.0, seed=3)
    for i in range(LEAD * FR + SR // 2, len(burst)):
        burst[i] = (0.0, 0.0)
    blocks = len(burst) // FR
    inp = write_raw(work / 'idle_in.raw', burst)
    # TONE 0's +9 dB peak multiplies the loop gain by 2.8: it rings out only below FDBK ~45
    for label, kw in (('FDBK 90', dict(TIME=0, FDBK=90)), ('FDBK 10, TONE 0', dict(TIME=0, FDBK=10, TONE=0))):
        _, (out,) = host.run([dict(core=0, pos=0, knobs=knobs(MIX=127, **kw))], blocks, [inp])
        tail = max(abs(v) for v in out[-SR:])
        g.check(f'idle: {label}, the last 0.5 s of a 9.5 s tail', dbfs(tail) < -90, f'{dbfs(tail):.1f} dBFS')
    rms = {}
    for lim in (0, 127):
        _, (out,) = host.run([dict(core=0, pos=0, knobs=knobs(MIX=127, TIME=0, FDBK=127, TONE=0, LIM=lim))], blocks // 2, [inp])
        peak = max(abs(v) for v in out)
        rms[lim] = dbfs(math.sqrt(sum(v * v for v in out[-SR:]) / SR))
        g.check(f'idle: FDBK 127, TONE 0, LIM {lim} self-oscillates, bounded below full scale',
                dbfs(peak) < -0.05 and any(out[-SR:]), f'peak {dbfs(peak):.2f} dBFS, last 0.5 s {rms[lim]:.1f} dBFS RMS')
    g.check('idle: LIM 127 settles the oscillation at least 8 dB under LIM 0 (off)', rms[0] - rms[127] >= 8,
            f'{rms[0] - rms[127]:.1f} dB quieter')


def gate_freeze(g, host, work):
    """FRZ 127 half a second into a signal that keeps playing: the line loops what it holds,
    sustained to the end, and the new input stays out (the model shows both)."""
    sig = signal(8.0, seed=4)
    blocks = len(sig) // FR
    at = LEAD + SR // FR
    calls = [knobs(TIME=60, FDBK=30, MIX=127)] * at + [knobs(TIME=60, FDBK=30, MIX=127, FRZ=127)] * (blocks - at)
    pf = work / 'freeze.csv'
    pf.write_text('\n'.join(','.join(map(str, [b, *k])) for b, k in enumerate(calls)) + '\n')
    _, (out,) = host.run([dict(core=0, pos=0, knobs=calls[0], paramfile=pf)], blocks, [write_raw(work / 'frz_in.raw', sig)])
    res = residual_db(out, reference(sig, calls), (LEAD + 64) * FR)
    early = max(abs(v) for v in out[2 * (at * FR + SR):2 * (at * FR + 2 * SR)])
    late = max(abs(v) for v in out[-2 * SR:])
    g.check('freeze: FRZ 127 mid-signal matches the model', res < -40, f'{res:.1f} dB')
    g.check('freeze: the frozen loop sustains', early > 0 and abs(dbfs(late) - dbfs(early)) < 3,
            f'peak {dbfs(early):.1f} dBFS 1 s after the freeze, {dbfs(late):.1f} dBFS at the end')

    # A slow crossfade into FRZ 127 on a self-oscillating loop keeps its level: one loop
    # sustains on the way up and 127 loops the line itself (a bucket mix used to comb it down)
    n = 10 * SR // FR * FR
    burst = noise(SR // 4 // FR * FR, 0.3, 11) + [(0.0, 0.0)] * (n - SR // 4 // FR * FR)
    blocks, at, ramp = n // FR, 5 * SR // FR, SR // 2 // FR
    calls = [knobs(TIME=64, FDBK=127, TONE=0, LIM=127, MIX=127,
                   FRZ=0 if b < at else min(127, round(127 * (b - at + 1) / ramp))) for b in range(blocks)]
    pf = work / 'freeze_ramp.csv'
    pf.write_text('\n'.join(','.join(map(str, [b, *k])) for b, k in enumerate(calls)) + '\n')
    _, (out,) = host.run([dict(core=0, pos=0, knobs=calls[0], paramfile=pf)], blocks, [write_raw(work / 'frzr_in.raw', burst)])

    def rms(lo, hi):
        w = out[2 * int(lo * SR):2 * int(hi * SR)]
        return 20 * math.log10(max(1.0, math.sqrt(sum(v * v for v in w) / len(w))) / (FS + 1))
    before, frozen = rms(4.0, 5.0), rms(8.5, 10.0)
    g.check('freeze: a 0.5 s crossfade to FRZ 127 keeps a self-oscillating loop\'s level', abs(frozen - before) < 2,
            f'{before:.1f} dBFS RMS before, {frozen:.1f} frozen ({frozen - before:+.1f} dB; LIM 127, TONE 0)')

    # Partial FRZ only lengthens trails: its FDBK stops at sustain for TONE's peak gain, so a
    # boosted TONE at low FDBK does not tip into self-oscillation on the way up
    calls = [knobs(TIME=64, FDBK=20, TONE=0, FRZ=100, MIX=127)] * blocks
    pf.write_text('\n'.join(','.join(map(str, [b, *k])) for b, k in enumerate(calls)) + '\n')
    _, (out,) = host.run([dict(core=0, pos=0, knobs=calls[0], paramfile=pf)], blocks, [write_raw(work / 'frzr_in.raw', burst)])
    tail = rms(8.5, 10.0)
    g.check('freeze: FRZ 100 with TONE 0 and FDBK 20 lengthens the trails without droning', tail < -70,
            f'{tail:.1f} dBFS RMS 8.5-10 s after a 0.25 s burst (limit -70)')


def gate_stock_reverbs(g, host, work):
    """DARK REV stays listed and calls a routine inside SPRING REV's code: on this image it must
    render bit-identically to the stock OS on both cores, fixed and moving controls."""
    import send_probe
    stock = {c: send_probe.dump_mem(STOCK, work / f'stock_{t}.mem', t) for c, t in ((0, 'A'), (1, 'B'))}
    sig = signal(2.0, seed=6)
    blocks = len(sig) // FR
    inp = write_raw(work / 'rev_in.raw', sig)
    rnd = random.Random(9)
    pf = work / 'rev_auto.csv'
    pf.write_text('\n'.join(','.join(map(str, [b] + [rnd.randrange(128) for _ in range(12)])) for b in range(0, blocks, 41)) + '\n')
    for core in (0, 1):
        for label, inst in (('fixed', dict(core=core, pos=1, knobs=[64] * 12)),
                            ('moving', dict(core=core, pos=1, knobs=[64] * 12, paramfile=pf))):
            _, (mine,) = host.run([inst], blocks, [inp], fx=0x16)
            _, (ref,) = host.run([inst], blocks, [inp], mems=stock, fx=0x16)
            g.check(f'stock: DARK REV on core {"AB"[core]} ({label}) renders as on the stock OS', mine == ref and any(mine),
                    f'{sum(1 for a, b in zip(mine, ref) if a != b)} of {len(ref)} words differ')


def instance_set():
    rnd = random.Random(5)
    out = []
    for core in (0, 1):
        for pos in range(4):
            kw = {n: rnd.randrange(p.count or 128) for n, p in zip(NAMES, MOD.params) if p.name}
            kw['FDBK'] = min(kw['FDBK'], 60)
            out.append(dict(core=core, pos=pos, knobs=knobs(**kw)))
    return out


def gate_isolation(g, host, work):
    blocks = 1600
    insts = instance_set()
    inputs = [write_raw(work / f'iso_{k}.raw', noise(blocks * FR, 0.4, 100 + k)) for k in range(len(insts))]
    extra = ('-guard', '0x4000', '-guard-shared', '-dirty', '0x5a')
    text, outs = host.run(insts, blocks, inputs, extra)
    rows = re.findall(r'instance (\d+): \d+ non-zero output samples, (\d+) stray write regions, (\d+) CLOBBERING', text)
    strays, clob = sum(int(s) for _, s, _ in rows), sum(int(c) for _, _, c in rows)
    g.check('isolation: eight instances under -guard 0x4000 -guard-shared -dirty 0x5a', len(rows) == 8 and strays == 0 and clob == 0,
            f'{len(rows)} instances guarded, {strays} stray regions, {clob} clobbers')
    same = 0
    for k, inst in enumerate(insts):
        _, (alone,) = host.run([inst], blocks, [inputs[k]], extra)
        same += alone == outs[k]
    g.check('isolation: each instance alone renders bit-identically', same == 8, f'{same} of 8 identical')


def gate_garbage(g, host, work):
    import verify_dirtystate as vd
    blocks = 600
    silent = write_raw(work / 'g_silent.raw', [(0.0, 0.0)] * (blocks * FR))
    tone = write_raw(work / 'g_tone.raw', [(0.3 * math.sin(2 * math.pi * 438.75 * i / 44100),) * 2 for i in range(blocks * FR)])
    sets = [knobs(), knobs(TIME=0, FDBK=127, TONE=0, MIX=127, STGS=1, HPF=127)]
    zero = {}
    for k, kn in enumerate(sets):
        _, (z,) = host.run([dict(core=0, pos=0, knobs=kn)], blocks, [tone])
        zero[k] = max(abs(v) for v in z[:2 * 256 * FR])
    # The bucket noise, lifted by the compander's warm start, leaves 1-2 LSB for ~0.2 s after a
    # reset from ANY start: the hygiene test is that garbage changes nothing (verify_dirtystate.py)
    clean = {k: host.run([dict(core=0, pos=0, knobs=kn)], blocks, [silent])[1][0] for k, kn in enumerate(sets)}
    same, within, loudest = True, True, max(max(map(abs, o)) for o in clean.values())
    for fill in vd.FILLS:
        mems = {c: vd.mem_with_fill(host.mems[c], fill, work / f'fill_{fill:06x}_{c}.mem', 2) for c in (0, 1)}
        for k, kn in enumerate(sets):
            _, (o,) = host.run([dict(core=0, pos=0, knobs=kn)], blocks, [silent], ('-dirty', '0x5a'), mems=mems)
            same &= o == clean[k]
            _, (t,) = host.run([dict(core=0, pos=0, knobs=kn)], blocks, [tone], mems=mems)
            first = max(abs(v) for v in t[:2 * 256 * FR])
            within &= abs(20 * math.log10(max(first, 1) / max(zero[k], 1))) <= 1.0
    g.check('garbage: on silence, a garbage block renders exactly as a zeroed one, below -100 dBFS',
            same and dbfs(loudest) < -100, f'{len(vd.FILLS)} fills x {len(sets)} knob sets, 600 blocks, Y dirty too; '
            f'loudest sample {loudest} LSB ({dbfs(loudest):.1f} dBFS): the bucket noise')
    g.check('garbage: a tone from a garbage block starts like a zeroed one', within, 'first 256 blocks peak within 1 dB')


# verify_knob_clicks.py's census, copied: importing it selects the rig fixture, which this
# module's private image does not carry. Same tone, windows, metric and limits.
KC_J1, KC_J2, KC_S0, KC_END = 1500, 2000, 2500, 3000
KC_LO, KC_HI = 20, 110
KC_STEP_LIMIT, KC_MARGIN = -70.0, 6.0
KC_WINDOWS = (('up', KC_J1, KC_J2), ('down', KC_J2, KC_S0), ('turn', KC_S0, KC_END))


def kc_phase_energy(x, b0, b1):
    e = [0.0] * FR
    for n in range(b0 * FR, b1 * FR):
        a, b, c, d = x[n - 2], x[n - 1], x[n], x[n + 1]
        if max(abs(a), abs(b), abs(c), abs(d)) >= 0.9999:
            continue
        v = d - 3 * c + 3 * b - a
        e[n % FR] += v * v
    return e


def kc_step_db(x, b0, b1):
    import statistics
    e = kc_phase_energy(x, b0, b1)
    med = statistics.median(e)
    spread = 1.4826 * statistics.median(abs(v - med) for v in e)
    excess = max(e) - med - 3 * spread
    return max(-140.0, 10 * math.log10(max(excess, 1e-30) / (6 * (b1 - b0))))


def kc_measure(move, lo, hi):
    return {name: (max(kc_step_db(v, b0, b1) for v in move), max(kc_step_db(v, b0, b1) for v in lo + hi))
            for name, b0, b1 in KC_WINDOWS}


def kc_flagged(res):
    return any(m > KC_STEP_LIMIT and m > s + KC_MARGIN for m, s in res.values())


# TONE acts only inside the feedback loop: measured with FDBK up.
ZIPPER_LOOP = (('TONE', dict(FDBK=60), KC_LO, KC_HI),)


def gate_zipper(g, host, work):
    blocks = KC_END + 2 + LEAD
    tone = write_raw(work / 'z_tone.raw', [((0.3 * math.sin(2 * math.pi * 438.75 * (i - LEAD * FR) / 44100),) * 2
                                           if i >= LEAD * FR else (0.0, 0.0)) for i in range(blocks * FR)])
    cases = [(n, {}, KC_LO, KC_HI) for n, p in zip(NAMES, MOD.params) if p.name and (p.count or 128) >= 128]
    flagged, rows = [], []
    for name, extra, lo, hi in cases + list(ZIPPER_LOOP):
        k = NAMES.index(name)
        base = dict(MIX=100, **extra)

        def render(at, sched=None):
            kw = dict(base, **{name: at})
            _, (o,) = host.run([dict(core=0, pos=0, knobs=knobs(**kw))], blocks, [tone], ('-sched', sched) if sched else ())
            return [[v / FS for v in o[0::2][LEAD * FR:]], [v / FS for v in o[1::2][LEAD * FR:]]]
        ev = [(KC_J1, hi), (KC_J2, lo)] + [(KC_S0 + 2 * j, v) for j, v in enumerate(range(lo + 1, hi + 1))]
        sched = ','.join(f'{b + LEAD}:0:{k}={v}' for b, v in ev)
        res = kc_measure(render(lo, sched), render(lo), render(hi))
        label = f"{name} {lo}<->{hi}" + ''.join(f' at {n} {v}' for n, v in extra.items())
        rows.append(f"{label}: " + ' '.join(f'{w} {m:.0f}/{s:.0f}' for w, (m, s) in res.items()))
        if kc_flagged(res):
            flagged.append(label)
    for r in rows:
        print('        ' + r)
    g.check('zipper: no block-rate step on any continuous knob', not flagged,
            f'{len(cases)} knobs, then TONE inside the loop; jump up / jump down / turn, move/static dBFS above; flagged {flagged or "none"}')


def main():
    import send_probe
    g = Gates()
    print('== bbd: render gates (dsp_host, private image; not hardware)')
    gate_source(g)
    with tempfile.TemporaryDirectory(prefix='bbd-verify.') as tmp:
        work = pathlib.Path(tmp)
        try:
            image, log = build_image(work)
        except (SystemExit, AssertionError) as error:
            g.check('placement: the image builds', False, str(error))
            return 1
        mems = {c: send_probe.dump_mem(image, work / f'mem_{t}.mem', t) for c, t in ((0, 'A'), (1, 'B'))}
        gate_placement(g, log)
        host = Host(mems, work)
        for gate in (gate_dry, gate_reference, gate_splits, gate_stages, gate_kill, gate_freeze, gate_idle, gate_isolation, gate_garbage, gate_zipper, gate_stock_reverbs):
            gate(g, host, work)
    print(f"== bbd: {'all gates pass' if not g.failed else str(len(g.failed)) + ' failed: ' + ', '.join(g.failed)}")
    return 1 if g.failed else 0


if __name__ == '__main__':
    sys.exit(main())
