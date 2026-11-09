#!/usr/bin/env python3
"""CHORD PLAY panel, UART, recording and companion lifecycle regression.

Use a disposable copy of a local template. Never mounts or opens a device.
All evidence, including the immutable tested image, stays in ignored out/.
"""
import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path
import verify_chord_play as c
import verify_midi_harmony_port as p

OUT=c.ROOT/'out/chord-play-port'
SYMBOLS={}
EXPECTED=[48,51,55,48,51,55,58,48,53,55,53,56,60]
# Dismiss the startup dialog with NO; YES can accept a project action.
PANEL='''100 key 0x32 down
150 key 0x32 up
300 key 0x35 down
350 key 0x35 up
500 key 0x22 down
550 key 0x22 up
700 key 0x2d down
800 key 0x20 down
850 key 0x20 up
1000 key 0x20 down
1050 key 0x20 up
1150 key 0x20 down
1200 key 0x20 up
1300 key 0x2d up
'''
RECORD='''1600 key 0x29 down
1700 key 0x28 down
1800 key 0x28 up
1900 key 0x29 up
2600 key 0 down
3100 key 9 down
3600 key 12 down
3800 key 9 up
4100 key 12 up
4400 key 0 up
4600 key 3 down
4900 key 3 up
5400 key 0x29 down
5500 key 0x29 up
15500 key 0x27 down
15600 key 0x27 up
'''
SAVE='''16000 key 0x1c down
16100 key 0x1c up
17300 key 0x21 down
17400 key 0x21 up
18100 key 0x20 down
18200 key 0x20 up
18800 key 0x31 down
18900 key 0x31 up
20200 key 0x31 down
20300 key 0x31 up
65000 quit
'''


def dump(work,name):
    return f'{SYMBOLS["mhc_lock_table"]:#x},131072={work}/{name}-locks.bin;0x400e21e0,0x9b340={work}/{name}-bank.bin;{SYMBOLS["mhc_lock_status"]:#x},16={work}/{name}-status.bin;{SYMBOLS["mhc_record_overflow"]:#x},4={work}/{name}-overflow.bin;0x10000000,0x100000={work}/{name}-cs1.bin;0x460ba98c,4={work}/{name}-leds.bin'


def run(work,name,script,card=None,extra=()):
    path=work/f'{name}.txt';path.write_text(script)
    events=p.run(work,name,['--rtc','1800000000','--live-script',path,'--internal-clock',
        '--lcd',work/f'{name}.lcd','--mem-dump',dump(work,name),*extra],card=card)
    p.balanced(events)
    assert (work/f'{name}-overflow.bin').read_bytes()==bytes(4),name
    return events


