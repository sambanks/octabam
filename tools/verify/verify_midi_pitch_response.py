#!/usr/bin/env python3
"""Focused linked LIVE response checks, with only native MIDI queue I/O replaced.

Run in the matching Octabam integration after building the selected composition.
The existing response fixture supplies native Part, ownership and release state.
This gate does not emulate sequencer time or prove UART/hardware timing; the
project-backed port gate supplies that separate boundary. No exhaustive scale
arithmetic is repeated here (see verify_harmony_follow_live.py).
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess

from unicorn import UC_HOOK_CODE
from unicorn.m68k_const import (
    UC_M68K_REG_A0, UC_M68K_REG_A1, UC_M68K_REG_A2, UC_M68K_REG_A3,
    UC_M68K_REG_A4, UC_M68K_REG_A5, UC_M68K_REG_A6, UC_M68K_REG_A7,
    UC_M68K_REG_D0, UC_M68K_REG_D1, UC_M68K_REG_D2, UC_M68K_REG_D3,
    UC_M68K_REG_D4, UC_M68K_REG_D5, UC_M68K_REG_D6, UC_M68K_REG_D7,
)
from harmony_midi_machine import MODES, ROOT, raw_scale
from verify_midi_follow_response import fixture


RECEIVER = 1
RELEASE = 0x46c77a16 + RECEIVER * 32
OWNERS = 0x46c78152 + RECEIVER * 128
DEADLINE = 0x46c7a7f0 + RECEIVER * 4
REGISTERS = (UC_M68K_REG_D0, UC_M68K_REG_D1, UC_M68K_REG_D2,
             UC_M68K_REG_D3, UC_M68K_REG_D4, UC_M68K_REG_D5,
             UC_M68K_REG_D6, UC_M68K_REG_D7, UC_M68K_REG_A0,
             UC_M68K_REG_A1, UC_M68K_REG_A2, UC_M68K_REG_A3,
             UC_M68K_REG_A4, UC_M68K_REG_A5, UC_M68K_REG_A6)
CALLBACKS = ('capture', 'prepare', 'owned', 'quant', 'target', 'shift')
CHECKS = Counter()


def linked_symbols():
    text = subprocess.check_output(
        ['m68k-elf-nm', str(ROOT / 'out/platform/runtime/runtime.elf')], text=True)
    rows = [row.split() for row in text.splitlines()]
    result = {f[2]: int(f[0], 16) for f in rows if len(f) == 3}
    # The accumulator's private BSS has no public alias. Refuse ambiguity
    # rather than accidentally checking an unrelated linked unit's state.
    phases = [int(f[0], 16) for f in rows
              if len(f) == 3 and f[1] == 'b' and f[2] == 'phases']
    if 'ha_fire_c' in result:
        assert len(phases) == 1, ('accumulator phases', phases)
        result['phases'] = phases[0]
    return result


def c_call(m, name, *args):
    m.uc.mem_write(m.stack + 4, b''.join(v.to_bytes(4, 'big') for v in args))
    return m.call(name)


def public_call(m, name, d0=0, d1=0):
    """The public tick and scratch adapter preserve registers and balance SP."""
    regs = {reg: 0x12340000 + index * 0x101 for index, reg in enumerate(REGISTERS)}
    regs.update({UC_M68K_REG_D0: d0, UC_M68K_REG_D1: d1,
                 UC_M68K_REG_D7: RECEIVER, UC_M68K_REG_A2: m.scratch})
    m.call(name, regs=regs)
    assert all(m.uc.reg_read(reg) == value for reg, value in regs.items()), name
    assert m.uc.reg_read(UC_M68K_REG_A7) == m.stack + 4, (name, 'stack')
    CHECKS[name] += 1


def callback_abi(symbols):
    """Call providers directly, without Follow's register-restoring wrappers."""
    def invoke(m, callback, inputs, expected, rotation=None):
        name = 'mh_pitch_' + callback
        regs = {reg: 0x23450000 + index * 0x101
                for index, reg in enumerate(REGISTERS)}
        # Each address sentinel points at mapped, writable scratch. None is a
        # callback parameter, but accidental dereferences cannot hit address 0.
        for index, reg in enumerate(REGISTERS[8:]):
            regs[reg] = m.scratch + 0x100 + index * 0x20
        regs[UC_M68K_REG_D7] = RECEIVER
        regs.update(inputs)
        m.call(name, regs=regs)
        allowed = {UC_M68K_REG_D0}
        if callback == 'prepare':
            allowed.add(UC_M68K_REG_D1)
            assert m.uc.reg_read(UC_M68K_REG_D1) == rotation, (name, 'rotation')
        assert m.uc.reg_read(UC_M68K_REG_D0) == expected, (
            name, hex(m.uc.reg_read(UC_M68K_REG_D0)), hex(expected))
        changed = {reg: (value, m.uc.reg_read(reg)) for reg, value in regs.items()
                   if reg not in allowed and m.uc.reg_read(reg) != value}
        assert not changed, (name, 'clobbered registers', changed)
        assert m.uc.reg_read(UC_M68K_REG_A7) == m.stack + 4, (name, 'stack')
        # Capture SR only after return: reading Unicorn's lazy flags inside a
        # callback can alter a branch. Preparation may mask briefly but must
        # restore the caller's non-maximal interrupt level.
        assert (m.read_sr() & 0x700) == (m.initial_sr & 0x700), (name, 'interrupt mask')
        if callback != 'prepare':
            assert all(m.stack - 4096 <= address and address + size <= m.stack + 4
                       for address, size in m.writes), (name, 'non-stack write', m.writes)
        assert m.events == [], (name, 'provider emitted MIDI')
        CHECKS[name] += 1

    for mode in (0, 1, 2):
        m = setup(symbols, follower_mode=mode, key=1)
        m.initial_sr = 0x2300
        m.uc.mem_write(m.part_address(RECEIVER, 19), b'\x23')  # C3, degree code 35
        m.call('hd_events_reset_c')
        m.uc.mem_write(symbols['hd_busy'] + RECEIVER, b'\0')
        m.uc.mem_write(symbols['hd_busy_context'] + RECEIVER, b'\0')
        m.uc.mem_write(0x46c7a124 + RECEIVER, b'\x03')
        m.uc.mem_write(0x46c77b1e + RECEIVER * 10, b'\0')
        invoke(m, 'capture', {UC_M68K_REG_D0: RECEIVER}, int(bool(mode)))
        m.uc.mem_write(0x46c77b1e + RECEIVER * 10, b'\1')
        invoke(m, 'capture', {UC_M68K_REG_D0: RECEIVER}, 1)
        m.uc.mem_write(0x46c77b1e + RECEIVER * 10, b'\0')
        invoke(m, 'owned', {UC_M68K_REG_D0: RECEIVER}, int(bool(mode)))
        invoke(m, 'quant', {UC_M68K_REG_D0: 42, UC_M68K_REG_D1: RECEIVER},
               41 if mode else 42)
        invoke(m, 'target', {UC_M68K_REG_D0: 38, UC_M68K_REG_D1: RECEIVER},
               41 if mode else 38)
        # The caller has established ownership once for this operation. OFF
        # declines at owned above and follows the native path in controls().
        if mode:
            invoke(m, 'shift', {UC_M68K_REG_D0: 40, UC_M68K_REG_D1: 36,
                               UC_M68K_REG_D2: 38}, 41)
            invoke(m, 'shift', {UC_M68K_REG_D0: 127, UC_M68K_REG_D1: 36,
                               UC_M68K_REG_D2: 38}, 0xffffffff)
        invoke(m, 'prepare', {UC_M68K_REG_D0: 60, UC_M68K_REG_D1: 9},
               48 if mode else 60, rotation=0 if mode else 9)
        # A changing captured context yields invalid preparation before the
        # valid-output branch. Its stock scale rotation must survive too.
        m.uc.mem_write(symbols['hd_busy'] + RECEIVER, b'\1')
        invoke(m, 'prepare', {UC_M68K_REG_D0: 60, UC_M68K_REG_D1: 9},
               0xffffffff, rotation=9)


