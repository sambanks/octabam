"""Author variants must match the runtime actually carried by an image.

Fixtures link the real pinned Scales source with tiny external providers and
package it behind a synthetic loader table. No stock firmware is needed.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tools/verify')]
import verify_midi_scales_reference as reference
from remix import pack, platform_build
from remix.schema import Linked

TOOLS = all(shutil.which(tool) for tool in (
    'm68k-elf-as', 'm68k-elf-ld', 'm68k-elf-objcopy',
    'm68k-elf-objdump', 'm68k-elf-nm'))
IMAGE_BASE = 0x40000400
RUNTIME_BASE = 0x40a00000
PROVIDERS = ('bf_source_resolve', 'bf_source_resolve_at',
             'store_part_ui_context', 'store_part_midi_context',
             'store_part_midi_key', 'mh_active')


class DeclarationTests(unittest.TestCase):
    def test_packaged_reference_gate_and_standalone_oracle_stay_declared(self):
        module = runpy.run_path(str(ROOT / 'modules/midi-scales/manifest.py'))['MODULE']
        gates = [gate for gate in module.gates
                 if gate.script == 'tools/verify/verify_midi_scales_reference.py']
        self.assertEqual(len(gates), 1)
        self.assertEqual(gates[0].stage, 'image')
        self.assertTrue(gates[0].venv)
        self.assertEqual(module.linked[0].reference_for({'MIDI SCALES'}), (
            0x40a955e0,
            'e265a08d11b72cc6806c6ac5212969b828c28e2c34681ae088c686e51db8c806'))


@unittest.skipUnless(TOOLS, 'needs the m68k-elf toolchain (make setup)')
class PackagedReferenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='scales-reference-test-')
        self.addCleanup(temporary.cleanup)
        self.out = Path(temporary.name)
        no_cache = patch.dict(os.environ, {'OCTABAM_NO_CACHE': '1'})
        no_cache.start()
        self.addCleanup(no_cache.stop)
        self.platform = self.out / 'platform'
        self.runtime = self.platform / 'runtime'

    def run_tool(self, *args):
        subprocess.run(list(map(str, args)), check=True, capture_output=True)

    def build(self, *companions):
        self.keys = {'MIDI SCALES', *companions}
        self.platform.mkdir()
        source = self.out / 'providers.s'
        source.write_text('.text\n' + ''.join(
            f'.global {name}\n{name}: moveq #{i},%d0\nrts\n'
            for i, name in enumerate(PROVIDERS)))
        unit = reference.author_unit()
        raw, self.exports, _, _ = platform_build.link_runtime(
            [('PROVIDERS', Linked('providers', str(source), dram=True)),
             ('MIDI SCALES', unit)],
            self.runtime, {}, RUNTIME_BASE,
            includes={unit.label: unit.include(self.keys)})
        (self.platform / 'layout.json').write_text(json.dumps({'base': RUNTIME_BASE}))
        self.package(raw)
        return raw

    def package(self, raw):
        blob = (platform_build.SIGNATURE + pack.PACKED_MAGIC
                + len(raw).to_bytes(4, 'big') + pack.pack(raw, 64))
        blob_path = self.platform / 'packed.bin'
        blob_path.write_bytes(blob)
        source = self.platform / 'loader.s'
        source.write_text(
            '.text\n.global synthetic_start\nsynthetic_start: rts\n.balign 4\n'
            'table: .long 1\n'
            f'.long blob,{len(blob)},{platform_build.roll(blob[4:])},0,'
            f'{RUNTIME_BASE + platform_build.UNCACHED},{len(raw)},'
            f'{platform_build.roll(raw)},0\n'
            f'blob: .incbin "{blob_path}"\n')
        obj, elf, binary = (self.platform / name for name in (
            'loader.o', 'loader.elf', 'loader.bin'))
        self.run_tool('m68k-elf-as', '-mcpu=54455', '-o', obj, source)
        self.run_tool('m68k-elf-ld', '-Ttext=' + hex(IMAGE_BASE + 256),
                      '-e', 'synthetic_start', '-o', elf, obj)
        self.run_tool('m68k-elf-objcopy', '-O', 'binary', elf, binary)
        (self.out / 'mainos_bus.bin').write_bytes(bytes(256) + binary.read_bytes())

    def verify(self, keys=None):
        with contextlib.redirect_stdout(io.StringIO()):
            reference.verify(self.keys if keys is None else keys, self.out)

    def changed_runtime(self):
        raw = bytearray((self.runtime / 'runtime.bin').read_bytes())
        raw[self.exports['ms_snap'] - RUNTIME_BASE + 2] ^= 1
        return bytes(raw)

    def test_standalone_author_variant(self):
        self.build()
        self.verify()

    def test_follow_author_variant(self):
        self.build('MIDI FOLLOW')
        self.verify()

    def test_harmony_author_variant(self):
        self.build('MIDI HARMONY')
        self.verify()

    def test_follow_and_harmony_author_variant(self):
        self.build('MIDI FOLLOW', 'MIDI HARMONY')
        self.verify()

    def test_wrong_author_variant_is_rejected(self):
        self.build('MIDI FOLLOW')
        with self.assertRaisesRegex(AssertionError, 'midiscales reference size|pinned author reference'):
            self.verify({'MIDI SCALES'})

    def test_changed_unit_with_consistent_packaging_is_rejected(self):
        self.build('MIDI FOLLOW')
        changed = self.changed_runtime()
        (self.runtime / 'runtime.bin').write_bytes(changed)
        self.package(changed)
        with self.assertRaisesRegex(AssertionError, 'packaged bytes differ from pinned author reference'):
            self.verify()

    def test_missing_final_import_is_rejected(self):
        self.build('MIDI FOLLOW')
        # The code bytes remain valid, but a local symbol is not a final export.
        self.run_tool('m68k-elf-objcopy', '--localize-symbol=bf_source_resolve',
                      self.runtime / 'runtime.elf')
        with self.assertRaisesRegex(AssertionError, 'missing final imports.*bf_source_resolve'):
            self.verify()

    def test_stale_runtime_sidecar_is_rejected(self):
        self.build('MIDI FOLLOW')
        (self.runtime / 'runtime.bin').write_bytes(self.changed_runtime())
        with self.assertRaisesRegex(AssertionError, 'packaged runtime differs from runtime.bin'):
            self.verify()

    def test_corrupt_packaged_payload_is_rejected(self):
        self.build('MIDI FOLLOW')
        image_path = self.out / 'mainos_bus.bin'
        image = bytearray(image_path.read_bytes())
        blob = reference.symbols(self.platform / 'loader.elf')['blob']
        image[blob - IMAGE_BASE + 12] ^= 1
        image_path.write_bytes(image)
        with self.assertRaisesRegex(AssertionError, 'runtime packed hash'):
            self.verify()


if __name__ == '__main__':
    unittest.main()