def record_save(source,root_mode=0):
    p.OUT=OUT
    assert root_mode in range(4)
    work=p.fixture(source,'record-save'+(f'-root{root_mode}' if root_mode else ''),{0:2},key_raw=2,roots={0:root_mode})
    chords=((48,51,55),(48,51,55,58),(48,53,55),(53,56,60))
    expected=EXPECTED if root_mode==0 else [n for chord in chords for n in
        (([chord[0]-12*(root_mode-1)] if root_mode>1 else [])+list(chord[1:]))]
    for path in (work/'project').glob('bank*.work'):
        def blank(data):
            for pat in range(16):
                for track in range(8):
                    at=0x492e+pat*0x8eec+track*0x8b9
                    data[at+9:at+33]=bytes(24)
                    data[at+0x39:at+0x839]=b'\xff'*2048
        p.otp._bank_write(work/'project',int(path.stem[4:]),blank,guard=False)
    card,_=p.emu_card.stage_project(work/'project','OCTABAM','BASS',tree=work/'blank-tree')
    (work/'card.img').write_bytes(card)
    events=run(work,'save',PANEL+RECORD+SAVE)
    actual=[e[2] for e in events if e[:2]==('on',1)]
    assert actual==expected*2,(actual,expected*2)
    bank=(work/'save-bank.bin').read_bytes();locks=(work/'save-locks.bin').read_bytes()
    steps=[(i,bank[0x4900+i*32],locks[i]) for i in range(64) if bank[0x4900+i*32]<128]
    assert steps==[(7,48,0),(11,48,1),(15,48,4),(23,53,0)],steps
    for step,root,q in steps:
        assert bank[0x4903+step*32:0x4906+step*32]==b'\xff'*3
    files=p.emu_card.extract_image((work/'save-card.img').read_bytes())
    for suffix in ('work','strd'):
        data=files[f'OCTABAM/BASS/chrd01.{suffix}']
        assert len(data)==8224 and data[:8]==b'CHD2'+(2).to_bytes(4,'big')
        assert data[32:]==locks[:8192]
    for bank in range(2,17):
        assert files[f'OCTABAM/BASS/chrd{bank:02d}.strd']==b'CHD0'+bytes(28)
    print('[ok] actual mode selector, REC+PLAY, recorded physical NOTE+CHRD, replay and complete SAVE/store',flush=True)
    # Fresh disk load and the firmware's own current-bank resume.
    script='100 key 0x32 down\n200 key 0x32 up\n500 key 0x28 down\n600 key 0x28 up\n9000 key 0x27 down\n9100 key 0x27 up\n10000 quit\n'
    for name,options in [('reload',()),('warm',('--no-post','--cs1-in',work/'save-cs1.bin'))]:
        events=run(work,name,script,work/'save-card.img',options)
        assert (work/f'{name}-locks.bin').read_bytes()==locks
        actual=[e[2] for e in events if e[:2]==('on',1)]
        assert actual==expected,(name,actual)
    print('[ok] disk reload and simulated power cycle reproduce the recorded chord changes',flush=True)
    return work,dict(recorded_steps=steps,recorded_replay=expected,root_mode=root_mode)


def edit_and_resume(work):
    # The saved project is already on MIDI. REC alone selects the grid layout.
    setup='100 key 0x32 down\n150 key 0x32 up\n500 key 0x22 down\n550 key 0x22 up\n700 key 0x29 down\n800 key 0x29 up\n'
    edit='1200 key 2 down\n1800 enc 3 1\n2200 key 2 up\n'
    run(work,'edit',setup+edit+'2700 quit\n',work/'save-card.img')
    q=(work/'edit-locks.bin').read_bytes()
    assert q[2]==1,q[:64]
    original=(work/'save-locks.bin').read_bytes()
    assert q[:2]+q[3:]==original[:2]+original[3:]
    bank=(work/'edit-bank.bin').read_bytes()
    assert bank[0x4903+2*32:0x4906+2*32]==b'\xff'*3
    # The working file still has the earlier locks: this verifies UNSAVED CS1 retention.
    run(work,'edit-warm','2000 quit\n',work/'save-card.img',('--no-post','--cs1-in',work/'edit-cs1.bin'))
    assert (work/'edit-warm-locks.bin').read_bytes()==q
    clear='2600 key 2 down\n3000 key 0x3b down\n3100 key 0x3b up\n3400 key 2 up\n4000 quit\n'
    run(work,'clear',setup+edit+clear,work/'save-card.img')
    assert (work/'clear-locks.bin').read_bytes()==original
    print('[ok] held step + D edits dedicated lock; D push clears it; unsaved lock survives simulated resume',flush=True)
    copy='''1200 key 11 down
1700 key 0x29 down
1800 key 0x29 up
2100 key 11 up
2500 key 4 down
3000 key 0x27 down
3100 key 0x27 up
3400 key 4 up
4000 quit
'''
    run(work,'copy-step',setup+copy,work/'save-card.img')
    q=(work/'copy-step-locks.bin').read_bytes()
    assert q[4]==q[11]==1,q[:64]
    bank=(work/'copy-step-bank.bin').read_bytes()
    assert bank[0x4900+4*32]==48
    print('[ok] actual held-step copy/paste carries NOTE and CHRD together',flush=True)
    return dict(edit_clear_unsaved_resume=True,step_copy=True)


