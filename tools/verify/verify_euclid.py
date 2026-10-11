#!/usr/bin/env python3
"""Euclid: mathematical timing, compiled ColdFire hooks, and real DSP renders.

Run from the repository root after `make bus REMIX=euclid`. Native control
and executed ColdFire traces must agree exactly; DSP tests use the actual
dispatch entries in both payloads. No hardware is accessed.
"""
import argparse
import ctypes as C
import json
import math
import os
import pathlib
import platform
import re
import shlex
import struct
import subprocess
import sys
import sysconfig

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import toolpath  # noqa: E402,F401
import send_probe  # noqa: E402
from dsp_host_cli import command as dsp_host_command  # noqa: E402
from remix import registry  # noqa: E402

OUT = ROOT / 'out/euclid'
Q = 1323000
DT = 16 * 2880
ANCHOR = 0xffff0000
FAILS = 0


class Clock(C.Structure):
    _fields_ = [(x, C.c_uint32) for x in ('now', 'quantum', 'remainder', 'epoch', 'initialized')]


class State(C.Structure):
    _fields_ = ([(x, C.c_uint32) for x in ('epoch', 'next', 'period', 'age', 'rng', 'triggers')]
                + [('values', C.c_uint16 * 64)]
                + [(x, C.c_uint16) for x in ('level', 'origin', 'target')]
                + [(x, C.c_uint8) for x in ('initialized', 'mode', 'active')]
                + [('reserved', C.c_uint16)])


class Params(C.Structure):
    _fields_ = ([(x, C.c_uint16) for x in ('freq', 'depth')]
                + [(x, C.c_uint8) for x in ('steps', 'pulses', 'rotate', 'rate', 'attack', 'decay', 'mode', 'scale', 'length', 'swing')]
                + [('reserved', C.c_uint16), ('mask_lo', C.c_uint32), ('mask_hi', C.c_uint32)])


def check(name, ok, detail=''):
    global FAILS
    FAILS += not ok
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f': {detail}' if detail else ''), flush=True)


def run(cmd, **kw):
    r = subprocess.run([str(x) for x in cmd], cwd=ROOT, capture_output=True, text=True, **kw)
    if r.returncode:
        raise RuntimeError(f"{' '.join(map(str, cmd))}\n{r.stdout[-1800:]}\n{r.stderr[-1800:]}")
    return r.stdout


def native_compiler():
    """Use the compiler (and, on macOS, architecture) of this Python."""
    cmd = shlex.split(sysconfig.get_config_var('CC') or 'cc')
    if sys.platform == 'darwin' and '-arch' not in cmd:
        cmd += ['-arch', platform.machine()]
    return cmd


def params(**kw):
    p = Params(freq=40 << 8, depth=100 << 8, steps=8, pulses=3, rate=1,
               decay=48, scale=6, length=16, mask_lo=0xaaaaaaaa, mask_hi=0xaaaaaaaa)
    for key, value in kw.items(): setattr(p, key, value)
    return p


