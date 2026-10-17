#!/usr/bin/env python3
"""Physical panel event protocol, native save/reload and LCD proof on a virtual card."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
import midi_loopback_port as p
import verify_midi_loopback as lb


def key(at,code):
    return f'{at} key {code:#x} down\n{at+80} key {code:#x} up\n'


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('remix',nargs='?',default='midi-loopback')
    ap.add_argument('--project',type=Path,required=True)
    a=ap.parse_args()
    assert a.remix.replace('-', '').isalnum()
    p.OUT=p.ROOT/'out'/f'{a.remix}-ui-port'
    (p.OUT/'result.json').unlink(missing_ok=True)
    image=p.freeze_candidate(p.OUT);sym=lb.symbols()
    w=p.fixture(a.project,'routing',{})
    # Force an audio-track start so the scripted MIDI toggle is deterministic.
    import re
    for f in (w/'project').glob('project.*'):
        s=re.sub(rb'MIDI_MODE=\d+',b'MIDI_MODE=0',f.read_bytes())
        s=re.sub(rb'(?m)^TRACK=\d+',b'TRACK=0',s);f.write_bytes(s)
    card,_=p.emu_card.stage_project(w/'project','OCTABAM','BASS',tree=w/'ui-tree')
    (w/'card.img').write_bytes(card)
    base=key(100,0x31)+key(600,0x35)+key(1100,0x10)
    base+='1600 key 0x2d down\n1700 key 0x22 down\n1850 key 0x22 up\n1950 key 0x2d up\n'
    edit=base+'2300 enc 0 4\n'+key(2500,0x38)+'2800 enc 0 4\n'
    # B..F have no function inside the window; their turns/pushes are consumed.
    for i in range(1,6):
        edit+=f'{3000+i*200} enc {i} 4\n'+key(3050+i*200,0x38+i)
    def run(name,script,card=None,extra=()):
        path=w/(name+'.txt');path.write_text(script)
        p.run(w,name,['--rtc','1800000000','--live-script',path,'--lcd',w/(name+'.lcd'),
                     '--mem-dump',f'0x100a4ece,25288={w}/{name}-parts.bin;{sym["lb_page_win"]:#x},4={w}/{name}-window.bin;0x100b14cc,1={w}/{name}-track.bin;0x10000000,1048576={w}/{name}-cs1.bin',*extra],card=card,physical_panel=True)
        return (w/(name+'-parts.bin')).read_bytes()
    state=run('open',edit+'4500 quit\n')
    assert state[0x4e2]==2, ('CHAN press did not apply pending channel',state[0x4e2])
    assert state[0x4e2+12]==4, ('A did not set INT',state[0x4e2+12])
    assert int.from_bytes((w/'open-window.bin').read_bytes(),'big')!=0
    assert (w/'open-track.bin').read_bytes()==b'\0'
    for t in range(1,8):assert state[0x4e2+36*t+12]==0
    subprocess.run([str(p.ROOT/'.venv/bin/python'),str(p.ROOT/'tools/emu/lcd_view.py'),str(w/'open.lcd'),'--png',str(w/'open.png')],check=True,stdout=subprocess.DEVNULL)
    # Save the immediately applied destination through the existing native UI.
    close=edit+key(4500,0x38)+key(4900,0x32)
    for at,k in zip(range(5500,9700,700),[0x1c,0x21,0x20,0x31,0x31]):close+=key(at,k)
    saved=run('save',close+'40000 quit\n')
    assert saved==state
    assert (w/'save-window.bin').read_bytes()==bytes(4)
    files=p.emu_card.extract_image((w/'save-card.img').read_bytes())
    for name in ('bank01.work','bank01.strd'):
        data=files['OCTABAM/BASS/'+name]
        for part in range(4):
            start=p.otp.PART_BASE+part*p.otp.PART_STRIDE+9
            assert data[start:start+6322]==state[part*6322:(part+1)*6322],name
    for name,extra in [('reload',()),('warm',('--no-post','--cs1-in',w/'save-cs1.bin'))]:
        assert run(name,'1500 quit\n',w/'save-card.img',extra)==saved,name
    # Closing keys act like Harmony/Follow and leave applied settings intact.
    for name,k in [('yes',0x32),('no',0x31),('track',0x11),('page',0x23)]:
        closed=run(name,edit+key(4500,k)+'4900 quit\n')
        assert closed==state,name
        assert (w/(name+'-window.bin')).read_bytes()==bytes(4),name
        assert (w/(name+'-track.bin')).read_bytes()==bytes([1 if name=='track' else 0]),name
    # Isolate transport from native received-note mappings that can select tracks.
    run('transport',edit+'4200 enc 0 -4\n'+key(4400,0x28)+key(6800,0x27)+'7300 quit\n',extra=('--internal-clock',))
    assert int.from_bytes((w/'transport-window.bin').read_bytes(),'big')!=0
    events=lb.decode((w/'transport.midi').read_bytes())
    assert any(e[0]&0xf0==0x90 and e[2]>0 for e in events), 'transport did not play through window'
    # Fresh project has no route carried over from retained memory.
    assert run('fresh','1500 quit\n',extra=('--cs1-in',w/'save-cs1.bin'))[0x4e2+12]==0
    result={'status':'pass','image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),
            'checks':['CHAN staged activation','A DEST and unused controls','close A/YES/NO/track/page',
                      'transport through window','native project save','disk reload','CS1 resume','fresh project EXT'],
            'scope':'full firmware under emulator, physical panel protocol; no hardware acceptance'}
    (p.OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('[ok] CHAN commit, modal controls/closing, native SAVE, disk reload, retained resume and fresh EXT')


if __name__=='__main__':main()
