#!/usr/bin/env python3
"""Execute the linked accumulator, independent boundary oracle and real file hooks.

The native filesystem boundary is substituted here, not the codec or saver.
Full-firmware panel/UART/card journeys live in the accompanying port gate.
"""
import json
import struct
import sys
from unicorn import UC_HOOK_CODE
from verify_harmony_degree_files import Files
from verify_harmony_track_retention import encode, header
from verify_harmony_degree_packed import oracle
from verify_harmony_degree_files import fnv
from unicorn.m68k_const import UC_M68K_REG_D7, UC_M68K_REG_A7, UC_M68K_REG_PC, UC_M68K_REG_D1, UC_M68K_REG_A0, UC_M68K_REG_A1, UC_M68K_REG_A5
import harmony_retained as retained
from verify_harmony_degree_integration import symbols

BANK=0x400e21e0


def machine():
    """Harmony-only fixture; this gate must not require optional PLOCKS."""
    m=Files();u=m.uc
    m.call('ch_lock_init')
    u.mem_write(BANK,b'\xff'*0x9b340)
    for pattern in range(16):u.mem_write(BANK+pattern*0x8ed8+0x8e57,b'\0')
    for part in range(8):
        base=BANK+(0x8ed80+part*0x18b2 if part<4 else 0x9504a+(part-4)*0x18b2)
        for track in range(8):
            u.mem_write(base+0x3e2+track*32,b'\x30')
            for field,value in ((3,0),(5,2),(16,0),(17,1),(18,0),(19,35)):
                u.mem_write(base+0x4e2+track*36+field,bytes((value,)))
    m.call('hd_bank_loaded',0)
    return m


