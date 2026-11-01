"""Firmware-free checks that MIDI CPU gates stop within their explicit budget."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HAS_UNICORN = importlib.util.find_spec('unicorn') is not None
if HAS_UNICORN:
    import unicorn as un
    spec = importlib.util.spec_from_file_location(
        'midi_machine', Path(__file__).resolve().parents[1] / 'midi_machine.py')
    midi = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(midi)


@unittest.skipUnless(HAS_UNICORN, 'existing emu extra not installed')
class InstructionBudgetTests(unittest.TestCase):
    BASE = 0x40010000

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='midi-budget-')
        self.addCleanup(temporary.cleanup)
        self.artifacts = Path(temporary.name)
        runtime = self.artifacts / 'platform/runtime'
        runtime.mkdir(parents=True)
        # Authored synthetic code only: MOVEQ #7,D0; RTS; BRA to itself;
        # MOVEQ #42,D0; 32 NOPs; RTS; 32 NOPs; JMP to the fixture init stop.
        code = bytes.fromhex('7007 4e75 60fe 702a') + bytes.fromhex('4e71') * 32
        code += bytes.fromhex('4e75')
        self.init_address = self.BASE + len(code)
        code += bytes.fromhex('4e71') * 32 + bytes.fromhex('4ef9 40025ace')
        (runtime / 'runtime.bin').write_bytes(code)
        (self.artifacts / 'mainos_bus.bin').write_bytes(bytes.fromhex('4e71'))
        (self.artifacts / 'platform/layout.json').write_text(json.dumps(
            dict(base=self.BASE, top=self.BASE + len(code),
                 stage_end=self.BASE + len(code), ceiling=0x41000000)))
        self.symbols = dict(quick=self.BASE, spin=self.BASE + 4, long=self.BASE + 6)

    def machine(self, **kwargs):
        return midi.Machine(lambda: self.symbols.copy(), artifact_root=self.artifacts, **kwargs)

    def counted_call(self, machine, name, expected_count, **kwargs):
        executed = []
        hook = machine.uc.hook_add(un.UC_HOOK_CODE,
                                   lambda _cpu, pc, _size, _data: executed.append(pc))
        try:
            with self.assertRaisesRegex(AssertionError, 'did not reach its stop within'):
                machine.call(name, **kwargs)
        finally:
            machine.uc.hook_del(hook)
        self.assertEqual(len(executed), expected_count)

    def test_default_budget_is_bounded_and_independent_of_harmony_symbols(self):
        for harmony_symbols in (False, True):
            with self.subTest(harmony_symbols=harmony_symbols):
                if harmony_symbols:
                    self.symbols['hd_set'] = self.BASE
                machine = self.machine()
                self.counted_call(machine, 'spin', 20_000)
                self.assertEqual(machine.call('quick'), 7)

    def test_machine_budget_stops_a_loop_and_allows_a_completed_call(self):
        machine = self.machine(instruction_budget=8)
        self.counted_call(machine, 'spin', 8)
        self.assertEqual(machine.call('quick'), 7)

    def test_call_override_does_not_change_the_machine_budget(self):
        machine = self.machine(instruction_budget=8)
        self.counted_call(machine, 'long', 8)
        self.assertEqual(machine.call('long', instruction_budget=64), 42)
        self.counted_call(machine, 'spin', 3, instruction_budget=3)
        self.counted_call(machine, 'long', 8)

    def test_constructor_initialization_uses_the_explicit_budget(self):
        self.symbols['mh_defaults'] = self.init_address
        with self.assertRaisesRegex(AssertionError, 'within 8 instructions'):
            self.machine(instruction_budget=8)
        machine = self.machine(instruction_budget=64)
        self.assertEqual(machine.call('quick'), 7)

    def test_unlimited_and_invalid_budgets_are_rejected(self):
        machine = self.machine()
        before = bytes(machine.uc.context_save())
        for budget in (0, -1, True, 1.5, '20000'):
            with self.subTest(budget=budget):
                with self.assertRaisesRegex(ValueError, 'positive integer'):
                    self.machine(instruction_budget=budget)
                with self.assertRaisesRegex(ValueError, 'positive integer'):
                    machine.call('spin', instruction_budget=budget)
                self.assertEqual(bytes(machine.uc.context_save()), before)


if __name__ == '__main__':
    unittest.main()
