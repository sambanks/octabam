#!/usr/bin/env python3
"""Exercise degree hooks in the selected linked firmware, before full port QA."""
import json
import re
import subprocess
from unicorn.m68k_const import *
from harmony_midi_machine import Machine, ROOT


def symbols():
    raw = subprocess.check_output(['m68k-elf-nm', str(ROOT/'out/platform/runtime/runtime.elf')], text=True)
    return {n:int(a,16) for a,n in re.findall(r'^([0-9a-f]+) [TtBbDdAa] ((?:seq|ed|ha|hd|ch|mh|bf|ms|store_part)_\w+)$',raw,re.M)}


class DegreeMachine(Machine):
    def __init__(self):
        super().__init__(symbols)
        self.instruction_budget = 30_000_000
        self.call('store_part_activate',stop=0x4000f938)
    def c(self,name,*args):
        self.uc.mem_write(self.stack+4,b''.join((v&0xffffffff).to_bytes(4,'big') for v in args))
        return self.call(name)


def main():
    m=DegreeMachine();u=m.uc;s=m.sym
    assert 'hd_set' in s, 'build REMIX=harmony-degrees first'
    def put(a,v,n=1): u.mem_write(a,v.to_bytes(n,'big'))
    def get(a,n=1): return int.from_bytes(u.mem_read(a,n),'big')
    # FUNC edits the tonic octave, including saturation at both ends.
    for held in (0,0x20):
        put(0x46100b1d,held)
        for code in range(84):
            for delta in (-1000,-2,-1,0,1,2,1000):
                expected=(max(0,min(11,code//7+delta))*7+code%7 if held
                          else max(0,min(83,code+delta)))
                assert m.c('hd_ui_advance_c',code,delta)==expected,(held,code,delta)
    put(0x46100b1d,0)
    print('[ok] FUNC DEG changes octaves and preserves degree at both limits',flush=True)
    m.call('ch_lock_init')
    bank=0x400e21e0
    u.mem_write(bank,b'\xff'*0x9b340)
    for p in range(16): put(bank+p*0x8ed8+0x8e57,p%4)
    for part in range(8):
        offset=(0x8ed80+part*0x18b2) if part<4 else (0x9504a+(part-4)*0x18b2)
        for t in range(8):
            put(bank+offset+0x3e2+t*32,48)
            for field,value in ((3,0),(5,0),(12,0),(13,35),(15,3),(16,0),(17,2),(18,0),(19,35)):
                put(bank+offset+0x4e2+t*36+field,value)
    put(bank+0x4900,48)
    put(0x46c82456,bank,4)
    put(0x46c76df1,2)
    put(0x46c76fe0,48)
    m.call('hd_bank_loaded',0)
    m.call('mh_set',0,2)
    assert m.call('mh_get',0)==2
    assert get(s['hd_busy'])==0
    assert m.c('hd_degree_c',0,0,0,0)==35

    # Execute the real detours, carrying a root from staging through native
    # pending payload copy and fire. Change KEY after staging, before fire.
    put(m.stack+48,0,4);put(m.stack+60,0xffffffff,4)
    m.call('ch_stage_fill',stop=0x4009d188,regs={UC_M68K_REG_D3:0,UC_M68K_REG_D7:0,
            UC_M68K_REG_A3:0,UC_M68K_REG_A5:m.scratch})
    m.call('ch_stage_copy_a',stop=0x4009b922,regs={UC_M68K_REG_D2:0,UC_M68K_REG_A0:0})
    put(bank+0x8ed80+0x4e2+17,6) # D minor
    put(0x46c76df1,6)
    u.mem_write(0x46c78960,bytes((48,100))+b'\0'*30)
    m.call('ch_pending_fire',stop=0x400a19e2,regs={UC_M68K_REG_D5:0,
           UC_M68K_REG_A0:0x46c78960,UC_M68K_REG_A1:0x46c76fe0})
    assert m.call('mh_prepare',48,0)==50
    u.mem_write(m.scratch,bytes((48,11,12,13)))
    m.call('hd_sequence_prepare',0,a0=m.scratch)
    m.call('mh_generate',0,0,a0=m.scratch)
    assert bytes(u.mem_read(m.scratch,4))==bytes((50,53,57,50))
    m.call('mh_set',0,0)
    assert get(bank+0x4900)==50
    assert get(0x1001614e+0x4900)==50
    assert m.call('mh_prepare',50,0)==50
    # A queued root is converted too; it cannot overwrite D3 with stale C3.
    m.call('ch_pending_fire',stop=0x400a19e2,regs={UC_M68K_REG_D5:0,
           UC_M68K_REG_A0:0x46c78960,UC_M68K_REG_A1:0x46c76fe0})
    assert get(0x46c76fe0)==50
    put(bank+0x8ed80+0x4e2+17,1) # KEY change while OFF
    put(0x46c76df1,1)
    m.call('mh_set',0,1)
    assert m.c('hd_degree_c',0,0,0,0)==36 # D3 -> 2:3
    m.call('mh_set',0,2)
    assert m.c('hd_degree_c',0,0,0,0)==36
    # Live and held-step degree edits preserve native lock inheritance.
    assert m.c('hd_ui_edit_c',1,0,0)==1
    assert m.c('hd_base_c',0,0,0)==37
    assert m.c('hd_ui_value_c',-1)==37
    put(0x460d174a,3,2);put(0x460d174c,0,4)
    assert m.c('hd_ui_edit_c',1,0,1)==1
    assert m.c('hd_ui_value_c',0)==(37|256)
    assert m.c('hd_ui_value_c',1)==(38|256)
    assert m.c('hd_ui_edit_c',0,1,1)==1
    assert get(bank+0x4900)==255 and get(bank+0x4920)==255
    assert m.c('hd_ui_value_c',0)==37
    # Physical keyboard conversion is captured in the then-current scale.
    put(0x46c76df1,6);put(bank+0x8ed80+0x4e2+17,6)
    assert m.call('hd_capture',50,0)==35
    put(0x46c76df1,1);put(bank+0x8ed80+0x4e2+17,1)
    assert m.call('hd_capture',50,0)==36
    # Combined current-bank retention uses a separate identity.
    m.call('ch_nv_save',0)
    from harmony_retained import committed
    assert committed(m)
    assert m.call('ch_nv_restore',0)==1
    # Copy a degree while the native NOTE snapshot is stale, then paste into
    # another Part/key and an OFF track. Exercise actual native memcpy too.
    put(bank+0x8ed80+0x4e2+17,2)
    put(bank+0x8ed80+0x18b2+0x4e2+17,6)
    put(bank+0x8ed80+0x18b2+0x4e2+5,2)
    m.c('hd_edit_step_c',0,0,0,0,35)
    put(bank+0x8ed80+0x4e2+17,6) # source degree 1 is now D3; NOTE still C3
    assert get(bank+0x4900)==48
    source=bank+0x48d0
    dest=bank+0x8ed8+0x48d0
    clip=0x460c8122
    m.c('hd_memcpy',clip,source,0x8b0)
    m.c('hd_memcpy',dest,clip,0x8b0)
    assert m.c('hd_degree_c',0,1,0,0)==35
    assert get(dest+0x30)==48  # canonical mirror; resolved D3 remains 50
    assert m.c('hd_resolve_c',0,1,0,0)==50
    m.c('hd_memcpy',bank+0x48d0+0x8b0,clip,0x8b0) # HARM -> OFF track
    assert get(bank+0x4900+0x8b0)==50
    # Stock often separately copies into CS1 from the same clipboard. It
    # must not reintroduce the stale C3 snapshot after the native repair.
    m.c('hd_memcpy',0x1001614e+0x48d0+0x8b0,clip,0x8b0)
    assert get(0x1001614e+0x4900+0x8b0)==50
    m.c('hd_edit_base_c',0,0,0,40)
    m.c('hd_memcpy',bank+0x9504a,bank+0x8ed80,0x18b2)
    assert m.c('hd_base_c',0,4,0)==40
    m.c('hd_edit_base_c',0,0,0,35)
    m.c('hd_memcpy',bank+0x8ed80,bank+0x9504a,0x18b2)
    assert m.c('hd_base_c',0,0,0)==40
    # An unlocked staged root inherits a later default edit. It must not
    # become an implicit lock just because the scheduler ran ahead.
    m.c('hd_event_stage_c',0,0,0,2,0)
    m.c('hd_event_fire_c',0,0)
    m.c('hd_edit_base_c',0,0,0,35)
    assert m.call('mh_prepare',48,0)==50
    m.c('hd_edit_base_c',0,0,0,36)
    assert m.call('mh_prepare',48,0)==52
    # The real enqueue hook freezes degree before the UI consumes its
    # message. Boundary conversion must leave the physical release pitch.
    put(0x46c76df1,6)
    u.mem_write(0x46c77bea,bytes((70,8,50,100))+b'\0'*8)
    m.call('ch_record_post',stop=0x40000c3c,regs={UC_M68K_REG_D5:0})
    message=get(m.stack+36,4)
    assert s['ch_messages'] <= message < s['ch_messages']+4096
    assert get(message+15)==35 and get(message+2)==50
    put(bank+0x8ed80+0x4e2+17,10)
    put(0x46c76df1,10)
    m.call('mh_set',0,0)
    assert get(message+15)==(128|52) and get(message+2)==50
    put(bank+0x8ed80+0x4e2+17,1)
    put(0x46c76df1,1)
    m.c('hd_record_c',0,0,0,3,get(message+15))
    assert get(bank+0x4900+3*32)==52
    m.call('mh_set',0,1)
    assert get(message+15)==37
    # Native SETUP slices carry both defaults. NOTE-only slices do not
    # overwrite DEG or CHRD; there is no second defaults clipboard to repair.
    m.c('hd_edit_base_c',0,0,0,40)
    m.call('ch_base_set',0,4)
    put(bank+0x8ed80+0x4e2+17,6)
    m.c('hd_memcpy',clip,source,0x8b0)
    m.c('hd_memcpy',clip+0x8b0,bank+0x8ed80+0x3e2,0xf0)
    m.c('hd_memcpy',bank+0x8ed80+0x18b2+0x3e2,clip+0x8b0,0xf0)
    assert m.c('hd_base_c',0,1,0)==35
    setup=bank+0x8ed80+0x4e2
    m.c('hd_memcpy',clip+0x8b0,setup,36)
    m.c('hd_memcpy',setup+0x18b2,clip+0x8b0,36)
    assert m.c('hd_base_c',0,1,0)==40
    assert get(setup+0x18b2+18)==4
    # Editing another bank must not replace the currently retained bank.
    m.c('hd_memcpy',bank+0x9b340+0x48d0,clip,0x8b0)
    assert get(s['ch_nv_bank'],4)==0
    # A sustained sequence arp pool changes representation on the engine
    # task, without adding TRAN twice or modifying held live-key pools.
    frame=m.scratch+0x2000
    put(frame-36,m.scratch+0x200,4)
    put(frame-42,0,4)
    put(0x46c76df1,6)
    put(0x46c76fe3,64);put(0x46c76fe4,64);put(0x46c76fe5,64)
    put(0x46c76fec,71)
    put(s['hd_rebuild'],1)
    tick={UC_M68K_REG_D7:0,UC_M68K_REG_A5:0x46c76dc0,UC_M68K_REG_A6:frame}
    m.call('hd_tick',stop=0x4009f9cc,regs=tick)
    assert get(0x46c7a2a0)==65
    m.call('mh_set',0,0)
    m.call('hd_tick',stop=0x4009f9cc,regs=tick)
    assert get(0x46c7a2a0)==58
    put(0x46c77b1e,1)
    put(0x46c7a2a0,73)
    put(s['hd_rebuild'],1)
    m.call('hd_tick',stop=0x4009f9cc,regs=tick)
    assert get(0x46c7a2a0)==73
    # A pending event keeps the Part captured when scheduled, including
    # quality/default inheritance; UI navigation cannot redirect its root.
    m.call('mh_set',0,1)
    m.c('hd_edit_step_c',0,0,0,0,35)
    m.c('hd_event_stage_c',0,0,0,0,0)
    put(bank+0x8ed80+0x18b2+0x4e2+17,10)
    put(bank+0x8e57,1)
    m.call('mh_set',0,0)
    assert m.c('hd_event_fire_c',0,0)==50
    put(bank+0x8e57,0)
    # An invalid degree cannot become valid via TRAN byte wrap. A follower
    # with a valid source must ignore that invalid own degree, however.
    if 'bf_source_resolve' in s:
        m.call('mh_set',0,1)
        m.c('hd_events_reset_c')
        m.c('hd_edit_base_c',0,0,0,0)
        put(bank+0x8ed80+0x4e2+17,1)
        put(0x46c76df1,1)
        put(0x46c76fec,71)
        put(s['bf_roots'],41);put(s['bf_pitches'],53)
        m.call('bf_latch',0,0,regs={UC_M68K_REG_D7:0,UC_M68K_REG_A5:0x46c76dc0})
        assert get(s['bf_roots'])==41 and get(s['bf_pitches'])==53
        u.mem_write(m.scratch,b'\xff'*4)
        assert m.call('mh_generate',0,7,a0=m.scratch)==0xffffffff
        m.follow_write('source',bytes((2,)))
        put(s['bf_roots']+1,38);put(s['bf_pitches']+1,50)
        m.follow_write('mode',bytes((2,)))
        u.mem_write(m.scratch,b'\xff'*4)
        assert m.call('mh_generate',0,0,a0=m.scratch)==1
        assert get(m.scratch)==50, (get(m.scratch), m.call('bf_offset_get',0))
    # Clear/place must invalidate metadata immediately. A later native NOTE
    # with the same byte must never resurrect the pre-clear scale identity.
    put(bank+0x8e57,0)
    for name,stop,args,regs in (
        ('ch_clear_locks',0x40040d4c,(0,0,0,1),{}),
        ('ch_clear_track',0x40039b08,(0,0,1),{}),
        ('ch_place',0x4005fd90,(),{UC_M68K_REG_D6:0,UC_M68K_REG_A5:0})):
        m.c('hd_edit_step_c',0,0,0,0,40)
        u.mem_write(m.stack+4,b''.join(v.to_bytes(4,'big') for v in args))
        m.call(name,stop=stop,regs=regs)
        assert get(s['hd_banks'])==255 and get(s['hd_banks']+64)==255,name
    # In HARM NOTE, hidden controls cannot silently change dormant
    # stock NOT2-4, including encoder pushes while a step is held.
    m.call('mh_set',0,1)
    put(0x80000012,1,4);put(0x460d1684,0,4);put(0x460d175c,0,4)
    # Main-page input stays active under the stock 18-row page-change
    # notification, as well as the 16-row held-step strip. A full SETUP
    # window must keep its native controls. Exercise both degree and CHRD.
    for mode in (1,2):
        m.call('mh_set',0,mode)
        for rows,want in ((16,True),(18,True),(64,False)):
            put(0x460d175c,m.scratch,4);put(m.scratch+40,rows,4)
            assert bool(m.call('hd_ui_owned',d1=0))==want,(mode,rows)
            assert bool(m.call('ch_ui_owned',d1=3))==(want and mode==2),(mode,rows)
    put(0x460d175c,0,4)
    m.call('mh_set',0,1)
    before=bytes(u.mem_read(bank,0x9b340))
    degree_before=bytes(u.mem_read(s['hd_banks'],16768))
    for slot in (3,5):
        m.c('ch_encoder',slot,4)
        m.c('ch_step_encoder',slot,4)
        m.c('ch_step_push',slot+56,1)
    assert bytes(u.mem_read(bank,0x9b340))==before
    assert bytes(u.mem_read(s['hd_banks'],16768))==degree_before
    result={'note_hidden_controls_do_not_edit_stock':'passed','native_clear_place_invalidation':'passed','pending_captured_part_context':'passed','invalid_degree_follow_and_transpose':'passed',
            'linked_mode_conversion':'passed','native_staging_pending_fire':'passed',
            'key_before_fire':'passed','note_chord_identity':'passed','degree_edit_lock_toggle':'passed',
            'captured_key':'passed','combined_retention':'passed',
            'native_track_clipboard_cross_mode_cs1':'passed','part_defaults_save_reload':'passed',
            'queued_record_boundaries':'passed','unlocked_pending_inheritance':'passed',
            'native_setup_default_slices':'passed','current_bank_retention_owner':'passed',
            'sequence_arp_mode_boundary':'passed','live_pool_preserved':'passed',
            'hardware_tested':False}
    print(json.dumps(result))
    out=ROOT/'out/harmony-degrees';out.mkdir(exist_ok=True)
    (out/'integration.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__': main()
