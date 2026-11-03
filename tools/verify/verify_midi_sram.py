#!/usr/bin/env python3
"""Execute the protected pool and native operations in the linked image.

The small machine gate stubs only UI notifications (no storage/copy/clear
routine). The full-port gate separately runs the real firmware and RTOS.
"""
import json
import random
import re
import subprocess
from unicorn import UC_HOOK_MEM_WRITE
from unicorn.m68k_const import *
from midi_machine import Machine, ROOT

BASE, B, SIZE = 0x1001614e, 0x400e21e0, 16*0x8ed8
OFFSETS = tuple(p*0x8ed8+0x4900+t*0x8b0+s*32+f
                for p in range(16) for t in range(8) for s in range(64) for f in (30,31))

def symbols():
    text=subprocess.check_output(['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True)
    return {n:int(a,16) for a,n in re.findall(r'^([0-9a-f]+) [A-Za-z] (\w+)$',text,re.M)}

class PoolMachine(Machine):
    def c(self, name, *args):
        self.uc.mem_write(self.stack+4,b''.join((a&0xffffffff).to_bytes(4,'big') for a in args))
        try:return self.call(name)
        except Exception:
            print(name,hex(self.uc.reg_read(UC_M68K_REG_PC)),flush=True)
            raise

def main():
    m=PoolMachine(symbols, instruction_budget=30_000_000);u=m.uc;m.call('store_part_activate',stop=0x4000f938)
    rng=random.Random(667)
    native=bytearray(rng.randbytes(SIZE))
    for o in OFFSETS:native[o]=255
    pool=rng.randbytes(len(OFFSETS));seed=bytearray(native)
    for o,v in zip(OFFSETS,pool):seed[o]=v
    u.mem_write(BASE,bytes(seed));u.mem_write(B,bytes(native))
    src=0x47001000
    # Staging is separate from the stack and large enough for every pool byte.
    src=0x46010000;dst=0x46018000
    u.mem_write(src,pool)
    assert m.c('rp_write',src,0,len(pool))==1
    assert bytes(u.mem_read(BASE,SIZE))==bytes(seed)
    assert m.c('rp_read',dst,0,len(pool))==1
    assert bytes(u.mem_read(dst,len(pool)))==pool
    for offset,length in ((16384,1),(16385,0),(16380,5),(0xffffffff,2),(1,0xffffffff)):
        before=bytes(u.mem_read(BASE,SIZE))
        assert m.c('rp_write',src,offset,length)==0
        assert m.c('rp_read',dst,offset,length)==0
        assert bytes(u.mem_read(BASE,SIZE))==before
    pads={BASE+o for o in OFFSETS};protected=False;writes=[]
    def watch(u,access,a,n,v,data):
        if protected and any(a+i in pads for i in range(n)):
            writes.append((hex(u.reg_read(UC_M68K_REG_PC)),hex(a),n))
    u.hook_add(UC_HOOK_MEM_WRITE,watch)
    cases=0
    # Real global native boundary, including one-byte/unaligned copies and
    # whole-bank/track/step copies. Every non-pool destination byte is native.
    m.sym['native_copy']=0x40020898
    for offset,length in ((0,SIZE),(15*0x8ed8,0x8ed8),(0x48d0,0x8b0),
                          (0x491c,8),(0x491e,1),(0x491f,3),(0x4900,32),(0,0)):
        u.mem_write(BASE,bytes(seed));u.mem_write(B,bytes(native))
        protected=True;m.c('native_copy',BASE+offset,B+offset,length);protected=False
        assert not writes,writes[:4]
        assert bytes(u.mem_read(BASE,SIZE))==bytes(seed)
        u.mem_write(B,b'\xa5'*SIZE)
        protected=True;m.c('native_copy',B+offset,BASE+offset,length);protected=False
        assert not writes,writes[:4]
        assert bytes(u.mem_read(B+offset,length))==bytes(native[offset:offset+length])
        cases+=1
    # A copy beginning before the pattern area still crosses pool slots.
    # This catches dispatch fast paths that inspect only the starting pointer.
    prefix=32;length=SIZE+prefix
    u.mem_write(BASE-prefix,b'\x73'*prefix+bytes(seed))
    u.mem_write(B-prefix,b'\x73'*prefix+bytes(native))
    protected=True;m.c('native_copy',BASE-prefix,B-prefix,length);protected=False
    assert not writes,writes[:4]
    assert bytes(u.mem_read(BASE-prefix,length))==b'\x73'*prefix+bytes(seed)
    u.mem_write(B-prefix,b'\xa5'*length)
    m.c('native_copy',B-prefix,BASE-prefix,length)
    assert bytes(u.mem_read(B-prefix,length))==b'\x73'*prefix+bytes(native)
    cases+=1
    # The native clear bodies execute; only repaint/notification tails are
    # stubs here. No SRAM writer is stubbed. Full-port tests cover the tails.
    if 'hd_track_read_c' in m.sym:
        # Isolate the underlying native clear here: installed Harmony clears
        # intentionally update the checkpoint. The track-retention gate tests
        # that installed path, including clear -> restore and other tracks.
        u.mem_write(0x40039b00,bytes.fromhex('4fefffc848d77cfc'))
    for at in (0x40027e00,0x400339d8,0x4009da20):u.mem_write(at,b'\x4e\x75')
    for name,entry,args in (
        ('track0',0x40039b00,(0,0,1)),('track127',0x40039b00,(15,7,1)),
        ('track_middle',0x40039b00,(7,3,1)),
    ):
        u.mem_write(BASE,bytes(seed));u.mem_write(B,bytes(native))
        m.sym[name]=entry
        protected=True;m.c(name,*args);protected=False
        assert not writes,(name,writes[:4])
        actual=bytes(u.mem_read(BASE,SIZE))
        assert bytes(actual[o] for o in OFFSETS)==pool,name
        steps=range(64) if name.startswith('track') else range(args[2]*16,args[2]*16+16)
        for step in steps:
            at=args[0]*0x8ed8+0x4900+args[1]*0x8b0+32*step
            assert actual[at:at+30]==b'\xff'*30,(name,step)
        cases+=1
    result={'capacity_bytes':len(pool),'bounded_pool_io':True,
            'native_copy_and_clear_cases':cases,'unexpected_pool_writes':len(writes),
            'hardware_tested':False}
    print(json.dumps(result))
    out=ROOT/'out/midi-sram';out.mkdir(exist_ok=True)
    (out/'machine.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
