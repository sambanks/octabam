#!/usr/bin/env python3
"""Execute Follow register policy, capture and output bytes from the linked image."""
import struct
from pathlib import Path
from midi_machine import Machine
from unicorn.m68k_const import *

def main():
    m=Machine();u=m.uc;s=m.sym;lane=m.scratch+0x1000
    def edit(track,control,delta):
        m.call('bf_reg_change',track,control,regs={UC_M68K_REG_D2:delta&0xffffffff})
    for track in range(8):
        assert m.call('bf_mode_get',track)==0
        assert m.call('bf_oct_get',track)==3
    edit(1,1,1);edit(1,0,2);edit(1,1,-1)
    assert m.call('bf_oct_get',1)==0xffffffff
    edit(1,0,-2);assert m.call('bf_oct_get',1)==4
    edit(1,0,0x7fffffff);assert m.call('bf_mode_get',1)==2
    edit(1,1,0x7fffffff);assert m.call('bf_oct_get',1)==2
    edit(1,1,-0x80000000);assert m.call('bf_oct_get',1)==0xfffffffe
    edit(1,0,-0x80000000);assert m.call('bf_mode_get',1)==0
    edit(1,1,0x7fffffff);assert m.call('bf_oct_get',1)==10
    edit(1,1,-0x80000000);assert m.call('bf_oct_get',1)==0
    # Exercise the actual C-ABI encoder callback, not only its register helper.
    # B must never write either saved octave; C must never change MODE/RFOL.
    u.mem_write(s['bf_page_track'],(3).to_bytes(4,'big'))
    def knob(control,delta):
        u.mem_write(m.stack+4,control.to_bytes(4,'big')+(delta&0xffffffff).to_bytes(4,'big'))
        m.call('bf_page_encoder')
    octaves=bytes((m.follow_read('fixed')+m.follow_read('offset')))
    for delta in (4,4,127,-4,-4,-128):
        knob(1,delta)
        assert bytes((m.follow_read('fixed')+m.follow_read('offset')))==octaves
    modes=bytes(m.follow_read('mode',8,0))
    sources=bytes(m.follow_read('source',8,0))
    knob(2,4)
    assert m.call('bf_oct_get',3)==4
    assert bytes(m.follow_read('mode',8,0))==modes
    assert bytes(m.follow_read('source',8,0))==sources
    knob(1,4);knob(1,4);assert m.call('bf_oct_get',3)==0 # recall relative offset
    knob(2,-4);assert m.call('bf_oct_get',3)==0xffffffff
    knob(1,-4);knob(1,-4);assert m.call('bf_oct_get',3)==4 # fixed value retained
    settings=bytes((m.follow_read('mode')+m.follow_read('fixed')+m.follow_read('offset')))
    knob(0,4)
    assert bytes((m.follow_read('mode')+m.follow_read('fixed')+m.follow_read('offset')))==settings
    assert bytes(m.follow_read('source',8,0))!=sources
    print('[ok] encoder isolation: A RFOL only, B MODE only, C OCT only; independent octave recall')
    before=bytes((m.follow_read('mode')+m.follow_read('fixed')+m.follow_read('offset')))
    edit(8,0,1);edit(0,2,1)
    assert bytes((m.follow_read('mode')+m.follow_read('fixed')+m.follow_read('offset')))==before
    assert m.call('bf_register',8,0)==256
    assert m.call('bf_register',0,8)==256
    assert m.call('bf_register',0,1)==256
    m.follow_write('source',bytes((0,1,2,0,0,0,0,0)),0)
    cases=0
    for root in range(128):
        u.mem_write(lane+0x220,bytes((root,)));u.mem_write(lane+0x22c,b'\x40')
        m.call('bf_latch',d1=0,regs={UC_M68K_REG_D7:0,UC_M68K_REG_A5:lane})
        assert u.mem_read(s['bf_pitches'],1)==bytes((root,))
        assert u.mem_read(s['bf_roots'],1)==bytes((36+root%12,))
        for mode,octaves in ((0,range(11)),(2,range(-2,3))):
            for octave in octaves:
                for receiver in (1,2): # direct and chained receiver use ultimate source
                    m.follow_write('mode',bytes((mode,)),receiver)
                    m.follow_write('offset' if mode else 'fixed',bytes((octave&255,)),receiver)
                    base=(root if mode else root%12)+12*octave
                    assert m.call('bf_register',0,receiver)==base&0xffffffff,(root,mode,octave)
                    for tran in (-12,0,12):
                        u.mem_write(lane+0x22c,bytes((64+tran,)))
                        u.mem_write(m.scratch,b'\x3c')
                        want=base+tran;valid=0<=want<128
                        m.call('bf_note',a0=0,stop=0x4009fb86 if valid else 0x4009fd2a,regs={UC_M68K_REG_D7:receiver,UC_M68K_REG_D4:0,UC_M68K_REG_A2:m.scratch,UC_M68K_REG_A5:lane})
                        assert u.mem_read(m.scratch,1)==bytes((want if valid else 255,)),(root,mode,octave,tran)
                        assert all((m.stack-192<=a<m.stack) or a==m.scratch or a==s['bf_scale_offsets']+receiver*4 for a,_ in m.writes),m.writes
                        cases+=1
    if 'mh_generate' in s:
        # Both sequenced and live sources retain their harmonic root's octave.
        m.set_key(0,1) # source C major inherited by receivers
        m.call('mh_set',1,1) # receiver HARM NOTE
        for root in range(128):
            m.call('mh_latch_key_root',root,regs={UC_M68K_REG_D2:0})
            assert u.mem_read(s['bf_pitches'],1)==bytes((root,))
            for mode,octaves in ((0,range(11)),(2,range(-2,3))):
                for octave in octaves:
                    m.follow_write('mode',bytes((mode,)),1)
                    m.follow_write('offset' if mode else 'fixed',bytes((octave&255,)),1)
                    for tran in (-190,-12,0,12,190):
                        pitch=(root if mode else root%12)+12*octave+tran
                        u.mem_write(m.scratch,b'\x3c\x01\x02\x03')
                        result=m.call('mh_generate',1,tran&0xffffffff,a0=m.scratch)
                        if 0<=pitch<=127:
                            wanted=min((n for n in range(128) if n%12 in (0,2,4,5,7,9,11)),key=lambda n:(abs(n-pitch),n))
                            assert result==1 and u.mem_read(m.scratch,4)==bytes((wanted,))*4,(root,mode,octave,tran)
                        else:
                            assert result==0xffffffff,(root,mode,octave,tran,result)
        print('[ok] Harmony NOTE inherits register before TRAN/scale, signed bounds, and live absolute-root capture')
    print(f'[ok] {cases} Follow register/TRAN/bounds cases, absolute source capture, chains, independent settings and UI clamps')

