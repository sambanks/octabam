#!/usr/bin/env python3
"""All-eight-track ownership and sustained sequence checks on a virtual card.

Live cases enter the real keyboard C ABI and execute stock output/arp/RTOS.
Sequence cases enter through native transport. No physical panel, external
MIDI receiver or wire-latency acceptance is claimed. Source project is copied.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import subprocess
import verify_midi_harmony_port as p


def fixture(source,name,channels,arp=False,sequenced=False,change=False):
    w=p.fixture(source,name,{t:2 for t in range(8)},key_raw=0)
    for path in (w/'project').glob('bank*.work'):
        def edit(d):
            for part in range(8):
                b=p.otp.PART_BASE+part*p.otp.PART_STRIDE+9
                for t,ch in enumerate(channels):
                    d[b+0x4e2+36*t]=ch
                    d[b+0x4e2+36*t+17]=0
                    lane=b+0x3e2+32*t
                    d[lane+2]=6
                    d[lane+14]=1 if arp else 0
                    d[lane+15]=1 if arp else 5
                    d[lane+6:lane+12]=bytes(6)
            for pattern in range(16):
                for t in range(8):
                    at=0x492e+pattern*0x8eec+t*0x8b9
                    d[at+9:at+33]=bytes(24)
                    d[at+0x39:at+0x839]=b'\xff'*2048
                    if sequenced:
                        d[at+9:at+17]=(1 if change and t<7 else (1<<16)-1).to_bytes(8,'big')
                        for step in range(16):
                            lock=at+0x39+step*32
                            d[lock:lock+3]=bytes((48+(step%4)*5,90+t,127 if change and t<7 else 3))
        p.otp._bank_write(w/'project',int(path.stem[4:]),edit,guard=False)
    card,_=p.emu_card.stage_project(w/'project','OCTABAM','BASS',tree=w/'tree')
    (w/'card.img').write_bytes(card)
    return w


def run(source,name,sym,image,channels,mode):
    arp=mode=='arp'
    sequenced=mode in ('sequence','change')
    w=fixture(source,name,channels,arp,sequenced,mode=='change')
    commands=[]
    def key(frame,t,n,v):commands.append((frame,f'call:{sym["mh_keyboard"]:#x},{t},{n},{v},0'))
    def poke(frame,at,value):commands.append((frame,f'poke:{at:#x}={value}'))
    expected=[]
    frames=3000
    if sequenced:
        frames=30000
        commands.append((28000,'call:0x4009f5bc'))
        if 'bf_source_get' in sym:
            # Longest reverse chain: T1 -> T2 -> ... -> T8, shared scale/root.
            for t in range(7):
                poke('-',0x400e21e0+0x8ed80+0x4e2+36*t+3,t+2)
                if mode=='change':poke('-',0x400e21e0+0x8ed80+0x4e2+36*t+12,2)
    elif mode=='bypass-first':
        for t in range(8):
            poke('-',0x400e21e0+0x8ed80+0x4e2+36*t+5,0)
            key(100,t,64+t,100)
            expected.append(('on',channels[t],64+t,100))
        for t in range(8):
            poke(400,0x400e21e0+0x8ed80+0x4e2+36*t+5,2)
            key(600,t,60+t,100)
            expected.extend(('on',channels[t],n+t,100) for n in (60,67))
        for t in range(8):
            key(1500,t,60+t,0)
            expected.extend(('off',channels[t],n+t,0) for n in (60,67))
        for t in range(8):
            key(2000,t,64+t,0)
            expected.append(('off',channels[t],64+t,0))
    elif mode=='stock-bypass':
        for t in range(8):
            poke('-',0x400e21e0+0x8ed80+0x4e2+36*t+5,0)
            key(100,t,24+t*12,100)
            expected.append(('on',channels[t],24+t*12,100))
        for t in range(8):
            key(1500,t,24+t*12,0)
            expected.append(('off',channels[t],24+t*12,0))
    elif mode=='all-pitches':
        keys=[(t,n) for t in range(8) for n in range(128)]
        rng=random.Random(140);rng.shuffle(keys)
        for t in range(8):poke('-',0x400e21e0+0x8ed80+0x4e2+36*t+5,1)
        for t,n in keys:
            key(100,t,n,100);expected.append(('on',channels[t],n,100))
        rng.shuffle(keys)
        for t,n in keys:
            key(5000,t,n,0);expected.append(('off',channels[t],n,0))
        frames=10000
    elif mode=='churn':
        rng=random.Random(20261008)
        for cycle in range(80):
            root=48+(cycle%12)
            tracks=list(range(8));rng.shuffle(tracks)
            for t in tracks:key(100+cycle*100,t,root,100)
            for channel in dict.fromkeys(channels[t] for t in tracks):
                expected.extend(('on',channel,n,100) for n in (root,root+4,root+7))
            rng.shuffle(tracks)
            for t in tracks:key(150+cycle*100,t,root,0)
            last={ch:max(i for i,t in enumerate(tracks) if channels[t]==ch) for ch in set(channels)}
            for ch in sorted(last,key=last.get):expected.extend(('off',ch,n,0) for n in (root,root+4,root+7))
        frames=8400
    else:
        for t in range(8):key(100,t,60,100)
        expected=[('on',ch,n,100) for ch in dict.fromkeys(channels) for n in (60,64,67)]
        if mode=='bypass':
            for t in range(8):
                poke(400,0x400e21e0+0x8ed80+0x4e2+36*t+5,0)
                key(600,t,64,100);key(900,t,64,0)
        if mode in ('channel-off','channel-change'):
            for t in range(8):poke(600,0x40171442+36*t,0 if mode=='channel-off' else 16-t)
        for t in range(8):key(1500,t,60,0)
        expected += [('off',ch,n,0) for ch in dict.fromkeys(channels) for n in (60,64,67)]
    extra=['--sequencer','--internal-clock','--frames',str(frames)]
    for frame,action in commands:extra+=['--step',f'{frame}:{action}']
    dump=';'.join(f'{sym[n]:#x},{size}={w}/{n}.bin' for n,size in
                  [('mh_held',4096),('mh_refs',1024),('mh_key_tokens',2048)])
    extra+=['--mem-dump',dump]
    events=p.run(w,'capture',extra,image=image)
    log=(w/'capture.log').read_text()
    assert 'load run ended: LOAD PROJECT handled' in log
    assert 'DID NOT RETURN' not in log and 'main never spun' not in log
    p.balanced(events)
    if not (arp or sequenced):assert events==expected,(name,events,expected)
    else:
        assert {e[1] for e in events if e[0]=='on'}==set(channels),(name,events)
        assert len(events)>=(400 if sequenced else 24),(name,len(events))
    if mode=='change':
        source_count=sum(e[:2]==('on',channels[7]) for e in events)
        assert source_count>=48,(name,'source did not run enough changes',source_count)
        for ch in channels[:7]:
            pitches=[e[2] for e in events if e[:2]==('on',ch)]
            assert len(pitches)==source_count and len(set(pitches))>=6,(name,ch,source_count,pitches)
    assert (w/'mh_held.bin').read_bytes()==b'\xff'*4096,name
    assert (w/'mh_refs.bin').read_bytes()==bytes(1024),name
    assert (w/'mh_key_tokens.bin').read_bytes()==b'\xff'*2048,name
    if mode=='stock-bypass':
        stock_extra=[value.replace(f'call:{sym["mh_keyboard"]:#x},','call:0x4009e9a8,') for value in extra]
        # Stock has no module memory; no candidate-state dumps on this control.
        stock_extra=stock_extra[:stock_extra.index('--mem-dump')]
        baseline=p.run(w,'stock',stock_extra,image=p.ROOT/'out/raw/section_3_MAIN_OS.bin')
        assert events==baseline,(name,'HARM OFF differs from stock')
    saved=p.emu_card.extract_image((w/'capture-card.img').read_bytes())
    for path in (w/'project').glob('bank*.*'):
        assert saved['OCTABAM/BASS/'+path.name]==path.read_bytes(),(name,path.name)
    print(f'[ok] {name}: {len(events)} UART note events, eight tracks, balanced releases and empty ownership',flush=True)
    return dict(events=len(events),channels=channels,frames=frames)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project',required=True,type=Path)
    ap.add_argument('--case',action='append')
    args=ap.parse_args()
    p.OUT=p.ROOT/'out/midi-concert-port';p.OUT.mkdir(parents=True,exist_ok=True)
    image=p.OUT/'candidate.bin';image.write_bytes((p.ROOT/'out/mainos_bus.bin').read_bytes())
    sym=p.harmony.symbols()
    (p.OUT/'symbols.json').write_text(json.dumps(sym,indent=2)+'\n')
    cases={'all-pitches':(list(range(1,9)),'all-pitches'),
           'separate-channels':(list(range(1,9)),'direct'),
           'shared-channel':([1]*8,'direct'),
           'paired-channels':([1,2,3,4]*2,'direct'),
           'bypass-first':(list(range(1,9)),'bypass-first'),
           'stock-bypass-control':(list(range(1,9)),'stock-bypass'),
           'bypass-overlap':(list(range(1,9)),'bypass'),
           'channel-off-held':(list(range(1,9)),'channel-off'),
           'channel-change-held':(list(range(1,9)),'channel-change'),
           'eight-arps':(list(range(1,9)),'arp'),
           'shared-channel-churn':([1,2,3,4]*2,'churn'),
           'eight-track-sequence':(list(range(1,9)),'sequence')}
    if 'bf_response_get' in sym:
        cases['seven-held-change-followers']=(list(range(1,9)),'change')
    selected=args.case or list(cases)
    assert all(n in cases for n in selected),selected
    receipt=p.OUT/('result-'+('-'.join(selected) if args.case else 'all')+'.json')
    receipt.unlink(missing_ok=True)
    results={}
    for name in selected:
        results[name]=run(args.project,name,sym,image,*cases[name])
        receipt.write_text(json.dumps(dict(status='pass' if len(results)==len(selected) else 'incomplete',
            cases=results,image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
            scope='ColdFire port UART; live C ABI and native sequencer; no physical wire timing',hardware_tested=False),indent=2)+'\n')


if __name__=='__main__':main()
