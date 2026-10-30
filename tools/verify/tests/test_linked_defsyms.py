"""Linked.defsyms reach the assembler and the linker; Linked.reference may
depend on the remix."""
import pathlib
import shutil
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from remix import platform_build  # noqa: E402
from remix import resident_link  # noqa: E402
from remix.schema import Linked  # noqa: E402

TOOLS = all(shutil.which(t) for t in ("m68k-elf-as", "m68k-elf-ld", "m68k-elf-objcopy", "m68k-elf-nm"))
SRC = """        .text
entry:
.ifdef GATE
        move.l  #0x11111111,%d0
.else
        move.l  #0x22222222,%d0
.endif
        move.l  #VAL,%d1
        rts
"""


@unittest.skipUnless(TOOLS, "needs the m68k-elf toolchain (make setup)")
class DefsymLinkTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "out").mkdir(parents=True, exist_ok=True)
        self.dir = pathlib.Path(tempfile.mkdtemp(prefix="octabam_defsym_", dir=ROOT / "out"))
        self.src = self.dir / "unit.s"
        self.src.write_text(SRC)
        self.unit = Linked("unit", str(self.src.relative_to(ROOT)), dram=True,
                           defsyms=(("GATE", 1), ("VAL", 0x1234)))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _link(self, defs):
        raw, _syms, _gsyms, _tables = platform_build.link_runtime(
            [("K", self.unit)], self.dir / "w", dict(defs), 0x40a00000, unit_defs={"unit": defs})
        return raw

    def test_ifdef_selects_code(self):
        self.assertTrue(self._link((("GATE", 1), ("VAL", 0x1234))).startswith(bytes.fromhex("203c11111111")))
        self.assertTrue(self._link((("VAL", 0x1234),)).startswith(bytes.fromhex("203c22222222")))

    def test_value_lands_in_the_bytes(self):
        self.assertIn(bytes.fromhex("223c00001234"), self._link((("GATE", 1), ("VAL", 0x1234))))

    def test_a_label_of_the_unit_is_refused(self):
        self.src.write_text(SRC + "VAL:    rts\n")
        with self.assertRaises(SystemExit) as e:
            self._link((("VAL", 0x1234),))
        self.assertIn("defines VAL", str(e.exception))


@unittest.skipUnless(TOOLS, "needs the m68k-elf toolchain (make setup)")
class UnitTableTests(unittest.TestCase):
    """Per-unit symbol tables: a same-named label in two units of one link
    resolves to each unit's own definition, not by nm table order (the
    octabam-bus storm, 15 Oct 2026)."""

    def test_duplicate_names_scope_to_their_unit(self):
        (ROOT / "out").mkdir(parents=True, exist_ok=True)
        d = pathlib.Path(tempfile.mkdtemp(prefix="octabam_units_", dir=ROOT / "out"))
        try:
            (d / "one.s").write_text("        .text\n        .globl  one\none:    rts\n"
                                     "cave:   rts\n")
            (d / "two.s").write_text("        .text\n        .globl  two\ntwo:    rts\n"
                                     "cave:   rts\n")
            one = Linked("one", str((d / "one.s").relative_to(ROOT)), dram=True)
            two = Linked("two", str((d / "two.s").relative_to(ROOT)), dram=True)
            _raw, _flat, _gsyms, _tables = platform_build.link_runtime(
                [("K", one), ("K", two)], d / "w", {}, 0x40a00000)
        finally:
            shutil.rmtree(d, ignore_errors=True)
        self.assertEqual(_tables["one"]["cave"], _tables["one"]["one"] + 2)
        self.assertEqual(_tables["two"]["cave"], _tables["two"]["two"] + 2)
        self.assertNotEqual(_tables["one"]["cave"], _tables["two"]["cave"])
        self.assertIn("one", _gsyms)
        self.assertNotIn("cave", _gsyms)