def invalid_files(work):
    files=p.emu_card.extract_image((work/'save-card.img').read_bytes())
    original=files['OCTABAM/BASS/chrd01.work']
    for name,status,change in [
        ('missing',0,lambda b:None),
        ('truncated',2,lambda b:b[:-1]),
        ('checksum',2,lambda b:b[:50]+bytes((b[50]^1,))+b[51:]),
        ('mismatch',3,lambda b:b[:20]+bytes((b[20]^1,))+b[21:]),
        ('oversize',2,lambda b:b+b'\0'),
    ]:
        case=work/name;project=case/'project';project.mkdir(parents=True,exist_ok=True)
        for path,data in files.items():
            if path.startswith('OCTABAM/BASS/') and '/' not in path[len('OCTABAM/BASS/'):]:
                (project/Path(path).name).write_bytes(data)
        payload=change(original)
        if payload is None:(project/'chrd01.work').unlink()
        else:(project/'chrd01.work').write_bytes(payload)
        card,_=p.emu_card.stage_project(project,'OCTABAM','BASS',tree=case/'tree')
        (case/'card.img').write_bytes(card)
        run(case,'load','1800 quit\n')
        assert (case/'load-locks.bin').read_bytes()==b'\xff'*131072,name
        assert (case/'load-status.bin').read_bytes()[0]==status,name
        if payload is not None:
            out=p.emu_card.extract_image((case/'load-card.img').read_bytes())
            assert out['OCTABAM/BASS/chrd01.work']==payload
    print('[ok] absent, truncated, checksum, mismatched and oversized companions; no partial publication',flush=True)
    return dict(invalid_companion_cases=5)


def playing_layout(source):
    p.OUT=OUT
    work=p.fixture(source,'playing-layout',{0:2},key_raw=2)
    run(work,'groups',PANEL+'1800 quit\n')
    leds=(work/'groups-leds.bin').read_bytes()
    assert leds==bytes.fromhex('5555aaaa'),leds.hex()
    script=PANEL+"""1600 key 0 down
2000 enc 3 1
2400 key 12 down
2700 key 9 down
3000 key 9 up
3300 key 12 up
3600 key 0 up
3900 key 4 down
4200 enc 3 6
4600 key 4 up
5000 quit
"""
    events=run(work,'base-overrides',script)
    expected=[48,51,55, 48,51,55,58, 48,53,55, 48,51,55,58,
              55,58,62,65, 55,58,62,68, 55,56,62, 55,60,62,
              55,59,62, 55,58,62, 55,59,62,65]
    assert [e[2] for e in events if e[:2]==('on',1)]==expected,events
    run(work,'held-groups',PANEL+'1600 key 0 down\n1700 key 9 down\n1800 key 0 up\n1900 key 9 up\n2000 quit\n')
    # Native cleanup must release captured notes when leaving the playing layout.
    for name,end in [
        ('leave-grid','2000 key 0x29 down\n2100 key 0x29 up\n'),
        ('leave-mode','2000 key 0x2d down\n2100 key 0x20 down\n2150 key 0x20 up\n2300 key 0x20 down\n2350 key 0x20 up\n2500 key 0x2d up\n'),
    ]:
        run(work,name,PANEL+'1600 key 0 down\n1700 key 9 down\n'+end+'3000 key 0 up\n3100 key 9 up\n3500 quit\n')
    script=work/'cm7.txt'
    script.write_text(PANEL+'1600 key 0 down\n1700 key 9 down\n2300 quit\n')
    events=p.run(work,'cm7',['--rtc','1800000000','--live-script',script,
        '--lcd',work/'cm7.lcd','--mem-dump',dump(work,'cm7')])
    # This capture intentionally stops with two physical keys held. The
    # release cases above verify the corresponding note-off behavior.
    assert [e[2] for e in events if e[:2]==('on',1)]==[48,51,55,48,51,55,58]
    assert (work/'cm7-leds.bin').read_bytes()==bytes.fromhex('5755aeaa')
    p.subprocess.run([p.sys.executable,str(p.ROOT/'tools/emu/lcd_view.py'),str(work/'cm7.lcd'),'--png',str(work/'cm7.png')],check=True)
    print('[ok] distinct LED groups, D live base, newest-held overrides, explicit DOM7 and mode/grid release cleanup',flush=True)
    return dict(playing_layout=True,led_groups=leds.hex())



