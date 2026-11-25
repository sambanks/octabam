"""Playing-mode registrations compose independently of musical modules."""
def replace(record, **changes):
    return record._replace(**changes)
from pathlib import Path
import runpy
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))


class TrigModesTests(unittest.TestCase):
    def setUp(self):
        ns = runpy.run_path(str(ROOT / 'modules/trig-modes/manifest.py'))
        self.ns = ns['registrations'].__globals__
        Mode = ns['Mode']
        self.a = Mode('PROBE A', 2, 'PROBE A', 30, 'a_key', 'a_leds', 'a_release')
        self.b = Mode('PROBE B', 9, 'PROBE B', 20, 'b_key', 'b_leds', 'b_release')
        self.ns['CLIENTS'] = (self.a, self.b)

    def test_zero_one_two_clients_and_sparse_ids(self):
        self.assertEqual(self.ns['rows'](set()), (0, 1, 4))
        self.assertEqual(self.ns['rows']({'PROBE A'}), (0, 1, 2, 4))
        self.assertEqual(self.ns['rows']({'PROBE B'}), (0, 1, 9, 4))
        self.assertEqual(self.ns['rows']({'PROBE A', 'PROBE B'}), (0, 1, 9, 2, 4))
        self.assertEqual(self.ns['select'](set()), dict(linked=(), detours=(), pokes=(), symbol_refs=()))

    def test_invalid_absent_clients_are_not_hidden(self):
        for bad in (replace(self.b, number=2), replace(self.b, number=1),
                    replace(self.b, number=True), replace(self.b, number=32),
                    replace(self.b, module='PROBE A'), replace(self.b, key='a_key'),
                    replace(self.b, leds=''), replace(self.b, title='BAD" TITLE'),
                    replace(self.b, icon=6), replace(self.b, order=100)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.ns['CLIENTS'] = (self.a, bad)
                self.ns['registrations'](set())

    def test_menu_capacity_is_checked(self):
        self.ns['CLIENTS'] = tuple(replace(self.a, module=f'PROBE {i}', number=6+i,
                                          key=f'p{i}_key', leds=f'p{i}_leds', release=f'p{i}_release')
                                    for i in range(4))
        with self.assertRaisesRegex(ValueError, 'six rows'):
            self.ns['select']({m.module for m in self.ns['CLIENTS']})


if __name__ == '__main__':
    unittest.main()
