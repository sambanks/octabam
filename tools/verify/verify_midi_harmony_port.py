#!/usr/bin/env python3
"""Full firmware MIDI/UI/project checks. Uses a copied project and virtual CF only."""
import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import re
import midi_fixture as follow
import verify_midi_harmony as harmony
ROOT=harmony.ROOT
sys.path.insert(0,str(ROOT/'tools'))
import emu_card
from hw import ot_project as otp
OUT=ROOT/'out/harmony-port-suite'


def fixture(source, name, records, arp=False, reverse=False, key_raw=1, first_note=62, tran=None, locks=None, auto=(), spreads=None, voicings=None, omits=None, roots=None, sizes=None, audio_cc_out=None):
    work=OUT/name;work.mkdir(parents=True,exist_ok=True)
    leader=7 if reverse else 0
    follow.fixture(source,work/'project',arp=arp,leader=leader,offsets=locks)
    for path in (work/'project').glob('bank*.work'):
        def mutate(data):
            for part in range(8):
                base=otp.PART_BASE+part*otp.PART_STRIDE+9
                for t in range(8):
                    setup=base+0x4e2+36*t
                    # Fixture records select OFF/NOTE/triad/seventh; native
                    # HARM remains OFF/NOTE/CHORD and CHRD owns the quality.
                    kind=records.get(t,0)
                    assert kind in range(4)
                    data[setup+5]=min(kind,2)
                    data[setup+18]=int(kind==3) | ((sizes or {}).get(t,0)<<3)
                    voic=(voicings or {}).get(t,int(t in auto))
                    root=(roots or {}).get(t,(omits or {}).get(t,0))
                    data[setup+16]=voic | ((spreads or {}).get(t,0)<<3) | (root<<5)
                    data[setup+17]=key_raw if t!=1 else 4
                for t,offset in (tran or {}).items():
                    data[base+0x3e2+32*t+12]=64+offset
                if arp:
                    # T2 arpeggiates its generated chord as well as the leader.
                    at=base+0x3e2+32
                    data[at+2]=18;data[at+14]=1;data[at+15]=3
            for p in range(16):
                at=0x492e+p*0x8eec+leader*0x8b9
                if p==0:data[at+0x39+2*32]=first_note # D minor, then F and G in C major.
        otp._bank_write(work/'project',int(path.stem[4:]),mutate,guard=False)
    if audio_cc_out is not None:
        for path in (work/'project').glob('project.*'):
            raw,n=re.subn(rb'MIDI_AUDIO_TRK_CC_OUT=\d+',
                          f'MIDI_AUDIO_TRK_CC_OUT={audio_cc_out}'.encode(),path.read_bytes())
            assert n==1,(path,'missing AUDIO CC OUT fixture setting')
            path.write_bytes(raw)
    card,_=emu_card.stage_project(work/'project','OCTABAM','BASS',tree=work/'tree')
    (work/'card.img').write_bytes(card)
    return work


CANDIDATE_IMAGE = None


def freeze_candidate(destination):
    """Keep an image and its helper addresses together throughout a long run.

    A later development build must not silently change a subsequent case.
    Stock-comparison cases can still pass their explicit image.
    """
    global CANDIDATE_IMAGE
    destination.mkdir(parents=True, exist_ok=True)
    CANDIDATE_IMAGE = destination / 'candidate.bin'
    CANDIDATE_IMAGE.write_bytes((ROOT/'out/mainos_bus.bin').read_bytes())
    frozen_symbols = harmony.symbols()
    harmony.symbols = lambda: frozen_symbols
    (destination/'candidate-symbols.json').write_text(json.dumps(frozen_symbols,indent=2)+'\n')
    return CANDIDATE_IMAGE


def choice_panel(text):
    """Expand logical custom-control choices into four-count physical reports."""
    lines=[]
    for line in text.splitlines():
        words=line.split()
        if len(words)==4 and words[1]=='enc' and int(words[2])<5:
            at,slot,steps=int(words[0]),int(words[2]),int(words[3])
            lines.extend(f'{at+i*25} enc {slot} {4 if steps>0 else -4}' for i in range(abs(steps)))
        elif words:lines.append(line)
    return '\n'.join(sorted(lines,key=lambda l:int(l.split()[0])))+'\n'


def run(work, name, extra=(), image=None, card=None, physical_panel=False):
    extra=list(extra)
    if '--live-script' in extra and not physical_panel:
        index=extra.index('--live-script')+1
        original=pathlib.Path(extra[index])
        physical=work/f'{name}-physical-panel.txt'
        physical.write_text(choice_panel(original.read_text()))
        extra[index]=physical

    cmd=[str(ROOT/'out/emu/ot_emu'),'--image',str(image or CANDIDATE_IMAGE or ROOT/'out/mainos_bus.bin'),
         '--card',str(card or work/'card.img'),'--set','OCTABAM','--project','BASS',
         '--load-ms','90000','--mkii','--midi-out',str(work/f'{name}.midi'),
         '--card-out',str(work/f'{name}-card.img')]+list(map(str,extra))
    with (work/f'{name}.log').open('w') as f:p=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
    log=(work/f'{name}.log').read_text()
    assert p.returncode==0 and ('run ended REACHED' in log or 'ended on quit' in log),(name,work/f'{name}.log')
    events=follow.notes((work/f'{name}.midi').read_bytes())
    (work/f'{name}-notes.json').write_text(json.dumps(events,indent=2)+'\n')
    return events


def balanced(events):
    held=set()
    for kind,ch,n,v in events:
        key=ch,n
        if kind=='on':
            assert key not in held,('duplicate',key);held.add(key)
        else:
            assert key in held,('unmatched off',key);held.remove(key)
    assert not held,('stuck',held)


