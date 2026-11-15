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
    def test_a_symbol_in_the_staging_range_is_not_a_runtime_symbol(self):
        nm = "40b50010 0000000c T CLONE_X\n40a00000 00000010 T real\n40aff0fc 00000010 T CLONE_Y\n"
        rows = []
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t)
            (p / "runtime").mkdir()
            (p / "runtime/runtime.elf").write_text("")
            (p / "layout.json").write_text('{"units": [], "stage": %d, "stage_end": %d}' % (0x40b50000, 0x40b7a6ad))
            with patch.object(symdb.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, nm, "")):
                symdb.ingest_map(lambda *a: rows.append(a), p)
        self.assertEqual([r[3] for r in rows], ["real", "CLONE_Y"])


class Dsp(unittest.TestCase):
    def test_records_become_rows(self):
        import json
        rows = []
        with tempfile.TemporaryDirectory() as t:
            d = pathlib.Path(t)
            (d / "window_records.json").write_text(json.dumps({"DLCOPY": [0x33dcb, [0] * 138], "LOAD METER:B": [0x37e50, [0] * 3],
                                                                "hook stub X sctap AB": [0x33fcd, [0] * 10]}))
            (d / "demand_records.json").write_text(json.dumps({"SPECTRUM": {"homes": [{"addr": 0x33820, "words": [0] * 5, "init": 0x33820, "proc": 0x3384c}]}}))
            (d / "guard_records.json").write_text(json.dumps({"PLATE REV:A": {"stock_init": 1, "init": 0x33ede, "proc": 0x33ee2}}))
            n = symdb.ingest_dsp(lambda *a: rows.append(a), d)
        self.assertEqual(n, len(rows))
        self.assertIn(("dspA:P", 0x33dcb, 138, "DLCOPY", "block", "DLCOPY", "build", "out/dsp/window_records.json"), rows)
        self.assertEqual({r[0] for r in rows if r[3] == "LOAD METER:B"}, {"dspB:P"})
        self.assertEqual({r[0] for r in rows if r[3].startswith("hook stub")}, {"dspA:P", "dspB:P"})
        self.assertIn("SPECTRUM proc (home 0)", [r[3] for r in rows])
        self.assertIn(("dspA:P", 0x33ee2, None, "PLATE REV guard proc", "func", "PLATE REV", "build", "out/dsp/guard_records.json"), rows)


@unittest.skipUnless((ROOT / "out/raw/section_3_MAIN_OS.bin").exists(), "needs the user's stock image")
class Dispatch(unittest.TestCase):
    def test_both_payloads_name_their_dispatch_entries(self):
        with tempfile.TemporaryDirectory() as t:
            db = sqlite3.connect(pathlib.Path(t) / "s.sqlite")
            db.executescript(symdb.DDL)
            n = symdb.ingest_dispatch(lambda *r: db.execute("INSERT INTO symbol VALUES (?,?,?,?,?,?,?,?)", r))
            names = {(r[0], r[1]): r[2] for r in db.execute("SELECT space, addr, name FROM symbol")}
        self.assertGreater(n, 100)
        self.assertEqual(names[("dspA:P", 0x7dd)], "fx_filter_process")
        self.assertEqual(names[("dspB:P", 0x59d)], "fx_filter_process")
        self.assertEqual(names[("dspA:X", 0x215)], "fx_init_table")


class Weighted(unittest.TestCase):
    def test_a_count_line_counts_that_many_times(self):
        got = list(sym.samples(["   0x40001010     90487  ", "0x40001020 5", "pc 0x40001010 and 0x40001020 x9", "text"]))
        self.assertEqual(got, [(0x40001010, 90487), (0x40001020, 5), (0x40001010, 1), (0x40001020, 1)])

    def test_histogram_takes_weights(self):
        with tempfile.TemporaryDirectory() as t:
            db = make(pathlib.Path(t) / "s.sqlite")
            h = sym.histogram(db, sym.samples(["0x40001010 7", "0x40001020 3"]))
        self.assertEqual(h["samples"], 10)
        self.assertEqual(dict(h["symbols"])["func_a"], 10)


class Histogram(unittest.TestCase):
    def test_counts_per_symbol_and_owner(self):
        with tempfile.TemporaryDirectory() as t:
            db = make(pathlib.Path(t) / "s.sqlite")
            h = sym.histogram(db, [0x40001010, 0x40001020, 0x40ac0004, 0x40002040, 0x30000000])
        self.assertEqual(h["samples"], 5)
        self.assertEqual(dict(h["owners"]), {"stock": 2, "REMOTE": 1, "unknown": 2})
        self.assertEqual(dict(h["symbols"])["func_a"], 2)
        self.assertEqual(dict(h["symbols"])["0x40002000.. (below: nosize)"], 1)
        self.assertEqual(dict(h["symbols"])["(none)"], 1)


if __name__ == "__main__":
    unittest.main()
