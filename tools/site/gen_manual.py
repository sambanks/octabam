#!/usr/bin/env python3
"""Render the manual of the published remixes from the manifests: one manual for all of them.

    python3 tools/site/gen_manual.py          # also run by gen_pages.py
    python3 tools/site/gen_manual.py --nav    # the manual's nav block for mkdocs.yml

The published remixes (release.REMIXES) share most of their features, so they
share one manual. Each page says which remixes have its feature; what is
particular to one remix is on that remix's overview page (the hand-written
remix-<name>.md at the site root). Written, gitignored like the rest of the
generated site, under reference/manual/ :

  index.md                  the introduction: the remixes, which feature is in which, the contents
  <section>/<module>.md     one page per feature a musician uses, in the section of PLACE
  brain/<part>.md           BRAIN, one page per part of it
  fixes.md                  every fix to stock behaviour, one section each
  inside.md                 what runs behind the scenes, one section each
  credits.md

A module is a page only when a musician operates it. The fixes and the
services other features rely on (STORE, EVENTS, the effect loader, ...) share
one page per section, so they are credited and explained without a chapter
each. A module that is part of another feature's use (RIG HOSTS and FX2 LOCK
of the bus, the VERB rows of VERBERATION) is a section of that feature's page
(FOLD). Stock effects are not documented here.

What can be read from the manifests is: which chooser an effect is in, the
knob layout of its two pages (A to F, the MODE renames), the settings and what
each remix sets them to. The prose is the hand-written usage fragment of each
module (the site's usage directory); its own Parameters table is dropped, since
the knobs are printed from the manifest, and so are its development sections
(DROP_SECTIONS: dated change notes, test records). A module with no fragment
gets its manifest line, so the manual never has a hole. BRAIN's pages are the
fragments docs/site/manual/brain-<part>.md.

The pages are listed by hand in the nav of mkdocs.yml (`--nav` prints the
block); tools/verify/verify_docs.py refuses a nav that does not match
pages_of() and a page that carries build or test text (LEAKS).
"""

import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)

import gen_pages  # noqa: E402
from gen_pages import OUT, _author, _label, title_case  # noqa: E402
from remix.schema import Category, Formatter, Option, Binary, Number, Pin, Trigger, Blob  # noqa: E402

USAGE = OUT.parent / pathlib.Path("usage")
INTROS = OUT.parent / pathlib.Path("manual")

# (folder, title) in the order a reader meets them. "fixes" and "inside" are one page each (COMBINED).
SECTIONS = (
    ("effects", "Effects"),
    ("bus", "The delay and reverb bus"),
    ("machines", "Machines"),
    ("sequencer", "Sequencer and recording"),
    ("parts", "Parts, Kits and scenes"),
    ("midi-usb", "MIDI and USB"),
    ("brain", "BRAIN"),
    ("utilities", "Utilities"),
    ("fixes", "Fixes to stock behaviour"),
    ("inside", "Behind the scenes"),
)
COMBINED = {
    "fixes": "Corrections to how stock OS 1.40C behaves. None of them has a control: each one is "
             "simply on in every image that has it.",
    "inside": "Services the features in this manual rely on. None of them has a menu or anything to "
              "set; they are listed here so that what you may notice has an explanation, and so that "
              "each is credited to its author.",
}
# The order of the Behind the scenes page: what a musician can notice first.
INSIDE_ORDER = ("DLPUMP", "DLCOPY", "LOAD METER", "MEMORY", "STORE", "PAGES", "EVENTS", "HOOKS",
                "KEYBUS", "SC KEYBUS BRIDGE", "SC LOAD METER BRIDGE", "REMOTE")

