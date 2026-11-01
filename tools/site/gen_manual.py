#!/usr/bin/env python3
"""Render the manual of each published remix from the manifests.

    python3 tools/site/gen_manual.py          # also run by gen_pages.py
    python3 tools/site/gen_manual.py --nav    # the manual's nav block for mkdocs.yml

Writes, gitignored like the rest of the generated site, under
reference/manual/<remix>/ :

  index.md                  the introduction, installing, the contents
  <section>/<module>.md     one page per module, in the section of PLACE
  brain/<part>.md           BRAIN, one page per part of it
  credits.md

The sections are the order a musician meets things: effects, machines, the
sequencer, Parts and scenes, MIDI and USB, BRAIN, utilities, fixes, and what
runs behind the scenes. A section the remix has no module in gets no pages.
Stock effects are not documented here.

What can be read from the manifests is: which chooser an effect is in, the knob
layout of its two pages (A to F, the MODE renames), the settings and what this
remix sets them to, what a module needs. The prose is the hand-written usage
fragment of each module (the site's usage directory); its own Parameters table
is dropped, since the knobs are printed from the manifest. A module with no
fragment gets its manifest line, so the manual never has a hole. BRAIN's pages
are the fragments docs/site/manual/brain-<part>.md.

Only the remixes in release.REMIXES have a manual. The pages are listed by hand
in the nav of mkdocs.yml (`--nav` prints the block); tools/verify/verify_docs.py
refuses a nav that does not match pages_of().
"""

import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)

import gen_pages  # noqa: E402
from gen_pages import OUT, _author, _label, _records, title_case  # noqa: E402
from remix.schema import Category, Formatter, Option, Binary, Number, Pin, Trigger, Blob  # noqa: E402

USAGE = OUT.parent / pathlib.Path("usage")
INTROS = OUT.parent / pathlib.Path("manual")

# (folder, title) in the order a reader meets them.
SECTIONS = (
    ("effects", "Effects"),
    ("machines", "Machines"),
    ("sequencer", "Sequencer and recording"),
    ("parts", "Parts, Kits and scenes"),
    ("midi-usb", "MIDI and USB"),
    ("brain", "BRAIN"),
    ("utilities", "Utilities"),
    ("fixes", "Fixes to stock behaviour"),
    ("inside", "Behind the scenes"),
)

# Where a module's page goes, by registry key. A module not named here goes by its
# category (BY_CATEGORY), so a new module is never left out of the manual.
PLACE = {
    "OCTA303": "machines",
    "DIRECT_JUMP_KYOTI": "sequencer", "RELOAD_FROM_PROJECT": "sequencer", "RLEN PLEN": "sequencer",
    "REC_TRIG_MUTE": "sequencer", "REC THRESHOLD": "sequencer", "PATTERN MUTE": "sequencer",
    "MUTE_MODES": "sequencer", "SCALE QUANTIZER": "sequencer", "QUANTIZE_LIVE_REC_TOGGLE": "sequencer",
    "EUCLID FILL": "sequencer", "TRACK PATTERNS": "sequencer", "TUNER": "sequencer",
    "KITS": "parts", "MIDI SCENES": "parts", "SCENES P2": "parts", "PLOCKS P2": "parts", "MORPH": "parts",
    "CC MAP": "midi-usb", "CC FEEDBACK": "midi-usb", "USB": "midi-usb",
    "BRAIN": "brain",
    "COPY PROJECT": "utilities", "BUFFER SAVER": "utilities", "FX2 LOCK": "utilities",
    "MODE DEFAULTS": "utilities", "REMIX SWITCH": "utilities",
    "LOFI AMF FIX": "fixes", "RECORDER LOOP FIX": "fixes", "BATCH_BUGFIXES": "fixes",
    "ERASE_EMPTY_TRIGLESS_LOCKS": "fixes", "ATA WRITE GUARD": "fixes",
    "EVENTS": "inside", "STORE": "inside", "HOOKS": "inside", "MEMORY": "inside",
    "DLPUMP": "inside", "DLCOPY": "inside", "LOAD METER": "inside",
}
BY_CATEGORY = {
    Category.TRACK: "effects", Category.MACHINES: "sequencer", Category.PARTS: "parts",
    Category.MIDI_USB: "midi-usb", Category.SETTINGS: "inside", Category.UTILITIES: "utilities",
    Category.FIXES: "fixes", Category.BUS: "utilities", Category.REFERENCE: "inside",
}