def c_minor_follow(m):
    """Check the generated pool, including Follow's effective KEY and CHRD."""
    u,s=m.uc,m.sym
    if 'bf_pitches' not in s:
        print('[N/A] C minor Follow examples require the combined image',flush=True)
        return
    part=BANK+0x8ed80+0x4e2
    u.mem_write(part+17,b'\x02')       # Source T1 KEY C minor.
    u.mem_write(part+36+3,b'\x01')    # Follower T2 RFOL T1.
    u.mem_write(part+36+5,b'\x01')    # Follower HARM NOTE.
    u.mem_write(part+36+17,b'\x01')   # Its own KEY is C major.
    assert m.c('hd_scale_c',0,0,1)==320
    minor={0,2,3,5,7,8,10}

    def generate():
        m.c('ha_fire_c',0,0,1,0)
        u.mem_write(m.scratch,b'\x24'*4)
        assert m.call('mh_generate',1,0,a0=m.scratch)==1
        notes=tuple(u.mem_read(m.scratch,4))
        m.c('ha_sounded_c',1)
        return notes

    count=0
    for mode in range(3):                 # FIXED, GRAV, SOURCE.
        u.mem_write(part+36+15,bytes(((mode<<4)|3,)))
        for amount in (1,2,-1):
            m.c('ha_bank_reset_c',0)
            m.c('ha_set_c',0,0,1,0,amount+9 if amount<0 else amount+8)
            for root in (48,51,55,56,58,52):  # Last root is chromatic E.
                m.c('ha_runtime_reset_c')
                m.c('bf_reset_c')
                u.mem_write(s['bf_pitches'],bytes((root,)))
                u.mem_write(s['bf_roots'],bytes((root,)))
                for _ in range(5):
                    note=generate()[0]
                    assert note%12 in minor,(mode,amount,root,note)
                    count+=1

    # The follower uses the source KEY. A C-major or KEY OFF source yields
    # E natural even when the follower's own KEY says C minor.
    u.mem_write(part+36+15,b'\x03')
    u.mem_write(part+36+17,b'\x02')
    u.mem_write(s['bf_pitches'],b'\x30')
    u.mem_write(s['bf_roots'],b'\x30')
    m.c('ha_bank_reset_c',0)
    m.c('ha_set_c',0,0,1,0,9)
    for source_key,expected in ((2,(48,50,51,53,55)),
                                (1,(48,50,52,53,55)),
                                (0,(48,50,52,53,55))):
        u.mem_write(part+17,bytes((source_key,)))
        m.c('ha_runtime_reset_c')
        assert tuple(generate()[0] for _ in range(5))==expected,source_key

    # Scale-relative TRI stays in C minor. Explicit MAJ intervals retain
    # their chromatic notes on C and D, while E-flat major fits the scale.
    u.mem_write(part+17,b'\x02')
    u.mem_write(part+36+5,b'\x02')
    for quality,expected in (
            (0,((48,51,55,48),(50,53,56,50),(51,55,58,51))),
            (5,((48,52,55,48),(50,54,57,50),(51,55,58,51)))):
        u.mem_write(s['ch_current']+1,bytes((quality,)))
        m.c('ha_runtime_reset_c')
        assert tuple(generate() for _ in range(3))==expected,quality
    print(f'[ok] C minor Follow: {count} NOTE outputs in scale; source KEY and explicit CHRD behavior',flush=True)

    # A CHORD source may sound a ninth or an explicit chromatic dominant
    # third. Follow publishes only its logical degree:oct root, so neither
    # generated voice nor dormant native NOT2-4 may seed a follower slot.
    if 'bf_latch_extra' not in s:
        print('[N/A] CHORD-source extension handoff requires the combined image',flush=True)
        return
    u.mem_write(part+5,b'\x02')
    u.mem_write(part+36+17,b'\x01')
    source_lane=0x47002000
    u.mem_write(source_lane+0x220,bytes((48,90,6,68,71,76)))
    u.mem_write(source_lane+0x22c,b'\x40')
    source_chords={0:(48,51,55,48),2:(48,51,55,62),7:(48,52,55,58)}
    follower_chords={1:((48,)*4,(50,)*4),
                     2:((48,51,55,48),(50,53,56,50))}
    for follower_mode,expected in follower_chords.items():
        u.mem_write(part+36+5,bytes((follower_mode,)))
        u.mem_write(s['ch_current']+1,b'\0') # Follower chooses its own TRI.
        for quality,source_expected in source_chords.items():
            m.c('ha_bank_reset_c',0)
            m.c('ha_set_c',0,0,1,0,9) # Follower ACC +1 scale degree.
            m.c('ha_runtime_reset_c')
            m.c('bf_reset_c')
            u.mem_write(s['bf_pitches'],b'\x30')
            u.mem_write(s['bf_roots'],b'\x30')
            u.mem_write(s['ch_current'],bytes((quality,)))
            u.mem_write(m.scratch,b'\x30'*4)
            assert m.call('mh_generate',0,0,a0=m.scratch)==1
            assert tuple(u.mem_read(m.scratch,4))==source_expected,quality
            u.mem_write(s['bf_intervals'],bytes((4,7,12)))
            m.call('bf_latch_extra',regs={UC_M68K_REG_D7:0,UC_M68K_REG_A5:source_lane})
            assert bytes(u.mem_read(s['bf_intervals'],3))==b'\x80'*3,quality
            actual=tuple(generate() for _ in range(2))
            assert actual==expected,(follower_mode,quality,actual)
    print('[ok] C minor CHORD source: TRI/ADD9/DOM7 voices stay local; NOTE/CHORD followers use root and own ACC +1',flush=True)


