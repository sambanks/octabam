#!/usr/bin/env python3
"""Linked-code gate for Part-owned CHRD defaults and pattern inheritance."""
import json
import re
import subprocess

from harmony_midi_machine import Machine, ROOT
from unicorn.m68k_const import *

BANK, STRIDE, PART = 0x400e21e0, 0x9b340, 0x18b2


def symbols():
    raw = subprocess.check_output(['m68k-elf-nm', str(ROOT/'out/platform/runtime/runtime.elf')], text=True)
    return {n: int(a, 16) for a, n in re.findall(r'^([0-9a-f]+) [TtBbDd] ((?:ch|store_part|mh|hd)_\w+)$', raw, re.M)}




def main():
    m = Machine(symbols)
    u = m.uc
    def put(a, v, n=1):
        u.mem_write(a, v.to_bytes(n, 'big'))
    def at(bank, part, track):
        return BANK+bank*STRIDE+0x8ed80+part*PART+0x4e2+track*36+18
    def ui(bank, part):
        put(0x46c82456, BANK+bank*STRIDE, 4)
        put(0x100b14cf, part)
    def lock(bank, pattern, track, step):
        return m.call('ch_lock_get', bank, pattern,
                      regs={UC_M68K_REG_D2: track, UC_M68K_REG_D3: step})
    # Simultaneous selected, engine, captured and pattern contexts differ.
    ui(2, 1)
    put(at(2, 1, 0), 2)
    put(at(5, 2, 0), 5)
    put(at(7, 3, 0), 7)
    put(0x8000666e, 5)
    put(0x80006676, 2)
    put(BANK+7*STRIDE+4*0x8ed8+0x8e57, 3)
    assert m.call('ch_base_get', 0) == 2
    assert m.call('ch_base_play', 0) == 5
    assert m.call('ch_base_at', 0, 31) == 7
    assert m.call('ch_base_pattern', 7, 4, regs={UC_M68K_REG_D2: 0}) == 7
    assert m.call('ch_pattern_context', 7, 4) == 31
    # Boot RAM is not guaranteed zero: compressed staging may overlap BSS.
    # First init frees every message; repeated init must retain queued owners.
    u.mem_write(m.sym['ch_messages'], b'\xa5'*4096)
    put(m.sym['ch_record_overflow'], 123, 4)
    m.call('ch_lock_init')
    assert bytes(u.mem_read(m.sym['ch_messages'], 4096)) == b'\0'*4096
    assert bytes(u.mem_read(m.sym['ch_record_overflow'], 4)) == b'\0'*4
    put(m.sym['ch_messages']+14, 1)
    m.call('ch_lock_init')
    assert u.mem_read(m.sym['ch_messages']+14, 1)[0] == 1
    m.call('ch_record_free', stop=0x40045614,
           regs={UC_M68K_REG_A2: m.sym['ch_messages']})
    assert u.mem_read(m.sym['ch_messages']+14, 1)[0] == 0
    assert lock(7, 4, 0, 6) == 7
    index = ((7*16+4)*8)*64+6
    put(m.sym['ch_lock_table']+index, 3)
    assert lock(7, 4, 0, 6) == 3
    put(at(7, 3, 0), 1)
    assert lock(7, 4, 0, 6) == 3, 'Part changes must not overwrite explicit CHRD'
    assert lock(7, 4, 0, 7) == 1, 'unlocked CHRD must inherit current Part'
    # Exercise the real staging/fire detours. Pending defaults use captured
    # context even when UI and engine move elsewhere before the trigger.
    def stage(step, slot):
        put(m.stack+48, 7, 4)
        put(m.stack+60, slot & 0xffffffff, 4)
        m.call('ch_stage_fill', stop=0x4009d188,
               regs={UC_M68K_REG_D3: 0, UC_M68K_REG_D7: step,
                     UC_M68K_REG_A3: 4, UC_M68K_REG_A5: m.scratch})
    def fire(slot):
        m.call('ch_pending_fire', stop=0x400a19e2,
               regs={UC_M68K_REG_A0: 0x46c78960+slot*8*32,
                     UC_M68K_REG_A1: m.scratch, UC_M68K_REG_D5: 0})
        return u.mem_read(m.sym['ch_sequence_quality'], 1)[0]
    stage(6, 0)  # explicit quality 3
    stage(7, 1)  # inherit captured bank 7, Part 3
    put(at(7, 3, 0), 6)
    put(0x8000666e, 1)
    put(0x80006676, 0)
    assert fire(0) == 3
    assert fire(1) == 6
    for name, track_reg, continuation in (('ch_stage_copy_a', UC_M68K_REG_D2, 0x4009b922),
                                          ('ch_stage_copy_b', UC_M68K_REG_D1, 0x4009c10e)):
        stage(7, -1)
        m.call(name, stop=continuation, regs={track_reg: 0, UC_M68K_REG_A0: 0})
        put(at(7, 3, 0), 4)
        assert fire(0) == 4, name
    # Every track in all working Parts and banks has independent storage.
    writes = 0
    for bank in range(16):
        for part in range(4):
            ui(bank, part)
            for track in range(8):
                value = (bank+part+track) % 8
                put(at(bank, part, track), 255)
                assert m.call('ch_base_set', track, value) == 1
                allowed = {at(bank, part, track), BANK+bank*STRIDE+0x95048,
                           BANK+bank*STRIDE+0x9b332,
                           0x100a4ece+part*PART+0x4e2+track*36+18,
                           0x100b145e, 0x100f8598}
                assert all(a in allowed or m.stack-128 <= a and a+n <= m.stack+4
                           for a, n in m.writes), m.writes
                assert m.call('ch_base_get', track) == value
                assert m.call('ch_base_at', track, bank*4+part) == value
                assert u.mem_read(0x100a4ece+part*PART+0x4e2+track*36+18, 1)[0] == value
                writes += 1
    # Native Part bytes are authoritative on recall; a volatile live override
    # and an earlier default cannot conceal a new Part in the same slot.
    ui(2, 1)
    put(at(2, 1, 0), 6)
    put(m.sym['ch_live'], 7)
    assert m.call('ch_base_get', 0) == 6
    put(at(2, 1, 0), 4)
    assert m.call('ch_base_get', 0) == 4
    # Corrupt values resolve to TRI, invalid edits never touch Part memory.
    for value in (32, 127, 255):
        put(at(2, 1, 0), value)
        assert m.call('ch_base_get', 0) == 0
        assert m.call('ch_base_set', 0, value) == 0
        assert bytes(u.mem_read(at(2, 1, 0), 1)) == bytes([value])
    for track, context in ((8, 0), (0, 64), (0, 0xffffffff)):
        assert m.call('ch_base_at', track, context) == 0
    for bank, pattern, track, step in ((16, 0, 0, 0), (0, 16, 0, 0),
                                       (0, 0, 8, 0), (0, 0, 0, 64)):
        assert lock(bank, pattern, track, step) == 0
    # Public Part helpers retain all non-result registers, including inputs.
    kept = (UC_M68K_REG_D1, UC_M68K_REG_D2, UC_M68K_REG_D3,
            UC_M68K_REG_D4, UC_M68K_REG_D5, UC_M68K_REG_D6, UC_M68K_REG_D7,
            UC_M68K_REG_A0, UC_M68K_REG_A1, UC_M68K_REG_A2,
            UC_M68K_REG_A3, UC_M68K_REG_A4, UC_M68K_REG_A5, UC_M68K_REG_A6)
    for name, d0, d1, d2 in (('ch_base_get', 0, 9, 13), ('ch_base_play', 0, 9, 13),
                             ('ch_base_at', 0, 9, 13), ('ch_base_set', 0, 3, 13),
                             ('ch_pattern_context', 7, 4, 13), ('ch_base_pattern', 7, 4, 0)):
        regs = {reg: 0x12345678 for reg in kept}
        regs[UC_M68K_REG_D1] = d1
        regs[UC_M68K_REG_D2] = d2
        m.call(name, d0, d1, regs=regs)
        for reg, expected in regs.items():
            assert u.reg_read(reg) == expected, (name, reg)
    # Execute the native initializer using this exact image's descriptors.
    # Fresh Parts have TRI on every track, without an auxiliary init store.
    fresh = 0x47002000
    u.mem_write(fresh, b'\xa5'*PART)
    m.sym['native_part_init'] = 0x40005638
    u.mem_write(m.stack+4, fresh.to_bytes(4, 'big'))
    m.call('native_part_init')
    assert all(u.mem_read(fresh+0x4e2+track*36+18, 1)[0] == 0 for track in range(8))
    assert int.from_bytes(u.mem_read(0x400d43a6, 4), 'big') == 32
    # Plain chromatic/grid roots inherit the selected Part, even when the
    # engine plays another Part and CHORD PLAY left an older live variation.
    # The real queued recorder freezes that quality before subsequent edits.
    ui(2, 1)
    physical_cases = 0
    for mode, grid in ((0, 0), (1, 0), (6, 0), (6, 1)):
        put(0x460d16f0, mode, 4)
        put(0x460d1736, grid, 4)
        for track in range(8):
            quality = (track+1) % 8
            latched = (quality+3) % 8
            put(at(2, 1, track), quality)
            put(at(2, 1, track)-13, 2)  # native HARM CHORD
            put(at(5, 2, track), (quality+5) % 8)
            put(0x8000666e+track, 5)
            put(0x80006676+track, 2)
            put(m.sym['ch_live']+track, latched)
            expected = latched if mode == 6 and not grid else quality
            assert m.call('ch_live_get', track) == expected
            m.call('ch_live_context', track)
            assert u.mem_read(m.sym['ch_current']+track, 1)[0] == expected
            assert u.mem_read(m.sym['ch_live']+track, 1)[0] == expected
            u.mem_write(0x46c77bea, bytes((70, 8, 48, 100))+b'\0'*8)
            m.call('ch_record_post', stop=0x40000c3c, regs={UC_M68K_REG_D5: track})
            message = int.from_bytes(u.mem_read(m.stack+36, 4), 'big')
            assert m.sym['ch_messages'] <= message < m.sym['ch_messages']+4096
            put(at(2, 1, track), (quality+1) % 8)
            assert bytes(u.mem_read(message+12, 2)) == bytes((expected, track))
            assert bytes(u.mem_read(message, 12)) == bytes((70, 8, 48, 100))+b'\0'*8
            physical_cases += 1
    print(json.dumps({'part_default_writes': writes, 'distinct_contexts': 4, 'pending_context_paths': 4,
                      'dirty_ram_message_pool_and_idempotent_init': 'passed',
                      'physical_key_and_queued_quality_cases': physical_cases,
                      'inheritance_explicit_locks_invalid_values_abi': 'passed',
                      'evidence': 'linked ColdFire', 'hardware_tested': False}))


if __name__ == '__main__':
    main()
