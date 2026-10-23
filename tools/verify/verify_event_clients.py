#!/usr/bin/env python3
"""Check actual selected callback code and installed system-hook ownership."""
import json
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
    runtime = ROOT/'out/platform/runtime/runtime.elf'
    # A standalone empty EVENTS image does not need a platform runtime.
    has_runtime = any(u.dram for m in selected.values() for u in m.linked)
    raw = subprocess.check_output(['m68k-elf-nm',str(runtime)],text=True) if has_runtime else ''
    symbols={f[2]:(int(f[0],16),f[1]) for line in raw.splitlines() if len(f:=line.split())==3}
    image=(ROOT/'out/mainos_bus.bin').read_bytes()
    callbacks=[];sites=[]
    key = 'EVENTS'
    if key in selected:
        declaration=runpy.run_path(str(ROOT/'modules/events/manifest.py'))
        for handlers in declaration['registrations'](selected).values():
            for names in handlers:
                for name in names:
                    assert name in symbols and symbols[name][1] in 'Tt', (name,symbols.get(name),'callback must be executable text')
                    callbacks.append(name)
        installed = {d.site for d in selected[key].detours}
        for hooks in declaration['HOOKS'].values():
            for d in hooks:
                if d.site not in installed:
                    offset=d.site-0x40000400
                    assert image[offset:offset+len(d.expect)] == d.expect, (hex(d.site), 'unused event changed stock bytes')
                    assert d.symbol not in symbols, (d.symbol, 'unused event code was linked')
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