def key(t,k):
    return f'{t} key {k} down\n{t+80} key {k} up\n'


def combo(t,k,modifier=0x2d):
    return f'{t} key {modifier} down\n'+key(t+100,k)+f'{t+250} key {modifier} up\n'


def edit_lifecycle(work):
    original=(work/'save-locks.bin').read_bytes()
    base=key(100,0x31)+key(500,0x22)
    cases={
        'copy-track':(key(800,0x29)+combo(1200,0x29)+key(1700,0x11)+combo(2100,0x27),64,original[:64]),
        'clear-track':(key(800,0x29)+combo(1200,0x28),0,b'\xff'*64),
        'undo-track':(key(800,0x29)+combo(1200,0x28)+combo(2000,0x28),0,original[:64]),
        'copy-pattern':(combo(1200,0x29)+combo(1800,1,0x2e)+combo(2300,0x27),512,original[:512]),
        'clear-pattern':(combo(1200,0x28),0,b'\xff'*512),
        'undo-pattern':(combo(1200,0x28)+combo(2000,0x28),0,original[:512]),
        'copy-bank':(combo(1200,0x29)+combo(1800,9,0x2f)+key(2800,0)+combo(3800,0x27),9*8192,original[:512]),
    }
    for name,(actions,start,wanted) in cases.items():
        run(work,name,base+actions+'6000 quit\n',work/'save-card.img')
        q=(work/f'{name}-locks.bin').read_bytes()
        expected=bytearray(original);expected[start:start+len(wanted)]=wanted
        assert q==expected,name
    print('[ok] native track/pattern copy, clear, undo and paste across banks preserve dedicated locks',flush=True)
    return dict(edit_lifecycle_cases=len(cases))


def same_step(work):
    script=PANEL+"""1600 key 0x29 down
1700 key 0x28 down
1800 key 0x28 up
1900 key 0x29 up
2600 key 0 down
2610 key 9 down
2620 key 12 down
3300 key 0 up
3400 key 9 up
3500 key 12 up
3800 key 0x29 down
3900 key 0x29 up
4500 key 0x27 down
4600 key 0x27 up
5500 quit
"""
    events=run(work,'same-step',script)
    assert [e[2] for e in events if e[:2]==('on',1)]==[48,51,55,48,51,55,58,48,53,55],events
    bank=(work/'same-step-bank.bin').read_bytes();q=(work/'same-step-locks.bin').read_bytes()
    notes=[(k,bank[0x4900+k*32],q[k]) for k in range(64) if bank[0x4900+k*32]<128]
    assert notes==[(7,48,4)],notes
    print('[ok] three performed chord changes in one quantized step leave the final NOTE+CHRD',flush=True)
    return dict(same_step_last_change=True)


def delete_replace_trig(work):
    setup=key(100,0x31)+key(500,0x22)+key(700,0x29)
    original=(work/'save-locks.bin').read_bytes()
    expected=bytearray(original);expected[11]=255
    for name,actions in [('delete-trig',key(1200,11)),
                         ('replace-trig',key(1200,11)+key(1800,11))]:
        run(work,name,setup+actions+'2500 quit\n',work/'save-card.img')
        assert (work/f'{name}-locks.bin').read_bytes()==expected,name
        bank=(work/f'{name}-bank.bin').read_bytes()
        bitmap=int.from_bytes(bank[0x48d0:0x48d8],'big')
        assert bool(bitmap & (1<<11))==(name=='replace-trig'),name
    print('[ok] native trig deletion and replacement clear CHRD without changing unrelated locks',flush=True)
    return dict(delete_replace_trig=True)


