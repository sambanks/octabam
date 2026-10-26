#!/usr/bin/env python3
"""Linked-code tests for the Follow TRIG/LIVE update control."""
import argparse
from midi_machine import Machine
from unicorn import UC_HOOK_CODE
from unicorn.m68k_const import UC_M68K_REG_A7,UC_M68K_REG_A2,UC_M68K_REG_D4,UC_M68K_REG_D7


def fixture(pitches=(36,), response=1, receiver=1, source=0):
    m=Machine();u=m.uc;s=m.sym;m.events=[]
    u.mem_write(0x46c78152,b'\xff'*2048)
    u.mem_write(0x46c77a16,b'\xff'*256)
    m.follow_write('source',bytes((source+1,)),receiver)
    u.mem_write(s['bf_roots']+source,b'\x24')
    u.mem_write(s['bf_pitches']+source,b'\x3c')
    u.mem_write(0x46c76fe0+receiver*32+12,b'\x40')
    u.mem_write(0x46c76de0+receiver*68,bytes((receiver+1,)))
    u.mem_write(0x400d807e,b'\x5b')
    u.mem_write(0x46c7a7f0+receiver*4,(37).to_bytes(4,'big'))
    u.mem_write(0x40010bc8,bytes.fromhex('4e75'))
    def send(u,pc,size,data):
        sp=u.reg_read(UC_M68K_REG_A7)
        count=int.from_bytes(u.mem_read(sp+4,4),'big')
        ptr=int.from_bytes(u.mem_read(sp+8,4),'big')
        assert count==3
        m.events.append(tuple(u.mem_read(ptr,3)))
    u.hook_add(UC_HOOK_CODE,send,begin=0x40010bc8,end=0x40010bc8)
    for slot,pitch in enumerate(pitches):
        at=0x46c77a16+receiver*32+slot*8
        u.mem_write(at,((0xffffff90+receiver)&0xffffffff).to_bytes(4,'big')+pitch.to_bytes(4,'big'))
        u.mem_write(0x46c78152+receiver*128+pitch,bytes((receiver*4+slot,)))
    m.call('bf_response_set',receiver,response)
    m.call('bf_response_tick',1<<receiver,0)
    u.mem_write(m.scratch,b'\x24')
    m.call('bf_response_observe',regs={UC_M68K_REG_D7:receiver,UC_M68K_REG_D4:0,UC_M68K_REG_A2:m.scratch})
    def change(pitch=65,mask=0,mute=0):
        u.mem_write(s['bf_roots']+source,bytes((36+pitch%12,)))
        u.mem_write(s['bf_pitches']+source,bytes((pitch,)))
        m.call('bf_response_tick',mask,mute)
        assert int.from_bytes(u.mem_read(0x46c7a7f0+receiver*4,4),'big')==37,'length changed'
        return m.events
    m.change=change
    return m


