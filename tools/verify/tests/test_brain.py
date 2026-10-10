"""Settings declarations, layer 1 and 2 resolution, the remix refusals and
the lock file (docs/proposals/BRAIN.md sections 2 and 4), on fixture
modules; no firmware."""
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from remix import brain  # noqa: E402
from remix.schema import (BRAIN_KEY, Apply, Binary, Blob, Claims, Kind, Linked,  # noqa: E402
                          ModeView, Module, Number, Option, Param, Pin, Remix, Scope,
                          Setting, Store, Trigger)

OUT = Setting(1, "OUT", Option("MAIN", "MAIN+CUE", "MASTER", "TRACKS"), apply=Apply.BUILD)
IN = Setting(2, "IN", Option("OFF", "AB", "CD", "ABCD"), apply=Apply.NEXT_BOOT, early=True)


def mod(name="usb", settings=(OUT, IN), store_id="octabam.usb", **kw):
    return Module(name=name, key=name.upper(), kind=Kind.CF_PATCH, doc="fixture",
                  store=Store(store_id) if store_id else None, settings=settings, **kw)


def core():
    return Module(name="brain", key=BRAIN_KEY, kind=Kind.CF_PATCH, doc="fixture")


def remix(*mods, **kw):
    return Remix(name="r", doc="fixture", modules=tuple(m.key for m in mods),
                 fallback="NONE", **kw)


def keyed(n_drawn=12, keys=None):
    keys = keys or list(range(1, 13))
    return tuple(Param(b"K%d" % i, 0, 128, active=i < n_drawn,
                       key=keys[i] if i < len(keys) else None) for i in range(12))


class Declarations(unittest.TestCase):
    def test_defaults_take_the_kinds_zero(self):
        self.assertEqual(Setting(1, "A", Binary()).default, 0)
        self.assertEqual(Setting(1, "A", Number(5, 9)).default, 5)
        self.assertEqual(Setting(1, "A", Number(-9, -5)).default, -5)
        self.assertEqual(Setting(1, "A", Blob(4)).default, b"")
        self.assertIsNone(Setting(1, "A", Trigger()).default)
        self.assertEqual(Setting(1, "A", Option("X", "Y"), default="Y").default, 1)

    def test_refusals(self):
        bad = [
            lambda: Setting(0, "A", Binary()),
            lambda: Setting(1, "", Binary()),
            lambda: Setting(1, "A", "binary"),
            lambda: Setting(1, "A", Option("X"), default="Z"),
            lambda: Setting(1, "A", Number(0, 10, step=2), default=3),
            lambda: Setting(1, "A", Number(0, 10), default=11),
            lambda: Setting(1, "A", Blob(2), default=b"abc"),
            lambda: Setting(1, "A", Binary(), scope=Scope.PROJECT, early=True),
            lambda: Setting(1, "A", Blob(2), early=True),
            lambda: Setting(1, "A", Trigger(), apply=Apply.BUILD),
            lambda: Option("X", "X"),
            lambda: Option(),
            lambda: Number(5, 1),
            lambda: Store("Bad Id"),
            lambda: Store("x" * 64),
            lambda: Param(b"A", key=0),
            lambda: mod(store_id=None),
            lambda: mod(settings=(OUT, Setting(1, "OTHER", Binary()))),
            lambda: mod(settings=(OUT, Setting(9, "OUT", Binary()))),
            lambda: mod(params=keyed(keys=[1, 1] + list(range(3, 13)))),
            lambda: mod(params=keyed(keys=list(range(1, 6)))),
        ]
        for i, f in enumerate(bad):
            with self.subTest(i):
                self.assertRaises(ValueError, f)

    def test_sizes(self):
        self.assertEqual([Setting(1, "A", k).size for k in
                          (Binary(), Option("X"), Number(0, 1), Trigger(), Blob(9))],
                         [1, 1, 2, 0, 9])

    def test_undrawn_slots_need_no_key(self):
        mod(params=keyed(n_drawn=5, keys=[1, 2, 3, 4, 5]))


