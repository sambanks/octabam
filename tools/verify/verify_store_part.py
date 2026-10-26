#!/usr/bin/env python3
"""Execute shared Part access machine code with distinct UI/engine contexts."""
import re
import json
import subprocess

from midi_machine import Machine, ROOT
from unicorn import UC_HOOK_CODE
from unicorn.m68k_const import *

BANK = 0x400e21e0
STRIDE = 0x9b340
WORK = 0x8ed80
PART = 0x18b2
CS1 = 0x100a4ece
FIELDS = (3, 5, 12, 13, 15, 16, 18, 19)


def symbols():
    raw = subprocess.check_output(['m68k-elf-nm', str(ROOT/'out/platform/runtime/runtime.elf')], text=True)
    return {n: int(a, 16) for a, n in re.findall(r'^([0-9a-f]+) [TtBb] (store_part_\w+)$', raw, re.M)}


def main():
    m = Machine(symbols); u = m.uc
    keys = {row[0] for row in json.loads((ROOT/'out/platform/layout.json').read_text())['units']}
    fields = set()
    if 'MIDI FOLLOW' in keys: fields.update((3,12,13,15))
    if 'MIDI LOOPBACK' in keys: fields.add(12)
    if 'MIDI HARMONY' in keys: fields.update((5,16,18,19))
    assert fields, 'this gate needs a native settings client'
    fields = tuple(sorted(fields))
    def put(a, v, n=1): u.mem_write(a, v.to_bytes(n, 'big'))
    def get(a, n=1): return int.from_bytes(u.mem_read(a, n), 'big')
    def ui(bank, part):
        put(0x46c82456, BANK+bank*STRIDE, 4); put(0x100b14cf, part)
    def call(name, track=0, context=0, field=3, value=0):
        return m.call(name, track, context, regs={UC_M68K_REG_D2: field, UC_M68K_REG_D3: value})

    for bank in range(16):
        for part in range(4):
            ui(bank, part)
            assert call('store_part_ui_context') == bank*4+part
    for ptr, part in ((0, 0), (BANK+1, 0), (BANK+STRIDE*16, 0), (BANK, 4)):
        put(0x46c82456, ptr, 4); put(0x100b14cf, part)
        assert call('store_part_ui_context') == 0xffffffff
    ui(15, 3)
    put(0x80001828, 2); put(0x80001829, 1)
    for track in range(8):
        put(0x8000182a+track,track);put(0x80001832+track,track%4)
        put(0x8000666e+track,15-track);put(0x80006676+track,(track+1)%4)
        assert call('store_part_audio_context',track)==track*4+track%4
        assert call('store_part_midi_context',track)==(15-track)*4+(track+1)%4
        put(0x8000666e+track,255)
        assert call('store_part_midi_context',track)==9
        assert call('store_part_audio_context',track)==track*4+track%4
        put(0x8000182a+track,255)
        assert call('store_part_audio_context',track)==9
    assert call('store_part_midi_context',8)==0xffffffff
    assert call('store_part_audio_context',8)==0xffffffff
    put(0x80001828,255)
    assert call('store_part_midi_context',0)==0xffffffff
    assert call('store_part_audio_context',0)==0xffffffff
    print('  [ok] UI, audio and MIDI contexts stay distinct; independent latches, unlatched fallback and invalid inputs')

    writes = 0
    for bank in (0, 7, 15):
        for part in range(4):
            for current in (True, False):
                ui(bank if current else (bank+1) % 16, part)
                u.mem_write(CS1, b'\xa5'*(PART*4))
                b = BANK+bank*STRIDE
                put(b+0x95048, 0); put(b+0x9b332, 0, 4)
                put(0x100b145e, 0); put(0x100f8598, 0, 4)
                for track in range(8):
                    for field in fields:
                        at = b+WORK+part*PART+0x4e2+track*36+field
                        put(at, 255)
                        value = (bank+part+track+field) % 128
                        assert call('store_part_midi_write', track, bank*4+part, field, value) == 1
                        allowed = {at, b+0x95048, b+0x9b332}
                        if current:
                            allowed |= {CS1+part*PART+0x4e2+track*36+field, 0x100b145e, 0x100f8598}
                        assert all(a in allowed or m.stack-128 <= a and a+n <= m.stack+4
                                   for a,n in m.writes), m.writes
                        assert get(at) == value
                        assert call('store_part_midi_read', track, bank*4+part, field) == value
                        mirror = CS1+part*PART+0x4e2+track*36+field
                        assert get(mirror) == (value if current else 0xa5)
                        writes += 1
                assert get(b+0x95048) == 1 << part
                assert get(b+0x9b332, 4) == 1
                assert get(0x100b145e) == ((1 << part) if current else 0)
                assert get(0x100f8598, 4) == int(current)

    for track, context, field, value in ((8,0,3,1), (0,64,3,1), (0,0,4,1),
                                       (0,0,20,1), (0,0,3,128), (0,0,3,0xffffffff)):
        assert call('store_part_midi_write', track, context, field, value) == 0
        assert all(m.stack-128 <= a and a+n <= m.stack+4 for a,n in m.writes), m.writes
    ui(0,0)
    for field in range(36):
        assert call('store_part_midi_read',0,0,field) == get(BANK+WORK+0x4e2+field)
        if field not in fields:
            assert call('store_part_midi_write',0,0,field,1) == 0
    # Public byte API uses Part-relative addresses and accepts all byte values.
    offset = 0x4e2+fields[0]
    assert m.call('store_part_write',offset,0,regs={UC_M68K_REG_D3:255}) == 1
    assert m.call('store_part_read',offset,0) == 255
    assert m.call('store_part_write',0x18b2,0,regs={UC_M68K_REG_D3:1}) == 0
    assert m.call('store_part_read',0x18b2,0) == 0xffffffff
    assert m.call('store_part_read',0,0) == 0xffffffff
    assert m.call('store_part_read',offset,64) == 0xffffffff
    # A replacement must not accept an edit that the native copy will overwrite.
    put(m.sym['store_part_snapshot_bank'],BANK,4)
    put(m.sym['store_part_snapshot_parts'],1,4)
    before = get(BANK+WORK+offset)
    assert m.call('store_part_write',offset,0,regs={UC_M68K_REG_D3:2}) == 0
    assert get(BANK+WORK+offset) == before
    put(m.sym['store_part_snapshot_bank'],0,4)
    put(m.sym['store_part_snapshot_parts'],0,4)
    regs = {r: 0x12345678 for r in (UC_M68K_REG_D4,UC_M68K_REG_D5,UC_M68K_REG_D6,
                                   UC_M68K_REG_D7,UC_M68K_REG_A0,UC_M68K_REG_A1)}
    regs.update({UC_M68K_REG_D2: 3, UC_M68K_REG_D3: 1})
    m.call('store_part_midi_write',0,0,regs=regs)
    assert all(u.reg_read(r) == v for r,v in regs.items())
    assert m.read_sr() & 0x2700 == 0x2700
    print(f'  [ok] {writes} field writes: bounded working storage, current-bank CS1, native dirty bits, register preservation')

    # The MIDI adapters share the byte reader's saved-register frame. Exercise
    # both exits and all fields, including KEY with an unrelated d2 value.
    preserved = (UC_M68K_REG_D3, UC_M68K_REG_D4, UC_M68K_REG_D5, UC_M68K_REG_D6,
                 UC_M68K_REG_D7, UC_M68K_REG_A0, UC_M68K_REG_A1, UC_M68K_REG_A2,
                 UC_M68K_REG_A3, UC_M68K_REG_A4, UC_M68K_REG_A5, UC_M68K_REG_A6)
    def read(name, track, context, field, expected, budget=None):
        regs = {r: 0x12340000+i for i,r in enumerate(preserved)}
        regs.update({UC_M68K_REG_D1:context, UC_M68K_REG_D2:field})
        count = [0]
        def instruction(uc, pc, size, data):
            if pc != m.done: count[0] += 1
        hook = u.hook_add(UC_HOOK_CODE, instruction)
        try:
            assert m.call(name,track,context,regs=regs) == expected, (name,track,context,field)
        finally:
            u.hook_del(hook)
        assert all(u.reg_read(r) == v for r,v in regs.items()), (name,track,context,field)
        assert u.reg_read(UC_M68K_REG_A7) == m.stack+4
        if budget is not None:
            assert count[0] <= budget, (name,count[0],budget)
    for context in (0,63):
        base = BANK+(context//4)*STRIDE+WORK+(context%4)*PART
        for track in (0,7):
            for field in range(36):
                value = (context+track*36+field)&255
                put(base+0x4e2+track*36+field,value)
                read('store_part_midi_read',track,context,field,value,44)
            read('store_part_midi_key',track,context,0xabcdef01,
                 get(base+0x4e2+track*36+17),42)
    for track,context,field in ((8,0,0),(0xffffffff,0,0),(0,64,0),(0,0xffffffff,0),
                                (0,0,36),(0,0,0xffffffff)):
        read('store_part_midi_read',track,context,field,0xffffffff)
    for track,context in ((8,0),(0xffffffff,0),(0,64),(0,0xffffffff)):
        read('store_part_midi_key',track,context,0xabcdef01,0xffffffff)
    # A selected Part reads the outgoing snapshot; another Part in that bank
    # still reads native data. The fast adapters must keep this distinction.
    put(m.sym['store_part_snapshot_bank'],BANK+15*STRIDE,4)
    put(m.sym['store_part_snapshot_parts'],1<<3,4)
    u.mem_write(m.sym['store_part_snapshot'],b'\x5a'*(4*288))
    for context in (62,63):
        base = BANK+15*STRIDE+WORK+(context%4)*PART
        for track in (0,7):
            put(base+0x4e2+track*36+3,0xa5)
            put(base+0x4e2+track*36+17,0xa5)
            expected = 0x5a if context==63 else 0xa5
            read('store_part_midi_read',track,context,3,expected)
            read('store_part_midi_key',track,context,0xabcdef01,expected)
    put(m.sym['store_part_snapshot_bank'],0,4)
    put(m.sym['store_part_snapshot_parts'],0,4)
    print('  [ok] MIDI read/KEY registers, bounds, snapshot selection and 44/42 instruction ceilings (not hardware cycles)')


if __name__ == '__main__': main()
