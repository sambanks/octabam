#!/usr/bin/env python3
"""Check the installed resident activation before native init hides side effects."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
import toolpath  # noqa: F401,E402
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.m68k_const import *

BASE, STOP, STACK = 0x40000400, 0x4000f938, 0x47008000
REGS = tuple(range(UC_M68K_REG_D0, UC_M68K_REG_D7+1)) + tuple(range(UC_M68K_REG_A0, UC_M68K_REG_A7+1))


def symbols(path):
    rows = [line.split() for line in subprocess.check_output(['m68k-elf-nm', str(path)], text=True).splitlines()]
    return {f[2]:int(f[0],16) for f in rows if len(f)==3 and f[1]!='U'}


def main():
    image = (ROOT/'out/mainos_bus.bin').read_bytes()
    raw = (ROOT/'out/platform/runtime/runtime.bin').read_bytes()
    layout = json.loads((ROOT/'out/platform/layout.json').read_text())
    runtime = symbols(ROOT/'out/platform/runtime/runtime.elf')
    resident = symbols(ROOT/'out/linked/store/storepartentry/u.elf')
    start = resident['store_part_resident_activate']
    original = runtime['store_part_activate']
    site = image[0x40000512-BASE:0x40000518-BASE]
    hk = runtime.get('hk_boot')
    if hk is not None and site == bytes.fromhex('4eb9')+hk.to_bytes(4,'big'):
        # HOOKS's boot bridge (modules/hooks, boot): BOOT TRACE's note, then a jmp to this
        # activation, which returns to the boot (verify_hooks checks the chain).
        body = raw[hk-layout['base']:hk-layout['base']+64]
        assert bytes.fromhex('4ef9')+start.to_bytes(4,'big') in body, 'hk_boot does not end in this activation'
    else:
        assert site == bytes.fromhex('4eb9')+start.to_bytes(4,'big')
    assert BASE <= start < BASE+len(image) and not layout['base'] <= start < layout['top']
    length = runtime['store_part_native_copy']-original
    assert length == 34
    assert image[start-BASE:start-BASE+length] == raw[original-layout['base']:original-layout['base']+length]
    for name in ('store_part_copy_target','store_part_init_target'):
        assert resident[name] == runtime[name]
        assert image[resident[name]-BASE:resident[name]-BASE+4] == bytes(4)
    expected_slots = ((resident['store_part_copy_target'],runtime['store_part_native_copy']),
                      (resident['store_part_init_target'],runtime['store_part_native_init']))

    def run(data, entry, cc, d0):
        u=Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN);u.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
        end=max(BASE+len(image),layout['top'],layout['base']+len(raw))
        u.mem_map(0x40000000,(end-0x40000000+4095)&~4095)
        u.mem_map(0x47000000,0x10000)
        u.mem_write(BASE,data);u.mem_write(layout['base'],raw)
        u.mem_write(STACK-128,b'\xa5'*256);u.mem_write(STACK-4,bytes.fromhex('40000518'))
        u.mem_write(0x4700f000,bytes.fromhex('40c74e71'))
        u.reg_write(UC_M68K_REG_SR,0x2700|cc)
        for i,reg in enumerate(REGS):u.reg_write(reg,(0x13579bdf+i*0x1020304)&0xffffffff)
        u.reg_write(UC_M68K_REG_D0,d0);u.reg_write(UC_M68K_REG_A7,STACK-4)
        writes=[]
        u.hook_add(UC_HOOK_CODE,lambda u,p,n,x:u.emu_stop() if p==STOP else None)
        u.hook_add(UC_HOOK_MEM_WRITE,lambda u,a,p,n,v,x:writes.append((p,n,v&((1<<(8*n))-1))))
        u.emu_start(entry,0,count=20);assert u.reg_read(UC_M68K_REG_PC)==STOP
        regs=tuple(u.reg_read(reg) for reg in REGS)
        # Materialize lazy condition flags using a real MOVE SR instruction.
        u.emu_start(0x4700f000,0x4700f002,count=1)
        assert writes==[(STACK-8,4,d0),*((p,4,v) for p,v in expected_slots)]
        return regs,u.reg_read(UC_M68K_REG_D7)&0xffff,bytes(u.mem_read(STACK-128,256)),writes

    for cc in range(32):
        for d0 in (0,0xffffffff,0x13579bdf):
            assert run(image,start,cc,d0)==run(image,original,cc,d0)
    broken=bytearray(image);broken[start-BASE+7]^=1
    try:run(bytes(broken),start,31,0xffffffff)
    except AssertionError:pass
    else:raise AssertionError('wrong callback publication was accepted')
    result=dict(result='PASS',image_sha256=hashlib.sha256(image).hexdigest(),activation_entry=hex(start),
                comparisons=96,installed_call_verified=True,reference_body_identical=True,
                pointer_corruption_rejected=True,hardware_tested=False,
                limitation='Instruction-level proof only; physical cache and reset behavior unmodeled.')
    (ROOT/'out/verify_midi_part_activation.json').write_text(json.dumps(result,indent=2)+'\n')
    print('[ok] installed resident activation: 96 register/status/stack/publication comparisons; corrupted callback rejected')


if __name__=='__main__':main()
