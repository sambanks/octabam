"""tools/hw/ot_store.py: every valid corpus file through JSON and back,
byte for byte."""
import json
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parents[1] / "hw"))
import ot_store  # noqa: E402

CORPUS = HERE / "obam_corpus"
EXPECT = json.loads((CORPUS / "expect.json").read_text())


class RoundTrip(unittest.TestCase):
    def test_dump_then_build_is_identical(self):
        for name, e in EXPECT.items():
            if e["outcome"] != "valid":
                continue
            with self.subTest(name):
                data = (CORPUS / f"{name}.obam").read_bytes()
                j = json.loads(json.dumps(ot_store.dump(data)))
                self.assertEqual(ot_store.build(j), data)

    def test_an_edited_value_lands(self):
        data = (CORPUS / "settings_known.obam").read_bytes()
        j = ot_store.dump(data)
        j["records"][0]["values"][2]["value"] = 1234
        out = ot_store.dump(ot_store.build(j))
        self.assertEqual(out["records"][0]["values"][2]["value"], 1234)


if __name__ == "__main__":
    unittest.main()
