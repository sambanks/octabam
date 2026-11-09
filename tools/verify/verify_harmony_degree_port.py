#!/usr/bin/env python3
"""Degree-root acceptance through the full firmware and disposable virtual CF."""
import argparse
import hashlib
import json
from verify_harmony_degree_packed import oracle
import shutil
import subprocess
from pathlib import Path
import verify_midi_harmony_port as p
import verify_chord_play_port as cp

OUT=p.ROOT/'out/harmony-degrees-port'
BANK=0x400e21e0
PART=BANK+0x8ed80
SIZE=16768
LANE=131
SYMBOLS={}


def degree_positions(data):
    """Validate every record, then compare musical identity across reloads.

    Physical slot provenance is deliberately detached by a load. It is not
    expected to be byte-identical to the previously attached runtime record.
    """
    assert len(data)%SIZE==0
    result=bytearray()
    for offset in range(0,len(data),LANE):
        record=data[offset:offset+LANE]
        degree,note=record[:64],record[64:128]
        state,scale,context=record[128:]
        assert state<=2 and scale<84 and (context<64 or context==255)
        assert all(v<84 or v==255 for v in degree)
        assert all(v<128 or v==255 for v in note)
        if state==0:assert context==255 and degree==note==b'\xff'*64
        elif state==1:assert degree==b'\xff'*64
        else:assert all((d==255)==(n==255) for d,n in zip(degree,note))
        result+=degree
    return bytes(result)


def dump(work,name):
    return (f'{SYMBOLS["hd_banks"]:#x},{SIZE*16}={work}/{name}-degrees.bin;'
            f'{SYMBOLS["mhc_lock_table"]:#x},131072={work}/{name}-locks.bin;'
            f'{BANK:#x},0x9b340={work}/{name}-bank.bin;'
            f'{SYMBOLS["mhc_lock_status"]:#x},16={work}/{name}-status.bin;'
            f'{SYMBOLS["mhc_record_overflow"]:#x},4={work}/{name}-overflow.bin;'
            f'0x10000000,0x100000={work}/{name}-cs1.bin;'
            f'0x460ba98c,4={work}/{name}-leds.bin')


def run(work,name,script,card=None,extra=()):
    path=work/f'{name}.txt';path.write_text(script)
    events=p.run(work,name,['--rtc','1800000000','--live-script',path,'--internal-clock',
        '--lcd',work/f'{name}.lcd','--mem-dump',dump(work,name),*extra],card=card)
    p.balanced(events)
    assert (work/f'{name}-overflow.bin').read_bytes()==bytes(4),name
    return events


def sequence(source):
    work=p.fixture(source,'degree-sequence',{0:2},key_raw=2,first_note=48)
    results={}
    for name,key,want in [('c-minor',2,[48,51,55,65,68,72,67,70,74]),
                          ('d-minor',6,[50,53,57,67,70,74,69,72,76])]:
        events=p.run(work,name,['--sequencer','--internal-clock','--frames','7000',
            '--step',f'-:poke:{PART+0x4e2+17:#x}={key};0x46c76df1={key}',
            '--mem-dump',dump(work,name)])
        p.balanced(events)
        actual=[e[2] for e in events if e[:2]==('on',1)]
        assert actual==want,(name,actual,want)
        results[name]=actual
    assert degree_positions((work/'c-minor-degrees.bin').read_bytes())==degree_positions((work/'d-minor-degrees.bin').read_bytes())
    off=p.fixture(source,'stock-off',{})
    args=['--sequencer','--internal-clock','--frames','7000']
    native=p.run(off,'native',args,image=p.ROOT/'out/raw/section_3_MAIN_OS.bin')
    candidate=p.run(off,'candidate',args)
    assert candidate==native
    p.balanced(candidate)
    print('[ok] C minor -> D minor preserves stored degrees; OFF output equals stock',flush=True)
    return results


