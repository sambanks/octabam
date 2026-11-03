#!/usr/bin/env python3
"""Pin the root states an interrupt may observe during editing/recording."""
import json
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.m68k_const import *
from verify_harmony_degree_integration import DegreeMachine, ROOT
from harmony_midi_machine import InterruptMaskTrace
from verify_midi_sram import BASE, OFFSETS


def main():
    m=DegreeMachine();u=m.uc;h=m.sym['hd_banks'];bank=0x400e21e0
    note=bank+0x4900;degree=h;snapshot=h+64
    expected=set();watch=False;pending=False;max_masked=masked=0
    check_duration=False;check_nv=False;observations=0
    mask_trace=InterruptMaskTrace(u)
    def put(a,v,n=1):u.mem_write(a,v.to_bytes(n,'big'))
    def get(a):return u.mem_read(a,1)[0]
    # Independent C-major pitch oracle, including nearest/lower tie policy.
    tones=(0,2,4,5,7,9,11)
    pitches=[n for n in range(128) if n%12 in tones]
    def encode(n):
        if n==255:return 255
        n=min(pitches,key=lambda p:(abs(p-n),p))
        return (n//12+1)*7+tones.index(n%12)
    retained_addresses={BASE+o for o in OFFSETS}
    def written(u,access,address,size,value,data):
        nonlocal pending
        if not watch:return
        if any(address<=a<address+size for a in (note,degree,snapshot)):pending=True
        if check_nv and any(a in retained_addresses for a in range(address,address+size)) and address != BASE+OFFSETS[0]:
            assert mask_trace.ipl==0,'bulk retention ran with interrupts masked'
    def inspect(u,pc,size,data):
        nonlocal pending,max_masked,masked,observations
        if not watch:return
        ipl=mask_trace.before(pc)
        if check_duration:
            if ipl==7:masked+=1
            else:max_masked=max(max_masked,masked);masked=0
        if not pending:return
        # Observe immediately AFTER each writer, before the next instruction.
        if ipl==7:return
        pending=False
        n=get(note);d=get(degree);s=get(snapshot)
        visible=d if n==s else encode(n)
        observations+=1
        assert visible in expected,('interrupt saw a third root',hex(pc),n,s,d,visible,expected)
    u.hook_add(UC_HOOK_MEM_WRITE,written);u.hook_add(UC_HOOK_CODE,inspect)
    put(0x80000002,0);put(bank+0x8e57,0)
    put(bank+0x8ed80+0x4e2+17,1)
    put(bank+0x8ed80+0x3e2,48)
    put(0x46c82456,bank,4)
    put(bank+0x8ed80+0x4e2+5,1)
    put(bank+0x8ed80+0x4e2+19,35)
    for initial_ipl in (0,0x500,0x700):
        for new_degree in (0,36,83,255):
            put(note,48);put(degree,35);put(snapshot,48)
            put(h+128,2);put(h+129,0);put(h+130,0)
            expected={35,new_degree};watch=True;pending=False
            mask_trace.ipl=initial_ipl>>8
            check_duration=initial_ipl!=0x700;masked=0
            u.mem_write(m.stack+4,b''.join(v.to_bytes(4,'big') for v in (0,0,0,0,new_degree)))
            m.call('hd_edit_step_c',regs={UC_M68K_REG_SR:0x2000|initial_ipl})
            watch=False
            assert u.reg_read(UC_M68K_REG_SR)&0x700==initial_ipl
            assert get(degree)==new_degree and get(snapshot)==get(note)
    # Clear must not be undone by a reader before the native clear continues.
    for active in (0,1):
        put(note,48);put(degree,35);put(snapshot,48);put(h+128,2 if active else 1);put(bank+0x8ed80+0x4e2+5,active)
        m.c('hd_forget_c',0,0,0,0)
        assert get(note)==(255 if active else 48),'OFF native NOTE changed'
        if active:assert m.c('hd_lock_c',0,0,0,0)==0xffffffff
    # Real recorder hook: physical D3 was captured as degree 1 under D minor,
    # then KEY changed to C major before commit. A reader must never see 2:3.
    put(bank+0x8ed80+0x4e2+5,1)
    put(note,48);put(degree,35);put(snapshot,48)
    put(h+128,2);put(h+129,0);put(h+130,0)
    put(m.sym['ch_record_active'],0,4);put(m.sym['hd_record_active'],35,4)
    put(m.scratch+8,0,4);put(m.scratch+16,100,4)
    expected={35};watch=True;pending=False;check_duration=False;check_nv=True
    mask_trace.ipl=0
    m.call('ch_record_commit',stop=0x400420fa,regs={UC_M68K_REG_SR:0x2000,
        UC_M68K_REG_D6:0,UC_M68K_REG_D5:0,UC_M68K_REG_A3:0,
        UC_M68K_REG_A4:50,UC_M68K_REG_A6:m.scratch})
    watch=False
    assert get(note)==get(snapshot)==48 and get(degree)==35
    assert u.reg_read(UC_M68K_REG_SR)&0x700==0
    assert observations>=9,'the observer never reached an interruptible publication'
    assert max_masked<300,('root update masked too much work',max_masked)
    max_edit=max_masked
    # A first recording must initialize a dense native lane before entering
    # the atomic single-root publication, not inside one long outer mask.
    for step in range(64):put(note+step*32,48+step%64)
    u.mem_write(h,b'\xff'*128+b'\0\0\xff')
    expected={35};pending=False;watch=True;check_duration=True
    mask_trace.ipl=0;max_masked=masked=0
    m.call('ch_record_commit',stop=0x400420fa,regs={UC_M68K_REG_SR:0x2000,
        UC_M68K_REG_D6:0,UC_M68K_REG_D5:0,UC_M68K_REG_A3:0,
        UC_M68K_REG_A4:50,UC_M68K_REG_A6:m.scratch})
    watch=False
    assert get(note)==get(snapshot)==48 and get(degree)==35
    assert max_masked<3000,('first recording masked whole-lane conversion',max_masked)
    result={'interrupt_visible_roots':'old_or_new_only','edit_cases':12,
            'clear_cannot_resurrect':True,'off_clear_native_unchanged':True,
            'record_captured_key_publication':True,'retention_unmasked':True,
            'max_edit_masked_instructions':max_edit,'max_cold_record_masked_instructions':max_masked,
            'observations':observations,
            'hardware_timing_measured':False}
    print(json.dumps(result))
    (ROOT/'out/harmony-degrees/publication.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
