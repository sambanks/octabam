#!/usr/bin/env python3
"""Stateful eight-track Harmony ownership stress against linked ColdFire code.

The stock keyboard/recorder boundaries are intercepted; this does not measure
UART bandwidth, RTOS scheduling or hardware latency. See the companion port
stress gate for actual stock output. Seeds and failing actions are replayable.
"""
import argparse
from collections import Counter
import hashlib
import json
import random
import os
import subprocess
import sys

import verify_midi_harmony as h
from unicorn.m68k_const import *


class Keyboard:
    def __init__(self):
        self.m = h.Machine()
        self.events = []
        self.recorded = []
        self.calls = 0

    def key(self, track, note, velocity):
        m, u = self.m, self.m.uc
        args = (track, note, velocity, 1)
        u.mem_write(m.stack, m.done.to_bytes(4, 'big') +
                    b''.join(v.to_bytes(4, 'big') for v in args))
        u.reg_write(UC_M68K_REG_A7, m.stack)
        u.reg_write(UC_M68K_REG_SR, 0x2700)
        m.stops = {m.done, 0x4009e9b0, m.sym['mh_record_key'], m.sym['mh_owned_key']}
        pc, events = m.sym['mh_keyboard'], []
        registers = (UC_M68K_REG_D2, UC_M68K_REG_D3, UC_M68K_REG_D4,
                     UC_M68K_REG_D5, UC_M68K_REG_D6, UC_M68K_REG_D7,
                     UC_M68K_REG_A2)
        for _ in range(24):
            m.arrival = None
            u.emu_start(pc, 0, count=100000)
            assert m.arrival in m.stops, ('keyboard budget', args, hex(u.reg_read(UC_M68K_REG_PC)))
            if m.arrival == m.done:
                self.calls += 1
                self.events.extend(events)
                return events
            sp = u.reg_read(UC_M68K_REG_A7)
            if m.arrival in (m.sym['mh_record_key'], m.sym['mh_owned_key']):
                event = tuple(int.from_bytes(u.mem_read(sp+4+4*i, 4), 'big') for i in range(4))
                (self.recorded if m.arrival == m.sym['mh_record_key'] else events).append(event)
                pc = int.from_bytes(u.mem_read(sp, 4), 'big')
                u.reg_write(UC_M68K_REG_A7, sp+4)
            else:
                event = tuple(int.from_bytes(u.mem_read(sp+32+4*i, 4), 'big') for i in range(4))
                events.append(event)
                for i, reg in enumerate(registers):
                    u.reg_write(reg, int.from_bytes(u.mem_read(sp+4*i, 4), 'big'))
                pc = int.from_bytes(u.mem_read(sp+28, 4), 'big')
                u.reg_write(UC_M68K_REG_A7, sp+32)
        raise AssertionError(('unbounded output fanout', args))


def tones(note, kind, key, mode):
    """Independent closed-position stock-scale reference, no module state reads."""
    if not kind:
        return {note}
    degrees = h.MODES[mode]
    valid = [n for n in range(128) if (n-key) % 12 in degrees]
    root = min(valid, key=lambda n: (abs(n-note), n))
    scale = [n for n in range(root, 160) if (n-key) % 12 in degrees]
    return {scale[i] for i in ((0,) if kind == 1 else (0, 2, 4, 6) if kind == 3 else (0, 2, 4)) if scale[i] < 128}


def ownership(seed, steps):
    k = Keyboard()
    m = k.m
    rng = random.Random(seed)
    owners, refs = {}, Counter()
    modes = tuple(range(7)) if 'ms_decode' in m.sym else (0, 5)
    settings = [(2, t % 12, modes[t % len(modes)]) for t in range(8)]
    for t, (kind, key, mode) in enumerate(settings):
        m.setting(t, kind, key, mode)
    def edge(t, note, velocity):
        expected = []
        for pitch in sorted(owners.pop((t, note), set())):
            refs[t, pitch] -= 1
            if not refs[t, pitch]:
                expected.append((t, pitch, 0, 0))
        if velocity:
            captured = tones(note, *settings[t])
            owners[t, note] = captured
            for pitch in sorted(captured):
                refs[t, pitch] += 1
                if refs[t, pitch] == 1:
                    expected.append((t, pitch, velocity, 0))
        actual = k.key(t, note, velocity)
        assert actual == expected, (seed, k.calls, (t, note, velocity), actual, expected)
        actual_refs = bytes(m.uc.mem_read(m.sym['mh_refs'], 1024))
        assert actual_refs == bytes(refs[t, n] for t in range(8) for n in range(128)), (seed, k.calls, 'reference counts')
    # 1,024 concurrent physical keys, many shared tones, every track active.
    keys = [(t, n) for t in range(8) for n in range(128)]
    rng.shuffle(keys)
    for t, n in keys:
        edge(t, n, 100)
    rng.shuffle(keys)
    for t, n in keys:
        edge(t, n, 0)
    # No reset between edits/retriggers/releases; changes affect only new keys.
    for index in range(steps):
        t, n = rng.randrange(8), rng.randrange(128)
        if index % 11 == 0:
            settings[t] = (rng.choice((1, 2, 3)), rng.randrange(12), rng.choice(modes))
            kind, key, mode = settings[t]
            m.setting(t, kind, key, mode)
        edge(t, n, rng.randrange(1, 128) if rng.randrange(3) else 0)
    for t, n in list(owners):
        edge(t, n, 0)
    assert not any(refs.values())
    assert bytes(m.uc.mem_read(m.sym['mh_held'], 4096)) == b'\xff'*4096
    print(f'[ok] seed {seed}: {k.calls} key edges, 1,024 simultaneous keys, all tracks drained', flush=True)
    return dict(seed=seed, edges=k.calls, output_events=len(k.events))


def bypass_overlap():
    k = Keyboard()
    for t in range(8):
        k.m.setting(t, 2)
        assert k.key(t, 60, 100) == [(t, n, 100, 0) for n in (60, 64, 67)]
        k.m.setting(t, 0)
        on = k.key(t, 64, 100)
        off = k.key(t, 64, 0)
        assert on == [] and off == [], ('bypass stole a held chord tone', t, on, off)
        assert k.key(t, 60, 0) == [(t, n, 0, 0) for n in (60, 64, 67)]
    print('[ok] all tracks: bypass overlapping an existing chord preserves its held tones', flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('remix', nargs='?')
    ap.add_argument('--steps', type=int, default=12000)
    ap.add_argument('--seed', type=int, action='append')
    ap.add_argument('--project', default=os.environ.get('OT_PROJECT'))
    ap.add_argument('--bypass-only', action='store_true')
    args = ap.parse_args()
    out = h.ROOT/'out/harmony-stress'
    out.mkdir(parents=True, exist_ok=True)
    receipt = out/'result.json'
    receipt.unlink(missing_ok=True)
    results = [] if args.bypass_only else [ownership(seed, args.steps) for seed in (args.seed or [140, 20261008, 8675309])]
    bypass_overlap()
    receipt.write_text(json.dumps(dict(status='pass', seeds=results,
        image_sha256=hashlib.sha256((h.ROOT/'out/mainos_bus.bin').read_bytes()).hexdigest(),
        scope='linked keyboard ownership; stock keyboard and recorder intercepted'), indent=2)+'\n')

    if args.project:
        subprocess.run([sys.executable,str(h.ROOT/'tools/verify/verify_midi_concert_port.py'),
                        '--project',args.project],check=True,timeout=1800)
    else:
        print('[SKIP] concert UART suite: supply --project DIR or OT_PROJECT',flush=True)


if __name__ == '__main__':
    main()
