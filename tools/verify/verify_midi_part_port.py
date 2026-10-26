#!/usr/bin/env python3
"""Real native Part lifecycle on a disposable virtual card, with no KITS API."""
import argparse
import hashlib
import json
from pathlib import Path
import midi_loopback_port as p

B=0x400e21e0
WORK=B+0x8ed80
SAVED=B+0x9504a
PS=0x18b2
CS1=0x100a4ece
FIELDS=(3,5,12,13,15,16,18,19)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project',type=Path,required=True)
    a=ap.parse_args()
    p.OUT=p.ROOT/'out/native-part-lifecycle'
    p.freeze_candidate(p.OUT)
    assert 'lb_dest_get' in p.symbols(), 'requires the Loopback test image'
    w=p.fixture(a.project,'native',{})
    for path in (w/'project').glob('bank*.work'):
        def seed(data):
            for part in range(8):
                for t in range(8):
                    at=p.otp.PART_BASE+part*p.otp.PART_STRIDE+9+0x4e2+36*t
                    # DEST plus all four values of the unrelated low bits.
                    values={field:0 for field in FIELDS}
                    values[12]=((part+t)%4)|(((part+t)%3)<<2)
                    for field,value in values.items():data[at+field]=value
        p.otp._bank_write(w/'project',int(path.stem[4:]),seed,guard=False)
    card,_=p.emu_card.stage_project(w/'project','OCTABAM','BASS',tree=w/'seed-tree')
    (w/'card.img').write_bytes(card)
    steps=[]
    def call(addr,*args):steps.extend(['--step','-:call:'+','.join(hex(v) for v in (addr,*args))])
    def dump(label,at=WORK,size=PS*4):steps.extend(['--step',f'-:dump:{at:#x},{size}={w}/{label}.bin'])
    dump('before');dump('saved-before',SAVED)
    call(0x4004a908,0);dump('saved',SAVED)
    # Corrupt only our live settings, then use native Reload to recover them.
    edits=';'.join(f'{WORK+0x4e2+36*t+f:#x}=0' for t in range(8) for f in FIELDS)
    steps.extend(['--step','-:poke:'+edits])
    call(0x4004aab4,0);dump('reloaded');dump('reloaded-cs1',CS1)
    call(0x4004a9d0,0);dump('cleared');dump('cleared-cs1',CS1);dump('cleared-saved',SAVED)
    # Copy from another real working Part through the native paste entry.
    call(0x40029a4c,WORK+PS,0);dump('pasted');dump('pasted-cs1',CS1)
    dump('saved-after',SAVED)
    script=w/'quit.txt';script.write_text('1500 quit\n')
    p.run(w,'lifecycle',steps+['--live-script',script])
    read=lambda name:(w/(name+'.bin')).read_bytes()
    before=read('before')
    assert read('saved')[:PS]==before[:PS]
    assert read('saved')[PS:]==read('saved-before')[PS:]
    assert read('reloaded')==before
    assert read('reloaded-cs1')==before
    clear=read('cleared')
    assert clear[PS:]==before[PS:]
    for t in range(8):
        for field in FIELDS:
            expected=({13:0x23,15:0x03}.get(field,0)
                      if 'bf_source_get' in p.symbols() else 0)
            assert clear[0x4e2+36*t+field]==expected,(t,field,clear[0x4e2+36*t+field],expected)
    # Stock Clear initializes both working and saved Part and leaves the
    # current CS1 working mirror to the caller's later refresh.
    assert read('cleared-cs1')==before
    assert read('pasted')[:PS]==before[PS:2*PS]
    assert read('pasted')[PS:]==before[PS:]
    assert read('pasted-cs1')==read('pasted')
    assert read('cleared-saved')[:PS]==clear[:PS], 'Clear must reset the saved Part too'
    assert read('saved-after')[:PS]==clear[:PS]
    assert read('saved-after')[PS:]==read('saved')[PS:]
    receipt=dict(native_save=True,reload=True,clear=True,paste=True,reload_paste_cs1_mirrors=True,clear_matches_native_saved_part_semantics=True,
                 unrelated_parts_unchanged=True,
                 image_sha256=hashlib.sha256(p.CANDIDATE_IMAGE.read_bytes()).hexdigest(),hardware_tested=False)
    (p.OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('[ok] native Part Save/Reload/Clear/Paste, native CS1 behavior and unrelated Part guards',flush=True)


if __name__=='__main__':main()
