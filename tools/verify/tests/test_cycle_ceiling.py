"""cycle_count.bank_worst prices an insert at its declared max_per_core."""
import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import toolpath  # noqa: E402,F401
from build import cycle_count  # noqa: E402
from remix.schema import DspSection  # noqa: E402

ROWS = [{"name": "ins", "cycles": 1000}]


def mod(**kw):
    return dict(stem="ins", key="INS", server=False, fx1_only=False, **kw)


class CeilingTests(unittest.TestCase):
    def test_undeclared_is_four_copies(self):
        worst, picks = cycle_count.bank_worst(ROWS, [mod()])
        self.assertEqual((worst, picks), (4000, [("ins", 4)]))

    def test_declared_two_is_two_copies(self):
        worst, picks = cycle_count.bank_worst(ROWS, [mod(max_per_core=2)])
        self.assertEqual((worst, picks), (2000, [("ins", 2)]))

    def test_declared_above_four_slots_is_four(self):
        self.assertEqual(cycle_count.bank_worst(ROWS, [mod(max_per_core=4)])[0], 4000)

    def test_schema_range(self):
        for bad in (0, 5, -1):
            with self.assertRaises(ValueError):
                DspSection(asm="x.asm", priority=1, max_per_core=bad)
        for ok in (None, 1, 4):
            DspSection(asm="x.asm", priority=1, max_per_core=ok)


class SequentialLoopTests(unittest.TestCase):
    SOURCE = """init:
        rts
proc:
        do n7,>first
        nop
first:
        nop
        do n7,>second
        nop
        nop
second:
        nop
        rts
"""

    def test_modes_take_the_maximum(self):
        with patch.object(cycle_count, "prep", return_value=self.SOURCE):
            measured = cycle_count.measure("loop_fixture")
        self.assertEqual(measured["cycles"], 2)

    def test_sequential_passes_add(self):
        src = "; CYCLES_SEQUENTIAL_LOOPS\n" + self.SOURCE
        with patch.object(cycle_count, "prep", return_value=src):
            measured = cycle_count.measure("loop_fixture")
        self.assertEqual(measured["cycles"], 3)


if __name__ == "__main__":
    unittest.main()