# BRAIN is one section with a page per part of it; the text of each is docs/site/manual/brain-<part>.md.
BRAIN_PAGES = (
    ("index", "BRAIN"), ("templates", "Templates"), ("remixes", "Remixes"), ("settings", "Settings"),
    ("performance", "Performance"), ("log", "Log"), ("about", "About"), ("files", "Files on the card"),
)

# Screenshots of the manifests' records that show another remix's screen (FX2 LOCK's was taken on the bus
# remix's delay host), not shown in this manual.
HIDE_SHOTS = {("fx2-lock", "chooser")}

TITLES = {"octabam": "Octabam"}
OVERVIEW = {"octabam": "remix-octabam.md"}
KNOB = "ABCDEF"


def title(name: str) -> str:
    return TITLES.get(name, title_case(name.replace("-", " ")))


def manual_title(name: str) -> str:
    return f"{title(name)} Remix Manual"


# ---- placement ----------------------------------------------------------

def _drawn(m) -> bool:
    return m.menu is not None and any(p.active for p in m.params)


def section_of(m) -> str:
    if m.key in PLACE:
        return PLACE[m.key]
    return "effects" if _drawn(m) else BY_CATEGORY.get(m.category or Category.REFERENCE, "inside")


def placed(r, mods) -> dict[str, list]:
    """The documented modules of one remix by section, each section by label. BRAIN has its own pages."""
    out: dict[str, list] = {}
    for k in r.modules:
        m = mods.get(k)
        if m is None or m.is_stock or m.key == "BRAIN":
            continue
        out.setdefault(section_of(m), []).append(m)
    return {s: sorted(ms, key=lambda m: _label(m).lower()) for s, ms in out.items()}


def page_of(m) -> str:
    """The module's page under the manual folder, without the extension."""
    return f"brain/index" if m.key == "BRAIN" else f"{section_of(m)}/{m.name}"


def pages_of(r, mods) -> list[str]:
    """The page names (no extension) of one remix's manual, in nav order."""
    groups = placed(r, mods)
    out = ["index"]
    for folder, _ in SECTIONS:
        if folder == "brain":
            if "BRAIN" in r.modules:
                out += [f"brain/{p}" for p, _ in BRAIN_PAGES]
        else:
            out += [f"{folder}/{m.name}" for m in groups.get(folder, [])]
    return out + ["credits"]


def _rel(here: str, target: str) -> str:
    """A link from the page `here` to the page `target` (both without the extension)."""
    return os.path.relpath(target + ".md", os.path.dirname(here) or ".")


def _up(here: str) -> str:
    """From a page of reference/manual/<remix>/ to the site root."""
    return "../" * (3 + here.count("/"))


# ---- the fragment -------------------------------------------------------

def _relink(text: str, here: str, r, mods, extra: dict | None = None) -> str:
    """A fragment is written for a page of the site's reference/modules/: its site
    links climb two levels and its sibling links are bare file names. Both are
    pointed at where this page is; a sibling that is not in this manual loses its link."""
    known = {m.name: page_of(m) for ms in placed(r, mods).values() for m in ms}
    known["brain"] = "brain/index"
    known.update(extra or {})
    up = _up(here)
    text = re.sub(r"\]\(\.\./\.\./brain\.md(#[\w-]+)?\)", lambda mt: "](" + _rel(here, "brain/index") + (mt.group(1) or "") + ")", text)
    text = re.sub(r"\]\(\.\./\.\./(?!\.\./)", "](" + up, text)

    def sibling(mt):
        label, name = mt.group(1), mt.group(2)
        return f"[{label}]({_rel(here, known[name])})" if name in known else label

    return re.sub(r"\[([^\]]+)\]\((?!https?:|#|\.\./|/)([\w-]+)\.md\)", sibling, text)


