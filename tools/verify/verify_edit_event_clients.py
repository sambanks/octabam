#!/usr/bin/env python3
"""Check selected EDIT EVENTS callback code and installed hook ownership."""
from pathlib import Path
import runpy
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import toolpath
from remix import registry

def main():
    remix=registry.remix(sys.argv[1]);selected={m.key:m for m in registry.selected(remix)}
    raw=subprocess.check_output(['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True)
    symbols={f[2]:(int(f[0],16),f[1]) for line in raw.splitlines() if len(f:=line.split())==3}
    image=(ROOT/'out/mainos_bus.bin').read_bytes()
    callbacks=[];sites=[]
    for slug,key in (('edit-events','EDIT EVENTS'),):
        if key not in selected:continue
        declaration=runpy.run_path(str(ROOT/'modules'/slug/'manifest.py'))
        for client,prefix,events in declaration['CLIENTS']:
            if client not in selected:continue
            for event in events:
                suffixes=('claim','handle') if event=='held' else (event,)
                for suffix in suffixes:
                    name=f'{prefix}_{suffix}'
                    assert name in symbols and symbols[name][1] in 'Tt', (name,symbols.get(name),'callback must be executable text')
                    callbacks.append(name)
        for d in selected[key].detours:
            owners=[m.key for m in selected.values() for other in m.detours if other.site==d.site]
            assert owners==[key],(hex(d.site),owners)
            target=symbols[d.symbol][0]
            opcode={'jmp':b'\x4e\xf9','jsr':b'\x4e\xb9','lea':d.expect[:2]}[d.kind]
            actual=image[d.site-0x40000400:d.site-0x40000400+6]
            assert actual==opcode+target.to_bytes(4,'big'),(hex(d.site),d.symbol)
            sites.append(d.site)
    print(f'[ok] {len(callbacks)} executable client callbacks; {len(sites)} exclusively owned, installed system hooks; no bridges')

if __name__=='__main__':main()
