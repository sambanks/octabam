"""module_gates: once-per-run gates and the shared half's carrier choice;
reach: the port stamp decides staleness by content."""
import os
import pathlib
import sys
import tempfile
import types
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import module_gates  # noqa: E402
import reach  # noqa: E402
from remix.schema import Gate  # noqa: E402


def module(key, *gates):
    return types.SimpleNamespace(key=key, gates=gates)


class PortRequired(unittest.TestCase):
    def test_no_port_binary_is_not_built(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            self.assertFalse(module_gates.port_built(d))
            (d / "out/emu").mkdir(parents=True)
            (d / "out/emu/ot_emu").write_text("bin")
            self.assertTrue(module_gates.port_built(d))


class OnceGates(unittest.TestCase):
    def test_once_needs_remix_arg_and_the_isolated_stage(self):
        Gate("tools/verify/x.py", once=True)
        with self.assertRaises(ValueError):
            Gate("tools/verify/x.py", once=True, remix_arg=False)
        with self.assertRaises(ValueError):
            Gate("tools/verify/x.py", once=True, stage="image")

    def test_collect_splits_once_from_per_remix(self):
        per = Gate("tools/verify/per.py")
        once = Gate("tools/verify/once.py", once=True)
        shared = Gate("tools/verify/shared.py", remix_arg=False)
        mods = [module("A", per, once), module("B", shared)]
        self.assertEqual([g.script for _, g in module_gates.collect(mods, "isolated", once=True)], [once.script])
        self.assertEqual([g.script for _, g in module_gates.collect(mods, "isolated", True, False)], [per.script])
        self.assertEqual([g.script for _, g in module_gates.collect(mods, "isolated", remix_arg=False)], [shared.script])
        self.assertEqual(len(module_gates.collect(mods, "isolated")), 3)

    def test_carrier_is_the_smallest_remix_carrying_the_module(self):
        big = types.SimpleNamespace(name="big")
        small = types.SimpleNamespace(name="small")
        other = types.SimpleNamespace(name="other")
        sel = {"big": [module("K"), module("X"), module("Y")], "small": [module("K"), module("X")],
               "other": [module("X")]}
        pick = module_gates.carrier("K", [big, other, small], selected=lambda r: sel[r.name])
        self.assertIs(pick, small)

    def test_a_probe_remix_carries_only_when_nothing_else_does(self):
        """#1124: `cfmeter` (family probes) was the smallest carrier of SCALE QUANTIZER, and its gate failed there."""
        probe = types.SimpleNamespace(name="probe", family="probes")
        big = types.SimpleNamespace(name="big", family="octabam")
        sel = {"probe": [module("K")], "big": [module("K"), module("X"), module("Y")]}
        self.assertIs(module_gates.carrier("K", [probe, big], selected=lambda r: sel[r.name]), big)
        self.assertIs(module_gates.carrier("K", [probe], selected=lambda r: sel[r.name]), probe)


class PortStamp(unittest.TestCase):
    def test_stamp_matches_content_not_mtime(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            src = d / "src"; src.mkdir(); (src / "a.cpp").write_text("int main(){}\n")
            exe = d / "ot_emu"; exe.write_bytes(b"\0")
            stamp = d / "stamp"
            reach.stamp_port(src, stamp)
            (src / "a.cpp").touch()                       # newer than the binary, same bytes
            self.assertFalse(reach.port_is_stale(exe, src, stamp))
            (src / "a.cpp").write_text("int main(){return 1;}\n")
            self.assertTrue(reach.port_is_stale(exe, src, stamp))

    def test_without_a_stamp_mtime_decides(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            src = d / "src"; src.mkdir(); (src / "a.cpp").write_text("x")
            exe = d / "ot_emu"; exe.write_bytes(b"\0")
            os.utime(exe, (0, 0))                          # an old binary; a touch can land in the same tick (CI)
            self.assertTrue(reach.port_is_stale(exe, src, d / "no-stamp"))


class Reached(unittest.TestCase):
    def test_a_change_reaches_the_modules_coupled_to_it(self):
        from remix import registry
        sel = registry.selected(registry.remix("octabam-bus"))
        self.assertEqual(module_gates.reached({"RIG HOSTS"}, sel), {"RIG HOSTS"})
        self.assertIn("MODE DEFAULTS", module_gates.reached({"CC MAP"}, sel))      # links its CC_MODEDEF1/2
        self.assertTrue({"STORE", "SCENES P2", "PLOCKS P2"} <= module_gates.reached({"KITS"}, sel))
        self.assertTrue({"REVERB SERVER", "SEND"} <= module_gates.reached({"DELAY SERVER"}, sel))   # the bus


class Ledger(unittest.TestCase):
    def test_first_fail_takes_the_fail_line(self):
        import gate_ledger
        self.assertEqual(gate_ledger.first_fail("a\n  [ok] b\n  [FAIL] c: d\n  [FAIL] e\n"), "[FAIL] c: d")
        self.assertEqual(gate_ledger.first_fail("a\nlast line\n\n"), "last line")
        self.assertEqual(gate_ledger.first_fail(""), "")


if __name__ == "__main__":
    unittest.main()
