#!/usr/bin/env python3
"""Linked degree/MIDI SCENES boundaries; full firmware acceptance is separate."""
import argparse
import json
import re
import subprocess
from unicorn.m68k_const import *
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from harmony_midi_machine import InterruptMaskTrace
from verify_harmony_degree_integration import DegreeMachine, ROOT

B, BS, PS = 0x400e21e0, 0x9b340, 0x18b2


def machine():
    m = DegreeMachine()
    # MIDISC's ordinary CC publisher reaches UART registers during refresh.
    # This linked harness provides register memory; UART timing is port QA.
    m.uc.mem_map(0xfc000000,0x100000)
    nm = subprocess.check_output(['m68k-elf-nm', str(ROOT/'out/platform/runtime/runtime.elf')], text=True)
    m.sym.update({name:int(addr,16) for addr,name in re.findall(r'^([0-9a-f]+) \w (\w+)$', nm, re.M)})
    assert 'scn_lib' in m.sym, 'build the MIDI SCENES degree carrier first'
    m.sym['native_pending'] = 0x400a19ce
    m.call('ch_lock_init')
    def put(a, v, n=1): m.uc.mem_write(a, v.to_bytes(n, 'big'))
    m.put = put
    m.get = lambda a,n=1: int.from_bytes(m.uc.mem_read(a,n),'big')
    for bank in (0,7):
        m.uc.mem_write(B+bank*BS, b'\xff'*BS)
        for pat in range(16): put(B+bank*BS+pat*0x8ed8+0x8e57,0)
        for part in range(4):
            base=B+bank*BS+0x8ed80+part*PS
            put(base+0x10,255);put(base+0x11,255)
            m.uc.mem_write(base+0x17a2,bytes(144))
            for t in range(8):
                put(base+0x3e2+t*32,48)
                for field,value in ((3,0),(5,2),(12,0),(13,35),(15,3),(16,0),(17,2),(18,0),(19,35)):
                    put(base+0x4e2+t*36+field,value)
    put(0x46c82456,B,4);put(0x80000012,1,4)
    put(0x800065b8,1,4);put(0x80001828,0);put(0x80001829,0)
    for t in range(8):
        put(0x8000666e+t,0);put(0x80006676+t,0)
    m.c('hd_scene_ensure_c')
    m.call('hd_bank_loaded',0)
    return m


def pending():
    m=machine();u=m.uc
    # Exercise the actual patched ROM entry through the untouched Scenes
    # pending-copy hook, not the direct compatibility entry used by older tests.
    for slot in range(4):
        for track in range(8):
            degree=35+track
            m.c('hd_edit_step_c',0,0,track,0,degree)
            m.c('hd_event_stage_c',0,0,track,0,slot)
            index=slot*8+track
            source=0x46c78960+index*32
            target=0x46c76fe0+track*32
            note=m.c('hd_decode_c',degree,320)
            payload=bytes([note,100])+bytes(range(2,32))
            u.mem_write(source,payload)
            m.put(m.sym['ch_pending']+index,track)
            m.put(m.sym['ch_pending_context']+index,0)
            m.put(m.stack+136,target,4)
            m.call('native_pending',source,stop=0x400a19e2,regs={UC_M68K_REG_D5:track})
            assert bytes(u.mem_read(target,32))==payload,(slot,track)
            assert m.get(m.sym['ch_sequence_quality']+track)==track
            assert u.reg_read(UC_M68K_REG_A7)==m.stack
            assert m.c('hd_prepare_c',note,track)==note
    return {'pending_slots':32,'native_copy':'unchanged','stack':'balanced'}


def playback():
    m=machine();base=B+0x8ed80
    m.put(base+0x10,0);m.put(base+0x11,1)
    scenes(m,[(0,35),(256,39)])
    m.c('hd_edit_step_c',0,0,0,0,35)
    m.c('hd_event_stage_c',0,0,0,0,0)
    m.c('hd_event_fire_c',0,0)
    m.put(0x460d16c8,0,4)  # right endpoint, scene B: degree 5:3 = G3
    actual=m.c('hd_prepare_c',48,0)
    assert actual==55,('scene DEG 5:3 must override the pattern root',actual)
    return {'scene_degree_root':actual}