def protected_state(m):
    """State a pitch response must not regenerate, advance, release or persist."""
    regions = {
        'native arp control': (0x46c77b1e, 0x46c78152 - 0x46c77b1e),
        'native arp pool': (0x46c7a2a0, 0x400),
        'native deadlines': (0x46c7a7f0, 32),
        'native Parts': (0x400e21e0 + 0x8ed80, 4 * 0x18b2),
    }
    if 'mh_generate' in m.sym:
        for name, size in (
            ('phases', 1120), ('ha_lanes', 75776),
            ('mh_voice_history', 64), ('mh_voice_context', 32), ('mh_voice_epoch', 32),
            ('mh_held', 4096), ('mh_refs', 1024), ('mh_key_tokens', 2048),
            ('mhc_sequence_quality', 8), ('mhc_pressed', 32),
        ):
            assert name in m.sym, ('missing protected state', name)
            regions[name] = (m.sym[name], size)
    return {name: bytes(m.uc.mem_read(address, size))
            for name, (address, size) in regions.items()}


def setup(symbols, tones=(36,), *, source_mode=0, follower_mode=0, key=0,
          quality=0, response=1, root=36):
    m = fixture(pitches=tones, response=response)
    m.instruction_budget = 30_000_000  # explicit dense accumulator initialization
    m.sym.update(symbols)
    u = m.uc
    for track, mode in ((0, source_mode), (RECEIVER, follower_mode)):
        u.mem_write(m.part_address(track, 5), bytes((mode,)))
    m.set_key(0, key)
    m.set_key(RECEIVER, 24 if key != 24 else 1)  # deliberately different own KEY
    if 'mh_generate' in m.sym:
        u.mem_write(m.sym['mhc_sequence_quality'] + RECEIVER, bytes((quality,)))
        # An unsounded valid ACC event makes accidental accepted-note/advance
        # observable even when its first offset is zero.
        m.call('ha_runtime_reset_c')
        c_call(m, 'ha_bank_reset_c', 0)
        c_call(m, 'ha_fire_c', 0, 0, RECEIVER, 0)
    u.mem_write(m.sym['bf_roots'], bytes((root,)))
    u.mem_write(m.sym['bf_pitches'], bytes((root + 24,)))
    m.call('bf_response_tick', 1 << RECEIVER, 0)
    u.mem_write(m.scratch, bytes((root,)))
    m.call('bf_response_observe', regs={UC_M68K_REG_D7: RECEIVER,
           UC_M68K_REG_D4: 0, UC_M68K_REG_A2: m.scratch})
    m.events.clear()
    # A response is not a new trig, generated chord, arp rebuild or ACC event.
    forbidden = {symbols[name]: name for name in (
        'mh_generate', 'mh_sequence', 'mh_voice', 'ha_fire_c', 'ha_sounded_c',
        'mh_seq_note_accepted', 'mhc_sequence_context') if name in symbols}
    forbidden[0x40099c08] = 'native arp rebuild'
    def guard(uc, pc, size, data):
        assert pc not in forbidden, ('LIVE entered ordinary event path', forbidden.get(pc))
    u.hook_add(UC_HOOK_CODE, guard)
    return m