def control_tests(lib):
    ok = True
    for n in range(1, 65):
        for k in range(n + 1):
            hits = [i for i in range(n) if lib.eu_pulse(i, n, k)]
            ok &= len(hits) == k and (not k or hits[0] == 0)
            if k:
                gaps = [(hits[(j + 1) % k] - hits[j]) % n or n for j in range(k)]
                ok &= max(gaps) - min(gaps) <= 1
    check('Every STEPS/PULSES combination has the right count and even gaps', ok)

    # Independent oracle for stock's swing offset, all rates and track scales.
    ok = True
    for scale in (3, 4, 6, 8, 12, 24, 48):
        for rate in range(5):
            for swing in (0, 16, 30):
                p = params(scale=scale, rate=rate, swing=swing, pulses=8)
                s, c = State(), Clock()
                lib.eu_clock_start(C.byref(c), ANCHOR)
                times = []
                for i in range(20):
                    q = i * (scale << rate)
                    track_step = q / (2 * scale)
                    whole = int(track_step)
                    fraction = track_step - whole
                    weight = (whole % 2) * (1 - fraction) + ((whole + 1) % 2) * fraction
                    when = q * Q + round(swing * 52920 * scale * weight)
                    if when:
                        lib.eu_clock_update(C.byref(c), (ANCHOR + when - 1) & 0xffffffff)
                        lib.eu_process(C.byref(s), C.byref(c), C.byref(p), 0, 1, 0)
                        ok &= s.triggers == i
                    lib.eu_clock_update(C.byref(c), (ANCHOR + when) & 0xffffffff)
                    lib.eu_process(C.byref(s), C.byref(c), C.byref(p), 1, 1, 0)
                    ok &= s.triggers == i + 1
                    times.append(when)
    check('Exact pulse deadlines: 7 track speeds x 5 rates x 3 swing amounts, including clock wrap', ok)

    # Odd cycle wraps must not restart the swing grid. Arbitrary track swing
    # placements must work too (not just hardcoded alternating steps).
    ok = True
    for rotate in range(13):
        p = params(steps=13, pulses=5, rotate=rotate, swing=30, mask_lo=0b10010110)
        s, c = State(), Clock(); lib.eu_clock_start(C.byref(c), 0)
        for i in range(52):
            delay = 30 * 52920 * 6 if (p.mask_lo >> (i % 16)) & 1 else 0
            lib.eu_clock_update(C.byref(c), (i * 12 * Q + delay) & 0xffffffff)
            before = s.triggers
            lib.eu_process(C.byref(s), C.byref(c), C.byref(p), DT, 1, 0)
            ok &= s.triggers - before == int(((i - rotate) % 13 * 5) % 13 < 5)
    check('13-step cycles, all rotations, and custom swing masks retain track-grid phase', ok)

    # RAND -> LOOP captures the values last heard, independent of pulse count
    # and rotation; the PRNG must stop advancing while locked.
    s, c, p = State(), Clock(), params(mode=2, pulses=8)
    lib.eu_clock_start(C.byref(c), 0)
    heard = []
    for i in range(8):
        lib.eu_clock_update(C.byref(c), i * 12 * Q)
        lib.eu_process(C.byref(s), C.byref(c), C.byref(p), DT, 1, 0)
        heard.append(s.level)
    seed = s.rng; p.mode = 3
    replay = []
    for i in range(8, 24):
        lib.eu_clock_update(C.byref(c), (i * 12 * Q) & 0xffffffff)
        lib.eu_process(C.byref(s), C.byref(c), C.byref(p), DT, 1, 0)
        replay.append(s.level)
    check('LOOP repeats the captured random cycle exactly and freezes the PRNG', replay == heard * 2 and s.rng == seed)
    p.rotate = 2; replay = []
    for i in range(24, 32):
        lib.eu_clock_update(C.byref(c), (i * 12 * Q) & 0xffffffff)
        lib.eu_process(C.byref(s), C.byref(c), C.byref(p), DT, 1, 0)
        replay.append(s.level)
    check('ROTATE moves the captured values with the rhythm', replay == heard[-2:] + heard[:-2])
    p.mode = 2
    lib.eu_clock_update(C.byref(c), 32 * 12 * Q)
    lib.eu_process(C.byref(s), C.byref(c), C.byref(p), DT, 1, 0)
    check('Returning to RAND resumes evolution', s.rng != seed)
    p.mode = 3; saved = list(s.values)
    lib.eu_clock_start(C.byref(c), 1234)
    lib.eu_process(C.byref(s), C.byref(c), C.byref(p), DT, 1, 0)
    check('PLAY resets phase and keeps the captured loop', s.next == 12 and list(s.values) == saved)
    neutral = lib.eu_process(C.byref(s), C.byref(c), C.byref(p), DT, 0, 0)
    check('STOP leaves the base filter and preserves captured random', neutral == p.freq and list(s.values) == saved)

    ok = True
    for mode in range(4):
        for depth in (0, 16384, 32512):
            s, c, p = State(), Clock(), params(mode=mode, depth=depth, pulses=64, steps=1)
            lib.eu_clock_start(C.byref(c), 0)
            value = lib.eu_process(C.byref(s), C.byref(c), C.byref(p), DT, 1, 0)
            ok &= (value <= p.freq if depth < 16384 else value == p.freq if depth == 16384 else value >= p.freq)
            p.pulses = 0
            ok &= lib.eu_process(C.byref(s), C.byref(c), C.byref(p), DT, 1, 0) == p.freq
    check('Bipolar depth, zero depth, zero pulses, and pulses clamped to steps in every output', ok)



    # Check the shapes in musical time; this is separate from pulse scheduling.
    def sample_shape(p, offsets):
        s, c, levels = State(), Clock(), []
        lib.eu_clock_start(C.byref(c), 0)
        previous = 0
        for q in offsets:
            now = round(q * Q)
            lib.eu_clock_update(C.byref(c), now)
            lib.eu_process(C.byref(s), C.byref(c), C.byref(p), now - previous, 1, 0)
            levels.append(s.level)
            previous = now
        return levels

    p = params(steps=64, pulses=1, attack=127, decay=64)
    levels = sample_shape(p, (0, 3, 6, 12, 18, 30))
    check('ENV rises through ATTACK and decays to the base cutoff',
          levels[0] == 0 < levels[1] < levels[2] < levels[3]
          and levels[3] > levels[4] > levels[5] == 0, str(levels))
    p = params(steps=64, pulses=1, mode=1, decay=63, attack=0)
    levels = sample_shape(p, (0, 3, 6, 9))
    check('GATE length is a fraction of a step', levels == [32767, 32767, 0, 0], str(levels))
    p.attack = 127
    levels = sample_shape(p, (0, 1.5, 3, 6, 7.5, 9))
    check('GATE EDGE softens both transitions',
          levels[0] == 0 < levels[1] < levels[2] == levels[3]
          and levels[3] > levels[4] > levels[5] == 0, str(levels))
    p = params(steps=64, pulses=1, mode=2, attack=127)
    levels = sample_shape(p, (0, 3, 6, 12, 18))
    check('RAND SLEW reaches and holds its chosen level',
          levels[0] == 0 < levels[1] < levels[2] < levels[3] == levels[4], str(levels))

    p = params(steps=16, pulses=1, attack=0, decay=127)
    levels = sample_shape(p, (0, 12, 24, 48, 84, 96))
    check('Maximum ENV decay crosses empty steps and reaches zero after eight steps',
          levels[0] == 32767 and all(a > b > 0 for a, b in zip(levels[:4], levels[1:5]))
          and levels[-1] == 0, str(levels))

    p = params(steps=64, pulses=1, scale=48, rate=4, attack=127, decay=127)
    levels = sample_shape(p, range(0, 6913, 384))
    check('Longest attack plus decay finishes across a raw-clock wrap',
          levels[0] == 0 and levels[2] == 32767 and levels[-1] == 0, str(levels))

    s, c, p = State(), Clock(), params(pulses=8)
    lib.eu_clock_start(C.byref(c), 0)
    lib.eu_process(C.byref(s), C.byref(c), C.byref(p), DT, 1, 0)
    lib.eu_clock_update(C.byref(c), 5 * Q)
    p.rate = 0
    lib.eu_process(C.byref(s), C.byref(c), C.byref(p), DT, 1, 0)
    before = s.triggers
    lib.eu_clock_update(C.byref(c), 6 * Q)
    lib.eu_process(C.byref(s), C.byref(c), C.byref(p), DT, 1, 0)
    check('Changing RATE joins the next new grid point without a burst', before == 1 and s.triggers == 2)


