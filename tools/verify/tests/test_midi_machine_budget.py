"""Firmware-free checks for explicit MIDI fixture profiles and call budgets."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

HAS_UNICORN = importlib.util.find_spec('unicorn') is not None
if HAS_UNICORN:
    import unicorn as un
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import midi_machine as midi
    import midi_scales_machine as scales


class InstructionBudgetCases:
    BASE = 0x40010000

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='midi-budget-')
        self.addCleanup(temporary.cleanup)
        self.artifacts = Path(temporary.name)
        runtime = self.artifacts / 'platform/runtime'
        runtime.mkdir(parents=True)
        # Authored synthetic code only: MOVEQ #7,D0; RTS; BRA to itself;
        # MOVEQ #42,D0; 32 NOPs; RTS; 32 NOPs; MOVEQ #99,D0; JMP to init stop.
        code = bytes.fromhex('7007 4e75 60fe 702a') + bytes.fromhex('4e71') * 32
        code += bytes.fromhex('4e75')
        self.init_address = self.BASE + len(code)
        code += bytes.fromhex('4e71') * 32 + bytes.fromhex('7063 4ef9 40025ace')
        (runtime / 'runtime.bin').write_bytes(code)
        (self.artifacts / 'mainos_bus.bin').write_bytes(bytes.fromhex('4e71'))
        (self.artifacts / 'platform/layout.json').write_text(json.dumps(
            dict(base=self.BASE, top=self.BASE + len(code),
                 stage_end=self.BASE + len(code), ceiling=0x41000000)))
        self.symbols = dict(quick=self.BASE, spin=self.BASE + 4, long=self.BASE + 6)

    def machine(self, **kwargs):
        return self.harness.Machine(lambda: self.symbols.copy(), artifact_root=self.artifacts,
                                    **kwargs)

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

    def test_module_initialization_is_explicit_and_uses_the_call_budget(self):
        self.symbols['mh_defaults'] = self.init_address
        machine = self.machine(instruction_budget=8)
        self.assertIsNone(machine.arrival)
        self.assertEqual(machine.uc.reg_read(un.m68k_const.UC_M68K_REG_D0), 0)
        with self.assertRaisesRegex(AssertionError, 'within 8 instructions'):
            machine.call('mh_defaults', stop=0x40025ace)
        self.assertEqual(machine.call('mh_defaults', stop=0x40025ace,
                                      instruction_budget=64), 99)
        self.assertEqual(machine.instruction_budget, 8)
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


@unittest.skipUnless(HAS_UNICORN, 'existing emu extra not installed')
class NativeMidiMachineTests(InstructionBudgetCases, unittest.TestCase):
    if HAS_UNICORN:
        harness = midi

    def test_profiles_are_independent_of_incidental_module_symbols(self):
        for names in ((), ('bf_source_get',), ('mh_defaults',),
                      ('bf_source_get', 'mh_defaults')):
            self.symbols = {name: self.init_address for name in names}
            for profile, expected_fields in ((None, (3, 2)), ('native', (3, 2)),
                                             ('follow', (35, 3))):
                with self.subTest(symbols=names, profile=profile):
                    machine = self.machine(**({} if profile is None else {'profile': profile}))
                    expected = bytearray(36)
                    expected[13], expected[15] = expected_fields
                    for part in range(4):
                        for track in range(8):
                            address = 0x400e21e0 + 0x8ed80 + part*0x18b2 + 0x4e2 + track*36
                            self.assertEqual(bytes(machine.uc.mem_read(address, 36)), bytes(expected))
                    # The incidental entry mutates D0 and reaches an explicit
                    # stop if executed; construction must run no guest code.
                    self.assertIsNone(machine.arrival)
                    self.assertEqual(machine.writes, [])
                    self.assertEqual(machine.uc.reg_read(un.m68k_const.UC_M68K_REG_PC), 0)
                    self.assertEqual(machine.uc.reg_read(un.m68k_const.UC_M68K_REG_D0), 0)

    def test_invalid_profile_is_rejected_before_loading_symbols_or_artifacts(self):
        loader = Mock(side_effect=AssertionError('symbol loader must not run'))
        for profile in ('folow', '', None, True):
            with self.subTest(profile=profile):
                with self.assertRaisesRegex(ValueError, 'unknown MIDI fixture profile'):
                    midi.Machine(loader, artifact_root=self.artifacts/'missing', profile=profile)
        loader.assert_not_called()


@unittest.skipUnless(HAS_UNICORN, 'existing emu extra not installed')
class ScalesMachineTests(InstructionBudgetCases, unittest.TestCase):
    if HAS_UNICORN:
        harness = scales


if __name__ == '__main__':
    unittest.main()