def explicit_arp(source):
    p.OUT=OUT
    work=p.fixture(source,'explicit-arp',{0:2},key_raw=2,arp=True)
    script=PANEL+'1700 key 15 down\n1800 key 4 down\n5300 key 4 up\n5400 key 15 up\n6200 quit\n'
    events=run(work,'held-dom7',script)
    pitches=[e[2] for e in events if e[:2]==('on',1)]
    assert set(pitches)=={55,59,62,65},pitches
    print('[ok] live DOM7 through native arp retains intentional B natural in C minor',flush=True)
    return dict(explicit_arp=True)


def unlocked_isolation(work):
    files=p.emu_card.extract_image((work/'save-card.img').read_bytes())
    case=work/'unlocked';project=case/'project';project.mkdir(parents=True,exist_ok=True)
    for path,data in files.items():
        if path.startswith('OCTABAM/BASS/') and '/' not in path[len('OCTABAM/BASS/'):]:
            (project/Path(path).name).write_bytes(data)
    data=bytearray((project/'chrd01.work').read_bytes());data[32+19]=255
    checksum=0x811c9dc5
    for byte in data[32:]:checksum=((checksum^byte)*0x01000193)&0xffffffff
    data[16:20]=struct.pack('>I',checksum);(project/'chrd01.work').write_bytes(data)
    card,_=p.emu_card.stage_project(project,'OCTABAM','BASS',tree=case/'tree')
    (case/'card.img').write_bytes(card)
    script=key(100,0x31)+key(500,0x22)+'800 enc 3 7\n'+key(1200,0x28)+key(10000,0x27)+'11000 quit\n'
    events=run(case,'play',script)
    assert [e[2] for e in events if e[:2]==('on',1)]==EXPECTED,events
    assert (case/'play-locks.bin').read_bytes()[19]==255
    print('[ok] unlocked step resolves to TRI after SUS4 despite DOM7 selected for live playing',flush=True)
    return dict(unlocked_sequence_isolation=True)


def rejected_resume_save(work):
    case=work/'mismatch'
    original=p.emu_card.extract_image((case/'card.img').read_bytes())
    run(case,'refuse-warm-save',key(100,0x31)+SAVE,case/'load-card.img',('--no-post','--cs1-in',case/'load-cs1.bin'))
    assert (case/'refuse-warm-save-status.bin').read_bytes()[0]==3
    saved=p.emu_card.extract_image((case/'refuse-warm-save-card.img').read_bytes())
    for name in ('chrd01.work','chrd01.strd','bank01.work','bank01.strd'):
        path='OCTABAM/BASS/'+name
        assert saved[path]==original[path],name
    print('[ok] mismatch diagnostic survives resume; SAVE preserves rejected companion and native bank',flush=True)
    return dict(rejected_resume_save=True)


def project_menu(index):
    return key(100,0x31)+key(500,0x1c)+key(900,0x21)+''.join(key(1200+i*250,0x20) for i in range(index))+key(4500,0x31)


