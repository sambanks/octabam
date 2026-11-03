"""Harmony's optional companions must not become hidden dependencies."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from remix import registry


class HarmonySelectionTests(unittest.TestCase):
    def test_harmony_does_not_require_follow_or_scales(self):
        harmony = registry.modules()['MIDI HARMONY']
        self.assertNotIn('MIDI FOLLOW', harmony.requires)
        self.assertNotIn('MIDI SCALES', harmony.requires)

    def test_four_compositions_have_one_scale_reader_and_optional_pitch_policy(self):
        for name, follow, scales in (
                ('midi-harmony', False, False),
                ('harmony-scales-provider', False, True),
                ('harmony-follow-native-review', True, False),
                ('midi-harmony-follow', True, True)):
            with self.subTest(remix=name):
                remix = registry.remix(name)
                selected = registry.selected(remix)
                labels = [unit.label for module in selected for unit in module.linked]
                self.assertEqual(labels.count('midiscaleprovider'), 1)
                self.assertEqual(labels.count('midiscalemath'), 1)
                self.assertEqual('bassfollow' in labels, follow)
                self.assertEqual('harmonypitchresponse' in labels, follow)
                self.assertEqual('MIDI SCALES' in remix.modules, scales)
                self.assertTrue({'chordpart', 'midiharmony', 'midisram'} <= set(labels))


if __name__ == '__main__':
    unittest.main()