def _without_parameters(text: str) -> str:
    """Drop a fragment's own Parameters table: the manual prints the knobs
    from the manifest, the one place a knob's name, range and default are declared."""
    return re.sub(r"(?ms)^## Parameters\n.*?(?=^## |\Z)", "", text).strip()


def _fragment(m, here: str, r, mods) -> str | None:
    path = USAGE / f"{m.name}.md"
    if not path.is_file():
        return None
    text = path.read_text().strip()
    if _drawn(m):
        text = _without_parameters(text)
    return _relink(text, here, r, mods)


def _shots(m) -> dict:
    return {k: rec for k, rec in _records(m).items() if (m.name, k) not in HIDE_SHOTS}


def _figure(record: dict, here: str) -> list[str]:
    caption = record["caption"]
    return [f"![{caption}]({_up(here)}img/{record['image']})", "", f"*{caption}*", ""]


# ---- the facts ----------------------------------------------------------

def _values(p) -> str:
    """What a knob's range reads as on the panel."""
    if p.labels:
        # a long list (STEPS 1 to 64, a note, a frequency) reads as its ends
        return " / ".join(p.labels) if len(p.labels) <= 8 else f"{p.labels[0]} to {p.labels[-1]}"
    if p.formatter is Formatter.BIPOLAR:
        return "−64 to +63"
    if p.count and p.count != 128:
        return f"1 to {p.count}" if p.formatter in (Formatter.STEPPED, Formatter.WIDE_STEPPED) else f"0 to {p.count - 1}"
    return "0 to 127"


def _default(p) -> str:
    if p.default is None:
        return "—"
    if p.labels:
        return p.labels[p.default]
    if p.formatter is Formatter.BIPOLAR:
        return f"{p.default - 64:+d}" if p.default != 64 else "0"
    return str(p.default)


def controls(m) -> list[str]:
    """The two effect pages as the panel lays them out, then each knob."""
    lines = ["## Controls", "",
             "Each effect has two pages of six knobs, A to F; the PAGE keys switch between them.", ""]
    for page in (0, 1):
        slots = range(page * 6, page * 6 + 6)
        if not any(m.params[i].active for i in slots):
            continue
        lines += [f"**Page {page + 1}**", "",
                  "| Knob | Name | Values | Default | What it does |", "|---|---|---|---|---|"]
        for i in slots:
            p = m.params[i]
            if not p.active:
                continue
            doc = (p.doc or "").replace("|", "\\|")
            lines.append(f"| {KNOB[i % 6]} | {p.name.decode()} | {_values(p)} | {_default(p)} | {doc} |")
        lines.append("")
    if m.mode_slot is not None and m.mode_views:
        mode = m.params[m.mode_slot]
        renames = [(v, {s: n.decode() for s, n in v.names.items()}) for v in m.mode_views if v.names]
        if renames:
            lines += [f"**What {mode.name.decode()} renames**", "",
                      "| " + mode.name.decode() + " | Knob | Reads as |", "|---|---|---|"]
            for v, names in renames:
                label = mode.labels[v.mode] if mode.labels and v.mode < len(mode.labels) else str(v.mode)
                for slot, name in sorted(names.items()):
                    lines.append(f"| {label} | {KNOB[slot % 6]} on page {slot // 6 + 1} "
                                 f"({m.canon_name(slot) or '—'}) | {name} |")
            lines.append("")
    return lines


