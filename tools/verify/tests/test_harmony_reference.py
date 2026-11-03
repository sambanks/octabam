"""Final placement and source mismatches must be visible in the packaged oracle."""
import contextlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_midi_scales_reference as fixtures
TOOLS, RUNTIME_BASE = fixtures.TOOLS, fixtures.RUNTIME_BASE
import verify_harmony_reference as reference
from remix import platform_build
from remix.schema import Linked


@unittest.skipUnless(TOOLS, 'needs the m68k-elf toolchain')
class HarmonyReferenceTests(unittest.TestCase):
    setUp = fixtures.PackagedReferenceTests.setUp
    run_tool = fixtures.PackagedReferenceTests.run_tool
    package = fixtures.PackagedReferenceTests.package

    def build(self):
        self.platform.mkdir()
        src = self.out / 'unit.s'
        src.write_text('.text\n.global harmony_probe\nharmony_probe:\n'
                       'lea state,%a0\nmove.l constant,%d0\njsr provider\nrts\n'
                       '.section .rodata\nconstant: .long 12345\n'
                       '.bss\n.balign 4\nstate: .space 64\n')
        provider = self.out / 'provider.s'
        provider.write_text('.text\n.global provider\nprovider: rts\n'
                            '.section .rodata\n.space 24\n.bss\n.space 128\n')
        self.unit = Linked('harmonyprobe', str(src), dram=True)
        raw, self.exports, _, _ = platform_build.link_runtime(
            [('PROVIDER', Linked('provider', str(provider), dram=True)),
             ('HARMONY PROBE', self.unit)], self.runtime, {}, RUNTIME_BASE)
        (self.platform / 'layout.json').write_text(json.dumps({'base': RUNTIME_BASE}))
        self.package(raw)
        return raw

    def verify(self):
        with patch.object(reference, 'author_modules', return_value=[SimpleNamespace(linked=(self.unit,))]):
            with contextlib.redirect_stdout(io.StringIO()):
                reference.verify(SimpleNamespace(modules=('MIDI HARMONY',)), self.out)

    def test_text_and_constants_use_final_data_and_bss_placement(self):
        self.build()
        self.verify()

    def test_consistently_repacked_changed_code_is_rejected(self):
        raw = bytearray(self.build())
        raw[self.exports['harmony_probe'] - RUNTIME_BASE + 2] ^= 1
        (self.runtime / 'runtime.bin').write_bytes(raw)
        self.package(raw)
        with self.assertRaisesRegex(AssertionError, 'packaged source mismatch'):
            self.verify()

    def test_changed_author_constant_is_rejected(self):
        self.build()
        src = Path(self.unit.source)
        src.write_text(src.read_text().replace('12345', '12346'))
        with self.assertRaisesRegex(AssertionError, 'packaged source mismatch'):
            self.verify()

    def test_stale_sidecar_is_rejected(self):
        raw = bytearray(self.build())
        raw[0] ^= 1
        (self.runtime / 'runtime.bin').write_bytes(raw)
        with self.assertRaisesRegex(AssertionError, 'packaged runtime differs'):
            self.verify()


if __name__ == '__main__':
    unittest.main()