def record_save(source):
    work=p.fixture(source,'degree-record-save',{0:2},key_raw=2)
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
    events=run(work,'save',cp.panel()+cp.RECORD+cp.SAVE)
    actual=[e[2] for e in events if e[:2]==('on',1)]
    assert actual==cp.EXPECTED*2,(actual,cp.EXPECTED*2)
    bank=(work/'save-bank.bin').read_bytes()
    degrees=(work/'save-degrees.bin').read_bytes()
    locks=(work/'save-locks.bin').read_bytes()
    steps=[(i,bank[0x4900+i*32],degrees[i],locks[i]) for i in range(64) if bank[0x4900+i*32]<128]
    assert steps==[(7,48,35,0),(11,48,35,1),(15,48,35,4),(23,53,38,0)],steps
    for step,*_ in steps:assert bank[0x4903+step*32:0x4906+step*32]==b'\xff'*3
    files=p.emu_card.extract_image((work/'save-card.img').read_bytes())
    for suffix in ('work','strd'):
        data=files[f'OCTABAM/BASS/hdeg01.{suffix}']
        version=4 if 'hd_track_read_c' in SYMBOLS else 3
        assert len(data)==(15136 if version==4 else 10400)
        assert data[:8]==f'HDP{version}'.encode()+version.to_bytes(4,'big')
        assert data[32:10400]==oracle(degrees[:SIZE], locks[:8192])
        if version==4:assert data[10400:]==(bytes(32)+bytes((0,7,0,3,1)))*128
    for bank in range(2,17):assert files[f'OCTABAM/BASS/hdeg{bank:02d}.strd']==b'HDP0'+bytes(28)
    print('[ok] real REC+PLAY captures degree and quality; project SAVE stores the complete companion',flush=True)
    script='100 key 0x32 down\n200 key 0x32 up\n500 key 0x28 down\n600 key 0x28 up\n9000 key 0x27 down\n9100 key 0x27 up\n10000 quit\n'
    for name,options in [('reload',()),('warm',('--no-post','--cs1-in',work/'save-cs1.bin'))]:
        events=run(work,name,script,work/'save-card.img',options)
        assert degree_positions((work/f'{name}-degrees.bin').read_bytes())==degree_positions(degrees),name
        assert (work/f'{name}-locks.bin').read_bytes()==locks,name
        actual=[e[2] for e in events if e[:2]==('on',1)]
        assert actual==cp.EXPECTED,(name,actual)
    print('[ok] cold project load and retained-current-bank resume reproduce degrees and playback',flush=True)
    return work,{'steps':steps,'replay':cp.EXPECTED}