def sequence(source):
    sym=harmony.symbols();has_follow='bf_source_get' in sym
    cases={}
    for arp,reverse in [(False,False),(True,False)]+([(False,True),(True,True)] if has_follow else []):
        name=('reverse-' if reverse else '')+('arp' if arp else 'chords')
        leader=7 if reverse else 0
        # Destination TYPE seventh, source TYPE triad. Different own scale on
        # follower proves it inherits C major instead of its stored C# minor.
        work=fixture(source,name,{leader:2,1:3},arp,reverse)
        extra=['--sequencer','--internal-clock','--frames','7000']
        if has_follow:extra+=['--step','-:poke:0x100b14cc=1','--step',f'-:call:{sym["bf_encoder"]:#x},3,4'] * (7 if reverse else 1)
        events=run(work,'patched',extra)
        balanced(events)
        leader_ch=13 if reverse else 1;follower_ch=5 if reverse else 2
        lead=[e[2] for e in events if e[:2]==('on',leader_ch)]
        bass=[e[2] for e in events if e[:2]==('on',follower_ch)]
        if not arp:
            assert lead==[62,65,69,65,69,72,67,71,74],lead
            if has_follow:
                # Before the leader has triggered, Follow uses the receiver's
                # own root. DEG entered C# minor as degree 7 (C ties down to B);
                # selecting a C-major source preserves that degree identity.
                initial=[47,50,53,57] if 'hd_banks' in sym else [48,52,55,59]
                assert bass==initial+[38,41,45,48,38,41,45,48,41,45,48,52,43,47,50,53,43,47,50,53],bass
        else:
            assert {62,65,69,72,67,71,74}<=set(lead),lead
            if has_follow:assert {38,41,45,48,43,47,50,53}<=set(bass),bass
        saved=emu_card.extract_image((work/'patched-card.img').read_bytes())
        for p in (work/'project').glob('bank*.*'):assert saved['OCTABAM/BASS/'+p.name]==p.read_bytes()
        cases[name]=dict(leader=lead,follower=bass)
        print(f'  [ok] full firmware {name}: generated chords, note ownership and unchanged bank files',flush=True)
    # BottleService intentionally emits additional audio CC feedback. Disable
    # AUDIO CC OUT in both fixtures so the strict full-UART comparison isolates
    # HARM OFF; other interaction cases keep the project's feedback setting.
    work=fixture(source,'off',{},audio_cc_out=0)
    extra=['--sequencer','--internal-clock','--frames','7000']
    a=run(work,'stock',extra,image=ROOT/'out/raw/section_3_MAIN_OS.bin')
    b=run(work,'patched',extra)
    assert a==b
    def transport_uart(name):
        # CC FEEDBACK can send the boot defaults before the project disables
        # AUDIO CC OUT. Use the port's recorded transport boundary, retaining
        # every byte (including CC and running status) during playback.
        raw=(work/f'{name}.midi').read_bytes()
        match=re.search(r'midi out\s+: (\d+) byte\(s\) on UART0 \((\d+) after the transport start\)',
                        (work/f'{name}.log').read_text())
        assert match,(name,'missing transport UART boundary')
        total,after=map(int,match.groups())
        assert total==len(raw) and 0<after<=total
        return raw[total-after:]
    assert transport_uart('stock')==transport_uart('patched'), 'HARM OFF changed playback UART'
    balanced(b)
    print('  [ok] full firmware HARM OFF matches every stock UART byte after transport start',flush=True)
    return cases


def extended_scale(source):
    sym=harmony.symbols()
    if 'ms_decode' not in sym:return {}
    work=fixture(source,'dorian-output',{},key_raw=25,first_note=64)
    extra=['--sequencer','--internal-clock','--frames','7000']
    if 'bf_source_get' in sym:
        extra+=['--step','-:poke:0x100b14cc=1','--step',f'-:call:{sym["bf_encoder"]:#x},3,4']
    events=run(work,'patched',extra);balanced(events)
    lead=[e[2] for e in events if e[:2]==('on',1)]
    bass=[e[2] for e in events if e[:2]==('on',2)]
    assert lead[0]==63 and all(n%12 in harmony.MODES[1] for n in lead),lead
    if 'bf_source_get' in sym:assert bass[:3]==[48,39,39],bass
    print('  [ok] full firmware added scale with HARM OFF: E snaps to Eb; follower uses Eb root',flush=True)
    return {'dorian-output':dict(leader=lead,follower=bass)}


def keyboard(source):
    results={}
    for arp in (False,True):
        work=fixture(source,'keys-arp' if arp else 'keys-chords',{0:2},arp=arp)
        script=work/'keys.txt'
        script.write_text('100 key 0x32 down\n200 key 0x32 up\n1000 key 0 down\n1800 key 4 down\n2600 key 0 up\n3400 key 4 up\n4300 quit\n')
        extra=['--step','-:poke:0x80000015=1','--step','-:poke:0x460d16f3=1',
               '--step','-:poke:0x100b14cc=0','--internal-clock','--live-script',script,
               '--lcd',work/'keys.lcd']
        events=run(work,'keys',extra)
        balanced(events)
        pitches=[e[2] for e in events if e[0]=='on']
        if not arp:
            assert pitches==[48,52,55,59],events
            assert [(e[0],e[2]) for e in events if e[0]=='off']==[('off',48),('off',52),('off',55),('off',59)],events
        else:
            assert {48,52,55,59}<=set(pitches),events
        results[work.name]=pitches
        print(f'  [ok] UART chromatic keys {work.name}: generated notes and balanced releases',flush=True)
    return results


def note_rules(source):
    sym=harmony.symbols();has_follow='bf_source_get' in sym;results={}
    for reverse in ([False,True] if has_follow else [False]):
        leader=7 if reverse else 0
        name='note-transpose-reverse' if reverse else 'note-transpose'
        work=fixture(source,name,{leader:1,1:1},reverse=reverse,first_note=71,
                     tran={leader:7,1:1},locks={2:6,3:1,6:12,8:7})
        extra=['--sequencer','--internal-clock','--frames','7000']
        if has_follow:extra+=['--step','-:poke:0x100b14cc=1','--step',f'-:call:{sym["bf_encoder"]:#x},3,4'] * (7 if reverse else 1)
        events=run(work,'patched',extra);balanced(events)
        lead=[e[2] for e in events if e[:2]==('on',13 if reverse else 1)]
        bass=[e[2] for e in events if e[:2]==('on',5 if reverse else 2)]
        assert lead==[77,72,74],lead # B+7 -> F, F+7 -> C, G+7 -> D
        if has_follow:assert bass==[48,47,41,48,45,38],bass
        results[name]=dict(leader=lead,follower=bass)
        print(f'  [ok] {name}: final scale snap after TRAN/P-locks; source latch and balanced releases',flush=True)
    for arp in (False,True):
        t=1 if has_follow else 0
        name='note-key-arp' if arp else 'note-key-direct'
        work=fixture(source,name,{t:1},arp=arp,tran={t:7})
        script=work/'keys.txt'
        script.write_text('100 key 0x32 down\n200 key 0x32 up\n1000 key 2 down\n1800 key 2 up\n2200 key 1 down\n3000 key 1 up\n3700 quit\n')
        extra=['--step','-:poke:0x80000015=1','--step','-:poke:0x460d16f3=1',
               '--step',f'-:poke:0x100b14cc={t}','--internal-clock','--live-script',script]
        if has_follow:extra+=['--step',f'-:call:{sym["bf_encoder"]:#x},3,4','--step',f'-:poke:{sym["bf_roots"]:#x}=41']
        events=run(work,'keys',extra);balanced(events)
        pitches=[e[2] for e in events if e[0]=='on']
        if arp:assert set(pitches)=={55,57},pitches
        else:assert pitches==[50,48],pitches
        results[name]=pitches
        print(f'  [ok] {name}: absolute keyboard root; live arp applies TRAN +7, direct keys ignore it',flush=True)
    return results