def change(m, root, mask=0, mute=0):
    before = protected_state(m)
    m.uc.mem_write(m.sym['bf_roots'], bytes((root,)))
    m.uc.mem_write(m.sym['bf_pitches'], bytes((root + 24,)))
    m.events.clear()
    public_call(m, 'bf_response_tick', mask, mute)
    after = protected_state(m)
    assert before == after, ('LIVE mutated protected state',
                             [name for name in before if before[name] != after[name]])
    assert int.from_bytes(m.uc.mem_read(DEADLINE, 4), 'big') == 37
    return list(m.events)


def owned(m, expected):
    for slot in range(4):
        value = int.from_bytes(m.uc.mem_read(RELEASE + slot * 8 + 4, 4), 'big')
        assert value == (expected[slot] if slot < len(expected) else 0xffffffff)
    for slot, pitch in enumerate(expected):
        assert m.uc.mem_read(OWNERS + pitch, 1)[0] == RECEIVER * 4 + slot


def transitions(symbols, key, mode, source_mode, quality=0, inversion=False):
    degrees = MODES[mode]
    scale = [n for n in range(-24, 161) if n % 12 in degrees]
    roots = [36, 36 + degrees[1], 36 + degrees[3], 36]
    if quality == 5:
        tones = (36, 40, 43)
    else:
        start = scale.index(36)
        tones = tuple(scale[start + degree] for degree in ((4, 7, 9) if inversion else (0, 2, 4)))
    for follower_mode in (1, 2):
        original = tones[:1] if follower_mode == 1 else tones
        m = setup(symbols, original, source_mode=source_mode,
                  follower_mode=follower_mode, key=key, quality=quality)
        previous = list(original)
        for root in roots[1:] * 2:
            shift = scale.index(root) - scale.index(36)
            want = [pitch + root - 36 if quality == 5 else scale[scale.index(pitch) + shift]
                    for pitch in original]
            events = change(m, root)
            assert events == ([(0x91, pitch, 0) for pitch in previous] +
                              [(0x91, pitch, 91) for pitch in want]), (
                                  key, source_mode, follower_mode, quality, events, want)
            owned(m, want)
            previous = want
            assert change(m, root) == [], 'unchanged source emitted MIDI'
            # The cached original pool is stable. Transform only each outgoing
            # scratch pitch, as stock continues its existing arp clock/order.
            state = protected_state(m)
            release = bytes(m.uc.mem_read(RELEASE, 32))
            owners = bytes(m.uc.mem_read(0x46c78152, 2048))
            for pitch, target in zip(original, want):
                m.uc.mem_write(m.scratch, bytes((pitch,)))
                public_call(m, 'bf_response_adjust')
                assert m.uc.mem_read(m.scratch, 1)[0] == target
            assert protected_state(m) == state
            assert bytes(m.uc.mem_read(RELEASE, 32)) == release
            assert bytes(m.uc.mem_read(0x46c78152, 2048)) == owners
            assert m.events == [], 'arp scratch adjustment emitted MIDI'


