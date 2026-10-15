"""Every link between tracked files resolves.

Two kinds of reference are checked:

- a relative Markdown link, `[text](path)` or `[text](path#anchor)`, in a
  tracked `.md` file: the path must exist, and an anchor into a `.md` file
  must match one of its headings (GitHub's slug rule). A link in a
  `docs/site/usage/` fragment resolves against the generated module page
  it is included into (`docs/site/reference/modules/`), because that
  page's directory is where the link will live on the site;
- a repository path to a Markdown file, `docs/...md`, `tools/...md`,
  `modules/...md` or `remixes/...md`, written anywhere in a tracked text
  file (code comments, Makefile help, docs): the file must exist.

Exempt: `docs/history/` (removed 16 Sep 2026; cited as provenance and read
with `git show 3ceba41:docs/history/<file>`), a path right after
`git show <sha>:`, a path holding a placeholder (`<name>`, `*`, `X`, `...`), and
CHANGELOG.md (a record of what was true at each image), and the tests'
fixtures under tools/verify/tests/.

A `.md` file may not contain the section sign: "BUILDING.md section 5",
never the symbol (30 Sep 2026: it reads like a mis-decoded character).
"""
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]

TEXT = {".md", ".py", ".sh", ".asm", ".s", ".S", ".inc", ".c", ".h", ".cpp",
        ".hpp", ".txt", ".yml", ".yaml", ".toml", ".json", ".swift", ""}
EXEMPT_FILES = {"CHANGELOG.md"}
EXEMPT_DIRS = ("tools/verify/tests/",)          # fixture paths, invented on purpose
MDLINK = re.compile(r"(?<![\w\]])\[(?:[^\[\]]|\[[^\]]*\])*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
REPOPATH = re.compile(r"(?<![\w./-])((?:docs|tools|modules|remixes)/[\w./+-]*?\.md)(?![\w/])")
GITSHOW = re.compile(r"git show [0-9a-f]{6,40}:\S*$")
FENCE = re.compile(r"^\s*(```|~~~)")


def tracked(root):
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True,
                         text=True, check=True).stdout
    return [p for p in out.split("\0") if p]


def slug(text, seen):
    """GitHub's heading anchor: markup stripped, lower case, punctuation
    dropped, spaces to hyphens; a repeat gets -1, -2, ..."""
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)      # [x](y) -> x
    t = re.sub(r"<[^>]+>", "", t)                             # inline html
    t = t.replace("`", "").replace("*", "").strip().lower()
    t = re.sub(r"[^\w\- ]", "", t).replace(" ", "-")
    n = seen.get(t, 0)
    seen[t] = n + 1
    return t if n == 0 else f"{t}-{n}"


_anchors = {}


def anchors(path):
    if path not in _anchors:
        seen, out, fenced = {}, set(), False
        for line in path.read_text(errors="replace").splitlines():
            if FENCE.match(line):
                fenced = not fenced
                continue
            m = None if fenced else re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
            if m:
                out.add(slug(m.group(1), seen))
        out |= set(re.findall(r'<a\s+(?:name|id)="([^"]+)"', path.read_text(errors="replace")))
        _anchors[path] = out
    return _anchors[path]


def placeholder(p):
    return "..." in p or any(c in p for c in "<>*{}$") or re.search(r"(^|/)(X|x|N|NAME|name)(\.md|/)", p)


def check(root=ROOT):
    fails = []
    for rel in tracked(root):
        path = root / rel
        if rel in EXEMPT_FILES or rel.startswith(EXEMPT_DIRS) or path.suffix not in TEXT or not path.is_file():
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        fenced = False
        for n, line in enumerate(text.splitlines(), 1):
            if path.suffix == ".md" and FENCE.match(line):
                fenced = not fenced
            if path.suffix == ".md" and "\u00a7" in line:
                fails.append(f"{rel}:{n}: the section sign -- write 'section N'")
            if path.suffix == ".md" and not fenced:
                for target in MDLINK.findall(re.sub(r"`[^`]*`", "", line)):
                    if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
                        if target.startswith("#") and target[1:] not in anchors(path):
                            fails.append(f"{rel}:{n}: no heading for {target}")
                        continue
                    ref, _, frag = target.partition("#")
                    base = (root / pathlib.Path("docs") / "site" / "reference" / "modules"
                            if rel.startswith("docs/site/usage/") else path.parent)
                    dest = (base / ref).resolve()
                    if not dest.exists():
                        fails.append(f"{rel}:{n}: link to {target} -- no such file")
                    elif frag and dest.suffix == ".md" and frag not in anchors(dest):
                        fails.append(f"{rel}:{n}: link to {target} -- no such heading")
            for m in REPOPATH.finditer(line):
                p = m.group(1)
                if p.startswith("docs/history/") or placeholder(p):
                    continue
                if GITSHOW.search(line[:m.end()]):
                    continue
                if not (root / p).exists():
                    fails.append(f"{rel}:{n}: {p} -- no such file")
    return fails