def scenes(m, entries, context=0, assigned=(0,1)):
    base=B+(context//4)*BS+0x8ed80+(context%4)*PS
    m.put(base+0x10,assigned[0]);m.put(base+0x11,assigned[1])
    table=bytearray(b'\xff'*4096)
    for index,value in entries:table[index]=value
    m.uc.mem_write(m.sym['scn_lib']+context*4096,bytes(table))



def sweep():
    m=machine();count=0
    for track in range(8):
        m.c('hd_edit_step_c',0,0,track,0,36)
        m.c('hd_event_stage_c',0,0,track,0,0)
        m.c('hd_event_fire_c',track,track)
        for key in (1,2,6,47):
            m.put(B+0x8ed80+0x4e2+36*track+17,key)
            scale=m.c('hd_scale_c',0,0,track)
            for a,b in ((35,39),(42,28),(0,83),(None,41),(33,None),(None,None)):
                scenes(m,[(side*256+track*32,v) for side,v in enumerate((a,b)) if v is not None])
                for xf in range(128):
                    m.put(0x460d16c8,xf,4)
                    va=36 if a is None else a;vb=36 if b is None else b;weight=127-xf
                    degree=va if weight==0 else vb if weight==127 else va+((vb-va)*weight//128)
                    expected=m.c('hd_decode_c',degree,scale)
                    assert m.c('hd_prepare_c',48,track)==expected,(track,key,a,b,xf,degree,expected)
                    count+=1
    # Unlocked trig inherits its Part DEG, not a stale native NOTE or UI Part.
    m=machine();scenes(m,[(256,39)])
    m.c('hd_event_stage_c',0,0,0,0,0);m.c('hd_event_fire_c',0,0)
    m.c('hd_edit_base_c',0,0,0,37);m.put(0x460d16c8,127,4)
    assert m.c('hd_prepare_c',0,0)==51
    m.put(0x46c82456,B+7*BS,4)  # unrelated UI navigation must not change captured context
    assert m.c('hd_prepare_c',0,0)==51
    return {'fader_key_track_cases':count,'empty_sides_inherit':True,'out_of_range_silent':True}


def capacity():
    m=machine()
    for context in (0,1,3,28,31):
        scenes(m,[(i,39) for i in range(4096)],context=context,assigned=(14,15))
        for track in range(8):
            for xf in (0,64,127):
                m.put(0x460d16c8,xf,4)
                assert m.c('hd_scene_value_c',context,track,0,35)==39
    scenes(m,[(0,39),(256,255)]);m.put(0x460d16c8,0,4)
    assert m.c('hd_scene_value_c',0,0,0,35)==35
    scenes(m,[(0,127),(256,128)]);m.put(0x460d16c8,127,4)
    assert m.c('hd_scene_value_c',0,0,0,35)==35
    return {'full_tables':5,'tracks':8,'invalid_endpoints_inherit':True}



def mode_editor():
    m=machine();base=B+0x8ed80
    m.sym['hold_a']=0x400534c2
    scenes(m,[]);m.put(0x460d169c,1,4)
    # Execute unchanged native editor, pack, morph and redraw after our seed.
    def edit(delta):
        m.call('hold_a',stop=0x40053a36,regs={UC_M68K_REG_D3:0,UC_M68K_REG_D6:delta&0xffffffff})
    before=bytes(m.uc.mem_read(base,PS))
    for flat in (3,4,5):
        m.call('hold_a',stop=0x40053a5c,regs={UC_M68K_REG_D3:flat,UC_M68K_REG_D6:1})
        assert bytes(m.uc.mem_read(base,PS))==before,'dormant NOT2-4 scene edited'
    edit(1)
    assert m.get(m.sym['scn_lib'])==36
    assert m.c('hd_base_c',0,0,0)==35
    assert m.c('hd_ui_value_c',-1)==292
    m.put(0x46100b1d,0x20)
    edit(1);assert m.get(m.sym['scn_lib'])==43
    edit(-1);assert m.get(m.sym['scn_lib'])==36
    m.put(0x46100b1d,0)
    edit(1000);assert m.get(m.sym['scn_lib'])==83
    edit(-1000);assert m.get(m.sym['scn_lib'])==0
    edit(39);assert m.get(m.sym['scn_lib'])==39
    m.c('hd_edit_step_c',0,0,0,0,35)
    m.c('hd_event_stage_c',0,0,0,0,0);m.c('hd_event_fire_c',0,0)
    m.put(0x460d16c8,127,4)
    assert m.c('hd_prepare_c',48,0)==55
    m.call('mh_set',0,0)
    assert m.get(m.sym['scn_lib'])==55
    m.c('hd_scene_ensure_c')
    assert m.get(m.sym['scn_lib'])==55,'native scene cache must load converted pitch'
    assert m.c('hd_prepare_c',48,0)==55,'converted OFF event must retain scene morph'
    m.c('hd_event_tick_c',0)
    assert m.get(0x46c76fe0)==55
    m.call('mh_set',0,2)
    assert m.get(m.sym['scn_lib'])==39
    assert m.c('hd_prepare_c',48,0)==55
    # Mode edits cannot convert scene values belonging to another track.
    return {'native_editor_seed':36,'range':[0,83],'scene_off_note':55,'round_trip_degree':39}


def contexts():
    m=machine();scenes(m,[(0,39)]);scenes(m,[(0,42)],context=1)
    m.put(0x460d16c8,127,4)
    assert m.c('hd_scene_value_c',0,0,0,35)==39
    assert m.c('hd_scene_value_c',1,0,0,35)==42
    m.c('hd_scene_before_c',0)
    m.put(m.sym['store_part_snapshot_bank'],B,4);m.put(m.sym['store_part_snapshot_parts'],1,4)
    scenes(m,[(0,28)])
    assert m.c('hd_scene_value_c',0,0,0,35)==39
    assert m.c('hd_scene_value_c',1,0,0,35)==42
    m.put(m.sym['store_part_snapshot_parts'],0,4)
    assert m.c('hd_scene_value_c',0,0,0,35)==28
    return {'outgoing_snapshot':True,'unrelated_context_independent':True,'incoming_published':True}


def interrupts():
    m=machine();u=m.uc;target=B+0x8ed80;source=0x47002000
    scenes(m,[(0,39),(512,42)]);scenes(m,[(0,42)],context=1,assigned=(2,3))
    u.mem_write(source,bytes(u.mem_read(target+PS,PS)))
    m.put(0x460d16c8,127,4)
    armed=True;pause=False;seen=set()
    def written(u,access,address,size,value,data):
        nonlocal pause
        if not armed:return
        point='snapshot-preparation' if address==m.sym['outgoing'] else 'native-copy' if address<=target+0x10<address+size else None
        if point and point not in seen:
            seen.add(point);pause=True
    def inspect(u,pc,size,data):
        if armed and pause:u.emu_stop()
    u.hook_add(UC_HOOK_MEM_WRITE,written);u.hook_add(UC_HOOK_CODE,inspect)
    u.reg_write(UC_M68K_REG_SR,0x2000);u.reg_write(UC_M68K_REG_A7,m.stack)
    u.mem_write(m.stack,b''.join(v.to_bytes(4,'big') for v in (m.done,target,source,PS)))
    m.arrival=None;m.stops={m.done};pc=0x40020898
    checks=0
    while m.arrival!=m.done:
        u.emu_start(pc,0,count=30000000)
        if m.arrival==m.done:break
        assert pause,hex(u.reg_read(UC_M68K_REG_PC))
        state=u.context_save();stack=m.stack
        armed=False;m.stack-=0x2000
        assert m.c('hd_scene_value_c',0,0,0,35)==39,seen
        m.stack=stack;u.context_restore(state)
        m.arrival=None;m.stops={m.done};pause=False;armed=True
        pc=u.reg_read(UC_M68K_REG_PC);checks+=1
    armed=False
    assert checks==2 and seen=={'snapshot-preparation','native-copy'},seen
    assert m.c('hd_scene_value_c',0,0,0,35)==42
    # Bound the full-table lookup in the event's existing critical section.
    m=machine();scenes(m,[(0,39)]+[(i,50) for i in range(1,30)]+[(256+i,40) for i in range(16)])
    m.c('hd_event_stage_c',0,0,0,0,0);m.c('hd_event_fire_c',0,0)
    trace=InterruptMaskTrace(m.uc);count=peak=0
    def masked(u,pc,size,data):
        nonlocal count,peak
        if trace.before(pc)==7:count+=1;peak=max(peak,count)
        else:count=0
    m.uc.hook_add(UC_HOOK_CODE,masked)
    m.uc.mem_write(m.stack+4,(48).to_bytes(4,'big')+bytes(4))
    m.call('hd_prepare_c',regs={UC_M68K_REG_SR:0x2000})
    assert peak<3500,peak
    return {'native_copy_interruptions':checks,'outgoing_until_publication':True,
            'max_scene_prepare_masked_instructions':peak,'hardware_timing_measured':False}


def commit_stack():
    m=machine();u=m.uc
    # The obsolete MIDISC2.1 stack workaround must leave this stock site alone.
    assert bytes(u.mem_read(0x400a44ee,6))==bytes.fromhex('23c080006628')
    m.sym['commit_site']=0x400a44ee
    checks=0
    for bank,pattern,part in ((0,0,0),(7,2,3),(255,0,0),(0,255,0),(0,0,255)):
        m.put(0x800065bd,bank);m.put(0x800065be,pattern)
        if bank<16 and pattern<16:m.put(B+bank*BS+pattern*0x8ed8+0x8e57,part)
        regs={r:0x12345600+i for i,r in enumerate(range(UC_M68K_REG_D0,UC_M68K_REG_D7+1))}
        regs.update({r:0x47001000+i for i,r in enumerate(range(UC_M68K_REG_A0,UC_M68K_REG_A6+1))})
        m.call('commit_site',stop=0x400a4500,regs=regs)
        assert u.reg_read(UC_M68K_REG_A7)==m.stack
        for r,v in regs.items():
            if r!=UC_M68K_REG_A1:assert u.reg_read(r)==v,(r,v,u.reg_read(r))
        assert u.reg_read(UC_M68K_REG_A1)==0x80006634
        assert m.get(0x80006628,4)==regs[UC_M68K_REG_D0]
        checks+=1
    return {'stock_commit_preserved':True,'native_commit_branches':checks,'stack_and_registers_preserved':True}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('remix',nargs='?')
    parser.add_argument('--case',choices=('pending','playback','sweep','capacity','mode-editor','contexts','interrupts','commit-stack'))
    args=parser.parse_args()
    probe=DegreeMachine()
    if not probe.c('hd_scenes_c'):
        assert probe.c('hd_scene_value_c',0,0,0,35)==35
        assert probe.c('hd_scene_delta_c',0,0,7)==7
        assert probe.c('hd_scene_ui_c',0,35)==35
        print(json.dumps({'scenes_absent':'all degree adapters inert'}))
        return
    selected={'pending':pending,'playback':playback,'sweep':sweep,'capacity':capacity,'mode-editor':mode_editor,'contexts':contexts,'interrupts':interrupts,'commit-stack':commit_stack}
    result={name:fn() for name,fn in selected.items() if not args.case or args.case==name}
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
