#!/usr/bin/env python3
"""Execute TEMPO SYNC's installed hook, including beside other linked caves."""
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import toolpath
from remix import registry
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn.m68k_const import (UC_CPU_M68K_CFV4E, UC_M68K_REG_A0,
    UC_M68K_REG_A2, UC_M68K_REG_A7, UC_M68K_REG_D0, UC_M68K_REG_D2,
    UC_M68K_REG_D4, UC_M68K_REG_PC, UC_M68K_REG_SR)

ROOT = Path(__file__).resolve().parents[2]
HOOK, END, STACK = 0x40004d40, 0x40004d4a, 0x40fff000
STOCK = bytes.fromhex('14280dbc488235420038')


def main():
    remix = registry.remix(sys.argv[1] if len(sys.argv) > 1 else 'octabam-bus')
    selected = {m.key: m for m in registry.selected(remix)}
    mode = selected['TEMPO SYNC'].build_values.get('CAVE', 'ON')
    image = (ROOT/'out/mainos_bus.bin').read_bytes()
    installed = image[HOOK-0x40000400:END-0x40000400]
    if mode == 'OFF':
        assert installed == STOCK
        print('[ok] TEMPO SYNC OFF retains the stock FX2 ID writer')
        return
    raw = subprocess.check_output(['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True)
    symbols = {f[2]:int(f[0],16) for line in raw.splitlines()
               if len(f:=line.split()) == 3 and f[1] == 'T'}
    target = symbols['replay' if mode == 'REPLAY' else 'cave']
    assert installed == b'\x4e\xb9'+target.to_bytes(4,'big')+b'\x4e\x71'*2, installed.hex()
    u = Uc(UC_ARCH_M68K,UC_MODE_BIG_ENDIAN)
    u.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
    u.mem_map(0x40000000,0x1000000);u.mem_map(0x80000000,0x10000)
    u.mem_write(0x40000400,image)
    layout = json.loads((ROOT/'out/platform/layout.json').read_text())
    u.mem_write(layout['base'],(ROOT/'out/platform/runtime/runtime.bin').read_bytes())
    u.hook_add(UC_HOOK_CODE,lambda cpu,pc,size,data: cpu.emu_stop() if pc == END else None)
    for track in range(8):
        for effect in (0,6,7,8,9,0x14):
            for note in (24,60,255):
                record = 0x80002000+64*track
                u.mem_write(record,b'\x7a'*64)
                u.mem_write(0x80000ecc+track,bytes([effect]))
                u.mem_write(0x400d64c2+track,bytes([note]))
                before = {UC_M68K_REG_D0:0x12345678,UC_M68K_REG_A0:0x80000110+track,
                          UC_M68K_REG_A2:record,UC_M68K_REG_D4:track}
                u.reg_write(UC_M68K_REG_SR,0x2000);u.reg_write(UC_M68K_REG_A7,STACK)
                u.reg_write(UC_M68K_REG_D2,0xdeadbeef)
                for reg,value in before.items():u.reg_write(reg,value)
                u.emu_start(HOOK,0,count=1000)
                assert u.reg_read(UC_M68K_REG_PC) == END
                expected = bytearray(b'\x7a'*64);expected[56:58]=effect.to_bytes(2,'big')
                if effect == 6 and mode == 'ON':expected[27]=0 if note == 255 else note
                assert bytes(u.mem_read(record,64)) == bytes(expected),(track,effect,note)
                assert u.reg_read(UC_M68K_REG_A7) == STACK
                assert all(u.reg_read(reg) == value for reg,value in before.items())
    print('[ok] installed TEMPO SYNC hook: all eight FX2 records, delay-note guard, release, surrounding bytes and registers')


if __name__ == '__main__':main()
