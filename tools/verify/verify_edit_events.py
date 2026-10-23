#!/usr/bin/env python3
"""Execute EDIT EVENTS with zero, one and three unrelated clients.

Assembles the production sources with synthetic registrations, then substitutes
only client callbacks and native continuation/copy boundaries. Separate module
and image gates verify real clients and native data behavior.
"""
from pathlib import Path
import runpy
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import toolpath
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn.m68k_const import *
def read_sr(uc, probe):
    # Unicorn's host SR accessor changes deferred flags; execute MOVE.W SR,D7
    # in a saved context so observing CCR cannot change the resumed test.
    saved = uc.context_save()
    try:
        uc.emu_start(probe, probe + 2, count=1)
        assert uc.reg_read(UC_M68K_REG_PC) == probe + 2
        return uc.reg_read(UC_M68K_REG_D7) & 0xffff
    finally:
        uc.context_restore(saved)

REGS = [UC_M68K_REG_D0, UC_M68K_REG_D1, UC_M68K_REG_D2, UC_M68K_REG_D3,
        UC_M68K_REG_D4, UC_M68K_REG_D5, UC_M68K_REG_D6, UC_M68K_REG_D7,
        UC_M68K_REG_A0, UC_M68K_REG_A1, UC_M68K_REG_A2, UC_M68K_REG_A3,
        UC_M68K_REG_A4, UC_M68K_REG_A5, UC_M68K_REG_A6]
BASE, STACK, DONE = 0x48000000, 0x47008000, 0x4700fff0


class Fixture:
    def __init__(self, slug, count, work):
        declaration = runpy.run_path(str(ROOT / 'modules' / slug / 'manifest.py'))
        fn = declaration['edit_inc']
        keys = tuple(f'CLIENT {i}' for i in range(count))
        events = declaration['EVENTS']
        fn.__globals__['CLIENTS'] = tuple((k, f'test{i}', events) for i, k in enumerate(keys))
        include = fn(keys)
        assert not any(f'test{i}_' in fn(()) for i in range(count)), 'absent clients must be omitted'
        self.callbacks = {}
        suffixes = ('claim','handle','copy_pre')
        for i in range(count):
            for suffix in suffixes:
                address = 0x47002000 + len(self.callbacks)*16
                self.callbacks[address] = (i,suffix)
                include += f'.set test{i}_{suffix},0x{address:x}\n'
        (work/'remix.inc').write_text(include)
        subprocess.run(['m68k-elf-as','-mcpu=54455','-I',str(work),'-o',str(work/'events.o'),
                        str(ROOT/'modules'/slug/'events.s')],check=True,capture_output=True)
        subprocess.run(['m68k-elf-ld','-Ttext=0x48000000','-o',str(work/'events.elf'),str(work/'events.o')],check=True,capture_output=True)
        subprocess.run(['m68k-elf-objcopy','-O','binary',str(work/'events.elf'),str(work/'events.bin')],check=True)
        nm=subprocess.check_output(['m68k-elf-nm',str(work/'events.elf')],text=True)
        self.sym={f[2]:int(f[0],16) for line in nm.splitlines() if len(f:=line.split())==3}
        self.uc=u=Uc(UC_ARCH_M68K,UC_MODE_BIG_ENDIAN)
        u.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
        for address,size in ((0x40000000,0x100000),(0x46c70000,0x20000),(0x47000000,0x10000),(BASE,0x10000),(0x80000000,0x10000)):
            u.mem_map(address,size)
        u.mem_write(BASE,(work/'events.bin').read_bytes())
        u.mem_write(DONE-16,bytes.fromhex('40c7'))
        self.log=[];self.claims=set();self.arrived=None;self.stop=DONE
        self.native_count=0;self.instructions=0
        u.hook_add(UC_HOOK_CODE,self.hook)

    def ret(self,result=None):
        u=self.uc;sp=u.reg_read(UC_M68K_REG_A7)
        if result is not None:u.reg_write(UC_M68K_REG_D0,result)
        u.reg_write(UC_M68K_REG_PC,int.from_bytes(u.mem_read(sp,4),'big'))
        u.reg_write(UC_M68K_REG_A7,sp+4)

    def hook(self,u,pc,size,data):
        if pc==self.stop:
            self.arrived=pc;u.emu_stop();return
        if BASE <= pc < BASE + 0x10000:
            self.instructions += 1
        if pc in self.callbacks:
            client,event=self.callbacks[pc]
            args=tuple(u.reg_read(r) for r in REGS[:4])
            self.log.append((client,event,args))
            if event=='handle':
                assert [u.reg_read(r) for r in REGS]==self.before, 'handler native registers'
                assert u.reg_read(UC_M68K_REG_A7)==STACK, 'handler native stack'
                assert bytes(u.mem_read(STACK+4,8))==struct.pack('>II',4,7)
                self.ret(91);return
            if event=='copy_pre':
                assert bytes(u.mem_read(0x47005000,4))==b'old!'
            for i,r in enumerate(REGS):u.reg_write(r,0xdead0000+i)
            u.reg_write(UC_M68K_REG_SR,0x271f)
            self.ret(int(client in self.claims) if event=='claim' else 0xabcdef01)
        elif pc==0x40020898:
            self.native_count+=1
            sp=u.reg_read(UC_M68K_REG_A7)
            dst,src,n=struct.unpack('>III',u.mem_read(sp+4,12))
            u.mem_write(dst,bytes(u.mem_read(src,n)))
            u.reg_write(UC_M68K_REG_SR,0x2705)
            self.ret(dst)

    def call(self,name,stop=DONE,values=None,args=()):
        u=self.uc;self.log=[];self.arrived=None;self.stop=stop;self.native_count=0
        self.instructions=0
        self.before=[0x12340000+i for i in range(len(REGS))]
        for i,v in (values or {}).items():self.before[i]=v
        u.reg_write(UC_M68K_REG_SR,0x2700)
        u.reg_write(UC_M68K_REG_A7,STACK)
        for r,v in zip(REGS,self.before):u.reg_write(r,v)
        u.mem_write(STACK,struct.pack('>I',DONE)+b''.join(struct.pack('>I',v) for v in args))
        u.emu_start(self.sym[name],0,count=10000)
        assert self.arrived==stop,(name,hex(u.reg_read(UC_M68K_REG_PC)))

    def preserved(self,changes=None,sp=STACK):
        want=self.before.copy()
        for i,v in (changes or {}).items():want[i]=v
        assert [self.uc.reg_read(r) for r in REGS]==want, (want,[self.uc.reg_read(r) for r in REGS])
        assert self.uc.reg_read(UC_M68K_REG_A7)==sp