def ui():
    """Execute stock drawing into a modal surface; check pixels, not call arguments."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'emu'))
    from lcd_view import png
    m=Machine(); u=m.uc; s=m.sym
    m.instruction_limit=lambda name: 200000 if name=='bf_page_draw' else 20000
    win=m.scratch; plane=win+0x1000
    u.mem_write(win+36,struct.pack('>IIII',120,60,2,plane))
    u.mem_write(s['bf_page_win'],win.to_bytes(4,'big'))
    m.follow_write('source',b'\x02',0)
    assert bytes(m.follow_read('response',8,0))==bytes(8),'TRIG must default on all tracks'
    out=Path(__file__).resolve().parents[2]/'out/follow-ui';out.mkdir(exist_ok=True)
    icons={}
    register_icons={};dials={0:set(),1:set(),2:set()};labels={}
    for mode,octaves in ((0,range(11)),(1,range(11)),(2,range(-2,3))):
        for octave in octaves:
            for response in (0,1):
                m.follow_write('mode',bytes((mode,)),0)
                m.follow_write(('fixed','home','offset')[mode],bytes((octave&255,)),0)
                m.call('bf_response_set',0,response)
                octtext=f'+{octave}' if mode==2 and octave>0 else str(octave)
                for formatter,value,want in (('bf_dial_oct_format',0,octtext),
                                             ('bf_mode_format',mode,('FIXED','GRAV','SOURCE')[mode]),
                                             ('bf_response_format',response,('TRIG','LIVE')[response])):
                    u.mem_write(m.stack+4,struct.pack('>II',win+512,value))
                    m.call(formatter)
                    assert bytes(u.mem_read(win+512,16)).split(b'\0')[0].decode()==want
                m.call('bf_page_draw')
                data=bytes(u.mem_read(plane,960))
                def pixel(x,y): return (data[x*8+y//8]>>(7-y%8))&1
                def crop(x,y,w,h): return tuple(pixel(i,j) for j in range(y,y+h) for i in range(x,x+w))
                # Full stock dials share their text and artwork baselines.
                # Measure actual value ink, excluding the dial beneath it.
                rfol=[(x,y) for x in range(1,39) for y in range(32,38) if pixel(x,y)]
                octink=[(x,y) for x in range(79,117) for y in range(32,38) if pixel(x,y)]
                assert octink,(mode,octave,'missing octave')
                assert {y for x,y in octink}=={y for x,y in rfol},(mode,octave,'baseline')
                assert abs(min(x for x,y in octink)+max(x for x,y in octink)-194)<=2,(mode,octave,'center')
                assert any(crop(92,38,11,13)), 'octave dial missing'
                assert any(crop(14,38,11,13)), 'source dial missing'
                dials[mode].add(crop(92,38,11,13))
                register_icons[mode]=crop(50,43,17,7)
                labels[mode]=crop(79,52,38,6)
                assert not any(crop(1,31,37,1)), 'source touches divider'
                assert not any(crop(79,31,38,1)), 'octave touches divider'
                assert not any(crop(1,29,37,1)), 'UPDT touches divider'
                assert not any(crop(1,58,37,2)), 'source label clips top'
                assert not any(crop(79,58,38,2)), 'octave label clips top'
                assert not any(crop(40,0,38,30)), 'unused E cell must be empty'
                assert not any(crop(79,0,38,30)), 'unused F cell must be empty'
                for x in (39,78):
                    assert any(crop(x,1,1,28)), 'six-cell grid needs both lower dividers'
                    assert any(crop(x,32,1,26)), 'six-cell grid needs both upper dividers'
                # Three-position REG and two-position UPDT remain separate.
                icon=crop(11,12,17,7)
                assert any(icon),'switch missing'
                icons[response]=icon
                name=f'{("fixed","grav","source")[mode]}-{octave}-{"trig" if response==0 else "live"}'
                rows=[[0]*128 for _ in range(64)]
                for y in range(60):
                    for x in range(120): rows[y+2][x+4]=pixel(x,59-y)
                png(rows,out/(name+'.png'))
    assert icons[0]!=icons[1],'switch must show selected position'
    assert len(set(register_icons.values()))==3,'REG must show three distinct positions'
    assert [len(dials[i]) for i in range(3)]==[11,11,5],'dial needles must reflect each value'
    assert labels[0]==labels[1] and labels[1]!=labels[2],'OCT/OFFS label follows REG'
    print('[ok] 54 native FOLLOW renders: stock dials, centered signed values, three-position REG and two-position UPDT; TRIG default on eight tracks')

if __name__=='__main__':
    main()
    ui()