def panel(work):
    setup='100 key 0x32 down\n150 key 0x32 up\n500 key 0x22 down\n550 key 0x22 up\n700 key 0x29 down\n800 key 0x29 up\n'
    # Existing explicit root: one encoder detent advances one scale degree.
    edit='1200 key 7 down\n1800 enc 0 1\n2200 key 7 up\n'
    run(work,'degree-edit',setup+edit+'2700 quit\n',work/'save-card.img')
    before=(work/'save-degrees.bin').read_bytes()
    after=(work/'degree-edit-degrees.bin').read_bytes()
    assert after[7]==36 and before[7]==35,(before[:64],after[:64])
    bank=(work/'degree-edit-bank.bin').read_bytes()
    assert bank[0x4900+7*32]==50
    run(work,'degree-edit-warm','2000 quit\n',work/'save-card.img',('--no-post','--cs1-in',work/'degree-edit-cs1.bin'))
    assert degree_positions((work/'degree-edit-warm-degrees.bin').read_bytes())==degree_positions(after)
    octave='1200 key 7 down\n1500 key 0x2d down\n1800 enc 0 1\n2000 key 0x2d up\n2200 key 7 up\n2700 quit\n'
    run(work,'degree-octave',setup+octave,work/'save-card.img')
    assert (work/'degree-octave-degrees.bin').read_bytes()[7]==42
    live_octave=cp.key(100,0x32)+cp.key(500,0x22)+'1100 key 0x2d down\n1400 enc 0 1\n1600 key 0x2d up\n2200 quit\n'
    run(work,'default-octave',live_octave,work/'save-card.img')
    base=(work/'save-bank.bin').read_bytes()[0x8ed80+0x4e2+19]
    assert (work/'default-octave-bank.bin').read_bytes()[0x8ed80+0x4e2+19]==base+7
    clear='2600 key 7 down\n3000 key 0x38 down\n3100 key 0x38 up\n3400 key 7 up\n4000 quit\n'
    run(work,'degree-unlock',setup+edit+clear,work/'save-card.img')
    assert (work/'degree-unlock-degrees.bin').read_bytes()[7]==255
    assert (work/'degree-unlock-bank.bin').read_bytes()[0x4900+7*32]==255
    copy='1200 key 23 down\n1700 key 0x29 down\n1800 key 0x29 up\n2100 key 23 up\n2500 key 4 down\n3000 key 0x27 down\n3100 key 0x27 up\n3400 key 4 up\n4000 quit\n'
    # Use first-page step 11 for a physical trig key, with a deliberately
    # changed degree so a same-native-NOTE clipboard bug cannot pass.
    copy=copy.replace('key 23','key 11')
    run(work,'degree-copy',setup+copy,work/'save-card.img')
    copied=(work/'degree-copy-degrees.bin').read_bytes()
    assert copied[4]==copied[11]==35
    live=cp.key(100,0x32)+cp.key(500,0x22)+'800 enc 0 1\n1200 enc 3 1\n1500 enc 4 1\n1800 enc 5 1\n2300 quit\n'
    # Edit while the native page-change notification is still visible.
    # This must reach the degree editor, never the stock semitone editor.
    for mode,extra in (('chord',()),('note',('--step',f'-:call:{SYMBOLS.get("bf_encoder", SYMBOLS["mh_note_encoder"]):#x},5,0xfffffffc'))):
        name=f'{mode}-default-edit'
        run(work,name,live,work/'save-card.img',extra)
        degree=(work/f'{name}-degrees.bin').read_bytes()
        native=(work/'save-bank.bin').read_bytes();edited=(work/f'{name}-bank.bin').read_bytes()
        assert edited[0x8ed80+0x4e2+19]==native[0x8ed80+0x4e2+19]+1,mode
        assert degree_positions(degree)==degree_positions(before)
        assert native[0x8ed80+0x3e2:0x8ed80+0x3e8]==edited[0x8ed80+0x3e2:0x8ed80+0x3e8],mode
    for name in ('degree-edit','degree-unlock'):
        subprocess.run([str(p.ROOT/'.venv/bin/python'),str(p.ROOT/'tools/emu/lcd_view.py'),str(work/f'{name}.lcd'),'--png',str(work/f'{name}.png')],check=True,stdout=subprocess.DEVNULL)
    print('[ok] held-step DEG encoder, unlock, copy/paste and unsaved warm resume',flush=True)
    return {'held_edit':True,'unlock':True,'copy':True,'unsaved_resume':True,
            'note_chord_default_edit_under_notification':True,'hidden_controls_preserve_NOT2_4':True}


def lifecycle(work):
    # Reuse the real panel gestures already established by CHORD PLAY, then
    # check the degree representation as well as its quality representation.
    cp.run=run
    cp.edit_lifecycle(work)
    original=degree_positions((work/'save-degrees.bin').read_bytes())
    for name,start,want in [('clear-track',0,b'\xff'*64),('undo-track',0,original[:64]),
                            ('copy-pattern',512,original[:512]),('clear-pattern',0,b'\xff'*512),
                            ('undo-pattern',0,original[:512]),('copy-bank',9*8192,original[:512])]:
        actual=degree_positions((work/f'{name}-degrees.bin').read_bytes())
        assert actual[start:start+len(want)]==want,name
    # Track 2 is OFF: a paste resolves the copied degrees to absolute notes.
    bank=(work/'copy-track-bank.bin').read_bytes()
    for step,note in ((7,48),(11,48),(15,48),(23,53)):
        assert bank[0x4900+0x8b0+step*32]==note
    cp.delete_replace_trig(work)
    for name in ('delete-trig','replace-trig'):
        assert (work/f'{name}-degrees.bin').read_bytes()[11]==255,name
    print('[ok] degree pattern/track/bank copy, native clear/undo, delete and replace',flush=True)
    return {'copy_clear_undo_cases':7,'delete_replace_cases':2}


