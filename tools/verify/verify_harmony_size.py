#!/usr/bin/env python3
"""Execute fixed-size voicing, Part storage and held-note ownership in ColdFire."""
from harmony_midi_machine import HARMONY_SOURCE
import argparse
import itertools
import json
import random
import subprocess
import verify_midi_harmony as h
from verify_midi_harmony_stress import Keyboard
from unicorn.m68k_const import *


def machine():
    subprocess.run(['python3',str(HARMONY_SOURCE/'generate.py'),'--check'],check=True)
    m=h.Machine();u=m.uc
    m.setting(0,2)
    def voice(root=60,quality=0):
        u.mem_write(m.sym['ch_current'],bytes((quality,)))
        raw=m.chord(0,root)
        u.mem_write(m.scratch,bytes(raw))
        m.call('mh_voice',0,a0=m.scratch)
        assert u.reg_read(UC_M68K_REG_A7)==m.stack+4
        return [n for n in u.mem_read(m.scratch,4) if n<128]
    # Musical examples are hand-written, independent of the implementation.
    examples=[
        (3,0,0,0,0,[60,64,67,72]),
        (3,2,0,0,0,[64,67,72,76]),
        (3,3,0,0,0,[67,72,76,79]),
        (3,4,0,0,0,[67,72,76,79]),
        (2,0,0,0,1,[60,64,71]),
        (2,0,0,0,7,[60,64,70]),
        (2,0,0,0,2,[60,64,74]),
        (1,0,0,0,0,[60,64]),
        (1,0,0,0,1,[60,71]),
        (1,0,0,0,2,[60,74]),
        (1,0,0,0,3,[60,62]),
        (1,0,0,0,4,[60,65]),
        (1,0,0,1,1,[64,71]),
        (2,0,0,1,0,[64,67,76]),
        (3,0,0,1,0,[64,67,76,79]),
        (3,0,0,2,0,[48,60,64,67]),
        (3,0,1,1,0,[64,76,79,91]),
    ]
    for size,voic,spread,rootmode,quality,want in examples:
        for name,value in [('size',size),('voic',voic),('sprd',spread),('root',rootmode)]:
            m.call('mh_'+name+'_set',0,value)
        got=voice(60,quality)
        assert got==want,(size,voic,spread,rootmode,quality,got,want)
    # In C major, Bdim keeps its altered fifth when reduced to two notes;
    # B half-diminished keeps root, b5, b7 at SIZE 3.
    m.call('mh_sprd_set',0,0);m.call('mh_root_set',0,0)
    m.call('mh_size_set',0,1)
    assert voice(71,0)==[71,77]
    m.call('mh_size_set',0,2)
    assert voice(71,1)==[71,77,81]
    # Same-root quality changes retain actual common voices in AUTO.
    m.call('mh_voic_set',0,1)
    assert voice(60,0)==[60,64,67]
    assert voice(60,1)==[60,64,71]
    # A changed quality must not reuse a stale same-root chord (old NAT fast path).
    assert voice(60,6)==[60,63,67]
    assert voice(60,0)==[60,64,67]
    assert voice(65,0)==[60,65,69]
    first=voice(65,1)
    assert first==[64,65,69], "quality change reseeded AUTO"
    assert voice(77,1)==[p+12 for p in first]
    print('[ok] SIZE: inversion/doubling, shells, extensions, altered fifths, ROOT, OPEN collisions and AUTO examples',flush=True)

    # Storage uses native Parts: every CHRD/SIZE combination, independent
    # writers, invalid bytes/edits, UI vs playing context, all eight tracks.
    for t,q,size in itertools.product(range(8),range(8),range(4)):
        m.call('ch_base_set',t,q);m.call('mh_size_set',t,size)
        assert m.call('ch_base_get',t)==q and m.call('mh_size_get',t)==size
        assert u.mem_read(m.part_address(t,18),1)[0]==q+8*size
        m.call('ch_base_set',t,(q+1)%8)
        assert m.call('mh_size_get',t)==size
    for byte in (32,63,127,255):
        u.mem_write(m.part_address(0,18),bytes((byte,)))
        assert m.call('mh_size_get',0)==m.call('ch_base_get',0)==0
    for value in (4,127,0xffffffff):
        before=bytes(u.mem_read(m.part_address(0,18),1))
        assert m.call('mh_size_set',0,value)==0
        assert bytes(u.mem_read(m.part_address(0,18),1))==before
    m.call('mh_size_set',0,3)
    assert m.call('ch_base_get',0)==0
    u.mem_write(0x100b14cf,b'\x01')
    m.call('mh_size_set',0,1)
    assert m.call('mh_size_get',0)==1 and m.call('mh_size_get_at',0,0)==3
    u.mem_write(0x100b14cf,b'\0')
    print('[ok] SIZE: packed Part isolation, independent CHRD edits, corrupt fallback and explicit contexts',flush=True)

    # Every quality, size, inversion, spacing and ROOT mode in a safe register.
    # Assert musical properties rather than transcribing the candidate search.
    count=0
    for size,voic,spread,rootmode,quality in itertools.product(range(1,4),range(5),range(3),range(4),range(8)):
        for name,value in [('size',size),('voic',voic),('sprd',spread),('root',rootmode)]:
            m.call('mh_'+name+'_set',0,value)
        for root in (48,53,59,60,65,71):
            got=voice(root,quality)
            raw=m.chord(0,root)
            assert len(got)==len(set(got))==size+1,(size,voic,spread,rootmode,quality,root,got)
            assert got==sorted(got) and set(p%12 for p in got)<=set(p%12 for p in raw)
            if rootmode==1:assert all(p%12!=raw[0]%12 for p in got)
            if rootmode>=2:assert raw[0]-12*(rootmode-1) in got
            if voic==1:assert voice(root,quality)==got,('repeat',root,quality,got,voice(root,quality))
            count+=1
    # Mixed-quality AUTO walks through all modes, chromatic keys and boundaries.
    rng=random.Random(0x512e)
    modes=range(7) if 'ms_decode' in m.sym else (0,5)
    for mode,key,size,spread,rootmode in itertools.product(modes,range(12),range(1,4),range(3),range(4)):
        m.setting(0,2,key,mode)
        for name,value in [('size',size),('voic',1),('sprd',spread),('root',rootmode)]:m.call('mh_'+name+'_set',0,value)
        for root in (0,1,11,12,23,24,48,60,65,67,72,115,120,126,127):
            q=rng.randrange(8);got=voice(root,q);raw=m.chord(0,root)
            assert len(got)==len(set(got))<=size+1
            assert got==sorted(got) and all(0<=p<=127 for p in got)
            assert {p%12 for p in got}<={p%12 for p in raw}
            if rootmode==1:assert all(p%12!=raw[0]%12 for p in got)
            count+=1
    print(f'[ok] SIZE: {count} complete/edge voicings and mixed-quality AUTO transitions',flush=True)

    # The C boundary preserves the assembly entry's complete register ABI.
    # Only the pool, existing history/context arrays and bounded stack may write.
    m.setting(0,2)
    for name,value in [('size',3),('voic',1),('sprd',0),('root',0)]:m.call('mh_'+name+'_set',0,value)
    kept=(UC_M68K_REG_D0,UC_M68K_REG_D1,UC_M68K_REG_D2,UC_M68K_REG_D3,
          UC_M68K_REG_D4,UC_M68K_REG_D5,UC_M68K_REG_D6,UC_M68K_REG_D7,
          UC_M68K_REG_A0,UC_M68K_REG_A1,UC_M68K_REG_A2,UC_M68K_REG_A3,
          UC_M68K_REG_A4,UC_M68K_REG_A5,UC_M68K_REG_A6)
    regs={r:0x12340000+i for i,r in enumerate(kept)}
    regs[UC_M68K_REG_D0]=0;regs[UC_M68K_REG_A0]=m.scratch
    allowed=[(m.scratch,4),(m.stack-512,512),
             (m.sym['mh_voice_history'],64),(m.sym['mh_voice_context'],32),
             (m.sym['mh_voice_epoch'],32)]
    for pitches in ((60,64,67,60),(65,69,72,65)):
        u.mem_write(m.scratch,bytes(pitches));m.call('mh_voice',regs=regs)
        assert all(u.reg_read(r)==v for r,v in regs.items())
        assert all(any(lo<=a and a+n<=lo+length for lo,length in allowed) for a,n in m.writes)
    print('[ok] SIZE: all registers preserved, bounded stack and history/pool-only writes',flush=True)

    # All-track held notes must release their captured pitches after SIZE,
    # quality, root, inversion, spread and Part-setting edits.
    k=Keyboard();m=k.m
    for t in range(8):
        m.setting(t,2)
        m.call('mh_size_set',t,1+t%3)
        m.call('mh_voic_set',t,1)
    held={}
    for t in range(8):
        events=k.key(t,48+t,100)
        held[t]=[e[1] for e in events if e[2]]
        assert len(held[t])==2+t%3,(t,events)
    for t in range(8):
        m.call('mh_size_set',t,(t+1)%4);m.call('ch_base_set',t,7)
        m.call('mh_root_set',t,1);m.call('mh_voic_set',t,3)
        events=k.key(t,48+t,0)
        assert sorted(e[1] for e in events if not e[2])==sorted(held[t])
    assert bytes(m.uc.mem_read(m.sym['mh_refs'],1024))==bytes(1024)
    print('[ok] SIZE: eight-track held-note release ownership survives setting/quality changes',flush=True)
    return {'examples':len(examples)+6,'voicings':count,'held_tracks':8,'hardware_tested':False}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('remix',nargs='?');ap.parse_args()
    result=machine();out=h.ROOT/'out/harmony-size';out.mkdir(parents=True,exist_ok=True)
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