# Where a module's page goes, by registry key. A module not named here goes by its
# category (BY_CATEGORY), so a new module is never left out of the manual.
PLACE = {
    "OCTA303": "machines", "WAVE CF": "machines",
    "DELAY SERVER": "bus", "REVERB SERVER": "bus", "SEND": "bus", "TEMPO BUS": "bus",
    "DIRECT_JUMP_KYOTI": "sequencer", "RELOAD_FROM_PROJECT": "sequencer", "RLEN PLEN": "sequencer",
    "REC_TRIG_MUTE": "sequencer", "REC THRESHOLD": "sequencer", "PATTERN MUTE": "sequencer",
    "MUTE_MODES": "sequencer", "SCALE QUANTIZER": "sequencer", "QUANTIZE_LIVE_REC_TOGGLE": "sequencer",
    "SEQ": "sequencer", "TRACK PATTERNS": "sequencer",
    "KITS": "parts", "MIDI SCENES": "parts", "SCENES P2": "parts", "PLOCKS P2": "parts", "MORPH": "parts",
    "CC MAP": "midi-usb", "CC FEEDBACK": "midi-usb", "USB": "midi-usb",
    "BRAIN": "brain",
    "COPY PROJECT": "utilities", "BUFFER SAVER": "utilities", "MODE DEFAULTS": "utilities",
    "REMIX SWITCH": "utilities", "SCOPE": "utilities", "TUNER": "utilities",
    "LOFI AMF FIX": "fixes", "RECORDER LOOP FIX": "fixes", "BATCH_BUGFIXES": "fixes",
    "ERASE_EMPTY_TRIGLESS_LOCKS": "fixes", "ATA WRITE GUARD": "fixes", "FRAME GUARD": "fixes",
    "REC CS1 SKIP": "fixes",
    "EVENTS": "inside", "STORE": "inside", "HOOKS": "inside", "MEMORY": "inside",
    "DLPUMP": "inside", "DLCOPY": "inside", "LOAD METER": "inside", "KEYBUS": "inside",
    "PAGES": "inside", "REMOTE": "inside", "SC KEYBUS BRIDGE": "inside", "SC LOAD METER BRIDGE": "inside",
}
BY_CATEGORY = {
    Category.TRACK: "effects", Category.MACHINES: "sequencer", Category.PARTS: "parts",
    Category.MIDI_USB: "midi-usb", Category.SETTINGS: "inside", Category.UTILITIES: "utilities",
    Category.FIXES: "fixes", Category.BUS: "bus", Category.REFERENCE: "inside",
}
# A module that is part of another feature's use: a section of that feature's page, not a page.
FOLD = {
    "RIG HOSTS": "SEND", "FX2 LOCK": "SEND", "TEMPO SYNC": "DELAY SERVER",
    "VERB PLATE": "VERBERATION", "VERB ROOM": "VERBERATION", "VERB HALL": "VERBERATION",
    "VERB PARTS": "VERBERATION",
}
# A page title in the manual where the Feature Directory's label tells two modules apart.
MANUAL_LABEL = {"direct-jump-kyoti": "Direct Jump"}

# Sections of a usage fragment that record its development, not its use: kept on the
# module's own page in the Feature Directory, left out of the manual.
DROP_SECTIONS = re.compile(r"(?i)^(changed on|checked|verification|hardware|tested|status|history)\b")
# Text no manual page may carry: build and test vocabulary, and values printed from Python.
LEAKS = (
    (r"\btest remix", "names a test remix"),
    (r"\bemulator\b", "reports an emulator result"),
    (r"\bin the same image\b", "lists a build dependency"),
    (r"\bChanged on \d", "carries a change note"),
    (r"µs\b|\bISR\b", "carries a timing measurement"),
    (r"(?<![\w`])b'[^']*'", "prints a Python bytes value"),
    (r"\bnot in an official remix\b", "says the feature is unpublished"),
)

# BRAIN is one section with a page per part of it; the text of each is docs/site/manual/brain-<part>.md.
BRAIN_PAGES = (
    ("index", "BRAIN"), ("templates", "Templates"), ("remixes", "Remixes"), ("settings", "Settings"),
    ("performance", "Performance"), ("log", "Log"), ("about", "About"), ("files", "Files on the card"),
)

# Screenshots of the manifests' records that show another remix's screen, not shown in the manual.
HIDE_SHOTS = set()

TITLES = {"octabam": "Octabam", "octabam-verbs": "Octabam Verbs", "octabam-bus": "Octabam Bus"}
OVERVIEW = {"octabam": "remix-octabam.md", "octabam-verbs": "remix-octabam-verbs.md",
            "octabam-bus": "remix-octabam-bus.md"}
MANUAL = "Octabam Manual"
# One line per remix for the manual's introduction (Remix.doc is written for whoever builds it).
SUMMARY = {
    "octabam": "the core features, all 14 stock effects, SCOPE and TUNER, the WAVE machine, and "
               "SPECTRUM, CHARACTER, MODULATION and SHATTER.",
    "octabam-verbs": "Octabam with VERBERATION in place of the three stock reverbs, and VIBRATO, "
                     "TRANSIENT and RESONATOR; no SCOPE and no WAVE machine.",
    "octabam-bus": "the core features around a delay and reverb bus on FX2, with a send from every track; "
                   "FX1 has SPECTRUM, CHARACTER and MODULATION, and 13 stock effects give way to the bus.",
}
KNOB = "ABCDEF"


