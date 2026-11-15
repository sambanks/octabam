"""tools/build/cf_forms.py on fixed objdump lines, a synthetic listing and the register parser (no image, no build)."""
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/build"))
import cf_forms as cf  # noqa: E402

MACH = cf.machine()


def f(mn, ops, n):
    return cf.form(mn, ops, n)


class Form(unittest.TestCase):
    def test_register_classes(self):
        self.assertEqual(f("movel", "%d1,%a0", 2), "movel Dn,An  [2b]")
        self.assertEqual(f("movel", "%sp@+,%fp", 2), "movel An@+,An  [2b]")
        self.assertEqual(f("movel", "%d3,%d4", 2), f("movel", "%d0,%d7", 2))

    def test_size_suffix_and_length_are_part_of_the_form(self):
        self.assertNotEqual(f("movew", "%d0,%d1", 2), f("movel", "%d0,%d1", 2))
        self.assertNotEqual(f("bsrs", "0x40", 2), f("bsrw", "0x400", 4))

    def test_numbers_and_displacements_blank(self):
        self.assertEqual(f("movel", "%a0@(256),%d0", 4), f("movel", "%a1@(4),%d3", 4))
        self.assertEqual(f("addql", "#1,%a2", 2), f("addql", "#8,%a3", 2))
        self.assertEqual(f("moveal", "#1207959552,%sp", 6), "moveal #N,An  [6b]")
        self.assertEqual(f("movew", "#-124,%a2@(4)", 6), "movew #N,An@(N)  [6b]")

    def test_absolute_and_branch_targets(self):
        self.assertEqual(f("movel", "0xfc0c4000,%d2", 6), "movel ABS,Dn  [6b]")
        self.assertEqual(f("bras", "0x40000450", 2), "bras ABS  [2b]")
        self.assertEqual(f("movel", "0x4000:w,%d2", 4), "movel ABS:w,Dn  [4b]")

    def test_index_size_and_scale_are_kept(self):
        self.assertEqual(f("movel", "%a0@(0,%d0:l:4),%d1", 4), "movel An@(N,Dn:l:4),Dn  [4b]")
        self.assertNotEqual(f("movel", "%a0@(0,%d0:l:4),%d1", 4), f("movel", "%a0@(0,%d0:l:2),%d1", 4))
        self.assertNotEqual(f("movel", "%a0@(0,%d0:l),%d1", 4), f("movel", "%a0@(0,%d0:w),%d1", 4))

    def test_pc_relative_keeps_pc(self):
        self.assertEqual(f("leal", "%pc@(4a),%a0", 4), "leal %pc@(N),An  [4b]")

    def test_emac_operands(self):
        self.assertEqual(f("macw", "%d1l,%d2u,<<,%a0@+&,%d3,%acc0", 4), "macw Dnl,Dnu,<<,An@+&,Dn,ACC  [4b]")
        self.assertEqual(f("movel", "%acc1,%d0", 2), "movel ACC,Dn  [2b]")
        self.assertEqual(f("movel", "%accext23,%d0", 2), "movel ACCEXT,Dn  [2b]")
        self.assertEqual(f("movel", "%macsr,%d0", 2), "movel %macsr,Dn  [2b]")

    def test_register_list(self):
        self.assertEqual(f("moveml", "%d2-%d7/%a2,%sp@", 4), "moveml REGS,An@  [4b]")
        self.assertEqual(f("moveml", "%d0-%fp,%sp@", 4), f("moveml", "%d2-%d3,%sp@", 4))

    def test_symbol_annotations_dropped(self):
        self.assertEqual(f("bsrw", "7c <rmt_put>", 4), "bsrw ABS  [4b]")

    def test_split_operands_keeps_parenthesised_commas(self):
        self.assertEqual(cf.split_operands("%a0@(0,%d0:l),%d1"), ["%a0@(0,%d0:l)", "%d1"])


LISTING = """\
   1 0000 4FEF FF04 		lea %sp@(-252),%sp
   2 ???? 41F9 0000 	1:	lea rmt_in,%a0
   2      0000
   3 000a 7002      		moveq #2,%d0   | a comment
   4 000c 0000 0001 		.long 1
   5 0010 4E71      	lab: nop
   6 26526 2D2D 00   	dl_dash:  .asciz  "--"
   6      0000
   7 0014 4E75      	>  rts
   8 0016 0000      	  .balign 4
   9               	        .data
  10 0018 0001      	tbl:	dc.w 1
"""


