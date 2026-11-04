"""SYNTH MACHINE's PLACE setting: CAVE keeps the author's pinned page cave, DRAM links page.s
into the runtime and leaves 0x400d24d0 alone (issue #771)."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import toolpath  # noqa: E402,F401
from remix import ledger, registry  # noqa: E402

PAGE_AT = 0x400d24d0
STOCK_DELAY_READS = range(0x400d24d0, 0x400d2ce0)   # entries 508..1023 (issue #1007)


class SynthPlace(unittest.TestCase):
    def setUp(self):
        self.mod = registry.by_key("SYNTH MACHINE")

    def test_cave_is_the_authors_form_and_pins_the_page(self):
        bound = self.mod.bind({"PLACE": "CAVE"})
        self.assertEqual([c.cave_addr for c in bound.cf_patches], [PAGE_AT])
        self.assertNotIn("page", [u.label for u in bound.linked])

    def test_dram_links_the_page_and_leaves_the_run(self):
        bound = self.mod.bind({"PLACE": "DRAM"})
        self.assertEqual(bound.cf_patches, ())
        page = [u for u in bound.linked if u.label == "page"]
        self.assertEqual(len(page), 1)
        self.assertTrue(page[0].dram)
        hook = [d for d in bound.detours if d.unit == "page"]
        self.assertEqual([(d.site, d.symbol) for d in hook], [(0x40031ece, "pg_resolve")])
        for kind, start, length, label in bound.write_spans():
            self.assertFalse(set(range(start, start + length)) & set(STOCK_DELAY_READS),
                             f"{kind} {label} at 0x{start:08x} overlaps the stock DELAY's table read")


    def test_dram_is_the_default(self):
        place = [s for s in self.mod.settings if s.name == "PLACE"][0]
        self.assertEqual(place.kind.labels[place.default], "DRAM")

    def test_the_ledger_refuses_the_cave_beside_the_stock_delay_only(self):
        delay = registry.by_key("DELAY")
        cave = ledger.check([delay, self.mod.bind({"PLACE": "CAVE"})])
        self.assertTrue(any(p.startswith("kept bytes") for p in cave), cave)
        self.assertEqual(ledger.check([delay, self.mod.bind({"PLACE": "DRAM"})]), [])
        self.assertEqual([p for p in ledger.check([self.mod.bind({"PLACE": "CAVE"})])
                          if p.startswith("kept bytes")], [])


if __name__ == "__main__":
    unittest.main()
