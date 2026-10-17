#!/usr/bin/env python3
"""Execute shared Part access machine code with distinct UI/engine contexts."""
import re
import subprocess

from midi_machine import Machine, ROOT
from unicorn.m68k_const import *

BANK = 0x400e21e0
STRIDE = 0x9b340
WORK = 0x8ed80
PART = 0x18b2
CS1 = 0x100a4ece
FIELDS = (3, 5, 12, 13, 15, 16, 18, 19)


def symbols():
    raw = subprocess.check_output(['m68k-elf-nm', str(ROOT/'out/platform/runtime/runtime.elf')], text=True)
    return {n: int(a, 16) for a, n in re.findall(r'^([0-9a-f]+) [Tt] (mp_\w+)$', raw, re.M)}


def main():
    m = Machine(symbols); u = m.uc
    def put(a, v, n=1): u.mem_write(a, v.to_bytes(n, 'big'))
    def get(a, n=1): return int.from_bytes(u.mem_read(a, n), 'big')
    def ui(bank, part):
        put(0x46c82456, BANK+bank*STRIDE, 4); put(0x100b14cf, part)
    def call(name, track=0, context=0, field=3, value=0):
        return m.call(name, track, context, regs={UC_M68K_REG_D2: field, UC_M68K_REG_D3: value})

    for bank in range(16):
        for part in range(4):
            ui(bank, part)
            assert call('mp_ui_context') == bank*4+part
    for ptr, part in ((0, 0), (BANK+1, 0), (BANK+STRIDE*16, 0), (BANK, 4)):
        put(0x46c82456, ptr, 4); put(0x100b14cf, part)
        assert call('mp_ui_context') == 0xffffffff
    ui(15, 3)
    put(0x80001828, 2); put(0x80001829, 1)
    for track in range(8):
        put(0x8000182a+track, track); put(0x80001832+track, track % 4)
        assert call('mp_play_context', track) == track*4+track % 4
        put(0x8000182a+track, 255)
        assert call('mp_play_context', track) == 9
    assert call('mp_play_context', 8) == 0xffffffff
    put(0x80001828, 255)
    assert call('mp_play_context', 0) == 0xffffffff
    print('  [ok] UI and per-track engine contexts stay distinct; unlatched fallback and invalid inputs')

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
                    for field in FIELDS:
                        at = b+WORK+part*PART+0x4e2+track*36+field
                        put(at, 255)
                        value = (bank+part+track+field) % 128
                        assert call('mp_write', track, bank*4+part, field, value) == 1
                        allowed = {at, b+0x95048, b+0x9b332}
                        if current:
                            allowed |= {CS1+part*PART+0x4e2+track*36+field, 0x100b145e, 0x100f8598}
                        assert all(a in allowed or m.stack-128 <= a and a+n <= m.stack+4
                                   for a,n in m.writes), m.writes
                        assert get(at) == value
                        assert call('mp_read', track, bank*4+part, field) == value
                        mirror = CS1+part*PART+0x4e2+track*36+field
                        assert get(mirror) == (value if current else 0xa5)
                        writes += 1
                assert get(b+0x95048) == 1 << part
                assert get(b+0x9b332, 4) == 1
                assert get(0x100b145e) == ((1 << part) if current else 0)
                assert get(0x100f8598, 4) == int(current)

    for track, context, field, value in ((8,0,3,1), (0,64,3,1), (0,0,4,1),
                                       (0,0,20,1), (0,0,3,128), (0,0,3,0xffffffff)):
        assert call('mp_write', track, context, field, value) == 0
        assert all(m.stack-128 <= a and a+n <= m.stack+4 for a,n in m.writes), m.writes
    ui(0,0)
    for field in range(36):
        if field not in FIELDS:
            assert call('mp_read',0,0,field) == 0xffffffff
    regs = {r: 0x12345678 for r in (UC_M68K_REG_D4,UC_M68K_REG_D5,UC_M68K_REG_D6,
                                   UC_M68K_REG_D7,UC_M68K_REG_A0,UC_M68K_REG_A1)}
    regs.update({UC_M68K_REG_D2: 3, UC_M68K_REG_D3: 1})
    m.call('mp_write',0,0,regs=regs)
    assert all(u.reg_read(r) == v for r,v in regs.items())
    assert u.reg_read(UC_M68K_REG_SR) & 0x2700 == 0x2700
    print(f'  [ok] {writes} field writes: bounded working storage, current-bank CS1, native dirty bits, register preservation')


if __name__ == '__main__': main()
