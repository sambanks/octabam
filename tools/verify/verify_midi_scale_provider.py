#!/usr/bin/env python3
"""Check the linked scale service against music and executable stock firmware.

The adapter reads explicit working/saved Part contexts. Pure-helper checks
cover the register/stack contract, native rounding, general masks and Harmony's
exact seven-mode whitelist; they do not qualify an external provider or hardware.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from midi_machine import Machine, ROOT
from unicorn.m68k_const import (
    UC_M68K_REG_A0, UC_M68K_REG_A1, UC_M68K_REG_A2, UC_M68K_REG_A3,
    UC_M68K_REG_A4, UC_M68K_REG_A5, UC_M68K_REG_A6, UC_M68K_REG_A7,
    UC_M68K_REG_D1, UC_M68K_REG_D2, UC_M68K_REG_D3, UC_M68K_REG_D4,
    UC_M68K_REG_D5, UC_M68K_REG_D6, UC_M68K_REG_D7,
)


MODES = ((0, 2, 4, 5, 7, 9, 11), (0, 2, 3, 5, 7, 9, 10),
         (0, 1, 3, 5, 7, 8, 10), (0, 2, 4, 6, 7, 9, 11),
         (0, 2, 4, 5, 7, 9, 10), (0, 2, 3, 5, 7, 8, 10),
         (0, 1, 3, 5, 6, 8, 10))
MASKS = tuple(sum(1 << n for n in notes) for notes in MODES)
REGISTERS = (UC_M68K_REG_D1, UC_M68K_REG_D2, UC_M68K_REG_D3,
             UC_M68K_REG_D4, UC_M68K_REG_D5, UC_M68K_REG_D6,
             UC_M68K_REG_D7, UC_M68K_REG_A0, UC_M68K_REG_A1,
             UC_M68K_REG_A2, UC_M68K_REG_A3, UC_M68K_REG_A4,
             UC_M68K_REG_A5, UC_M68K_REG_A6)
BANK, BANK_STRIDE, PART_STRIDE = 0x400e21e0, 0x9b340, 0x18b2
WORKING, SAVED, SETUP, KEY = 0x8ed80, 0x9504a, 0x4e2, 17
U32 = 0xffffffff


def symbols():
    rows = subprocess.check_output(
        ['m68k-elf-nm', str(ROOT / 'out/platform/runtime/runtime.elf')], text=True)
    return {f[2]: int(f[0], 16) for row in rows.splitlines()
            if len(f := row.split()) == 3}


def key_mode(key, extended):
    if not 1 <= key <= (84 if extended else 24):
        return None
    if key <= 24:
        return (key - 1) // 2, 5 if key % 2 == 0 else 0
    return (key - 25) // 5, (1, 2, 3, 4, 6)[(key - 25) % 5]


def descriptor(key, extended):
    decoded = key_mode(key, extended)
    if decoded is None:
        return 0
    tonic, mode = decoded
    return MASKS[mode] | tonic << 12 | (0x10000 if key <= 24 else 0)


def field(context, track):
    saved = context >= 64
    bank, part = divmod(context % 64, 4)
    return (BANK + bank * BANK_STRIDE + (SAVED if saved else WORKING)
            + part * PART_STRIDE + SETUP + track * 36 + KEY)


def nearest(pitch, tonic, mask):
    valid = [n for n in range(128) if mask & (1 << ((n - tonic) % 12))]
    return min(valid, key=lambda n: (abs(n - pitch), n))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('remix', nargs='?')
    parser.add_argument('--output', type=Path, default=ROOT / 'out/midi-scale-provider.json')
    args = parser.parse_args()
    artifact_names = ('mainos_bus.bin', 'mainos_bus.remix', 'platform/layout.json',
                      'platform/runtime/runtime.elf', 'platform/runtime/runtime.bin')
    def identity():
        return {name: hashlib.sha256((ROOT / 'out' / name).read_bytes()).hexdigest()
                for name in artifact_names}
    before = identity()
    marker = (ROOT / 'out/mainos_bus.remix').read_text().split()
    assert len(marker) == 2 and marker[1] == before['mainos_bus.bin'], marker
    if args.remix:
        assert marker[0] == args.remix, (marker, args.remix)
    sym = symbols()
    for name in ('msp_quant', 'msp_legacy'):
        assert name in sym, ('missing scale service', name)
    extended = 'ms_snap' in sym
    m = Machine(lambda: sym.copy())
    m.initial_sr = 0x2300
    counts = dict(reads=0, native_quant=0, extension_quant=0,
                  general_quant=0, legacy=0, guards=0, abi=0, effective=0)

    def call(name, d0=0, d1=0):
        regs = {reg: 0x12340000 + i * 0x101 for i, reg in enumerate(REGISTERS)}
        regs[UC_M68K_REG_D1] = d1 & U32
        got = m.call(name, d0 & U32, d1 & U32, regs=regs)
        assert all(m.uc.reg_read(reg) == value for reg, value in regs.items()), (name, 'registers')
        assert m.uc.reg_read(UC_M68K_REG_A7) == m.stack + 4, (name, 'stack')
        assert m.read_sr() & 0x700 == m.initial_sr & 0x700, (name, 'interrupt mask')
        assert all(m.stack - 512 <= a and a + n <= m.stack + 4 for a, n in m.writes), (name, 'write bounds', m.writes)
        counts['abi'] += 1
        return got

    native_key_adapter = 'msp_key_read' in sym
    # A future adapter must qualify its own explicit-context reader. The
    # common arithmetic contract remains testable without a KEY reader.
    if native_key_adapter:
        # UI and live lane deliberately disagree with explicit reads.
        m.uc.mem_write(0x46c82456, (BANK + 2 * BANK_STRIDE).to_bytes(4, 'big'))
        m.uc.mem_write(0x100b14cf, b'\x02')
        for track in range(8):
            m.uc.mem_write(0x46c76df1 + 68 * track, b'\x18')
        for context in (0, 7, 64, 127):
            for key in range(256):
                m.uc.mem_write(field(context, 3), bytes((key,)))
                assert call('msp_key_read', 3, context) == descriptor(key, extended), (context, key)
                counts['reads'] += 1
        for context in range(128):
            for track in range(8):
                key = (context * 8 + track) % 85
                m.uc.mem_write(field(context, track), bytes((key,)))
                assert call('msp_key_read', track, context) == descriptor(key, extended), (context, track, key)
                counts['reads'] += 1
        for track, context in ((8, 0), (255, 0), (U32, 0), (0, 128), (0, 255), (0, U32)):
            assert call('msp_key_read', track, context) == U32, (track, context)
            counts['guards'] += 1

    # Execute stock's own correction instructions, including their edge cases.
    stock = Machine(lambda: sym.copy())
    stock.uc.mem_write(0x40000400, (ROOT / 'out/raw/section_3_MAIN_OS.bin').read_bytes())
    stock.sym['stock_quant'] = 0x4009fb58
    frame = stock.scratch + 0x100
    for key in range(25):
        decoded = key_mode(key, extended)
        legacy = U32 if decoded is None else decoded[0] << 2 | decoded[1] << 6
        assert call('msp_legacy', descriptor(key, extended)) == legacy, key
        counts['legacy'] += 1
        rotation = (12 if key & 1 else 21) - ((key - 1) // 2) if key else 0
        stock.uc.mem_write(frame - 64, rotation.to_bytes(4, 'big'))
        for pitch in range(128):
            stock.uc.mem_write(stock.scratch, bytes((pitch,)))
            # Capture the full correction result immediately before stock's
            # byte store: native edge notes can return -1 or 128. Consumers
            # decide whether to suppress them, so truncating here hides drift.
            expected = stock.call('stock_quant', d0=pitch,
                                  stop=0x4009fb7e if key else 0x4009fb80,
                                  regs={UC_M68K_REG_A2: stock.scratch,
                                        UC_M68K_REG_A6: frame})
            assert call('msp_quant', pitch, descriptor(key, extended)) == expected, (key, pitch, expected)
            counts['native_quant'] += 1
    for key in range(25, 85):
        tonic, mode = key_mode(key, True)
        for pitch in range(128):
            desc = descriptor(key, True)
            assert call('msp_quant', pitch, desc) == nearest(pitch, tonic, MASKS[mode]), (key, pitch)
            counts['extension_quant'] += 1

    # Seven notes alone do not make a supported Harmony mode. These exercise
    # shared mask arithmetic only; no unregistered provider is composed.
    extra = ((0, 2, 3, 5, 7, 8, 11), (0, 2, 4, 7, 9),
             (0, 2, 4, 6, 8, 10), (0, 2, 3, 5, 6, 8, 9, 11), tuple(range(12)))
    for notes in extra:
        mask = sum(1 << n for n in notes)
        assert mask not in MASKS
        for tonic in range(12):
            desc = mask | tonic << 12
            assert call('msp_legacy', desc) == U32 - 1, (notes, tonic)
            for pitch in range(128):
                assert call('msp_quant', pitch, desc) == nearest(pitch, tonic, mask), (notes, tonic, pitch)
                counts['general_quant'] += 1
    assert call('msp_legacy', 0) == U32
    for mask in range(1, 4096):
        want = MASKS.index(mask) << 6 if mask in MASKS else U32 - 1
        assert call('msp_legacy', mask) == want, mask
        counts['legacy'] += 1
    for tonic in range(12):
        for mode, mask in enumerate(MASKS):
            assert call('msp_legacy', tonic << 12 | mask) == tonic << 2 | mode << 6
            counts['legacy'] += 1
    invalid = (U32, 0x20000 | MASKS[0], 12 << 12 | MASKS[0],
               15 << 12 | MASKS[0], 1 << 12, 0x10000,
               0x10000 | MASKS[1], 0x10000 | 0xfff)
    for desc in invalid:
        assert call('msp_legacy', desc) == U32 - 1, hex(desc)
        for pitch in (0, 60, 127):
            assert call('msp_quant', pitch, desc) == U32, (pitch, hex(desc))
            counts['guards'] += 1
    for pitch in (128, 255, U32):
        for desc in (0, descriptor(1, extended), U32):
            assert call('msp_quant', pitch, desc) == pitch, (pitch, desc)
            counts['guards'] += 1
    if native_key_adapter and 'bf_effective' in sym:
        # The source-capture caller can suppress stock KEY correction even
        # when its Part has a KEY. A descriptor must not erase that decision.
        source = Machine(lambda: sym.copy())
        lane = source.scratch + 0x800
        source.uc.mem_write(lane + 0x22c, b'\x40')
        source.uc.mem_write(0x46c7a124, b'\0')
        source.uc.mem_write(0x8000666e, bytes(16))
        for key, rotations in ((1, (0, 12)), (2, (0, 21))):
            source.uc.mem_write(field(0, 0), bytes((key,)))
            for rotation in rotations:
                stock.uc.mem_write(frame - 64, rotation.to_bytes(4, 'big'))
                for pitch in range(128):
                    stock.uc.mem_write(stock.scratch, bytes((pitch,)))
                    stock.call('stock_quant', stop=0x4009fb80,
                               regs={UC_M68K_REG_A2: stock.scratch, UC_M68K_REG_A6: frame})
                    expected = stock.uc.mem_read(stock.scratch, 1)[0]
                    if expected > 127:
                        expected = 256
                    got = source.call('bf_effective', pitch, rotation,
                                      regs={UC_M68K_REG_A5: lane, UC_M68K_REG_D7: 0})
                    assert got == expected, ('source capture', key, rotation, pitch, got, expected)
                    counts['effective'] += 1
    assert identity() == before, 'image changed during scale gate'
    receipt = dict(remix=marker[0], artifacts=before, extended_key_adapter=extended,
                   counts=counts, explicit_working_and_saved_contexts=native_key_adapter,
                   adapter_read_coverage='native KEY matrix' if native_key_adapter else 'requires adapter-specific gate',
                   exact_seven_mode_whitelist=True, stock_instruction_oracle=True,
                   registers_stack_interrupt_mask_and_write_bounds=True,
                   boundary=__doc__, hardware_tested=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + '\n')
    print('[ok] scale service:', counts, 'MIDI Scales' if extended else 'stock KEY', flush=True)


if __name__ == '__main__':
    main()
