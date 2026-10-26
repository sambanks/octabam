#!/usr/bin/env python3
"""Linked GRAV policy, real event continuations, lifecycle and packing isolation."""
import random
import struct
import sys
import subprocess
from unicorn import UC_HOOK_CODE
from midi_machine import Machine, ROOT
from verify_store_part_settings import symbols
from verify_midi_follow import REGS
from unicorn.m68k_const import UC_M68K_REG_D7, UC_M68K_REG_A7, UC_M68K_REG_PC


def choose(pc, previous, home):
    lo=12*home
    def cost(n):
        outside=max(lo-n,0,n-(lo+11))
        return ((0 if previous is None else (n-previous)**2)+outside**2,outside,n)
    return min(range(pc,128,12),key=cost)


def main():
    subprocess.run([sys.executable,str(ROOT/'modules/midi-follow/upstream/modules/midi-follow/generate.py'),'--check'],check=True)
    m=Machine(symbols);u=m.uc;s=m.sym
    for address,name in ((0x4009c3d4,'seq_start'),(0x4009c4d4,'seq_resume'),
                         (0x4009fbb2,'seq_sent_a'),(0x4009fcfa,'seq_sent_b')):
        assert bytes(u.mem_read(address,6))==b'\x4e\xf9'+s[name].to_bytes(4,'big')
    if '--negative-control' in sys.argv:
        def skip_commit(uc,pc,size,data):
            sp=uc.reg_read(UC_M68K_REG_A7)
            uc.reg_write(UC_M68K_REG_PC,int.from_bytes(uc.mem_read(sp,4),'big'))
            uc.reg_write(UC_M68K_REG_A7,sp+4)
        u.hook_add(UC_HOOK_CODE,skip_commit,begin=s['bf_sent_c'],end=s['bf_sent_c'])
    def root(note):
        u.mem_write(s['bf_roots'],bytes((36+note%12,)))
        u.mem_write(s['bf_pitches'],bytes((note,)))
    def begin(t=1):m.call('bf_register_begin',t)
    def query(t=1):
        preserved={r:0x12340000+i for i,r in enumerate(REGS[1:-1])}
        preserved[REGS[1]]=t
        result=m.call('bf_register',0,t,regs=preserved)
        assert all(u.reg_read(r)==v for r,v in preserved.items()), 'register ABI'
        assert u.reg_read(UC_M68K_REG_A7)==m.stack+4, 'unbalanced query stack'
        state=s['bf_history']+16*t
        for address,size in m.writes:
            assert (state<=address and address+size<=state+16
                    or m.stack-256<=address and address+size<=m.stack), ('query write',hex(address),size)
        return result
    def sent(t=1,velocity=100,live=0,hook='seq_sent_a'):
        u.mem_write(0x400d807e,bytes((velocity,)))
        u.mem_write(0x46c77b1e+10*t,bytes((live,)))
        m.call(hook,stop=0x4009fbb8 if hook=='seq_sent_a' else 0x4009fd00,
               regs={UC_M68K_REG_D7:t})
    m.call('bf_source_set',1,1);m.call('bf_mode_set',1,1);m.call('bf_home_set',1,2)
    root(35);begin();assert query()==35;sent()
    root(36);begin();assert query()==36;sent()
    root(41);begin();assert query()==29;sent()
    # Repeated calculation, voices and arp reads reuse a single proposal.
    for _ in range(10):assert query()==29;sent()
    # A silent proposal cannot replace the last actually sounded reference.
    root(47);begin();assert query()==35
    sent(velocity=0);sent(live=1)
    root(36);begin();assert query()==24  # previous F2, not the rejected B2
    sent(live=0)
    rng=random.Random(181026);cases=0
    for home in range(11):
        m.call('bf_home_set',1,home);m.call('bf_register_reset')
        previous=None
        for _ in range(128):
            note=rng.randrange(128);root(note);begin()
            want=choose(note%12,previous,home)
            assert query()==want,(home,note,previous,want,query())
            for _ in range(3):assert query()==want
            if rng.randrange(4):
                sent(hook='seq_sent_b');previous=want
                assert query()==want,'commit must not recompute this event'
            cases+=1
    # Independent receiving tracks, reset boundaries and remembered controls.
    for t in range(1,8):
        m.call('bf_source_set',t,1);m.call('bf_mode_set',t,1);m.call('bf_home_set',t,2)
    m.call('bf_register_reset');root(35)
    for t in range(1,8):begin(t);assert query(t)==35;sent(t)
    root(0)
    for t in range(1,8):begin(t);assert query(t)==36;sent(t)
    transport_seen=[]
    def observe_transport(uc,pc,size,data):
        transport_seen.append(int.from_bytes(uc.mem_read(0x800065b8,4),'big'))
    observer=u.hook_add(UC_HOOK_CODE,observe_transport,
                        begin=s['bf_seq_start'],end=s['bf_seq_start'])
    for hook,stop in (('seq_start',0x4009c3da),('seq_resume',0x4009c4da)):
        epoch=(int.from_bytes(u.mem_read(s['eu_clock']+12,4),'big')
               if 'eu_clock' in s else None)
        u.mem_write(0x800065b8,bytes(4))
        m.call(hook,1,stop=stop)
        assert transport_seen[-1]==1, 'Follow notification must follow native PLAYING write'
        if epoch is not None:
            assert int.from_bytes(u.mem_read(s['eu_clock']+12,4),'big')==epoch+1, \
                'EUCLID must receive exactly one reset alongside Follow'
        for t in range(1,8):assert query(t)==24
    assert transport_seen==[1,1], 'one Follow reset per transport notification'
    u.hook_del(observer)
    # Same-slot native Part replacement invalidates history without saving it.
    root(35);begin();query();sent();root(0);begin();assert query()==36;sent()
    part=0x400e21e0+0x8ed80;copy=m.scratch+0x1000
    u.mem_write(copy,bytes(u.mem_read(part,0x18b2)))
    u.mem_write(m.stack+4,struct.pack('>III',part,copy,0x18b2))
    m.call('store_part_native_copy');assert query()==24
    # Ordinary pattern changes do not touch the native Part identity.
    root(35);begin();query();sent();u.mem_write(0x100b14d0,b'\x01')
    root(0);begin();assert query()==36
    sent()
    m.call('bf_home_set',1,3);m.call('bf_home_set',1,2)
    assert query()==24,'rapid edits away/back must reset history'
    # All combinations fit seven-bit native fields and preserve flags.
    for t in range(8):
        flags=m.part_address(t,12);u.mem_write(flags,b'\x0e')
        for fixed in range(11):
            for offset in range(-2,3):
                assert m.call('bf_fixed_set',t,fixed)==1
                assert m.call('bf_offset_set',t,offset&0xffffffff)==1
                assert m.call('bf_fixed_get',t)==fixed
                assert m.call('bf_offset_get',t)==offset&0xffffffff
                assert u.mem_read(m.part_address(t,13),1)[0]<80
        for home in range(11):
            for mode in range(3):
                assert m.call('bf_home_set',t,home)==1
                assert m.call('bf_mode_set',t,mode)==1
                assert m.call('bf_home_get',t)==home
                assert m.call('bf_mode_get',t)==mode
                assert u.mem_read(m.part_address(t,15),1)[0]<48
        assert u.mem_read(flags,1)==b'\x0e','UPDT/Loopback changed'
    # Native byte ranges include invalid subfield combinations; readers must
    # fall back independently without changing neighbours or stored bytes.
    u.mem_write(m.part_address(0,13),b'\x4f')
    u.mem_write(m.part_address(0,15),b'\x2f')
    assert m.call('bf_fixed_get',0)==3 and m.call('bf_offset_get',0)==2
    assert m.call('bf_home_get',0)==3 and m.call('bf_mode_get',0)==2
    u.mem_write(m.part_address(0,15),b'\x33')
    assert m.call('bf_mode_get',0)==0 and m.call('bf_home_get',0)==3
    print(f'[ok] GRAV: {cases} scored events, repeated queries, successful-send/velocity/live gates, seven receivers, transport/Part resets, pattern continuity and all packed combinations')


if __name__=='__main__':main()
