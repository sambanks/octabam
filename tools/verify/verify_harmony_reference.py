#!/usr/bin/env python3
"""Compare packaged MIDI module bytes to fresh assemblies of their pinned source.

This is a source/options/final-link oracle, not an independent author binary.
Musical behavior, retained state and hardware acceptance are separate checks.
"""
import argparse
import json
from pathlib import Path
import re
import runpy
import subprocess
import tempfile

from verify_midi_scales_reference import ROOT, packaged_runtime, symbols
from remix import registry, schema


def reference_bytes(unit, keys, remix, address, exports, work, sections):
    args = []
    if unit.include:
        (work / 'remix.inc').write_text(unit.include(keys, remix))
        args = ['-I', str(work)]
    obj, elf, binary = (work / name for name in ('unit.o', 'unit.elf', 'unit.bin'))
    subprocess.run(['m68k-elf-as', '-mcpu=54455', *args,
                    *[f'--defsym={name}={value}' for name, value in unit.defsyms],
                    '-o', str(obj), unit.source], check=True)
    undefined = subprocess.check_output(['m68k-elf-nm', '-u', str(obj)], text=True)
    imports = sorted(line.split()[-1] for line in undefined.splitlines() if line.strip())
    assert not set(imports) - exports.keys(), (unit.label, 'missing final imports')
    subprocess.run(['m68k-elf-ld', '-Ttext=' + hex(address), '-e', hex(address),
                    *[f'--section-start={name}={hex(start)}' for name, start in sections.items()],
                    *[f'--defsym={name}={hex(exports[name])}' for name in imports],
                    '-o', str(elf), str(obj)], check=True)
    result = {}
    for section in ('.text', *sections):
        if section == '.bss':
            continue
        subprocess.run(['m68k-elf-objcopy', '-O', 'binary', '-j', section, str(elf), str(binary)], check=True)
        result[section] = binary.read_bytes()
    return result


def author_modules(keys):
    for key, slug in (('MIDI HARMONY', 'midi-harmony'),
                      ('MIDI SRAM', 'midi-sram'), ('MIDI FOLLOW', 'midi-follow')):
        if key not in keys:
            continue
        author = ROOT / 'modules' / slug / 'upstream/modules' / slug / 'manifest.py'
        yield schema.apply_select(runpy.run_path(str(author))['MODULE'], keys)


def verify(remix, out):
    keys = frozenset(remix.modules)
    runtime = out / 'platform/runtime'
    raw = (runtime / 'runtime.bin').read_bytes()
    base = json.loads((out / 'platform/layout.json').read_text())['base']
    loader = symbols(out / 'platform/loader.elf')
    packaged = packaged_runtime((out / 'mainos_bus.bin').read_bytes(), loader['table'], base)
    assert packaged == raw, 'packaged runtime differs from runtime.bin'
    mapping = (runtime / 'runtime.map').read_text()
    exports = symbols(runtime / 'runtime.elf', global_only=True)
    checked = 0
    with tempfile.TemporaryDirectory(prefix='harmony-author-reference-') as temporary:
        for module in author_modules(keys):
            for unit in module.linked:
                spans = re.findall(r'^ \.text\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+.*?/\d+_'
                                   + re.escape(unit.label) + r'\.o$', mapping, re.M)
                assert len(spans) == 1, (unit.label, 'text spans', spans)
                address, size = (int(value, 16) for value in spans[0])
                offset = address - base
                assert size > 0 and 0 <= offset <= len(raw) - size, unit.label
                work = Path(temporary) / unit.label
                work.mkdir()
                sections = {name: int(start, 16) for name, start in re.findall(
                    r'^ (\.(?:bss|data|rodata))\s+0x([0-9a-f]+)\s+0x[0-9a-f]+\s+.*?/\d+_'
                    + re.escape(unit.label) + r'\.o$', mapping, re.M)}
                oracle = reference_bytes(unit, keys, remix, address, exports, work, sections)
                assert len(oracle['.text']) == size, (unit.label, 'reference size', len(oracle['.text']), size)
                for section, data in oracle.items():
                    if not data:
                        continue
                    at = address if section == '.text' else sections[section]
                    offset = at - base
                    assert 0 <= offset <= len(packaged) - len(data), (unit.label, section, 'bounds')
                    assert packaged[offset:offset + len(data)] == data, (unit.label, section, 'packaged source mismatch')
                checked += 1
    print(f'[ok] {checked} selected MIDI units match freshly assembled, final-linked pinned source')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('remix')
    args = parser.parse_args()
    verify(registry.remix(args.remix), ROOT / 'out')


if __name__ == '__main__':
    main()