def firmware_tests(lib, image, frames=10000):
    # Build only the probe; no changes to the firmware builder are required.
    run(['cmake', '-S', 'tools/emu/ot_emu', '-B', 'out/emu'])
    run(['cmake', '--build', 'out/emu', '--target', 'ot_euclid_test', '-j8'])
    symbols = {s[2]: int(s[0], 16) for l in run(['m68k-elf-nm', 'out/platform/runtime/runtime.elf']).splitlines()
               if len(s := l.split()) == 3}
    for mode in range(4):
        trace = OUT / f'cf_{mode}.csv'
        result = run(['out/emu/ot_euclid_test', image, 'out/platform/runtime.raw',
                      f'{json.loads((ROOT / "out/platform/layout.json").read_text())["base"]:x}',
                      f'{symbols["eu_states"]:x}', trace, mode, frames])
        check(f'ColdFire mode {mode}: preserves registers and all neighboring parameters', 'PASS:' in result, result.strip())
        states, clock = [State() for _ in range(4)], Clock()
        lib.eu_clock_start(C.byref(clock), ANCHOR)
        p = params(mode=mode, swing=16)
        if mode == 0:
            p.steps, p.pulses, p.decay = 16, 1, 127
        rows = [list(map(int, line.split(','))) for line in trace.read_text().splitlines()]
        first_diff = None
        for row in rows:
            frame = row[0]
            if mode == 2 and frame >= 3000: p.mode = 3
            lib.eu_clock_update(C.byref(clock), (ANCHOR + frame * DT) & 0xffffffff)
            values = [lib.eu_process(C.byref(s), C.byref(clock), C.byref(p), DT, 1, identity)
                      for identity, s in zip((0, 1, 14, 15), states)]
            got = values[:2] + [s.triggers for s in states[:2]] + values[2:] + [s.triggers for s in states[2:]]
            if got != row[1:]: first_diff = (frame, got, row[1:]); break
        check(f'ColdFire mode {mode}: exact match to native control for both FX slots on tracks 1 and 8', first_diff is None, str(first_diff or f'{frames} frames'))
    trace = OUT / 'cf_moving.csv'
    result = run(['out/emu/ot_euclid_test', image, 'out/platform/runtime.raw',
                  f'{json.loads((ROOT / "out/platform/layout.json").read_text())["base"]:x}',
                  f'{symbols["eu_states"]:x}', trace, 0, frames, 'moving'])
    check('ColdFire all controls moving on 16 instances remains bounded',
          'PASS:' in result, result.strip())


