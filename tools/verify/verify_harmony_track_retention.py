#!/usr/bin/env python3
"""Execute track-local retention, scoped native clears and interrupted saves.

Independent Python encoding checks every step's physical address and lane
header. Only native UI notifications are stubbed in the clear test; the
installed edit/clear bodies, SRAM protection and retention are executed.
"""
import json
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.m68k_const import *
from verify_harmony_degree_files import Files, BANK, STRIDE
from verify_harmony_degree_packed import oracle, mirror
from verify_midi_sram import BASE, OFFSETS, SIZE
from harmony_midi_machine import ROOT, InterruptMaskTrace
import harmony_retained as retained


def fnv(data):
    h=0x811c9dc5
    for b in data:h=((h^b)*0x1000193)&0xffffffff
    return h


def encode(payload, bank=0, ticket=1, status=1):
    if len(payload)==10368:
        payload=payload+(bytes(32)+bytes((0,7,0,3,1)))*128
    result=bytearray()
    for lane in range(128):
        p=payload[lane*81:(lane+1)*81]
        a=payload[10368+lane*37:10368+(lane+1)*37]
        header=bytes((2,p[0],status))+ticket.to_bytes(4,'big')
        header+=fnv(bytes((bank,lane))+header+p+a).to_bytes(4,'big')
        header+=a[32:36]+bytes((a[36]<<4,))
        meta=int.from_bytes(header,'big')>>2
        tokens=int.from_bytes(p[1:],'big')
        for step in range(64):
            top=2 if step==0 else (meta>>(2*(63-step)))&3
            token=(tokens>>(10*(63-step)))&1023
            amount=(a[step//2]>>(0 if step%2 else 4))&15
            result.extend(((top<<14)|(amount<<10)|token).to_bytes(2,'big'))
    return bytes(result)


def header(data,lane=0):
    words=[int.from_bytes(data[i:i+2],'big') for i in range(lane*128,(lane+1)*128,2)]
    n=0
    for word in words[1:]:n=(n<<2)|(word>>14)
    return (n<<2).to_bytes(16,'big')


def main():
    m=Files();u=m.uc;s=m.sym
    m.call('ch_lock_init')
    roots,qualities=m.seed()
    # Exercise ALL 765 legal degree/chord pairs, including independent unlocks.
    roots=bytearray(roots);qualities=bytearray(qualities)
    for lane in range(128):
        for step in range(64):
            token=(lane*64+step)%765;d,q=divmod(token,9)
            d=255 if d==84 else d;q=255 if q==8 else q
            roots[lane*131+step]=d;roots[lane*131+64+step]=mirror(d)
            qualities[lane*64+step]=q
            u.mem_write(BANK+(lane//8)*0x8ed8+0x4900+(lane%8)*0x8b0+step*32,bytes((mirror(d),)))
    u.mem_write(s['hd_banks'],bytes(roots));u.mem_write(s['ch_lock_table'],bytes(qualities))
    m.sym['native_copy']=0x40020898
    m.c('native_copy',BASE,BANK,STRIDE)
    guard=bytes((i*13)%251 for i in range(0x7a00))
    u.mem_write(0x100f8600,guard)
    before=bytes(u.mem_read(BASE,SIZE))
    m.c('hd_nv_save_c',0)
    expected_payload=oracle(bytes(u.mem_read(s['hd_banks'],16768)),qualities)
    snapshot=retained.snapshot(m);h=header(snapshot)
    assert snapshot==encode(expected_payload,0,int.from_bytes(h[3:7],'big'),h[2])
    after=bytes(u.mem_read(BASE,SIZE));pads=set(OFFSETS)
    assert all(a==b for i,(a,b) in enumerate(zip(before,after)) if i not in pads)
    assert bytes(u.mem_read(0x100f8600,len(guard)))==guard
    u.mem_write(s['hd_banks'],b'\xcc'*16768);u.mem_write(s['ch_lock_table'],b'\xcc'*8192)
    assert m.c('hd_nv_restore_c',0)==1
    assert oracle(bytes(u.mem_read(s['hd_banks'],16768)),bytes(u.mem_read(s['ch_lock_table'],8192)))==expected_payload
    print('[ok] all 765 legal tuples mapped to their own steps; dense restore; native/PLOCKS/Scenes guards',flush=True)

    # A damaged lane cannot partially publish any other lane. Wrong bank,
    # track swaps and a valid older lane from another generation also reject.
    before_roots=bytes(u.mem_read(s['hd_banks'],16768));before_q=bytes(u.mem_read(s['ch_lock_table'],8192))
    corruptions=[]
    for lane in range(128):
        bad=bytearray(snapshot);bad[lane*128+127]^=1;corruptions.append(bad)
    bad=bytearray(snapshot);bad[:128],bad[128:256]=bad[128:256],bad[:128];corruptions.append(bad)
    old=encode(expected_payload,0,int.from_bytes(h[3:7],'big')-1,h[2])
    bad=bytearray(snapshot);bad[127*128:]=old[127*128:];corruptions.append(bad)
    # Valid checksums must not make illegal musical tokens acceptable.
    for state,token in ((0,0),(1,0),(2,765),(2,1023)):
        p=bytearray(expected_payload);p[0]=state*84
        packed=int.from_bytes(p[1:81],'big')
        p[1:81]=((packed & ((1<<630)-1)) | (token<<630)).to_bytes(80,'big')
        corruptions.append(encode(p,0,int.from_bytes(h[3:7],'big'),h[2]))
    for bad in corruptions:
        retained.install(m,bad)
        assert m.c('hd_nv_restore_c',0)==0
        assert bytes(u.mem_read(s['hd_banks'],16768))==before_roots
        assert bytes(u.mem_read(s['ch_lock_table'],8192))==before_q
    retained.install(m,snapshot);assert m.c('hd_nv_restore_c',1)==0
    print('[ok] corruption in every track, swapped tracks and mixed generations reject before publication',flush=True)

    # Clear actual first/middle/last MIDI tracks, restore, and verify scope.
    for addr in (0x40027e00,0x400339d8,0x4009da20):u.mem_write(addr,b'\x4e\x75')
    for lane in (0,59,127):
        m.seed();m.c('native_copy',BASE,BANK,STRIDE);m.c('hd_nv_save_c',0)
        old_q=bytearray(u.mem_read(s['ch_lock_table'],8192))
        old_roots=bytearray(u.mem_read(s['hd_banks'],16768))
        m.sym['clear_native']=0x40039b00
        m.c('clear_native',lane//8,lane%8,1)
        m.c('hd_nv_poll_c')
        u.mem_write(s['hd_banks'],b'\xcc'*16768);u.mem_write(s['ch_lock_table'],b'\xcc'*8192)
        assert m.c('hd_nv_restore_c',0)==1
        now_q=bytes(u.mem_read(s['ch_lock_table'],8192));now_roots=bytes(u.mem_read(s['hd_banks'],16768))
        old_q[lane*64:(lane+1)*64]=b'\xff'*64
        assert now_q==old_q
        for other in range(128):
            want=b'\xff'*64 if other==lane else old_roots[other*131:other*131+64]
            assert now_roots[other*131:other*131+64]==want,(lane,other)
        words=retained.snapshot(m)[lane*128:(lane+1)*128]
        assert all(int.from_bytes(words[i:i+2],'big')&1023==764 for i in range(0,128,2))
    print('[ok] native clear first/middle/last track removes its Harmony locks across restore; other lanes intact',flush=True)

    # A preempting saver cannot commit its buffer while the outer saver is
    # writing. Capture a torn checkpoint, then retry with the new last step.
    m.seed();m.c('hd_nv_save_c',0)
    last_ticket=int.from_bytes(header(retained.snapshot(m))[3:7],'big')
    watch=False;pending=False;interrupted=False;writes=0;torn=None
    trace=InterruptMaskTrace(u);addresses={BASE+o for o in OFFSETS}
    def written(uc,access,address,size,value,data):
        nonlocal pending,writes
        if watch and address in addresses and address!=BASE+OFFSETS[0]:
            assert trace.ipl==0,'bulk retained writes masked interrupts'
            assert not retained.committed(m),'bank published during bulk writes'
            writes+=1
            if not interrupted:pending=True
    def inspect(uc,pc,size,data):
        if watch:
            trace.before(pc)
            if pending:uc.emu_stop()
    u.hook_add(UC_HOOK_MEM_WRITE,written);u.hook_add(UC_HOOK_CODE,inspect)
    u.mem_write(m.stack,m.done.to_bytes(4,'big')+bytes(4))
    u.reg_write(UC_M68K_REG_A7,m.stack);u.reg_write(UC_M68K_REG_SR,0x2000)
    m.arrival=None;watch=True
    u.emu_start(s['hd_nv_save_c'],0,count=30000000)
    assert pending
    saved=u.context_save();torn=retained.snapshot(m);interrupted=True;pending=False;watch=False
    outer=m.stack;m.stack=0x4700c000
    m.c('ha_set_c',0,15,7,63,10)  # real ACC edit invalidates the in-flight bank
    u.mem_write(s['ch_lock_table']+8191,b'\x06')
    for _ in range(20):m.c('hd_nv_poll_c')
    m.c('hd_nv_save_c',0)
    assert not retained.committed(m)
    m.stack=outer;u.context_restore(saved);m.arrival=None;trace.ipl=0;watch=True
    u.emu_start(u.reg_read(UC_M68K_REG_PC),0,count=30000000);watch=False
    assert m.arrival==m.done and writes>8192
    finished=retained.snapshot(m)
    assert int.from_bytes(header(finished)[3:7],'big')==last_ticket+3,'UI polls created spurious generations'
    retained.install(m,torn)
    assert m.c('hd_nv_restore_c',0)==0
    retained.install(m,finished);u.mem_write(s['ch_lock_table']+8191,b'\xff')
    assert m.c('hd_nv_restore_c',0)==1 and u.mem_read(s['ch_lock_table']+8191,1)==b'\x06'
    assert m.c('ha_lock_c',0,15,7,63)==10
    result=dict(step_mapping='same pattern/track/step',legal_tuples=765,lanes=128,steps=8192,
        corruption_cases=len(corruptions),native_track_clear_restore=[0,59,127],
        preempting_save='retried',busy_ui_polls_coalesced=20,torn_snapshot_rejected=True,bulk_writes_unmasked=True,
        contiguous_sram_unchanged=True,hardware_tested=False)
    out=ROOT/'out/harmony-track-retention';out.mkdir(parents=True,exist_ok=True)
    (out/'machine.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
