#!/usr/bin/env python3
"""Part-scoped UI/playback settings and real linked MIDI consumers."""
import re
import subprocess
from midi_machine import Machine, ROOT
from unicorn.m68k_const import *

B = 0x400e21e0
BS = 0x9b340
PS = 0x18b2


def symbols():
    raw = subprocess.check_output(['m68k-elf-nm', str(ROOT/'out/platform/runtime/runtime.elf')], text=True)
    return {n:int(a,16) for a,n in re.findall(r'^([0-9a-f]+) [TtBb] ((?:hd|mh|bf|ch|store_part|ms|seq|eu)_\w+)$',raw,re.M)}


def main():
    m=Machine(symbols); u=m.uc
    def byte(a,v):u.mem_write(a,bytes((v,)))
    def ui(bank,part):
        u.mem_write(0x46c82456,(B+bank*BS).to_bytes(4,'big'));byte(0x100b14cf,part)
    def at(bank,part,track,field):return B+bank*BS+0x8ed80+part*PS+0x4e2+track*36+field
    def play(track,bank,part):byte(0x8000666e+track,bank);byte(0x80006676+track,part)
    for bank in range(2):
        for part in range(4):
            for track in range(8):
                byte(at(bank,part,track,13),35);byte(at(bank,part,track,15),3)
                byte(at(bank,part,track,17),1)
    ui(0,0)
    for t in range(8):play(t,1,2)
    # YES refreshes only module-owned staged values in the selected Part.
    # Execute the real detour and stop after the displaced native prologue.
    for part in range(4):
        ui(0,part)
        for track in range(8):
            byte(0x100b14cc,track)
            staged=[4,17,29,7,31,0]
            u.mem_write(0x460d5cb4,b''.join(v.to_bytes(4,'big') for v in staged))
            byte(at(0,part,track,3),2);byte(at(0,part,track,5),1)
            expected=staged[:]
            if 'bf_source_get' in m.sym:expected[3]=2
            if 'mh_get' in m.sym:expected[5]=1
            m.sym['native_note_confirm']=0x4004af20
            m.call('native_note_confirm',stop=0x4004af28)
            actual=[int.from_bytes(u.mem_read(0x460d5cb4+4*i,4),'big') for i in range(6)]
            assert actual==expected,(part,track,actual,expected)
            byte(at(0,part,track,3),0);byte(at(0,part,track,5),0)
    ui(0,0);byte(0x100b14cc,0)
    print('  [ok] NOTE SETUP YES keeps live RFOL/HARM across all tracks/Parts and preserves stock staged fields')
    if 'mh_set' in m.sym:
        for t in range(8):
            for prefix,maximum in [('mh',2),('mh_voic',4),('mh_sprd',2),('mh_root',3)]:
                for value in range(maximum+1):
                    assert m.call(prefix+'_set',t,value)==1
                    assert m.call(prefix+'_get',t)==value
                    assert m.call(prefix+'_get_at',t,6)==0
                before=bytes(u.mem_read(at(0,0,t,0),36))
                assert m.call(prefix+'_set',t,maximum+1)==0
                assert bytes(u.mem_read(at(0,0,t,0),36))==before
            assert m.call('mh_active',t)==0
        # UI and playback operation/KEY must both use their own context.
        m.call('mh_set',0,2);m.call('mh_voic_set',0,0);m.call('mh_sprd_set',0,0);m.call('mh_root_set',0,0)
        byte(at(0,0,0,17),2)  # UI C minor
        byte(at(1,2,0,5),1)   # playing NOTE/C major
        u.mem_write(m.scratch,bytes((64,1,2,3)))
        assert m.call('mh_direct',0,0,a0=m.scratch)==1
        assert list(u.mem_read(m.scratch,4))==[63,67,70,63]
        u.mem_write(m.scratch,bytes((64,1,2,3)))
        assert m.call('mh_generate',0,0,a0=m.scratch)==1
        assert list(u.mem_read(m.scratch,4))==[64]*4
        # Captured context remains usable after changing the UI again.
        ui(0,3)
        assert m.call('mh_get_at',0,0)==2
        assert m.call('mh_get',0)==0
        assert m.call('mh_active',0)==1
        print('  [ok] Harmony Part fields/ranges, UI vs playback, captured getter, native KEY and generated pitches')
    if 'bf_select' in m.sym:
        ui(0,0)
        m.call('bf_select',1,1)
        assert m.call('bf_source_get',1)==1
        assert m.call('bf_source_play',1)==0
        m.call('bf_reg_change',1,1,regs={UC_M68K_REG_D2:2})
        assert m.call('bf_oct_get',1)==5
        m.call('bf_reg_change',1,0,regs={UC_M68K_REG_D2:2})
        m.call('bf_reg_change',1,1,regs={UC_M68K_REG_D2:-1 & 0xffffffff})
        assert m.call('bf_oct_get',1)==0xffffffff
        m.call('bf_response_set',1,1)
        assert m.call('bf_mode_get',1)==2 and m.call('bf_response_get',1)==1
        m.call('bf_reg_change',1,0,regs={UC_M68K_REG_D2:-2 & 0xffffffff})
        assert m.call('bf_oct_get',1)==5 and m.call('bf_response_get',1)==1
        assert m.call('bf_response_play',1)==0
        # Receiver T2 reads its playing Part; T1 supplies its own context.
        byte(at(1,2,1,3),1);byte(at(1,2,1,13),4)
        u.mem_write(m.sym['bf_roots'],bytes((38,255,255,255,255,255,255,255)))
        assert m.call('bf_source_resolve',1)==0
        assert m.call('bf_register',0,1)==50
        # Chain crosses a different Part on T1; cycle fallback is bounded.
        play(0,0,1);byte(at(0,1,0,3),3)
        assert m.call('bf_source_resolve',1)==2
        byte(at(1,2,2,3),2)
        assert m.call('bf_source_resolve',1)==1
        print('  [ok] Follow independent octaves, packed response, per-track playback chains and cycle fallback')


    if 'mh_voice' in m.sym:
        fresh=Machine(symbols);u=fresh.uc
        fresh.call('mh_set',0,2);fresh.call('mh_voic_set',0,1);fresh.set_key(0,1)
        def chord(root):
            u.mem_write(fresh.scratch,bytes((root,0,0,0)))
            fresh.call('mh_generate',0,0,a0=fresh.scratch)
            return bytes(u.mem_read(fresh.scratch,4))
        chord(48);fresh.call('mh_voice',0,a0=fresh.scratch)
        original=bytes(u.mem_read(B+0x8ed80,PS));source=0x47002000
        u.mem_write(source,original)
        u.mem_write(fresh.stack+4,b''.join(v.to_bytes(4,'big') for v in (B+0x8ed80,source,PS)))
        epoch=fresh.call('store_part_epoch',0)
        fresh.call('store_part_native_copy')
        assert fresh.call('store_part_epoch',0)==epoch+1
        assert fresh.call('store_part_epoch',1)==0
        expected=chord(55);fresh.call('mh_voice',0,a0=fresh.scratch)
        assert bytes(u.mem_read(fresh.scratch,4))==expected,'recalled Part inherited old AUTO history'
        print('  [ok] Native same-slot replacement advances only its epoch and resets Harmony AUTO history')


if __name__=='__main__':main()
