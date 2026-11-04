#!/usr/bin/env python3
"""Execute two non-musical STORE clients without Harmony or Part fields."""
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tempfile

from verify_store_retained import PoolMachine, symbols, ROOT, BASE, SIZE, OFFSETS


def main():
    subprocess.run([sys.executable, str(ROOT/'modules/store/generate-retained.py'), '--check'], check=True)
    ns = runpy.run_path(str(ROOT/'modules/store/parts.py'))
    retained = ns['_RETAINED']
    clients = {'PROBE A': (7, 0, 13), 'PROBE B': (29, 16367, 17)}
    retained['RETAINED_CLIENTS'].clear()
    retained['RETAINED_CLIENTS'].update(clients)
    keys = set(clients)
    assert ns['layout'](keys)[0] == () and ns['enabled'](keys)
    with tempfile.TemporaryDirectory(prefix='store-retained-clients-') as tmp:
        work = Path(tmp)
        (work/'remix.inc').write_text(ns['part_inc'](keys) + retained['retained_inc'](keys))
        objs = []
        for slug in ('part', 'part-copy', 'retained', 'retained-copy', 'retained-clients'):
            obj = work/(slug+'.o'); objs.append(str(obj))
            subprocess.run(['m68k-elf-as', '-mcpu=54455', '-I', str(work), '-o', str(obj),
                            str(ROOT/f'modules/store/{slug}.s')], check=True)
        elf, binary = work/'clients.elf', work/'clients.bin'
        subprocess.run(['m68k-elf-ld', '-Ttext=0x48000000', '-e', 'store_retained_read',
                        '--defsym=store_part_copy_target=0x47002000',
                        '--defsym=store_part_init_target=0x47002004',
                        '-o', str(elf), *objs], check=True)
        subprocess.run(['m68k-elf-objcopy', '-O', 'binary', str(elf), str(binary)], check=True)
        rows = subprocess.check_output(['m68k-elf-nm', str(elf)], text=True)
        syms = {name: int(at, 16) for at, name in re.findall(r'^([0-9a-f]+) [A-Za-z] (store_\w+)$', rows, re.M)}
        m = PoolMachine(symbols, instruction_budget=30_000_000); u = m.uc
        u.mem_map(0x48000000, 0x10000); u.mem_write(0x48000000, binary.read_bytes()); m.sym.update(syms)
        m.call('store_part_activate', stop=0x4000f938)
        assert int.from_bytes(u.mem_read(0x47002000, 4), 'big') == syms['store_part_native_copy']
        src, dst = 0x46010000, 0x46018000
        seed = bytes([0x5a])*SIZE; u.mem_write(BASE, seed)
        expected = bytearray(seed)
        for client, offset, length in clients.values():
            payload = bytes(range(client, client+length)); u.mem_write(src, payload)
            assert m.c('store_retained_write', src, client, 0, length) == 1
            for at, value in zip(OFFSETS[offset:offset+length], payload): expected[at] = value
            assert bytes(u.mem_read(BASE, SIZE)) == bytes(expected), 'client wrote outside its reservation'
            assert m.c('store_retained_read', dst, client, 0, length) == 1
            assert bytes(u.mem_read(dst, length)) == payload
            for start, size in ((length, 1), (length+1, 0), (length-1, 2), (0xffffffff, 1), (1, 0xffffffff)):
                u.mem_write(dst, b'\xa5'*32)
                assert m.c('store_retained_write', src, client, start, size) == 0
                assert m.c('store_retained_read', dst, client, start, size) == 0
                assert bytes(u.mem_read(BASE, SIZE)) == bytes(expected)
                assert bytes(u.mem_read(dst, 32)) == b'\xa5'*32
            assert m.c('store_retained_write', src, client, length, 0) == 1
            assert m.c('store_retained_read', dst, client, length, 0) == 1
        for absent in (0, 8, 0xffffffff):
            u.mem_write(dst, b'\xa5'*32)
            assert m.c('store_retained_write', src, absent, 0, 1) == 0
            assert m.c('store_retained_read', dst, absent, 0, 1) == 0
            assert bytes(u.mem_read(BASE, SIZE)) == bytes(expected)
            assert bytes(u.mem_read(dst, 32)) == b'\xa5'*32
        # Native copy protection is available even without a Part-window client.
        u.mem_write(src, b'\x33'*32)
        m.c('store_part_native_copy', BASE+OFFSETS[0]-30, src, 32)
        assert u.mem_read(BASE+OFFSETS[0]-30, 30) == b'\x33'*30
        assert u.mem_read(BASE+OFFSETS[0], 2) == bytes(expected[OFFSETS[0]:OFFSETS[0]+2])
        m.c('store_part_native_copy', dst, BASE+OFFSETS[0]-30, 32)
        assert u.mem_read(dst, 32) == b'\x33'*30+b'\xff\xff'
    print('[ok] two non-Harmony clients, disjoint bounds, absent IDs, overflow refusal, and retained-only native copy activation')


if __name__ == '__main__':
    main()
