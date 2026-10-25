#!/usr/bin/env python3
"""Native MIDI Part fixture and CPU harness; callers supply their module symbols.

No firmware is bundled. The memory fixture seeds native Part defaults; it is
not a generic CPU-only fixture.
"""
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




def read_sr(uc, probe):
    """Read supervisor SR at a stopped boundary without changing CPU state.

    The caller reserves a MOVE.W SR,D7 instruction at probe and allows its code
    hooks to execute it. Unicorn 2.1.4's host SR read overwrites cc_op before
    evaluating pending flags; even reading only the interrupt mask can change
    a resumed branch. Guest capture followed by context restore avoids that.
    """
    if bytes(uc.mem_read(probe, 2)) != bytes.fromhex('40c7'):
        raise ValueError('SR probe must contain MOVE.W SR,D7')
    saved = uc.context_save()
    try:
        uc.emu_start(probe, probe + 2, count=1)
        if uc.reg_read(UC_M68K_REG_PC) != probe + 2:
            raise RuntimeError('SR capture did not complete')
        return uc.reg_read(UC_M68K_REG_D7) & 0xffff
    finally:
        uc.context_restore(saved)


def dram_map_size(layout):
    """Cover stock RAM and the selected runtime, staging and retained state."""
    end = max(0x41000000, layout['top'], layout['stage_end'], layout['ceiling'])
    return (end - 0x40000000 + 4095) & ~4095



class Machine:
    def __init__(self, symbol_loader=None, artifact_root=None):
        if symbol_loader is None:
            def symbol_loader():
                raw=subprocess.check_output(['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True)
                return {name:int(address,16) for address,name in re.findall(r'^([0-9a-f]+) [TtBb] ((?:bf|mh|hd|ms|ch)_\w+)$',raw,re.M)}
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
        self.sr_probe=self.done-16
        u.mem_write(self.sr_probe,bytes.fromhex('40c7'))  # MOVE.W SR,D7
        self.stops={self.done}; self.arrival=None;self.writes=[]
        u.hook_add(UC_HOOK_CODE,self.stop)
        u.hook_add(UC_HOOK_MEM_WRITE,lambda u,a,p,n,v,x:self.writes.append((p,n)))
        # A native fresh Part fixture, with UI and all engine tracks on bank 0
        # Part 0. Tests may move either context independently.
        u.mem_write(0x46c82456,(0x400e21e0).to_bytes(4,'big'))
        follow_defaults = 'bf_source_get' in self.sym
        for p in range(4):
            for t in range(8):
                u.mem_write(0x400e21e0+0x8ed80+p*0x18b2+0x4e2+t*36+13,
                            b'\x23' if follow_defaults else b'\x03')
                u.mem_write(0x400e21e0+0x8ed80+p*0x18b2+0x4e2+t*36+15,
                            b'\x03' if follow_defaults else b'\x02')
        if 'mh_defaults' in self.sym:self.call('mh_defaults',stop=0x40025ace)
    def part_address(self,track,field):
        bank=int.from_bytes(self.uc.mem_read(0x46c82456,4),'big')
        part=self.uc.mem_read(0x100b14cf,1)[0]
        return bank+0x8ed80+part*0x18b2+0x4e2+track*36+field
    def follow_write(self,field,data,track=0):
        """Seed the Follow fields in native Parts for module gates."""
        slots={'source':3,'mode':15,'response':12,'fixed':13,'offset':13,'home':15}
        for t,value in enumerate(data,track):
            address=self.part_address(t,slots[field])
            old=self.uc.mem_read(address,1)[0]
            if field=='mode':value=(old&0x0f)|((value&3)<<4)
            elif field=='response':value=(old&~2)|((value&1)<<1)
            elif field=='fixed':value=(old&0xf0)|(value&15)
            elif field=='offset':value=(old&0x0f)|(((value+2)&7)<<4)
            elif field=='home':value=(old&0xf0)|(value&15)
            self.uc.mem_write(address,bytes((value,)))
    def follow_read(self,field,count=8,track=0):
        slots={'source':3,'mode':15,'response':12,'fixed':13,'offset':13,'home':15}
        values=[]
        for t in range(track,track+count):
            value=self.uc.mem_read(self.part_address(t,slots[field]),1)[0]
            if field=='mode':value=(value>>4)&3
            elif field=='response':value=(value>>1)&1
            elif field in ('fixed','home'):value&=15
            elif field=='offset':value=(((value>>4)&7)-2)&255
            values.append(value)
        return bytes(values)
    def set_key(self,track,value):
        self.uc.mem_write(self.part_address(track,17),bytes((value,)))
        self.uc.mem_write(0x46c76df1+68*track,bytes((value,)))
    def stop(self,u,p,n,x):
        if p in self.stops:self.arrival=p;u.emu_stop()
    def read_sr(self):
        return read_sr(self.uc,self.sr_probe)
    def call(self,name,d0=0,d1=0,a0=None,stop=None,regs=None):
        u=self.uc;self.stops={stop or self.done};self.arrival=None;self.writes=[]
        u.reg_write(UC_M68K_REG_SR,self.initial_sr);u.reg_write(UC_M68K_REG_A7,self.stack)
        u.mem_write(self.stack,self.done.to_bytes(4,'big'))
        u.reg_write(UC_M68K_REG_D0,d0);u.reg_write(UC_M68K_REG_D1,d1)
        if a0 is not None:u.reg_write(UC_M68K_REG_A0,a0)
        for r,v in (regs or {}).items():u.reg_write(r,v)
        u.emu_start(self.sym[name],0,count=self.instruction_limit(name))
        assert self.arrival in self.stops,(name,hex(u.reg_read(UC_M68K_REG_PC)))
        return u.reg_read(UC_M68K_REG_D0)
    def instruction_limit(self,name):
        return 10000000 if 'hd_set' in self.sym else 20000
