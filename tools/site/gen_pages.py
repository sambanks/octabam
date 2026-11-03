#!/usr/bin/env python3
"""Render the manual site's generated pages from the manifests.

    python3 tools/site/gen_pages.py

Writes the generated pages (gitignored, so the deploy builds them fresh):

  manual/<remix>/...   the manual of each published remix (gen_manual.py)
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
        "bbd": "BBD delay",
        "blackpyramids-303": "BlackPyramids 303",
        "character-txtr": "Character TXTR",
        "devilish": "dEVILish",
        "dlcopy": "Effect loader (copier)",
        "dlpump": "Effect loader (sender)",
        "direct-jump-kyoti": "Direct jump (Kyoti)",
        "distorx": "DisTorX",
        "lofi-amf-fix": "Lo-Fi AMF fix",
        "octa303": "OCTA-303",
        "plocks-p2": "Page 2 parameter locks",
        "rec-trig-mute": "Recorder trig mute",
        "rlen-plen": "RLEN PLEN",
        "rnd-name": "Random naming",
        "scenes-p2": "Page 2 scene locks",
        "stems": "Stem recording",
        "tempo-bus": "Tempo controls",
    }
    if m.name in names:
        return title_case(names[m.name])
    acronyms = {"USB", "MIDI", "CC", "FX1", "FX2", "DSP", "CPU", "CF", "LFO", "LOFI2", "BRAIN"}
    words = m.key.replace("_", " ").split()
    return title_case(" ".join(word if word in acronyms else word.lower() for word in words))


def _author(m) -> str:
    if m.is_stock:
        return "stock"
    return f"[{m.author}]({m.author_url})" if m.author_url else (m.author or "?")


def _records(m) -> dict:
    path = OUT.parent / "screenshots.json"
    records = json.loads(path.read_text()) if path.exists() else {}
    return records.get(m.name, {})


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
    recs = _records(m)
    return "main" if "main" in recs else next(iter(recs), None)


def hero(m) -> list[str]:
    key = _hero_key(m)
    return _figure(_records(m)[key]) if key else []


def screen_reference(m) -> list[str]:
    notes_path = OUT.parent / "screen-notes.json"
    notes = json.loads(notes_path.read_text()) if notes_path.exists() else {}
    hero_key = _hero_key(m)
    rest = [r for k, r in _records(m).items() if k != hero_key]
    lines = []
    if rest:
        lines += ["## Screen reference", ""]
        for record in rest:
            lines += _figure(record)
    if m.name in notes:
        lines += ["## Display behaviour", "", notes[m.name], ""]
    return lines


def directory_page(mods, manual_page: dict) -> str:
    """The feature directory: first what is in the release, by the manual's sections, each linked to its
    manual page; then every other contributed module by category, each linked to its page here."""
    import gen_manual
    import release
    v = release.VERSION
    lines = ["# Feature Directory", "",
             f"Every feature the project has. The first part is what is in Octabam {v}, with a page in the "
             "[manual](manual/octabam/index.md) for each; the second part is the rest, with a page here for each. "
             "The stock effects are described in Elektron's own manual.", "",
             f"## In Octabam {v}", ""]
    mine = {k: m for k, m in mods.items() if k in manual_page and not m.is_stock}
    for folder, title in gen_manual.SECTIONS:
        ms = sorted((m for m in mine.values()
                     if (folder == "brain") == (m.key == "BRAIN") and (m.key == "BRAIN" or gen_manual.section_of(m) == folder)),
                    key=lambda m: _label(m).lower())
        if ms:
            lines += [f"### {title}", "", "| Feature | Author |", "|---|---|"]
            lines += [f"| [{_label(m)}](manual/{manual_page[m.key]}) | {_author(m)} |" for m in ms] + [""]
    lines += [f"## Not in Octabam {v}", ""]
    for cat, ms in index.by_category(mods).items():
        ms = [m for m in ms if not m.is_stock and m.key not in manual_page]
        if not ms:
            continue
        lines += [f"### {CATEGORY_TITLE[cat]}", "", "| Feature | Author |", "|---|---|"]
        lines += [f"| [{_label(m)}](modules/{m.name}.md) | {_author(m)} |" for m in ms] + [""]
    return "\n".join(lines) + "\n"


def module_page(m, mods, manual_page: dict) -> str:
    """One page per contributed module: the usage fragment (docs/site/usage/<name>.md) when one is written,
    else the manifest's line, then where the module is and its facts."""
    fragment = OUT.parent / pathlib.Path("usage") / f"{m.name}.md"
    who = html.escape(m.author or "?")
    if m.author_url:
        who = f'<a href="{html.escape(m.author_url)}">{who}</a>'
    lines = ["---", "not_in_nav: true", "---", "", f"# {_label(m)}", "", f'<p class="byline">By {who}</p>', ""]
    target = manual_page.get(m.key)
    import release
    v = release.VERSION
    if target:
        lines += [f"This feature is in Octabam {v}: see its [manual page](../manual/{target}).", ""]
    else:
        lines += [f'!!! note "Not in Octabam {v}"', f"    This feature is not in the {v} image.", ""]
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
    manual_page = gen_manual.published_pages(mods, official)
    jobs["modules.md"] = directory_page(mods, manual_page)
    for m in mods.values():
        if not m.is_stock:
            jobs[f"modules/{m.name}.md"] = module_page(m, mods, manual_page)
    for name, r in official:
        jobs[f"_remix-{name}.md"] = "\n".join(gen_manual.remix_table(name, r, mods)) + "\n"
    jobs.update(gen_manual.main(mods, official))
    for name, text in sorted(jobs.items()):
        (OUT / name).parent.mkdir(parents=True, exist_ok=True)
        (OUT / name).write_text(text)
        if not quiet:
            print(f"wrote docs/site/reference/{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
