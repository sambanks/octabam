#!/usr/bin/env python3
"""Sounding-chord display: captured live pitches, sequencer ownership and release."""
import argparse,json,hashlib,struct,subprocess,sys
from pathlib import Path
import verify_chord_play as c
import verify_chord_play_port as panel
from unicorn.m68k_const import *
ROOT=c.ROOT
OUT=ROOT/'out/chord-display'

def machine():
    m=c.h.Machine();u=m.uc;s=m.sym
    m.setting(0,2,0,0)
    u.mem_write(0x46c77a16,b'\xff'*256)
    def text():
        m.call('ch_chord_name',0)
        return bytes(u.mem_read(u.reg_read(UC_M68K_REG_A0),32)).split(b'\0')[0].decode()
    def row(start,end):
        m.call('ch_note_text',start,end)
        return bytes(u.mem_read(u.reg_read(UC_M68K_REG_A0),32)).split(b'\0')[0].decode()
    assert text()==''
    u.mem_write(s['ch_pressed'],struct.pack('>I',60)+b'\xff'*28)
    u.mem_write(s['ch_last_root'],bytes((60,)))
    u.mem_write(s['ch_live'],b'\x01');u.mem_write(s['ch_pressed_quality'],b'\x01')
    u.mem_write(s['mh_held']+60*4,bytes((48,64,79,255)))
    assert text()=='Cmaj7'
    assert row(0,4)=='C3-E4-G5'
    for pitch,label in enumerate(('C','C#','D','D#','E','F','F#','G','G#','A','A#','B'),48):
        m.setting(0,1,0,0)
        # KEY OFF gives an unsnapped root name; shared spelling must still agree.
        m.set_key(0,0)
        u.mem_write(s['ch_pressed'],struct.pack('>I',pitch)+b'\xff'*28)
        u.mem_write(s['ch_last_root'],bytes((pitch,)))
        u.mem_write(s['mh_held']+pitch*4,bytes((pitch,255,255,255)))
        assert text()==label and row(0,4)==label+'3'
    m.setting(0,2,0,0)
    u.mem_write(s['ch_pressed'],struct.pack('>I',60)+b'\xff'*28)
    u.mem_write(s['ch_last_root'],b'\x3c')
    u.mem_write(s['ch_live'],b'\x01');u.mem_write(s['ch_pressed_quality'],b'\x01')
    u.mem_write(s['mh_held']+60*4,bytes((48,64,79,255)))
    # Settings can change while notes sustain: retain the actual captured notes.
    m.call('mh_root_set',0,3);m.call('mh_sprd_set',0,2)
    assert text()=='Cmaj7' and row(0,2)=='C3-E4'
    u.mem_write(s['ch_pressed'],b'\xff'*32)
    assert text()=='' and row(0,2)==''
    u.mem_write(s['ch_sequence_root'],b'\x3e')
    u.mem_write(s['ch_sequence_quality'],b'\x01')
    for i,n in enumerate((62,65,69,72)):
        u.mem_write(0x46c77a16+i*8,struct.pack('>ii',0x90,n))
    assert text()=='Dm7'
    assert row(0,4)=='D4-F4-A4-C5'
    # Native note-off marks note=-1; stale root/quality must not keep the name.
    for i in range(4):u.mem_write(0x46c77a1a+i*8,b'\xff'*4)
    assert text()=='' and row(0,2)==''
    u.mem_write(s['ch_display_notes'],bytes((0,1,126,127)))
    assert row(0,4)=='C-1-C#-1-F#9-G9'
    # Execute native drawing too: wide accidentals and octave -1 remain on one
    # line inside the guide, without changing pixels in adjacent controls.
    plane=0x46c7e0ea
    for line in ('C3-E3-G4', 'C#3-D#3-F#3-A#3',
                 'C#-1-D#-1-F#-1-A#-1', 'C-1-C#-1-F#9-G9'):
        u.mem_write(plane,bytes(1024))
        u.mem_write(m.scratch,line.encode()+b'\0')
        m.call('ch_draw_note_line',a0=m.scratch)
        ink=bytes(u.mem_read(plane,1024))
        lit=[(x,y) for x in range(128) for y in range(64)
             if ink[x*8+y//8] & (0x80>>(y%8))]
        assert lit and all(61<=x<=118 and 25<=y<=30 for x,y in lit),(line,lit)
    for name in ('Cmaj7','Ddim(addb9)','D#dim(addb9)','F#sus#4b5'):
        u.mem_write(plane,bytes(1024))
        u.mem_write(m.scratch,name.encode()+b'\0')
        m.call('ch_draw_chord_name',a0=m.scratch)
        ink=bytes(u.mem_read(plane,1024))
        lit=[(x,y) for x in range(128) for y in range(64)
             if ink[x*8+y//8] & (0x80>>(y%8))]
        assert lit and all(78<=x<=118 and 16<=y<=22 for x,y in lit),(name,lit)
    print('[ok] single-line drawing: all four voices, sharps and negative octaves stay inside the guide',flush=True)
    for size,label in enumerate(('N','2','3','4')):
        m.call('mh_size_set',0,size)
        for voic,v in enumerate(('V:R','V:A','V:1','V:2','V:3')):
            for spread,sp in enumerate(('S:C','S:O','S:W')):
                for root,r in enumerate(('R:K','R:O','R:-1','R:-2')):
                    m.call('mh_voic_set',0,voic);m.call('mh_sprd_set',0,spread);m.call('mh_root_set',0,root)
                    m.call('ch_settings_text',0)
                    actual=bytes(u.mem_read(u.reg_read(UC_M68K_REG_A0),24)).split(b'\0')[0].decode()
                    assert actual==f'N:{label} {v} {sp} {r}',actual
                    u.mem_write(plane,bytes(1024));m.call('ch_draw_settings',0)
                    ink=bytes(u.mem_read(plane,1024))
                    lit=[(x,y) for x in range(128) for y in range(64) if ink[x*8+y//8] & (0x80>>(y%8))]
                    assert lit and all(61<=x<=118 and 9<=y<=14 for x,y in lit),(actual,lit)
    print('[ok] all 240 N/V/S/R summaries fit below the chord name without touching the octave box',flush=True)
    # The UI seam must return the queued event unchanged to native dispatch.
    u.mem_write(0x460d16f0,(6).to_bytes(4,'big'));u.mem_write(0x80000012,(1).to_bytes(4,'big'))
    for setter in ('mh_voic_set','mh_sprd_set','mh_root_set','mh_size_set'):m.call(setter,0,0)
    m.call('ch_display_poll',stop=s['ch_play_guide'])
    m.call('ch_display_poll') # unchanged settings must not redraw
    for setter in ('mh_voic_set','mh_sprd_set','mh_root_set','mh_size_set'):
        m.call(setter,0,1)
        m.call('ch_display_poll',stop=s['ch_play_guide'])
        m.call('ch_display_poll')
    # REC/grid changes key dispatch, not the sounding-chord display. A new
    # sequenced note must still invalidate the guide without touching a key.
    u.mem_write(0x460d1736,(1).to_bytes(4,'big'))
    u.mem_write(s['ch_sequence_root'],b'\x3e')
    u.mem_write(s['ch_sequence_quality'],b'\x01')
    for i,n in enumerate((62,65,69,72)):
        u.mem_write(0x46c77a16+i*8,struct.pack('>ii',0x90,n))
    m.call('ch_display_poll',stop=s['ch_play_guide'])
    m.call('ch_display_poll')
    assert text()=='Dm7'
    u.mem_write(0x460d1736,bytes(4))
    u.mem_write(0x460d16f0,bytes(4))
    print('[ok] settings and grid playback trigger redraws; unchanged values do not',flush=True)
    u.mem_write(m.scratch,b'\x01')
    preserved={r:0x12340000+i for i,r in enumerate((UC_M68K_REG_D2,UC_M68K_REG_D3,UC_M68K_REG_D4,UC_M68K_REG_D5,UC_M68K_REG_D6,UC_M68K_REG_D7,UC_M68K_REG_A1,UC_M68K_REG_A2,UC_M68K_REG_A3,UC_M68K_REG_A4,UC_M68K_REG_A5,UC_M68K_REG_A6))}
    m.call('ch_display_tick',m.scratch,0x1357,stop=0x40056c82,regs=preserved)
    assert u.reg_read(UC_M68K_REG_D0)==1 and u.reg_read(UC_M68K_REG_D1)==0x1357
    assert u.reg_read(UC_M68K_REG_A0)==m.scratch and u.reg_read(UC_M68K_REG_A7)==m.stack+4
    assert all(u.reg_read(r)==v for r,v in preserved.items())
    print('[ok] live captured voices, sustained settings, sequenced identity, note-off clearing and MIDI octave bounds',flush=True)


def port(source, selected=None):
    p=panel.p;p.OUT=OUT;p.freeze_candidate(OUT);sym=p.harmony.symbols()
    work=p.fixture(source,'panel',{0:2},key_raw=2)
    # Give source trigs a known sustain so the UI can be sampled mid-note.
    for bank in (work/'project').glob('bank*.work'):
        def sustain(data):
            for pattern in range(16):
                track=0x492e+pattern*0x8eec
                for step in range(64):data[track+0x39+step*32+2]=12
        p.otp._bank_write(work/'project',int(bank.stem[4:]),sustain,guard=False)
    card,_=p.emu_card.stage_project(work/'project','OCTABAM','BASS',tree=work/'sustain-tree')
    (work/'card.img').write_bytes(card)
    cases={
        'held':(panel.PANEL+'1600 key 0 down\n2300 quit\n','Cm',[48,51,55]),
        'accidentals':(panel.PANEL+'1600 key 0 down\n1800 key 9 down\n2300 quit\n','D#m7',[51,54,58,61]),
        'ninth':(panel.PANEL+'1600 key 1 down\n1800 key 10 down\n2300 quit\n','Ddim(addb9)',[50,53,56,63]),
        'settings':(panel.PANEL+'2300 quit\n','',[]),
        'no-scale':(panel.PANEL+'1600 key 1 down\n2300 quit\n','D',[50,54,57]),
        'no-scale-minor':(panel.PANEL+'1600 key 1 down\n1800 key 14 down\n2300 quit\n','Dm',[50,53,57]),
        'no-scale-sequence':(panel.PANEL+panel.key(1600,0x28)+'2100 quit\n',None,None),
        'released':(panel.PANEL+'1600 key 0 down\n1900 key 0 up\n2300 quit\n','',[]),
        'octave':(panel.PANEL+panel.combo(1500,0x21)+'2000 key 0 down\n2400 quit\n','Cm',[60,63,67]),
        'sequence':(panel.PANEL+panel.key(1600,0x28)+'2100 quit\n',None,None),
        'next-sequence':(panel.PANEL+panel.key(1600,0x28)+'2300 quit\n',None,None),
        'grid-sequence':(panel.PANEL+panel.key(1400,0x29)+panel.key(1600,0x28)+'2100 quit\n',None,None),
        'grid-next-sequence':(panel.PANEL+panel.key(1400,0x29)+panel.key(1600,0x28)+'2300 quit\n',None,None),
        'grid-rest':(panel.PANEL+panel.key(1400,0x29)+panel.key(1600,0x28)+'3800 quit\n','',[]),
        'grid-stopped':(panel.PANEL+panel.key(1400,0x29)+panel.key(1600,0x28)+panel.key(2400,0x27)+'2800 quit\n','',[]),
        'rest':(panel.PANEL+panel.key(1600,0x28)+'3800 quit\n','',[]),
        'stopped':(panel.PANEL+panel.key(1600,0x28)+panel.key(2400,0x27)+'2800 quit\n','',[]),
    }
    results={};panel_work=work
    for name,(script,want_name,want_notes) in cases.items():
        if selected and name not in selected:continue
        # Configure the Part too, so native KEY caches agree with the UI.
        work=p.fixture(source,'accidentals',{0:2},key_raw=8) if name=='accidentals' else p.fixture(source,name,{0:2},key_raw=0) if name.startswith('no-scale') else panel_work
        if name=='settings':work=p.fixture(source,name,{0:2},key_raw=2,voicings={0:2},spreads={0:1},roots={0:2})
        if name=='no-scale-sequence':
            for bank in (work/'project').glob('bank*.work'):
                p.otp._bank_write(work/'project',int(bank.stem[4:]),sustain,guard=False)
            card,_=p.emu_card.stage_project(work/'project','OCTABAM','BASS',tree=work/'sustain-tree')
            (work/'card.img').write_bytes(card)
        path=work/f'{name}.txt';path.write_text(script)
        dump=f'{sym["ch_name_text"]:#x},32={work}/{name}-name.bin;{sym["ch_display_notes"]:#x},4={work}/{name}-notes.bin;0x400beba2,4={work}/{name}-octave.bin;0x46c77a16,32={work}/{name}-native.bin'
        dump+=f';{sym["ch_settings_buffer"]:#x},24={work}/{name}-settings.bin'
        dump+=f';0x460d1736,4={work}/{name}-grid.bin'
        events=p.run(work,name,['--rtc','1800000000','--live-script',path,'--internal-clock','--lcd',work/f'{name}.lcd','--mem-dump',dump])
        actual=(work/f'{name}-name.bin').read_bytes().split(b'\0')[0].decode()
        notes=[n for n in (work/f'{name}-notes.bin').read_bytes() if n<128]
        if want_name is not None:assert (actual,notes)==(want_name,want_notes),(name,actual,notes)
        else:
            # Compare the UI snapshot to notes still active on the actual UART.
            held=set()
            for kind,ch,n,v in events:
                if ch==1:
                    if kind=='on':held.add(n)
                    else:held.discard(n)
            assert notes and set(notes)==held,(name,actual,notes,held)
            assert actual and actual!='Cm',(name,actual)
            if name=='no-scale-sequence':assert actual=='D'
            if name in ('next-sequence','grid-next-sequence'):assert actual!='Ddim'
        assert bool(int.from_bytes((work/f'{name}-grid.bin').read_bytes(),'big'))==name.startswith('grid-'),name
        assert int.from_bytes((work/f'{name}-octave.bin').read_bytes(),'big')==(5 if name=='octave' else 4)
        subprocess.run([sys.executable,str(ROOT/'tools/emu/lcd_view.py'),str(work/f'{name}.lcd'),'--png',str(work/f'{name}.png')],check=True,stdout=subprocess.DEVNULL)
        plane=(work/f'{name}.lcd').read_bytes()
        # Native title strip: solid border around inverse text, even after STOP.
        def bit(x,y):return bool(plane[x*8+y//8] & (0x80>>(y%8)))
        assert all(bit(x,31) for x in range(60,119)),name
        assert all(bit(60,y) for y in range(25,32)),name
        summary=(work/f'{name}-settings.bin').read_bytes().split(b'\0')[0].decode()
        assert summary==('N:N V:1 S:O R:-1' if name=='settings' else 'N:N V:R S:C R:K'),(name,summary)
        results[name]=dict(name=actual,notes=notes,title_bar=True,settings=summary)
        print('[ok]',name,actual,notes,flush=True)
    (OUT/('receipt-'+ '-'.join(selected)+'.json' if selected else 'receipt.json')).write_text(json.dumps(dict(cases=results,image_sha256=hashlib.sha256(p.CANDIDATE_IMAGE.read_bytes()).hexdigest(),hardware_tested=False),indent=2)+'\n')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('remix',nargs='?');ap.add_argument('--project',type=Path);ap.add_argument('--case',action='append',dest='selected',choices=('settings','held','accidentals','no-scale','no-scale-minor','no-scale-sequence','ninth','released','octave','sequence','next-sequence','rest','stopped','grid-sequence','grid-next-sequence','grid-rest','grid-stopped'));args=ap.parse_args()
    machine()
    if args.project:port(args.project,args.selected)