def _kind_text(k) -> str:
    if isinstance(k, Binary):
        return "off / on"
    if isinstance(k, Option):
        return " / ".join(k.labels)
    if isinstance(k, Number):
        return f"{k.min} to {k.max}" + (f" {k.unit}" if k.unit else "")
    if isinstance(k, Trigger):
        return "an action"
    if isinstance(k, Blob):
        return "text"
    return "?"


def _setting_value(k, v) -> str:
    if isinstance(k, Binary):
        return "on" if v else "off"
    if isinstance(k, Option):
        i = k.index(v)
        return k.labels[i] if i is not None else str(v)
    return str(v)


def settings(m, r) -> list[str]:
    """The module's settings with the value this remix gives them: a pinned
    setting has no menu row and cannot be changed on the unit."""
    shown = [s for s in m.settings if s.apply.value != "build"]
    if not shown or m.store is None:
        return []
    lines = ["## Settings", "",
             "| Setting | Values | In this image | Takes effect | What it does |", "|---|---|---|---|---|"]
    applies = {"live": "at once", "callback": "after a load or an edit", "next_boot": "at the next boot"}
    for s in shown:
        mine = r.settings.get((m.store.id, s.name), s.default)
        if isinstance(mine, Pin):
            now = f"{_setting_value(s.kind, mine.value)} (fixed)"
        else:
            now = _setting_value(s.kind, mine)
        when = applies[s.apply.value]
        if s.apply.value != "build":
            when += " (stored with the project)" if s.scope.value == "project" else " (stored on the card)"
        doc = (s.doc or "").replace("|", "\\|")
        lines.append(f"| {s.name} | {_kind_text(s.kind)} | {now} | {when} | {doc} |")
    return lines + [""]


def relations(m, mods, here: str, r) -> list[str]:
    known = {x.key: page_of(x) for ms in placed(r, mods).values() for x in ms}

    def ref(key):
        if key not in mods:
            return key
        label = _label(mods[key])
        return f"[{label}]({_rel(here, known[key])})" if key in known else label

    out = []
    if m.requires:
        out.append("Needs " + ", ".join(ref(k) for k in m.requires) + " in the same image.")
    return [" ".join(out), ""] if out else []


def _on_fx2(m, r) -> bool:
    """FX2 unless the module has a SLOTS build setting that this remix leaves
    on FX1 (the stations: an FX2 instance there is a dry pass)."""
    for s in m.settings:
        if s.name == "SLOTS" and isinstance(s.kind, Option) and m.store is not None:
            mine = r.settings.get((m.store.id, s.name), s.default)
            mine = mine.value if isinstance(mine, Pin) else mine
            i = s.kind.index(mine)
            return i is not None and "FX2" in s.kind.labels[i]
    return True


def where(m, r) -> str | None:
    """Which chooser an effect is in, read from the remix."""
    if m.menu is None or m.is_stock:
        return None
    on = [n for n, ok in (("FX1", m.key in r.fx1), ("FX2", _on_fx2(m, r))) if ok]
    text = " and ".join(on)
    if m.key in r.locked:
        text += " (locked to its host track; the chooser cannot change it)"
    if m.menu.replaces:
        text += f", in place of {m.menu.replaces}"
    return text


# ---- pages ---------------------------------------------------------------

def module_page(m, r, mods) -> str:
    here = page_of(m)
    lines = [f"# {_label(m)}", "", f"*By {_author(m)}.*", ""]
    place = where(m, r)
    if place:
        lines += [f"**Chooser:** {place}.", ""]
    recs = _shots(m)
    key = "main" if "main" in recs else next(iter(recs), None)
    if key:
        lines += _figure(recs[key], here)
    frag = _fragment(m, here, r, mods)
    lines += [frag if frag else m.doc, ""]
    if _drawn(m):
        lines += controls(m)
    lines += settings(m, r)
    lines += relations(m, mods, here, r)
    rest = [rec for k, rec in recs.items() if k != key]
    if rest:
        lines += ["## Screens", ""]
        for rec in rest:
            lines += _figure(rec, here)
    return "\n".join(lines).rstrip() + "\n"