def title(name: str) -> str:
    return TITLES.get(name, title_case(name.replace("-", " ")))


def label(m) -> str:
    return title_case(MANUAL_LABEL[m.name]) if m.name in MANUAL_LABEL else _label(m)


def slug(text: str) -> str:
    """A heading's anchor, as both MkDocs and GitHub spell it for a plain heading."""
    return re.sub(r"[\s]+", "-", re.sub(r"[^\w\s-]", "", text.lower()).strip())


# ---- placement ----------------------------------------------------------

def _drawn(m) -> bool:
    return m.menu is not None and any(p.active for p in m.params)


def section_of(m) -> str:
    if m.key in PLACE:
        return PLACE[m.key]
    return "effects" if _drawn(m) else BY_CATEGORY.get(m.category or Category.REFERENCE, "inside")


class Book:
    """The published remixes and the modules their manual documents."""

    def __init__(self, mods, official):
        self.mods = mods
        self.official = list(official)            # [(name, remix)]
        self.has: dict[str, list[str]] = {}       # module key -> the remixes that have it, in release order
        for name, r in self.official:
            for k in r.modules:
                m = mods.get(k)
                if m is None or m.is_stock:
                    continue
                self.has.setdefault(k, []).append(name)

    def documented(self):
        return [self.mods[k] for k in self.has]

    def placed(self) -> dict[str, list]:
        """The modules with a page or a section of a combined page, by section, each section by label.
        BRAIN has its own pages; a folded module is a section of its host's page."""
        out: dict[str, list] = {}
        for m in self.documented():
            if m.key == "BRAIN" or self.host(m) is not None:
                continue
            out.setdefault(section_of(m), []).append(m)
        for s, ms in out.items():
            if s == "inside":
                ms.sort(key=lambda m: (INSIDE_ORDER.index(m.key) if m.key in INSIDE_ORDER else 99, label(m).lower()))
            else:
                ms.sort(key=lambda m: label(m).lower())
        return out

    def host(self, m):
        """The module whose page this one is a section of, when that module is published too."""
        k = FOLD.get(m.key)
        return self.mods[k] if k in self.has else None

    def folded(self, m) -> list:
        return sorted((x for x in self.documented() if FOLD.get(x.key) == m.key and x.key != m.key),
                      key=lambda x: (not _drawn(x), label(x).lower()))

    def page_of(self, m) -> str:
        """Where the module is described under the manual folder: a page, without the extension,
        and an anchor when it is a section of a page."""
        if m.key == "BRAIN":
            return "brain/index"
        h = self.host(m)
        if h is not None:
            return f"{self.page_of(h)}#{slug(label(m))}"
        s = section_of(m)
        return f"{s}#{slug(label(m))}" if s in COMBINED else f"{s}/{m.name}"

    def pages(self) -> list[str]:
        """The page names (no extension) of the manual, in nav order."""
        groups = self.placed()
        out = ["index"]
        for folder, _ in SECTIONS:
            if folder == "brain":
                if "BRAIN" in self.has:
                    out += [f"brain/{p}" for p, _ in BRAIN_PAGES]
            elif folder in COMBINED:
                if groups.get(folder):
                    out.append(folder)
            else:
                out += [f"{folder}/{m.name}" for m in groups.get(folder, [])]
        return out + ["credits"]

    def where_in(self, m) -> str:
        names = self.has.get(m.key, [])
        if len(names) == len(self.official):
            return "all three remixes" if len(names) == 3 else "every remix"
        return _and([title(n) for n in names])

    def remix(self, name):
        return dict(self.official)[name]


_NUM = {2: "two", 3: "three", 4: "four", 5: "five"}


def _and(words: list[str]) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def _rel(here: str, target: str) -> str:
    """A link from the page `here` to `target` (both without the extension; target may carry an anchor)."""
    page, _, anchor = target.partition("#")
    if page == here:
        return f"#{anchor}" if anchor else f"{os.path.basename(page)}.md"
    link = os.path.relpath(page + ".md", os.path.dirname(here) or ".")
    return link + (f"#{anchor}" if anchor else "")


