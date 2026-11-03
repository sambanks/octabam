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

    def test_loopback_cost_is_scoped_to_its_composition(self):
        base, _ = cpu.instruction_budgets({'mh_pitch_owned': 1, 'ms_output': 2})
        routed, basis = cpu.instruction_budgets({'mh_pitch_owned': 1, 'ms_output': 2,
                                                'lb_track_send': 3})
        self.assertEqual(set(routed), set(base))
        self.assertIn('Loopback EXT', basis)
        self.assertEqual(routed['off_tick.warm'], base['off_tick.warm'])
        self.assertEqual(routed['live_seven_GRAV.unchanged'], base['live_seven_GRAV.unchanged'])
        self.assertEqual(routed['live_direct_GRAV.moved4'] - base['live_direct_GRAV.moved4'], 944)
        self.assertEqual(routed['live_seven_GRAV.moved4'] - base['live_seven_GRAV.moved4'], 6608)
        unchanged, _ = cpu.instruction_budgets({'mh_pitch_owned': 1, 'ms_output': 2})
        self.assertEqual(unchanged, base)

    def test_unmeasured_loopback_composition_is_not_silently_accepted(self):
        with self.assertRaisesRegex(AssertionError, 'measured EXT instruction profile'):
            cpu.instruction_budgets({'mh_pitch_owned': 1, 'lb_track_send': 3})

    def test_inactive_policy_cost_is_explicit(self):
        limits, _ = cpu.instruction_budgets({'mh_pitch_owned': 1})
        self.assertEqual(limits['off_tick.warm'], 1776)
        self.assertEqual(limits['note_key0_direct_FIXED_bf_note.warm.0'], 828)
        self.assertGreater(limits['live_seven_FIXED.unchanged'],
                           cpu.BUDGETS['live_seven_FIXED.unchanged'])


if __name__ == '__main__':
    unittest.main()