class Resolution(unittest.TestCase):
    def setUp(self):
        self.usb, self.core = mod(), core()
        self.mods = {m.key: m for m in (self.usb, self.core)}

    def rows(self, r):
        self.assertEqual(brain.check_remix(r, self.mods), [])
        return {res.name: (res.value, res.layer, res.runtime) for res, _s in brain.resolve(r, self.mods)}

    def test_layers_without_the_core(self):
        r = remix(self.usb, settings={("octabam.usb", "OUT"): Pin("MASTER"),
                                      ("octabam.usb", "IN"): "CD"})
        self.assertEqual(self.rows(r), {"OUT": (2, "pin", False), "IN": (2, "remix", False)})

    def test_layers_with_the_core(self):
        r = remix(self.usb, self.core)
        self.assertEqual(self.rows(r), {"OUT": (0, "manifest", False), "IN": (0, "manifest", True)})
        r = remix(self.usb, self.core, settings={("octabam.usb", "IN"): Pin(3)})
        self.assertEqual(self.rows(r)["IN"], (3, "pin", False))

    def test_remix_refusals(self):
        for settings, words in (
                ({("octabam.nope", "OUT"): 1}, "no selected module"),
                ({("octabam.usb", "NOPE"): 1}, "has no setting"),
                ({("octabam.usb", "OUT"): "SURROUND"}, "not one of"),
                ({("octabam.usb", "OUT"): Pin(9)}, "not one of"),
                ({"OUT": 1}, "(store id, setting name)")):
            with self.subTest(words):
                bad = brain.check_remix(remix(self.usb, settings=settings), self.mods)
                self.assertTrue(bad and words in bad[0], bad)

    def test_requires_brain(self):
        m = mod(name="names", store_id="octabam.names", requires_brain=True)
        mods = {m.key: m, BRAIN_KEY: self.core}
        self.assertIn("does not carry BRAIN", brain.check_remix(remix(m), mods)[0])
        self.assertEqual(brain.check_remix(remix(m, self.core), mods), [])

    def test_duplicate_store_ids(self):
        a, b = mod(name="a"), mod(name="b")
        self.assertEqual(len(brain.check_modules({"A": a, "B": b})), 1)


class EarlyBudget(unittest.TestCase):
    def test_bottleservice_layout(self):
        kits = Module(name="kits", key="KITS", kind=Kind.CF_PATCH, doc="fixture",
                      claims=Claims(sram=((0x100F85A0, 0x48, "RESID"), (0x100FFE00, 0x100, "ASSIGN"))))
        plocks = Module(name="plocks", key="PLOCKS", kind=Kind.CF_PATCH, doc="fixture",
                        claims=Claims(sram=((0x100F8600, 0x7800, "P2NV"),)))
        mods = {m.key: m for m in (kits, plocks, core())}
        r = remix(kits, plocks, core())
        self.assertEqual(brain.early_budget(r, mods), 24 - brain.EARLY_HEADER)
        self.assertEqual(brain.early_budget(remix(core()), {BRAIN_KEY: core()}),
                         0x100FFF00 - 0x100F859C - brain.EARLY_HEADER)

    def test_overflow_refused(self):
        many = tuple(Setting(k, f"S{k}", Number(0, 9), early=True) for k in range(1, 12))
        m = mod(settings=many)
        plocks = Module(name="plocks", key="PLOCKS", kind=Kind.CF_PATCH, doc="fixture",
                        claims=Claims(sram=((0x100F85A0, 0x100FFF00 - 0x100F85A0, "all"),)))
        mods = {x.key: x for x in (m, plocks, core())}
        bad = brain.check_remix(remix(m, plocks, core()), mods)
        self.assertTrue(bad and "early settings take 22 bytes" in bad[0], bad)
        self.assertEqual(brain.check_remix(remix(m, plocks), mods), [])