def _up(here: str) -> str:
    """From a page of reference/manual/ to the site root."""
    return "../" * (2 + here.count("/"))


# ---- the fragment -------------------------------------------------------

def _relink(text: str, here: str, book: Book, extra: dict | None = None) -> str:
    """A fragment is written for a page of the site's reference/modules/: its site
    links climb two levels and its sibling links are bare file names. Both are
    pointed at where this page is; a sibling that is not in this manual loses its link."""
    known = {m.name: book.page_of(m) for m in book.documented()}
    known["brain"] = "brain/index"
    known.update(extra or {})
    up = _up(here)
    text = re.sub(r"\]\(\.\./\.\./brain\.md(#[\w-]+)?\)",
                  lambda mt: "](" + _rel(here, "brain/index") + (mt.group(1) or "") + ")", text)
    text = re.sub(r"\]\(\.\./\.\./(?!\.\./)", "](" + up, text)

    def sibling(mt):
        lab, name, anchor = mt.group(1), mt.group(2), mt.group(3) or ""
        if name not in known:
            return lab
        target = known[name]
        if anchor and "#" not in target:
            target += anchor
        return f"[{lab}]({_rel(here, target)})"

    return re.sub(r"\[([^\]]+)\]\((?!https?:|#|\.\./|/)([\w-]+)\.md(#[\w-]+)?\)", sibling, text)


def _drop_sections(text: str, drop_parameters: bool) -> str:
    """Drop a fragment's own Parameters table (the manual prints the knobs from the manifest,
    the one place a knob's name, range and default are declared) and its development sections."""
    parts = re.split(r"(?m)^(?=## )", text)
    keep = []
    for part in parts:
        head = part[3:].split("\n", 1)[0].strip() if part.startswith("## ") else None
        if head is not None and (DROP_SECTIONS.match(head) or (drop_parameters and head == "Parameters")):
            continue
        keep.append(part)
    return "".join(keep).strip()


def _fragment(m, here: str, book: Book) -> str | None:
    path = USAGE / f"{m.name}.md"
    if not path.is_file():
        return None
    return _relink(_drop_sections(path.read_text().strip(), _drawn(m)), here, book)


def _demote(text: str) -> str:
    """A fragment's headings one level down, for a section of a page."""
    return re.sub(r"(?m)^(#{2,5}) ", lambda mt: "#" + mt.group(1) + " ", text)


def _shots(m) -> dict:
    return {k: rec for k, rec in gen_pages._page_records(m).items() if (m.name, k) not in HIDE_SHOTS}


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


