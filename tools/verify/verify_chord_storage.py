#!/usr/bin/env python3
"""Linked CHRD table/retention/edit checks; no hardware proof."""
import json
import struct
import harmony_retained as retained
from pathlib import Path
from unicorn.m68k_const import *
import verify_midi_harmony as h
import verify_chord_play as c


def main():
    from verify_harmony_load_hooks import check
    check()
    h.symbols=c.symbols
    m=h.Machine();u=m.uc;s=m.sym;table=s['ch_lock_table']
    u.mem_write(0x46c82456,struct.pack('>I',0x400e21e0))
    m.call('ch_lock_init')
    assert bytes(u.mem_read(table,131072))==b'\xff'*131072
    def index(b,p,t,k):return ((b*16+p)*8+t)*64+k
    def setq(b,p,t,k,v):
        m.call('ch_lock_set',b,p,regs={UC_M68K_REG_D2:t,UC_M68K_REG_D3:k,UC_M68K_REG_D4:v})
    for b,p,t,k,q in ((0,0,0,0,1),(15,15,7,63,7),(3,7,5,27,4)):
        setq(b,p,t,k,q)
        assert u.mem_read(table+index(b,p,t,k),1)==bytes((q,))
        assert m.call('ch_lock_get',b,p,regs={UC_M68K_REG_D2:t,UC_M68K_REG_D3:k})==q
    before=bytes(u.mem_read(table,131072))
    for args in ((16,0,0,0,1),(0,16,0,0,1),(0,0,8,0,1),(0,0,0,64,1),(0,0,0,0,8),(0xffffffff,0,0,0,1)):
        setq(*args);assert bytes(u.mem_read(table,131072))==before,args
    setq(0,0,0,0,255)
    assert m.call('ch_lock_get',regs={UC_M68K_REG_D2:0,UC_M68K_REG_D3:0})==0
    # Full, dense bank: no sparse capacity loss with 8192 explicit locks.
    dense=bytes(i%8 for i in range(8192));u.mem_write(table+3*8192,dense)
    u.mem_write(s['ch_lock_status']+3,b'\x03')
    m.call('ch_nv_save',3)
    snapshot=retained.snapshot(m)
    u.mem_write(table+3*8192,b'\xff'*8192)
    u.mem_write(s['ch_lock_status']+3,b'\x00')
    assert m.call('ch_nv_restore',3)==1
    assert u.mem_read(s['ch_lock_status']+3,1)==b'\x03'
    assert bytes(u.mem_read(table+3*8192,8192))==dense
    for pos in (0,4,8,12,16,24,28,32,8223):
        corrupt=bytearray(snapshot);corrupt[pos]^=0x80
        retained.install(m,corrupt);u.mem_write(table+3*8192,b'\x05'*8192)
        assert m.call('ch_nv_restore',3)==0,pos
        assert bytes(u.mem_read(table+3*8192,8192))==b'\x05'*8192
    retained.install(m,snapshot)
    assert m.call('ch_nv_restore',4)==0
    # Current-bank edits update the retained snapshot, distant banks do not.
    setq(3,15,7,63,6)
    u.mem_write(table+3*8192+8191,b'\xff')
    assert m.call('ch_nv_restore',3)==1
    assert u.mem_read(table+3*8192+8191,1)==b'\x06'
    snapshot=retained.snapshot(m);setq(1,0,0,0,2)
    assert retained.snapshot(m)==snapshot
    # Failed native saves must not copy corrupt work over the stored backup.
    for bank in range(16):
        for status in range(5):
            u.mem_write(s['ch_lock_status']+bank,bytes((status,)))
            for suffix in ('work','strd'):
                u.mem_write(m.scratch,f'/SET/PROJECT/bank{bank+1:02d}.{suffix}\0'.encode())
                result=m.call('ch_copy_guard',regs={UC_M68K_REG_A0:m.scratch})
                assert result==(0xfffffff9 if suffix=='work' and status>=2 else 0),(bank,status,suffix,result)
    for name in ('project.work','bank00.work','bank17.work','bank01.work.old','bankAA.work'):
        u.mem_write(m.scratch,name.encode()+b'\0')
        assert m.call('ch_copy_guard',regs={UC_M68K_REG_A0:m.scratch})==0,name
    # Native copy/undo boundaries; assert the dedicated copy before stock runs.
    def call_args(name,args,stop):
        u.mem_write(m.stack+4,b''.join(struct.pack('>I',a) for a in args))
        m.call(name,stop=stop)
    pat0=0x400e21e0;pat1=pat0+0x8ed8
    payload=bytes(i%9 if i%9<8 else 255 for i in range(512))
    u.mem_write(table,payload)
    call_args('ch_memcpy',[0x460c8122,pat0,0x8ed8],0x40020898)
    call_args('ch_memcpy',[pat1,0x460c8122,0x8ed8],0x40020898)
    assert bytes(u.mem_read(table+512,512))==payload
    call_args('ch_memcpy',[0x460bf218,pat1,0x8ed8],0x40020898)
    u.mem_write(table+512,b'\xff'*512)
    call_args('ch_memcpy',[pat1,0x460bf218,0x8ed8],0x40020898)
    assert bytes(u.mem_read(table+512,512))==payload
    src=pat0+0x48d0+2*0x8b0;dst=pat1+0x48d0+5*0x8b0
    call_args('ch_memcpy',[0x460c8122,src,0x8b0],0x40020898)
    call_args('ch_memcpy',[dst,0x460c8122,0x8b0],0x40020898)
    assert bytes(u.mem_read(table+512+5*64,64))==payload[128:192]
    call_args('ch_clear_locks',[1,5,2,0x8001],0x40040d4c)
    assert u.mem_read(table+512+5*64+32,1)==b'\xff'
    assert u.mem_read(table+512+5*64+47,1)==b'\xff'
    call_args('ch_clear_track',[1,5,1],0x40039b08)
    assert bytes(u.mem_read(table+512+5*64,64))==b'\xff'*64
    print('[ok] CHRD indices, invalid input guards, dense CS1 retention, corruption rejection, rejected-save backup protection, pattern/track copy and undo, clear')
    c.OUT.mkdir(parents=True,exist_ok=True)
    (c.OUT/'storage-machine.json').write_text(json.dumps({'dense_locks':8192,'nv_corruption_cases':9,'copy_guard_cases':165,'copy_clear':'passed'},indent=2)+'\n')

if __name__=='__main__':main()