class ReferenceTests(unittest.TestCase):
    A = (0x400d7000, "a" * 64)
    B = (0x400d7000, "b" * 64)

    def test_callable_picks_a_variant(self):
        u = Linked("u", "u.s", include=lambda mods, remix: "",
                   reference=lambda mods: self.B if "SIDECHAIN" in mods else self.A)
        self.assertEqual(u.reference_for({"SIDECHAIN": object()}), self.B)
        self.assertEqual(u.reference_for({}), self.A)
        optional = Linked("optional", "u.s", reference=lambda mods: None if "SIDECHAIN" in mods else self.A)
        self.assertIsNone(optional.reference_for({"SIDECHAIN": object()}))
        self.assertEqual(optional.reference_for({}), self.A)

    def test_shape_is_validated(self):
        with self.assertRaises(ValueError):
            Linked("u", "u.s", reference=(0x400d7000, "not a hash"))
        with self.assertRaises(ValueError):
            Linked("u", "u.s", reference=lambda mods: 0x400d7000).reference_for({})

    def test_a_name_declared_twice_is_refused(self):
        with self.assertRaises(ValueError):
            Linked("u", "u.s", defsyms=(("A", 1), ("A", 2)))


class ResidentReferenceTests(unittest.TestCase):
    def unit(self, **kwargs):
        return Linked('entry', 'entry.s', defsyms=(('CALLBACK', 0),),
                      runtime_refs=(('CALLBACK', 'provider', 'callback'),), **kwargs)

    def test_only_resident_units_and_explicit_defaults(self):
        for kwargs in ({'dram': True}, {'loader': True}):
            with self.assertRaises(ValueError):
                self.unit(**kwargs)
        with self.assertRaises(ValueError):
            Linked('u', 'u.s', runtime_refs=(('A', 'v', 'target'),))
        with self.assertRaises(ValueError):
            Linked('u', 'u.s', defsyms=(('A', 0),),
                   runtime_refs=(('A', 'v', 'target'), ('A', 'w', 'target')))

    def test_provider_scope_beats_same_named_symbol_elsewhere(self):
        tables = {'provider': {'callback': 0x40a90000},
                  'other': {'callback': 0x40aa0000}}
        self.assertEqual(resident_link.resolve(self.unit(), tables), {'CALLBACK': 0x40a90000})

    def test_missing_provider_or_symbol_never_uses_reference_default(self):
        for tables in ({}, {'provider': {}}, {'other': {'callback': 0x40a90000}}):
            with self.assertRaisesRegex(ValueError, 'does not define'):
                resident_link.resolve(self.unit(), tables)

    @unittest.skipUnless(TOOLS, 'needs the m68k-elf toolchain')
    def test_real_relink_preserves_entries_and_rejects_changed_layout(self):
        with tempfile.TemporaryDirectory(prefix='resident-link-', dir=ROOT/'out') as temp:
            work = pathlib.Path(temp)
            source = work/'entry.s'
            source.write_text('.text\n.global entry, slot\nentry:\n'
                              'move.l #CALLBACK,%d0\nslot: .long 0\n')
            unit = Linked('resident', str(source), defsyms=(('CALLBACK', 0),),
                          runtime_refs=(('CALLBACK', 'provider', 'callback'),))
            def link(folder, value):
                raw, _, exports, _ = platform_build.link_runtime(
                    [('K', unit)], work/folder, {'CALLBACK': value}, 0x400d6b80,
                    unit_defs={'resident': (('CALLBACK', value),)})
                return raw, {n:v for n,v in exports.items() if n != 'CALLBACK'}
            before, old = link('first', 0x11223344)
            after, new = link('final', 0x40a9582e)
            resident_link.check_layout('resident', before, old, after, new)
            self.assertIn(bytes.fromhex('203c40a9582e'), after)
            # A source whose assembly changes size with the resolved value
            # must not overwrite the next placed unit.
            source.write_text('.text\n.global entry, slot\nentry:\n'
                              'move.l #CALLBACK,%d0\n.if CALLBACK\n nop\n.endif\n'
                              'slot: .long 0\n')
            after, new = link('grown', 0x40a9582e)
            with self.assertRaisesRegex(ValueError, 'changed resident size'):
                resident_link.check_layout('resident', before, old, after, new)
            # Equal size alone is insufficient: another unit may already
            # reference a data slot that moved within the resident unit.
            source.write_text('.text\n.global entry, slot\nentry:\n'
                              'move.w #CALLBACK,%d0\nslot: .long 0\n nop\n')
            after, new = link('moved-slot', 0x1234)
            with self.assertRaisesRegex(ValueError, 'moved resident exports'):
                resident_link.check_layout('resident', before, old, after, new)


if __name__ == "__main__":
    unittest.main()
