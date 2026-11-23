#!/usr/bin/env python3
"""Verify the built ColdFire control transport and source setup ABI.

Requires the selected firmware's runtime and Unicorn from the repo venv.
Instruction counts are diagnostics, not hardware timing measurements.
"""
import ctypes as ct
import pathlib
import struct
import subprocess
import sys

from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn.m68k_const import (UC_CPU_M68K_CFV4E, UC_M68K_REG_A7,
                               UC_M68K_REG_D0, UC_M68K_REG_D1, UC_M68K_REG_D2, UC_M68K_REG_D6, UC_M68K_REG_A0,
                               UC_M68K_REG_A1, UC_M68K_REG_A2, UC_M68K_REG_A3, UC_M68K_REG_PC, UC_M68K_REG_SR)

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/harness'))


def main():
    runtime = ROOT / 'out/platform/runtime'
    nm = subprocess.check_output(['m68k-elf-nm', str(runtime / 'runtime.elf')], text=True)
    symbols = {f[2]: int(f[0], 16) for f in (line.split() for line in nm.splitlines())
               if len(f) == 3}
    headers = subprocess.check_output(
        ['m68k-elf-objdump', '-h', str(runtime / 'runtime.elf')], text=True)
    base = int(next(line.split()[3] for line in headers.splitlines()
                    if len(line.split()) > 3 and line.split()[1] == '.text'), 16)
    data = (runtime / 'runtime.bin').read_bytes()
    uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
    uc.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
    mapped = base & ~4095
    uc.mem_map(mapped, (base - mapped + len(data) + 4095) & ~4095)
    uc.mem_write(base, data)
    uc.mem_map(0x10000, 0x20000)
    stop, stack = 0x10000, 0x20000
    uc.reg_write(UC_M68K_REG_SR, 0x2000)
    instructions = [0]

    def count(_uc, _address, _size, _data):
        instructions[0] += 1
    uc.hook_add(UC_HOOK_CODE, count)

    def call(name, *args):
        uc.reg_write(UC_M68K_REG_A7, stack)
        uc.mem_write(stack, struct.pack('>' + 'I' * (1 + len(args)), stop, *args))
        uc.emu_start(symbols[name], stop, count=100000)
        assert uc.reg_read(UC_M68K_REG_PC) == stop, name
        assert uc.reg_read(UC_M68K_REG_A7) == stack + 4, (name, 'stack imbalance')
        return ct.c_int32(uc.reg_read(UC_M68K_REG_D0)).value

    # The row, the signature and the chooser's commits are MACHINES's (modules/machines/verify.py);
    # ANALOG BD's row is the word MACHINES gives it.
    ab_row = struct.unpack('>I', data[symbols['ab_mc_row'] - base:symbols['ab_mc_row'] - base + 4])[0]
    assert ab_row >= 5, ab_row
    print(f'PASS ANALOG BD is MACHINES client row {ab_row}')

    for value,label in ((0,b'OFF'),(1,b'500'),(64,b'ORIG'),(127,b'18000')):
        uc.mem_write(0x24000,bytes(16))
        call('ab_lpf_fmt',0x24000,value)
        assert bytes(uc.mem_read(0x24000,len(label)+1))==label+b'\0'
    print('PASS native LPF formatter: OFF, Hz, ORIG')
    # Exercise the real renderer ABI at every frame split. The final
    # control record must occupy exactly the old two-segment FLEX span.
    for address,size in ((0x100b1000,0x1000),(0x46104000,0x1000),
                         (0x46c82000,0x1000),(0x80000000,0x10000),
                         (0x42000000,0xa0000)):
        uc.mem_map(address,size)
    bank=0x42000000; livepart=bank+0x8ed80; cursor=0x80001c90
    uc.mem_write(0x46c82456,struct.pack('>I',bank))
    # The track shortcut must only intercept a signed Analog BD audio track.
    for part_index in range(4):
        selected_part=livepart+6322*part_index
        uc.mem_write(0x100b14cf,bytes([part_index]))
        for track in range(8):
            uc.mem_write(0x100b14cc,bytes([track]))
            for machine,signature,midi,expected in (
                    (1,b'AB\x01',0,1),(1,b'AB\x01',1,0),
                    (1,b'AB\x00',0,0),(1,b'\0\0\0',0,0),
                    (2,b'AB\x01',0,0),(0,b'AB\x01',0,0)):
                uc.mem_write(selected_part+0x22+track,bytes([machine]))
                uc.mem_write(selected_part+60+30*track,signature)
                uc.mem_write(0x80000015,bytes([midi]))
                assert call('ab_selected_source')==expected, (part_index,track,machine,signature,midi)
    uc.mem_write(0x100b14cf,b'\0')
    uc.mem_write(0x100b14cc,b'\0')
    uc.mem_write(0x80000015,b'\0')
    print('PASS track shortcut predicate: all parts/tracks, ordinary machines and MIDI')
    for address in (0x40058000,0x40079000,0x460e7000):
        uc.mem_map(address,0x1000)
    def stop_shortcut(_uc,address,_size,_data):
        if address in (symbols['ab_engine_open'],0x400791f6):
            _uc.emu_stop()
    # Observe TST flags through a branch, not Unicorn's lazy SR readout.
    # beq +4; moveq #0,d2; bra +2; moveq #1,d2; nop
    uc.mem_write(0x400791ec,bytes.fromhex('67047400600274014e71'))
    hook=uc.hook_add(UC_HOOK_CODE,stop_shortcut)
    registers=(UC_M68K_REG_D0,UC_M68K_REG_D1,UC_M68K_REG_A0,
               UC_M68K_REG_A1,UC_M68K_REG_A2)
    for signed in (False,True):
        uc.mem_write(livepart+0x22,b'\x01')
        uc.mem_write(livepart+60,b'AB\x01' if signed else b'\0\0\0')
        for pool in (0,0x12345678):
            uc.mem_write(0x460e70e0,struct.pack('>I',pool))
            for i,reg in enumerate(registers):uc.reg_write(reg,0x12340000+i)
            uc.reg_write(UC_M68K_REG_A7,stack)
            uc.emu_start(symbols['ab_pool_open'],stop,count=10000)
            assert uc.reg_read(UC_M68K_REG_PC)==(symbols['ab_engine_open'] if signed else 0x400791f6)
            assert uc.reg_read(UC_M68K_REG_A7)==stack-(0 if signed else 4)
            for i,reg in enumerate(registers):assert uc.reg_read(reg)==0x12340000+i
            if not signed:
                assert int.from_bytes(uc.mem_read(stack-4,4),'big')==0x12340004
                assert uc.reg_read(UC_M68K_REG_D2)==int(pool==0)
    uc.hook_del(hook)
    print('PASS track shortcut ABI: stock continuation, flags, stack and registers')

    uc.mem_map(0x40077000,0x1000)
    def stop_title(_uc,address,_size,_data):
        if address in (0x40077b62,0x40077b70): _uc.emu_stop()
    hook=uc.hook_add(UC_HOOK_CODE,stop_title)
    for signed in (False,True):
        uc.mem_write(livepart+60,b'AB\x01' if signed else b'\0\0\0')
        for row in range(ab_row+2):
            uc.reg_write(UC_M68K_REG_D0,row)
            uc.reg_write(UC_M68K_REG_A0,0x400334d8)
            uc.reg_write(UC_M68K_REG_A7,stack)
            uc.emu_start(symbols['ab_pool_title'],stop,count=10000)
            expected=0x40077b62 if row<2 or (row==ab_row and signed) else 0x40077b70
            assert uc.reg_read(UC_M68K_REG_PC)==expected,(row,signed)
            assert uc.reg_read(UC_M68K_REG_D0)==row
            assert uc.reg_read(UC_M68K_REG_D6)==1
            assert uc.reg_read(UC_M68K_REG_A0)==0x400334d8
            assert uc.reg_read(UC_M68K_REG_A7)==stack
    uc.hook_del(hook)
    print('PASS pool header: stock chevrons for STATIC/FLEX and signed Analog BD; other rows unchanged')
    uc.mem_map(0x4003a000,0x1000)
    def stop_editor(_uc,address,_size,_data):
        if address in (0x4003a536,0x4003a624): _uc.emu_stop()
    hook=uc.hook_add(UC_HOOK_CODE,stop_editor)
    for machine in range(ab_row+1):
        for knob in range(6):
            uc.reg_write(UC_M68K_REG_D2,machine)
            uc.reg_write(UC_M68K_REG_A3,knob)
            uc.reg_write(UC_M68K_REG_A7,stack)
            uc.emu_start(symbols['mc_setup_edit6'],stop,count=1000)   # MACHINES's editor, ANALOG BD's slot flag
            assert uc.reg_read(UC_M68K_REG_PC)==(0x4003a624 if machine==ab_row and knob==0 else 0x4003a536)
            assert uc.reg_read(UC_M68K_REG_A7)==stack
    uc.hook_del(hook)
    print('PASS hidden model editor: Analog BD encoder A ignored; other knobs/machines retain stock path')


    uc.mem_write(livepart+0x22,b'\x01')
    uc.mem_write(livepart+60,b'AB\x01')
    uc.mem_write(0x800062a4,struct.pack('>I',0x26000))
    uc.mem_write(0x800062a8,struct.pack('>I',0x27000))
    knobs=[64,32,64,32,64,99,1,100,0,64,127,0]
    for track in range(8):
        uc.mem_write(livepart+0x22+track,b'\x01')
        uc.mem_write(livepart+60+30*track,b'AB\x01')
    for track in range(8):
      for ping in (0,1):
        cursor=0x80001c90+ping*0xa80+336*track
        for model in (0,1):
            knobs[6]=model
            uc.mem_write(0x27000,b''.join(struct.pack('>H',v<<8) for v in knobs[:6]))
            uc.mem_write(0x80000830+72*track,bytes(knobs[6:]))
            for split in range(16):
                uc.mem_write(cursor,bytes([0xa5])*200)
                uc.mem_write(0x80001c80,struct.pack('>I',cursor))
                uc.mem_write(0x46104d0c+track,b'\x10')
                call('ab_render',track,ping,0,split)
                call('ab_render',track,ping,split,16)
                expected=struct.pack('>4I12H',0xab090000,0x09090001,0,0,*knobs)
                assert bytes(uc.mem_read(cursor,len(expected)))==expected,split
                assert int.from_bytes(uc.mem_read(0x80001c80,4),'big')==cursor+160
                assert bytes(uc.mem_read(cursor+160,40))==bytes([0xa5])*40
    print('PASS DSP control record: all 8 tracks, both ping buffers, all 16 trigger offsets, knobs and next-record boundary')

    # Engine list commits update Part, SRAM, live byte and dirty flags together.
    for address,size in ((0x100a4000,0x9000),(0x100f8000,0x1000),
                         (0x40027000,0x1000),(0x4004d000,0x1000),
                         (0x400d3000,0x1000),(0x400d5000,0x1000)):
        uc.mem_map(address,size)
    for address in (0x40027e00,0x4004d948):uc.mem_write(address,bytes.fromhex('4e75'))
    for track in range(8):
        uc.mem_write(0x100b14cc,bytes([track]))
        for name,value in (('engine_bank',bank),('engine_part',0),('engine_track',track)):
            uc.mem_write(symbols[name],struct.pack('>I',value))
        for model in (1,0):
            at=0x1e0+30*track
            call('ab_engine_select',model)
            for address in (livepart+at,0x100a4ece+at,0x80000830+72*track):
                assert bytes(uc.mem_read(address,1))==bytes([model]),(track,model,hex(address))
        call('ab_engine_select',2)
        assert bytes(uc.mem_read(livepart+at,1))==b'\0'
        uc.mem_write(0x100b14cc,bytes([(track+1)%8]))
        call('ab_engine_select',1)
        assert bytes(uc.mem_read(livepart+at,1))==b'\0','stale browser changed another track'
    print('PASS engine browser commit: both models, all tracks, mirrors, invalid/stale selection')


if __name__ == '__main__':
    main()
