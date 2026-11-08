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
                self.assertTrue({'chordpart', 'midiharmony', 'storeretained'} <= set(labels))
                self.assertNotIn('MIDI SRAM', remix.modules)
                store = next(m for m in selected if m.key == 'STORE')
                self.assertEqual([u.label for u in store.linked].count('storeretained'), 1)
                self.assertEqual([u.label for u in store.linked].count('storeretainedcopy'), 1)
                self.assertEqual(len(store.claims.sram), 8192)
                self.assertTrue(all('midi-harmony/upstream' not in u.source for u in store.linked))
                self.assertIn('storeretainedclients', labels)
                self.assertIn('tools/verify/verify_store_retained.py', {g.script for g in store.gates})

    def test_combined_midi_remix_and_test_only_controls(self):
        remix = registry.remix('midi')
        self.assertTrue({'MIDI HARMONY', 'MIDI FOLLOW', 'MIDI SCALES',
                         'MIDI LOOPBACK', 'STORE', 'EVENTS'} <= set(remix.modules))
        self.assertEqual(registry.remix_dir('midi'), ROOT / 'remixes/midi')
        for name in ('midi-harmony', 'midi-harmony-follow',
                     'harmony-scales-provider', 'harmony-follow-native-review'):
            self.assertEqual(registry.remix_dir(name).parent, ROOT / 'remixes/test')
        selected = registry.selected(remix)
        labels = [unit.label for module in selected for unit in module.linked]
        for label in ('midiscaleprovider', 'midiscalemath', 'storeretained', 'storeretainedcopy'):
            self.assertEqual(labels.count(label), 1)
        fields = runpy.run_path(str(ROOT / 'modules/store/parts.py'))
        inc = fields['part_inc'](set(remix.modules))
        self.assertIn('jmp store_retained_copy', inc)
        self.assertEqual(fields['layout'](set(remix.modules))[1], ((0x4e2, 288),))

    def test_chords_factory_is_refused_before_linking(self):
        # Both modules replace the native MIDI trig modes and export ch_*.
        from remix import ledger
        modules = registry.modules()
        problems = ledger.check([modules['MIDI HARMONY'], modules['CHORDS FACTORY']])
        self.assertTrue(any('declared conflict' in p and 'chords' in p.lower()
                            for p in problems), problems)

    def test_other_store_clients_do_not_install_retained_storage(self):
        for name in ('octabam', 'events-clients', 'midi-follow', 'midi-follow-events', 'midi-loopback'):
            with self.subTest(remix=name):
                selected = registry.selected(registry.remix(name))
                labels = {u.label for m in selected for u in m.linked}
                self.assertFalse({'storeretained', 'storeretainedcopy'} & labels)
                store = next(m for m in selected if m.key == 'STORE')
                self.assertTrue(store.claims is None or not store.claims.sram)
                self.assertNotIn('tools/verify/verify_store_retained.py', {g.script for g in store.gates})
                self.assertNotIn(0x4002adc8, {p.addr for p in store.pokes})


if __name__ == '__main__':
    unittest.main()