def brain_page(part: str, label: str, r, mods) -> str:
    here = f"brain/{part}"
    path = INTROS / f"brain-{part}.md"
    text = path.read_text().strip() if path.is_file() else mods["BRAIN"].doc
    lines = [f"# {label}", ""]
    if part == "index":
        lines += [f"*By {_author(mods['BRAIN'])}.*", ""]
    lines += [_relink(text, here, r, mods, {p: f"brain/{p}" for p, _ in BRAIN_PAGES}), ""]
    if part == "index":
        lines += ["## The parts of BRAIN", ""]
        lines += [f"- [{t}]({p}.md)" for p, t in BRAIN_PAGES if p != "index"] + [""]
    return "\n".join(lines).rstrip() + "\n"


def _credit_name(entries) -> str:
    """One name for an author whose modules spell it differently: a real name over a handle."""
    names = sorted({a for a, _ in entries if a})
    return next((n for n in names if " " in n), names[0] if names else "stock")


def credits_page(r, mods) -> str:
    by_who: dict[str, list] = {}
    for ms in placed(r, mods).values():
        for m in ms:
            by_who.setdefault(m.author_url or (m.author or ""), []).append(m)
    if "BRAIN" in r.modules:
        by_who.setdefault(mods["BRAIN"].author_url or mods["BRAIN"].author, []).append(mods["BRAIN"])
    body = ["Every feature in this image was written by someone, and is credited here.", ""]
    for who, ms in sorted(by_who.items(), key=lambda kv: _credit_name([(m.author, m.author_url) for m in kv[1]]).lower()):
        name = _credit_name([(m.author, m.author_url) for m in ms])
        link = f"[{name}]({ms[0].author_url})" if ms[0].author_url else name
        body.append(f"- {link}: " + ", ".join(sorted({_label(m) for m in ms}, key=str.lower)))
    return "\n".join([f"# Credits", ""] + body) + "\n"


def index_page(name: str, r, mods) -> str:
    heading = manual_title(name)
    groups = placed(r, mods)
    intro = [f"The manual for the **{title(name)}** image: Octatrack OS 1.40C with the features listed "
             f"here added, each credited to the person who wrote it.", ""]
    if name in OVERVIEW:
        intro += [f"For the short version, see the [{title(name)} overview]({_up('index')}{OVERVIEW[name]}).", ""]
    written = INTROS / f"{name}.md"
    text = written.read_text().strip() if written.is_file() else f"### About {title(name)}\n\n{r.doc}"
    intro += [text, ""]
    intro += ["### Conventions", "",
              "Names in capitals are what the unit's screen prints. Effects sit on the FX1 and FX2 keys; "
              "each has two pages of six knobs, A to F, reached with the PAGE keys as on any Octatrack effect. "
              "**Bold labels** are controls and menu items; an arrow is a menu path, as in "
              "**PROJ → BRAIN → TEMPLATES**; a plus sign is a key combination (hold **FUNC** while pressing "
              "the other key).", ""]
    intro += ["### What is in this image", "", "| Section | Features |", "|---|---|"]
    for folder, sec in SECTIONS:
        if folder == "brain":
            if "BRAIN" in r.modules:
                intro.append(f"| [{sec}](brain/index.md) | " + ", ".join(
                    f"[{t}](brain/{p}.md)" for p, t in BRAIN_PAGES if p != "index") + " |")
            continue
        ms = groups.get(folder, [])
        if ms:
            intro.append(f"| {sec} | " + ", ".join(f"[{_label(m)}]({folder}/{m.name}.md)" for m in ms) + " |")
    intro += ["", "[Credits](credits.md)", "",
              "### Installing", "",
              f"Build the image from your own copy of OS 1.40C and install it as described in "
              f"[Build and Install]({_up('index')}web-builder.md). Nothing from Elektron is on this site; "
              f"the builder patches your copy in your browser. After the flash, SYSTEM STATUS → OS VERSION "
              f"shows `{r.name.upper()}` and the build number.", "",
              f"Back up the card first. To go back to stock, follow [Safety and Recovery]({_up('index')}safety.md).", ""]
    return "\n".join([f"# {heading}", ""] + intro) + "\n"