def controls(symbols):
    modes = (0, 2) if 'mh_generate' in symbols else (0,)
    for follower_mode in modes:
        def case(tones=(36,), **kwargs):
            return setup(symbols, tones, follower_mode=follower_mode, **kwargs)
        m = case((36, 40, 43))  # KEY OFF stays chromatic with or without Harmony.
        assert change(m, 38) == ([(0x91, n, 0) for n in (36, 40, 43)] +
                                  [(0x91, n, 91) for n in (38, 42, 45)])
        owned(m, (38, 42, 45))
        if not follower_mode:
            m.uc.mem_write(m.scratch, b'\x28')
            public_call(m, 'bf_response_adjust')
            assert m.uc.mem_read(m.scratch, 1) == b'\x28', 'unclaimed arp changed'
        assert change(case(response=0), 38) == [], 'TRIG changed held pitch'
        assert change(case(()), 38) == [], 'rest acquired a voice'
        for mask, mute in ((2, 0), (2 << 8, 0), (2 << 16, 0), (0, 2)):
            m = case()
            before = bytes(m.uc.mem_read(RELEASE, 32))
            assert change(m, 38, mask, mute) == []
            assert bytes(m.uc.mem_read(RELEASE, 32)) == before
        m = case()
        m.uc.mem_write(OWNERS + 36, b'\x20')  # foreign/live owner
        assert change(m, 38) == []
        assert m.uc.mem_read(OWNERS + 36, 1) == b'\x20'
        assert int.from_bytes(m.uc.mem_read(RELEASE + 4, 4), 'big') == 36
        m = case()
        m.uc.mem_write(OWNERS + 38, b'\x08')  # other track already owns target
        assert change(m, 38) == [(0x91, 36, 0)]
        assert m.uc.mem_read(OWNERS + 38, 1) == b'\x08'
        assert m.uc.mem_read(OWNERS + 36, 1) == b'\xff'
        owned(m, ())
        for pitch, root, target in ((127, 36, 38), (0, 41, 36)):
            m = case((pitch,), root=root)
            assert change(m, target) == [(0x91, pitch, 0)], 'out-of-range pitch wrapped'
            owned(m, ())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('remix', nargs='?')
    parser.add_argument('--expect-harmony', choices=('present', 'absent'))
    parser.add_argument('--output', type=Path, default=ROOT / 'out/midi-pitch-response.json')
    args = parser.parse_args()
    CHECKS.clear()
    def artifact_hashes():
        return {name: hashlib.sha256((ROOT / 'out' / name).read_bytes()).hexdigest()
                for name in ('mainos_bus.bin', 'platform/runtime/runtime.elf',
                             'platform/runtime/runtime.bin', 'platform/layout.json',
                             'mainos_bus.remix')}
    identity = artifact_hashes()
    marker = (ROOT / 'out/mainos_bus.remix').read_text().split()
    assert len(marker) == 2 and marker[1] == identity['mainos_bus.bin'], 'invalid image identity'
    if args.remix:
        assert marker[0] == args.remix, ('unexpected remix', marker[0], args.remix)
    symbols = linked_symbols()
    assert 'bf_response_tick' in symbols, 'select MIDI FOLLOW for this response gate'
    harmony = 'mh_generate' in symbols
    for callback in CALLBACKS:
        assert ('mh_pitch_' + callback in symbols) == harmony, (
            callback, 'unexpected provider composition')
    if args.expect_harmony:
        assert harmony == (args.expect_harmony == 'present'), 'unexpected composition'
    controls(symbols)
    scales = []
    if harmony:
        callback_abi(symbols)
        scales = [(1, 0), (2, 5)]
        if 'ms_snap' in symbols:
            scales += [(raw_scale(0, 1), 1), (raw_scale(0, 3), 3)]
        for key, mode in scales:
            for source_mode in range(3):
                transitions(symbols, key, mode, source_mode)
        transitions(symbols, 1, 0, 0, quality=5)
        transitions(symbols, 1, 0, 2, inversion=True)
    assert artifact_hashes() == identity, 'linked artifacts changed during response gate'
    receipt = dict(
        image_sha256=identity['mainos_bus.bin'], artifacts=identity,
        remix=marker[0], checked_calls=dict(CHECKS), checked_call_count=sum(CHECKS.values()),
        harmony_selected=harmony, scales=scales, native_controls=True,
        registers_and_stack=True, unchanged_deadlines=True,
        ownership_collisions_and_bounds=True, protected_state_unchanged=True,
        ordinary_event_paths_not_entered=True,
        direct_callback_abi=harmony,
        boundary='linked firmware with substituted native MIDI queue; no sequencer clock or UART',
        hardware_tested=False,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(f'[ok] {sum(CHECKS.values())} checked calls: selected LIVE response, cached arp scratch, register/stack ABI, '
          'ownership/deadlines and unchanged arp/ACC/voice/Part state', flush=True)


if __name__ == '__main__':
    main()