def reverb_tests(image, keys=('PLATE REV', 'SPRING REV', 'DARK REV')):
    """Pin the shipping menu's reverb promise independently of its manifest."""
    import dsp_modmap as dm
    from remix import stock

    original = dm.IMG.read_bytes()
    from remix import booted
    built = booted.image(pathlib.Path(image).read_bytes())

    def rd32(data, address):
        return struct.unpack_from('>I', data, address - dm.BASE)[0]

    menu = rd32(built, 0x400375f4)
    ids = set()
    for row in range(32):
        descriptor = rd32(built, menu + 4 * row)
        if not descriptor: break
        ids.add(rd32(built, descriptor))
    check('Shipping FX2 chooser retains ' + ', '.join(keys),
          {registry.by_key(key).menu.fx2_id for key in keys}.issubset(ids))

    def memory(data, address, length):
        records, blob = dm.modules(data, address, length)
        return {(space, start + i): dm.w24(blob, offset + 3 * i)
                for space, start, count, offset in records for i in range(count)}

    for payload, address, length in dm.PAYLOADS:
        before = memory(original, address, length)
        after = memory(built, address, length)
        for key in keys:
            if key in stock.NO_DSP:
                continue
            start, count = stock.p_spans(payload)[key]
            fxid = registry.by_key(key).menu.fx2_id
            code = [(0, start + i) for i in range(count)]
            dispatch = [(1, table + fxid) for table in (0x215, 0x235)]
            check(f'DSP {payload}: {key} code and init/process dispatch remain stock',
                  all(pos in before and before[pos] == after.get(pos) for pos in code + dispatch))


