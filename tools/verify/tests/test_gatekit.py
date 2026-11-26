"""gatekit writes the check lines the runners read, and reads the runtime map.
tools/verify/gatekit.py; the regexes are acceptance.py's own."""
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/verify"))
sys.path.insert(0, str(ROOT / "tools"))
import acceptance  # noqa: E402
import gatekit  # noqa: E402


class Lines(unittest.TestCase):
    def gate(self, **kw):
        lines = []
        return gatekit.Gate(out=lines.append, **kw), lines

    def test_pass_and_fail_lines(self):
        g, lines = self.gate()
        self.assertTrue(g.check("loads", 1, "crc 0x1"))
        self.assertFalse(g.check("plays", 0))
        self.assertEqual(lines, ["  [PASS] loads -- crc 0x1", "  [FAIL] plays"])
        self.assertEqual((g.fails, g.checks, g.exit_code()), (["plays"], 2, 1))

    def test_the_runners_see_a_failure_and_a_skip(self):
        g, lines = self.gate()
        g.check("a", True)
        text = "\n".join(lines)
        self.assertIsNone(acceptance.FAIL.search(text))
        g.check("b", False, "detail")
        g.skip("c", "no project")
        text = "\n".join(lines)
        self.assertIsNotNone(acceptance.FAIL.search(text))
        self.assertIsNotNone(acceptance.SKIP.search(text))

    def test_na_is_neither(self):
        g, lines = self.gate()
        g.na("FX2 path", "FX1 only")
        text = "\n".join(lines)
        self.assertIsNone(acceptance.FAIL.search(text))
        self.assertIsNone(acceptance.SKIP.search(text))
        self.assertIsNotNone(acceptance.NA.search(text))
        self.assertEqual(g.exit_code(), 0)

    def test_detail_only_on_failure(self):
        g, lines = self.gate(detail_on_pass=False)
        g.check("a", True, "hidden")
        g.check("b", False, "shown")
        self.assertEqual(lines, ["  [PASS] a", "  [FAIL] b -- shown"])


class RuntimeSymbol(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.map = pathlib.Path(self.dir.name) / "runtime.map"
        self.map.write_text(" .text          0x47f00000     0x1234 runtime.o\n"
                            "                0x47f00010                dr_state\n"
                            "                0x47f00200                dr_step\n")

    def tearDown(self):
        self.dir.cleanup()

    def test_found(self):
        self.assertEqual(gatekit.runtime_symbol("dr_step", "t", self.map), 0x47f00200)

    def test_missing_ends_the_gate_or_is_none(self):
        with self.assertRaises(SystemExit) as c:
            gatekit.runtime_symbol("nope", "verify_x", self.map, hint=" (build the image first)")
        self.assertEqual(str(c.exception), "verify_x: nope not in the runtime map (build the image first)")
        self.assertIsNone(gatekit.runtime_symbol("nope", "t", self.map, need=False))

    def test_a_section_line_is_not_a_symbol(self):
        self.assertIsNone(gatekit.runtime_symbol(".text", "t", self.map, need=False))


if __name__ == "__main__":
    unittest.main()
