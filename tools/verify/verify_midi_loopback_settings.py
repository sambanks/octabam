#!/usr/bin/env python3
"""Linked native Part destinations, Follow flag composition and held-note cleanup."""
import re
import subprocess
import verify_midi_loopback as lb
from unicorn.m68k_const import UC_M68K_REG_D0, UC_M68K_REG_D1

B, BS, PS = 0x400e21e0, 0x9b340, 0x18b2


def field(bank, part, track):
    return B + bank*BS + 0x8ed80 + part*PS + 0x4e2 + track*36 + 12


def main():
    m=lb.Machine()
    raw=subprocess.check_output(['m68k-elf-nm', str(lb.ROOT/'out/platform/runtime/runtime.elf')],text=True)
    m.sym.update({n:int(a,16) for a,n in re.findall(r'^([0-9a-f]+) [TtBb] (\w+)$',raw,re.M)})
    m.put(0x46c82456,B)
    m.call('lb_part_sync')
    def call(name,track,value=0):
        return m.call(name,regs={UC_M68K_REG_D0:track,UC_M68K_REG_D1:value})
    # All UI Parts and tracks; unrelated bits and selected/playing separation.
    for bank in (0,15):
        m.put(0x46c82456,B+bank*BS)
        for part in range(4):
            m.put(0x100b14cf,part,1)
            for track in range(8):
                for flags in range(4):
                    m.put(field(bank,part,track),flags,1)
                    m.put(0x100a4ece+part*PS+0x4e2+track*36+12,flags,1)
                    for route in range(3):
                        assert call('lb_dest_set',track,route)==1
                        assert call('lb_dest_get',track)==route
                        assert m.get(field(bank,part,track),1)==flags+4*route
                        if bank==0:
                            assert m.get(0x100a4ece+part*PS+0x4e2+track*36+12,1)==flags+4*route
    before=m.get(field(15,3,7),1)
    for track,value in ((8,1),(0xffffffff,1),(7,3),(7,0xffffffff)):
        assert call('lb_dest_set',track,value)==0
    assert m.get(field(15,3,7),1)==before
    for value in (12,15,16,127,255):
        m.put(field(15,3,0),value,1)
        assert call('lb_dest_get',0)==0
    print('[ok] every track/Part, first/last bank, packed flags, native mirror, bounds and invalid-data EXT fallback')
    m.put(0x46c82456,B);m.put(0x100b14cf,0,1)
    if 'bf_mode_set' in m.sym:
        for route in range(3):
            call('lb_dest_set',0,route)
            for mode in range(2):
                for response in range(2):
                    call('bf_mode_set',0,mode);call('bf_response_value_set',0,response)
                    assert call('lb_dest_get',0)==route
                    assert m.get(field(0,0,0),1)==route*4+mode+response*2
        print('[ok] Follow MODE/UPDT edits preserve DEST; DEST preserves both Follow flags')
    # Sounding Part is independent of the UI. Changes release the old route.
    m.put(0x80001832,1,1)
    m.put(field(0,1,0),4,1)
    m.call('lb_part_sync')
    assert m.get('lb_routes',1)==1
    m.capture((0x90,84,100));assert m.next()==bytes((0x90,84,100))
    call('lb_dest_set',0,0)
    assert m.get('lb_internal_held')==1, 'editing another Part released the playing Part'
    m.put(0x80001832,0,1);m.call('lb_part_sync')
    assert m.next()==bytes((0x80,84,0))
    assert m.get('lb_internal_held')==0 and m.get('lb_routes',1)==0
    assert m.capture((0x80,84,0),0x4009f8c2)==0
    # Same-slot native recall changes the epoch and must also release notes.
    call('lb_dest_set',0,1)
    m.capture((0x90,85,100));assert m.next()==bytes((0x90,85,100))
    work=B+0x8ed80
    m.u.mem_write(0x47004000,bytes(m.u.mem_read(work,PS)))
    m.call('mp_native_copy',(work,0x47004000,PS));m.call('lb_part_sync')
    assert m.next()==bytes((0x80,85,0))
    assert m.get('lb_internal_held')==0
    print('[ok] playing context separation, Part switch and same-slot recall release original destinations without duplicate offs')
    # Exact formatter output and bounded strings, including CHAN OFF.
    m.put(0x100b14cc,0,1)
    for route,suffix in enumerate(('', 'I', 'B')):
        call('lb_dest_set',0,route)
        for channel in (0,1,16):
            m.u.mem_write(lb.MSG,b'?'*16)
            m.call('lb_channel_format',(lb.MSG,channel))
            expected=('OFF' if channel==0 else str(channel))+suffix
            assert bytes(m.u.mem_read(lb.MSG,len(expected)+2))==expected.encode()+b'\0?'
    print('[ok] CHAN formatter OFF/1/16 and I/B markers stay within their output buffer')


if __name__=='__main__':main()
