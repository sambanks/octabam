"""symdb.py and sym.py on a synthetic database (no image, no build)."""
import io
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/build"))
import symdb  # noqa: E402
import sym  # noqa: E402


def make(path, ingesters="layout,map"):
    db = sqlite3.connect(path)
    db.executescript(symdb.DDL)
    rows = [("cf", 0x40001000, 0x100, "func_a", "func", "stock", "layout", "x:1"),
            ("cf", 0x40001000, None, "alias_a", "label", "stock", "equ", "y"),
            ("cf", 0x40002000, None, "nosize", "func", "stock", "layout", None),
            ("cf", 0x40ac0000, 0x20, "rmt_in", "func", "REMOTE", "map", "runtime.elf")]
    db.executemany("INSERT INTO symbol VALUES (?,?,?,?,?,?,?,?)", rows)
    db.execute("INSERT INTO cite VALUES ('cf', 4096+0x40000000, 'docs/a.md', 3)")
    db.execute("INSERT INTO meta VALUES ('ingesters', ?)", (ingesters,))
    db.commit()
    return db


class Sym(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self.d.name) / "s.sqlite"
        self.db = make(self.path)

    def tearDown(self):
        self.d.cleanup()

    def test_exact_and_two_names_at_one_address(self):
        self.assertEqual({r["name"] for r in sym.at(self.db, 0x40001000)}, {"func_a", "alias_a"})

    def test_nearest_below_and_offset(self):
        r = sym.at(self.db, 0x40001010)
        self.assertEqual(sym.label(r[0]), "alias_a+0x10")
        self.assertTrue(next(x for x in r if x["name"] == "func_a")["covers"])
        self.assertFalse(next(x for x in r if x["name"] == "alias_a")["covers"])

    def test_past_size_is_not_covered(self):
        self.assertFalse(sym.at(self.db, 0x40001200)[0]["covers"])

    def test_no_symbol_below(self):
        self.assertEqual(sym.at(self.db, 0x30000000), [])

    def test_cite_count(self):
        self.assertEqual(sym.cites(self.db, 0x40001000), 1)

    def test_resolve_rewrites_covered_and_exact_only(self):
        c = {}
        self.assertEqual(sym.resolve_line(self.db, "a 0x40001010 b", c), "a 0x40001010 <func_a+0x10> b")
        self.assertEqual(sym.resolve_line(self.db, "0x40002000", c), "0x40002000 <nosize>")
        self.assertEqual(sym.resolve_line(self.db, "0x40002040", c), "0x40002040")
        self.assertEqual(sym.resolve_line(self.db, "0x48000000", c), "0x48000000")

    def test_callers_without_ghidra_exits_2(self):
        with patch.object(sys, "argv", ["sym", "--db", str(self.path), "--callers", "0x40001000"]), \
                patch("sys.stderr", io.StringIO()):
            self.assertEqual(sym.main(), 2)

    def test_prefix_match(self):
        with patch.object(sys, "argv", ["sym", "--db", str(self.path), "func"]), redirect_stdout(io.StringIO()) as o:
            self.assertEqual(sym.main(), 0)
        self.assertIn("func_a", o.getvalue())


class Staging(unittest.TestCase):
    def test_clone_exports_are_not_runtime_symbols(self):
        nm = "40aff634 0000000c T CLONE_X\n40a00000 00000010 T real\n"
        rows = []
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t)
            (p / "runtime").mkdir()
            (p / "runtime/runtime.elf").write_text("")
            with patch.object(symdb.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, nm, "")):
                symdb.ingest_map(lambda *a: rows.append(a), p)
        self.assertEqual([r[3] for r in rows], ["real"])


if __name__ == "__main__":
    unittest.main()