def chord_rules(source):
    sym=harmony.symbols();has_follow='bf_source_get' in sym;results={}
    def chord(root,kind):
        notes=[n for n in range(root,160) if n%12 in harmony.MODES[0]]
        return [notes[i*2] for i in range(kind+1) if notes[i*2]<=127]
    for kind in (2,3):
        for arp in (False,True):
            name=f'chord-transpose-{kind}-' + ('arp' if arp else 'direct')
            work=fixture(source,name,{0:kind,1:kind},arp=arp,first_note=71,
                         tran={0:7,1:1},locks={2:6,3:1,6:12,8:7})
            extra=['--sequencer','--internal-clock','--frames','7000']
            if has_follow:extra+=['--step','-:poke:0x100b14cc=1','--step',f'-:call:{sym["bf_encoder"]:#x},3,4']
            events=run(work,'patched',extra);balanced(events)
            lead=[e[2] for e in events if e[:2]==('on',1)]
            bass=[e[2] for e in events if e[:2]==('on',2)]
            want_lead=[n for root in (77,72,74) for n in chord(root,kind)]
            want_bass=[n for root in (48,47,41,48,45,38) for n in chord(root,kind)]
            if arp:
                assert lead and set(lead)<=set(want_lead) and {77,81,84}<=set(lead),lead
                if has_follow:assert bass and set(bass)<=set(want_bass),bass
            else:
                assert lead==want_lead,(lead,want_lead)
                if has_follow:assert bass==want_bass,(bass,want_bass)
            results[name]=dict(leader=lead,follower=bass)
            print(f'  [ok] {name}: snapped root then diatonic thirds; follower P-locks; balanced releases',flush=True)
            t=1 if has_follow else 0
            name=f'chord-key-{kind}-' + ('arp' if arp else 'direct')
            work=fixture(source,name,{t:kind},arp=arp,tran={t:7})
            script=work/'keys.txt'
            script.write_text('100 key 0x32 down\n200 key 0x32 up\n1000 key 2 down\n1800 key 2 up\n2200 key 1 down\n3000 key 1 up\n3700 quit\n')
            extra=['--step','-:poke:0x80000015=1','--step','-:poke:0x460d16f3=1',
                   '--step',f'-:poke:0x100b14cc={t}','--internal-clock','--live-script',script]
            if has_follow:extra+=['--step',f'-:call:{sym["bf_encoder"]:#x},3,4','--step',f'-:poke:{sym["bf_roots"]:#x}=41']
            events=run(work,'keys',extra);balanced(events)
            pitches=[e[2] for e in events if e[0]=='on']
            want=chord(50,kind)+chord(48,kind)
            if arp:
                valid=[n for n in range(128) if n%12 in harmony.MODES[0]]
                shifted={min(valid,key=lambda n:(abs(n-(pitch+7)),n)) for pitch in want}
                assert set(pitches)==shifted,pitches
            else:assert pitches==want,pitches
            results[name]=pitches
            print(f'  [ok] {name}: absolute D/C chord roots, inherited scale, stock live-arp TRAN +7',flush=True)
    return results


def recording(source):
    results={}
    for kind,voic,spread,omit in ((1,0,0,0),(2,0,0,0),(3,0,0,0),(2,1,0,0),(3,1,0,0),(2,1,1,0),(3,1,2,0),(2,2,1,0),(3,4,0,0),(2,2,1,1),(3,4,0,1),(2,1,0,1),(2,0,0,2),(3,4,0,3),(2,1,0,2)):
        name=f'live-record-{kind}'+(f'-voic{voic}' if voic>1 else '-auto' if voic else '')+(f'-spread{spread}' if spread else '')+(f'-root{omit}' if omit else '')
        work=fixture(source,name,{0:kind},spreads={0:spread},voicings={0:voic},roots={0:omit})
        for path in (work/'project').glob('bank*.work'):
            def blank(data):
                for pat in range(16):
                    for track in range(8):
                        at=0x492e+pat*0x8eec+track*0x8b9
                        data[at+9:at+33]=bytes(24)
                        data[at+0x39:at+0x839]=b'\xff'*2048
            otp._bank_write(work/'project',int(path.stem[4:]),blank,guard=False)
        card,_=emu_card.stage_project(work/'project','OCTABAM','BASS',tree=work/'blank-tree')
        (work/'card.img').write_bytes(card)
        script=work/'record.txt'
        # REC+PLAY, play C#/D/F, leave REC, hear the next loop, then STOP.
        script.write_text('100 key 0x32 down\n200 key 0x32 up\n600 key 0x29 down\n700 key 0x28 down\n800 key 0x28 up\n900 key 0x29 up\n1600 key 1 down\n1900 key 1 up\n2600 key 2 down\n2900 key 2 up\n3600 key 5 down\n3900 key 5 up\n4400 key 0x29 down\n4500 key 0x29 up\n14500 key 0x27 down\n14600 key 0x27 up\n15500 quit\n')
        extra=['--step','-:poke:0x80000015=1','--step','-:poke:0x460d16f3=1',
               '--step','-:poke:0x100b14cc=0','--internal-clock','--live-script',script,
               '--mem-dump',f'0x400e21e0,0x9b340={work}/bank-ram.bin;0x100a4ece,6322={work}/part.bin;0x46c76df1,1={work}/key.bin']
        events=run(work,'record',extra);balanced(events)
        pitches=[e[2] for e in events if e[:2]==('on',1)]
        expected=[]
        for root in (48,50,53):
            degrees=[n for n in range(root,80) if n%12 in harmony.MODES[0]]
            expected.extend(degrees[::2][:1 if kind==1 else kind+1])
        if voic==1:
            expected=([48,52,55,50,53,57,48,53,57] if kind==2 else
                      [48,52,55,59,48,50,53,57,48,52,53,57])
        if spread and voic<2:
            expected=([48,55,64,50,57,65,53,60,69] if kind==2 else
                      [48,64,67,71,50,65,69,72,53,69,72,76])
        if voic>1:
            expected=([52,60,67,53,62,69,57,65,72] if kind==2 else
                      [59,60,64,67,60,62,65,69,64,65,69,72])
        if omit:
            count=kind+1
            expected=[n for i,root in enumerate((48,50,53)) for n in
                      (([root-12*(omit-1)] if omit>1 else [])+
                       [p for p in expected[i*count:(i+1)*count] if p%12!=root%12])]
        assert pitches==expected*2,(pitches,expected) # performed chord == replayed chord
        bank=(work/'bank-ram.bin').read_bytes()
        lanes=[bank[0x4900+step*32:0x4920+step*32] for step in range(64)]
        recorded=[lane for lane in lanes if lane[0]<128]
        assert [lane[0] for lane in recorded]==[49,50,53],recorded
        assert all(lane[3:6]==b'\xff'*3 for lane in recorded),recorded
        state=(work/'part.bin').read_bytes()
        assert state[0x4e2+5]==min(kind,2)
        assert state[0x4e2+16]==voic+8*spread+32*omit
        assert (work/'key.bin').read_bytes()==b'\x01'
        results[name]=dict(notes=pitches,recorded_roots=[lane[0] for lane in recorded])
        print(f'  [ok] {name}: REC+PLAY -> chromatic C#/D/F -> physical keys recorded once -> identical chord playback',flush=True)
    return results


