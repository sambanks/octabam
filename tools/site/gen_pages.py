#!/usr/bin/env python3
"""Render the manual site's generated pages from the manifests.

    python3 tools/site/gen_pages.py

Writes the generated pages (gitignored, so the deploy builds them fresh):

  manual/...          the manual of the published remixes, one for all of them (gen_manual.py)
  _remix-<name>.md     the module table of each published remix's overview page

Only the remixes in release.REMIXES are published. The pages are rendered at
deploy time (the Pages workflow on main; the site job of ci.yml on a PR), so
the site and the manifests cannot drift. Stdlib only, like the rest of the
tools. The registry execs the manifests, so the author submodules must be
checked out first (git submodule update --init).

Links to the repository are written as full https URLs; no literal
repository path appears in this file on purpose: tools/verify/doclinks.py
scans it too, and every path it finds must exist.
"""

import html
import pathlib
import json
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / pathlib.Path("docs") / "site" / "reference"

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)

from remix import index, registry  # noqa: E402
from remix.schema import CATEGORY_TITLE, Category  # noqa: E402

GH = "https://github.com/sambanks/octabam"

_SMALL = {"a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "of", "on", "or", "the", "to", "with", "over"}
_UPPER = {"os", "din", "dj", "eq", "bd", "usb", "midi", "cc", "cpu", "dsp", "cf", "lfo", "ata", "txtr", "amf",
          "fx1", "fx2", "lofi2", "brain", "ui", "id", "sd"}


def title_case(text: str) -> str:
    """Title Case for headings and nav labels. Tokens that already carry capitals
    or digits (device labels, acronyms) and links/code are kept as written."""
    out, started, after_colon = [], False, False
    for tok in text.replace("octabam-", "octabam ").split(" "):
        word = tok.strip(":,()")
        if re.fullmatch(r"[a-z]+(-[a-z]+)+", word):
            tok = tok.replace(word, "-".join(x.upper() if x in _UPPER else x.capitalize() for x in word.split("-")), 1)
            out.append(tok)
            started = True
            continue
        if not re.fullmatch(r"[a-z][a-z']*", word):
            out.append(tok)
            started = started or bool(re.search(r"[A-Za-z]", tok))
            after_colon = tok.endswith(":")
            continue
        if word in _UPPER:
            new = word.upper()
        elif word in _SMALL and started and not after_colon:
            new = word
        else:
            new = word.capitalize()
        out.append(tok.replace(word, new, 1))
        started = True
        after_colon = tok.endswith(":")
    return " ".join(out)


def _label(m) -> str:
    """Readable headings; manifest keys and device labels keep their spelling."""
    names = {
        "analog-bassdrum": "Analog BD",
        "ata-write-guard": "ATA write guard",
        "bar-led": "Bar LED",
        "bbd": "BBD delay",
        "busdelay": "Bus delay",
        "busverb": "Bus reverb",
        "blackpyramids-303": "BlackPyramids 303",
        "character-txtr": "Character TXTR",
        "devilish": "dEVILish",
        "dlcopy": "Effect loader (copier)",
        "dlpump": "Effect loader (sender)",
        "direct-jump-kyoti": "Direct jump (Kyoti)",
        "distorx": "DisTorX",
        "lofi-amf-fix": "Lo-Fi AMF fix",
        "octa303": "OCTA-303",
        "wavecf": "WAVE",
        "plocks-p2": "Page 2 parameter locks",
        "rec-cs1-skip": "Recorder CS1 skip",
        "rec-trig-mute": "Recorder trig mute",
        "rlen-plen": "RLEN PLEN",
        "rnd-name": "Random naming",
        "scenes-p2": "Page 2 scene locks",
        "seq": "SEQ",
        "sc-keybus-bridge": "Side-chain and Keybus bridge",
        "sc-loadmeter-bridge": "Side-chain and Load Meter bridge",
        "scope": "SCOPE",
        "tuner": "TUNER",
        "stems": "Stem recording",
        "tempo-bus": "TEMPO window",
    }
    if m.name in names:
        return title_case(names[m.name])
    acronyms = {"USB", "MIDI", "CC", "FX1", "FX2", "DSP", "CPU", "CF", "LFO", "LOFI2", "BRAIN"}
    words = m.key.replace("_", " ").split()
    return title_case(" ".join(word if word in acronyms else word.lower() for word in words))


def _account(url: str | None) -> str | None:
    """The GitHub account of an author link, whether it names the account or one of its repositories."""
    mt = re.match(r"https://github\.com/([^/]+)", url or "")
    return mt.group(1).lower() if mt else None


def _clean(name: str) -> str:
    return re.sub(r",\s*ported here$", "", name.strip())


_NAMES: dict[str, str] = {}


def who(m) -> tuple[str, str | None, tuple[str, str] | None]:
    """An author as one person however their modules spell them: (name, profile link, (repository, link)
    when the module names a repository rather than the account). The name is the one of the account's
    spellings that reads as a name (holds a space), else the handle; never "account/repository"."""
    acc = _account(m.author_url)
    if acc is None:
        return (_clean(m.author or "?"), m.author_url, None)
    if not _NAMES:
        spellings: dict[str, set] = {}
        for x in registry.modules().values():
            a = _account(x.author_url)
            if a and x.author and not x.is_stock:
                spellings.setdefault(a, set()).add(_clean(x.author))
        for a, names in spellings.items():
            plain = sorted(n for n in names if "/" not in n)
            _NAMES[a] = next((n for n in plain if " " in n), plain[0] if plain else a)
    handle = re.match(r"https://github\.com/([^/]+)", m.author_url).group(1)
    name = _NAMES.get(acc, handle)
    profile = f"https://github.com/{handle}"
    rest = m.author_url[len(profile):].strip("/")
    repo = (rest.split("/")[0], m.author_url) if rest else None
    return (name, profile, repo)


def _author(m) -> str:
    if m.is_stock:
        return "stock"
    name, url, repo = who(m)
    text = f"[{name}]({url})" if url else name
    if repo:
        verb = "ported from" if "ported here" in (m.author or "") else "from"
        text += f", {verb} [{repo[0]}]({repo[1]})"
    return text


def _records(m) -> dict:
    path = OUT.parent / "screenshots.json"
    records = json.loads(path.read_text()) if path.exists() else {}
    return records.get(m.name, {})


def _page_records(m) -> dict:
    """Screenshots still needing placement after the usage fragment's images."""
    fragment = OUT.parent / "usage" / f"{m.name}.md"
    text = fragment.read_text() if fragment.is_file() else ""
    embedded = set(re.findall(r"!\[[^\]]*\]\(\.\./\.\./img/([^\s)]+)\)", text))
    return {k: rec for k, rec in _records(m).items() if rec["image"] not in embedded}


def _module_url(m) -> str:
    d = pathlib.Path("modules") / m.name
    if (ROOT / d / "README.md").exists():
        return f"{GH}/blob/main/{d}/README.md"
    return f"{GH}/tree/main/{d}"


def _figure(record: dict) -> list[str]:
    caption = record["caption"]
    return [f"![{caption}](../../img/{record['image']})", "", f"*{caption}*", ""]


def _hero_key(m) -> str | None:
    """The screenshot shown under the title: `main` where captured, else the first."""
    recs = _page_records(m)
    return "main" if "main" in recs else next(iter(recs), None)


def hero(m) -> list[str]:
    key = _hero_key(m)
    return _figure(_page_records(m)[key]) if key else []


def screen_reference(m) -> list[str]:
    notes_path = OUT.parent / "screen-notes.json"
    notes = json.loads(notes_path.read_text()) if notes_path.exists() else {}
    hero_key = _hero_key(m)
    rest = [r for k, r in _page_records(m).items() if k != hero_key]
    lines = []
    if rest:
        lines += ["## Screen reference", ""]
        for record in rest:
            lines += _figure(record)
    if m.name in notes:
        lines += ["## Display behaviour", "", notes[m.name], ""]
    return lines


def directory_page(mods, book) -> str:
    """The feature directory: first what is in the release, by the manual's sections, each linked to its
    manual page with the remixes that have it; then every other contributed module by category, each
    linked to its page here."""
    import gen_manual
    import release
    v = release.VERSION
    manual_page = gen_manual.published_pages(book)
    names = [n for n, _ in book.official]
    lines = ["# Feature Directory", "",
             f"Every feature the project has. The first part is what is in the {v} release, with a page in the "
             "[manual](manual/index.md) for each; the second part is the rest, with a page here for each. "
             "The stock effects are described in Elektron's own manual.", "",
             f"## In {v}", "",
             "| Section | Feature | Author | In |", "|---|---|---|---|"]
    last = None
    for sec, m, _ in gen_manual._feature_rows(book, lambda n, m: None):
        ins = [gen_manual.title(n) for n in names if n in book.has.get(m.key, [])]
        lines.append(f"| {sec if sec != last else ''} | [{gen_manual.label(m)}](manual/{manual_page[m.key]}) "
                     f"| {_author(m)} | {', '.join(ins)} |")
        last = sec
    lines += ["", f"## Not in {v}", ""]
    for cat, ms in index.by_category(mods).items():
        ms = [m for m in ms if not m.is_stock and m.key not in manual_page]
        if not ms:
            continue
        lines += [f"### {CATEGORY_TITLE[cat]}", "", "| Feature | Author |", "|---|---|"]
        lines += [f"| [{_label(m)}](modules/{m.name}.md) | {_author(m)} |" for m in ms] + [""]
    return "\n".join(lines) + "\n"


def module_page(m, mods, book) -> str:
    """One page per contributed module: the usage fragment (docs/site/usage/<name>.md) when one is written,
    else the manifest's line, then where the module is and its facts."""
    fragment = OUT.parent / pathlib.Path("usage") / f"{m.name}.md"
    name, url, _ = who(m)
    byline = html.escape(name)
    if url:
        byline = f'<a href="{html.escape(url)}">{byline}</a>'
    lines = ["---", "not_in_nav: true", "---", "", f"# {_label(m)}", "", f'<p class="byline">By {byline}</p>', ""]
    import gen_manual
    import release
    v = release.VERSION
    target = gen_manual.published_pages(book).get(m.key)
    if target:
        ins = ", ".join(gen_manual.title(n) for n, _ in book.official if n in book.has.get(m.key, []))
        lines += [f"This feature is in the {v} release ({ins}): see its [manual page](../manual/{target}).", ""]
    else:
        lines += [f'!!! note "Not in {v}"', f"    This feature is not in any {v} remix.", ""]
    # Usage that leads with architecture diagrams: prose + path first, LCD
    # shots under ## Screens. Everyone else keeps a hero screen under the title.
    _DIAGRAM_FIRST = frozenset({"void", "resonator", "shatter", "stuttr"})
    if m.name in _DIAGRAM_FIRST and fragment.is_file():
        lines += [f'--8<-- "usage/{m.name}.md"', ""]
        recs = _page_records(m)
        if recs:
            lines += ["## Screens", ""]
            for record in recs.values():
                lines += _figure(record)
        notes_path = OUT.parent / "screen-notes.json"
        notes = json.loads(notes_path.read_text()) if notes_path.exists() else {}
        if m.name in notes:
            lines += ["## Display behaviour", "", notes[m.name], ""]
    else:
        lines += hero(m)
        if fragment.is_file():
            lines += [f'--8<-- "usage/{m.name}.md"', ""]
        else:
            lines += [m.doc, ""]
        lines += screen_reference(m)
    rows = [f"| Author | {_author(m)} |",
            f"| Category | {CATEGORY_TITLE[m.category or Category.REFERENCE]} |"]
    if m.requires:
        rows.append("| Requires | " + ", ".join(
            f"[{k}]({mods[k].name}.md)" if k in mods and not mods[k].is_stock else k for k in m.requires) + " |")
    if m.conflicts:
        rows.append("| Conflicts | " + "; ".join(
            (f"[{o}]({mods[o].name}.md)" if o in mods and not mods[o].is_stock else o) + f" — {why}"
            for o, why in m.conflicts) + " |")
    lines += ['??? note "Module facts"', ""]
    lines += ["    " + line if line else "" for line in [m.doc, "", "| Detail | Value |", "|---|---|"] + rows + ["", f"On GitHub: {_module_url(m)}"]]
    lines += ["", "[Feature directory](../modules.md)"]
    return "\n".join(lines) + "\n"


def main(quiet: bool = False) -> int:
    import gen_manual
    import release
    mods = registry.modules()
    official = [(n, registry.remix(n)) for n in release.REMIXES]
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = {}
    book = gen_manual.Book(mods, official)
    jobs["modules.md"] = directory_page(mods, book)
    for m in mods.values():
        if not m.is_stock:
            jobs[f"modules/{m.name}.md"] = module_page(m, mods, book)
    for name, r in official:
        jobs[f"_remix-{name}.md"] = "\n".join(gen_manual.remix_table(name, book)) + "\n"
    jobs.update(gen_manual.main(mods, official))
    for name, text in sorted(jobs.items()):
        (OUT / name).parent.mkdir(parents=True, exist_ok=True)
        (OUT / name).write_text(text)
        if not quiet:
            print(f"wrote docs/site/reference/{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