def main():
    cases=0;costs={}
    with tempfile.TemporaryDirectory(prefix='octabam-edit-events-') as td:
        work=Path(td)
        for count in (0,1,3):
            f=Fixture('edit-events',count,work);u=f.uc
            u.mem_write(0x47005000,b'old!');u.mem_write(0x47005100,b'new!')
            f.call('ed_copy',args=(0x47005000,0x47005100,4))
            assert [(i,e,a[:3]) for i,e,a in f.log]==[(i,e,(0x47005000,0x47005100,4)) for e in ('copy_pre',) for i in range(count)]
            assert f.native_count==1
            assert bytes(u.mem_read(0x47005000,4))==b'new!'
            f.preserved({0:0x47005000},STACK+4)
            assert read_sr(u,DONE-16)==0x2705, 'native copy condition codes'
            costs[count]={'copy':f.instructions}
            cases+=1
            for claims in [set(),*({i} for i in range(count)),set(range(count))]:
                f.claims=claims
                stop=DONE if claims else 0x400508ec
                f.call('ed_held',stop,args=(4,7))
                owner=min(claims) if claims else None
                assert [(i,e) for i,e,a in f.log]==([(i,'claim') for i in range(owner+1)]+[(owner,'handle')] if claims else [(i,'claim') for i in range(count)])
                assert all(a[:2]==(4,7) for i,e,a in f.log if e=='claim')
                if claims:f.preserved({0:91},STACK+4)
                else:
                    f.preserved(sp=STACK-80)
                    assert read_sr(u,DONE-16)==0x2700, 'native held fallthrough flags'
                    costs[count]['held_fallthrough']=f.instructions
                cases+=1
    assert costs == {
        0: {'copy': 29, 'held_fallthrough': 16},
        1: {'copy': 37, 'held_fallthrough': 28},
        3: {'copy': 53, 'held_fallthrough': 52},
    }, costs
    print('Dispatcher instruction counts (excluding native bodies and synthetic callbacks):', costs)
    print(f'[ok] {cases} assembled cases for EDIT EVENTS: 0/1/3 unrelated clients, register preservation, ordering and native boundaries')

if __name__=='__main__':main()
