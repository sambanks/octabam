"""Retained storage registrations must work without musical-module knowledge."""
import pathlib
import runpy
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'tools'))


class StoreRetainedTests(unittest.TestCase):
    def setUp(self):
        self.parts = runpy.run_path(str(ROOT/'modules/store/parts.py'))
        self.retained = self.parts['_RETAINED']

    def test_zero_one_and_multiple_clients(self):
        clients = {'A': (11, 0, 128), 'B': (4, 128, 37)}
        layout = self.retained['layout']
        self.assertEqual(layout(set(), clients), ())
        self.assertEqual(layout({'A'}, clients), (('A', 11, 0, 128),))
        self.assertEqual(layout({'A', 'B'}, clients), (('B', 4, 128, 37), ('A', 11, 0, 128)))
        self.assertEqual(self.retained['additions'](set()), dict(linked=(), pokes=(), gates=(), sram=()))

    def test_conflicts_and_invalid_reservations(self):
        for clients in ({'X': (1, -1, 1)}, {'X': (1, 16384, 1)}, {'X': (1, 0, 0)},
                        {'X': (-1, 0, 1)}, {'X': (True, 0, 1)}, {'X': (1, 0, 0xffffffff)},
                        {'A': (1, 0, 1), 'B': (1, 2, 1)}):
            with self.subTest(clients=clients), self.assertRaises(ValueError):
                self.retained['layout'](set(clients), clients)
        clients = {'A': (1, 0, 128), 'B': (2, 127, 1)}
        self.assertEqual(len(self.retained['layout']({'A'}, clients)), 1)
        with self.assertRaisesRegex(ValueError, 'overlap'):
            self.retained['layout'](set(clients), clients)

    def test_existing_harmony_layout_and_sparse_backing_are_preserved(self):
        self.assertEqual(self.retained['RETAINED_CLIENTS']['MIDI HARMONY'], (0, 0, 16384))
        claims = self.retained['additions']({'MIDI HARMONY'})['sram']
        expected = {(0x1001614e + p*0x8ed8 + 0x4900 + t*0x8b0 + s*32 + 30, 2)
                    for p in range(16) for t in range(8) for s in range(64)}
        self.assertEqual({(start, size) for start, size, _ in claims}, expected)
        clients = dict(self.retained['RETAINED_CLIENTS'], OTHER=(3, 0, 2))
        with self.assertRaisesRegex(ValueError, 'overlap'):
            self.retained['layout'](set(clients), clients)

    def test_retained_only_client_installs_native_service_without_part_fields(self):
        self.retained['RETAINED_CLIENTS'].clear()
        self.retained['RETAINED_CLIENTS'].update({'PROBE': (9, 100, 8)})
        self.assertEqual(self.parts['layout']({'PROBE'})[0], ())
        self.assertTrue(self.parts['enabled']({'PROBE'}))
        self.assertIn('jmp store_retained_copy', self.parts['part_inc']({'PROBE'}))
        self.assertTrue(self.parts['additions']({'PROBE'})['detours'])
        support = self.retained['additions']({'PROBE'})
        self.assertEqual(len(support['sram']), 8192)
        self.assertEqual(len(support['pokes']), 8)
        self.assertTrue(all(u.source.startswith('modules/store/') for u in support['linked']))
        self.assertIn('.long 9,100,8', self.retained['retained_inc']({'PROBE'}))

    def test_retained_only_activation_composes_with_boot_trace(self):
        hooks = runpy.run_path(str(ROOT/'modules/hooks/manifest.py'))
        retained = hooks['_STORE_PARTS']['_RETAINED']
        retained['RETAINED_CLIENTS'].clear()
        retained['RETAINED_CLIENTS'].update({'PROBE': (9, 100, 8)})
        self.assertIn('boot', hooks['bridged']({'STORE', 'BOOT TRACE', 'PROBE'}))
        self.assertNotIn('boot', hooks['bridged']({'STORE', 'BOOT TRACE'}))


if __name__ == '__main__':
    unittest.main()
