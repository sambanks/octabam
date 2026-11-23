#!/usr/bin/env python3
"""Choose Analog Bassdrum and select its engine using actual stock panel events."""
import json,os,pathlib,shutil,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/harness'))
from ab_fixture import prepare
def key(code, gap=.6, hold=.6):
    return [(gap, f"key {code:#x} down"), (hold, f"key {code:#x} up")]
OUT=pathlib.Path(os.environ.get('AB_UI_OUT',ROOT/'out/analog-bassdrum/ui-gate')).resolve()
def main():
    src=os.environ.get('OT_PROJECT')
    if not src:
        print('[SKIP] Analog Bassdrum panel: set OT_PROJECT to a stock project fixture');return
    OUT.mkdir(parents=True,exist_ok=True)
    fixture=prepare(src,OUT/'project')
    card=OUT/'card.img'
    subprocess.run([sys.executable,str(ROOT/'tools/emu/ot_emu/stage_card.py'),str(fixture),'OCTABAM','RIG','--tree',str(OUT/'tree'),'--out',str(card)],check=True,cwd=ROOT)
    image=OUT/'image.bin';shutil.copy2(os.environ.get('AB_IMAGE',ROOT/'out/mainos_bus.bin'),image)
    sym={l.split()[-1]:int(l.split()[0],16) for l in subprocess.check_output(['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True).splitlines() if len(l.split())==3}
    if os.environ.get('AB_SYMBOLS'): sym=json.loads(pathlib.Path(os.environ['AB_SYMBOLS']).read_text())
    # ANALOG BD's row on the machine list is the word MACHINES gives it (modules/machines)
    rt=ROOT/'out/platform/runtime'
    heads=subprocess.check_output(['m68k-elf-objdump','-h',str(rt/'runtime.elf')],text=True).splitlines()
    rt_base=int(next(l.split()[3] for l in heads if len(l.split())>3 and l.split()[1]=='.text'),16)
    at=sym['ab_mc_row']-rt_base
    ab_row=int.from_bytes((rt/'runtime.bin').read_bytes()[at:at+4],'big')
    spans=f'0x40170f60,6322={OUT}/part.bin;{sym["desc"]:#x},916={OUT}/desc.bin;{0x400d5f38+4*ab_row:#x},4={OUT}/page.bin;0x460e70e0,4={OUT}/pool.bin;0x400bb7d0,4={OUT}/setup.bin;0x460e5e30,28={OUT}/list.bin;0x100a4ece,6322={OUT}/shadow.bin;0x80000830,1={OUT}/live.bin;0x460e738e,16={OUT}/navigation.bin'
    cmd=[os.environ.get('AB_EMU',str(ROOT/'out/emu/ot_emu')),'--image',str(image),'--card',str(card),'--set','OCTABAM','--project','RIG','--load-ms','20000','--dsp','--mem-dump',spans]
    cmd += ["--lcd", str(OUT/"lcd.bin")]
    # T1 -> SRC SETUP -> bottom row -> YES; the former MODEL encoder is inert.
    script=key(0x10)+[(.6,'key 0x2d down'),(.3,'key 0x22 down'),(.3,'key 0x22 up'),(.3,'key 0x2d up')]
    for _ in range(6):script+=key(0x20,.25,.25)
    # Beside other machines (modules/machines) the list has more rows: the row count, poked at
    # 0x40079248, and ANALOG BD's row say how many UPs from the bottom reach it.
    # A short press: a 0.25 s hold auto-repeats (the DOWNs above rely on it only to reach the end).
    rows=image.read_bytes()[0x40079248-0x40000400+3]
    for _ in range(rows-1-ab_row):script+=key(0x33,.25,.06)
    script+=key(0x31)
    script+=[(.8,'enc 0 16'),(.8,'enc 2 -4')]
    # Close setup, then double-tap T1 with a 210 ms down-to-down gap.
    script+=key(0x32)+[(.6,'key 0x10 down'),(.06,'key 0x10 up'),
                      (.15,'key 0x10 down'),(.06,'key 0x10 up')]
    # Navigate to the machine column and back, as with STATIC/FLEX.
    # A disabled draw bit alone does not stop the stock editor. Select 909,
    # turn the old MODEL encoder backwards, and ensure it stays selected.
    left_script=script+key(0x20)+key(0x31)
    left_script += [(.6,'key 0x2d down'),(.3,'key 0x22 down'),(.3,'key 0x22 up'),(.3,'key 0x2d up'),(.8,'enc 0 -16')]
    left_script += key(0x32)+[(.6,'key 0x10 down'),(.06,'key 0x10 up'),(.15,'key 0x10 down'),(.06,'key 0x10 up')]+key(0x34)+[(.8,'quit')]
    script+=key(0x34)
    # Visit FLEX's real sample column, then return to Analog BD's engine column.
    # Short presses: one row each (a 0.25 s hold repeats, and below ANALOG BD can be OCTA-303).
    for _ in range(ab_row-1): script+=key(0x33,.25,.06)
    script+=key(0x21)+key(0x34)
    for _ in range(ab_row-1): script+=key(0x20,.25,.06)
    script+=key(0x21)
    # Select 909 through the pool, then return and select 808.
    script+=key(0x20)+key(0x31)
    script+=[(.6,'key 0x10 down'),(.06,'key 0x10 up'),(.15,'key 0x10 down'),(.06,'key 0x10 up')]
    # Select 808 from the list, then reopen: the highlight must follow the stored model.
    script+=key(0x33)+key(0x31)
    script+=[(.6,'key 0x10 down'),(.06,'key 0x10 up'),(.15,'key 0x10 down'),(.06,'key 0x10 up'),(.8,'quit')]
    # Browse away and cancel; reopening must still select 808.
    script=script[:-1]+key(0x20)+key(0x32)
    script+=[(.6,'key 0x10 down'),(.06,'key 0x10 up'),(.15,'key 0x10 down'),(.06,'key 0x10 up'),(.8,'quit')]
    elapsed=0; left_events=[]
    for delay,event in left_script:
        elapsed+=round(delay*1000)
        left_events.append(f'{elapsed} {event}\n')
    leftfile=OUT/'left-events.txt';leftfile.write_text(''.join(left_events))
    with (OUT/'left-port.log').open('w') as log:
        subprocess.run(cmd+['--live-script',str(leftfile)],cwd=ROOT,
                       stdout=log,stderr=subprocess.STDOUT,timeout=600,check=True)
    assert int.from_bytes((OUT/'pool.bin').read_bytes(),'big')!=0, 'LEFT did not open machine chooser'
    assert int.from_bytes((OUT/'list.bin').read_bytes()[:4],'big')==0, 'LEFT left engine list open'
    nav=(OUT/'navigation.bin').read_bytes()
    assert (OUT/'part.bin').read_bytes()[0x1da+6]==1, 'hidden MODEL encoder changed engine'
    assert int.from_bytes(nav[:4],'big')==ab_row, 'LEFT did not highlight Analog BD'
    assert int.from_bytes(nav[12:16],'big')==0, 'LEFT did not select machine column'
    shutil.copy2(OUT/'lcd.bin',OUT/'left-lcd.bin')
    elapsed=0; events=[]
    for delay,event in script:
        elapsed+=round(delay*1000)
        events.append(f'{elapsed} {event}\n')
    eventfile=OUT/'events.txt';eventfile.write_text(''.join(events))
    with (OUT/'port.log').open('w') as log:
        subprocess.run(cmd+['--live-script',str(eventfile)],cwd=ROOT,
                       stdout=log,stderr=subprocess.STDOUT,timeout=600,check=True)
    part=(OUT/'part.bin').read_bytes()
    assert part[0x22]==1 and part[60:63]==b'AB\x01', ('Analog BD selection did not land',part[0x22],part[60:63])
    assert int.from_bytes((OUT/'pool.bin').read_bytes(),'big')==0, 'sample pool opened'
    listing=(OUT/'list.bin').read_bytes()
    assert int.from_bytes(listing[:4],'big')!=0, 'engine list did not open'
    assert int.from_bytes(listing[16:20],'big')==0, 'engine list highlight did not follow 808'
    assert int.from_bytes(listing[24:28],'big')==2, 'engine list row count'
    assert (OUT/'shadow.bin').read_bytes()[0x1da+6]==0
    assert (OUT/'live.bin').read_bytes()==b'\0'
    log=(OUT/'port.log').read_text();assert 'ILLEGAL' not in log and 'ended on quit' in log
    part=(OUT/'part.bin').read_bytes();desc=(OUT/'desc.bin').read_bytes()
    assert part[0x22]==1 and part[60:63]==b'AB\x01',('selection',part[0x22],part[60:63])
    assert 64 < part[0x1da+8] < 127, ('LPF encoder',part[0x1da+8])
    assert part[0x1da+6]==0,('MODEL',part[0x1da+6])
    assert list(part[48:54])==[64,80,80,64,64,0],list(part[48:54])
    assert desc[0x4e+6*6:0x4e+6*6+6]==bytes(6)
    assert int.from_bytes(desc[0xd2+4*6:0xd2+4*7],'big')==0
    assert int.from_bytes((OUT/'page.bin').read_bytes(),'big')==sym['desc']+0x38, 'MODEL page did not change'
    for model in (0,1):
        d=desc[model*458:(model+1)*458]
        assert d[0x4e+2*6:0x4e+2*6+6]==(b'TONE\0\0' if model==0 else b'TUNE\0\0')
        assert d[0x4e+8*6:0x4e+8*6+6]==b'LPF\0\0\0'
        assert int.from_bytes(d[0x1c2:0x1c6],'big')==0x111
        assert int.from_bytes(d[0x1c6:0x1ca],'big')==0x10111111
        assert d[0x96+8]==127
        assert d[0x4e+5*6:0x4e+6*6] == b'SAT\0\0\0'
        assert d[0x96+9:0x96+11] == bytes([64,64])
        assert int.from_bytes(d[0x132+4*6:0x136+4*6],"big")==0
        assert int.from_bytes(d[0x162+4*6:0x166+4*6],"big")==0
        if model:
            assert d[0x4e+9*6:0x4e+11*6] == b'LOW\0\0\0HIGH\0\0'
    print('PASS chooser: Analog Bassdrum, defaults, hidden MODEL encoder is inert and LPF remains editable; LEFT returns to machine chooser, FLEX/AB horizontal navigation, engine pool selects 808, cancels a 909 browse and reopens on 808')
if __name__=='__main__':main()