def controls(m, level: int = 2) -> list[str]:
    """The two effect pages as the panel lays them out, then each knob."""
    lines = ["#" * level + " Controls", "",
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
                lab = mode.labels[v.mode] if mode.labels and v.mode < len(mode.labels) else str(v.mode)
                for s, name in sorted(names.items()):
                    lines.append(f"| {lab} | {KNOB[s % 6]} on page {s // 6 + 1} "
                                 f"({m.canon_name(s) or '—'}) | {name} |")
            lines.append("")
    return lines


def starting_values(m, host) -> list[str]:
    """A row of the host's chooser that starts the host's code at other values: the knobs that differ."""
    diff = [f"{p.name.decode()} {_default(p)}" for p, h in zip(m.params, host.params)
            if p.active and h.active and p.name == h.name and p.default != h.default]
    if not diff:
        return [f"Starts at the same values as {label(host)}.", ""]
    return [f"Starts at {label(host)}'s values except " + ", ".join(diff) + ".", ""]


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
    if isinstance(v, (bytes, bytearray)):
        return f"`{v.decode(errors='replace')}`" if v else "empty"
    return str(v)


def settings(m, book: Book, level: int = 2) -> list[str]:
    """The module's settings with the value each remix gives them: a pinned
    setting has no menu row and cannot be changed on the unit."""
    shown = [s for s in m.settings if s.apply.value != "build"]
    if not shown or m.store is None:
        return []
    lines = ["#" * level + " Settings", "",
             "| Setting | Values | Starts at | Takes effect | What it does |", "|---|---|---|---|---|"]
    applies = {"live": "at once", "callback": "after a load or an edit", "next_boot": "at the next boot"}
    for s in shown:
        per: dict[str, list[str]] = {}
        for name in book.has[m.key]:
            mine = book.remix(name).settings.get((m.store.id, s.name), s.default)
            now = (f"{_setting_value(s.kind, mine.value)} (fixed)" if isinstance(mine, Pin)
                   else _setting_value(s.kind, mine))
            per.setdefault(now, []).append(title(name))
        now = next(iter(per)) if len(per) == 1 else "; ".join(f"{v} in {_and(ns)}" for v, ns in per.items())
        when = applies[s.apply.value]
        when += " (stored with the project)" if s.scope.value == "project" else " (stored on the card)"
        doc = (s.doc or "").replace("|", "\\|")
        lines.append(f"| {s.name} | {_kind_text(s.kind)} | {now} | {when} | {doc} |")
    return lines + [""]


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


def _where_one(m, r) -> str:
    on = [n for n, ok in (("FX1", m.key in r.fx1), ("FX2", _on_fx2(m, r))) if ok]
    text = " and ".join(on)
    if m.key in r.locked:
        text += " (locked to its host track; the chooser cannot change it)"
    if m.menu.replaces:
        text += f", in place of {m.menu.replaces}"
    return text


def where(m, book: Book) -> str | None:
    """Which chooser an effect is in, read from each remix that has it."""
    if m.menu is None or m.is_stock:
        return None
    per: dict[str, list[str]] = {}
    for name in book.has[m.key]:
        per.setdefault(_where_one(m, book.remix(name)), []).append(title(name))
    if len(per) == 1:
        return next(iter(per))
    return "; ".join(f"{text} in {_and(ns)}" for text, ns in per.items())


# ---- pages ---------------------------------------------------------------

def _head(m, book: Book) -> list[str]:
    lines = [f"*By {_author(m)}. In {book.where_in(m)}.*", ""]
    place = where(m, book)
    if place:
        lines += [f"**Chooser:** {place}.", ""]
    return lines


# On a combined page the page says it once: no section repeats that it has nothing to operate.
_NOTHING = ("There is nothing to operate and nothing on the panel", "It has no controls and nothing on the panel",
            "Nothing on the panel", "It has no menu of its own", "Nothing to set")
NOTHING = re.compile(r"\s*(?:" + "|".join(t.replace(" ", r"\s+") for t in _NOTHING) + r")[.;]")


def _section(m, book: Book, here: str, host=None) -> list[str]:
    """A module as a section of a page: a folded module, or one of a combined page."""
    lines = [f"## {label(m)}", ""] + _head(m, book)
    recs = _shots(m)
    frag = _fragment(m, here, book)
    text = _demote(frag) if frag else m.doc
    if host is None:
        text = NOTHING.sub("", text)
    lines += [text, ""]
    if host is not None and _drawn(m) and _drawn(host):
        lines += starting_values(m, host)
    elif _drawn(m):
        lines += controls(m, level=3)
    lines += settings(m, book, level=3)
    for rec in recs.values():
        lines += _figure(rec, here)
    return lines


def module_page(m, book: Book) -> str:
    here = book.page_of(m)
    lines = [f"# {label(m)}", ""] + _head(m, book)
    recs = _shots(m)
    key = "main" if "main" in recs else next(iter(recs), None)
    if key:
        lines += _figure(recs[key], here)
    frag = _fragment(m, here, book)
    lines += [frag if frag else m.doc, ""]
    if _drawn(m):
        lines += controls(m)
    lines += settings(m, book)
    for x in book.folded(m):
        lines += _section(x, book, here, host=m)
    rest = [rec for k, rec in recs.items() if k != key]
    if rest:
        lines += ["## Screens", ""]
        for rec in rest:
            lines += _figure(rec, here)
    return "\n".join(lines).rstrip() + "\n"


def combined_page(folder: str, book: Book) -> str:
    here = folder
    heading = dict(SECTIONS)[folder]
    ms = book.placed().get(folder, [])
    lines = [f"# {heading}", "", COMBINED[folder], ""]
    lines += [f"- [{label(m)}](#{slug(label(m))})" for m in ms] + [""]
    for m in ms:
        lines += _section(m, book, here)
    return "\n".join(lines).rstrip() + "\n"


def brain_page(part: str, lab: str, book: Book) -> str:
    here = f"brain/{part}"
    path = INTROS / f"brain-{part}.md"
    brain = book.mods["BRAIN"]
    text = path.read_text().strip() if path.is_file() else brain.doc
    lines = [f"# {lab}", ""]
    if part == "index":
        lines += [f"*By {_author(brain)}. In {book.where_in(brain)}.*", ""]
    lines += [_relink(text, here, book, {p: f"brain/{p}" for p, _ in BRAIN_PAGES}), ""]
    if part == "index":
        lines += ["## The parts of BRAIN", ""]
        lines += [f"- [{t}]({p}.md)" for p, t in BRAIN_PAGES if p != "index"] + [""]
    return "\n".join(lines).rstrip() + "\n"


def credits_page(book: Book) -> str:
    by_who: dict[str, list] = {}
    for m in book.documented():
        name, url, _ = gen_pages.who(m)
        by_who.setdefault(url or name, []).append(m)
    body = ["Every feature in the published remixes was written by someone, and is credited here.", ""]
    for who, ms in sorted(by_who.items(), key=lambda kv: gen_pages.who(kv[1][0])[0].lower()):
        name, url, _ = gen_pages.who(ms[0])
        link = f"[{name}]({url})" if url else name
        items = sorted({(label(m), book.page_of(m)) for m in ms}, key=lambda t: t[0].lower())
        body.append(f"- {link}: " + ", ".join(f"[{t}]({_rel('credits', p)})" for t, p in items))
    return "\n".join(["# Credits", ""] + body) + "\n"


def _feature_rows(book: Book, mark, pages_only: bool = False) -> list[str]:
    """Every documented feature by section, one row each, with `mark(name, m)` per remix.
    With pages_only, a feature with a page of its own: no folded section, no combined page's."""
    rows = []
    groups = book.placed()
    for folder, sec in SECTIONS:
        if folder == "brain":
            ms = [book.mods["BRAIN"]] if "BRAIN" in book.has else []
        elif pages_only and folder in COMBINED:
            continue
        else:
            ms = list(groups.get(folder, []))
            for m in list(ms) if not pages_only else []:
                ms += book.folded(m)
            if folder != "inside":
                ms.sort(key=lambda m: label(m).lower())
        for m in ms:
            rows.append((sec, m, [mark(n, m) for n, _ in book.official]))
    return rows


def index_page(book: Book) -> str:
    import release
    here = "index"
    names = [n for n, _ in book.official]
    lines = [f"# {MANUAL}", "",
             f"This is the manual of Octabam {release.VERSION}: Octatrack OS 1.40C with features added, each "
             "credited to the person who wrote it. It assumes you know the stock Octatrack: tracks, Parts, "
             "patterns, scenes and the front panel. Stock effects and stock behaviour are in Elektron's own "
             "manual.", "",
             "## The remixes", "",
             f"There are {_NUM.get(len(names), len(names))} remixes, and they share most of their features, so they share this "
             "manual. Each page says which remixes have its feature. What is particular to one remix, and "
             "how to install it, is on its overview page:", ""]
    for n in names:
        doc = SUMMARY.get(n) or (book.remix(n).doc or "").strip().split("\n\n")[0].replace("\n", " ")
        lines.append(f"- [{title(n)}]({_up(here)}{OVERVIEW.get(n, 'index.md')}): {doc}")
    lines += ["",
              "## Conventions", "",
              "Names in capitals are what the unit's screen prints. Effects sit on the FX1 and FX2 keys; "
              "each has two pages of six knobs, A to F, reached with the PAGE keys as on any Octatrack effect. "
              "**Bold labels** are controls and menu items; an arrow is a menu path, as in "
              "**PROJ → BRAIN → TEMPLATES**; a plus sign is a key combination (hold **FUNC** while pressing "
              "the other key). Screen illustrations are captured firmware screens; their values are examples.", "",
              "## Which remix has what", "",
              "| Section | Feature | " + " | ".join(title(n) for n in names) + " |",
              "|---|---|" + "---|" * len(names)]
    last = None
    for sec, m, marks in _feature_rows(book, lambda n, m: "✓" if n in book.has.get(m.key, []) else "—",
                                       pages_only=True):
        lines.append(f"| {sec if sec != last else ''} | [{label(m)}]({_rel(here, book.page_of(m))}) | "
                     + " | ".join(marks) + " |")
        last = sec
    groups = book.placed()
    for folder, sec in SECTIONS:
        if folder in COMBINED and groups.get(folder):
            have = {n for m in groups[folder] for n in book.has[m.key]}
            lines.append(f"| {sec} | [all of them]({folder}.md) | "
                         + " | ".join("✓" if n in have else "—" for n in names) + " |")
    lines += ["", "[Credits](credits.md) lists every author.", "",
              "## Installing", "",
              f"Build the image from your own copy of OS 1.40C and install it as described in "
              f"[Build and Install]({_up(here)}web-builder.md). Nothing from Elektron is on this site; "
              f"the builder patches your copy in your browser. After the flash, SYSTEM STATUS → OS VERSION "
              f"shows the remix's name and the build number. Back up the card first. To go back to stock, "
              f"follow [Safety and Recovery]({_up(here)}safety.md).", ""]
    return "\n".join(lines) + "\n"


def manual(book: Book) -> dict[str, str]:
    """The pages of the manual, keyed by file name."""
    out = {"index.md": index_page(book), "credits.md": credits_page(book)}
    for folder, ms in book.placed().items():
        if folder in COMBINED:
            out[f"{folder}.md"] = combined_page(folder, book)
        else:
            for m in ms:
                out[f"{book.page_of(m)}.md"] = module_page(m, book)
    if "BRAIN" in book.has:
        for part, lab in BRAIN_PAGES:
            out[f"brain/{part}.md"] = brain_page(part, lab, book)
    return out


def remix_table(name: str, book: Book) -> list[str]:
    """The module table of a remix's overview page: every feature of the image with its page and author."""
    r = book.remix(name)
    rows = ["| Section | Feature | Author |", "|---|---|---|"]
    base = "reference/manual/"
    last = None
    for sec, m, _ in _feature_rows(book, lambda n, m: None):
        if name not in book.has.get(m.key, []):
            continue
        page, _, anchor = book.page_of(m).partition("#")
        rows.append(f"| {sec if sec != last else ''} | [{label(m)}]({base}{page}.md{'#' + anchor if anchor else ''}) "
                    f"| {_author(m)} |")
        last = sec
    stock = sorted((book.mods[k] for k in r.modules if k in book.mods and book.mods[k].is_stock),
                   key=lambda m: _label(m).lower())
    if stock:
        rows.append("| Stock effects | " + ", ".join(_label(m) for m in stock) + " | Elektron |")
    return rows


def published_pages(book: Book) -> dict[str, str]:
    """Module key -> where it is described under reference/manual/ (a page, with an anchor for a section)."""
    out = {}
    for m in book.documented():
        page, _, anchor = book.page_of(m).partition("#")
        out[m.key] = f"{page}.md" + (f"#{anchor}" if anchor else "")
    return out


def _q(text: str) -> str:
    """A nav label as YAML: quoted when it holds a colon or a quote."""
    return '"' + text.replace('"', '\\"') + '"' if re.search(r'[:#"\']', text) else text


def nav(book: Book) -> list[str]:
    """The manual's block of the mkdocs nav, four spaces to a level."""
    base = "reference/manual/"
    groups = book.placed()
    out = [f"  - {MANUAL}:", f"      - Introduction: {base}index.md"]
    for folder, sec in SECTIONS:
        if folder == "brain":
            if "BRAIN" in book.has:
                out.append(f"      - {sec}:")
                out += [f"          - {t}: {base}brain/{p}.md" for p, t in BRAIN_PAGES]
            continue
        ms = groups.get(folder, [])
        if not ms:
            continue
        if folder in COMBINED:
            out.append(f"      - {_q(sec)}: {base}{folder}.md")
            continue
        out.append(f"      - {_q(sec)}:")
        out += [f"          - {_q(label(m))}: {base}{folder}/{m.name}.md" for m in ms]
    out.append(f"      - Credits: {base}credits.md")
    return out


def leaks(pages: dict[str, str]) -> list[str]:
    """Build and test text on a manual page: (page, line, what)."""
    out = []
    for page, text in sorted(pages.items()):
        fence = False
        for n, line in enumerate(text.splitlines(), 1):
            if line.startswith("```"):
                fence = not fence
            if fence:
                continue
            for pat, why in LEAKS:
                if re.search(pat, line):
                    out.append(f"reference/manual/{page}:{n}: {why}: {line.strip()[:90]}")
    return out


def main(mods, official) -> dict[str, str]:
    """The manual pages, keyed by their path under reference/."""
    return {f"manual/{page}": text for page, text in manual(Book(mods, official)).items()}


if __name__ == "__main__":
    if "--nav" in sys.argv:
        from remix import registry
        import release
        print("\n".join(nav(Book(registry.modules(), [(n, registry.remix(n)) for n in release.REMIXES]))))
        sys.exit(0)
    sys.exit(gen_pages.main())
