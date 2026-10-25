#!/usr/bin/env python3
"""Physical RFOL response encoder and sequencer MIDI capture on a frozen image."""
import argparse,hashlib,json,re,subprocess,sys
from pathlib import Path
import verify_midi_follow as f
from midi_fixture import fixture,notes
from hw import ot_project as otp
import emu_card
ROOT=f.ROOT
SETUP='100 key 0x31 down\n150 key 0x31 up\n300 key 0x35 down\n350 key 0x35 up\n500 key 0x11 down\n550 key 0x11 up\n700 key 0x2d down\n800 key 0x22 down\n850 key 0x22 up\n900 key 0x2d up\n1100 enc 3 4\n1300 key 0x3b down\n1350 key 0x3b up\n'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--project',type=Path,required=True);ap.add_argument('--harmony',action='store_true');a=ap.parse_args()
    out=ROOT/'out/follow-response-port';out.mkdir(exist_ok=True)
    image=out/'candidate.bin';image.write_bytes((ROOT/'out/mainos_bus.bin').read_bytes())
    sym=f.symbols();results={}
    for mode,arp,harmony in [(m,arp,h) for h in ((False,True) if a.harmony else (False,)) for arp in (False,True) for m in (0,1)]:
        name=f'response-{mode}-arp-{int(arp)}-harmony-{int(harmony)}'
        work=out/name;work.mkdir(exist_ok=True)
        project=work/'project';fixture(a.project,project)
        for bank in project.glob('bank*.work'):
            def mutate(data):
                for part in range(8):
                    base=otp.PART_BASE+part*otp.PART_STRIDE+9
                    data[base+0x4e2+5]=int(harmony)
                    data[base+0x4e2+36+5]=int(harmony)
                    data[base+0x4e2+17]=1 if harmony else 0
                    data[base+0x4e2+36+17]=1 if harmony else 0
                    if arp:
                        data[base+0x3e2+32+14]=1
                        data[base+0x3e2+32+15]=3
            otp._bank_write(project,int(bank.stem[4:]),mutate,guard=False)
        card,_=emu_card.stage_project(project,'OCTABAM','BASS',tree=work/'tree');(work/'card.img').write_bytes(card)
        script=work/'panel.txt'
        script.write_text(SETUP+('1500 enc 3 4\n' if mode else '')+'1900 key 0x28 down\n1950 key 0x28 up\n5200 key 0x27 down\n5250 key 0x27 up\n5600 quit\n')
        cmd=[str(ROOT/'out/emu/ot_emu'),'--image',str(image),'--card',str(work/'card.img'),'--set','OCTABAM','--project','BASS','--load-ms','90000','--mkii','--rtc','1800000000','--internal-clock','--live-script',str(script),'--midi-out',str(work/'notes.midi'),'--lcd',str(work/'screen.lcd'),'--mem-dump',f'0x100a4ece,6322={work}/part.bin']
        with (work/'run.log').open('w') as log:r=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        assert r.returncode==0,work
        events=notes((work/'notes.midi').read_bytes());(work/'notes.json').write_text(json.dumps(events,indent=2)+'\n')
        state=(work/'part.bin').read_bytes()
        assert state[0x4e2+36+3]==1
        assert bytes((state[0x4e2+36*t+12]>>1)&1 for t in range(8))==bytes((0,mode,0,0,0,0,0,0))
        bass=[e[2] for e in events if e[:2]==('on',2)]
        want=[48,36,36,41,43,43] if not mode else [48,36,36,41,41,43,43]
        if not arp:assert bass==want,(name,bass,want)
        else:
            f_index=next(i for i,e in enumerate(events) if e[:3]==('on',1,65))
            next_bass=next(e[2] for e in events[f_index+1:] if e[:2]==('on',2))
            assert len(bass)>6,(name,bass)
            assert next_bass==(41 if mode or not harmony else 36),(name,next_bass,events)
        held=set()
        for kind,ch,n,_ in events:
            if kind=='on':assert (ch,n) not in held,(mode,events);held.add((ch,n))
            else:assert (ch,n) in held,(mode,events);held.remove((ch,n))
        assert not held
        subprocess.run([sys.executable,str(ROOT/'tools/emu/lcd_view.py'),str(work/'screen.lcd'),'--png',str(work/'screen.png')],check=True,stdout=subprocess.DEVNULL)
        results[name]=bass;print('[ok]',name,':',bass,'balanced MIDI',flush=True)
    if a.harmony:
        import verify_chord_play_port as chord
        for mode in (0,1):
            name=f'live-source-{mode}'
            work=out/name;work.mkdir(exist_ok=True)
            project=work/'project';fixture(a.project,project)
            for bank in project.glob('bank*.work'):
                def mutate_live(data):
                    for part in range(8):
                        base=otp.PART_BASE+part*otp.PART_STRIDE+9
                        for t in (0,1):
                            data[base+0x4e2+36*t+17]=1
                            data[base+0x4e2+36*t+5]=2 if t==0 else 1
                        data[base+0x4e2+36+3]=1
                        data[base+0x4e2+36+12]=mode<<1
                    for pat in range(16):
                        for t in range(8):
                            at=0x492e+pat*0x8eec+t*0x8b9
                            data[at+9:at+33]=bytes(24)
                            if pat==0 and t==1:
                                data[at+9:at+17]=(1).to_bytes(8,'big')
                                data[at+0x39:at+0x39+3]=bytes((48,91,127))
                otp._bank_write(project,int(bank.stem[4:]),mutate_live,guard=False)
            card,_=emu_card.stage_project(project,'OCTABAM','BASS',tree=work/'tree');(work/'card.img').write_bytes(card)
            script=work/'panel.txt'
            script.write_text(chord.PANEL+'1600 key 0 down\n1750 key 0 up\n1900 key 0x28 down\n1950 key 0x28 up\n2600 key 3 down\n2750 key 3 up\n3300 key 4 down\n3450 key 4 up\n4200 key 0x27 down\n4250 key 0x27 up\n4500 quit\n')
            cmd=[str(ROOT/'out/emu/ot_emu'),'--image',str(image),'--card',str(work/'card.img'),'--set','OCTABAM','--project','BASS','--load-ms','90000','--mkii','--rtc','1800000000','--internal-clock','--live-script',str(script),'--midi-out',str(work/'notes.midi')]
            with (work/'run.log').open('w') as log:r=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            assert r.returncode==0,work
            events=notes((work/'notes.midi').read_bytes());(work/'notes.json').write_text(json.dumps(events,indent=2)+'\n')
            bass=[e[2] for e in events if e[:2]==('on',2)]
            assert bass==([36,41,43] if mode else [36]),(name,bass,events)
            held=set()
            for kind,ch,n,_ in events:
                if kind=='on':assert (ch,n) not in held;held.add((ch,n))
                else:assert (ch,n) in held;held.remove((ch,n))
            assert not held
            results[name]=bass;print('[ok]',name,':',bass,'live Chord Play over sustained bass, balanced MIDI',flush=True)
    (out/'receipt.json').write_text(json.dumps({'sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'cases':results},indent=2)+'\n')
if __name__=='__main__':main()