def parts(work):
    def call(address,*args):return ['--step','-:call:'+','.join(hex(n) for n in (address,*args))]
    edit=SYMBOLS['hd_edit_base_c']
    prefix=call(edit,0,0,0,39)+call(0x4004a908,0)
    run(work,'part-save-reload','1800 quit\n',work/'save-card.img',
        prefix+call(edit,0,0,0,40)+call(0x4004aab4,0))
    b=(work/'part-save-reload-bank.bin').read_bytes()
    assert b[0x8ed80+0x4e2+19]==b[0x9504a+0x4e2+19]==39
    # These are the actual native Part functions, called on the firmware's
    # main task, with their real CS1 copies and engine refreshes intact.
    run(work,'part-clear','1800 quit\n',work/'save-card.img',prefix+call(0x4004a9d0,0))
    d=(work/'part-clear-degrees.bin').read_bytes();b=(work/'part-clear-bank.bin').read_bytes()
    note=b[0x8ed80+0x3e2]
    assert note==48 and b[0x8ed80+0x4e2+19]==b[0x9504a+0x4e2+19]==35
    print('[ok] native Part Save, Reload and Clear preserve/reset degree defaults and retained copies',flush=True)
    return {'save_reload':True,'clear':True}


def projects(work):
    original=(work/'save-degrees.bin').read_bytes()
    quality=(work/'save-locks.bin').read_bytes()
    # The full STORE/KITS/Scenes selection can still show LOADING PROJECT
    # at 30 simulated seconds. Inspect the completed reload, not its cleared
    # intermediate state; the assertions below require the complete payload.
    for name,index in [('project-reload',2),('bank-reload',10)]:
        run(work,name,cp.project_menu(index)+cp.key(6500,0x31)+'90000 quit\n',
            work/'save-card.img',('--no-post','--cs1-in',work/'degree-edit-cs1.bin'))
        assert degree_positions((work/f'{name}-degrees.bin').read_bytes())==degree_positions(original),name
        assert (work/f'{name}-locks.bin').read_bytes()==quality,name
    run(work,'save-as',cp.project_menu(4)+'6000 enc 6 -1\n'+cp.key(6500,0x31)+'45000 quit\n',work/'save-card.img')
    files=p.emu_card.extract_image((work/'save-as-card.img').read_bytes())
    prefix='OCTABAM/BASS~/'
    project=work/'save-as-project';project.mkdir(exist_ok=True)
    for bank in range(16):
        data=files[prefix+f'hdeg{bank+1:02d}.work']
        assert data[32:]==oracle(original[bank*SIZE:(bank+1)*SIZE], quality[bank*8192:(bank+1)*8192])
        assert (prefix+f'bank{bank+1:02d}.strd' in files)==(prefix+f'hdeg{bank+1:02d}.strd' in files)
    for path,data in files.items():
        if path.startswith(prefix) and '/' not in path[len(prefix):]:
            (project/Path(path).name).write_bytes(data)
    card,_=p.emu_card.stage_project(project,'OCTABAM','BASS',tree=work/'save-as-tree')
    (work/'save-as-load.img').write_bytes(card)
    run(work,'save-as-load','1800 quit\n',work/'save-as-load.img')
    assert degree_positions((work/'save-as-load-degrees.bin').read_bytes())==degree_positions(original)
    assert (work/'save-as-load-locks.bin').read_bytes()==quality
    cp.run=run;cp.new_project(work)
    data=(work/'project-new-degrees.bin').read_bytes()
    for bank in range(16):
        block=data[bank*SIZE:(bank+1)*SIZE]
        # The UI may observe the fresh current lane during native project
        # initialization. UNKNOWN and observed STOCK are both empty; neither
        # may retain a degree, note snapshot, scale or old Part association.
        for offset in range(0,SIZE,LANE):
            record=block[offset:offset+LANE]
            assert record[:128]==b'\xff'*128
            assert record[128] in (0,1) and record[129:]==b'\0\xff'
        assert degree_positions(block)==b'\xff'*8192
    native=(work/'project-new-bank.bin').read_bytes()
    for part in range(8):
        base=0x8ed80+part*0x18b2 if part<4 else 0x9504a+(part-4)*0x18b2
        for track in range(8):
            setup=base+0x4e2+track*36
            assert (native[setup+5],native[setup+18],native[setup+19])==(0,0,35)
    print('[ok] project/bank Reload, Save To New, fresh load and New Project degree lifecycle',flush=True)
    return {'project_reload':True,'bank_reload':True,'save_as':True,'new_project':True}


