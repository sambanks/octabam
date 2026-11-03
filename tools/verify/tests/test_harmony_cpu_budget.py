"""The new consumer has explicit ceilings without weakening standalone Follow."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_midi_follow_cpu as cpu


class HarmonyCpuBudgetTests(unittest.TestCase):
    def test_standalone_limits_are_unchanged(self):
        limits, _ = cpu.instruction_budgets({})
        self.assertIs(limits, cpu.BUDGETS)

    def test_composed_case_sets_and_batch_limits(self):
        for extended, count in ((False, 79), (True, 143)):
            symbols = {'mh_pitch_owned': 1}
            if extended:
                symbols['ms_output'] = 2
            limits, _ = cpu.instruction_budgets(symbols)
            self.assertEqual(len(limits), count)
            self.assertTrue(all(value > 0 for value in limits.values()))
            for name, baseline in cpu.LIVE_BATCH_BASELINE.items():
                if name in limits:
                    self.assertLessEqual(limits[name], baseline * 8 // 10)

    def test_inactive_policy_cost_is_explicit(self):
        limits, _ = cpu.instruction_budgets({'mh_pitch_owned': 1})
        self.assertEqual(limits['off_tick.warm'], 1776)
        self.assertEqual(limits['note_key0_direct_FIXED_bf_note.warm.0'], 828)
        self.assertGreater(limits['live_seven_FIXED.unchanged'],
                           cpu.BUDGETS['live_seven_FIXED.unchanged'])


if __name__ == '__main__':
    unittest.main()
