#!/usr/bin/env python3
"""Shared machine-code harness for MIDI module verification. No firmware is bundled."""
import json
import pathlib
import re
import subprocess
import sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
import toolpath
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.m68k_const import *




def dram_map_size(layout):
    """Cover stock RAM and the selected runtime, staging and retained state."""
    end = max(0x41000000, layout['top'], layout['stage_end'], layout['ceiling'])
    return (end - 0x40000000 + 4095) & ~4095



def symbols():
    raw = subprocess.check_output(['m68k-elf-nm', str(ROOT/'out/platform/runtime/runtime.elf')], text=True)
    return {n:int(a,16) for a,n in re.findall(r'^([0-9a-f]+) [Tt] ((?:mp|lb)_\w+)$',raw,re.M)}

class Machine:
    def __init__(self, symbol_loader=symbols, artifact_root=None):
        self.sym=symbol_loader(); self.uc=Uc(UC_ARCH_M68K,UC_MODE_BIG_ENDIAN)
        out = artifact_root or ROOT/'out'
        layout = json.loads((out/'platform/layout.json').read_text())
        self.initial_sr = 0x2700
        u=self.uc; u.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
        # The combined image's linked BSS can extend beyond the former 16 MiB
        # test map. Cover the declared runtime/retained reservation, as the
        # full firmware port does, instead of faulting on valid state writes.
        dram_size = dram_map_size(layout)
        for a,n in [(0x40000000,dram_size),(0x46000000,0x200000),(0x47000000,0x10000),(0x46c70000,0x20000),(0x10000000,0x200000),(0x80000000,0x10000)]:u.mem_map(a,n)
        u.mem_write(0x40000400,(out/'mainos_bus.bin').read_bytes())
        self.base=layout['base']
        u.mem_write(self.base,(out/'platform/runtime/runtime.bin').read_bytes())
        self.stack=0x47008000;self.done=0x4700fff0;self.scratch=0x47001000
        self.stops={self.done}; self.arrival=None;self.writes=[]
        u.hook_add(UC_HOOK_CODE,self.stop)
        u.hook_add(UC_HOOK_MEM_WRITE,lambda u,a,p,n,v,x:self.writes.append((p,n)))
        # A native fresh Part fixture, with UI and all engine tracks on bank 0
        # Part 0. Tests may move either context independently.
        u.mem_write(0x46c82456,(0x400e21e0).to_bytes(4,'big'))
        for p in range(4):
            for t in range(8):
                u.mem_write(0x400e21e0+0x8ed80+p*0x18b2+0x4e2+t*36+13,b'\x03')
                u.mem_write(0x400e21e0+0x8ed80+p*0x18b2+0x4e2+t*36+15,b'\x02')
    def part_address(self,track,field):
        bank=int.from_bytes(self.uc.mem_read(0x46c82456,4),'big')
        part=self.uc.mem_read(0x100b14cf,1)[0]
        return bank+0x8ed80+part*0x18b2+0x4e2+track*36+field
    def stop(self,u,p,n,x):
        if p in self.stops:self.arrival=p;u.emu_stop()
    def call(self,name,d0=0,d1=0,a0=None,stop=None,regs=None):
        u=self.uc;self.stops={stop or self.done};self.arrival=None;self.writes=[]
        u.reg_write(UC_M68K_REG_SR,self.initial_sr);u.reg_write(UC_M68K_REG_A7,self.stack)
        u.mem_write(self.stack,self.done.to_bytes(4,'big'))
        u.reg_write(UC_M68K_REG_D0,d0);u.reg_write(UC_M68K_REG_D1,d1)
        if a0 is not None:u.reg_write(UC_M68K_REG_A0,a0)
        for r,v in (regs or {}).items():u.reg_write(r,v)
        u.emu_start(self.sym[name],0,count=20000)
        assert self.arrival in self.stops,(name,hex(u.reg_read(UC_M68K_REG_PC)))
        return u.reg_read(UC_M68K_REG_D0)
