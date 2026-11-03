"""Harmony's optional companions must not become hidden dependencies."""
import pathlib
import runpy
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
        self.assertEqual(harmony.requires, ('STORE', 'EVENTS'))
        self.assertNotIn('MIDI SRAM', registry.modules())

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
                self.assertNotIn('MIDI SRAM', remix.modules)
                store = next(m for m in selected if m.key == 'STORE')
                self.assertEqual([u.label for u in store.linked].count('midisram'), 1)
                self.assertEqual([u.label for u in store.linked].count('midisramcopy'), 1)
                source = ROOT / 'modules/midi-harmony/upstream/modules/midi-sram/manifest.py'
                author = runpy.run_path(str(source))['MODULE']
                self.assertEqual(store.claims.sram, author.claims.sram)
                self.assertEqual(len(store.claims.sram), 8192)
                for unit in author.linked:
                    self.assertIn(unit, store.linked)
                for poke in author.pokes:
                    self.assertIn(poke, store.pokes)
                for gate in author.gates:
                    self.assertIn(gate, store.gates)

    def test_other_store_clients_do_not_install_retained_storage(self):
        for name in ('octabam', 'events-clients', 'midi-follow', 'midi-follow-events', 'midi-loopback'):
            with self.subTest(remix=name):
                selected = registry.selected(registry.remix(name))
                labels = {u.label for m in selected for u in m.linked}
                self.assertFalse({'midisram', 'midisramcopy'} & labels)
                store = next(m for m in selected if m.key == 'STORE')
                self.assertTrue(store.claims is None or not store.claims.sram)
                self.assertNotIn('tools/verify/verify_midi_sram.py', {g.script for g in store.gates})
                self.assertNotIn(0x4002adc8, {p.addr for p in store.pokes})


if __name__ == '__main__':
    unittest.main()
