"""dsp_forms.form() on fixed disassembly lines and the CHIP.md row parser (no image, no assembler)."""
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/build"))
import dsp_forms as df  # noqa: E402


class Form(unittest.TestCase):
    def test_short_and_long_are_two_forms(self):
        self.assertNotEqual(df.form("move x0,x:(r7+$40)", 1), df.form("move x0,x:(r7+$40)", 2))

    def test_displacement_sign_is_not_a_form(self):
        self.assertEqual(df.form("move a,y:(r3-$1)", 1), df.form("move a,y:(r3+$1)", 1))

    def test_numbers_blank(self):
        self.assertEqual(df.form("move    #>$4000,x0", 2), "move #N,x0  [2w]")
        self.assertEqual(df.form("move x:>$213,r4", 2), df.form("move x:>$3fe8,r4", 2))

    def test_branch_targets_blank(self):
        self.assertEqual(df.form("ble func_0009c2", 2), "ble L  [2w]")
        self.assertEqual(df.form("jsr loc_000100", 2), df.form("jsr sub_03b9e2", 2))

    def test_registers_and_spaces_kept(self):
        self.assertNotEqual(df.form("move x:(r1)+,x0", 1), df.form("move x:(r2)+,x0", 1))
        self.assertNotEqual(df.form("move x:(r1)+,x0", 1), df.form("move y:(r1)+,x0", 1))

    def test_forms_of_listing(self):
        lines = ["000800: move    x:>$213,r4                     ; 64f000 000213",
                 "000804: move    x:(r4),x0                      ; 44e400", "not a line"]
        self.assertEqual(set(df.forms_of(lines)), {"move x:N,r4  [2w]", "move x:(r4),x0  [1w]"})


class Rows(unittest.TestCase):
    def test_parser_reads_only_the_register_section(self):
        text = ("# T\n\n| `not a row` (1w) | x | y |\n\n### The instruction-form register\n\nprose\n\n"
                "| form | used by | evidence |\n|---|---|---|\n"
                "| `ble L` (2w) | M | ev one |\n| `move x:(r7+N),y0` (2w) | M | ev two |\n\n## Next\n\n| `later` (1w) | a | b |\n")
        with tempfile.NamedTemporaryFile("w", suffix=".md") as f:
            f.write(text)
            f.flush()
            rows = df.register_rows(f.name)
        self.assertEqual(set(rows), {"ble L  [2w]", "move x:(r7+N),y0  [2w]"})

    def test_rows_spell_as_form_does(self):
        rows = df.register_rows()
        self.assertIn(df.form("move b,x:(r1+$37f60)", 2), rows)


if __name__ == "__main__":
    unittest.main()
