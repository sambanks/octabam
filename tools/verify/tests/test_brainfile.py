"""The brain file against its byte corpus (docs/proposals/BRAIN.md
section 7): every outcome, byte-for-byte round trips, kept bytes after an
edit, and the .work / .strd pair rule of section 6.2."""
import json
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
from remix import brainfile  # noqa: E402
import make_brainfile_corpus as corpus  # noqa: E402

EXPECT = json.loads((corpus.OUT / "expect.json").read_text())


def load(name):
    return (corpus.OUT / f"{name}.brain").read_bytes()


def shown(v):
    if v.type == brainfile.BLOB:
        return v.data.hex()
    if v.type in brainfile.TYPE_NAMES:
        return brainfile.decode_value(v.type, v.data)
    return f"type {v.type}"


class Corpus(unittest.TestCase):
    def test_committed_copy_is_current(self):
        self.assertEqual(corpus.stale(), [], "python3 tools/verify/tests/make_brainfile_corpus.py")

    def test_every_outcome(self):
        for name, e in EXPECT.items():
            with self.subTest(name):
                data = load(name)
                if e["outcome"] == "invalid":
                    self.assertRaises(brainfile.Invalid, brainfile.parse, data)
                    continue
                if e["outcome"] == "unreadable":
                    self.assertRaises(brainfile.Unreadable, brainfile.parse, data)
                    continue
                f = brainfile.parse(data)
                self.assertEqual(len(f.records), e["records"])
                if "applicable" in e:
                    self.assertEqual([r.applicable() for r in f.records], e["applicable"])
                if "carried" in e:
                    self.assertEqual([r.store_id == corpus.KNOWN and r.major == 1
                                      for r in f.records], e["carried"])
                for i, vals in e.get("values", {}).items():
                    got = {str(v.key): shown(v) for v in f.records[int(i)].values()}
                    self.assertEqual(got, vals)
                if "duplicates" in e:
                    self.assertEqual(len(f.duplicates()), e["duplicates"])
                if "targets" in e:
                    self.assertEqual([list(t) if t else None for t in
                                      (r.target() for r in f.records)], e["targets"])
                if "template_name" in e:
                    self.assertEqual(f.records[1].name(), e["template_name"])

    def test_valid_files_round_trip(self):
        for name, e in EXPECT.items():
            if e["outcome"] == "valid":
                with self.subTest(name):
                    data = load(name)
                    self.assertEqual(brainfile.parse(data).encode(), data)


class Edits(unittest.TestCase):
    def test_edit_keeps_other_records_and_unknown_keys(self):
        f = brainfile.parse(load("absent_module"))
        other = f.records[1].encode()
        f.records[0].replace(1, brainfile.BINARY, b"\x00")
        out = brainfile.parse(f.encode())
        self.assertEqual(out.records[1].encode(), other)
        self.assertEqual(out.records[0].values()[0].data, b"\x00")

        f = brainfile.parse(load("newer_minor_unknown_key"))
        unknown = [v.raw for v in f.records[0].values() if v.key == 99][0]
        f.records[0].replace(2, brainfile.OPTION, b"\x00")
        out = brainfile.parse(f.encode())
        self.assertEqual([v.raw for v in out.records[0].values() if v.key == 99][0], unknown)
        self.assertEqual(out.records[0].minor, 5)

    def test_unknown_type_value_kept_on_edit(self):
        f = brainfile.parse(load("unknown_value_type"))
        raw = f.records[0].values()[1].raw
        f.records[0].replace(1, brainfile.BINARY, b"\x00")
        self.assertEqual(brainfile.parse(f.encode()).records[0].values()[1].raw, raw)

    def test_flags_kept_on_edit(self):
        f = brainfile.parse(load("flags_and_reserved"))
        f.records[0].replace(1, brainfile.BINARY, b"\x00")
        self.assertEqual(brainfile.parse(f.encode()).records[0].flags, 0x8001)

    def test_value_codecs(self):
        from remix.schema import Binary, Blob, Number, Option
        for kind, v in ((Binary(), 1), (Option("A", "B", "C"), "C"), (Number(-5, 5), -3),
                        (Blob(8), b"xyz")):
            t, d = brainfile.encode_value(kind, v)
            back = brainfile.decode_value(t, d)
            self.assertEqual(back, kind.index(v) if isinstance(kind, Option) else v)
        self.assertEqual(brainfile.decode_value(brainfile.NAME, brainfile.name_data("CUT")), "CUT")
        self.assertRaises(ValueError, brainfile.name_data, "CUTOFF")
        self.assertRaises(ValueError, brainfile.decode_value, brainfile.NUMBER, b"\x00")

    def test_layout_hash_changes_with_a_key_or_count(self):
        base = [(i + 1, 128) for i in range(12)]
        h = brainfile.layout_hash(base, 6)
        self.assertNotEqual(h, brainfile.layout_hash(base, None))
        self.assertNotEqual(h, brainfile.layout_hash([(13, 128)] + base[1:], 6))
        self.assertNotEqual(h, brainfile.layout_hash([(1, 5)] + base[1:], 6))
        self.assertRaises(ValueError, brainfile.layout_hash, base[:11], 6)


class Pair(unittest.TestCase):
    """BRAIN.md section 6.2, one test per row."""
    good = load("settings_known")
    bad = load("bad_file_crc")

    def check(self, work, strd, action, write=True):
        got, _f, w = brainfile.pair(work, strd)
        self.assertEqual((got, w), (action, write))

    def test_rows(self):
        g, b = self.good, self.bad
        self.check(None, None, brainfile.FRESH)
        self.check(g, None, brainfile.USE_WORK)
        self.check(g, g, brainfile.USE_WORK)
        self.check(g, b, brainfile.WORK_STRD_DAMAGED)
        self.check(None, g, brainfile.RECOVER)
        self.check(b, g, brainfile.RECOVER)
        self.check(b, None, brainfile.DAMAGED, False)
        self.check(None, b, brainfile.DAMAGED, False)
        self.check(b, b, brainfile.DAMAGED, False)

    def test_newer_major_is_not_overwritten(self):
        self.check(load("newer_container_major"), None, brainfile.DAMAGED, False)


if __name__ == "__main__":
    unittest.main()
