#!/usr/bin/env python3
"""Full firmware: physical Follow controls, register melodies and native note-offs."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import verify_midi_follow as f
from midi_fixture import fixture, notes
from verify_midi_follow_response_port import SETUP
from hw import ot_project as otp
import emu_card


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--project',type=Path,required=True)
    a=ap.parse_args();root=f.ROOT;out=root/'out/follow-gravity-port';out.mkdir(exist_ok=True)
    image=out/'candidate.bin';image.write_bytes((root/'out/mainos_bus.bin').read_bytes())
    results={}
    # Visit every mode, set its independent control, then return to the target.
    edits='1500 enc 2 -4\n1600 enc 1 4\n1700 enc 2 -4\n1800 enc 1 4\n1900 enc 2 -4\n'
    for mode,response in ((0,0),(1,0),(2,0),(1,1)):
        work=out/f'mode-{mode}-response-{response}';work.mkdir(exist_ok=True)
        project=work/'project';fixture(a.project,project)
        for path in project.glob('bank*.work'):
            def mutate(data):
                for step,note in ((2,59),(4,72),(8,53)):
                    data[0x492e+0x39+step*32]=note
            otp._bank_write(project,int(path.stem[4:]),mutate,guard=False)
        card,_=emu_card.stage_project(project,'OCTABAM','BASS',tree=work/'tree')
        (work/'card.img').write_bytes(card)
        select=''.join(f'{2000+100*i} enc 1 -4\n' for i in range(2-mode))
        script=work/'panel.txt'
        script.write_text(SETUP+edits+select+('2300 enc 3 4\n' if response else '')+
                          '2400 enc 4 4\n2450 enc 5 -4\n2500 key 0x28 down\n2550 key 0x28 up\n'
                          '5800 key 0x27 down\n5850 key 0x27 up\n6200 quit\n')
        cmd=[str(root/'out/emu/ot_emu'),'--image',str(image),'--card',str(work/'card.img'),
             '--set','OCTABAM','--project','BASS','--load-ms','90000','--mkii','--rtc','1800000000',
             '--internal-clock','--live-script',str(script),'--midi-out',str(work/'notes.midi'),
             '--lcd',str(work/'screen.lcd'),'--mem-dump',f'0x100a4ece,6322={work}/part.bin']
        with (work/'run.log').open('w') as log:
            r=subprocess.run(cmd,cwd=root,stdout=log,stderr=subprocess.STDOUT)
        assert r.returncode==0,work
        state=(work/'part.bin').read_bytes();at=0x4e2+36
        assert (state[at+3],state[at+12],state[at+13],state[at+15])==(1,response*2,18,2+mode*16)
        events=notes((work/'notes.midi').read_bytes())
        bass=[e[2] for e in events if e[:2]==('on',2)]
        want=([48,35,35,24,29,29] if mode==0 else [48,47,47,60,41,41] if mode==2
              else [48,35,35,36,36,29,29] if response else [48,35,35,36,29,29])
        assert bass==want,(mode,response,bass,want)
        held=set()
        for kind,ch,n,_ in events:
            if kind=='on':assert (ch,n) not in held;held.add((ch,n))
            else:assert (ch,n) in held;held.remove((ch,n))
        assert not held
        subprocess.run([sys.executable,str(root/'tools/emu/lcd_view.py'),str(work/'screen.lcd'),
                        '--png',str(work/'screen.png')],check=True,stdout=subprocess.DEVNULL)
        results[work.name]=bass
        print('[ok]',work.name,bass,'panel settings, unused E/F, balanced MIDI',flush=True)
    (out/'receipt.json').write_text(json.dumps(dict(image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
        cases=results,hardware_tested=False),indent=2)+'\n')

if __name__=='__main__':main()
