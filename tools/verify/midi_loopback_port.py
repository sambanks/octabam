#!/usr/bin/env python3
"""Full firmware MIDI/UI/project checks. Uses a copied project and virtual CF only."""
import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import re
import midi_fixture
import midi_machine
ROOT=midi_machine.ROOT
sys.path.insert(0,str(ROOT/'tools'))
import emu_card
from hw import ot_project as otp
OUT=ROOT/'out/midi-loopback-port'


def fixture(source, name, records=None, arp=False):
    work=OUT/name;work.mkdir(parents=True,exist_ok=True)
    midi_fixture.fixture(source,work/'project',arp=arp)
    card,_=emu_card.stage_project(work/'project','OCTABAM','BASS',tree=work/'tree')
    (work/'card.img').write_bytes(card)
    return work


CANDIDATE_IMAGE = None
CANDIDATE_SYMBOLS = None


def symbols():
    """Loopback/STORE Part symbols belonging to the frozen candidate, if any."""
    if CANDIDATE_SYMBOLS is not None:
        return dict(CANDIDATE_SYMBOLS)
    raw = subprocess.check_output(['m68k-elf-nm', str(ROOT/'out/platform/runtime/runtime.elf')], text=True)
    return {n: int(a, 16) for a, n in re.findall(r'^([0-9a-f]+) [Tt] ((?:store_part|lb|bf)_\w+)$', raw, re.M)}



def freeze_candidate(destination):
    """Keep an image and its helper addresses together throughout a long run.

    A later development build must not silently change a subsequent case.
    Stock-comparison cases can still pass their explicit image.
    """
    global CANDIDATE_IMAGE, CANDIDATE_SYMBOLS
    destination.mkdir(parents=True, exist_ok=True)
    CANDIDATE_IMAGE = destination / 'candidate.bin'
    CANDIDATE_IMAGE.write_bytes((ROOT/'out/mainos_bus.bin').read_bytes())
    CANDIDATE_SYMBOLS = None
    frozen_symbols = symbols()
    CANDIDATE_SYMBOLS = frozen_symbols
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
    events=midi_fixture.notes((work/f'{name}.midi').read_bytes())
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