def machine():
    m=fixture();assert m.change()==[(0x91,36,0),(0x91,41,91)]
    assert int.from_bytes(m.uc.mem_read(0x46c77a3a,4),'big')==41
    assert m.uc.mem_read(0x46c78152+128+36,1)==b'\xff'
    assert m.uc.mem_read(0x46c78152+128+41,1)==b'\x04'
    assert m.change()==[(0x91,36,0),(0x91,41,91)]
    assert m.change(67)[-2:]==[(0x91,41,0),(0x91,43,91)]
    assert fixture(response=0).change()==[]
    assert fixture(pitches=()).change()==[]
    for bit in (1,1<<8,1<<16):assert fixture().change(mask=bit<<1)==[]
    assert fixture().change(mute=2)==[]
    m=fixture();assert m.change(65,mute=2)==[]
    assert m.change(67)==[(0x91,36,0),(0x91,43,91)],'muted root must not move the sounding anchor'
    for addr,value in ((0x80006677,255),(0x8000666f,255),(0x46c76de0+68,0)):
        m=fixture();m.uc.mem_write(addr,bytes((value,)));assert m.change()==[]
    m=fixture(pitches=(36,40,43))
    assert m.change()==[(0x91,36,0),(0x91,40,0),(0x91,43,0),(0x91,41,91),(0x91,45,91),(0x91,48,91)]
    m=fixture(pitches=(36,41))
    assert m.change()==[(0x91,36,0),(0x91,41,0),(0x91,41,91),(0x91,46,91)]
    m=fixture();m.uc.mem_write(0x46c78152+128+41,b'\x08')
    assert m.change()==[(0x91,36,0)]
    assert m.uc.mem_read(0x46c78152+128+41,1)==b'\x08'
    m=fixture();m.uc.mem_write(0x46c78152+128+36,b'\x20');assert m.change()==[]
    m=fixture(pitches=(125,));assert m.change()==[(0x91,125,0)]
    for receiver in range(8):
        source=(receiver+1)%8;m=fixture(receiver=receiver,source=source)
        assert m.change()==[(0x90+receiver,36,0),(0x90+receiver,41,91)]
    m=fixture();s=m.sym
    m.follow_write('source',b'\x03',1)
    m.follow_write('source',b'\x01',2)
    assert m.change()==[(0x91,36,0),(0x91,41,91)],'ultimate source chain'
    m=fixture();assert m.change(72)==[],'FIXED ignores source octaves'
    m=fixture(pitches=(60,));s=m.sym
    m.follow_write('mode',b'\x02',1)
    m.call('bf_response_observe',regs={UC_M68K_REG_D7:1,UC_M68K_REG_D4:0,UC_M68K_REG_A2:m.scratch})
    assert m.change(72)==[(0x91,60,0),(0x91,72,91)]
    m=fixture();m.uc.mem_write(0x46c76fe0+32+12,b'\x47')
    assert m.change(60)==[],'TRAN edit alone is not a root change'
    assert m.change(65)==[(0x91,36,0),(0x91,48,91)]
    m=fixture();s=m.sym
    m.call('bf_response_set',1,0);m.call('bf_response_set',1,1)
    assert m.change()==[],'setting switch must arm at next ordinary trig'
    m.call('bf_response_observe',regs={UC_M68K_REG_D7:1,UC_M68K_REG_D4:0,UC_M68K_REG_A2:m.scratch})
    assert m.change(67)==[],'arp-only output cannot arm an unknown cached pool'
    # New Parts and same-slot native replacement must not retune old voices.
    # An unrelated Part replacement must leave this receiver's anchor intact.
    from verify_store_part_settings import symbols, B, PS
    for operation in ('switch','replace','unrelated'):
        m=fixture();m.sym.update(symbols());u=m.uc
        part0=B+0x8ed80
        source=0x47002000
        u.mem_write(source,bytes(u.mem_read(part0,PS)))
        if operation=='switch':
            u.mem_write(part0+PS,bytes(u.mem_read(part0,PS)))
            u.mem_write(0x80006676+1,b'\x01')
        else:
            dest=part0+(3*PS if operation=='unrelated' else 0)
            u.mem_write(m.stack+4,b''.join(v.to_bytes(4,'big') for v in (dest,source,PS)))
            m.call('store_part_native_copy')
        events=m.change()
        if operation=='unrelated':
            assert events==[(0x91,36,0),(0x91,41,91)]
        else:
            assert events==[],operation
            assert int.from_bytes(u.mem_read(0x46c77a3a,4),'big')==36,'old release pitch changed'
    print('[ok] Part switch/same-slot replacement disarm LIVE until a native trig; unrelated Parts preserve held response')
    print('[ok] TRIG identity; LIVE held root/voices, repeated roots, rests, scheduled edges, mute/enable/channel gates, ownership collisions, MIDI bounds, all receivers and unchanged release deadlines')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('remix',nargs='?');ap.parse_args()
    machine()
