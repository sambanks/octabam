"""Firmware-free project fixtures keep Follow defaults local to Follow gates."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tools/harness'), str(ROOT / 'tools/verify')]
from hw import ot_project as otp
from midi_fixture import fixture


class MidiFixtureProfiles(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        # Synthetic bank structure only: no firmware or user's project bytes.
        for bank in (1, 2):
            for suffix in ('work', 'strd'):
                data = bytearray(otp.PART_BASE + 8 * otp.PART_STRIDE + 30)
                for pattern in range(16):
                    for track in range(8):
                        at = 0x492e + pattern * 0x8eec + track * 0x8b9
                        data[at:at+4] = b'MTRA'
                for part in range(8):
                    for track in range(8):
                        at = self.setup_offset(part, track)
                        data[at:at+36] = bytes([77]) * 36
                        # Includes stock keys and extended Scales keys, in both
                        # working/saved Parts and the two bank-file variants.
                        data[at+17] = (0, 1, 2, 25, 26)[(bank + part + track + (suffix == 'strd')) % 5]
                data[-2:] = (sum(data[0x10:-2]) & 0xffff).to_bytes(2, 'big')
                (self.source / f'bank{bank:02d}.{suffix}').write_bytes(data)
        self.originals = {p.name: p.read_bytes() for p in self.source.iterdir()}

    @staticmethod
    def setup_offset(part, track):
        return otp.PART_BASE + part * otp.PART_STRIDE + 9 + 0x4e2 + track * 36

    def test_default_preserves_template_keys_and_legacy_fields(self):
        dest = self.root / 'native'
        fixture(self.source, dest)
        for name, original in self.originals.items():
            data = (dest / name).read_bytes()
            for part in range(8):
                for track in range(8):
                    at = self.setup_offset(part, track)
                    self.assertEqual(data[at+17], original[at+17], (name, part, track))
                    self.assertEqual((data[at+13], data[at+15]), (3, 2))
                    for field in (3, 5, 12, 16, 18, 19):
                        self.assertEqual(data[at+field], 0)
                    self.assertEqual(data[at+14], 77)  # unrelated SETUP byte
            self.assertEqual(int.from_bytes(data[-2:], 'big'), sum(data[0x10:-2]) & 0xffff)
            self.assertEqual((self.source / name).read_bytes(), original)

    def test_follow_changes_only_its_defaults_and_key(self):
        native, follow = self.root / 'native', self.root / 'follow'
        fixture(self.source, native, arp=True, leader=7, offsets={3: -2}, voices=True)
        fixture(self.source, follow, arp=True, leader=7, offsets={3: -2}, voices=True, profile='follow')
        for name in self.originals:
            before, after = (native / name).read_bytes(), (follow / name).read_bytes()
            allowed = {len(after)-2, len(after)-1}  # changed bank checksum
            for part in range(8):
                for track in range(8):
                    at = self.setup_offset(part, track)
                    allowed.update(at + field for field in (13, 15, 17))
                    self.assertEqual((after[at+13], after[at+15], after[at+17]), (35, 3, 0))
            changed = {i for i, (a, b) in enumerate(zip(before, after)) if a != b}
            self.assertTrue(changed <= allowed, (name, changed - allowed))
            self.assertEqual(len(before), len(after))
            self.assertEqual(int.from_bytes(after[-2:], 'big'), sum(after[0x10:-2]) & 0xffff)

    def test_invalid_profile_does_not_replace_existing_destination(self):
        dest = self.root / 'existing'
        dest.mkdir()
        marker = dest / 'keep.txt'
        marker.write_text('untouched')
        with self.assertRaisesRegex(ValueError, 'unknown MIDI fixture profile'):
            fixture(self.source, dest, profile='folow')
        self.assertEqual(marker.read_text(), 'untouched')


if __name__ == '__main__':
    unittest.main()