def project_lifecycle(work):
    original=(work/'save-locks.bin').read_bytes()
    for name,index in [('project-reload',2),('bank-reload',10)]:
        run(work,name,project_menu(index)+key(6500,0x31)+'30000 quit\n',work/'save-card.img',('--no-post','--cs1-in',work/'edit-cs1.bin'))
        assert (work/f'{name}-locks.bin').read_bytes()==original,name
    run(work,'save-as',project_menu(4)+'6000 enc 6 -1\n'+key(6500,0x31)+'45000 quit\n',work/'save-card.img')
    files=p.emu_card.extract_image((work/'save-as-card.img').read_bytes())
    project=work/'save-as-project';project.mkdir(parents=True,exist_ok=True)
    for bank in range(16):
        prefix='OCTABAM/BASS~/'
        name=f'chrd{bank+1:02d}.work'
        assert files[prefix+name][32:]==original[bank*8192:(bank+1)*8192],name
        assert prefix+f'bank{bank+1:02d}.work' in files
        # Save To New follows native work/strd policy, including no stored bank yet.
        assert (prefix+f'bank{bank+1:02d}.strd' in files)==(prefix+f'chrd{bank+1:02d}.strd' in files)
    for path,data in files.items():
        if path.startswith('OCTABAM/BASS~/') and '/' not in path[len('OCTABAM/BASS~/'):]:
            (project/Path(path).name).write_bytes(data)
    card,_=p.emu_card.stage_project(project,'OCTABAM','BASS',tree=work/'save-as-tree')
    (work/'save-as-load.img').write_bytes(card)
    run(work,'save-as-load','1800 quit\n',work/'save-as-load.img')
    assert (work/'save-as-load-locks.bin').read_bytes()==original
    print('[ok] project and current-bank RELOAD discard unsaved edits; Save To New retains all locks on fresh load',flush=True)
    return dict(project_reload=True,bank_reload=True,save_as=True)


def new_project(work):
    script=key(100,0x31)+key(500,0x1c)+key(900,0x21)+key(3000,0x31)+key(4000,0x33)+key(4500,0x31)+'6000 enc 6 -1\n'+key(6500,0x31)+key(8500,0x31)+'45000 quit\n'
    run(work,'project-new',script,work/'save-card.img')
    assert (work/'project-new-locks.bin').read_bytes()==b'\xff'*131072
    files=p.emu_card.extract_image((work/'project-new-card.img').read_bytes())
    new_names={path.split('/')[1] for path in files if path.startswith('OCTABAM/') and path.endswith('/project.work')}-{'BASS'}
    assert len(new_names)==1,new_names
    print('[ok] CREATE NEW PROJECT resets every CHRD bank without inheriting old locks',flush=True)
    return dict(new_project=True)


def octave_layout(source):
    p.OUT=OUT
    work=p.fixture(source,'octave-layout',{0:2},key_raw=2)
    script=PANEL+key(1600,0)+combo(2100,0x21)+key(2700,0)+combo(3200,0x34)+key(3800,0)+'4400 quit\n'
    events=run(work,'octaves',script)
    assert [e[2] for e in events if e[:2]==('on',1)]==[48,51,55,60,63,67,48,51,55],events
    print('[ok] CHORD PLAY FUNC+RIGHT/LEFT changes octave and returns; captured notes release correctly',flush=True)
    return dict(chord_play_octaves=True)


def root_chord_play(source):
    p.OUT=OUT
    qualities=((48,51,55),(48,51,55,58),(48,51,55,62),(48,50,55),
               (48,53,55),(48,52,55),(48,51,55),(48,52,55,58))
    for mode in (2,3):
        drop=12*(mode-1)
        work=p.fixture(source,f'root-chord-play-{mode}',{0:2},key_raw=2,roots={0:mode})
        script=PANEL
        for quality in range(8):
            t=1600+quality*700
            script+=f'{t} key {8+quality} down\n{t+100} key 0 down\n{t+400} key 0 up\n{t+500} key {8+quality} up\n'
        events=run(work,'qualities',script+'7500 quit\n')
        expected=[n for chord in qualities for n in (chord[0]-drop,*chord[1:])]
        assert [e[2] for e in events if e[:2]==('on',1)]==expected,(mode,events)
        work=p.fixture(source,f'root-chord-arp-{mode}',{0:2},key_raw=2,roots={0:mode},arp=True)
        script=PANEL+'''1600 key 10 down
1700 key 0 down
4700 key 0 up
4800 key 10 up
5100 key 15 down
5200 key 4 down
8200 key 4 up
8300 key 15 up
9000 quit
'''
        events=run(work,'add9-dom7',script)
        actual={e[2] for e in events if e[:2]==('on',1)}
        assert actual=={48-drop,51,55,62,55-drop,59,65},(mode,actual)
    print('[ok] CHORD PLAY ROOT octave drops across all eight qualities; ADD9/DOM7 through native arp',flush=True)
    return dict(root_chord_play=True)


