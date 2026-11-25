"""tools/build/cf_scan.py on fixed objdump lines, synthetic sources and synthetic unit ranges (no image, no build)."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/build"))
import cf_scan as S  # noqa: E402


def cycles(rows):
    return [(r[4], r[5]) for r in S.model([(2 * i, mn, ops) for i, (mn, ops) in enumerate(rows)],
                                          {2 * i: 1 for i in range(len(rows))})]


class Table(unittest.TestCase):
    """MCF54455RM Tables 3-13..3-20, as cf_timing.py transcribes them."""

    def test_selftest(self):
        self.assertEqual(S.selftest(), 0)

    def test_moves(self):
        self.assertEqual(S.price("movel", "%a0@(4),%d0"), (1, ""))          # (d16,Ay) -> Dx: 1(1/0)
        self.assertEqual(S.price("movel", "%d0,%a1@"), (1, ""))             # Dy -> (Ax): 1(0/1)
        self.assertEqual(S.price("movel", "%a0@,%a1@+"), (2, ""))           # (Ay) -> (Ax)+: 2(1/1)
        self.assertEqual(S.price("movel", "%d2,%a0@(0,%d0:l:4)"), (2, ""))  # Dy -> (d8,Ax,Xi*SF): 2(0/1)
        self.assertEqual(S.price("moveq", "#1,%d0"), (1, ""))

    def test_dear_forms(self):
        self.assertEqual(S.price("nop", "")[0], 6)
        self.assertEqual(S.price("tpf", "")[0], 1)
        self.assertEqual(S.price("jsr", "%a0@")[0], 5)
        self.assertEqual(S.price("jsr", "0x40001000")[0], 1)
        self.assertEqual(S.price("movel", "%d0,%macsr")[0], 8)
        self.assertEqual(S.price("movel", "%d0,%mask")[0], 7)
        self.assertEqual(S.price("divul", "%d1,%d0")[0], 35)
        self.assertEqual(S.price("mulsl", "%d1,%d0")[0], 4)
        self.assertEqual(S.price("rts", "")[0], 2)

    def test_movem_counts_registers(self):
        self.assertEqual(S.price("moveml", "%d2-%d7/%a2-%a6,%sp@")[0], 11)
        self.assertEqual(S.price("moveml", "%d0-%d1/%a0-%a1,%sp@")[0], 4)

    def test_unknown_is_flagged(self):
        self.assertEqual(S.price("frobl", "%d0")[1], "unpriced")


class Stalls(unittest.TestCase):
    def test_base_written_then_used(self):
        self.assertEqual(cycles([("lea", "%a0@(4),%a1"), ("movel", "%a1@,%d2")])[1], (1, 2))

    def test_index_scaled_by_four(self):
        # the manual's own example: muls.l then move.l (a0,d0.l*4): three cycles
        self.assertEqual(cycles([("mulsl", "%d1,%d0"), ("movel", "%a0@(0,%d0:l:4),%d1")])[1], (2, 3))

    def test_postincrement_base_written_before_stalls(self):
        self.assertEqual(cycles([("moveal", "%d0,%a0"), ("movel", "%a0@+,%d1")])[1], (1, 2))

    def test_postincrement_result_does_not_stall(self):
        self.assertEqual(cycles([("movel", "%a0@+,%d1"), ("movel", "%a0@,%d2")])[1], (1, 0))

    def test_unrelated_register_does_not_stall(self):
        self.assertEqual(cycles([("lea", "%a0@(4),%a1"), ("movel", "%a2@,%d2")])[1], (1, 0))

    def test_loop_head_stalls_on_entry_only(self):
        # moveq #4,%d1 once, then a five-pass loop whose head uses d1 as its index: one stall, not five
        rows = [(0, "moveq", "#4,%d1"), (2, "mvzb", "%a1@(0,%d1:l),%d0"), (6, "addl", "%d0,%d2"),
                (8, "subql", "#1,%d1"), (10, "bpls", "0x2")]
        res = S.model(rows, {0: 1, 2: 5, 6: 5, 8: 5, 10: 5})
        self.assertEqual(res[1][5], 2)
        self.assertEqual(sum(r[7] for r in res), 2)

    def test_straight_line_stall_counts_every_time(self):
        res = S.model([(0, "lea", "%a0@(4),%a1"), (4, "movel", "%a1@,%d2")], {0: 7, 4: 7})
        self.assertEqual(res[1][7], 14)

    def test_accumulator_read_after_mac(self):
        mac = ("macl", "%d0,%d1,%acc0")
        self.assertEqual(cycles([mac, ("movclrl", "%acc0,%d3")])[1], (1, 3))
        self.assertEqual(cycles([mac, ("moveq", "#0,%d5"), ("movclrl", "%acc0,%d3")])[2], (1, 2))
        self.assertEqual(cycles([mac, ("moveq", "#0,%d5"), ("moveq", "#0,%d6"), ("moveq", "#0,%d7"),
                                 ("movclrl", "%acc0,%d3")])[4], (1, 0))


class C07(unittest.TestCase):
    def sites(self, src):
        return [(s[1], s[2]) for s in S.c07_sites(src)]

    def test_zero_extension_and_its_consumer(self):
        self.assertEqual(self.sites("\tmoveq #0,%d0\n\tmove.b (%a0),%d0\n\tcmp.l #5,%d0\n"), [("Z1", "SAFE")])
        self.assertEqual(self.sites("\tmoveq #0,%d0\n\tmove.b (%a0),%d0\n\tbeq 1f\n"), [("Z1", "SAFE")])
        self.assertEqual(self.sites("\tmoveq #0,%d0\n\tmove.b (%a0),%d0\n\tbmi 1f\n"), [("Z1", "REVIEW")])
        self.assertEqual(self.sites("\tmoveq #0,%d0\n\tmove.b (%a0),%d0\n1:\tadd.l %d0,%d1\n"), [("Z1", "REVIEW")])
        self.assertEqual(self.sites("\tmoveq #0,%d0\n\tmove.b (%a0),%d0\n\tlea 4(%a0),%a0\n\ttst.l %d0\n"),
                         [("Z1", "SAFE")])

    def test_mit_syntax(self):
        self.assertEqual(self.sites("        moveq   #0,%d1\n        moveb   %a0@(8,%d7:l),%d1\n        movel   %d1,%d2\n"),
                         [("Z1", "SAFE")])

    def test_other_shapes_keep_every_flag(self):
        self.assertEqual(self.sites("\tmove.b (%a0),%d0\n\tand.l #0xff,%d0\n\tbmi 1f\n"), [("Z2", "SAFE")])
        self.assertEqual(self.sites("\tmove.b (%a0),%d0\n\textb.l %d0\n"), [("S1", "SAFE")])
        self.assertEqual(self.sites("\tmove.w (%a0),%d0\n\text.l %d0\n"), [("S2", "SAFE")])

    def test_spacer_hides_an_address_use_stall(self):
        self.assertEqual(self.sites("\tlea lm_raw,%a1\n\tmoveq #0,%d0\n\tmove.b (%a1),%d0\n\tcmp.l #5,%d0\n"),
                         [("Z1", "SPACER")])
        self.assertEqual(self.sites("\tmoveq #4,%d1\n\tmoveq #0,%d0\n\tmove.b 0(%a1,%d1.l),%d0\n\ttst.l %d0\n"),
                         [("Z1", "SPACER")])
        self.assertEqual(self.sites("        moveal  %d2,%a0\n        moveq   #0,%d1\n        moveb   %a0@,%d1\n"
                                    "        orl     %d1,%d0\n"), [("Z1", "SPACER")])
        # a loop's head: the entry falls through from the writer (price decides whether the swap still pays)
        self.assertEqual(self.sites("\tlea x,%a1\n2:\tmoveq #0,%d0\n\tmove.b (%a1),%d0\n\ttst.l %d0\n"),
                         [("Z1", "SPACER")])
        # the writer is another register, or a branch comes before: no stall to hide
        self.assertEqual(self.sites("\tlea lm_raw,%a2\n\tmoveq #0,%d0\n\tmove.b (%a1),%d0\n\ttst.l %d0\n"),
                         [("Z1", "SAFE")])
        self.assertEqual(self.sites("\tbne.s 1f\n\tmoveq #0,%d0\n\tmove.b (%a1),%d0\n\ttst.l %d0\n"),
                         [("Z1", "SAFE")])
        self.assertEqual(self.sites("\tbra.s 3f\n2:\tmoveq #0,%d0\n\tmove.b (%a1),%d0\n\ttst.l %d0\n"),
                         [("Z1", "SAFE")])

    def test_motorola_operands_in_mit_form(self):
        self.assertEqual(S.mit("(%a0)"), "%a0@")
        self.assertEqual(S.mit("(%a0)+"), "%a0@+")
        self.assertEqual(S.mit("-(%sp)"), "%sp@-")
        self.assertEqual(S.mit("16(%a1)"), "%a1@(16)")
        self.assertEqual(S.mit("4(%a0,%d1.l*4)"), "%a0@(4,%d1:l:4)")
        self.assertEqual(S.mit("-4(%a0)"), "%a0@(-4)")
        self.assertEqual(S.mit("S_LATCHED(%a0)"), "%a0@(0)")
        self.assertEqual(S.mit("%a0@(0,%d7:l)"), "%a0@(0,%d7:l)")

    def test_not_a_site(self):
        self.assertEqual(self.sites("\tmoveq #0,%d0\n\tmove.b (%a0),%d1\n"), [])          # another register
        self.assertEqual(self.sites("\tmoveq #1,%d0\n\tmove.b (%a0),%d0\n"), [])          # not a zero
        self.assertEqual(self.sites("\tmoveq #0,%d0\n1:\tmove.b (%a0),%d0\n"), [])        # a label between


class Attribution(unittest.TestCase):
    def test_units_caves_and_the_frame_isr(self):
        ranges = sorted([(0x40a00000, 0x40a00100, "LOAD METER", "meter"), (0x400d0000, 0x400d0010, "STORE", "cave")])
        syms = [(0x40a00000, "lm_in"), (0x40a00080, "lm_out")]
        lines = ["40a00000 5 10", "40a00084 5 30", "400d0004 5 7", "4000aad0 5 100", "40001000 0 50", "junk"]
        rep = S.attribute(lines, ranges, syms)
        o = rep["owners"]
        self.assertEqual(rep["total"], 197)
        self.assertEqual(o["LOAD METER"]["samples"], 40)
        self.assertEqual(o["LOAD METER"]["hottest"], [("lm_out", 30), ("lm_in", 10)])
        self.assertEqual(o["STORE"]["samples"], 7)
        self.assertEqual(o["stock: frame ISR"]["samples"], 100)
        self.assertEqual(o["stock"]["by_mask"], {0: 50})


if __name__ == "__main__":
    unittest.main()
