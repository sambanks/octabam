"""The link map's object lines must parse when the checkout path has a space."""
import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from remix.platform_build import _map_sections
MAP = """\
 .text          0x40a00000      0x120 /Volumes/Data Disk/octabam/out/work/00_brain.o
 .data          0x40a00120       0x10 /Volumes/Data Disk/octabam/out/work/00_brain.o
 .text          0x40a00130       0x40 /tmp/octabam/out/work/01_tuner.o
 *(.text)
"""
class MapSectionsTests(unittest.TestCase):
    def parse(self, text):
        with tempfile.TemporaryDirectory() as d:
            m = pathlib.Path(d) / "link.map"
            m.write_text(text)
            return _map_sections(m)
    def test_path_with_space(self):
        out = self.parse(MAP)
        self.assertEqual(out[("/Volumes/Data Disk/octabam/out/work/00_brain.o", ".text")],
                         (0x40a00000, 0x120))
        self.assertEqual(out[("/Volumes/Data Disk/octabam/out/work/00_brain.o", ".data")],
                         (0x40a00120, 0x10))
    def test_path_without_space(self):
        self.assertEqual(self.parse(MAP)[("/tmp/octabam/out/work/01_tuner.o", ".text")],
                         (0x40a00130, 0x40))
    def test_trailing_whitespace(self):
        out = self.parse(" .text  0x10  0x4 /a b/c.o   \n")
        self.assertEqual(out[("/a b/c.o", ".text")], (0x10, 0x4))
if __name__ == "__main__":
    unittest.main()
