#!/usr/bin/env python3
"""Execute the degree codec's real ColdFire instructions against a pitch oracle.

No device files or shared build outputs are modified. Standalone so conversion
can be proven before any persistence/UI hook is installed.
"""
from harmony_midi_machine import HARMONY_SOURCE
import json
import pathlib
import re
import subprocess
import tempfile

from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn.m68k_const import *

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODES = ((0, 2, 4, 5, 7, 9, 11), (0, 2, 3, 5, 7, 9, 10),
         (0, 1, 3, 5, 7, 8, 10), (0, 2, 4, 6, 7, 9, 11),
         (0, 2, 4, 5, 7, 9, 10), (0, 2, 3, 5, 7, 8, 10),
         (0, 1, 3, 5, 6, 8, 10))


def main():
    with tempfile.TemporaryDirectory(prefix='harmony-degree-codec-') as tmp:
        out = pathlib.Path(tmp)
        subprocess.run(['m68k-elf-as', '-mcpu=54455', '-o', str(out/'codec.o'),
                        str(HARMONY_SOURCE/'codec.s')], check=True)
        subprocess.run(['m68k-elf-ld', '-Ttext=0x47000000', '-e', 'hd_encode',
                        '-o', str(out/'codec.elf'), str(out/'codec.o')], check=True)
        subprocess.run(['m68k-elf-objcopy', '-O', 'binary', str(out/'codec.elf'),
                        str(out/'codec.bin')], check=True)
        nm = subprocess.check_output(['m68k-elf-nm', str(out/'codec.elf')], text=True)
        sym = {n: int(a, 16) for a, n in re.findall(r'^([0-9a-f]+) [Tt] (hd_\w+)$', nm, re.M)}
        u = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        u.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
        u.mem_map(0x47000000, 0x10000)
        u.mem_write(0x47000000, (out/'codec.bin').read_bytes())
        done, stack = 0x4700fff0, 0x47008000
        reached = []
        def hook(u, pc, size, data):
            if pc == done:
                reached.append(True)
                u.emu_stop()
        u.hook_add(UC_HOOK_CODE, hook)
        def call(name, value, scale):
            reached.clear()
            u.reg_write(UC_M68K_REG_SR, 0x2700)
            u.reg_write(UC_M68K_REG_A7, stack)
            u.mem_write(stack, done.to_bytes(4, 'big'))
            u.reg_write(UC_M68K_REG_D0, value & 0xffffffff)
            u.reg_write(UC_M68K_REG_D1, scale & 0xffffffff)
            for reg in (UC_M68K_REG_D2, UC_M68K_REG_D3, UC_M68K_REG_D4,
                        UC_M68K_REG_D5, UC_M68K_REG_D6, UC_M68K_REG_D7,
                        UC_M68K_REG_A0):
                u.reg_write(reg, 0x12345678)
            u.emu_start(sym[name], 0, count=10000)
            assert reached, (name, value, scale, hex(u.reg_read(UC_M68K_REG_PC)))
            for reg in (UC_M68K_REG_D2, UC_M68K_REG_D3, UC_M68K_REG_D4,
                        UC_M68K_REG_D5, UC_M68K_REG_D6, UC_M68K_REG_D7,
                        UC_M68K_REG_A0):
                assert u.reg_read(reg) == 0x12345678, (name, reg)
            assert u.reg_read(UC_M68K_REG_D1) == scale & 0xffffffff
            return u.reg_read(UC_M68K_REG_D0)
        encoded = decoded = 0
        for mode, intervals in enumerate(MODES):
            for key in range(12):
                scale = mode*64 + key*4
                valid = [n for n in range(128) if (n-key) % 12 in intervals]
                for note in range(128):
                    snapped = min(valid, key=lambda n: (abs(n-note), n))
                    q, semitone = divmod(snapped-key, 12)
                    expected = (q+1)*7 + intervals.index(semitone)
                    actual = call('hd_encode', note, scale)
                    assert actual == expected, (mode, key, note, actual, expected)
                    assert call('hd_decode', actual, scale) == snapped
                    encoded += 1
                for degree in range(84):
                    q, index = divmod(degree, 7)
                    pitch = 12*(q-1) + key + intervals[index]
                    expected = pitch if 0 <= pitch < 128 else 0xffffffff
                    assert call('hd_decode', degree, scale) == expected, (mode, key, degree)
                    decoded += 1
        for value in range(128):
            assert call('hd_encode', value, -1) == call('hd_encode', value, 0)
        for value in (128, 255, -1, 0x7fffffff):
            assert call('hd_encode', value, 0) == 0xffffffff
        for value in (84, 127, 255, -1):
            assert call('hd_decode', value, 0) == 0xffffffff
        for degree in range(84):
            u.reg_write(UC_M68K_REG_A7, stack)
            u.mem_write(stack, done.to_bytes(4, 'big') + (stack+32).to_bytes(4, 'big')
                        + degree.to_bytes(4, 'big'))
            u.emu_start(sym['hd_format'], 0, count=1000)
            expected = f'{degree%7+1}:{degree//7-2}'.encode()
            assert bytes(u.mem_read(stack+32, len(expected)+1)) == expected+b'\0'
        print(json.dumps({'encode_cases': encoded, 'decode_cases': decoded,
                          'format_cases': 84, 'bounds_fallback_registers': 'passed',
                          'hardware_tested': False}))


if __name__ == '__main__':
    main()