class Listing(unittest.TestCase):
    def read(self, text=LISTING):
        with tempfile.NamedTemporaryFile("w", suffix=".lst") as t:
            t.write(text)
            t.flush()
            return cf.listing_instructions(t.name)

    def test_instruction_lines_only(self):
        got = self.read()
        self.assertEqual([g[0] for g in got], [1, 2, 3, 5, 7])

    def test_continuation_bytes_join_their_line(self):
        got = {g[0]: g[2] for g in self.read()}
        self.assertEqual(got[1], bytes.fromhex("4FEFFF04"))
        self.assertEqual(len(got[2]), 6)

    def test_a_data_line_does_not_take_the_next_continuation(self):
        self.assertEqual(len(dict((g[0], g[2]) for g in self.read())[5]), 2)

    def test_five_digit_address_and_macro_prefix(self):
        self.assertIn(7, [g[0] for g in self.read()])            # `>` marks a macro expansion's line
        self.assertNotIn(6, [g[0] for g in self.read()])         # a 5-digit address is read, and it is data

    def test_label_and_comment_are_not_the_mnemonic(self):
        got = {g[0]: g[1] for g in self.read()}
        self.assertTrue(got[5].endswith("nop"))
        self.assertIn("moveq", got[3])


@unittest.skipUnless(MACH, "needs m68k-elf-objdump")
class Decode(unittest.TestCase):
    def test_decode_lengths(self):
        rows = cf.decode(bytes.fromhex("4fefff04" "7001"), MACH)
        self.assertEqual([(r[1], r[2]) for r in rows], [(4, "lea"), (2, "moveq")])

    def test_unit_forms_checks_the_decoded_length(self):
        # a listing that claims a 2-byte `lea %sp@(-252),%sp`: objdump reads 4 bytes
        lst = "   1 0000 4FEF      \t\tlea %sp@(-252),%sp\n   2 0002 7001      \t\tmoveq #1,%d0\n"
        with tempfile.NamedTemporaryFile("w", suffix=".lst") as t:
            t.write(lst)
            t.flush()
            forms, problems, n = cf.unit_forms(t.name, MACH)
        self.assertEqual(n, 0)
        self.assertEqual(len(problems), 1)
        self.assertIn(":1:", problems[0])

    def test_unit_forms_clean(self):
        lst = "   1 0000 4FEF FF04 \t\tlea %sp@(-252),%sp\n   2 0004 7001      \t\tmoveq #1,%d0\n"
        with tempfile.NamedTemporaryFile("w", suffix=".lst") as t:
            t.write(lst)
            t.flush()
            forms, problems, n = cf.unit_forms(t.name, MACH)
        self.assertEqual((problems, n), ([], 2))
        self.assertIn("moveq #N,Dn  [2b]", forms)


class Rows(unittest.TestCase):
    def test_register_rows_parse(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md") as t:
            t.write("| form | how | date |\n|---|---|---|\n| `satsl Dn  [2b]` | run by the author's unit test | 2026-11-15 |\n"
                    "| prose | `not a form` | x |\n")
            t.flush()
            rows = cf.register_rows(t.name)
        self.assertEqual(list(rows), ["satsl Dn  [2b]"])

    def test_missing_table_is_empty(self):
        self.assertEqual(cf.register_rows("/nonexistent/COLDFIRE_FORMS.md"), {})


class Runs(unittest.TestCase):
    def test_code_runs_skip_comments(self):
        with tempfile.NamedTemporaryFile("w", suffix=".tsv") as t:
            t.write("# image-sha256: abc\n# runs: 2\n40000400\t4000054e\n40000550\t400006de\n")
            t.flush()
            self.assertEqual(cf.code_runs(t.name), [(0x40000400, 0x4000054e), (0x40000550, 0x400006de)])
            self.assertEqual(cf.runs_header(t.name)["image-sha256"], "abc")


if __name__ == "__main__":
    unittest.main()