class Lock(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        (root / "modules" / "usb").mkdir(parents=True)
        self.p = patch.object(brain, "ROOT", root)
        self.p.start()

    def tearDown(self):
        self.p.stop()
        self.tmp.cleanup()

    def test_missing_then_written_then_current(self):
        m = mod()
        self.assertIn("no brain.lock", brain.check_lock(m)[0])
        self.assertEqual(brain.write_lock(m), [])
        self.assertEqual(brain.check_lock(m), [])

    def test_added_key_is_stale_until_relocked(self):
        brain.write_lock(mod())
        m = mod(settings=(OUT, IN, Setting(3, "GAIN", Number(0, 10))))
        self.assertIn("stale", brain.check_lock(m)[0])
        self.assertEqual(brain.write_lock(m), [])
        self.assertEqual(brain.check_lock(m), [])

    def test_breaking_changes(self):
        brain.write_lock(mod())
        cases = {
            "was removed": mod(settings=(OUT,)),
            "changed type": mod(settings=(OUT, Setting(2, "IN", Number(0, 3)))),
            "append only": mod(settings=(OUT, Setting(2, "IN", Option("OFF", "CD", "AB", "ABCD")))),
            "store id": mod(store_id="octabam.usb2"),
        }
        for words, m in cases.items():
            with self.subTest(words):
                bad = brain.check_lock(m)
                self.assertTrue(any(words in b for b in bad), bad)
                self.assertTrue(brain.write_lock(m))

    def test_appended_label_and_rename_pass(self):
        brain.write_lock(mod())
        m = mod(settings=(OUT, Setting(2, "INPUT", Option("OFF", "AB", "CD", "ABCD", "USB"))))
        self.assertEqual(brain.write_lock(m), [])

    def test_retire_then_reuse_refused(self):
        brain.write_lock(mod())
        m = mod(settings=(OUT,))
        self.assertEqual(brain.write_lock(m, retire=[2]), [])
        self.assertEqual(brain.check_lock(m), [])
        back = mod(settings=(OUT, Setting(2, "NEW", Binary())))
        self.assertTrue(any("in use again" in b for b in brain.check_lock(back)))

    def test_type_change_with_a_new_major(self):
        brain.write_lock(mod())
        m = Module(name="usb", key="USB", kind=Kind.CF_PATCH, doc="fixture",
                   store=Store("octabam.usb", major=2),
                   settings=(OUT, Setting(2, "IN", Number(0, 3))))
        self.assertEqual(brain.write_lock(m), [])

    def test_params(self):
        m = mod(params=keyed())
        brain.write_lock(m)
        self.assertEqual(brain.check_lock(m), [])
        moved = mod(params=keyed(keys=[2, 1] + list(range(3, 13))))
        self.assertIn("stale", brain.check_lock(moved)[0])
        gone = mod(params=keyed(n_drawn=11, keys=list(range(1, 12))))
        self.assertTrue(any("was removed" in b for b in brain.check_lock(gone)))
        self.assertEqual(brain.write_lock(gone, retire_param=[12]), [])


def fx(**kw):
    """An effect with a MODE select on slot 6 and a knob renamed in mode 1."""
    params = tuple(Param(b"K%d" % i, 10, 128, active=True) for i in range(6)) + \
        (Param(b"MODE", 0, 3, active=True, labels=("A", "B", "C")),) + \
        tuple(Param(b"P%d" % i, 20, 128, active=True) for i in range(7, 12))
    return Module(name="fx", key="FX", kind=Kind.CF_PATCH, doc="fixture", params=params,
                  mode_slot=6, mode_views=(ModeView(1, names={0: b"RATE"}, defaults={7: 40}),), **kw)


class Binding(unittest.TestCase):
    def test_variant_sets_fields_and_values(self):
        def variant(v):
            return {"linked": (Linked("u", "u.s", cpu="5475", dram=True,
                                      include=lambda mods, n=v["LAYOUT"]: n),)}
        m = mod(settings=(OUT,), variant=variant)
        b = m.bind({"LAYOUT": "MAIN"})
        self.assertEqual(b.linked[0].include({}), "MAIN")
        self.assertEqual(dict(b.build_values), {"LAYOUT": "MAIN"})
        self.assertEqual(m.build_values, {})

    def test_variant_may_not_rename(self):
        m = mod(settings=(OUT,), variant=lambda v: {"key": "OTHER"})
        self.assertRaises(ValueError, m.bind, {"LAYOUT": "MAIN"})

    def test_variant_needs_a_build_setting(self):
        self.assertRaises(ValueError, lambda: mod(settings=(IN,), variant=lambda v: {}))

    def test_build_values_take_labels(self):
        usb = mod()
        r = remix(usb, settings={("octabam.usb", "OUT"): Pin(2)})
        self.assertEqual(brain.build_values(r, {usb.key: usb}), {"USB": {"OUT": "MASTER"}})
        self.assertEqual(brain.value(r, {usb.key: usb}, "octabam.usb", "OUT"), "MASTER")
        self.assertIsNone(brain.value(r, {usb.key: usb}, "octabam.none", "OUT"))


class KnobDefaults(unittest.TestCase):
    def setUp(self):
        self.m = fx()
        self.mods = {"FX": self.m}

    def test_applied(self):
        r = remix(self.m, defaults={("FX", None, "K0"): 64, ("FX", "B", "RATE"): 5,
                                     ("FX", 2, "P7"): 90})
        self.assertEqual(brain.check_remix(r, self.mods), [])
        over = brain.apply_defaults(self.m, brain.defaults_by_module(r, self.mods)["FX"])
        self.assertEqual(over["params"][0].default, 64)
        views = {v.mode: v for v in over["mode_views"]}
        self.assertEqual(views[1].defaults, {7: 40, 0: 5})
        self.assertEqual(views[1].names, {0: b"RATE"})
        self.assertEqual(views[2].defaults, {7: 90})
        self.assertEqual(self.m.params[0].default, 10)

    def test_refusals(self):
        for entry, v, words in ((("NOPE", None, "K0"), 1, "not in the remix"),
                                (("FX", "Z", "K0"), 1, "no MODE value"),
                                (("FX", None, "NOPE"), 1, "no knob"),
                                (("FX", None, "MODE"), 3, "outside"),
                                (("FX", "A", "MODE"), 1, "MODE itself"),
                                (("FX", None, "K0"), 128, "outside")):
            with self.subTest(words):
                bad = brain.check_remix(remix(self.m, defaults={entry: v}), self.mods)
                self.assertTrue(bad and words in bad[0], bad)

    def test_report(self):
        usb = mod()
        mods = {"FX": self.m, "USB": usb}
        r = remix(self.m, usb, settings={("octabam.usb", "OUT"): Pin("MAIN")},
                  defaults={("FX", None, "K0"): 64})
        lines = brain.report(r, mods)
        self.assertEqual(lines[0][:12], "=== Settings")
        self.assertIn("  octabam.usb OUT = MAIN  (pin; fixed in the image)", lines)
        self.assertIn("  FX K0 default = 64  (remix)", lines)
        self.assertEqual(brain.report(remix(self.m), {"FX": self.m}), [])


class LiveTable(unittest.TestCase):
    """The run-time value table and the read macro (BRAIN.md section 5)."""

    def setUp(self):
        self.usb = mod()
        self.log = mod("log", settings=(Setting(2, "B", Binary(), apply=Apply.NEXT_BOOT),
                                        Setting(1, "A", Number(0, 9), apply=Apply.NEXT_BOOT)),
                       store_id="octabam.log")
        self.core = core()
        self.mods = {"USB": self.usb, "LOG": self.log, BRAIN_KEY: self.core}

    def names(self, r):
        return [(res.store_id, res.name) for res, _s, _m in brain.live_table(r, self.mods)]

    def test_empty_without_brain(self):
        self.assertEqual(brain.live_table(remix(self.usb, self.log), self.mods), [])

    def test_skips_build_settings(self):
        r = remix(self.core, self.usb)
        self.assertEqual(self.names(r), [("octabam.usb", "IN")])

    def test_skips_pinned(self):
        r = remix(self.core, self.usb, settings={("octabam.usb", "IN"): Pin(1)})
        self.assertEqual(self.names(r), [])

    def test_order_is_remix_then_key(self):
        r = remix(self.core, self.log, self.usb)
        self.assertEqual(self.names(r), [("octabam.log", "A"), ("octabam.log", "B"),
                                         ("octabam.usb", "IN")])
        r = remix(self.core, self.usb, self.log)
        self.assertEqual(self.names(r)[0], ("octabam.usb", "IN"))

    def test_table_carries_module_and_setting(self):
        res, s, m = brain.live_table(remix(self.core, self.usb), self.mods)[0]
        self.assertIs(s, IN)
        self.assertIs(m, self.usb)
        self.assertEqual(res.key, 2)

    def test_symbol(self):
        self.assertEqual(brain.value_symbol("octabam.usb", 2), "brain_v_octabam_usb_2")

    def test_read_macro_live(self):
        out = brain.read_macro(remix(self.core, self.usb), self.mods, "octabam.usb", "IN", "get_in")
        self.assertIn(".macro  get_in reg", out)
        self.assertIn("move.l  brain_v_octabam_usb_2,\\reg", out)

    def test_read_macro_absent_pinned_and_build(self):
        cases = [((self.usb,), {}, "IN", 0),
                 ((self.core, self.usb), {("octabam.usb", "IN"): Pin(3)}, "IN", 3),
                 ((self.core, self.usb), {}, "OUT", 0)]
        for mods, pins, name, want in cases:
            out = brain.read_macro(remix(*mods, settings=pins), self.mods, "octabam.usb", name, "m")
            self.assertIn(f"move.l  #{want},\\reg", out)
            self.assertNotIn("brain_v_", out)

    def test_read_macro_unknown(self):
        with self.assertRaises(KeyError):
            brain.read_macro(remix(self.core, self.usb), self.mods, "octabam.usb", "NOPE", "m")


if __name__ == "__main__":
    unittest.main()