def manual(name: str, r, mods) -> dict[str, str]:
    """The pages of one remix's manual, keyed by file name."""
    out = {"index.md": index_page(name, r, mods), "credits.md": credits_page(r, mods)}
    for ms in placed(r, mods).values():
        for m in ms:
            out[f"{page_of(m)}.md"] = module_page(m, r, mods)
    if "BRAIN" in r.modules:
        for part, label in BRAIN_PAGES:
            out[f"brain/{part}.md"] = brain_page(part, label, r, mods)
    return out


def remix_table(name: str, r, mods) -> list[str]:
    """The module table of the remix's overview page: every feature of the image with its page and author."""
    rows = ["| Feature | Author |", "|---|---|"]
    stock = [mods[k] for k in r.modules if k in mods and mods[k].is_stock]
    base = f"reference/manual/{name}/"
    for folder, sec in SECTIONS:
        if folder == "brain":
            if "BRAIN" in r.modules:
                rows.append(f"| [BRAIN]({base}brain/index.md) | {_author(mods['BRAIN'])} |")
            continue
        for m in placed(r, mods).get(folder, []):
            rows.append(f"| [{_label(m)}]({base}{folder}/{m.name}.md) | {_author(m)} |")
    rows += [f"| {_label(m)} | stock |" for m in sorted(stock, key=lambda m: _label(m).lower())]
    return rows


def published_pages(mods, official) -> dict[str, str]:
    """Module key -> its page under reference/manual/, for every module in a published manual."""
    out: dict[str, str] = {}
    for name, r in official:
        for ms in placed(r, mods).values():
            for m in ms:
                out.setdefault(m.key, f"{name}/{page_of(m)}.md")
        if "BRAIN" in r.modules:
            out.setdefault("BRAIN", f"{name}/brain/index.md")
    return out


def _q(label: str) -> str:
    """A nav label as YAML: quoted when it holds a colon or a quote."""
    return '"' + label.replace('"', '\\"') + '"' if re.search(r'[:#"\']', label) else label


def nav(name: str, r, mods) -> list[str]:
    """The manual's block of the mkdocs nav, four spaces to a level."""
    base = f"reference/manual/{name}/"
    groups = placed(r, mods)
    out = [f"  - {manual_title(name)}:", f"      - Introduction: {base}index.md"]
    for folder, sec in SECTIONS:
        if folder == "brain":
            if "BRAIN" in r.modules:
                out.append(f"      - {sec}:")
                out += [f"          - {t}: {base}brain/{p}.md" for p, t in BRAIN_PAGES]
            continue
        ms = groups.get(folder, [])
        if ms:
            out.append(f"      - {sec}:")
            out += [f"          - {_q(_label(m))}: {base}{folder}/{m.name}.md" for m in ms]
    out.append(f"      - Credits: {base}credits.md")
    return out


def main(mods, official) -> dict[str, str]:
    """The manual pages, keyed by their path under reference/."""
    jobs = {}
    for name, r in official:
        for page, text in manual(name, r, mods).items():
            jobs[f"manual/{name}/{page}"] = text
    return jobs


if __name__ == "__main__":
    if "--nav" in sys.argv:
        from remix import registry
        import release
        for n in release.REMIXES:
            print("\n".join(nav(n, registry.remix(n), registry.modules())))
        sys.exit(0)
    sys.exit(gen_pages.main())