def native_page_chords(source):
    """Complete chords still sound during a short root press with PAGE held."""
    p.OUT=OUT
    results={}
    for name,arp,opts,want in (
        ('page-direct',False,{},[48,52,55]),
        ('page-size4',False,dict(sizes={0:3},roots={0:2},auto=(0,)),[36,48,52,55]),
        ('page-arp',True,{},None),
    ):
        work=p.fixture(source,name,{0:2},arp=arp,**opts)
        script=PANEL+'1500 key 0x1b down\n1600 key 0 down\n'
        end=2600 if arp else 1610
        script+=f'{end} key 0 up\n{end+100} key 0x1b up\n{end+400} quit\n'
        path=work/'page.txt';path.write_text(script)
        events=p.run(work,'page',['--live-script',path,'--internal-clock','--mem-dump',
            f'{SYMBOLS["mh_refs"]:#x},1024={work}/refs.bin;{SYMBOLS["mh_key_tokens"]:#x},2048={work}/tokens.bin'])
        p.balanced(events)
        notes=[e[2] for e in events if e[:2]==('on',1)]
        if want is None:assert set(notes)=={48,52,55},(name,notes)
        else:assert notes==want,(name,notes)
        assert (work/'refs.bin').read_bytes()==bytes(1024),name
        assert (work/'tokens.bin').read_bytes()==b'\xff'*2048,name
        results[name]=notes
    print('[ok] PAGE held: short presses emit complete 3/4-note chords, native ARP works, all notes release',flush=True)
    return dict(native_page_chords=results)


def main():
    global SYMBOLS
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project',required=True,type=Path)
    ap.add_argument('--native-page-only',action='store_true')
    ap.add_argument('--resume-record',action='store_true',help='reuse this gate\'s prior record/save artifact for focused debugging')
    ap.add_argument('--load-lifecycle-only',action='store_true',help='record/save, fresh load, resume, reload, Save As, invalid companions and new project')
    args=ap.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    p.freeze_candidate(OUT);SYMBOLS=p.harmony.symbols()
    if args.native_page_only:
        results=native_page_chords(args.project)
        results.update(image_sha256=hashlib.sha256(p.CANDIDATE_IMAGE.read_bytes()).hexdigest(),hardware_tested=False)
        (OUT/'native-page-receipt.json').write_text(json.dumps(results,indent=2)+'\n')
        return
    if 'hd_banks' in SYMBOLS:
        raise SystemExit('Current degree storage: use verify_harmony_degree_port.py --case record-save --case panel --case lifecycle; the CHD companion tests below are historical.')
    if args.resume_record:work=OUT/'record-save';results={}
    else:work,results=record_save(args.project)
    if args.load_lifecycle_only:
        for check in (edit_and_resume,project_lifecycle,invalid_files,new_project):
            results.update(check(work))
    else:
        results.update(playing_layout(args.project))
        results.update(octave_layout(args.project))
        results.update(edit_and_resume(work))
        results.update(edit_lifecycle(work))
        results.update(delete_replace_trig(work))
        results.update(same_step(work))
        results.update(explicit_arp(args.project))
        results.update(invalid_files(work))
        results.update(unlocked_isolation(work))
        results.update(rejected_resume_save(work))
        results.update(project_lifecycle(work))
        results.update(new_project(work))
        results.update(root_chord_play(args.project))
        results['root_recordings']={}
        for mode in (2,3):
            _,recorded=record_save(args.project,mode)
            results['root_recordings'][mode]=recorded
    results.update(image_sha256=hashlib.sha256(p.CANDIDATE_IMAGE.read_bytes()).hexdigest(),hardware_tested=False)
    (OUT/'receipt.json').write_text(json.dumps(results,indent=2)+'\n')

if __name__=='__main__':main()