def dsp_tests(image):
    host = ROOT / 'vendor/dsp56300/build/source/dsp_host/dsp_host'
    mod = registry.by_name('euclid')
    count = 16000
    defaults = [p.default or 0 for p in mod.params]

    def render(mem, ep, signal, values, label, automation=None, meter=False):
        src, dst = OUT / 'input.raw', OUT / f'{label}.raw'
        src.write_bytes(struct.pack(f'<{len(signal)}i', *signal))
        args = dsp_host_command(host, mem, ep[0], ep[1], src, dst, values,
                                len(signal) // 16, guard=True,
                                schedules=automation or ())
        report = run(args)
        data = dst.read_bytes()
        audio = struct.unpack(f'<{len(data)//4}i', data)[::2]
        if not meter:
            return audio
        match = re.search(r'core 0 meter: max (\d+).*?mean (\d+)', report)
        if not match:
            raise RuntimeError(f'missing DSP meter in {label}: {report[-1000:]}')
        return audio, tuple(map(int, match.groups()))

    def rms(x): return math.sqrt(sum(a*a for a in x) / len(x))

    for payload in 'AB':
        mem = send_probe.dump_mem(str(image), OUT / f'{payload}.mem', payload)
        ep = send_probe.entry_points(str(mem), mod.menu.fx2_id)
        check(f'DSP {payload}: dispatch points to Euclid, not the stock null', ep != send_probe.entry_points(str(mem), 0))
        ramp = [round(-8388607 + 16777214 * i / (count - 1)) for i in range(count)]
        p = defaults.copy(); p[11] = 0
        dry = render(mem, ep, ramp, p, f'dry_{payload}')
        check(f'DSP {payload}: MIX zero is bit-exact on a bipolar full-scale ramp', tuple(ramp) == dry)
        dc = [1000000] * count
        levels = []
        for typ in range(3):
            p = defaults.copy(); p[0] = 64; p[1] = 0; p[8] = typ
            out = render(mem, ep, dc, p, f'dc_{payload}_{typ}')
            levels.append(rms(out[-4000:]))
        check(f'DSP {payload}: LP passes DC; BP and HP reject DC', abs(levels[0] - 1000000) < 500 and max(levels[1:]) < 500, str(levels))
        levels = []
        for f in (2000, 4000):
            tone = [round(1e6 * math.sin(2*math.pi*f*i/44100)) for i in range(count)]
            p = defaults.copy(); p[0] = 48; p[1] = 0
            levels.append(rms(render(mem, ep, tone, p, f'lp_{payload}_{f}')[-8000:]))
        slope = 20 * math.log10(levels[0] / max(levels[1], 1))
        check(f'DSP {payload}: two-pole low-pass slope', 10 < slope < 14, f'{slope:.2f} dB/oct')

        # The two-integrator SVF uses Q=1 at RES=0. Check its knee as well as
        # the asymptotic slope, including the bilinear frequency warping.
        errors = []
        for cutoff in (32, 64, 96):
            fc = 30 * 500 ** (cutoff / 128)
            for ratio in (0.5, 1, 2):
                f = fc * ratio
                tone = [round(1e6 * math.sin(2*math.pi*f*i/44100)) for i in range(count)]
                p = defaults.copy(); p[0] = cutoff; p[1] = 0
                out = render(mem, ep, tone, p, f'knee_{payload}_{cutoff}_{ratio}')
                gain = rms(out[-8000:]) / rms(tone[-8000:])
                w = math.tan(math.pi*f/44100) / math.tan(math.pi*fc/44100)
                target = 1 / math.sqrt((1 - w*w)**2 + w*w)
                errors.append(abs(20 * math.log10(gain / target)))
        check(f'DSP {payload}: non-resonant LP matches the two-pole target at three cutoffs',
              max(errors) < 0.2, f'{max(errors):.3f} dB max error')

        p = defaults.copy(); p[0] = 127; p[8] = 3; p[11] = 127
        amp = render(mem, ep, ramp, p, f'amp_unity_{payload}')
        error = max(abs(a - b) for a, b in zip(ramp, amp))
        check(f'DSP {payload}: AMP at full level and full MIX is unity',
              error <= 2, f'{error} LSB max error')
        p[0] = 0
        amp = render(mem, ep, ramp, p, f'amp_zero_{payload}')
        residual = max(map(abs, amp))
        check(f'DSP {payload}: AMP at zero level and full MIX is silent',
              residual <= 2, f'{residual} LSB residual')

        # AMP has its own arithmetic-identical gain path and must no longer
        # execute the coefficient lookup, divide or stereo SVFs.
        p = defaults.copy(); p[8] = 3
        _, amp_meter = render(mem, ep, ramp, p, f'amp_meter_{payload}', meter=True)
        p[8] = 0
        _, lp_meter = render(mem, ep, ramp, p, f'lp_meter_{payload}', meter=True)
        check(f'DSP {payload}: AMP fast path costs less than 30% of LP',
              amp_meter[1] * 10 < lp_meter[1] * 3,
              f'mean {amp_meter[1]} vs {lp_meter[1]} instructions/block')

        # NOTCH reuses the already-computed LP and HP taps. At the selected
        # frequency it must cut, while retaining the low and high bands.
        p = defaults.copy(); p[0] = 64; p[1] = 64; p[8] = 4
        notch_levels = []
        for f in (100, 30 * math.sqrt(500), 8000):
            tone = [round(1e6 * math.sin(2*math.pi*f*i/44100)) for i in range(count)]
            out = render(mem, ep, tone, p, f'notch_{payload}_{round(f)}')
            notch_levels.append(rms(out[-8000:]))
        notch_db = 20 * math.log10(max(notch_levels[0], notch_levels[2])
                                   / max(notch_levels[1], 1))
        check(f'DSP {payload}: NOTCH rejects its center and retains both sides',
              notch_db > 8 and min(notch_levels[0], notch_levels[2]) > 300000,
              f'{notch_db:.1f} dB center rejection, levels {[round(x) for x in notch_levels]}')

        # The AMP shortcut freezes the hidden SVF. Returning to a filter
        # clears those integrators before processing, so old filter history
        # cannot erupt when TYPE is edited live.
        tone = [round(200000 * math.sin(2*math.pi*440*i/44100)) for i in range(count)]
        p = defaults.copy(); p[0] = 127; p[1] = 127
        rows = []
        for block, typ in ((80, 3), (160, 0), (240, 3), (320, 4)):
            p[8] = typ
            rows.append([block, *p])
        switched = render(mem, ep, tone, defaults, f'type_switch_{payload}', rows)
        # At maximum resonance the settled LP/NOTCH response can reach about
        # 2x this tone on the ARM64 host. A TYPE edit is safe when its two
        # 64-block settling windows remain close to the response after they
        # settle; an absolute ceiling still catches a persistent eruption.
        transient = (switched[160*16:224*16] + switched[320*16:384*16])
        settled = (switched[224*16:240*16] + switched[384*16:])
        transition_peak = max(map(abs, transient))
        settled_peak = max(map(abs, settled))
        check(f'DSP {payload}: rapid FILTER/AMP/NOTCH changes stay bounded',
              transition_peak < 450000
              and transition_peak * 8 <= settled_peak * 9,
              f'transition {transition_peak}, settled {settled_peak}')

        # The denominator must follow the cutoff ramp. Freezing it at the
        # destination caused >20x overshoots on low-level input when closing.
        tone = [round(200000 * math.sin(2*math.pi*440*i/44100)) for i in range(count)]
        peaks = []
        for resonance in (0, 64, 127):
            p = defaults.copy(); p[1] = resonance
            rows = []
            for block in range(0, count // 16, 40):
                p[0] = 127 if block % 80 == 0 else 0
                rows.append([block, *p])
            signal = render(mem, ep, tone, p, f'sweep_{payload}_{resonance}', rows)
            peaks.append(max(map(abs, signal)))
        check(f'DSP {payload}: full-range cutoff jumps stay bounded at three resonances',
              max(peaks) < 400000, str(peaks))



def playback_test(image, project):
    """Boot a copied project and require the modulation to survive stock writes.

    The isolated hook test cannot catch an incorrectly placed hook: scene/LFO
    processing can overwrite its perfectly correct result later in the frame.
    """
    if not project:
        print('  [SKIP] Euclid full playback: provide OT_PROJECT or --project')
        return
    import ot_project as otp
    import verify_repitch as fixture
    work = OUT / 'playback'
    work.mkdir(parents=True, exist_ok=True)
    fixture.make_loop(work / 'tone.wav')
    fixture.build_project(pathlib.Path(project).expanduser(), work / 'project', 0, 2, 120, 64, 127)
    defaults = bytes(p.default or 0 for p in registry.by_name('euclid').params)

    def mut(data):
        for part in range(otp.NPARTS_ALL):
            b = otp.PART_BASE + part * otp.PART_STRIDE
            data[b + otp.FX1_OFF:b + otp.FX1_OFF + 8] = bytes(8)
            data[b + otp.FX2_OFF:b + otp.FX2_OFF + 8] = bytes(8)
            data[b + otp.FX1_OFF] = 0x1d
            data[b + otp.P1_OFF:b + otp.P1_OFF + 6] = defaults[:6]
            data[b + otp.P2_OFF:b + otp.P2_OFF + 6] = defaults[6:]
            for track in range(8):
                data[b + 0x12c + track * 24] = 64 if track == 0 else 0
                data[b + 0x123 + track * 24:b + 0x126 + track * 24] = bytes(3)
        off = otp.trac_off(0, 0)
        data[off:off + 8] = bytes(7) + b'\x01'
        data[off + 0x52] = 16
    otp._bank_write(work / 'project', 1, mut, guard=False)
    fixture.stage(work / 'project', work / 'card.img', work / 'tone.wav')
    cmd = ['out/emu/ot_emu', '--image', str(image), '--card', str(work / 'card.img'),
           '--set', 'OCTABAM', '--project', 'RIG', '--sequencer', '--internal-clock',
           '--frames', '4500', '--load-ms', '90000', '--dsp', '--main-level', '64',
           '--audio-out', str(work / 'audio'), '--watch-mem', '0x8000011c,2',
           '--call-at', '2500', '--call', '0x4009c7c4,90,0']
    with (work / 'run.log').open('w') as log:
        result = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    log = (work / 'run.log').read_text()
    check('Full firmware plays through a live 120 -> 90 BPM change',
          result.returncode == 0 and 'run ended REACHED' in log and 'returned, d0' in log)
    rows = [(float(m[1]), int(m[2], 16), int(m[3], 16)) for m in re.finditer(
        r'\[\s*([\d.]+)\] \[0x8000011c\] <- (0x[0-9a-f]+).*?at pc (0x[0-9a-f]+)', log)]
    base = json.loads((ROOT / 'out/platform/layout.json').read_text())['base']
    end = base + (ROOT / 'out/platform/runtime.raw').stat().st_size
    groups, group = [], []
    for row in rows:
        if row[2] == 0x4000cb4e:
            if group: groups.append(group)
            group = []
        group.append(row)
    if group: groups.append(group)
    groups = [g for g in groups if g[0][2] == 0x4000cb4e]
    final = [g[-1] for g in groups]
    check('Euclid is the final cutoff writer in each outgoing frame',
          len(groups) > 1000 and all(base <= g[-1][2] < end and g[-1][0] - g[0][0] < 16 for g in groups))
    check('Modulation reaches the outgoing records with fractional cutoff values',
          len({r[1] for r in final}) > 50 and max((r[1] for r in final), default=0) > 25000)
    channels = []
    for core in (0, 1):
        path = work / f'audio_core{core}.wav'
        match = re.search(rf'audio_core{core}\.wav, .*?transport start at frame (\d+)', log)
        if path.exists() and match:
            channels.extend(x[int(match[1]):] for x in fixture.read_wav24(path))
    best = max(channels, key=lambda x: sum(v*v for v in x), default=[])
    energy = [math.sqrt(sum(v*v for v in best[i:i+1024]) / 1024)
              for i in range(4096, len(best) - 1024, 1024)]
    if energy and max(energy) == 0:
        # No audio at all: the DSP's main mixdown gain reads 0 under the port
        # on this machine (tools/emu/README.md, the voice-silence entry, 28
        # Sep 2026); the records' modulation above is still measured.
        print('  [SKIP] Full DSP audio contains the filter pulses on the steady test tone: no audio on '
              'any slot -- the port\'s main mixdown gain (tools/emu/README.md)', flush=True)
    else:
        check('Full DSP audio contains the filter pulses on the steady test tone',
              bool(energy) and min(energy) > 0 and max(energy) > 2 * min(energy),
              f'{max(energy, default=0):.0f} peak / {min(energy, default=0):.0f} base RMS')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('remix', nargs='?', default='euclid')
    ap.add_argument('--image', default='out/mainos_bus.bin')
    ap.add_argument('--control-only', action='store_true')
    ap.add_argument('--project', default=os.environ.get('OT_PROJECT', ''))
    a = ap.parse_args()
    if 'EUCLID' not in registry.remix(a.remix).modules:
        print(f'  [ -- ] verify_euclid: {a.remix} carries no EUCLID')
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    run([sys.executable, 'modules/euclid/generate_control.py', '--check'])
    library = OUT / 'control.so'
    run([*native_compiler(), '-O2', '-shared', '-fPIC', '-DEUCLID_NATIVE',
         'modules/euclid/control.c', '-o', library])
    lib = C.CDLL(str(library))
    lib.eu_clock_start.argtypes = lib.eu_clock_update.argtypes = [C.POINTER(Clock), C.c_uint32]
    lib.eu_process.argtypes = [C.POINTER(State), C.POINTER(Clock), C.POINTER(Params), C.c_uint32, C.c_uint, C.c_uint]
    lib.eu_process.restype = C.c_uint16
    lib.eu_pulse.argtypes = [C.c_uint, C.c_uint, C.c_uint]
    control_tests(lib)
    if not a.control_only:
        if a.remix == 'euclid':
            reverb_tests(a.image)
        firmware_tests(lib, a.image)
        dsp_tests(a.image)
        playback_test(a.image, a.project)
    print(f'Euclid: {FAILS} failed checks')
    return bool(FAILS)


if __name__ == '__main__':
    sys.exit(main())
