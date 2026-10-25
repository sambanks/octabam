#!/usr/bin/env python3
"""RFOL register UI and MIDI output using disposable virtual cards only."""
import argparse,json,hashlib,re,subprocess,sys
from pathlib import Path
import verify_midi_follow as f
from midi_fixture import fixture,notes
from hw import ot_project as otp
import emu_card
ROOT=f.ROOT

def panel(text):
    # Logical choices use four raw UART counts; never skip a choice per report.
    def expand(m):
        t,knob,steps=map(int,m.groups())
        if knob in (0,1):knob+=1 # RFOL now occupies A; MODE/OCT are B/C.
        return ''.join(f'{t+i*35} enc {knob} {4 if steps>0 else -4}\n' for i in range(abs(steps)))
    return re.sub(r'(?m)^(\d+) enc (\d+) (-?\d+)\n',expand,text)


def settings(work):
    part=(work/'part-after.bin').read_bytes()
    return bytes([part[0x4e2+36*t+12]&1 for t in range(8)]+
                 [part[0x4e2+36*t+13] for t in range(8)]+
                 [(part[0x4e2+36*t+15]-2)&255 for t in range(8)])


def guard_parts(work):
    before=(work/'part-before.bin').read_bytes()
    after=(work/'part-after.bin').read_bytes()
    allowed={0x4e2+36*t+field for t in range(8) for field in (3,12,13,15)}
    changed={i for i,(a,b) in enumerate(zip(before,after)) if a!=b}
    assert len(before)==len(after)==25288
    assert changed<=allowed,(work,sorted(changed-allowed))


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--project',type=Path,required=True)
    ap.add_argument('--build-root',type=Path,default=ROOT,help='Checkout providing the image and linked symbols; emulator stays local')
    ap.add_argument('--harmony',action='store_true',help='Source CHORD with ROOT -2 OCT, receiver NOTE')
    a=ap.parse_args()
    out=ROOT/('out/follow-register-harmony-port' if a.harmony else 'out/follow-register-port');out.mkdir(exist_ok=True)
    image=out/'candidate.bin';image.write_bytes((a.build_root/'out/mainos_bus.bin').read_bytes())
    f.ROOT=a.build_root
    sym=f.symbols();(out/'symbols.json').write_text(json.dumps(sym,indent=2)+'\n')
    project=out/'project';fixture(a.project,project)
    for path in project.glob('bank*.work'):
        def mutate(data):
            for part in range(8):
                base=otp.PART_BASE+part*otp.PART_STRIDE+9
                for track in range(8):
                    setup=base+0x4e2+36*track
                    data[setup+17]=1 if a.harmony else 0
                    data[setup+5]=(2 if track==0 else 1 if track==1 else 0) if a.harmony else 0
                    data[setup+16]=96 if a.harmony and track==0 else 0
            for pat in range(16):
                for trk in range(8):
                    at=0x492e+pat*0x8eec+trk*0x8b9
                    data[at+9:at+33]=bytes(24);data[at+0x39:at+0x839]=b'\xff'*2048
                    entries={0:36,8:60,16:50} if trk==0 else {1:48,9:48,17:48} if trk==1 else {}
                    if pat==0:
                        data[at+9:at+17]=sum(1<<s for s in entries).to_bytes(8,'big')
                        for step,note in entries.items():data[at+0x39+step*32:at+0x39+step*32+3]=bytes((note,100,6))
        otp._bank_write(project,int(path.stem[4:]),mutate,guard=False)
    card,_=emu_card.stage_project(project,'OCTABAM','BASS',tree=out/'tree');(out/'card.img').write_bytes(card)
    setup='100 key 0x31 down\n150 key 0x31 up\n300 key 0x35 down\n350 key 0x35 up\n500 key 0x11 down\n550 key 0x11 up\n700 key 0x2d down\n800 key 0x22 down\n850 key 0x22 up\n900 key 0x2d up\n1100 enc 3 1\n1300 key 0x3b down\n1350 key 0x3b up\n'
    cases={}
    for mode,octave in [(0,3),(0,4),(1,0),(1,-2),(1,2)]:
        name=f'mode{mode}-oct{octave}';work=out/name;work.mkdir(exist_ok=True)
        script=work/'panel.txt';script.write_text(panel(setup+f'1500 enc 0 {mode}\n1600 enc 0 {1 if mode else -1}\n1700 enc 1 {octave-(3 if mode==0 else 0)}\n1900 key 0x28 down\n1950 key 0x28 up\n5200 key 0x27 down\n5250 key 0x27 up\n5600 quit\n'))
        dump=f'{sym["bf_pitches"]:#x},8={work}/pitches.bin;{sym["bf_page_win"]:#x},4={work}/window.bin;0x100a4ece,25288={work}/part-after.bin'
        cmd=[str(ROOT/'out/emu/ot_emu'),'--image',str(image),'--card',str(out/'card.img'),'--set','OCTABAM','--project','BASS','--load-ms','90000','--mkii','--rtc','1800000000','--internal-clock','--live-script',str(script),'--midi-out',str(work/'notes.midi'),'--lcd',str(work/'screen.lcd'),'--step',f'-:dump:0x100a4ece,25288={work}/part-before.bin','--mem-dump',dump]
        with (work/'run.log').open('w') as log:r=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        assert r.returncode==0,(name,r.returncode)
        events=notes((work/'notes.midi').read_bytes());(work/'notes.json').write_text(json.dumps(events)+'\n')
        if a.harmony:
            source=[e[2] for e in events if e[:2]==('on',1)]
            assert source==[12,40,43,36,64,67,26,53,57],(name,source)
        received=[e[2] for e in events if e[:2]==('on',2)]
        wanted=[(n if mode else n%12)+12*octave for n in (36,60,50)]
        assert received==wanted,(name,received,wanted)
        state=settings(work);assert state[1]==mode
        assert state[(16 if mode else 8)+1]==octave&255,state
        assert state[(8 if mode else 16)+1]==(3 if mode else 0), 'B/C touched the other mode octave'
        assert all(state[t]==0 and state[8+t]==3 and state[16+t]==0 for t in range(8) if t!=1)
        assert (work/'window.bin').read_bytes()!=bytes(4)
        guard_parts(work)
        held=set()
        for kind,ch,n,_ in events:
            if kind=='on':assert (ch,n) not in held;held.add((ch,n))
            else:assert (ch,n) in held;held.remove((ch,n))
        assert not held,held
        subprocess.run([sys.executable,str(ROOT/'tools/emu/lcd_view.py'),str(work/'screen.lcd'),'--png',str(work/'screen.png')],check=True,stdout=subprocess.DEVNULL)
        cases[name]=received;print('[ok]',name,received,flush=True)
    # Close, switch tracks, edit independently, reopen, and restore native UI.
    lifecycle=out/'lifecycle';lifecycle.mkdir(exist_ok=True)
    script=lifecycle/'panel.txt'
    script.write_text(panel(setup+'1500 enc 0 1\n1700 enc 1 2\n1900 key 0x32 down\n1950 key 0x32 up\n2100 key 0x12 down\n2150 key 0x12 up\n2300 key 0x3b down\n2350 key 0x3b up\n2500 enc 1 1\n2700 key 0x32 down\n2750 key 0x32 up\n2900 key 0x11 down\n2950 key 0x11 up\n3100 key 0x3b down\n3150 key 0x3b up\n3300 key 0x32 down\n3350 key 0x32 up\n3500 quit\n'))
    cmd=[arg.replace(str(work)+'/',str(lifecycle)+'/') for arg in cmd]
    with (lifecycle/'run.log').open('w') as log:
        result=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    assert result.returncode==0
    state=settings(lifecycle)
    assert state[1]==1 and state[17]==2 and state[2]==0 and state[10]==4,state
    assert (lifecycle/'window.bin').read_bytes()==bytes(4)
    guard_parts(lifecycle)
    print('[ok] close/reopen, independent receiver settings, only native Follow fields changed',flush=True)
    # A on FOLLOW edits RFOL itself, then closing must redraw the parent.
    sync=out/'source-sync';sync.mkdir(exist_ok=True)
    (sync/'panel.txt').write_text(panel(setup)+'1500 enc 0 4\n1800 key 0x32 down\n1850 key 0x32 up\n2200 quit\n')
    sync_cmd=[arg.replace(str(lifecycle)+'/',str(sync)+'/') for arg in cmd]
    with (sync/'run.log').open('w') as log:
        result=subprocess.run(sync_cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    assert result.returncode==0
    assert (sync/'part-after.bin').read_bytes()[0x4e2+36+3]==3 # skip the receiving T2
    assert (sync/'window.bin').read_bytes()==bytes(4)
    guard_parts(sync)
    subprocess.run([sys.executable,str(ROOT/'tools/emu/lcd_view.py'),str(sync/'screen.lcd'),'--png',str(sync/'screen.png')],check=True,stdout=subprocess.DEVNULL)
    print('[ok] FOLLOW A selects RFOL T3 and closes to refreshed NOTE SETUP',flush=True)
    (out/'receipt.json').write_text(json.dumps(dict(cases=cases,image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),ui_lifecycle=True,harmony=a.harmony,build_root=str(a.build_root),emulator=str(ROOT/'out/emu/ot_emu'),hardware_tested=False),indent=2)+'\n')
if __name__=='__main__':main()
