"""schema.Evidence, Level, best and from_proof; evidence.py's source list (no image, no build)."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from remix.schema import Evidence, Level, Proof, best, from_proof  # noqa: E402


class Ev(unittest.TestCase):
    def test_rank_order(self):
        self.assertEqual([l.name for l in sorted(Level, key=lambda l: l.rank)],
                         ["BUILD", "EMULATOR", "RENDER", "UNIT", "UNIT_MEASURED"])

    def test_best_is_strongest_then_latest(self):
        a, b, c = Evidence(Level.EMULATOR), Evidence(Level.UNIT, unit="MKI"), Evidence(Level.UNIT, unit="MKII")
        self.assertIs(best((a, b)), b)
        self.assertIs(best((b, a, c)), c)
        self.assertIsNone(best(()))

    def test_refusals(self):
        with self.assertRaises(ValueError):
            Evidence(Level.UNIT, unit="MK2")
        with self.assertRaises(ValueError):
            Evidence(Level.UNIT, date="12 Nov 2026")
        with self.assertRaises(ValueError):
            Evidence(Level.RENDER, unit="MKII")

    def test_text(self):
        e = Evidence(Level.UNIT, unit="MKII", who="sambanks", image="OCTABAM88", date="2026-09-27", note="n")
        self.assertEqual(e.text(), "on a unit (MKII, sambanks, OCTABAM88, 2026-09-27): n")
        self.assertEqual(Evidence(Level.BUILD).text(), "builds")

    def test_from_proof_reads_the_note(self):
        e = from_proof(Proof.HARDWARE, "Ilia's MKII, OCTABAM26, 31 Oct 2026: the chooser")
        self.assertEqual((e.level, e.unit, e.who, e.image, e.date), (Level.UNIT, "MKII", "Ilia", "OCTABAM26", "2026-10-31"))
        self.assertEqual(from_proof(Proof.HARDWARE, "the author's MKI", "zk").who, "zk")
        e = from_proof(Proof.PORT, "verify_hooks: the chains")
        self.assertEqual((e.level, e.ref), (Level.EMULATOR, "verify_hooks"))
        self.assertEqual(from_proof(Proof.CHECK, "").level, Level.EMULATOR)
        self.assertEqual(from_proof(Proof.RENDER, "x").level, Level.RENDER)


if __name__ == "__main__":
    unittest.main()