def corrupt_files(work):
    files=p.emu_card.extract_image((work/'save-card.img').read_bytes())
    original=files['OCTABAM/BASS/hdeg01.work']
    for name,status,at in [('checksum',2,100),('mismatch',3,20)]:
        case=work/('degree-'+name);project=case/'project';project.mkdir(parents=True,exist_ok=True)
        for path,data in files.items():
            if path.startswith('OCTABAM/BASS/') and '/' not in path[len('OCTABAM/BASS/'):]:
                (project/Path(path).name).write_bytes(data)
        corrupt=original[:at]+bytes((original[at]^1,))+original[at+1:]
        (project/'hdeg01.work').write_bytes(corrupt)
        card,_=p.emu_card.stage_project(project,'OCTABAM','BASS',tree=case/'tree')
        (case/'card.img').write_bytes(card)
        run(case,'load','1800 quit\n')
        assert (case/'load-status.bin').read_bytes()[0]==status
        assert (case/'load-locks.bin').read_bytes()==b'\xff'*131072
        if name=='mismatch':
            run(case,'refuse-warm-save',cp.key(100,0x32)+cp.SAVE,case/'load-card.img',
                ('--no-post','--cs1-in',case/'load-cs1.bin'))
            saved=p.emu_card.extract_image((case/'refuse-warm-save-card.img').read_bytes())
            for file in ('hdeg01.work','hdeg01.strd','bank01.work','bank01.strd'):
                assert saved['OCTABAM/BASS/'+file]==(corrupt if file=='hdeg01.work' else files['OCTABAM/BASS/'+file]),file
    print('[ok] corrupt/mismatched disk companions rejected; warm SAVE preserves stored bank and companion',flush=True)
    return {'corrupt_rejected':2,'warm_save_preserves_backup':True}


def playback(source):
    result={'follow_sequence':p.sequence(source),'note_transpose':p.note_rules(source),
            'held_arp_cleanup':p.live_transpose_cleanup(source)}
    print('[ok] Follow in both track orders, sequence arp, NOTE/TRAN and held live arp cleanup',flush=True)
    return result


def boundaries(source):
    work=p.fixture(source,'mode-boundary',{0:2},key_raw=2,first_note=48)
    encoder=SYMBOLS.get('bf_encoder', SYMBOLS['mh_note_encoder'])
    extra=['--sequencer','--internal-clock','--frames','7000',
           '--step',f'-:poke:{PART+0x4e2+17:#x}=6;0x46c76df1=6',
           '--step',f'-:call:{encoder:#x},5,0xfffffffc',
           '--step',f'-:call:{encoder:#x},5,0xfffffffc',
           '--step',f'-:dump:{BANK:#x},0x9b340={work}/off-bank.bin',
           '--step',f'-:poke:{PART+0x4e2+17:#x}=1;0x46c76df1=1',
           '--step',f'-:call:{encoder:#x},5,4',
           '--step',f'-:call:{encoder:#x},5,4',
           '--mem-dump',dump(work,'back')]
    events=p.run(work,'back',extra);p.balanced(events)
    notes=[e[2] for e in events if e[:2]==('on',1)]
    assert notes==[50,53,57,67,71,74,69,72,76],notes
    assert (work/'off-bank.bin').read_bytes()[0x4900+2*32]==50
    assert (work/'back-degrees.bin').read_bytes()[2]==36
    # While a sequenced arp runs, use the actual HARM encoder callback on
    # the main task. Native note-off ownership must survive both boundaries.
    arp=p.fixture(source,'arp-mode-boundary',{0:2},key_raw=2,first_note=48,arp=True,tran={0:7})
    events=p.run(arp,'switch',['--sequencer','--internal-clock','--frames','7000',
        '--step',f'1700:call:{encoder:#x},5,0xfffffffc',
        '--step',f'1700:call:{encoder:#x},5,0xfffffffc',
        '--step',f'3300:poke:{PART+0x4e2+17:#x}=6;0x46c76df1=6',
        '--step',f'4200:call:{encoder:#x},5,4',
        '--step',f'4200:call:{encoder:#x},5,4'])
    p.balanced(events)
    assert len([e for e in events if e[:2]==('on',1)])>6
    print('[ok] KEY/HARM/OFF conversion through the real encoder and active sequence arp boundaries',flush=True)
    return {'off_materialized_D3':True,'return_C_major_degree_2':True,'replay':notes,'arp_balanced':True}