def empty_note_locks(source):
    results={}
    for kind in (2,3):
        for value in (64,0):
            name=f'explicit-empty-{kind}-{value}'
            work=fixture(source,name,{0:kind})
            for path in (work/'project').glob('bank*.work'):
                def lock(data):
                    for step in (2,4,8):
                        at=0x492e+0x39+step*32
                        data[at+3:at+6]=bytes((value,))*3
                otp._bank_write(work/'project',int(path.stem[4:]),lock,guard=False)
            card,_=emu_card.stage_project(work/'project','OCTABAM','BASS',tree=work/'locked-tree')
            (work/'card.img').write_bytes(card)
            events=run(work,'play',['--sequencer','--internal-clock','--frames','7000']);balanced(events)
            pitches=[e[2] for e in events if e[:2]==('on',1)]
            expected=[]
            for root in (62,65,67):
                degrees=[n for n in range(root,100) if n%12 in harmony.MODES[0]]
                expected.extend(degrees[::2][:kind+1])
            assert pitches==expected,(pitches,expected)
            results[name]=pitches
            print(f'  [ok] {name}: explicit NOT2-4 locks do not suppress generated chord voices',flush=True)
    return results


def persistence(source,voic=1,omit=0):
    expected_key=25 if 'ms_decode' in harmony.symbols() else 2
    name=('persistence' if voic==1 else f'persistence-voic{voic}')+(f'-root{omit}' if omit else '')
    work=fixture(source,name,{0:2,1:1})
    follow_settings={}
    if 'bf_source_get' in harmony.symbols():
        follow_settings={t:{3:int(t!=0),12:((t//2)&1)<<1,
                            13:(t+2)|((t%5)<<4),15:(t+1)|((t%3)<<4)} for t in range(8)}
        for path in (work/'project').glob('bank*.work'):
            def seed(data):
                for part in range(8):
                    for t,fields in follow_settings.items():
                        for field,value in fields.items():
                            data[otp.PART_BASE+part*otp.PART_STRIDE+9+0x4e2+36*t+field]=value
            otp._bank_write(work/'project',int(path.stem[4:]),seed,guard=False)
        card,_=emu_card.stage_project(work/'project','OCTABAM','BASS',tree=work/'follow-tree')
        (work/'card.img').write_bytes(card)
    lines=[]
    def key(at,k,hold=100):lines.extend([f'{at} key {k:#x} down',f'{at+hold} key {k:#x} up'])
    key(100,0x32);key(600,0x35);key(1100,0x10)
    lines.extend(['1600 key 0x2d down','1700 key 0x22 down','1850 key 0x22 up','1950 key 0x2d up','2300 enc 5 4'])
    # Open Harmony with the physical F press. CHORD maps A-D to
    # VOIC/SPRD/ROOT/SIZE; E/F are inactive. These are logical choice counts
    # expanded by run() into four-count physical encoder reports.
    key(2400,0x3d,50)
    lines.extend([f'2500 enc 0 {4 if voic==1 else voic-1}','2600 enc 1 1',
                  f'2630 enc 2 {omit}','2640 enc 3 3','2650 enc 4 1','2660 enc 5 4'])
    key(2700,0x32,50)
    key(2800,0x32)
    lines.extend(['3300 key 0x2d down','3400 key 0x23 down','3550 key 0x23 up','3650 key 0x2d up',f'4000 enc 5 {4 if expected_key==25 else 1}'])
    key(4500,0x32)
    for at,k in zip(range(5000,9200,700),[0x1c,0x21,0x20,0x31,0x31]):key(at,k)
    lines.append('40000 quit')
    script=work/'save.txt';script.write_text('\n'.join(lines)+'\n')
    extra=['--rtc','1800000000','--live-script',script,'--lcd',work/'save.lcd',
           '--mem-dump',f'0x10000000,0x100000={work}/saved-cs1.bin;0x100a4ece,6322={work}/saved-state.bin']
    run(work,'save',extra)
    expected=(work/'saved-state.bin').read_bytes()
    assert expected[0x4e2+5]==2
    assert expected[0x4e2+16]==voic+8+32*omit
    assert expected[0x4e2+12]==0, 'Harmony controls changed Follow flags'
    assert expected[0x4e2+18]==24, 'SIZE 4 was not stored alongside TRI'
    for t,fields in follow_settings.items():
        for field,value in fields.items():
            assert expected[0x4e2+36*t+field]==value
    files=emu_card.extract_image((work/'save-card.img').read_bytes())
    for name in ('bank01.work','bank01.strd'):
        data=files['OCTABAM/BASS/'+name]
        part=data[otp.PART_BASE+9:otp.PART_BASE+9+6322]
        assert part==expected,(name,'saved native Part differs from RAM')
        assert part[0x4e2+17]==expected_key,(name,part[0x4e2+17])
    quit_script=work/'quit.txt';quit_script.write_text('1500 quit\n')
    for name,options in [('reload',[]),('warm',['--no-post','--cs1-in',work/'saved-cs1.bin'])]:
        run(work,name,['--rtc','1800000000','--live-script',quit_script,
                      '--mem-dump',f'0x100a4ece,6322={work}/{name}-state.bin;0x46c76df1,1={work}/{name}-key.bin']+options,
            card=work/'save-card.img')
        assert (work/f'{name}-state.bin').read_bytes()==expected,name
        assert (work/f'{name}-key.bin').read_bytes()==bytes((expected_key,)),name
    fresh=fixture(source,'fresh-project',{})
    run(fresh,'load',['--rtc','1800000000','--cs1-in',work/'saved-cs1.bin','--live-script',quit_script,
                    '--mem-dump',f'0x100a4ece,6322={fresh}/state.bin'])
    state=(fresh/'state.bin').read_bytes()
    for track in range(8):
        at=0x4e2+36*track
        assert state[at+5]==state[at+16]==state[at+12]==state[at+18]==0
        if follow_settings:
            assert (state[at+3],state[at+13],state[at+15])==(0,35,3)
    print('  [ok] UART Harmony A-D controls and inactive E/F, native bank SAVE, disk reload, CS1 warm boot and fresh-project defaults',flush=True)
    return {work.name:'pass'}


def auto_voicing(source):
    results={};sym=harmony.symbols();has_follow='bf_source_get' in sym
    for arp in (False,True):
        work=fixture(source,'auto-sequence-'+('arp' if arp else 'chords'),{0:2,1:1},
                     arp=arp,first_note=60,auto=(0,))
        extra=['--sequencer','--internal-clock','--frames','7000']
        if has_follow:extra+=['--step','-:poke:0x100b14cc=1','--step',f'-:call:{sym["bf_encoder"]:#x},3,4']
        events=run(work,'play',extra);balanced(events)
        lead=[e[2] for e in events if e[:2]==('on',1)]
        bass=[e[2] for e in events if e[:2]==('on',2)]
        if not arp:assert lead==[60,64,67,60,65,69,59,62,67],lead
        else:assert {60,64,67,65,69,59,62}<=set(lead),lead
        if has_follow:
            if not arp:assert bass==[48,36,36,41,43,43],bass
            else:assert {36,41,43}<=set(bass),bass
        results[work.name]=dict(leader=lead,follower=bass)
        print(f'  [ok] {work.name}: C -> inverted F -> inverted G; follower uses harmonic root',flush=True)
        # Actual chromatic keys, overlapping common C, and releasing C then F.
        work=fixture(source,'auto-key-'+('arp' if arp else 'chords'),{0:2},arp=arp,auto=(0,))
        script=work/'keys.txt'
        script.write_text('100 key 0x32 down\n200 key 0x32 up\n1000 key 0 down\n1800 key 5 down\n2600 key 0 up\n3400 key 5 up\n4300 quit\n')
        extra=['--step','-:poke:0x80000015=1','--step','-:poke:0x460d16f3=1',
               '--step','-:poke:0x100b14cc=0','--internal-clock','--live-script',script]
        if has_follow:extra+=['--mem-dump',f'{sym["bf_roots"]:#x},8={work}/roots.bin']
        events=run(work,'keys',extra);balanced(events)
        pitches=[e[2] for e in events if e[0]=='on']
        if not arp:assert pitches==[48,52,55,53,57],pitches
        else:assert set(pitches)=={48,52,55,53,57},pitches
        if has_follow:assert (work/'roots.bin').read_bytes()[0]==41
        results[work.name]=pitches
        print(f'  [ok] {work.name}: live F is C-F-A, retained F root, balanced overlapping releases',flush=True)
    # A lasting screenshot proves a separate window, not just injected memory.
    work=fixture(source,'harmony-page',{0:2})
    script=work/'page.txt'
    script.write_text('100 key 0x32 down\n200 key 0x32 up\n600 key 0x2d down\n700 key 0x22 down\n850 key 0x22 up\n950 key 0x2d up\n1400 key 0x3d down\n1500 key 0x3d up\n2000 enc 1 4\n2100 enc 2 1\n2200 key 0 down\n2300 key 0 up\n2400 key 5 down\n2500 key 5 up\n3000 quit\n')
    events=run(work,'page',['--step','-:poke:0x80000015=1','--step','-:poke:0x460d16f3=1',
                    '--step','-:poke:0x100b14cc=0','--live-script',script,'--lcd',work/'page.lcd',
                    '--mem-dump',f'0x100a4ece,6322={work}/state.bin;{sym["mh_page_win"]:#x},4={work}/window.bin'])
    state=(work/'state.bin').read_bytes()
    assert state[0x4e2+5]==2 and state[0x4e2+16]==9
    assert int.from_bytes((work/'window.bin').read_bytes(),'big')!=0
    balanced(events)
    # OPEN AUTO must retain each generated root, including F3 (53).
    assert [e[2] for e in events if e[0]=='on']==[48,55,64,45,53,60],events
    subprocess.run([sys.executable,str(ROOT/'tools/emu/lcd_view.py'),str(work/'page.lcd'),'--png',str(work/'page.png')],check=True)
    results['harmony-page']='pass'
    return results


def bypass_follow(source, key_off_only=False):
    """Live roots drive followers with HARM OFF or no selected scale."""
    sym=harmony.symbols();results={}
    if 'bf_source_get' not in sym:return results
    for source_type,key_raw,dest_type in ((0,1,0),(0,1,1),(0,1,2),(2,0,0),(2,0,2),(1,1,1)):
        if key_off_only and key_raw:continue
        for arp in (False,True):
            name=f'bypass-follow-{source_type}-{key_raw}-{dest_type}-{int(arp)}'
            work=fixture(source,name,{0:source_type,1:dest_type},arp=arp,key_raw=key_raw)
            for path in (work/'project').glob('bank*.work'):
                def mutate(data):
                    for pattern in range(16):
                        for track in (0,2):
                            at=0x492e+pattern*0x8eec+track*0x8b9
                            data[at+9:at+33]=bytes(24) # source has no programmed trigs
                    for part in range(8):
                        base=otp.PART_BASE+part*otp.PART_STRIDE+9
                        data[base+0x3e2+32+14]=0 # follower emits its own rhythmic chord
                otp._bank_write(work/'project',int(path.stem[4:]),mutate,guard=False)
            card,_=emu_card.stage_project(work/'project','OCTABAM','BASS',tree=work/'tree')
            (work/'card.img').write_bytes(card)
            script=work/'keys.txt'
            script.write_text('100 key 0x32 down\n200 key 0x32 up\n1000 key 5 down\n1500 key 0x28 down\n1600 key 0x28 up\n5000 key 5 up\n6000 key 0x27 down\n6100 key 0x27 up\n6800 quit\n')
            events=run(work,'keys',['--step','-:poke:0x80000015=1',
                       '--step','-:poke:0x460d16f3=1','--step','-:poke:0x100b14cc=1',
                       '--step',f'-:call:{sym["bf_encoder"]:#x},3,4',
                       '--step','-:poke:0x100b14cc=0','--internal-clock','--live-script',script,
                       '--mem-dump',f'{sym["bf_roots"]:#x},8={work}/roots.bin'])
            balanced(events)
            bass=[e[2] for e in events if e[:2]==('on',2)]
            want={41,45,48} if dest_type==2 else {41}
            assert bass and set(bass)==want,(name,bass,want)
            assert (work/'roots.bin').read_bytes()[0]==41,(name,'lost live F root')
            lead=[e[2] for e in events if e[:2]==('on',1)]
            expected_lead={53,57,60} if source_type==2 and key_raw==0 else {53}
            assert lead and set(lead)==expected_lead,(name,lead)
            results[name]=dict(leader=lead,follower=bass)
            print(f'  [ok] {name}: live F drives rhythmic follower, including source arp ticks',flush=True)
    return results


def octave_output(source):
    """Real chromatic keys: octave selection must survive AUTO's history."""
    results={}
    for kind in (2,3):
        for spread in range(3):
            name=f'auto-octave-{kind}-{spread}'
            work=fixture(source,name,{0:kind},key_raw=2,auto=(0,),spreads={0:spread})
            script=work/'keys.txt'
            script.write_text('100 key 0x32 down\n200 key 0x32 up\n1000 key 0 down\n1500 key 0 up\n2000 key 12 down\n2500 key 12 up\n3000 key 0 down\n3500 key 0 up\n4300 quit\n')
            events=run(work,'keys',['--step','-:poke:0x80000015=1',
                       '--step','-:poke:0x460d16f3=1','--step','-:poke:0x100b14cc=0',
                       '--live-script',script])
            balanced(events)
            base=harmony.spread_notes([48,51,55]+([58] if kind==3 else []),spread)
            want=base+[n+12 for n in base]+base
            pitches=[e[2] for e in events if e[0]=='on']
            assert pitches==want,(name,pitches,want)
            results[name]=pitches
            print(f'  [ok] {name}: C minor up/down an octave, balanced live note releases',flush=True)
    return results


def spread_output(source):
    results={};sym=harmony.symbols();has_follow='bf_source_get' in sym
    # Fixed, musically readable expectations independently pin the candidate
    # search on a C/F/G progression. Machine checks cover all scales/registers.
    expected={
        (2,0,1):[60,67,76,65,72,81,67,74,83],
        (2,0,2):[60,76,79,65,81,84,67,83,86],
        (3,0,1):[60,67,71,76,65,72,76,81,67,74,77,83],
        (3,0,2):[60,76,79,83,65,81,84,88,67,83,86,89],
        (2,1,1):[60,67,76,57,65,72,59,67,74],
        (2,1,2):[60,76,79,65,81,84,67,83,86],
        (3,1,1):[60,67,71,76,60,65,69,76,59,65,67,74],
        (3,1,2):[60,76,79,83,65,81,84,88,67,83,86,89],
    }
    for (kind,auto,spread),want in expected.items():
        for arp in ((False,True) if kind==3 and auto else (False,)):
            name=f'spread-{kind}-{auto}-{spread}'+('-arp' if arp else '')
            work=fixture(source,name,{0:kind,1:1},arp=arp,first_note=60,
                         auto=(0,) if auto else (),spreads={0:spread})
            extra=['--sequencer','--internal-clock','--frames','7000']
            if has_follow:extra+=['--step','-:poke:0x100b14cc=1','--step',f'-:call:{sym["bf_encoder"]:#x},3,4']
            events=run(work,'play',extra);balanced(events)
            lead=[e[2] for e in events if e[:2]==('on',1)]
            bass=[e[2] for e in events if e[:2]==('on',2)]
            if not arp:assert lead==want,(name,lead,want)
            else:
                # The first chord lasts three arp ticks, the next two five
                # each. Do not require its unsounded fourth tone to appear.
                count=kind+1
                arp_want=want[:3]+(want[count:2*count]*2)[:5]+(want[2*count:]*2)[:5]
                assert lead==arp_want,(name,lead,arp_want)
            if has_follow:
                if not arp:assert bass==[48,36,36,41,43,43],bass
                else:assert {36,41,43}<=set(bass),bass
            results[name]=dict(leader=lead,follower=bass)
            print(f'  [ok] {name}: spaced chords, unchanged follower roots and balanced note-offs',flush=True)
    return results


def manual_inversions(source):
    results={};sym=harmony.symbols();has_follow='bf_source_get' in sym
    examples={(2,2):[64,67,72,69,72,77,71,74,79],
              (2,3):[67,72,76,72,77,81,74,79,83],
              (3,4):[71,72,76,79,76,77,81,84,77,79,83,86]}
    for kind,choice,omit in ((2,2,0),(2,3,0),(3,4,0),(2,2,1),(3,4,1),(2,2,2),(3,4,2),(3,4,3)):
        expected=examples[kind,choice]
        if omit:
            count=kind+1
            expected=[n for i,root in enumerate((60,65,67)) for n in (([root-12*(omit-1)] if omit>1 else [])+[p for p in expected[i*count:(i+1)*count] if p%12!=root%12])]
        for arp in ((False,True) if choice==4 else (False,)):
            work=fixture(source,f'manual-{kind}-{choice}'+(f'-root{omit}' if omit else '')+('-arp' if arp else ''),
                         {0:kind,1:1},arp=arp,first_note=60,voicings={0:choice},roots={0:omit})
            extra=['--sequencer','--internal-clock','--frames','7000']
            if has_follow:extra+=['--step','-:poke:0x100b14cc=1','--step',f'-:call:{sym["bf_encoder"]:#x},3,4']
            events=run(work,'play',extra);balanced(events)
            lead=[e[2] for e in events if e[:2]==('on',1)]
            bass=[e[2] for e in events if e[:2]==('on',2)]
            if not arp:assert lead==expected,(lead,expected)
            else:assert set(lead)<=set(expected) and lead[:3]==expected[:3] and {77,83}<=set(lead),lead
            if has_follow:
                if not arp:assert bass==[48,36,36,41,43,43],bass
                else:assert {36,41,43}<=set(bass),bass
            results[work.name]=dict(leader=lead,follower=bass)
            print(f'  [ok] {work.name}: manual inversion before arp, original follower root, balanced notes',flush=True)
    work=fixture(source,'omit-empty-sequence',{0:2,1:1},first_note=127,omits={0:1})
    extra=['--sequencer','--internal-clock','--frames','7000']
    if has_follow:extra+=['--step','-:poke:0x100b14cc=1','--step',f'-:call:{sym["bf_encoder"]:#x},3,4']
    events=run(work,'play',extra);balanced(events)
    lead=[e[2] for e in events if e[:2]==('on',1)]
    assert lead==[69,72,71,74],lead # empty first chord must not leak note zero
    if has_follow:
        bass=[e[2] for e in events if e[:2]==('on',2)]
        assert bass==[48,43,43,41,43,43],bass
    results[work.name]=lead
    print('  [ok] omit-empty-sequence: silent root-only chord, follower root retained, next chord recovers',flush=True)
    work=fixture(source,'manual-page',{0:3})
    script=work/'page.txt'
    script.write_text('100 key 0x32 down\n200 key 0x32 up\n600 key 0x2d down\n700 key 0x22 down\n850 key 0x22 up\n950 key 0x2d up\n1400 key 0x3d down\n1500 key 0x3d up\n2000 enc 1 3\n2100 enc 2 2\n2150 enc 3 1\n2200 key 0 down\n2300 key 0 up\n2400 key 5 down\n2500 key 5 up\n3000 quit\n')
    events=run(work,'page',['--step','-:poke:0x80000015=1','--step','-:poke:0x460d16f3=1',
                    '--step','-:poke:0x100b14cc=0','--live-script',script,'--lcd',work/'page.lcd',
                    '--mem-dump',f'0x100a4ece,6322={work}/state.bin'])
    state=(work/'state.bin').read_bytes()
    assert state[0x4e2+5]==2 and state[0x4e2+16]==52
    balanced(events)
    assert [e[2] for e in events if e[0]=='on']==[59,76,79,64,81,84],events
    subprocess.run([sys.executable,str(ROOT/'tools/emu/lcd_view.py'),str(work/'page.lcd'),'--png',str(work/'page.png')],check=True)
    results['manual-page']='pass'
    print('  [ok] manual-page: physical encoder 3RD/WIDE/OMIT ROOT, live chord MIDI and five-position widget capture',flush=True)
    return results


def root_live(source):
    results={}
    for mode in (2,3):
        drop=12*(mode-1)
        for arp in (False,True):
            work=fixture(source,f'root-live-{mode}-{int(arp)}',{0:3},arp=arp,roots={0:mode})
            script=work/'keys.txt'
            # C and E share two upper tones. Change ROOT while both are held;
            # both releases must still own the exact pitches sounded earlier.
            script.write_text('100 key 0x32 down\n200 key 0x32 up\n600 key 0x2d down\n700 key 0x22 down\n850 key 0x22 up\n950 key 0x2d up\n1100 key 0x3d down\n1200 key 0x3d up\n1500 key 0 down\n2300 key 4 down\n3100 enc 3 -3\n3300 key 0 up\n4100 key 4 up\n5000 quit\n')
            events=run(work,'keys',['--step','-:poke:0x80000015=1','--step','-:poke:0x460d16f3=1',
                       '--step','-:poke:0x100b14cc=0','--internal-clock','--live-script',script])
            balanced(events)
            pitches=[e[2] for e in events if e[0]=='on']
            want={48-drop,52-drop,52,55,59,62}
            assert set(pitches)==want,(work.name,pitches,want)
            results[work.name]=pitches
        work=fixture(source,f'root-page-{mode}',{0:3})
        script=work/'page.txt'
        script.write_text(f'100 key 0x32 down\n200 key 0x32 up\n600 key 0x2d down\n700 key 0x22 down\n850 key 0x22 up\n950 key 0x2d up\n1100 key 0x3d down\n1200 key 0x3d up\n1400 enc 3 {mode}\n1600 key 0 down\n1800 key 0 up\n2100 quit\n')
        events=run(work,'page',['--step','-:poke:0x80000015=1','--step','-:poke:0x460d16f3=1',
                   '--step','-:poke:0x100b14cc=0','--live-script',script,'--lcd',work/'page.lcd'])
        balanced(events)
        assert [e[2] for e in events if e[0]=='on']==[48-drop,52,55,59],events
        subprocess.run([sys.executable,str(ROOT/'tools/emu/lcd_view.py'),str(work/'page.lcd'),'--png',str(work/'page.png')],check=True)
        results[work.name]='pass'
    print('  [ok] ROOT live: octave placement, shared-tone ownership, edits while held, arp and physical encoder/LCD',flush=True)
    return results


def live_transpose(source):
    """Physical TRAN edits during live keys/arp; record exact release ownership."""
    import verify_chord_play_port as chord
    results={}
    qualities=((36,39,43),(36,39,43,46),(36,39,43,50),(36,38,43),
               (36,41,43),(36,40,43),(36,39,43),(36,40,43,46))
    # mode, HARM, quality, arp, offset, octave, voicing, spread, ROOT
    cases=[('chromatic',kind,1,arp,7,3,0,0,0) for kind in (1,2) for arp in (False,True)]
    cases += [('chord-play',2,1,False,7,3,0,0,0)]
    cases += [('chord-play',2,q,True,7,3,0,0,0) for q in range(8)]
    cases += [('chord-play',2,1,True,d,3,0,0,0) for d in (-12,1,12)]
    cases += [('chord-play',2,1,True,7,3,2,1,2),
              ('chord-play',2,1,True,12,9,0,0,0),
              ('chord-play',2,1,True,-12,0,0,0,0)]
    for mode,kind,q,arp,delta,octave,voic,spread,root in cases:
        name=f'transpose-{mode}-h{kind}-q{q}-a{int(arp)}-d{delta}-o{octave}-v{voic}-s{spread}-r{root}'
        work=fixture(source,name,{0:kind},key_raw=2,arp=arp,voicings={0:voic},spreads={0:spread},roots={0:root})
        sym=harmony.symbols()
        extra=['--step',f'-:poke:0x400beba5={octave}']
        if mode=='chord-play':
            script=chord.PANEL+f'1700 key {8+q} down\n2000 key 0 down\n'+chord.key(2400,0x23)
        else:
            extra+=['--step','-:poke:0x80000015=1','--step','-:poke:0x460d16f3=1','--step','-:poke:0x100b14cc=0','--step',f'-:poke:{sym["ch_live"]:#x}={q}']
            script=chord.key(100,0x31)+chord.key(500,0x23)+'2000 key 0 down\n'
        script+=f'3000 enc 0 {delta}\n5000 key 0 up\n'
        if not arp:script+='5500 key 0 down\n6500 key 0 up\n'
        if mode=='chord-play':script+=f'6700 key {8+q} up\n'
        script+='7100 quit\n'
        path=work/'keys.txt';path.write_text(script)
        events=run(work,'keys',extra+['--rtc','1800000000','--internal-clock','--live-script',path,'--lcd',work/'screen.lcd','--mem-dump',f'0x46c76fec,1={work}/tran.bin'],physical_panel=True)
        balanced(events)
        assert (work/'tran.bin').read_bytes()==bytes((64+delta,))
        notes=[e[2] for e in events if e[:2]==('on',1)]
        before=[36] if kind==1 else list(qualities[q])
        before=[n+12*(octave-3) for n in before]
        if voic:before=[24,39,46,55] # 1ST + OPEN + ROOT -1 OCT, all before TRAN
        shifted=[]
        for note in before:
            value=note+delta
            if 0<=value<=127:
                if kind==1 or q<5:
                    value=min((n for n in range(128) if n%12 in harmony.MODES[5]),key=lambda n:(abs(n-value),n))
                shifted.append(value)
        if arp:assert set(notes)==set(before+shifted),(name,notes,before,shifted)
        else:assert notes==before*2,(name,notes,before)
        results[name]=dict(before=before,transposed=shifted if arp else before,actual=notes)
        print(f'  [ok] {name}: {before} -> {shifted if arp else before}; balanced releases',flush=True)
        # Preserve scripts/UART/LCD and project fixtures; discard generated card copies.
        for file in work.glob('*.img'):file.unlink()
        import shutil
        shutil.rmtree(work/'tree')
    return results


def live_transpose_cleanup(source):
    """Leaving CHORD PLAY releases transposed arp notes with keys still held."""
    import shutil
    import verify_chord_play_port as chord
    results={}
    for name,end in (
        ('grid',chord.key(3500,0x29)),
        ('mode','3500 key 0x2d down\n3600 key 0x20 down\n3650 key 0x20 up\n3800 key 0x20 down\n3850 key 0x20 up\n4000 key 0x2d up\n'),
    ):
        work=fixture(source,f'transpose-leave-{name}',{0:2},key_raw=2,arp=True)
        script=work/'keys.txt'
        script.write_text(chord.PANEL+'1700 key 9 down\n2000 key 0 down\n'+chord.key(2400,0x23)+'3000 enc 0 7\n'+end+'4500 quit\n')
        # TRAN is a native pitch control. Its raw report must not be expanded
        # into the four-count choices used by HARM/DEG/CHRD enumerations.
        events=run(work,'keys',['--rtc','1800000000','--internal-clock','--live-script',script,
            '--mem-dump',f'0x46c76fec,1={work}/tran.bin'],physical_panel=True)
        assert (work/'tran.bin').read_bytes()==bytes((71,))
        balanced(events)
        notes=[e[2] for e in events if e[:2]==('on',1)]
        assert {48,51,55,58}<=set(notes) and set(notes)&{62,65},notes
        results[f'transpose-leave-{name}']=dict(actual=notes,balanced_with_keys_held=True)
        print(f'  [ok] transpose-leave-{name}: transposed arp releases before physical key-up',flush=True)
        for card in work.glob('*.img'):card.unlink()
        shutil.rmtree(work/'tree')
    return results


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project',required=True,type=pathlib.Path)
    ap.add_argument('--settings-only',action='store_true',help='native Part project SAVE, disk load, CS1 resume and fresh defaults')
    ap.add_argument('--live-transpose-only',action='store_true',help='stock-compatible live arp TRAN, direct-key identity, qualities and releases')
    ap.add_argument('--root-only',action='store_true',help='ROOT placement, arp, follower, recording, UI and persistence')
    ap.add_argument('--bypass-follow-only',action='store_true',help='live HARM OFF / KEY OFF source with rhythmic MIDI followers')
    ap.add_argument('--octave-only',action='store_true',help='live AUTO octave-jump regressions in C minor')
    ap.add_argument('--recording-only',action='store_true',help='run the recording and explicit-empty-lock regressions')
    ap.add_argument('--spread-only',action='store_true',help='run the spaced sequence/arp and follower-root cases')
    ap.add_argument('--inversions-only',action='store_true',help='manual MIDI/arp/follow, recording and persistence')
    ap.add_argument('--voicing-only',action='store_true',help='run AUTO MIDI, page, persistence and recording regressions')
    a=ap.parse_args();OUT.mkdir(exist_ok=True)
    freeze_candidate(OUT)
    if a.settings_only:
        cases=persistence(a.project)
        (OUT/'result-settings.json').write_text(json.dumps(dict(cases=cases,image_sha256=hashlib.sha256(CANDIDATE_IMAGE.read_bytes()).hexdigest(),hardware_tested=False),indent=2)+'\n')
        return
    if a.live_transpose_only:
        cases=live_transpose(a.project)
        cases.update(live_transpose_cleanup(a.project))
        (OUT/'result-live-transpose.json').write_text(json.dumps(dict(cases=cases,image_sha256=hashlib.sha256(CANDIDATE_IMAGE.read_bytes()).hexdigest(),hardware_tested=False),indent=2)+'\n')
        return
    if a.root_only:
        cases=manual_inversions(a.project);cases.update(recording(a.project));cases.update(root_live(a.project))
        cases.update(persistence(a.project,4,2));cases.update(persistence(a.project,1,3))
        (OUT/'result-root.json').write_text(json.dumps(dict(cases=cases,image_sha256=hashlib.sha256(CANDIDATE_IMAGE.read_bytes()).hexdigest(),hardware_tested=False),indent=2)+'\n')
        return
    if a.bypass_follow_only:
        cases=bypass_follow(a.project)
        (OUT/'result-bypass-follow.json').write_text(json.dumps(dict(cases=cases,image_sha256=hashlib.sha256(CANDIDATE_IMAGE.read_bytes()).hexdigest(),hardware_tested=False),indent=2)+'\n')
        return
    if a.octave_only:
        cases=octave_output(a.project)
        (OUT/'result-octave.json').write_text(json.dumps(dict(cases=cases,image_sha256=hashlib.sha256(CANDIDATE_IMAGE.read_bytes()).hexdigest(),hardware_tested=False),indent=2)+'\n')
        return
    if a.inversions_only:
        cases=manual_inversions(a.project);cases.update(recording(a.project));cases.update(persistence(a.project,4,1))
        (OUT/'result-inversions.json').write_text(json.dumps(dict(cases=cases,image_sha256=hashlib.sha256(CANDIDATE_IMAGE.read_bytes()).hexdigest(),hardware_tested=False),indent=2)+'\n')
        return
    if a.spread_only:
        cases=spread_output(a.project)
        (OUT/'result-spread.json').write_text(json.dumps(dict(cases=cases,image_sha256=hashlib.sha256(CANDIDATE_IMAGE.read_bytes()).hexdigest(),hardware_tested=False),indent=2)+'\n')
        return
    if a.voicing_only:
        cases=spread_output(a.project);cases.update(auto_voicing(a.project));cases.update(recording(a.project));cases.update(persistence(a.project))
        (OUT/'result-voicing.json').write_text(json.dumps(dict(cases=cases,image_sha256=hashlib.sha256(CANDIDATE_IMAGE.read_bytes()).hexdigest(),hardware_tested=False),indent=2)+'\n')
        return
    if a.recording_only:
        cases=recording(a.project);cases.update(empty_note_locks(a.project))
        (OUT/'result-recording.json').write_text(json.dumps(dict(cases=cases,image_sha256=hashlib.sha256(CANDIDATE_IMAGE.read_bytes()).hexdigest(),hardware_tested=False),indent=2)+'\n')
        return
    cases=sequence(a.project)
    cases.update(extended_scale(a.project))
    cases.update(keyboard(a.project))
    cases.update(note_rules(a.project))
    cases.update(chord_rules(a.project))
    cases.update(live_transpose(a.project))
    cases.update(live_transpose_cleanup(a.project))
    cases.update(recording(a.project))
    cases.update(empty_note_locks(a.project))
    cases.update(persistence(a.project))
    cases.update(auto_voicing(a.project))
    cases.update(octave_output(a.project))
    cases.update(bypass_follow(a.project))
    cases.update(spread_output(a.project))
    cases.update(manual_inversions(a.project))
    cases.update(persistence(a.project,4,1))
    cases.update(persistence(a.project,4,2))
    cases.update(persistence(a.project,1,3))
    cases.update(root_live(a.project))
    (OUT/'result.json').write_text(json.dumps(dict(cases=cases,image_sha256=hashlib.sha256(CANDIDATE_IMAGE.read_bytes()).hexdigest(),hardware_tested=False),indent=2)+'\n')
if __name__=='__main__':main()
