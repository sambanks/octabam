#!/usr/bin/env python3
"""Exercise real native copy/init entries with degree provenance attached.

Pause after native SETUP writes have begun, consume roots/events through the
actual shared snapshot, then finish. This is composed ColdFire evidence, not
native filesystem/RTOS scheduling or hardware timing evidence.
"""
import json
from unicorn import UC_HOOK_CODE
from unicorn.m68k_const import *
from verify_harmony_degree_integration import DegreeMachine, ROOT
from harmony_midi_machine import InterruptMaskTrace

B, BS, PS, LANE = 0x400e21e0, 0x9b340, 0x18b2, 131
COPY, INIT = 0x40020898, 0x40005638


def main():
    m=DegreeMachine();u=m.uc;s=m.sym
    m.call('mhc_lock_init')
    h=s['hd_banks']
    def put(a,v,n=1):u.mem_write(a,v.to_bytes(n,'big'))
    def get(a,n=1):return int.from_bytes(u.mem_read(a,n),'big')
    def field(bank,part,track,slot):return B+bank*BS+0x8ed80+part*PS+0x4e2+track*36+slot
    def step(bank,track,index=0):return B+bank*BS+0x4900+track*0x8b0+index*32
    for bank in (0,7):
        u.mem_write(B+bank*BS,b'\xff'*BS)
        for p in range(16):put(B+bank*BS+p*0x8ed8+0x8e57,0)
        for part in range(8):
            po=0x8ed80+part*PS if part<4 else 0x9504a+(part-4)*PS
            for track in range(8):
                put(B+bank*BS+po+0x3e2+track*32,48)
                for f,v in ((3,0),(5,0),(12,0),(13,35),(15,3),(16,0),(17,2),(18,0),(19,35)):
                    put(B+bank*BS+po+0x4e2+track*36+f,v)
    put(0x46c82456,B,4);put(0x100b14cf,0);put(0x100b14d0,0)
    source=m.scratch+0x2000
    paused=False;observing=False;instructions=0;masked=0;max_masked=0
    mask_trace=InterruptMaskTrace(u)
    def observe(u,pc,size,data):
        nonlocal paused,instructions,masked,max_masked
        if not observing:return
        instructions+=1
        if mask_trace.before(pc)==7:masked+=1
        else:max_masked=max(max_masked,masked);masked=0
        if not paused and pc==0x400208ae and u.reg_read(UC_M68K_REG_A1)>=B+0x8ed80+0x4e2+144:
            paused=True;u.emu_stop()
    u.hook_add(UC_HOOK_CODE,observe)
    copy_counts=[]
    for incoming in (0,1,2):
        # Each track has an explicit tonic and an unlocked next step.
        for track in range(8):
            put(field(0,0,track,5),2);put(field(0,0,track,17),2)
            put(field(0,0,track,19),35)
            m.c('hd_edit_step_c',0,0,track,0,35)
            for slot in range(4):m.c('hd_event_stage_c',0,0,track,0,slot)
        u.mem_write(source,bytes(u.mem_read(B+0x8ed80,PS)))
        for track in range(8):
            put(source+0x4e2+track*36+5,incoming)
            put(source+0x4e2+track*36+17,6)
            put(source+0x4e2+track*36+19,39)
            put(source+0x3e2+track*32,65)
        args=(B+0x8ed80,source,PS)
        u.reg_write(UC_M68K_REG_SR,0x2000);u.reg_write(UC_M68K_REG_A7,m.stack)
        u.mem_write(m.stack,b''.join(v.to_bytes(4,'big') for v in (m.done,*args)))
        m.arrival=None;m.stops={m.done};paused=False;observing=True;instructions=0
        mask_trace.ipl=0
        u.emu_start(COPY,0,count=2000000)
        assert paused and m.arrival is None
        assert get(s['store_part_snapshot_bank'],4)==B and get(s['store_part_snapshot_parts'],4)==1
        assert u.reg_read(UC_M68K_REG_SR)&0x700==0,'native bulk copy masked interrupts'
        observing=False
        saved=u.context_save();stack=m.stack;m.stack-=0x2000
        for track in range(8):
            assert m.c('hd_resolve_c',0,0,track,0)==48
            assert get(h+track*LANE+130)==255,'interruption reattached outgoing slot'
            assert m.c('hd_base_c',0,0,track)==35,'incoming default leaked through snapshot'
            assert m.c('hd_event_fire_c',track,track)==0xffffffff
            assert m.c('hd_prepare_c',48,track)==48
        # Engine/UI readers can run while the lower-priority Part writer is
        # paused. Re-reading its detached outgoing snapshot is not an edit:
        # advancing the revision here can starve a retained checkpoint forever.
        revision=m.c('hd_revision_c',0)
        for _ in range(20):
            m.c('hd_ui_observe_c')
            assert m.c('hd_resolve_c',0,0,0,0)==48
        assert m.c('hd_revision_c',0)==revision,'unchanged outgoing snapshot counted as a new edit'
        m.stack=stack;u.context_restore(saved);m.arrival=None;m.stops={m.done};observing=True
        u.emu_start(u.reg_read(UC_M68K_REG_PC),0,count=2000000)
        observing=False;copy_counts.append(instructions)
        assert m.arrival==m.done and u.reg_read(UC_M68K_REG_A7)==m.stack+4
        assert get(s['store_part_snapshot_bank'],4)==get(s['store_part_snapshot_parts'],4)==0
        for track in range(8):
            assert m.c('hd_sync_c',0,0,track)==bool(incoming)
            assert get(step(0,track))==48
            assert get(step(0,track,1))==255
            assert get(B+0x8ed80+0x3e2+track*32)==65
            assert m.c('hd_base_c',0,0,track)==39
            if incoming:
                assert m.c('hd_resolve_c',0,0,track,0)==50
                assert m.c('hd_resolve_c',0,0,track,1)==57
            for slot in range(1,4):
                result=m.c('hd_event_fire_c',slot*8+track,track)
                assert result==(0xffffffff if incoming else 48)
                assert m.c('hd_prepare_c',48,track)==(50 if incoming else 48)
    # Real native Clear supplies its own C3/1:3 defaults. Explicit outgoing
    # D3 is preserved independently, including all eight tracks.
    for track in range(8):
        put(field(0,0,track,5),2);put(field(0,0,track,17),6)
        m.c('hd_edit_step_c',0,0,track,0,35)
    m.sym['native_part_init']=INIT
    m.c('native_part_init',B+0x8ed80)
    for track in range(8):
        assert m.c('hd_sync_c',0,0,track)==0
        assert get(step(0,track))==50
        assert get(field(0,0,track,5))==0
        assert get(field(0,0,track,18))==0 and get(field(0,0,track,19))==35
        assert get(B+0x8ed80+0x3e2+track*32)==48
    result={'native_interrupted_part_copies':3,'tracks_each':8,'pending_slots_each':4,
            'same_slot_c3_and_incoming_defaults':'passed','snapshot_cannot_reattach':'passed',
            'repeated_outgoing_observations_do_not_dirty':20,
            'native_clear_outgoing_d3':'passed','copy_instructions':copy_counts,
            'max_copy_masked_instructions':max_masked,'hardware_timing_measured':False}
    print(json.dumps(result))
    out=ROOT/'out/harmony-degrees';out.mkdir(exist_ok=True)
    (out/'part-state.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