def clean_completed_fixtures():
    """Keep evidence and the shared saved project; discard regenerable cards.

    A complete run otherwise retains several GiB of duplicate 64 MiB virtual
    cards. This directory belongs only to this verifier in its own worktree.
    Called between completed cases, never while an emulator is running.
    """
    root=OUT.resolve();saved=root/'degree-record-save'
    retained={saved/'card.img',saved/'save-card.img'}
    removed=[]
    for path in root.rglob('*.img'):
        if path in retained or path.is_symlink():continue
        assert path.resolve().is_relative_to(root)
        removed.append(str(path.relative_to(root)));path.unlink()
    for case in root.iterdir():
        if not case.is_dir() or case.is_symlink():continue
        for path in list(case.iterdir()):
            if path.is_dir() and 'tree' in path.name and not path.is_symlink():
                assert path.resolve().is_relative_to(root)
                removed.append(str(path.relative_to(root)));shutil.rmtree(path)
    with (OUT/'fixture-cleanup.jsonl').open('a') as f:
        f.write(json.dumps({'removed_generated_fixtures':removed})+'\n')


def main():
    global SYMBOLS
    ap=argparse.ArgumentParser();ap.add_argument('--project',type=Path,required=True)
    ap.add_argument('--case',choices=('sequence','record-save','panel','lifecycle','parts','projects','corrupt','playback','boundaries'),action='append')
    ap.add_argument('--frozen',action='store_true',help='reuse the immutable image and symbol receipt')
    ap.add_argument('--keep-fixtures',action='store_true',help='retain disposable virtual cards after successful cases')
    args=ap.parse_args();p.OUT=OUT
    if args.frozen:
        p.CANDIDATE_IMAGE=OUT/'candidate.bin'
        frozen=json.loads((OUT/'candidate-symbols.json').read_text())
        p.harmony.symbols=lambda:frozen
    else:p.freeze_candidate(OUT)
    SYMBOLS=p.harmony.symbols()
    assert 'hd_banks' in SYMBOLS,'build the degree candidate first'
    cases={};selected=args.case or ['sequence','record-save','panel','lifecycle','parts','projects','corrupt','playback','boundaries']
    work=OUT/'degree-record-save'
    for case in selected:
        if case=='sequence':cases[case]=sequence(args.project)
        elif case=='record-save':work,cases[case]=record_save(args.project)
        elif case=='playback':cases[case]=playback(args.project)
        elif case=='boundaries':cases[case]=boundaries(args.project)
        else:cases[case]={'panel':panel,'lifecycle':lifecycle,'parts':parts,
                         'projects':projects,'corrupt':corrupt_files}[case](work)
        receipt={'cases':cases,'image_sha256':hashlib.sha256(p.CANDIDATE_IMAGE.read_bytes()).hexdigest(),'hardware_tested':False}
        (OUT/('receipt-'+ '-'.join(selected)+'.json')).write_text(json.dumps(receipt,indent=2)+'\n')
        if not args.keep_fixtures:clean_completed_fixtures()


if __name__=='__main__':main()
