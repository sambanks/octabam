#!/usr/bin/env python3
"""Compare packaged MIDI Scales bytes with a fresh build of the pinned author unit.

Composition imports use their final addresses. This checks source/option/link
fidelity; the standalone fixed SHA and musical-behavior gate remain separate.
"""
import argparse
import json
from pathlib import Path
import re
import runpy
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import toolpath  # noqa: E402,F401
from ghidra import depack  # noqa: E402
from remix import platform_build, registry  # noqa: E402


def symbols(elf, *, global_only=False):
    args = ['m68k-elf-nm', '--defined-only']
    if global_only:
        args.append('-g')
    rows = subprocess.check_output([*args, str(elf)], text=True)
    return {name: int(address, 16) for address, name in re.findall(
        r'^([0-9a-f]+) [TtBbDdAaRr] (\S+)$', rows, re.M)}


def author_unit():
    manifest = ROOT / 'modules/midi-scales/upstream/modules/midi-scales/manifest.py'
    module = runpy.run_path(str(manifest))['MODULE']
    assert len(module.linked) == 1, 'update the reference gate for additional author units'
    return module.linked[0]


def packaged_runtime(image, table_address, runtime_base):
    """Read the real image's loader table and validate its runtime payload."""
    def span(address, size):
        offset = address - 0x40000400
        assert size >= 0 and 0 <= offset <= len(image) - size, ('image span', address, size)
        return image[offset:offset + size]

    count, = struct.unpack('>I', span(table_address, 4))
    assert count > 0, 'empty loader table'
    rows = span(table_address + 4, count * 32)
    matches = []
    for src, size, phash, _stage, dst, rawlen, rhash, _backup in struct.iter_unpack('>8I', rows):
        if dst != runtime_base + platform_build.UNCACHED:
            continue
        blob = span(src, size)
        assert blob[:4] == platform_build.SIGNATURE and blob[4:8] == b'GKA3', 'runtime blob header'
        assert platform_build.roll(blob[4:]) == phash, 'runtime packed hash'
        raw = depack.depack(blob[4:])
        assert len(raw) == rawlen and platform_build.roll(raw) == rhash, 'runtime decoded hash/size'
        matches.append(raw)
    assert len(matches) == 1, ('runtime payload count', len(matches))
    return matches[0]


def reference_bytes(module_keys, address, exports, work):
    unit = author_unit()
    (work / 'remix.inc').write_text(unit.include(module_keys) if unit.include else '')
    obj, elf, binary = (work / name for name in ('unit.o', 'unit.elf', 'unit.bin'))
    # All platform DRAM units use the chip's ISA C, regardless of cave CPU defaults.
    subprocess.run(['m68k-elf-as', '-mcpu=54455', '-I', str(work), '-o', str(obj),
                    unit.source], check=True)
    undefined = subprocess.check_output(['m68k-elf-nm', '-u', str(obj)], text=True)
    imports = sorted(line.split()[-1] for line in undefined.splitlines() if line.strip())
    missing = set(imports) - exports.keys()
    assert not missing, f'midiscales missing final imports: {sorted(missing)}'
    subprocess.run(['m68k-elf-ld', '-Ttext=' + hex(address), '-e', hex(address),
                    *[f'--defsym={name}={hex(exports[name])}' for name in imports],
                    '-o', str(elf), str(obj)], check=True)
    subprocess.run(['m68k-elf-objcopy', '-O', 'binary', str(elf), str(binary)], check=True)
    return binary.read_bytes(), len(imports)


def verify(module_keys, out):
    assert 'MIDI SCALES' in module_keys, 'selection does not carry MIDI Scales'
    runtime = out / 'platform/runtime'
    raw = (runtime / 'runtime.bin').read_bytes()
    base = json.loads((out / 'platform/layout.json').read_text())['base']
    loader = symbols(out / 'platform/loader.elf')
    packaged = packaged_runtime((out / 'mainos_bus.bin').read_bytes(), loader['table'], base)
    assert packaged == raw, 'packaged runtime differs from runtime.bin'
    mapping = (runtime / 'runtime.map').read_text()
    spans = re.findall(r'^ \.text\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+.*?/\d+_midiscales\.o$',
                       mapping, re.M)
    assert len(spans) == 1, ('midiscales text spans', spans)
    address, size = (int(value, 16) for value in spans[0])
    offset = address - base
    assert size > 0 and 0 <= offset <= len(raw) - size, 'midiscales outside runtime'
    with tempfile.TemporaryDirectory(prefix='scales-author-reference-') as temporary:
        oracle, imports = reference_bytes(module_keys, address,
                                         symbols(runtime / 'runtime.elf', global_only=True),
                                         Path(temporary))
    assert len(oracle) == size, ('midiscales reference size', len(oracle), size)
    actual = packaged[offset:offset + size]
    assert actual == oracle, 'midiscales packaged bytes differ from pinned author reference'
    print(f'[ok] pinned author midiscales: {size} packaged bytes match; {imports} final imports')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('remix', nargs='?', default='midi-scales')
    args = parser.parse_args()
    verify(set(registry.remix(args.remix).modules), ROOT / 'out')


if __name__ == '__main__':
    main()
