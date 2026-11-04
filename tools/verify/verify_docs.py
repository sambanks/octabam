#!/usr/bin/env python3
"""The two Markdown copies of the registry are current, every remix has
its README, and every link between tracked files resolves.

    python3 tools/verify/verify_docs.py

README.md's module table and remixes/README.md are rendered from the
manifests and the selections by `make docs` (tools/remix/index.py --write);
this refuses a stale copy. It also refuses a remix directory without a
README.md. Eight merged modules and four remixes had no row or page on
27 Sep 2026, when the README was a hand copy nothing compared. The link
rules are in tools/verify/doclinks.py; 14 references pointed at no file on
30 Sep 2026, when nothing checked them.

The hand-written site pages link to the generated manual pages, so this
renders them first (tools/site/gen_pages.py, gitignored output); CI's docs
job runs the generator before this anyway. Every page of the published
manual (tools/site/release.py) needs an entry in the site nav
(docs/site/mkdocs.yml), and the nav names no page the manifests do not make.
"""
import pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "site"))  # gen_pages lives outside the toolpath groups
from remix import index, registry
import doclinks
import gen_manual
import gen_pages
import release

ROOT = pathlib.Path(__file__).resolve().parents[2]


def main():
    gen_pages.main(quiet=True)
    fails = [f"{p.relative_to(ROOT)} is stale: make docs" for p in index.stale()]
    for name in registry.remix_names():
        d = registry.remix_dir(name)
        if d is None:
            fails.append(f"remixes/{name}.py: a remix is a directory, remixes/{name}/remix.py "
                         f"(or remixes/test/{name}/remix.py) + README.md")
        elif not (d / "README.md").exists():
            fails.append(f"{d.relative_to(ROOT)}/README.md: missing")
    nav = (ROOT / "docs/site/mkdocs.yml").read_text()
    mods = registry.modules()
    # the manual of each published remix: every page the manifests make is in the nav, and the nav names no other
    want = {f"reference/manual/{n}/{p}.md" for n in release.REMIXES for p in gen_manual.pages_of(registry.remix(n), mods)}
    have = set(re.findall(r"reference/manual/[\w-]+/[\w/-]+\.md", nav))
    for path in sorted(want - have):
        fails.append(f"docs/site/mkdocs.yml: no nav entry for the manual page {path} (python3 tools/site/gen_manual.py --nav)")
    for path in sorted(have - want):
        fails.append(f"docs/site/mkdocs.yml: nav entry {path} is not a page of a published manual")
    fails += doclinks.check()
    for f in fails:
        print("  [FAIL]", f)
    n = len([m for m in registry.modules().values() if not m.is_stock])
    print(f"verify_docs: {n} modules, {len(registry.remix_names())} remixes, "
          f"{len(fails)} problem{'s' if len(fails) != 1 else ''}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
