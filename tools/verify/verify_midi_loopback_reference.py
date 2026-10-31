#!/usr/bin/env python3
"""Independently assemble pinned Loopback units against installed STORE imports.

The former whole-author runtime included the retired Part helper. STORE is
now Octabam-owned; compare each author's unit at its installed address with
its final external symbols, without rebuilding or copying STORE into the
source repository. No firmware bytes are distributed.
"""
from pathlib import Path
import json
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import toolpath
from remix import registry


def main():
    remix=sys.argv[1] if len(sys.argv)>1 else 'midi-loopback'
    selected=registry.bound(registry.remix(remix));module=selected['MIDI LOOPBACK']
    out=ROOT/'out/platform/runtime';raw=(out/'runtime.bin').read_bytes()
    base=json.loads((ROOT/'out/platform/layout.json').read_text())['base']
    rows=subprocess.check_output(['m68k-elf-nm',str(out/'runtime.elf')],text=True)
    exports={n:int(a,16) for a,n in re.findall(r'^([0-9a-f]+) [TtBbDdAa] (\S+)$',rows,re.M)}
    mapping=(out/'runtime.map').read_text()
    with tempfile.TemporaryDirectory(prefix='loopback-source-reference-') as tmp:
        d=Path(tmp)
        for unit in module.linked:
            found=re.findall(r'^ \.text\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+.*?/\d+_'+re.escape(unit.label)+r'\.o$',mapping,re.M)
            assert len(found)==1,(unit.label,found)
            address,size=map(lambda x:int(x,16),found[0])
            (d/'remix.inc').write_text(unit.include(set(registry.remix(remix).modules),registry.remix(remix)) if unit.include else '')
            obj=d/'unit.o';elf=d/'unit.elf';binary=d/'unit.bin'
            subprocess.run(['m68k-elf-as','-mcpu='+unit.cpu,'-I',str(d),'-o',str(obj),unit.source],check=True)
            undefined=subprocess.check_output(['m68k-elf-nm','-u',str(obj)],text=True)
            imports=[line.split()[-1] for line in undefined.splitlines() if line.strip()]
            assert all(name in exports for name in imports),(unit.label,imports)
            subprocess.run(['m68k-elf-ld','-Ttext='+hex(address),'-e',hex(address),*[f'--defsym={n}={hex(exports[n])}' for n in imports],'-o',str(elf),str(obj)],check=True,stdout=subprocess.DEVNULL)
            subprocess.run(['m68k-elf-objcopy','-O','binary',str(elf),str(binary)],check=True)
            oracle=binary.read_bytes()
            assert len(oracle)==size,(unit.label,len(oracle),size)
            assert raw[address-base:address-base+size]==oracle,unit.label
            print(f'[ok] pinned author {unit.label}: {size} bytes match installed unit; {len(imports)} final imports')


if __name__=='__main__':main()
