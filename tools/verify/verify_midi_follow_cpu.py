#!/usr/bin/env python3
"""Instruction budgets for installed Follow code, with observable MIDI results.

This gate never builds. --artifact-root can point at a preserved out/ tree,
including its mainos_bus.remix image-identity marker;
--record-only records a baseline without enforcing optimization budgets.
Counts exclude the continuation instruction. They are executed instructions,
not ColdFire cycles, CPU utilization, UART latency or hardware deadlines. The
native packet enqueue routine is stubbed; its execution/transmission cost is
excluded. Cold/warm describe Follow state, not the processor instruction cache.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

from midi_machine import Machine, ROOT
from unicorn import UC_HOOK_CODE
from unicorn.m68k_const import (UC_M68K_REG_A2, UC_M68K_REG_A5, UC_M68K_REG_A6,
                               UC_M68K_REG_A7, UC_M68K_REG_D2, UC_M68K_REG_D3,
                               UC_M68K_REG_D4, UC_M68K_REG_D7)


# Exact warmed measurements from PR #824 f79ad3ca, source fde8036c. Image:
# 9b476627e979949177a8e87a10a6d048fe6a209f9e21799f00a2a856e0d7b695.
# The fixtures below preserve these measured cases. Additional cold, voice and
# lifecycle cases do not inherit an unmeasured historical baseline.
BASELINE = {
    'off_tick.cold': 2200, 'off_prepass.cold': 2277, 'off_accepted.cold': 137,
    'off_tick.warm': 2136, 'off_prepass.warm': 2213, 'off_accepted.warm': 137,
    'live_direct_FIXED.unchanged': 2667,
    'live_direct_FIXED.moved4': 5744,
    'live_direct_GRAV.unchanged': 3602,
    'live_direct_GRAV.moved4': 8775,
    'live_chain7_FIXED.unchanged': 3261,
    'live_chain7_FIXED.moved4': 8714,
    'live_chain7_GRAV.unchanged': 5384,
    'live_chain7_GRAV.moved4': 15309,
    'live_seven_FIXED.unchanged': 5853, 'live_seven_FIXED.moved4': 27392,
    'live_seven_GRAV.unchanged': 12398, 'live_seven_GRAV.moved4': 48609,
    'live_direct_GRAV.committed_moved4': 8808,
    'live_chain7_GRAV.committed_moved4': 15342,
    'live_seven_GRAV.committed_moved4': 48840,
}

# Cold root, then warm voices 0..3, measured again against the same preserved
# f79ad3ca image. This also budgets standalone KEY-OFF and every chord voice.
NOTE_BASELINE = {
    'key0_direct_FIXED_bf_note': (925, 925, 838, 838, 838),
    'key25_direct_FIXED_bf_note': (990, 990, 954, 903, 954),
    'key25_direct_FIXED_ms_output': (1272, 1272, 1236, 1185, 1236),
    'key0_direct_GRAV_bf_note': (1750, 1421, 1334, 1334, 1334),
    'key25_direct_GRAV_bf_note': (1815, 1486, 1450, 1399, 1450),
    'key25_direct_GRAV_ms_output': (2097, 1768, 1732, 1681, 1732),
    'key0_chain7_FIXED_bf_note': (2113, 2113, 2026, 2026, 2026),
    'key25_chain7_FIXED_bf_note': (2178, 2178, 2142, 2091, 2142),
    'key25_chain7_FIXED_ms_output': (3054, 3054, 3018, 2967, 3018),
    'key0_chain7_GRAV_bf_note': (3532, 3203, 3116, 3116, 3116),
    'key25_chain7_GRAV_bf_note': (3597, 3268, 3232, 3181, 3232),
    'key25_chain7_GRAV_ms_output': (4473, 4144, 4108, 4057, 4108),
}
for _name, (_cold, *_warm) in NOTE_BASELINE.items():
    for _phase in ('cold', 'warm'):
        for _slot, _count in enumerate(_warm):
            BASELINE[f'note_{_name}.{_phase}.{_slot}'] = _cold if _phase == 'cold' and _slot == 0 else _count
for _name, _count in tuple(BASELINE.items()):
    if _name.endswith('.unchanged'):
        BASELINE[_name.replace('.unchanged', '.settled')] = _count

# Targets are instruction regressions, not a claim about real-time capacity.
# Require a material reduction from the measured review cases. All other
# paths still have an explicit termination limit and report their totals.
BUDGETS = {name: value * 9 // 10 for name, value in BASELINE.items()}
# Long-chain / seven-receiver unchanged GRAV must still recompute the target:
# unchanged source tokens do not imply valid TRAN or unchanged lifecycle.
# The unsafe token-only shortcut is deliberately excluded. These paths retain
# an 8% reduction target; other measured paths require at least 10%. Keep the
# invalid-TRAN and Part round-trip assertions below when changing this work.
for _profile in ('chain7', 'seven'):
    for _phase in ('unchanged', 'settled'):
        _name = f'live_{_profile}_GRAV.{_phase}'
        BUDGETS[_name] = BASELINE[_name] * 92 // 100
BANK = 0x400e21e0
PART = BANK + 0x8ed80
PART_SIZE = 0x18b2
PITCHES = (36, 40, 43, 47)


def artifact_identity(artifacts, remix):
    """Refuse a mislabeled image and detect replacement during the gate."""
    marker_path = artifacts/'mainos_bus.remix'
    marker = marker_path.read_text().split()
    assert len(marker) == 2 and re.fullmatch(r'[0-9a-f]{64}', marker[1]), \
        f'invalid image marker: {marker_path}'
    assert marker[0] == remix, \
        f'requested remix {remix}, but {marker_path} identifies {marker[0]}'
    paths = dict(image_sha256='mainos_bus.bin',
                 runtime_sha256='platform/runtime/runtime.bin',
                 symbols_sha256='platform/runtime/runtime.elf',
                 layout_sha256='platform/layout.json')
    identity = {name: hashlib.sha256((artifacts/path).read_bytes()).hexdigest()
                for name, path in paths.items()}
    assert identity['image_sha256'] == marker[1], \
        f'image hash does not match {marker_path}'
    return identity


class Probe:
    def __init__(self, artifacts):
        self.artifacts = artifacts
        raw = subprocess.check_output(
            ['m68k-elf-nm', str(artifacts/'platform/runtime/runtime.elf')], text=True)
        self.symbols = {n: int(a, 16) for a, n in re.findall(
            r'^([0-9a-f]+) [TtBbDdAa] (\w+)$', raw, re.M)}
        self.names = defaultdict(list)
        for name, address in self.symbols.items():
            if name.startswith(('bf_', 'store_part_', 'ms_', 'lb_')):
                self.names[address].append(name)
        self.results = {}

    def machine(self):
        m = Machine(lambda: self.symbols.copy(), artifact_root=self.artifacts)
        m.instruction_limit = lambda name: 300000
        return m

    def measure(self, name, m, call):
        total = 0
        calls = Counter()

        def trace(uc, pc, size, data):
            nonlocal total
            if pc in m.stops:
                return
            total += 1
            calls.update(self.names.get(pc, ()))

        hook = m.uc.hook_add(UC_HOOK_CODE, trace)
        try:
            result = call()
        finally:
            m.uc.hook_del(hook)
        assert total > 0, name
        self.results[name] = dict(instructions=total, calls=dict(sorted(calls.items())))
        return result


def idle(probe):
    for name, entry, kwargs in (
        ('off_tick', 'bf_response_tick', {}),
        ('off_prepass', 'bf_pre_capture', dict(stop=0x4009f98c,
                                             regs={UC_M68K_REG_A6: 0x47004000})),
        ('off_accepted', 'bf_seq_note_accepted', dict(
            regs={UC_M68K_REG_D2: 100, UC_M68K_REG_D3: 60})),
    ):
        m = probe.machine()
        for phase in ('cold', 'warm'):
            probe.measure(f'{name}.{phase}', m, lambda: m.call(entry, **kwargs))


def route(m, chain, grav, key=0):
    source = 7 if chain else 1
    graph = (2, 3, 4, 5, 6, 7, 8, 0) if chain else (2, 0, 0, 0, 0, 0, 0, 0)
    m.follow_write('source', bytes(graph))
    m.follow_write('mode', bytes((int(grav),)))
    m.set_key(source, key)
    m.uc.mem_write(m.sym['bf_roots']+source, b'\x24')
    m.uc.mem_write(m.sym['bf_pitches']+source, b'\x3c')
    m.uc.mem_write(m.sym['bf_intervals']+source*3, bytes((4, 7, 11)))
    return source


def notes(probe):
    for chain in (False, True):
        for grav in (False, True):
            for key in (0, 25) if 'ms_output' in probe.symbols else (0,):
                for entry in ('bf_note', 'ms_output') if key else ('bf_note',):
                    m = probe.machine()
                    route(m, chain, grav, key)
                    frame, lane = m.scratch+0x3000, m.scratch+0x1000
                    m.uc.mem_write(lane+0x22c, b'\x40')
                    m.uc.mem_write(frame-4, b'\x3c\xff\xff\xff')
                    prefix = f'note_key{key}_{"chain7" if chain else "direct"}_{"GRAV" if grav else "FIXED"}_{entry}'
                    # Explicit harmonic examples, independent of the runtime's
                    # routing/scale implementation: Cmaj7 and C Dorian.
                    expected = (36, 39, 43, 46) if key == 25 else PITCHES
                    for phase in ('cold', 'warm'):
                        for slot, pitch in enumerate(expected):
                            m.uc.mem_write(m.scratch, b'\x3c')
                            regs = {UC_M68K_REG_D7: 0, UC_M68K_REG_D4: slot,
                                    UC_M68K_REG_A2: m.scratch, UC_M68K_REG_A5: lane,
                                    UC_M68K_REG_A6: frame}
                            probe.measure(f'{prefix}.{phase}.{slot}', m,
                                          lambda: m.call(entry, stop=0x4009fb86, regs=regs))
                            assert m.uc.mem_read(m.scratch, 1)[0] == pitch, (prefix, phase, slot, pitch)


def live_fixture(probe, chain=False, grav=False, receivers=(0,)):
    m = probe.machine()
    u, s = m.uc, m.sym
    m.events = []
    source = route(m, chain, grav)
    if len(receivers) > 1:
        source = 7
        m.follow_write('source', bytes((8,)*7+(0,)))
        m.follow_write('mode', bytes((int(grav),)*7))
        u.mem_write(s['bf_roots']+source, b'\x24')
        u.mem_write(s['bf_pitches']+source, b'\x3c')
    # This probe measures Follow's computation; native queue/transmit is a
    # documented boundary and the emitted packet list remains observable.
    u.mem_write(0x40010bc8, bytes.fromhex('4e75'))
    u.mem_write(0x46c78152, b'\xff'*2048)
    u.mem_write(0x46c77a16, b'\xff'*256)
    u.mem_write(0x400d807e, b'\x5b')

    def enqueue(uc, pc, size, data):
        stack = uc.reg_read(UC_M68K_REG_A7)
        count, pointer = struct.unpack('>II', uc.mem_read(stack+4, 8))
        assert count == 3
        m.events.append(tuple(uc.mem_read(pointer, 3)))

    u.hook_add(UC_HOOK_CODE, enqueue, begin=0x40010bc8, end=0x40010bc8)
    for receiver in receivers:
        u.mem_write(0x46c76fe0+receiver*32+12, b'\x40')
        u.mem_write(0x46c76de0+receiver*68, bytes((receiver+1,)))
        u.mem_write(0x46c7a7f0+receiver*4, (37).to_bytes(4, 'big'))
        for slot, pitch in enumerate(PITCHES):
            u.mem_write(0x46c77a16+receiver*32+slot*8,
                        struct.pack('>II', 0xffffff90+receiver, pitch))
            u.mem_write(0x46c78152+receiver*128+pitch, bytes((receiver*4+slot,)))
        m.call('bf_response_set', receiver, 1)
    mask = sum(1 << t for t in receivers)
    m.call('bf_response_tick', mask, 0)
    for receiver in receivers:
        u.mem_write(m.scratch, b'\x24')
        m.call('bf_response_observe', regs={UC_M68K_REG_D7: receiver,
               UC_M68K_REG_D4: 0, UC_M68K_REG_A2: m.scratch})
    m.call('bf_response_tick', 0, 0)
    m.events.clear()
    return m, source


def assert_voices(m, receivers, shift):
    expected = []
    for receiver in receivers:
        expected += [(0x90+receiver, p, 0) for p in PITCHES]
        expected += [(0x90+receiver, p+shift, 91) for p in PITCHES]
        for slot, pitch in enumerate(PITCHES):
            at = 0x46c77a16+receiver*32+slot*8+4
            assert int.from_bytes(m.uc.mem_read(at, 4), 'big') == pitch+shift
        assert int.from_bytes(m.uc.mem_read(0x46c7a7f0+receiver*4, 4), 'big') == 37
    assert m.events == expected, (m.events, expected)


def live(probe):
    for chain, receivers in ((False, (0,)), (True, (0,)), (False, tuple(range(7)))):
        for grav in (False, True):
            m, source = live_fixture(probe, chain, grav, receivers)
            prefix = f'live_{"seven" if len(receivers)>1 else "chain7" if chain else "direct"}_{"GRAV" if grav else "FIXED"}'
            probe.measure(prefix+'.unchanged', m, lambda: m.call('bf_response_tick', 0, 0))
            assert m.events == [], prefix
            m.uc.mem_write(m.sym['bf_roots']+source, b'\x29')
            m.uc.mem_write(m.sym['bf_pitches']+source, b'\x41')
            probe.measure(prefix+'.moved4', m, lambda: m.call('bf_response_tick', 0, 0))
            assert_voices(m, receivers, 5)
            m.events.clear()
            probe.measure(prefix+'.settled', m, lambda: m.call('bf_response_tick', 0, 0))
            assert m.events == [], prefix


def committed_live(probe):
    # Keep the historical uncommitted fixtures above unchanged. A previously
    # sounded GRAV root adds history-scoring work to the next LIVE movement.
    for chain, receivers in ((False, (0,)), (True, (0,)), (False, tuple(range(7)))):
        m, source = live_fixture(probe, chain, True, receivers)
        for receiver in receivers:
            m.call('bf_register_sent', receiver)
        m.uc.mem_write(m.sym['bf_roots']+source, b'\x29')
        m.uc.mem_write(m.sym['bf_pitches']+source, b'\x41')
        profile = 'seven' if len(receivers) > 1 else 'chain7' if chain else 'direct'
        probe.measure(f'live_{profile}_GRAV.committed_moved4', m,
                      lambda: m.call('bf_response_tick', 0, 0))
        assert_voices(m, receivers, 5)


def lifecycle(probe):
    # State must stay correct when an optimization skips idle feature work.
    # These use public setters, native context latches and actual Part copy.
    for operation in ('mode', 'mode_roundtrip', 'source_roundtrip', 'off_on',
                      'context', 'context_roundtrip', 'context_trig_roundtrip',
                      'replace', 'invalid_tran'):
        m, source = live_fixture(probe, grav=True)
        u = m.uc
        if operation in ('mode', 'mode_roundtrip'):
            m.call('bf_mode_set', 0, 0)
            if operation == 'mode':
                m.call('bf_response_tick', 0, 0)
            m.call('bf_mode_set', 0, 1)
        elif operation == 'source_roundtrip':
            m.call('bf_source_set', 0, 0)
            m.call('bf_source_set', 0, source+1)
        elif operation == 'off_on':
            m.call('bf_response_set', 0, 0)
            m.call('bf_response_tick', 0, 0)
            m.call('bf_response_set', 0, 1)
        elif operation == 'invalid_tran':
            # Even with an unchanged source token, an invalid effective
            # target disarms LIVE. Restoring TRAN cannot retune the old note.
            u.mem_write(0x46c76fe0+12, b'\x00')  # TRAN -64 => C3 - 64 < 0
            probe.measure('lifecycle.invalid_tran_same_token', m,
                          lambda: m.call('bf_response_tick', 0, 0))
            assert m.events == []
            u.mem_write(0x46c76fe0+12, b'\x40')
        else:
            copy = m.scratch+0x1000
            u.mem_write(copy, bytes(u.mem_read(PART, PART_SIZE)))
            if operation.startswith('context'):
                u.mem_write(PART+PART_SIZE, bytes(u.mem_read(copy, PART_SIZE)))
                u.mem_write(0x80006676, b'\x01')
                if operation == 'context_trig_roundtrip':
                    flags = PART+PART_SIZE+0x4e2+12
                    u.mem_write(flags, bytes((u.mem_read(flags, 1)[0] & ~2,)))
                    m.call('bf_response_tick', 0, 0)
                    u.mem_write(0x80006676, b'\x00')
                if operation == 'context_roundtrip':
                    u.mem_write(0x80006676, b'\x00')
            else:
                u.mem_write(m.stack+4, struct.pack('>III', PART, copy, PART_SIZE))
                m.call('store_part_native_copy')
        u.mem_write(m.sym['bf_roots']+source, b'\x29')
        u.mem_write(m.sym['bf_pitches']+source, b'\x41')
        probe.measure('lifecycle.'+operation, m, lambda: m.call('bf_response_tick', 0, 0))
        if operation in ('mode', 'mode_roundtrip', 'source_roundtrip', 'context_roundtrip'):
            # Register edits reset GRAV history while LIVE remains armed;
            # a latch round trip between services leaves the same identity.
            assert_voices(m, (0,), 5)
        else:
            assert m.events == [], (operation, m.events)
            # The release still identifies the originally sounding note.
            assert int.from_bytes(u.mem_read(0x46c77a1a, 4), 'big') == 36, operation


def accepted_lifecycle(probe):
    for operation in ('epoch', 'route', 'context'):
        m = probe.machine()
        source = route(m, False, True)
        m.call('bf_home_set', 0, 2)
        u = m.uc

        def root(pitch):
            u.mem_write(m.sym['bf_roots']+source, bytes((36+pitch % 12,)))
            u.mem_write(m.sym['bf_pitches']+source, bytes((pitch,)))

        def query():
            m.call('bf_register_begin', 0)
            return m.call('bf_register', source, 0)

        def accepted():
            return m.call('bf_seq_note_accepted', 0, 0,
                          regs={UC_M68K_REG_D2: 100, UC_M68K_REG_D3: 36})

        root(35)
        assert query() == 35
        accepted()
        root(36)
        assert query() == 36  # proposal exists but has not sounded
        if operation == 'epoch':
            copy = m.scratch+0x1000
            u.mem_write(copy, bytes(u.mem_read(PART, PART_SIZE)))
            u.mem_write(m.stack+4, struct.pack('>III', PART, copy, PART_SIZE))
            m.call('store_part_native_copy')
        elif operation == 'route':
            source = 2
            # Native state can change independently of the panel setter.
            m.follow_write('source', b'\x03')
        else:
            u.mem_write(PART+PART_SIZE, bytes(u.mem_read(PART, PART_SIZE)))
            u.mem_write(0x80006676, b'\x01')
        probe.measure('accepted.invalidate_'+operation, m, accepted)
        root(0)
        # With no committed history the home octave chooses C2. Committing
        # the stale C3 proposal above would incorrectly keep the next C at 36.
        assert query() == 24, operation


def enable_after_rest(probe):
    m = probe.machine()
    u = m.uc
    frame, lane = m.scratch+0x3000, 0x46c76dc0+7*32
    # All followers are OFF when a muted T8 source sounds. Enabling one later
    # during a rest must still see that historical source root.
    u.mem_write(frame-42, (128).to_bytes(4, 'big'))
    u.mem_write(frame-37, b'\x80')
    u.mem_write(0x46c76dc0+7*68+32, b'\x08')
    u.mem_write(lane+0x220, bytes((65, 90)))
    u.mem_write(lane+0x22c, b'\x40')
    probe.measure('enable.muted_source_while_off', m,
                  lambda: m.call('bf_pre_capture', stop=0x4009f98c,
                                 regs={UC_M68K_REG_A6: frame}))
    assert u.mem_read(m.sym['bf_roots']+7, 1)[0] == 41
    m.call('bf_source_set', 0, 8)
    u.mem_write(frame-42, bytes(4))
    probe.measure('enable.rest_after_source', m,
                  lambda: m.call('bf_pre_capture', stop=0x4009f98c,
                                 regs={UC_M68K_REG_A6: frame}))
    u.mem_write(m.scratch, b'\x3c')
    u.mem_write(frame-4, b'\x3c\xff\xff\xff')
    probe.measure('enable.note_after_rest', m,
                  lambda: m.call('bf_note', stop=0x4009fb86,
                                 regs={UC_M68K_REG_D7: 0, UC_M68K_REG_D4: 0,
                                       UC_M68K_REG_A2: m.scratch,
                                       UC_M68K_REG_A5: lane, UC_M68K_REG_A6: frame}))
    assert u.mem_read(m.scratch, 1)[0] == 41


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('remix', nargs='?', default='midi-follow')
    parser.add_argument('--artifact-root', type=Path, default=ROOT/'out',
                        help='built out/ tree, including mainos_bus.remix')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--record-only', action='store_true')
    args = parser.parse_args()
    output = args.output or ROOT/'out'/f'{args.remix}-follow-cpu.json'
    output.unlink(missing_ok=True)
    artifacts = args.artifact_root.resolve()
    identity = artifact_identity(artifacts, args.remix)
    probe = Probe(artifacts)
    for check in (idle, notes, live, committed_live, lifecycle, accepted_lifecycle, enable_after_rest):
        check(probe)
    assert artifact_identity(artifacts, args.remix) == identity, \
        'image/runtime/symbols/layout changed during Follow CPU gate'
    failures = []
    for name, result in probe.results.items():
        if name in BASELINE:
            result['review_baseline_instructions'] = BASELINE[name]
        if name in BUDGETS:
            result['budget'] = BUDGETS[name]
            if result['instructions'] > BUDGETS[name]:
                failures.append(f'{name}: {result["instructions"]} > {BUDGETS[name]}')
        print(f'  {name}: {result["instructions"]} instructions')
    receipt = dict(status='recorded' if args.record_only else 'fail' if failures else 'pass',
                   remix=args.remix, artifact_root=str(probe.artifacts),
                   **identity,
                   scope=__doc__, cases=probe.results, budget_failures=failures)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2)+'\n')
    assert args.record_only or not failures, '\n'.join(failures)
    print(f'[ok] {len(probe.results)} Follow instruction cases and lifecycle checks; {output}')


if __name__ == '__main__':
    main()
