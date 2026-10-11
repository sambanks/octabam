"""tools/hw/ot_brain.py: every valid corpus file through JSON and back,
byte for byte."""
import json
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parents[1] / "hw"))
import ot_brain  # noqa: E402

CORPUS = HERE / "brainfile_corpus"
EXPECT = json.loads((CORPUS / "expect.json").read_text())


class RoundTrip(unittest.TestCase):
    def test_dump_then_build_is_identical(self):
        for name, e in EXPECT.items():
            if e["outcome"] != "valid":
                continue
            with self.subTest(name):
                data = (CORPUS / f"{name}.brain").read_bytes()
                j = json.loads(json.dumps(ot_brain.dump(data)))
                self.assertEqual(ot_brain.build(j), data)

    def test_an_edited_value_lands(self):
        data = (CORPUS / "settings_known.brain").read_bytes()
        j = ot_brain.dump(data)
        j["records"][0]["values"][2]["value"] = 1234
        out = ot_brain.dump(ot_brain.build(j))
        self.assertEqual(out["records"][0]["values"][2]["value"], 1234)


if __name__ == "__main__":
    unittest.main()
