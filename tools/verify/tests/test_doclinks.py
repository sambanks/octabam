"""tools/verify/doclinks.py: what it refuses and what it lets through, on a
throwaway git repository."""
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import doclinks  # noqa: E402

GUIDE = """# Guide

## 1a. Linux and WSL2

## Two `words` here
"""


class DocLinks(unittest.TestCase):
    def repo(self, files):
        d = pathlib.Path(tempfile.mkdtemp())
        for rel, text in files.items():
            (d / rel).parent.mkdir(parents=True, exist_ok=True)
            (d / rel).write_text(text)
        subprocess.run(["git", "init", "-q"], cwd=d, check=True)
        subprocess.run(["git", "add", "-A"], cwd=d, check=True)
        return d

    def fails(self, files):
        return doclinks.check(self.repo({"docs/guide/GUIDE.md": GUIDE, **files}))

    def test_links_and_anchors_that_resolve_pass(self):
        self.assertEqual(self.fails({"README.md":
            "[g](docs/guide/GUIDE.md) [s](docs/guide/GUIDE.md#1a-linux-and-wsl2) "
            "[w](docs/guide/GUIDE.md#two-words-here) [web](https://x.org/a.md)\n"}), [])

    def test_a_missing_file_is_refused(self):
        got = self.fails({"README.md": "[g](docs/gone/GUIDE.md)\n"})
        self.assertEqual(len(got), 2)                 # the link, and the repo path in it
        self.assertIn("README.md:1: link to docs/gone/GUIDE.md -- no such file", got)

    def test_a_missing_heading_is_refused(self):
        got = self.fails({"README.md": "[s](docs/guide/GUIDE.md#1-linux)\n"})
        self.assertEqual(got, ["README.md:1: link to docs/guide/GUIDE.md#1-linux -- no such heading"])

    def test_a_repo_path_in_code_is_checked(self):
        got = self.fails({"tools/x.py": "# see docs/firmware/GONE.md section 2\n"})
        self.assertEqual(got, ["tools/x.py:1: docs/firmware/GONE.md -- no such file"])

    def test_the_section_sign_is_refused_in_markdown(self):
        got = self.fails({"README.md": "see GUIDE \u00a70\n", "tools/x.py": "# GUIDE \u00a70\n"})
        self.assertEqual(got, ["README.md:1: the section sign -- write 'section N'"])

    def test_history_git_show_placeholders_and_code_spans_pass(self):
        self.assertEqual(self.fails({
            "tools/x.py": "# docs/history/RTOS_FORK.md s10 and git show 3ceba41:docs/firmware/OLD.md\n"
                          "# modules/<name>/README.md, docs/...md\n",
            "README.md": "`lib.a[2](gpt.cpp.o)` and `[x](nowhere.md)`\n",
            "CHANGELOG.md": "[old](docs/TIMESTRETCH_PIPELINE.md)\n"}), [])

    def test_usage_fragment_links_resolve_against_the_generated_page(self):
        self.assertEqual(self.fails({
            "docs/site/usage/x.md":
                "![knobs](../../img/x/knobs.png) [index](../modules.md)\n",
            "docs/site/reference/modules/x.md": "# X\n",
            "docs/site/reference/modules.md": "# Modules\n",
            "docs/site/img/x/knobs.png": "\n"}), [])

    def test_a_usage_fragment_link_still_must_resolve(self):
        got = self.fails({
            "docs/site/usage/x.md": "![knobs](../../img/x/gone.png)\n",
            "docs/site/reference/modules/x.md": "# X\n"})
        self.assertEqual(got,
                         ["docs/site/usage/x.md:1: link to ../../img/x/gone.png -- no such file"])


if __name__ == "__main__":
    unittest.main()
