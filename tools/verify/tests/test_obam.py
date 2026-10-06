"""The OBAM container against its byte corpus (docs/proposals/STORE.md
section 7): every outcome, byte-for-byte round trips, kept bytes after an
edit, and the .work / .strd pair rule of section 6.2."""
import json
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
from remix import obam  # noqa: E402
import make_obam_corpus as corpus  # noqa: E402

EXPECT = json.loads((corpus.OUT / "expect.json").read_text())


def load(name):
    return (corpus.OUT / f"{name}.obam").read_bytes()


def shown(v):
    if v.type == obam.BLOB:
        return v.data.hex()
    if v.type in obam.TYPE_NAMES:
        return obam.decode_value(v.type, v.data)
    return f"type {v.type}"


class Corpus(unittest.TestCase):
    def test_committed_copy_is_current(self):
        self.assertEqual(corpus.stale(), [], "python3 tools/verify/tests/make_obam_corpus.py")

    def test_every_outcome(self):
        for name, e in EXPECT.items():
            with self.subTest(name):
                data = load(name)
                if e["outcome"] == "invalid":
                    self.assertRaises(obam.Invalid, obam.parse, data)
                    continue
                if e["outcome"] == "unreadable":
                    self.assertRaises(obam.Unreadable, obam.parse, data)
                    continue
                f = obam.parse(data)
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
                    self.assertEqual(obam.parse(data).encode(), data)


class Edits(unittest.TestCase):
    def test_edit_keeps_other_records_and_unknown_keys(self):
        f = obam.parse(load("absent_module"))
        other = f.records[1].encode()
        f.records[0].replace(1, obam.BINARY, b"\x00")
        out = obam.parse(f.encode())
        self.assertEqual(out.records[1].encode(), other)
        self.assertEqual(out.records[0].values()[0].data, b"\x00")

        f = obam.parse(load("newer_minor_unknown_key"))
        unknown = [v.raw for v in f.records[0].values() if v.key == 99][0]
        f.records[0].replace(2, obam.OPTION, b"\x00")
        out = obam.parse(f.encode())
        self.assertEqual([v.raw for v in out.records[0].values() if v.key == 99][0], unknown)
        self.assertEqual(out.records[0].minor, 5)

    def test_unknown_type_value_kept_on_edit(self):
        f = obam.parse(load("unknown_value_type"))
        raw = f.records[0].values()[1].raw
        f.records[0].replace(1, obam.BINARY, b"\x00")
        self.assertEqual(obam.parse(f.encode()).records[0].values()[1].raw, raw)

    def test_flags_kept_on_edit(self):
        f = obam.parse(load("flags_and_reserved"))
        f.records[0].replace(1, obam.BINARY, b"\x00")
        self.assertEqual(obam.parse(f.encode()).records[0].flags, 0x8001)

    def test_value_codecs(self):
        from remix.schema import Binary, Blob, Number, Option
        for kind, v in ((Binary(), 1), (Option("A", "B", "C"), "C"), (Number(-5, 5), -3),
                        (Blob(8), b"xyz")):
            t, d = obam.encode_value(kind, v)
            back = obam.decode_value(t, d)
            self.assertEqual(back, kind.index(v) if isinstance(kind, Option) else v)
        self.assertEqual(obam.decode_value(obam.NAME, obam.name_data("CUT")), "CUT")
        self.assertRaises(ValueError, obam.name_data, "CUTOFF")
        self.assertRaises(ValueError, obam.decode_value, obam.NUMBER, b"\x00")

    def test_layout_hash_changes_with_a_key_or_count(self):
        base = [(i + 1, 128) for i in range(12)]
        h = obam.layout_hash(base, 6)
        self.assertNotEqual(h, obam.layout_hash(base, None))
        self.assertNotEqual(h, obam.layout_hash([(13, 128)] + base[1:], 6))
        self.assertNotEqual(h, obam.layout_hash([(1, 5)] + base[1:], 6))
        self.assertRaises(ValueError, obam.layout_hash, base[:11], 6)


class Pair(unittest.TestCase):
    """STORE.md section 6.2, one test per row."""
    good = load("settings_known")
    bad = load("bad_file_crc")

    def check(self, work, strd, action, write=True):
        got, _f, w = obam.pair(work, strd)
        self.assertEqual((got, w), (action, write))

    def test_rows(self):
        g, b = self.good, self.bad
        self.check(None, None, obam.FRESH)
        self.check(g, None, obam.USE_WORK)
        self.check(g, g, obam.USE_WORK)
        self.check(g, b, obam.WORK_STRD_DAMAGED)
        self.check(None, g, obam.RECOVER)
        self.check(b, g, obam.RECOVER)
        self.check(b, None, obam.DAMAGED, False)
        self.check(None, b, obam.DAMAGED, False)
        self.check(b, b, obam.DAMAGED, False)

    def test_newer_major_is_not_overwritten(self):
        self.check(load("newer_container_major"), None, obam.DAMAGED, False)


if __name__ == "__main__":
    unittest.main()
