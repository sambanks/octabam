"""tools/build/postinc.py: no committed ColdFire unit steps an address register in its source operand and
reads the same register in its destination (sambanks/octabam#1134)."""
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/build"))
import postinc  # noqa: E402


class Detector(unittest.TestCase):
    def test_the_forms_it_refuses(self):
        for line in ("\tmove.b (%a0)+,(%a0,%d0.l)",              # BRAIN's sw_out, before the fix
                     "\tmove.b (%a2)+,(%a3,%a2.l)",              # COPY PROJECT's scan_restore, before the fix
                     ".L284:\tmove.l (%a1)+,4(%a1)",
                     "\tmove.w -(%a4),(%a4)",
                     "\tmovel %a0@+,%a0@(0,%d0:l)",               # MIT syntax
                     "\tmoveb %sp@+,%sp@(4)"):
            self.assertEqual(len(postinc.ambiguous(line)), 1, line)

    def test_the_forms_it_allows(self):
        for line in ("\tmove.b (%a0)+,(%a1)+",
                     "\tmove.b (%a0)+,(%a1,%d0.l)",
                     "\tmove.l (%a0),(%a0,%d0.l)",               # no side effect
                     "\tmove.b (%a10)+,(%a1)",                    # not a register name
                     "\tmove.b (%a0)+,%d0  | (%a0) in a comment",
                     "\tmovel %a0@+,%a1@"):
            self.assertEqual(postinc.ambiguous(line), [], line)


class Tree(unittest.TestCase):
    def test_no_committed_unit_has_the_form(self):
        files = subprocess.run(["git", "ls-files", "*.s", "*.S"], cwd=ROOT, capture_output=True, text=True,
                               check=True).stdout.split()
        found = [f"{f}:{n}: {line}" for f in files if not f.startswith("vendor/")
                 for n, line in postinc.ambiguous((ROOT / f).read_text(errors="replace"))]
        self.assertEqual(found, [], "an instruction steps a register its destination reads; hide one pointer "
                                    "from GCC (tools/build/postinc.py):\n" + "\n".join(found))


if __name__ == "__main__":
    unittest.main()