def main():
    m=machine();u=m.uc;s=m.sym
    if '--negative-control' in sys.argv:
        def no_advance(uc,pc,size,data):
            if pc==s['ha_sounded_c']:
                sp=uc.reg_read(UC_M68K_REG_A7)
                uc.reg_write(UC_M68K_REG_PC,int.from_bytes(uc.mem_read(sp,4),'big'))
                uc.reg_write(UC_M68K_REG_A7,sp+4)
        u.hook_add(UC_HOOK_CODE,no_advance)
    u.mem_write(0x46c82456,BANK.to_bytes(4,'big'))
    u.mem_write(0x100b14cc,b'\0');u.mem_write(0x100b14d0,b'\0')
    tones=(0,2,4,5,7,9,11)
    def pitch(offset):
        octave,degree=divmod(offset,7)
        return 48+12*octave+tones[degree]
    def setting(lo,hi,boundary=0,reset=3,base=1):
        m.c('ha_bank_reset_c',0);m.c('ha_runtime_reset_c')
        u.mem_write(s['ha_lanes']+32,bytes((lo&255,hi,boundary,reset,base)))
    def event(step=0,sound=True,repeats=1):
        m.c('ha_fire_c',0,0,0,step)
        value=m.c('ha_shift_c',48,0,0)
        if sound:
            for _ in range(repeats):m.c('ha_sounded_c',0)
        # A pool rebuild after output still uses this trig's captured offset.
        assert m.c('ha_shift_c',48,0,0)==value
        return value
    # UI and saved bounds share the same three-octave limits.
    setting(0,7)
    assert m.c('ha_setting_c',0,0,0)==0
    assert m.c('ha_setting_c',0,1,0)==7
    assert m.c('ha_setting_c',0,0,-1000)&255==235
    assert m.c('ha_setting_c',0,1,1000)==21
    assert m.c('ha_setting_c',0,0,1000)==0
    assert m.c('ha_setting_c',0,1,-1000)==0
    for low,high,valid in ((-21,21,1),(-22,21,0),(-21,22,0)):
        setting(low,high)
        assert m.c('ha_valid_c',s['ha_lanes'])==valid,(low,high)
    print('[ok] three-octave UI/storage caps and unchanged defaults',flush=True)
    counts=0
    for mode in range(4):
        for lo,hi in ((0,0),(0,1),(-1,0),(-1,1),(-7,7),(-21,21)):
            for amount in (*range(-7,0),*range(1,8)):
                setting(lo,hi,mode)
                m.c('ha_set_c',0,0,0,0,amount+9 if amount<0 else amount+8)
                current=0;direction=1
                for _ in range(32):
                    result=event(repeats=4)
                    want=pitch(current)
                    assert result==(want if 0<=want<=127 else 0xffffffff),(mode,lo,hi,amount,current,result,want)
                    n=current+amount*direction
                    if lo==hi:n=lo
                    elif not lo<=n<=hi:
                        if mode==0:n=lo+(n-lo)%(hi-lo+1)
                        elif mode==1:
                            while not lo<=n<=hi:
                                n=2*hi-n if n>hi else 2*lo-n
                                direction=-direction
                        elif mode==2:n=max(lo,min(hi,n))
                        else:n=0
                    current=n;counts+=1
    print('[ok] independent boundary oracle:',counts,'outputs; arp repeats do not advance twice',flush=True)
    setting(0,7,base=9)
    assert event(sound=False)==48
    assert event()==48 and event()==50
    assert event(1)==48 and event(0)==52
    m.c('ha_set_c',0,0,0,0,1)
    assert event()==48 and event()==48
    m.c('ha_set_c',0,0,0,0,0)
    assert event()==48 and event()==50
    # START reads the incoming pattern policy; PAT and NONE have independent
    # contracts, and an unrelated step has its own phase/direction.
    setting(0,7,reset=1,base=9)
    assert event()==48 and event()==50
    m.c('ha_transport_c')
    assert event()==48
    setting(0,7,reset=0,base=9)
    assert event()==48 and event()==50
    m.c('ha_transport_c')
    assert event()==52
    for policy in range(4):
        setting(0,7,reset=policy,base=9)
        u.mem_write(s['ha_lanes']+8*37+32,bytes((0,7,0,policy,9)))
        assert event()==48 and event()==50
        m.c('ha_fire_c',0,1,0,0)
        assert m.c('ha_shift_c',48,0,0)==(48 if policy&2 else 52)
        m.c('ha_sounded_c',0)
        assert event()==(48 if policy&2 else 53)
        m.c('ha_transport_c')
        assert event()==(48 if policy&1 else 50 if policy&2 else 55)
    # Enter the installed firmware detour, not an uninstalled helper with the
    # same behavior. Both standalone Harmony and the Follow bridge must notify
    # every selected consumer exactly once.
    with_follow = 'bf_register_sent' in s
    events = {
        'start_a': (0x4009c3d4, 0x4009c3da),
        'start_b': (0x4009c4d4, 0x4009c4da),
        'sent_a': (0x4009fbb2, 0x4009fbb8),
        'sent_b': (0x4009fcfa, 0x4009fd00),
    }
    for name, (site, _) in events.items():
        expected = s[{'start_a':'seq_start','start_b':'seq_resume','sent_a':'seq_sent_a','sent_b':'seq_sent_b'}[name]]
        assert bytes(u.mem_read(site, 6)) == b'\x4e\xf9' + expected.to_bytes(4, 'big'), name
        s['installed_' + name] = site

    def installed(name, d0=0, regs=None, notify=True):
        callbacks = (['ha_transport_c'] if name.startswith('start') else ['ha_note_sent'])
        if with_follow:
            callbacks += ['bf_register_reset' if name.startswith('start') else 'bf_register_sent']
        counts = {symbol: 0 for symbol in callbacks}
        def count_callback(uc, pc, size, data):
            for symbol in callbacks:
                if pc == s[symbol]:
                    counts[symbol] += 1
        token = u.hook_add(UC_HOOK_CODE, count_callback)
        try:
            result = m.call('installed_' + name, d0, stop=events[name][1], regs=regs)
        finally:
            u.hook_del(token)
        assert counts == {symbol: int(notify) for symbol in callbacks}, (name, counts)
        return result

    for hook in ('start_a', 'start_b'):
        setting(0,7,reset=1,base=9)
        assert event()==48 and event()==50
        saved={UC_M68K_REG_D1:0x12345678,UC_M68K_REG_A0:m.scratch,UC_M68K_REG_A1:m.scratch+32}
        assert installed(hook,1,regs=saved)==1
        assert all(u.reg_read(reg)==value for reg,value in saved.items())
        assert u.reg_read(UC_M68K_REG_A7)==m.stack
        assert bytes(u.mem_read(0x800065b8,4))==b'\0\0\0\1'
        assert event()==48
    # Actual successful-send continuations: velocity zero and live arp pools
    # cannot consume a sequenced event. Register/stack ABI executes as linked.
    for hook in ('sent_a', 'sent_b'):
        setting(0,7,base=9)
        m.c('ha_fire_c',0,0,0,0)
        u.mem_write(0x46c77b1e,b'\0');u.mem_write(0x400d807c,b'\x90\x30\0')
        installed(hook,regs={UC_M68K_REG_D7:0},notify=False)
        assert event(sound=False)==48
        u.mem_write(0x400d807e,b'\x64');u.mem_write(0x46c77b1e,b'\1')
        installed(hook,regs={UC_M68K_REG_D7:0},notify=False)
        assert event(sound=False)==48
        u.mem_write(0x46c77b1e,b'\0')
        installed(hook,regs={UC_M68K_REG_D7:0})
        assert event(sound=False)==50
    print('[ok] installed event hooks: one callback per selected consumer; silent/live guards, reset policies and register ABI',flush=True)
    # All 16 states survive a dense same-step checkpoint, including OFF.
    expected=bytearray()
    for lane in range(128):
        row=bytes(((2*i+lane)%16<<4)|((2*i+lane+1)%16) for i in range(32))
        row+=bytes(((-lane%22)&255, lane%22, lane%4, (lane//4)%4,1+lane%15))
        # lower is a signed non-positive byte, independently from upper.
        row=row[:32]+bytes(((-(lane%22))&255,))+row[33:]
        expected.extend(row)
    u.mem_write(s['ha_lanes'],bytes(expected))
    m.c('hd_nv_save_c',0)
    roots=bytes(u.mem_read(s['hd_banks'],16768));q=bytes(u.mem_read(s['ch_lock_table'],8192))
    payload=oracle(roots,q)+expected
    snap=retained.snapshot(m);h=header(snap)
    assert snap==encode(payload,0,int.from_bytes(h[3:7],'big'),h[2])
    u.mem_write(s['ha_lanes'],b'\xcc'*4736)
    assert m.c('hd_nv_restore_c',0)==1
    assert bytes(u.mem_read(s['ha_lanes'],4736))==expected
    # Valid checksums cannot admit malformed settings, even in the last lane.
    for offset,value in ((32,1),(32,234),(33,22),(34,4),(35,4),(36,0)):
        corrupt=bytearray(payload);corrupt[10368+127*37+offset]=value
        retained.install(m,encode(corrupt))
        assert m.c('hd_nv_restore_c',0)==0
        assert bytes(u.mem_read(s['ha_lanes'],4736))==expected
    retained.install(m,snap)
    print('[ok] 8192 ACC nibbles and all settings: physical mapping, dense restore, corrupt-config rejection',flush=True)
    assert m.call('ch_file_write',0)==1
    path='/SET/PROJECT/hdeg01.work';new=m.files[path]
    assert new[:8]==b'HDP4\0\0\0\4' and len(new)==15136
    m.c('ha_bank_reset_c',0);m.call('ch_file_read',0)
    assert bytes(u.mem_read(s['ha_lanes'],4736))==expected
    old_payload=new[32:32+10368]
    old=struct.pack('>8I',0x48445033,3,0,10368,fnv(old_payload),int.from_bytes(new[20:24],'big'),0,0)+old_payload
    m.files[path]=old;m.call('ch_file_read',0)
    assert u.mem_read(s['ch_lock_status'],1)==b'\2'
    assert m.call('ch_file_write',0)==0xfffffff9 and m.files[path]==old
    m.files[path]=new;m.call('ch_file_read',0)
    assert bytes(u.mem_read(s['ha_lanes'],4736))==expected
    assert bytes(u.mem_read(s['ch_lock_table'],8192))==q
    print('[ok] HDP4 round trip; obsolete HDP3 rejected and protected from overwrite',flush=True)
    legacy=bytearray()
    for lane in range(128):
        row=old_payload[lane*81:(lane+1)*81]
        hdr=bytes((1,0,lane,row[0],1,0,0,0))+(17).to_bytes(4,'big')
        hdr+=fnv(hdr+row).to_bytes(4,'big')
        meta=int.from_bytes(hdr,'big')<<4
        tokens=int.from_bytes(row[1:],'big')
        for step in range(64):
            top=43 if step==0 else (meta>>(6*(22-step)))&63 if step<=22 else 0
            legacy.extend(((top<<10)|((tokens>>(10*(63-step)))&1023)).to_bytes(2,'big'))
    retained.install(m,legacy);u.mem_write(s['ha_lanes'],bytes(expected))
    assert m.c('hd_nv_restore_c',0)==0
    assert bytes(u.mem_read(s['ha_lanes'],4736))==expected
    assert bytes(u.mem_read(s['ch_lock_table'],8192))==q
    print('[ok] obsolete HMT1 checkpoint rejected without publication',flush=True)
    # Carry actual musical config through the existing native memcpy bridge.
    u.mem_write(s['ha_lanes'],bytes(expected))
    for dst,src,length in ((BANK+0x8ed8+0x48d0,BANK+0x48d0,0x8b0),
                           (0x460c8122,BANK,0x8ed8),
                           (BANK+2*0x8ed8,0x460c8122,0x8ed8)):
        m.c('ch_memcpy',dst,src,length)
    assert bytes(u.mem_read(s['ha_lanes']+8*37,37))==expected[:37]
    assert bytes(u.mem_read(s['ha_lanes']+16*37,8*37))==expected[:8*37]
    before=bytes(u.mem_read(s['ha_lanes'],4736))
    m.c('hd_forget_c',0,0,0,3)
    cleared=bytearray(before);cleared[1]&=0xf0
    assert bytes(u.mem_read(s['ha_lanes'],4736))==cleared
    print('[ok] native track/pattern clipboard bridge carries ACC; step clear is scoped',flush=True)
    c_minor_follow(m)
    result=dict(boundary_outputs=counts,dense_steps=8192,obsolete_formats_rejected=True,hardware_tested=False)
    out=__import__('pathlib').Path(__file__).resolve().parents[2]/'out/harmony-accumulator'
    out.mkdir(parents=True,exist_ok=True);(out/'linked.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
